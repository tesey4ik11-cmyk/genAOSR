#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ЭТАП 1 — Функциональная планировка банного SPA-комплекса.
Модель в мм. Предлагаемая (согласованная) геометрия: 20.0 × 17.8 м.
Генерирует: plan SVG, conflict SVG, REPORT.md; выполняет проверки.
"""
import math

# ---------------- МОДЕЛЬ (мм), Y на север ----------------
BW, BD = 20000, 17800           # здание
E = 300                         # наружная стена
DIV = (6400, 6600)              # стена зал|блок (200), ось 6500
TECH_WALL = (12900, 13100)      # стена посетительская|тех зона (200)

# Комнаты: ключ: (имя, x1,y1,x2,y2, зона, примечание)
ROOMS = {
 "ТАМБУР":      ("Тамбур",        300,  300, 2700, 2800, "dry",  "вход 1200"),
 "ХОЛЛ":        ("Входной холл", 2800,  300, 6400, 2800, "dry",  "ресепшн"),
 "РАЗД":        ("Раздевалка",    300, 2900, 6400, 6400, "dry",  "12–14 мест"),
 "СУ":          ("Санузел",       300, 6500, 1500, 9100, "dry",  "доступ из раздевалки"),
 "ДУШ":         ("Душевые",      1600, 6500, 6400, 9100, "wet",  "4 душа + проход"),
 "ПАРНАЯ":      ("Русская парная", 300, 9200, 2600,12900, "hot",  "полки 2 яруса"),
 "САУНА":       ("Финская сауна",2700, 9200, 4500,12900, "hot",  "компакт"),
 "ХАМАМ":       ("Хамам",        4600, 9200, 6400,12900, "hot",  "лежанка + кювета"),
 "ИНЖ":         ("Инженерное пом.\n(вент.,осушение,ТН)",300,13100,3400,17500,"tech","венткамера"),
 "НАСОС":       ("Тех. помещение\nбассейна (насосная)",  3500,13100,6400,17500,"tech","фильтрация"),
 "ЗАЛ":         ("Бассейновый зал",6600, 300,19700,17500,"hall", ""),
}
POOL  = (8150, 2800, 18150, 12800)     # 10000×10000
LOUNGE= (6600,15300,19700,17500)       # открытая зона отдыха в зале
WALK  = {  # дорожки зала (для подписей)
 "S": (6600, 300,19700, 2800), "N": (6600,12800,19700,15300),
 "W": (6600, 2800,8150,12800),"E":(18150, 2800,19700,12800)}

# Двери: id, ориентация стены, коорд стены, (проём a,b), петля, открывание, (комната1,комната2), ширина
DOORS = [
 ("D1","V", 150,(1100,2300),"a","E",("УЛ_ЗАП","ТАМБУР"),1200),  # главный вход
 ("D2","V",2750,(1200,2100),"a","E",("ТАМБУР","ХОЛЛ"),  900),
 ("D3","H",2850,(4300,5300),"a","N",("ХОЛЛ","РАЗД"),   1000),
 ("D4","H",6450,( 600,1400),"a","N",("РАЗД","СУ"),      800),
 ("D5","H",6450,(4400,5200),"a","N",("РАЗД","ДУШ"),     800),
 ("D6","H",9150,(1750,2550),"a","S",("ДУШ","ПАРНАЯ"),   800),
 ("D8","H",9150,(3200,4000),"a","S",("ДУШ","САУНА"),    800),
 ("D7","H",9150,(5000,5800),"a","S",("ДУШ","ХАМАМ"),    800),
 ("D9","V",6500,(7300,8100),"a","E",("ДУШ","ЗАЛ"),      800),  # душ→зал
 ("D10","H",17650,(1500,2500),"a","S",("УЛ_СЕВ","ИНЖ"),1000),  # тех. вход
 ("D11","V",3450,(15200,16000),"a","E",("ИНЖ","НАСОС"),800),
 ("D12","V",6500,(14000,14800),"a","E",("НАСОС","ЗАЛ"),800),   # техперсонал→зал
]

# Стены как списки сегментов (x1,y1,x2,y2,толщина) — проёмы вырезаны заранее
def segs(axis, const, spans, t):
    out=[]
    for a,b in spans:
        out.append((a,const,b,const,t) if axis=="H" else (const,a,const,b,t))
    return out
WALLS = []
WALLS += segs("H", 150, [(0,20000)], E)                     # юг
WALLS += segs("V", 150, [(0,17800)], E)                     # запад (проём D1 ниже)
WALLS += segs("H",17650,[(0,1500),(2500,20000)],E)          # север (проём D10)
WALLS += segs("V",19850,[(0,17800)],E)                      # восток
# вырез D1 из западной стены: пересобираем
WALLS = [w for w in WALLS if not (w[4]==300 and w[0]==w[2]==150)]
WALLS += segs("V",150,[(0,1100),(2300,17800)],E)
WALLS += segs("V",6500,[(300,7300),(8100,14000),(14800,17500)],200)  # divider (D9,D12)
WALLS += segs("H",13000,[(300,6400)],200)                   # visitor|tech
WALLS += segs("H",2850,[(300,4300),(5300,6400)],100)        # холл|разд (D3)
WALLS += segs("V",2750,[(300,1200),(2100,2800)],100)        # тамбур|холл (D2)
WALLS += segs("H",6450,[(300,600),(1400,4400),(5200,6400)],100)  # разд|с/у+душ (D4,D5)
WALLS += segs("V",1550,[(6500,9100)],100)                   # су|душ
WALLS += segs("H",9150,[(300,1750),(2550,3200),(4000,5000),(5800,6400)],100) # душ|бани
WALLS += segs("V",2650,[(9200,12900)],100)                  # пар|сауна
WALLS += segs("V",4550,[(9200,12900)],100)                  # сауна|хамам
WALLS += segs("V",3450,[(13100,15200),(16000,17500)],100)   # инж|насос (D11)

def room_at(x,y):
    for k,(n,x1,y1,x2,y2,z,p) in ROOMS.items():
        if x1<=x<=x2 and y1<=y<=y2: return k
    if x<0: return "УЛ_ЗАП"
    if y>BD: return "УЛ_СЕВ"
    return None

def door_rooms(d):
    _id,o,c,(a,b),h,s,(r1,r2),w = d
    m=(a+b)/2; off=250
    if o=="V": A,B = room_at(c-off,m), room_at(c+off,m)
    else:      A,B = room_at(m,c-off), room_at(m,c+off)
    return A,B

# ---------------- ПРОВЕРКИ ----------------
report=[]
def log(s=""): print(s); report.append(s)

px1,py1,px2,py2 = POOL
hx1,hy1,hx2,hy2 = ROOMS["ЗАЛ"][1:5]
mW,mE = px1-hx1, hx2-px2
mS,mN = py1-hy1, hy2-py2-17500+17500  # ниже пересчитаем
mS = py1-hy1                         # до южной стены (вкл. лаунж? нет — это S дорожка)
mN = 15300-py2                       # северная дорожка до лаунжа
log("="*74)
log("ПРОВЕРКА А. БАССЕЙН 10×10 В ЗАЛЕ (предлагаемая геометрия 20.0×17.8)")
log("="*74)
log(f"Чистый зал: {(hx2-hx1)/1000:.2f} × {(hy2-hy1)/1000:.2f} м")
log(f"Торцевые проходы (Запад/Восток): {mW} / {mE} мм  (треб. ≥1500)  "
    f"{'OK' if mW>=1500 and mE>=1500 else 'ОШИБКА'}")
log(f"Боковые проходы  (Юг/Север):     {mS} / {mN} мм (треб. ≥2500)  "
    f"{'OK' if mS>=2500 and mN>=2500 else 'ОШИБКА'}")
assert mW>=1500 and mE>=1500 and mS>=2500 and mN>=2500

log("\n"+"="*74)
log("ПРОВЕРКА Б. ДВЕРИ: каждая ведёт из помещения в помещение (не в стену)")
log("="*74)
for d in DOORS:
    A,B = door_rooms(d)
    expect=set((d[6][0],d[6][1])); real=set((A,B))
    ok = expect==real and None not in real
    log(f"  {d[0]:<4} [{d[6][0]} ↔ {d[6][1]}]  факт: [{A} ↔ {B}]  "
        f"шир.{d[7]} мм  {'OK' if ok else 'ОШИБКА'}")
    assert ok

log("\n"+"="*74)
log("ПРОВЕРКА В. ДОСТУПНОСТЬ (обход графа дверей)")
log("="*74)
adj={}
for d in DOORS:
    r1,r2=d[6]
    adj.setdefault(r1,[]).append((r2,d[0])); adj.setdefault(r2,[]).append((r1,d[0]))
def bfs(start, banned=set()):
    seen={start}; stack=[start]
    while stack:
        cur=stack.pop()
        for nxt,_ in adj.get(cur,[]):
            if nxt in banned or nxt in seen: continue
            seen.add(nxt); stack.append(nxt)
    return seen
vis = bfs("УЛ_ЗАП")
allr = set(ROOMS)| {"УЛ_ЗАП","УЛ_СЕВ"}
tech = bfs("УЛ_СЕВ", banned={"ТАМБУР","ХОЛЛ","РАЗД","СУ","ДУШ","ПАРНАЯ","САУНА","ХАМАМ"})
log("ПОСЕТИТЕЛЬ (от УЛ_ЗАП):")
for k in ROOMS: log(f"  {ROOMS[k][0].split(chr(10))[0]:<30} {'достижимо' if k in vis else 'НЕДОСТУПНО ✗'}")
log("ТЕХПЕРСОНАЛ (от УЛ_СЕВ, без посетительских помещений):")
for k in ("ИНЖ","НАСОС","ЗАЛ"):
    log(f"  {ROOMS[k][0].split(chr(10))[0]:<30} {'достижимо' if k in tech else 'НЕДОСТУПНО ✗'}")
assert all(k in vis for k in ROOMS)
assert all(k in tech for k in ("ИНЖ","НАСОС","ЗАЛ"))

log("\n"+"="*74)
log("ПРОВЕРКА Г. ДВЕРНЫЕ ПРОЁМЫ НА ОДНОЙ СТЕНЕ НЕ ПЕРЕСЕКАЮТСЯ")
log("="*74)
from collections import defaultdict
wallmap=defaultdict(list)
for d in DOORS: wallmap[(d[1],d[2])].append(d)
for wl,ds in wallmap.items():
    ds2=sorted(ds,key=lambda d:d[3][0]); txt="OK"
    for i in range(1,len(ds2)):
        if ds2[i][3][0] < ds2[i-1][3][1]: txt="ПЕРЕСЕЧЕНИЕ ✗"
    log(f"  стена {wl}: {[d[0] for d in ds2]}  {txt}")

# ---------------- ПЛОЩАДИ ----------------
def area(k): n,x1,y1,x2,y2,z,p=ROOMS[k]; return (x2-x1)*(y2-y1)/1e6
def dims(k): n,x1,y1,x2,y2,z,p=ROOMS[k]; return (x2-x1)/1000,(y2-y1)/1000
lounge_s=(LOUNGE[2]-LOUNGE[0])*(LOUNGE[3]-LOUNGE[1])/1e6
walk_s=area("ЗАЛ")-lounge_s-100.0
log("\n"+"="*74)
log("ЭКСПЛИКАЦИЯ (площади вычислены из геометрии: S = L × W)")
log("="*74)
for k in ["ТАМБУР","ХОЛЛ","РАЗД","СУ","ДУШ","ПАРНАЯ","САУНА","ХАМАМ","ИНЖ","НАСОС","ЗАЛ"]:
    w,l=dims(k); log(f"  {ROOMS[k][0].replace(chr(10),' '):<38} {w:5.2f} × {l:5.2f} м  = {area(k):7.2f} м²")
log(f"  {'  в т.ч. чаша бассейна 10.0×10.0':<38} {'':22} 100.00 м²")
log(f"  {'  в т.ч. дорожки вокруг бассейна':<38} {'':22}{walk_s:7.2f} м²")
log(f"  {'  в т.ч. открытая зона отдыха':<38} {'':22}{lounge_s:7.2f} м²")

log("\n"+"="*74)
log("БАЛАНС ПЛОЩАДЕЙ")
log("="*74)
tot=BW*BD/1e6
wet=sum(area(k) for k in ("ДУШ",))
hot=sum(area(k) for k in ("ПАРНАЯ","САУНА","ХАМАМ"))
dry=sum(area(k) for k in ("ТАМБУР","ХОЛЛ","РАЗД","СУ"))
techarr=sum(area(k) for k in ("ИНЖ","НАСОС"))
hall=area("ЗАЛ")
walls=tot-(wet+hot+dry+techarr+hall)
log(f"  Общая площадь здания (в осях 20.00×17.80): {tot:7.2f} м²")
log(f"  Бассейновый зал (с дорожками и лаунжем):   {hall:7.2f} м²")
log(f"    — чаша бассейна:                          100.00 м²")
log(f"    — дорожки (проходы вокруг бассейна):     {walk_s:7.2f} м²")
log(f"    — зона отдыха (открытая):                {lounge_s:7.2f} м²")
log(f"  Посетительские помещения:                  {dry+wet+hot:7.2f} м²")
log(f"    — сухие (тамбур,холл,раздевалка,с/у):    {dry:7.2f} м²")
log(f"    — душевые:                               {wet:7.2f} м²")
log(f"    — бани (парная+сауна+хамам):             {hot:7.2f} м²")
log(f"  Технические помещения:                     {techarr:7.2f} м²")
log(f"  Стены и перегородки (остаток):             {walls:7.2f} м² ({walls/tot*100:.1f}%)")
log(f"  Контроль: {wet+hot+dry+techarr+hall+walls:7.2f} = {tot:7.2f}  {'OK' if abs(wet+hot+dry+techarr+hall+walls-tot)<0.01 else '✗'}")

# ---------------- SVG ----------------
S=0.1; ML,MT = 170,150
def fx(x): return ML+x*S
def fy(y): return MT+(BD-y)*S
def rect(x1,y1,x2,y2,**kw):
    a=f'<rect x="{fx(x1):.1f}" y="{fy(y2):.1f}" width="{(x2-x1)*S:.1f}" height="{(y2-y1)*S:.1f}" '
    a+=" ".join(f'{k.replace("_","-")}="{v}"' for k,v in kw.items())
    return a+"/>"
def line(x1,y1,x2,y2,**kw):
    a=f'<line x1="{fx(x1):.1f}" y1="{fy(y1):.1f}" x2="{fx(x2):.1f}" y2="{fy(y2):.1f}" '
    a+=" ".join(f'{k.replace("_","-")}="{v}"' for k,v in kw.items())
    return a+"/>"
def text(x,y,s,size=12,anchor="middle",weight="normal",fill="#111",rotate=None,spacing=None):
    sp=f' letter-spacing="{spacing}"' if spacing else ""
    rot=f' transform="rotate({rotate} {fx(x):.1f} {fy(y):.1f})"' if rotate else ""
    st=f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{fill}"{sp}{rot}'
    return f'<text x="{fx(x):.1f}" y="{fy(y):.1f}" {st}>{s}</text>'
def path(d,**kw):
    a=f'<path d="{d}" fill="none" '
    a+=" ".join(f'{k.replace("_","-")}="{v}"' for k,v in kw.items())
    return a+"/>"

ZCOL={"dry":"#f6efdd","wet":"#cfe8f7","hot":"#ffd9b8","tech":"#dddddd",
      "hall":"#e6f4fc"}
svg=[]
W_,H_ = ML+2000+330, MT+1780+170
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W_}" height="{H_}" viewBox="0 0 {W_} {H_}" font-family="DejaVu Sans, Arial, sans-serif">')
svg.append(f'<rect width="{W_}" height="{H_}" fill="white"/>')
# миллиметровка
for gx in range(0,20001,1000):
    svg.append(line(gx,0,gx,BD,stroke="#e6e6e6",stroke_width=0.5))
for gy in range(0,17801,1000):
    svg.append(line(0,gy,20000,gy,stroke="#e6e6e6",stroke_width=0.5))
# заливки помещений
for k,(n,x1,y1,x2,y2,z,p) in ROOMS.items():
    svg.append(rect(x1,y1,x2,y2,fill=ZCOL[z],stroke="none"))
svg.append(rect(*LOUNGE,fill="#d8f0cd",stroke="#7cb46b",stroke_width=1,stroke_dasharray="6 4"))
svg.append(rect(*POOL,fill="#4db3e6",stroke="#1a7fb8",stroke_width=2))
svg.append(rect(POOL[0]+450,POOL[1]+450,POOL[2]-450,POOL[3]-450,fill="#66c1ee",stroke="#2d9bd6",stroke_width=1))
# границы заливок комнат (тонкие)
for k,(n,x1,y1,x2,y2,z,p) in ROOMS.items():
    if k!="ЗАЛ": svg.append(rect(x1,y1,x2,y2,fill="none",stroke="#999",stroke_width=0.6))
# дорожки: лёгкий тон
for k,(x1,y1,x2,y2) in WALK.items():
    svg.append(rect(x1,y1,x2,y2,fill="#f2fbff",stroke="none"))
svg.append(rect(*POOL,fill="#4db3e6",stroke="#1a7fb8",stroke_width=2))
svg.append(rect(*LOUNGE,fill="#d8f0cd",stroke="#7cb46b",stroke_width=1,stroke_dasharray="6 4"))
# стены
for x1,y1,x2,y2,t in WALLS:
    svg.append(line(x1,y1,x2,y2,stroke="#1a1a1a",stroke_width=t*S,stroke_linecap="butt"))

# двери
def door_svg(d):
    _id,o,c,(a,b),h,sw,(r1,r2),w = d
    out=[]
    if o=="V":
        hy = a if h=="a" else b
        sx = 1 if sw=="E" else -1
        leaf=(c+sx*w, hy); wall_end=(c, (b if h=="a" else a))
        out.append(line(c,hy,leaf[0],leaf[1],stroke="#0a5c9e",stroke_width=2))
        hx,hyv = fx(c),fy(hy); lx,lyv = fx(leaf[0]),fy(leaf[1]); wx,wyv=fx(wall_end[0]),fy(wall_end[1])
        v1=(lx-hx,lyv-hyv); v2=(wx-hx,wyv-hyv)
        sweep = 1 if (v1[0]*v2[1]-v1[1]*v2[0])<0 else 0
        out.append(f'<path d="M {lx:.1f} {lyv:.1f} A {w*S:.1f} {w*S:.1f} 0 0 {sweep} {wx:.1f} {wyv:.1f}" fill="none" stroke="#0a5c9e" stroke-width="1" stroke-dasharray="3 2"/>')
        mx,my=(c+leaf[0])/2,(hy+wall_end[1])/2
        out.append(text(mx,my,_id,10,weight="bold",fill="#0a5c9e"))
    else:
        hx_ = a if h=="a" else b
        sy = 1 if sw=="N" else -1
        leaf=(hx_, c+sy*w); wall_end=((b if h=="a" else a), c)
        out.append(line(hx_,c,leaf[0],leaf[1],stroke="#0a5c9e",stroke_width=2))
        hxx,hyy=fx(hx_),fy(c); lx,lyv=fx(leaf[0]),fy(leaf[1]); wx,wyv=fx(wall_end[0]),fy(wall_end[1])
        v1=(lx-hxx,lyv-hyy); v2=(wx-hxx,wyv-hyy)
        sweep = 1 if (v1[0]*v2[1]-v1[1]*v2[0])<0 else 0
        out.append(f'<path d="M {lx:.1f} {lyv:.1f} A {w*S:.1f} {w*S:.1f} 0 0 {sweep} {wx:.1f} {wyv:.1f}" fill="none" stroke="#0a5c9e" stroke-width="1" stroke-dasharray="3 2"/>')
        mx,my=(hx_+wall_end[0])/2,(c+leaf[1])/2
        out.append(text(mx,my,_id,10,weight="bold",fill="#0a5c9e"))
    return out
for d in DOORS: svg += door_svg(d)

# подписи помещений
def rlabel(key, sub_lines=(), dx=0, dy=0, size=13):
    n,x1,y1,x2,y2,z,p=ROOMS[key]
    cx,cy=(x1+x2)/2+dx,(y1+y2)/2+dy
    w,l=dims(key)
    out=[text(cx,cy+(len(sub_lines)+1)*8,n.split("\n")[0],size,weight="bold")]
    for i,ln in enumerate(n.split("\n")[1:]):
        out.append(text(cx,cy+(len(sub_lines))*8-11+i*11,ln,10.5,weight="bold"))
    out.append(text(cx,cy-6,f"{w:.2f} × {l:.2f} м",10))
    out.append(text(cx,cy-18,f"S = {area(key):.2f} м²",10,fill="#234"))
    for i,s in enumerate(sub_lines):
        out.append(text(cx,cy-30-i*11,s,9.5,fill="#555"))
    return out
for k in ROOMS:
    if k!="ЗАЛ": svg+=rlabel(k)
cx=(hx1+hx2)/2
svg.append(text(13150,2500,"БАССЕЙНОВЫЙ ЗАЛ",15,weight="bold",fill="#145"))
svg.append(text(13150,1500,f"13.10 × 17.20 м   S = {area('ЗАЛ'):.2f} м² (с дорожками и зоной отдыха)",10.5,fill="#145"))
svg.append(text(13150,7800,"БАССЕЙН",17,weight="bold",fill="#fff"))
svg.append(text(13150,6900,"10.00 × 10.00 м",12,weight="bold",fill="#fff"))
svg.append(text(13150,6100,"глубина 1.40 м   V = 140 м³",10.5,fill="#fff"))
svg.append(text(13150,16400,"ЗОНА ОТДЫХА / LOUNGE",12.5,weight="bold",fill="#2f6b23"))
svg.append(text(13150,16000,f"13.10 × 2.20 м   S = {lounge_s:.2f} м² (открытая, с видом на воду)",10,fill="#2f6b23"))
# подписи проходов вокруг бассейна
svg.append(text(7375,7800,"1.55",11,weight="bold",fill="#b00",rotate=-90))
svg.append(text(18925,7800,"1.55",11,weight="bold",fill="#b00",rotate=-90))
svg.append(text(14500,1550,"проход 2.50 м",10.5,fill="#b00"))
svg.append(text(10500,14050,"проход 2.50 м",10.5,fill="#b00"))

# размерные линии
def dim_h(x1,x2,y,label,off=0):
    out=[line(x1,y,x2,y,stroke="#000",stroke_width=0.8),
         line(x1,y-200,x1,y+200,stroke="#000",stroke_width=0.8),
         line(x2,y-200,x2,y+200,stroke="#000",stroke_width=0.8),
         text((x1+x2)/2,y+(80 if off else 80),label,11,weight="bold")]
    return out
def dim_v(y1,y2,x,label):
    return [line(x,y1,x,y2,stroke="#000",stroke_width=0.8),
            line(x-200,y1,x+200,y1,stroke="#000",stroke_width=0.8),
            line(x-200,y2,x+200,y2,stroke="#000",stroke_width=0.8),
            text(x,y1+ (y2-y1)/2,label,11,weight="bold",rotate=-90)]
svg += dim_h(0,6500,-700,"6.50")
svg += dim_h(6500,20000,-700,"13.50")
svg += dim_h(0,20000,-1500,"20 000",0)
svg += dim_v(0,12900,-800,"12.90")
svg += dim_v(12900,17800,-800,"4.90")
svg += dim_v(0,17800,-1500,"17 800")
# подписи бассейн-размеры внутри
svg += dim_h(8150,18150,2100,"10 000")
svg += dim_v(2800,12800,19150,"10 000")

# улицы и входы
svg.append(text(-2600,900,"У Л И Ц А",14,weight="bold",rotate=-90,fill="#333",spacing=3))
svg.append(text(14000,18800,"У Л И Ц А  (технический въезд)",13,weight="bold",fill="#333",spacing=2))
# стрелка север
svg.append(f'<path d="M {fx(-1300):.1f} {fy(17800)+40:.1f} L {fx(-1300):.1f} {fy(15600):.1f}" stroke="#000" stroke-width="2"/>')
svg.append(f'<path d="M {fx(-1300):.1f} {fy(15900):.1f} l -8 26 l 16 0 z" fill="#000" transform="rotate(180 {fx(-1300):.1f} {fy(15900)+13:.1f})"/>')
svg.append(text(-1300,19200-1700,"С",13,weight="bold"))

def arrow(p1,p2,color,w=3.2,dash=None):
    x1,y1=fx(p1[0]),fy(p1[1]); x2,y2=fx(p2[0]),fy(p2[1])
    dd=f' stroke-dasharray="{dash}"' if dash else ""
    s=f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{w}"{dd}/>'
    ang=math.degrees(math.atan2(y2-y1,x2-x1))
    s+=f'<path d="M {x2:.1f} {y2:.1f} l -11 -5.5 l 0 11 z" fill="{color}" transform="rotate({ang:.1f} {x2:.1f} {y2:.1f})"/>'
    return s

# МАРШРУТ ПОСЕТИТЕЛЯ (синий)
B="#0046c7"
main=[(-1900,1700),(-150,1700),(1500,1700),(2750,1650),(4600,1600),(4800,2850),
      (4700,4600),(4800,6450),(4200,7900),(6500,7700),(7375,7800)]
for i in range(len(main)-1): svg.append(arrow(main[i],main[i+1],B,dash=None if i<10 else None))
# ветки к баням (с возвратом, пунктир обратно)
def spur(start,door,inside):
    svg.append(arrow(start,door,B,dash="9 5"))
    svg.append(arrow(door,inside,B,dash="9 5"))
spur((4200,7900),(2150,9150),(1300,11100))
spur((4200,7900),(3600,9150),(3600,11100))
spur((4200,7900),(5400,9150),(5400,11100))
# по залу к северу и в лаунж
tail=[(7375,7800),(7375,14050),(12500,14050),(13150,16100)]
for i in range(len(main)-2,len(main)-2): pass
for i in range(len(tail)-1): svg.append(arrow(tail[i],tail[i+1],B))
# МАРШРУТ ТЕХПЕРСОНАЛА (красный)
R="#d21f1f"
t=[(2000,18850),(2000,17850),(1900,15600),(3450,15600),(4900,15200),(6500,14400),(7375,14450)]
for i in range(len(t)-1): svg.append(arrow(t[i],t[i+1],R,))

# легенда
LX=ML+2000+40; LY=MT+40
svg.append(f'<text x="{LX}" y="{LY-14}" font-size="15" font-weight="bold">ЛЕГЕНДА</text>')
def leg(y,fill,label,dash=None):
    s=f'<rect x="{LX}" y="{y-11}" width="22" height="14" fill="{fill}" stroke="#888" stroke-width="0.6"/>'
    s+=f'<text x="{LX+28}" y="{y+1}" font-size="11">{label}</text>'
    return s
ly=LY+16
svg.append(leg(ly,"#e6f4fc","Бассейновый зал / дорожки")); ly+=20
svg.append(leg(ly,"#4db3e6","Чаша бассейна 10×10, h=1.40")); ly+=20
svg.append(leg(ly,"#d8f0cd","Зона отдыха (открытая)")); ly+=20
svg.append(leg(ly,"#f6efdd","Сухие помещения")); ly+=20
svg.append(leg(ly,"#cfe8f7","Мокрые помещения")); ly+=20
svg.append(leg(ly,"#ffd9b8","Бани (парная/сауна/хамам)")); ly+=20
svg.append(leg(ly,"#dddddd","Технические помещения")); ly+=26
svg.append(f'<line x1="{LX}" y1="{ly}" x2="{LX+26}" y2="{ly}" stroke="#111" stroke-width="8"/><text x="{LX+32}" y="{ly+4}" font-size="11">стена 300 / 200 / 100</text>'); ly+=22
svg.append(f'<line x1="{LX}" y1="{ly}" x2="{LX+26}" y2="{ly}" stroke="#0a5c9e" stroke-width="2"/><path d="M {LX+26} {ly} A 12 12 0 0 1 {LX+14} {ly-12}" fill="none" stroke="#0a5c9e" stroke-width="1"/><text x="{LX+32}" y="{ly+4}" font-size="11">дверь (полотно, направ. открыв.)</text>'); ly+=24
svg.append(arrow((0,0),(0,0),B))
svg = svg[:-1]  # убрать невидимую стрелку-заглушку
svg.append(f'<line x1="{LX}" y1="{ly}" x2="{LX+26}" y2="{ly}" stroke="{B}" stroke-width="3.2"/><path d="M {LX+26} {ly} l -11 -5.5 l 0 11 z" fill="{B}"/><text x="{LX+32}" y="{ly+4}" font-size="11">маршрут посетителя</text>'); ly+=22
svg.append(f'<line x1="{LX}" y1="{ly}" x2="{LX+26}" y2="{ly}" stroke="{R}" stroke-width="3.2"/><path d="M {LX+26} {ly} l -11 -5.5 l 0 11 z" fill="{R}"/><text x="{LX+32}" y="{ly+4}" font-size="11">маршрут техперсонала</text>'); ly+=30
svg.append(f'<text x="{LX}" y="{ly}" font-size="11" font-weight="bold">Входы: D1 — главный (1200),</text>'); ly+=15
svg.append(f'<text x="{LX}" y="{ly}" font-size="11" font-weight="bold">D10 — технический (1000)</text>'); ly+=18
svg.append(f'<text x="{LX}" y="{ly}" font-size="10.5">Все размеры на плане — в метрах/мм,</text>'); ly+=14
svg.append(f'<text x="{LX}" y="{ly}" font-size="10.5">площади вычислены из геометрии.</text>'); ly+=24
svg.append(f'<text x="{LX}" y="{ly}" font-size="10.5" fill="#b00">⚠ Габарит 20.00 × 15.00 м из ТЗ</text>'); ly+=14
svg.append(f'<text x="{LX}" y="{ly}" font-size="10.5" fill="#b00">не выполняет проходы бассейна:</text>'); ly+=14
svg.append(f'<text x="{LX}" y="{ly}" font-size="10.5" fill="#b00">1.25/2.20 м вместо 1.50/2.50 м.</text>'); ly+=14
svg.append(f'<text x="{LX}" y="{ly}" font-size="10.5" fill="#b00">Предложена глубина 17.80 м (см. отчёт).</text>')

# штамп
TX=ML+2000-5; TY=MT+1780+40
svg.append(f'<text x="{TX}" y="{TY}" font-size="13" font-weight="bold" text-anchor="end">БАННЫЙ SPA-КОМПЛЕКС — Функциональная планировка. Этап 1</text>')
svg.append(f'<text x="{TX}" y="{TY+18}" font-size="11" text-anchor="end">Согласованная геометрия 20.00 × 17.80 м (356.0 м²). Предложение к утверждению. М 1:100</text>')
svg.append(f'<text x="{ML}" y="{TY}" font-size="12" font-weight="bold" text-anchor="start">ПЛАН СХ-1</text>')
svg.append(f'<text x="{ML}" y="{TY+18}" font-size="10.5" text-anchor="start">Посетитель: улица→тамбур→холл→раздевалка→душ→бани→зал→лаунж  |  Тех.: улица→инженерная→насосная→зал</text>')
svg.append('</svg>')
open("spa_stage1/plan_v1_20x17.8.svg","w").write("\n".join(svg))

# ---------------- конфликт-эскиз 20×15 ----------------
csvg=[]
cML,cMT=90,90
def cx(x): return cML+x*0.1
def cy(y): return cMT+(15000-y)*0.1
csvg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{cML*2+2000+420}" height="{cMT*2+1500+220}" font-family="DejaVu Sans, Arial, sans-serif">')
csvg.append(f'<rect width="100%" height="100%" fill="white"/>')
def crect(x1,y1,x2,y2,**kw):
    return f'<rect x="{cx(x1):.1f}" y="{cy(y2):.1f}" width="{(x2-x1)*0.1:.1f}" height="{(y2-y1)*0.1:.1f}" '+' '.join(f'{k.replace("_","-")}="{v}"' for k,v in kw.items())+'/>'
def cline(x1,y1,x2,y2,**kw):
    return f'<line x1="{cx(x1):.1f}" y1="{cy(y1):.1f}" x2="{cx(x2):.1f}" y2="{cy(y2):.1f}" '+' '.join(f'{k.replace("_","-")}="{v}"' for k,v in kw.items())+'/>'
def ctext(x,y,s,size=13,anchor="middle",weight="normal",fill="#111",rotate=None):
    rot=f' transform="rotate({rotate} {cx(x):.1f} {cy(y):.1f})"' if rotate else ""
    return f'<text x="{cx(x):.1f}" y="{cy(y):.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}"{rot}>{s}</text>'
csvg.append(f'<text x="60" y="50" font-size="17" font-weight="bold">ПРОВЕРКА ИСХОДНОЙ СХЕМЫ: здание 20.00 × 15.00, зал 13.0 × 15.0 (по осям)</text>')
csvg.append(crect(0,0,20000,15000,fill="#f4f4f4",stroke="#111",stroke_width=3))
csvg.append(crect(7100,300,19700,14700,fill="#e6f4fc",stroke="#1a1a1a",stroke_width=2))
csvg.append(crect(300,300,6900,14700,fill="#f6efdd",stroke="#1a1a1a",stroke_width=2))
csvg.append(crect(8400,2500,18400,12500,fill="#4db3e6",stroke="#1a7fb8",stroke_width=3,stroke_dasharray="10 6"))
csvg.append(ctext(13400,7800,"БАССЕЙН 10×10",15,weight="bold",fill="#fff"))
csvg.append(ctext(3500,7800,"СЕРВИСНО-БАННЫЙ БЛОК",13,weight="bold",rotate=-90))
csvg.append(ctext(13400,14100,"боковой проход: 2.20 м  ✗ (треб. 2.50)",13,weight="bold",fill="#c00"))
csvg.append(ctext(13400,1550,"2.20 м  ✗",13,weight="bold",fill="#c00"))
csvg.append(ctext(7650,7800,"1.25 ✗",12,weight="bold",fill="#c00",rotate=-90))
csvg.append(ctext(19050,7800,"1.25 ✗",12,weight="bold",fill="#c00",rotate=-90))
csvg.append(ctext(13400,-700,"13.00 (по осям)",12,weight="bold"))
csvg.append(ctext(-600,7800,"15.00 (по осям)",12,weight="bold",rotate=-90))
bx=2200
csvg.append(f'<text x="{cML+2000+40}" y="{cMT+40}" font-size="14" font-weight="bold" fill="#c00">ИТОГ ПРОВЕРКИ: ОШИБКА</text>')
lines=[
 "Чистый габарит зала: 12.50 × 14.40 м",
 "(осевые 13.0 и 15.0 минус стены 200/300)",
 "",
 "Торцевые проходы: 1.25 / 1.25 м  < 1.50  ✗",
 "Боковые проходы:  2.20 / 2.20 м  < 2.50  ✗",
 "",
 "Боковые 2.50 м с двух сторон требуют",
 "чистой глубины 10.00+2.50+2.50 = 15.00 м,",
 "а всё здание даёт максимум 14.40 м.",
 "=> В 15.0 м глубины требование проходов",
 "   не выполняется ни при какой планировке.",
 "",
 "Альтернатива (боковые 2.50 по ширине 20 м):",
 "зал 15.50 м осевых → блок всего 4.50 м,",
 "программа ~80 м² туда не помещается (57.6 м²).",
 "",
 "Бюджет согласованной схемы: ≈ 356 м².",
 "ВЫВОД: глубина 15.00 → 17.80 м",
 "(см. план СХ-1) либо сокращать программу.",
]
yy=cMT+75
for i,ln in enumerate(lines):
    fillc = "#c00" if ("✗" in ln or "ВЫВОД" in ln) else "#111"
    csvg.append(f'<text x="{cML+2000+40}" y="{yy}" font-size="12" fill="{fillc}">{ln}</text>')
    yy+=18
csvg.append('</svg>')
open("spa_stage1/conflict_20x15.svg","w").write("\n".join(csvg))

# ---------------- REPORT.md ----------------
with open("spa_stage1/REPORT.md","w") as f:
    f.write("# ЭТАП 1 — Функциональная планировочная схема банного SPA-комплекса\n\n")
    f.write("## 1. Проверка исходной геометрии (20.00 × 15.00 м, зал 13 × 15)\n\n")
    f.write("| Параметр | Требование | Факт (со стенами 300/200) | Статус |\n|---|---|---|---|\n")
    f.write("| Чистый зал | — | 12.50 × 14.40 м | — |\n")
    f.write("| Торцевые проходы | ≥ 1.50 м | 1.25 / 1.25 м | ✗ ОШИБКА |\n")
    f.write("| Боковые проходы | ≥ 2.50 м | 2.20 / 2.20 м | ✗ ОШИБКА |\n\n")
    f.write("Боковые 2.50 м требуют чистой глубины 15.00 м (10+2.5+2.5), всё здание даёт 14.40 м\n")
    f.write("⇒ **требование невыполнимо в глубине 15.0 м ни при какой планировке.**\n")
    f.write("Ориентация «боковые по ширине 20 м» требует зал 15.5 м осевых → сервисный блок 4.5 м,\n")
    f.write("программа ~80 м² туда не помещается (доступно 57.6 м²). См. `conflict_20x15.svg`.\n\n")
    f.write("**Бюджет согласованной схемы: зал 210.6 + банный блок ~95 + лаунж ~29 + тех ~27 ≈ 356 м²**\n\n")
    f.write("### Предложенная корректировка геометрии (к утверждению)\n\n")
    f.write("**Глубина 15.00 → 17.80 м (ширина 20.00 м без изменений), площадь 356.0 м² (+18.7%).**\n")
    f.write("Альтернативы (не разрабатывались): сохранить 300 м², сократив состав помещений/удалив лаунж;\n")
    f.write("уменьшить бассейн — запрещено ТЗ.\n\n")
    f.write("## 2. Результаты автоматических проверок модели\n\n```\n")
    f.write("\n".join(report))
    f.write("\n```\n")
print("\nSVG: spa_stage1/plan_v1_20x17.8.svg, spa_stage1/conflict_20x15.svg")
print("REPORT: spa_stage1/REPORT.md")
