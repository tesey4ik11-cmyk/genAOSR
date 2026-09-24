#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Нарезка лиц (портретов) с листов-сеток на белом фоне + раскладка на A4 + PDF для печати.

1. Находит на каждом исходнике отдельные лица (сегментация по белому фону,
   разрезы по белым "коридорам" между лицами).
2. Вырезает каждое лицо отдельным PNG БЕЗ пересэмплирования (пиксель-в-пиксель).
3. Кладёт лицо на страницу A4 максимально крупно, по центру, без обрезки и без
   искажения пропорций (поле 10 мм).
4. Собирает PDF: 1 лицо = 1 страница A4. Пиксели не пережимаются (Flate, lossless).
5. Проверяет результат: число страниц, формат A4, положение внутри полей,
   и что каждое лицо целиком попало в кадр (белый запас вокруг лица).

Запуск:
  PYTHONPATH=/home/user/.cache/pyvendor python3 tools/cut_faces_a4.py --out faces --src <файлы>
"""

import argparse
import glob
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


MM = 72.0 / 25.4               # мм -> пункты PDF (1 pt = 1/72")
A4_W_MM, A4_H_MM = 210.0, 297.0
MARGIN_MM = 10.0               # поля страницы
DPI_A4 = 300                   # только для растровых A4-страниц


def log(msg=""):
    print(msg, flush=True)


# ------------------------------------------------------------------ анализ исходника

def load_rgb_white(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im).convert("RGB")
    else:
        im = im.convert("RGB")
    return im


def ink_mask(rgb, thr=246):
    arr = np.asarray(rgb, dtype=np.uint8)
    return arr.min(axis=2) < thr


def runs_of(mask_1d):
    idx = np.flatnonzero(np.diff(np.r_[0, mask_1d.view(np.int8), 0]))
    return [(int(a), int(b) - 1) for a, b in zip(idx[0::2], idx[1::2])]


def bands_by_gutters(ink, min_gap):
    """Полосы по полностью белым коридорам (гарантия: коридор не пересекает ни одно лицо)."""
    h, w = ink.shape
    row_gaps = [r for r in runs_of(~ink.any(axis=1)) if (r[1] - r[0] + 1) >= min_gap]
    col_gaps = [r for r in runs_of(~ink.any(axis=0)) if (r[1] - r[0] + 1) >= min_gap]

    def bands(gaps, size):
        out, cur = [], 0
        for a, b in gaps:
            if a > cur:
                out.append((cur, a - 1))
            cur = b + 1
        if cur <= size - 1:
            out.append((cur, size - 1))
        return out

    return bands(row_gaps, h), bands(col_gaps, w), row_gaps, col_gaps


def tight_box(ink, x0, y0, x1, y1, min_area):
    """Габаритный прямоугольник «не белого» в ячейке (мелкий шум по площади отбрасываем)."""
    sub = ink[y0:y1 + 1, x0:x1 + 1]
    if not sub.any():
        return None
    if ndimage is not None:
        lab, n = ndimage.label(sub, structure=np.ones((3, 3), int))
        keep = np.zeros_like(sub)
        for i in range(1, n + 1):
            m = lab == i
            if int(m.sum()) >= min_area:
                keep |= m
        if not keep.any():
            return None
        ys, xs = np.nonzero(keep)
    else:
        ys, xs = np.nonzero(sub)
    return (x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()), y0 + int(ys.max()))


def analyse_sheet(path, pad_frac, min_area=400, min_gap=6):
    rgb = load_rgb_white(path)
    ink = ink_mask(rgb)
    H, W = ink.shape
    ybands, xbands, row_gaps, col_gaps = bands_by_gutters(ink, min_gap)

    info = {
        "file": os.path.basename(path), "size": [W, H],
        "grid": [len(ybands), len(xbands)],
        "row_gaps": row_gaps, "col_gaps": col_gaps,
        "cells": len(ybands) * len(xbands),
    }

    faces = []
    for (cy0, cy1) in ybands:
        for (cx0, cx1) in xbands:
            tb = tight_box(ink, cx0, cy0, cx1, cy1, min_area)
            if tb is None:
                continue
            bx0, by0, bx1, by1 = tb
            bw, bh = bx1 - bx0 + 1, by1 - by0 + 1
            pad = max(4, int(round(pad_frac * max(bw, bh))))
            x0, y0 = max(0, bx0 - pad), max(0, by0 - pad)
            x1, y1 = min(W - 1, bx1 + pad), min(H - 1, by1 + pad)
            crop = rgb.crop((x0, y0, x1 + 1, y1 + 1))
            faces.append({
                "crop_box": (x0, y0, x1 + 1, y1 + 1),
                "face_box": (bx0, by0, bx1, by1),
                "pad": pad,
                "img": crop,
                "face_inside": (bx0 >= x0 and by0 >= y0 and bx1 <= x1 and by1 <= y1),
                "source_edge": (bx0 == 0 or by0 == 0 or bx1 == W - 1 or by1 == H - 1),
            })

    info["faces"] = len(faces)
    info["faces_inside"] = sum(1 for f in faces if f["face_inside"])
    info["faces_at_source_edge"] = sum(1 for f in faces if f["source_edge"])
    return rgb, faces, info


def white_margin_around_face(crop, min_area=400):
    """Проверка выреза: возвращает запас белого (px) вокруг крупнейшего объекта в PNG.
    Запас 0 хотя бы с одной стороны = лицо упирается в край выреза (обрезано)."""
    ink = ink_mask(crop)
    if not ink.any():
        return None
    if ndimage is not None:
        lab, n = ndimage.label(ink, structure=np.ones((3, 3), int))
        sizes = ndimage.sum(ink, lab, range(1, n + 1))
        big = [i + 1 for i, s in enumerate(sizes) if s >= min_area]
        if not big:
            return None
        m = np.isin(lab, big)
    else:
        m = ink
    ys, xs = np.nonzero(m)
    h, w = ink.shape
    return [int(ys.min()), int(h - 1 - ys.max()), int(xs.min()), int(w - 1 - xs.max())]


# ------------------------------------------------------------------ A4 / PDF

def fit_rect(px_w, px_h, page_w_mm=A4_W_MM, page_h_mm=A4_H_MM, margin_mm=MARGIN_MM):
    avail_w, avail_h = page_w_mm - 2 * margin_mm, page_h_mm - 2 * margin_mm
    k = min(avail_w / px_w, avail_h / px_h)         # мм на пиксель
    w_mm, h_mm = px_w * k, px_h * k
    return (page_w_mm - w_mm) / 2.0, (page_h_mm - h_mm) / 2.0, w_mm, h_mm, k


class PDF:
    """Минимальный lossless-сборщик PDF: RGB-изображения через /FlateDecode, без пережатия."""

    def __init__(self):
        self.objs = [None]                       # 1-based

    def add(self, payload):
        self.objs.append(payload)
        return len(self.objs) - 1

    def reserve(self):
        self.objs.append(None)
        return len(self.objs) - 1

    def set(self, num, payload):
        self.objs[num] = payload

    def write(self, path):
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offs = [0] * len(self.objs)
        for i in range(1, len(self.objs)):
            offs[i] = len(out)
            out += f"{i} 0 obj\n".encode() + self.objs[i] + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(self.objs)}\n".encode()
        out += b"0000000000 65535 f \n"
        for i in range(1, len(self.objs)):
            out += f"{offs[i]:010d} 00000 n \n".encode()
        out += (f"trailer\n<< /Size {len(self.objs)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n").encode()
        with open(path, "wb") as f:
            f.write(bytes(out))
        return path


def add_a4_page(pdf, img, pages_obj, interpolate=True):
    """Страница A4 с одной картинкой: максимально крупно, по центру, без обрезки."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    h, w = rgb.shape[:2]
    img_obj = pdf.reserve()
    data = zlib.compress(rgb.tobytes(), 9)
    pdf.set(img_obj, (
        f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
        f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} /Interpolate {'true' if interpolate else 'false'} >>\n"
        f"stream\n").encode() + data + b"\nendstream")

    x_mm, y_mm, iw_mm, ih_mm, _ = fit_rect(w, h)
    x_pt, iw_pt, ih_pt = x_mm * MM, iw_mm * MM, ih_mm * MM
    y_pt = (A4_H_MM - y_mm - ih_mm) * MM          # от нижнего края листа

    content = f"q {iw_pt:.4f} 0 0 {ih_pt:.4f} {x_pt:.4f} {y_pt:.4f} cm /Im0 Do Q".encode()
    c_obj = pdf.add(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")

    page = pdf.add((
        f"<< /Type /Page /Parent {pages_obj} 0 R "
        f"/MediaBox [0 0 {A4_W_MM * MM:.4f} {A4_H_MM * MM:.4f}] "
        f"/Resources << /XObject << /Im0 {img_obj} 0 R >> /ProcSet [/PDF /ImageC] >> "
        f"/Contents {c_obj} 0 R >>").encode())
    return page, (x_mm, y_mm, iw_mm, ih_mm)


def build_pdf(items, out_path):
    """items: [(PIL.Image, name)] -> PDF, страниц столько же, сколько лиц."""
    pdf = PDF()
    catalog = pdf.reserve()                       # 1
    pages_obj = pdf.reserve()                     # 2
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode())
    kids, layout = [], []
    for img, name in items:
        p, rect = add_a4_page(pdf, img, pages_obj)
        kids.append(f"{p} 0 R")
        layout.append({"name": name, "placed_mm": [round(v, 2) for v in rect],
                       "pixels": [img.width, img.height]})
    pdf.set(pages_obj, (f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(kids)}] >>").encode())
    pdf.write(out_path)
    return layout


# ------------------------------------------------------------------ проверка PDF

def verify_pdf(path, expect_pages, margin_mm=MARGIN_MM):
    res = {"file": os.path.basename(path), "pages": 0, "a4": True, "inside_margins": True,
           "images_ok": True, "problems": []}
    with pikepdf.open(path) as pdf:
        res["pages"] = len(pdf.pages)
        if res["pages"] != expect_pages:
            res["problems"].append(f"страниц {res['pages']}, ожидалось {expect_pages}")
        tol = 1.0
        lo = margin_mm * MM - tol
        dpi_min = None
        for i, page in enumerate(pdf.pages, 1):
            mb = [float(v) for v in page.MediaBox]
            w_pt, h_pt = mb[2] - mb[0], mb[3] - mb[1]
            if abs(w_pt - A4_W_MM * MM) > 2 or abs(h_pt - A4_H_MM * MM) > 2:
                res["a4"] = False
                res["problems"].append(f"стр.{i}: размер {w_pt:.1f}x{h_pt:.1f} пт, не A4")
                continue
            xo = page.Resources.get("/XObject", None)
            imgs = [] if xo is None else [v for v in xo.values() if str(v.get("/Subtype", "")) == "/Image"]
            if len(imgs) != 1:
                res["images_ok"] = False
                res["problems"].append(f"стр.{i}: картинок {len(imgs)}, ожидалась 1")
                continue
            img = imgs[0]
            px_w, px_h = int(img.Width), int(img.Height)
            txt = page.Contents.read_bytes().decode("latin-1")
            m = re.search(r"([-\d.]+) 0 0 ([-\d.]+) ([-\d.]+) ([-\d.]+) cm", txt)
            if not m:
                res["problems"].append(f"стр.{i}: нет матрицы размещения")
                continue
            iw, ih, x, y = (float(g) for g in m.groups())
            if (x < lo - 0.5 or y < lo - 0.5 or x + iw > A4_W_MM * MM - lo + 0.5
                    or y + ih > A4_H_MM * MM - lo + 0.5):
                res["inside_margins"] = False
                res["problems"].append(f"стр.{i}: картинка за полями "
                                       f"(x={x / MM:.1f}мм y={y / MM:.1f}мм {iw / MM:.1f}x{ih / MM:.1f}мм)")
            if iw <= 0 or ih <= 0 or iw / ih > 10 or ih / iw > 10:
                res["images_ok"] = False
                res["problems"].append(f"стр.{i}: подозрительные пропорции {iw:.1f}x{ih:.1f}")
            dpi = px_w / (iw / 72.0)
            dpi_min = dpi if dpi_min is None else min(dpi_min, dpi)
        res["min_dpi_in_page"] = round(dpi_min, 1) if dpi_min else None
    res["ok"] = not res["problems"]
    return res


def contact_sheet(items, out_path, cols=6, thumb=330):
    rows = (len(items) + cols - 1) // cols
    cw, ch = thumb, int(thumb * 1.42)
    sheet = Image.new("RGB", (cols * cw, rows * ch), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(items):
        c, r = i % cols, i // cols
        x, y = c * cw, r * ch
        t = im.copy()
        t.thumbnail((cw - 14, ch - 38), Image.LANCZOS)
        sheet.paste(t, (x + (cw - t.width) // 2, y + 26))
        d.rectangle([x + 1, y + 1, x + cw - 2, y + ch - 2], outline=(110, 110, 110))
        d.text((x + 8, y + 8), name, fill=(0, 0, 0))
    sheet.save(out_path)
    return out_path


# ------------------------------------------------------------------ main

def main():
    global MARGIN_MM

    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True)
    ap.add_argument("--out", default="faces")
    ap.add_argument("--pad", type=float, default=0.035)
    ap.add_argument("--margin", type=float, default=MARGIN_MM)
    args = ap.parse_args()

    MARGIN_MM = args.margin

    src = []
    for s in args.src:
        src.extend(sorted(glob.glob(s)) if any(c in s for c in "*?[") else [s])
    src = [s for s in src if os.path.isfile(s)]
    if not src:
        log("Нет исходников")
        sys.exit(2)

    d_crop = os.path.join(args.out, "01_лица_по_отдельности")
    d_a4 = os.path.join(args.out, "02_страницы_A4_300dpi")
    d_chk = os.path.join(args.out, "03_проверка")
    for d in (d_crop, d_a4, d_chk):
        os.makedirs(d, exist_ok=True)

    report, thumbs, faces_list = [], [], []
    idx = 1
    for path in src:
        rgb, faces, info = analyse_sheet(path, pad_frac=args.pad)
        log(f"[{info['file']}] {info['size'][0]}x{info['size'][1]}px | сетка "
            f"{info['grid'][0]}x{info['grid'][1]} | лиц: {info['faces']} | "
            f"целиком в вырезе: {info['faces_inside']} | у края исходника: {info['faces_at_source_edge']}")
        for f in faces:
            f["name"] = f"{idx:02d}"
            f["src_file"] = info["file"]
            faces_list.append(f)
            idx += 1
        report.append(info)

    total = len(faces_list)
    log(f"\nВСЕГО ЛИЦ: {total}")

    for f in faces_list:
        p = os.path.join(d_crop, f"lice_{f['name']}.png")
        f["png"] = p
        f["img"].save(p, "PNG", optimize=True, compress_level=9)
        thr = f["img"].copy()
        thr.thumbnail((900, 900), Image.LANCZOS)
        thumbs.append((f"{f['name']} ({f['img'].width}x{f['img'].height})", thr))

    # --- PDF №1: пиксели исходной нарезки, без пересэмплирования (эталон качества)
    pdf1 = os.path.join(args.out, "Лица_A4_печать.pdf")
    layout1 = build_pdf([(f["img"], f"lice_{f['name']}") for f in faces_list], pdf1)
    log(f"PDF без пересэмплирования: {pdf1}")

    # --- растровые страницы A4 300 dpi (лицо максимально крупно) + PDF №2
    items2 = []
    for f in faces_list:
        x_mm, y_mm, w_mm, h_mm, _ = fit_rect(f["img"].width, f["img"].height)
        tw = max(1, int(round(w_mm / 25.4 * DPI_A4)))
        th = max(1, int(round(h_mm / 25.4 * DPI_A4)))
        face = f["img"].resize((tw, th), Image.LANCZOS)
        page = Image.new("RGB", (int(round(A4_W_MM / 25.4 * DPI_A4)), int(round(A4_H_MM / 25.4 * DPI_A4))),
                         (255, 255, 255))
        page.paste(face, (int(round(x_mm / 25.4 * DPI_A4)), int(round(y_mm / 25.4 * DPI_A4))))
        page.save(os.path.join(d_a4, f"A4_{f['name']}.png"), "PNG", optimize=True, compress_level=9)
        items2.append((page, f"lice_{f['name']}"))
    pdf2 = os.path.join(args.out, "Лица_A4_печать_300dpi_макс_размер.pdf")
    build_pdf(items2, pdf2)
    log(f"PDF страницы 300 dpi:      {pdf2}")

    # --- проверка каждой нарезки
    checks = []
    for f in faces_list:
        im = Image.open(f["png"]).convert("RGB")
        m = white_margin_around_face(im)
        fw = f["face_box"][2] - f["face_box"][0] + 1
        fh = f["face_box"][3] - f["face_box"][1] + 1
        ratio = f["img"].width / f["img"].height
        checks.append({
            "name": f["name"], "src": f["src_file"],
            "PNG": os.path.basename(f["png"]),
            "crop_px": [f["img"].width, f["img"].height],
            "face_px": [fw, fh],
            "белый_запас_px_сверху_снизу_слева_справа": m,
            "лицо_целиком": bool(f["face_inside"] and m and min(m) > 0),
            "у_края_исходника": bool(f["source_edge"]),
            "соотношение_сторон": round(ratio, 3),
        })

    contact_sheet(thumbs, os.path.join(d_chk, "превью_всех_лиц.png"))

    v1 = verify_pdf(pdf1, total)
    v2 = verify_pdf(pdf2, total)

    bad = [c for c in checks if not c["лицо_целиком"]]
    edge = [c for c in checks if c["у_края_исходника"]]

    summary = {
        "источников": len(src),
        "лиц_найдено": total,
        "ожидалось_по_заданию": 24,
        "совпадает_с_24": total == 24,
        "нарезка": checks,
        "проверка_pdf": [v1, v2],
        "PDF": [os.path.basename(pdf1), os.path.basename(pdf2)],
        "каталоги": {"нарезка": d_crop, "A4_страницы": d_a4, "проверка": d_chk},
        "источники_детально": report,
        "лиц_с_проблемой_обрезки": [c["name"] for c in bad],
        "лиц_у_края_исходника": [c["name"] for c in edge],
        "итог": ("OK" if (total == 24 and not bad and v1["ok"] and v2["ok"]) else "ПРОВЕРИТЬ"),
    }
    with open(os.path.join(d_chk, "отчёт.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    log("\n=== ПРОВЕРКА ===")
    for v in (v1, v2):
        log(f"{v['file']}: страниц {v['pages']}, A4={v['a4']}, внутри полей={v['inside_margins']}, "
            f"мин. плотность {v['min_dpi_in_page']} dpi, проблемы: {v['problems'] or 'нет'}")
    log(f"лиц с признаками обрезки: {[c['name'] for c in bad] or 'нет'}")
    log(f"лиц, упирающихся в край исходника: {[c['name'] for c in edge] or 'нет'}")
    log(f"ИТОГ: {summary['итог']}")


if __name__ == "__main__":
    main()
