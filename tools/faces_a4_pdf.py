#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Нарезка лиц с листов-сеток (белый фон) -> отдельные PNG -> A4 -> PDF для печати.

Особенность исходников: лица в столбцах СТЫКАЮТСЯ (подбородок верхнего касается
волос нижнего), поэтому чистых белых коридоров между рядами нет.
Алгоритм:
  1) столбцы разделяются по полностью белым вертикальным коридорам;
  2) внутри каждого столбца границы между лицами ищутся как "перешейки" —
     локальные минимумы профиля заполнения (там, где ширина силуэта минимальна);
  3) каждый вырез = столбец x (ряд в границах перешейка) + запас 12 px с обеих
     сторон перешейка, чтобы гарантированно не срезать ни подбородок, ни волосы;
  4) по горизонтали вырез затягивается по габаритам содержимого (там всегда белый фон);
  5) каждый вырез кладётся на A4 максимально крупно, по центру, без обрезки,
     пропорции сохраняются;
  6) собираются 2 PDF (1 лицо = 1 страница A4): без пересэмплирования (пиксели
     исходные, lossless) и с ресемплингом Lanczos под 300 dpi для печати;
  7) автоматическая проверка: 24 страницы, формат A4, картинка внутри полей,
     лицо не упирается в край выреза (кроме случаев, где обрезано уже в исходнике).
"""

import argparse
import json
import os
import re
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw

try:
    from scipy import ndimage
except Exception:
    ndimage = None

import pikepdf

MM = 72.0 / 25.4
A4_W_MM, A4_H_MM = 210.0, 297.0
MARGIN_MM = 10.0
DPI_A4 = 300
OVERLAP_PX = 12          # запас с каждой стороны перешейка
THR_INK = 250            # порог "не белого"
MIN_GAP = 20             # минимальная ширина белого коридора между столбцами
MIN_VALLEY_PROM = 30     # минимальная проминентность перешейка
MIN_VALLEY_DIST = 100    # минимальное расстояние между перешейками


def log(m=""):
    print(m, flush=True)


# ------------------------------------------------------------------ сегментация

def load_rgb_white(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im).convert("RGB")
    else:
        im = im.convert("RGB")
    return im


def ink_mask(im, thr=THR_INK):
    a = np.asarray(im).astype(np.int16)
    m = a.min(axis=2) <= thr
    if ndimage is not None:
        m = ndimage.binary_opening(m, structure=np.ones((3, 3), bool))
    return m


def runs_of(mask1d, min_len=1):
    idx = np.flatnonzero(np.diff(np.r_[0, mask1d.view(np.int8), 0]))
    return [(int(a), int(b)) for a, b in zip(idx[0::2], idx[1::2]) if b - a >= min_len]


def column_bands(ink, min_gap=MIN_GAP):
    """Столбцы лиц: разрез по полностью белым вертикальным полосам."""
    white_cols = ~ink.any(axis=0)
    gaps = runs_of(white_cols, min_len=0)
    bands, cur = [], 0
    for a, b in gaps:
        if b - a + 1 >= min_gap:
            if a > cur:
                bands.append((cur, a - 1))
            cur = b
    if cur < ink.shape[1]:
        bands.append((cur, ink.shape[1] - 1))
    return bands


def find_cuts(ink, x0, x1, min_prom=MIN_VALLEY_PROM, min_dist=MIN_VALLEY_DIST, win=80):
    """Границы между лицами внутри столбца: чистые белые полосы + перешейки."""
    prof = ink[:, x0:x1 + 1].sum(axis=1).astype(float)
    n = len(prof)
    cands = []

    # 1) полностью белые строки (если есть) — идеальный разрез.
    # полосы, примыкающие к краю листа, разрезом не являются (это просто фон над/под лицом)
    for a, b in runs_of(prof == 0, min_len=5):
        if a == 0 or b >= n - 1:
            continue
        cands.append((0.0, (a + b) // 2, "white"))

    # 2) перешейки — локальные минимумы профиля со значимой проминентностью
    k = 15
    sm = np.convolve(prof, np.ones(2 * k + 1) / (2 * k + 1), mode="same")
    edge = 35
    for y in range(edge, n - edge):
        lo, hi = max(0, y - win), min(n, y + win + 1)
        if sm[y] <= sm[lo:hi].min() + 1e-9:
            prom = min(sm[lo:y + 1].max(), sm[y:hi].max()) - sm[y]
            if prom >= min_prom:
                cands.append((float(-prom), y, "valley"))

    if not cands:
        return [], prof, sm

    cands.sort()
    chosen = []
    for _, y, kind in cands:
        if all(abs(y - y2) >= min_dist for _, y2, _ in chosen):
            chosen.append((0, y, kind))
    chosen.sort(key=lambda t: t[1])

    # при наличии белых разрезов убираем перешейки, попавшие в те же межрядовые зоны
    return [y for _, y, _ in chosen], prof, sm


def content_bbox(ink, x0, x1, y0, y1, min_area=300):
    sub = ink[y0:y1 + 1, x0:x1 + 1]
    if not sub.any():
        return None
    if ndimage is not None:
        lab, n = ndimage.label(sub, structure=np.ones((3, 3), bool))
        keep = np.zeros_like(sub)
        for i, sl in enumerate(ndimage.find_objects(lab), 1):
            if sl is None:
                continue
            m = lab[sl] == i
            if int(m.sum()) >= min_area:
                keep[sl] |= m
        if not keep.any():
            keep = sub
        ys, xs = np.nonzero(keep)
    else:
        ys, xs = np.nonzero(sub)
    return (x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()), y0 + int(ys.max()))


def extract_faces(path, overlap=OVERLAP_PX, verbose=True):
    im = load_rgb_white(path)
    ink = ink_mask(im)
    H, W = ink.shape
    bands = column_bands(ink)
    faces, diag = [], {"file": os.path.basename(path), "size": [W, H], "columns": [], }
    for ci, (x0, x1) in enumerate(bands, 1):
        cuts, prof, sm = find_cuts(ink, x0, x1)
        edges = [0] + cuts + [H - 1]
        col_info = {"column": ci, "x": [x0, x1], "cuts": cuts, "faces": []}
        for k in range(len(edges) - 1):
            ty, by = edges[k], edges[k + 1]
            y0 = 0 if k == 0 else max(0, ty - overlap)
            y1 = H - 1 if k == len(edges) - 2 else min(H - 1, by + overlap)
            bb = content_bbox(ink, x0, x1, y0, y1)
            if bb is None:
                continue
            bx0, by0, bx1, by1 = bb
            if (by1 - by0 + 1) < 60 or (bx1 - bx0 + 1) * (by1 - by0 + 1) < 1200:
                if verbose:
                    log(f"    отброшен огрызок в столбце {ci} ряды {y0}-{y1} "
                        f"({bx1 - bx0 + 1}x{by1 - by0 + 1} px)")
                continue
            # Кадрируем по габариту содержимого (лицо + возможная часть соседа в зоне стыка)
            # и добавляем белый запас, чтобы ни лицо, ни пиксели соседа не упирались в край.
            pad_x, pad_y = 8, 12
            cx0, cx1 = max(0, bx0 - pad_x), min(W - 1, bx1 + pad_x)
            cy0, cy1 = max(0, by0 - pad_y), min(H - 1, by1 + pad_y)
            crop = im.crop((cx0, cy0, cx1 + 1, cy1 + 1))
            # содержимое строгой полосы ряда (без зоны перекрытия) = само лицо
            band = content_bbox(ink, x0, x1, ty, by, min_area=200) or bb
            faces.append({
                "img": crop, "src": os.path.basename(path),
                "col": ci, "row": k + 1,
                "box": [cx0, cy0, cx1 + 1, cy1 + 1],
                "content": [bx0, by0, bx1, by1],
                "face_band": list(band),
                "cut_top": ty, "cut_bottom": by,
                "crop_w": crop.width, "crop_h": crop.height,
                "src_w": W, "src_h": H,
            })
            col_info["faces"].append({"row": k + 1, "cuts": [ty, by], "crop": [crop.width, crop.height]})
        diag["columns"].append(col_info)
        if verbose:
            log(f"  столбец {ci}: x {x0}-{x1}, лиц {len(col_info['faces'])}, "
                f"перешейки {cuts}")
    diag["faces"] = len(faces)
    return faces, diag


# ------------------------------------------------------------------ A4 / PDF

def fit_rect(px_w, px_h, margin_mm=MARGIN_MM, allow_upscale=True):
    aw, ah = A4_W_MM - 2 * margin_mm, A4_H_MM - 2 * margin_mm
    k = min(aw / px_w, ah / px_h)
    if not allow_upscale:
        k = min(k, 1.0)
    w_mm, h_mm = px_w * k, px_h * k
    return (A4_W_MM - w_mm) / 2.0, (A4_H_MM - h_mm) / 2.0, w_mm, h_mm


class PDF:
    def __init__(self):
        self.objs = [None]

    def add(self, payload):
        self.objs.append(payload)
        return len(self.objs) - 1

    def reserve(self):
        self.objs.append(None)
        return len(self.objs) - 1

    def set(self, n, payload):
        self.objs[n] = payload

    def write(self, path):
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offs = [0] * len(self.objs)
        for i in range(1, len(self.objs)):
            offs[i] = len(out)
            out += f"{i} 0 obj\n".encode() + self.objs[i] + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(self.objs)}\n".encode() + b"0000000000 65535 f \n"
        for i in range(1, len(self.objs)):
            out += f"{offs[i]:010d} 00000 n \n".encode()
        out += (f"trailer\n<< /Size {len(self.objs)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n").encode()
        open(path, "wb").write(bytes(out))
        return path


def a4_pdf(items, out_path, margin_mm=MARGIN_MM, allow_upscale=True):
    """items: [(PIL.Image, имя)] -> PDF A4, по одному изображению на страницу (lossless)."""
    pdf = PDF()
    catalog = pdf.reserve()
    pages_obj = pdf.reserve()
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode())
    kids, placed = [], []
    for img, name in items:
        rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
        h, w = rgb.shape[:2]
        data = zlib.compress(rgb.tobytes(), 9)
        im_obj = pdf.reserve()
        pdf.set(im_obj, (
            f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
            f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} /Interpolate true >>\nstream\n"
        ).encode() + data + b"\nendstream")

        x_mm, y_mm, w_mm, h_mm = fit_rect(w, h, margin_mm, allow_upscale)
        iw, ih = w_mm * MM, h_mm * MM
        x_pt, y_pt = x_mm * MM, (A4_H_MM - y_mm - h_mm) * MM
        content = f"q {iw:.4f} 0 0 {ih:.4f} {x_pt:.4f} {y_pt:.4f} cm /Im0 Do Q".encode()
        c_obj = pdf.add(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
        page = pdf.add((
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {A4_W_MM * MM:.4f} {A4_H_MM * MM:.4f}] "
            f"/Resources << /XObject << /Im0 {im_obj} 0 R >> /ProcSet [/PDF /ImageC] >> "
            f"/Contents {c_obj} 0 R >>").encode())
        kids.append(f"{page} 0 R")
        placed.append({"name": name, "px": [w, h], "mm": [round(w_mm, 1), round(h_mm, 1)],
                       "dpi": round(w / (w_mm / 25.4), 1)})
    pdf.set(pages_obj, f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(kids)}] >>".encode())
    pdf.write(out_path)
    return placed


def a4_pdf_jpeg(items, out_path, margin_mm=MARGIN_MM, quality=95):
    """PDF A4: изображения кладутся в JPEG (для печати, компактный файл)."""
    from io import BytesIO
    pdf = PDF()
    catalog = pdf.reserve()
    pages_obj = pdf.reserve()
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode())
    kids, placed = [], []
    for img, name in items:
        rgb = img.convert("RGB")
        bio = BytesIO()
        rgb.save(bio, "JPEG", quality=quality, subsampling=0, optimize=True)
        data = bio.getvalue()
        w, h = rgb.size
        im_obj = pdf.reserve()
        pdf.set(im_obj, (
            f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
            f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(data)} >>\nstream\n"
        ).encode() + data + b"\nendstream")
        x_mm, y_mm, w_mm, h_mm = fit_rect(w, h, margin_mm, True)
        content = (f"q {w_mm * MM:.4f} 0 0 {h_mm * MM:.4f} {x_mm * MM:.4f} "
                   f"{(A4_H_MM - y_mm - h_mm) * MM:.4f} cm /Im0 Do Q").encode()
        c_obj = pdf.add(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
        page = pdf.add((
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {A4_W_MM * MM:.4f} {A4_H_MM * MM:.4f}] "
            f"/Resources << /XObject << /Im0 {im_obj} 0 R >> /ProcSet [/PDF /ImageC] >> "
            f"/Contents {c_obj} 0 R >>").encode())
        kids.append(f"{page} 0 R")
        placed.append({"name": name, "px": [w, h], "mm": [round(w_mm, 1), round(h_mm, 1)],
                       "dpi": round(w / (w_mm / 25.4), 1)})
    pdf.set(pages_obj, f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(kids)}] >>".encode())
    pdf.write(out_path)
    return placed


def verify_pdf(path, expect, margin_mm=MARGIN_MM):
    res = {"file": os.path.basename(path), "pages": 0, "a4": True, "inside": True, "problems": []}
    with pikepdf.open(path) as pdf:
        res["pages"] = len(pdf.pages)
        if res["pages"] != expect:
            res["problems"].append(f"страниц {res['pages']}, ожидалось {expect}")
        tol, lo = 1.0, margin_mm * MM - 1.0
        dpi_min = None
        for i, page in enumerate(pdf.pages, 1):
            mb = [float(v) for v in page.MediaBox]
            if abs((mb[2] - mb[0]) - A4_W_MM * MM) > 2 or abs((mb[3] - mb[1]) - A4_H_MM * MM) > 2:
                res["a4"] = False
                res["problems"].append(f"стр.{i}: не A4")
                continue
            xo = page.Resources.get("/XObject")
            imgs = [] if xo is None else [v for v in xo.values() if str(v.get("/Subtype")) == "/Image"]
            if len(imgs) != 1:
                res["problems"].append(f"стр.{i}: картинок {len(imgs)}")
                continue
            m = re.search(r"([-\d.]+) 0 0 ([-\d.]+) ([-\d.]+) ([-\d.]+) cm",
                          page.Contents.read_bytes().decode("latin-1"))
            if not m:
                res["problems"].append(f"стр.{i}: нет матрицы")
                continue
            iw, ih, x, y = (float(g) for g in m.groups())
            if iw / ih > 5 or ih / iw > 5 or iw < 1 or ih < 1:
                res["problems"].append(f"стр.{i}: странные пропорции")
            if x < lo - .5 or y < lo - .5 or x + iw > A4_W_MM * MM - lo + .5 or y + ih > A4_H_MM * MM - lo + .5:
                res["inside"] = False
                res["problems"].append(f"стр.{i}: за полями")
            d = int(imgs[0].Width) / (iw / 72.0)
            dpi_min = d if dpi_min is None else min(dpi_min, d)
        res["min_dpi"] = round(dpi_min, 1) if dpi_min else None
    res["ok"] = not res["problems"]
    return res


def contact_sheet(items, out_path, cols=6, cell=420):
    rows = (len(items) + cols - 1) // cols
    ch = int(cell * 1.35)
    sheet = Image.new("RGB", (cols * cell, rows * ch), (232, 232, 232))
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(items):
        c, r = i % cols, i // cols
        x, y = c * cell, r * ch
        d.rectangle([x + 2, y + 2, x + cell - 3, y + ch - 3], fill=(255, 255, 255), outline=(120, 120, 120))
        d.text((x + 10, y + 8), label, fill=(0, 0, 0))
        t = im.copy()
        t.thumbnail((cell - 32, ch - 56), Image.LANCZOS)
        sheet.paste(t, (x + (cell - t.width) // 2, y + 30))
    sheet.save(out_path)
    return out_path


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True)
    ap.add_argument("--out", default="result")
    ap.add_argument("--overlap", type=int, default=OVERLAP_PX)
    ap.add_argument("--margin", type=float, default=MARGIN_MM)
    ap.add_argument("--expect", type=int, default=24)
    args = ap.parse_args()

    d_crop = os.path.join(args.out, "01_лица")
    d_a4 = os.path.join(args.out, "02_страницы_A4_300dpi")
    d_chk = os.path.join(args.out, "03_проверка")
    for d in (d_crop, d_a4, d_chk):
        os.makedirs(d, exist_ok=True)

    diags, faces = [], []
    for p in args.src:
        log(f"[{os.path.basename(p)}]")
        f, diag = extract_faces(p, overlap=args.overlap)
        diags.append(diag)
        faces.extend(f)

    total = len(faces)
    log(f"\nВСЕГО ЛИЦ: {total}")

    # сортировка: лист -> столбец -> ряд
    faces.sort(key=lambda f: (f["src"], f["col"], f["row"]))
    for i, f in enumerate(faces, 1):
        f["name"] = f"{i:02d}"

    thumbs, checks, raw_items, smooth_items = [], [], [], []
    for f in faces:
        im = f["img"]
        png = os.path.join(d_crop, f"lice_{f['name']}.png")
        im.save(png, "PNG", optimize=True, compress_level=9)
        f["png"] = png
        t = im.copy()
        t.thumbnail((1000, 1000), Image.LANCZOS)
        thumbs.append((f"{f['name']} · {im.width}x{im.height}", t))

        # проверка: лицо целиком внутри выреза? (по контенту внутри выреза)
        ink = ink_mask(im)
        bb = content_bbox(ink, 0, im.width - 1, 0, im.height - 1, min_area=200)
        marg = None
        if bb:
            marg = [bb[1], im.height - 1 - bb[3], bb[0], im.width - 1 - bb[2]]  # top,bottom,left,right
        src_w, src_h = f["src_w"], f["src_h"]
        bx = f["box"]
        touches_src = {
            "top": bx[1] == 0, "bottom": bx[3] == src_h,
            "left": bx[0] == 0, "right": bx[2] == src_w,
        }
        fb = f["face_band"]                     # габарит самого лица в исходнике
        bx = f["box"]
        face_inside = (fb[0] >= bx[0] and fb[1] >= bx[1] and fb[2] <= bx[2] and fb[3] <= bx[3])
        checks.append({
            "имя": f["name"], "файл": f["src"], "столбец": f["col"], "ряд": f["row"],
            "лицо_целиком_в_вырезе": bool(face_inside),
            "лицо_в_исходнике_px": [fb[2] - fb[0] + 1, fb[3] - fb[1] + 1],
            "PNG": os.path.basename(png), "размер_px": [im.width, im.height],
            "вырез_в_исходнике": bx,
            "перешейки_столбца": [f["cut_top"], f["cut_bottom"]],
            "белое_поле_в_вырезе_px_сверху_снизу_слева_справа": marg,
            "вырез_касается_края_исходника": [k for k, v in touches_src.items() if v],
            "пропорции": round(im.width / im.height, 4),
        })

        raw_items.append((im, f"lice_{f['name']}"))
        x_mm, y_mm, w_mm, h_mm = fit_rect(im.width, im.height, args.margin, True)
        tw, th = max(1, round(w_mm / 25.4 * DPI_A4)), max(1, round(h_mm / 25.4 * DPI_A4))
        smooth = im.resize((tw, th), Image.LANCZOS)
        page = Image.new("RGB", (round(A4_W_MM / 25.4 * DPI_A4), round(A4_H_MM / 25.4 * DPI_A4)), (255, 255, 255))
        page.paste(smooth, (round(x_mm / 25.4 * DPI_A4), round(y_mm / 25.4 * DPI_A4)))
        page.save(os.path.join(d_a4, f"A4_{f['name']}.jpg"), "JPEG", quality=95, subsampling=0, optimize=True)
        smooth_items.append((smooth, f"lice_{f['name']}"))

    pdf_raw = os.path.join(args.out, "Лица_24_A4_печать_пиксели_без_изменений.pdf")
    pdf_up = os.path.join(args.out, "Лица_24_A4_печать_300dpi_сглаженный.pdf")
    pl_raw = a4_pdf(raw_items, pdf_raw, args.margin, allow_upscale=True)             # пиксели исходной нарезки
    pl_up = a4_pdf_jpeg(smooth_items, pdf_up, args.margin, quality=95)               # сглажено Lanczos под 300 dpi

    contact_sheet(thumbs, os.path.join(d_chk, "превью_24_лиц.png"))
    v_raw, v_up = verify_pdf(pdf_raw, total, args.margin), verify_pdf(pdf_up, total, args.margin)

    not_full = [c["имя"] for c in checks if not c["лицо_целиком_в_вырезе"]]
    report = {
        "исходники": diags,
        "лиц_всего": total,
        "лиц_целиком_в_вырезе": total - len(not_full),
        "лиц_с_обрезкой_вырезом": not_full,
        "ожидалось": args.expect,
        "совпадает": total == args.expect,
        "нарезка": checks,
        "PDF": [
            {"файл": os.path.basename(pdf_raw), "описание": "пиксели исходные, масштабирование страницей",
             "проверка": v_raw, "страницы": pl_raw},
            {"файл": os.path.basename(pdf_up), "описание": "страницы A4 300 dpi, сглаживание Lanczos",
             "проверка": v_up, "страницы": pl_up},
        ],
        "каталоги": {"лица": d_crop, "A4": d_a4, "проверка": d_chk},
    }
    with open(os.path.join(d_chk, "отчёт.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    log("\n=== ПРОВЕРКА PDF ===")
    for v in (v_raw, v_up):
        log(f"{v['file']}: страниц {v['pages']}, A4={v['a4']}, внутри полей={v['inside']}, "
            f"мин. плотность {v['min_dpi']} dpi, проблемы: {v['problems'] or 'нет'}")
    log("\n=== ПРОВЕРКА НАРЕЗКИ ===")
    for c in checks:
        log(f"  {c['имя']}: {c['размер_px'][0]}x{c['размер_px'][1]} px, поле(бтлп)="
            f"{c['белое_поле_в_вырезе_px_сверху_снизу_слева_справа']}, "
            f"у края исходника: {c['вырез_касается_края_исходника'] or 'нет'}")
    log(f"\nлиц: {total} (ожидалось {args.expect}) -> {'ОК' if total == args.expect else 'ПРОБЛЕМА'}")
    log(f"лиц целиком в вырезе: {total - len(not_full)}/{total}; обрезанных вырезом: {not_full or 'нет'}")


if __name__ == "__main__":
    main()
