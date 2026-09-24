#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PNG-рендер плана (та же модель, что и gen_plan.py). Запуск из корня репо."""
import math, gen_plan as G
from PIL import Image, ImageDraw, ImageFont

S=0.1; ML,MT=170,150
BW,BD=G.BW,G.BD
W,H = ML+2000+330, MT+1780+170
def fx(x): return ML+x*S
def fy(y): return MT+(BD-y)*S
F  = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
FB = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)

img=Image.new("RGB",(W,H),"white"); dr=ImageDraw.Draw(img)
ZCOL={"dry":"#f6efdd","wet":"#cfe8f7","hot":"#ffd9b8","tech":"#dddddd","hall":"#e6f4fc"}

# сетка
for gx in range(0,20001,1000): dr.line([fx(gx),fy(0),fx(gx),fy(BD)],fill="#e6e6e6",width=1)
for gy in range(0,17801,1000): dr.line([fx(0),fy(gy),fx(20000),fy(gy)],fill="#e6e6e6",width=1)
# заливки помещений
def rrect(x1,y1,x2,y2,**kw): dr.rectangle([fx(x1),fy(y2),fx(x2),fy(y1)],**kw)
for k,(n,x1,y1,x2,y2,z,p) in G.ROOMS.items():
    rrect(x1,y1,x2,y2,fill=ZCOL[z])
for k,(x1,y1,x2,y2) in G.WALK.items(): rrect(x1,y1,x2,y2,fill="#f2fbff")
rrect(*G.LOUNGE,fill="#d8f0cd"); 
# lounge пунктирная рамка
x1,y1,x2,y2=G.LOUNGE
def dashline(p1,p2,fill,w=2,d=8,g=5):
    x1,y1=p1;x2,y2=p2
    L=math.hypot(x2-x1,y2-y1); n=int(L//(d+g))+1
    for i in range(n):
        t0=i*(d+g)/L; t1=min(1,(i*(d+g)+d)/L)
        dr.line([x1+(x2-x1)*t0,y1+(y2-y1)*t0,x1+(x2-x1)*t1,y1+(y2-y1)*t1],fill=fill,width=w)
dashline([fx(x1),fy(y1)],[fx(x2),fy(y1)],"#7cb46b"); dashline([fx(x1),fy(y2)],[fx(x2),fy(y2)],"#7cb46b")
dashline([fx(x1),fy(y1)],[fx(x1),fy(y2)],"#7cb46b"); dashline([fx(x2),fy(y1)],[fx(x2),fy(y2)],"#7cb46b")
rrect(*G.POOL,fill="#4db3e6",outline="#1a7fb8",width=3)
px1,py1,px2,py2=G.POOL
rrect(px1+450,py1+450,px2-450,py2-450,fill="#66c1ee",outline="#2d9bd6",width=1)
# тонкие границы
for k,(n,rx1,ry1,rx2,ry2,z,p) in G.ROOMS.items():
    if k!="ЗАЛ": rrect(rx1,ry1,rx2,ry2,outline="#999999",width=1)
# стены
for x1,y1,x2,y2,t in G.WALLS:
    dr.line([fx(x1),fy(y1),fx(x2),fy(y2)],fill="#1a1a1a",width=max(2,int(t*S)))
# двери
def ang(p1,p2): return math.degrees(math.atan2(p2[1]-p1[1],p2[0]-p1[0]))%360
def draw_arc(center,r,a_leaf,a_wall):
    d1=(a_wall-a_leaf)%360
    a,b=(a_leaf,a_wall) if d1<=180 else (a_wall,a_leaf)
    dr.arc([center[0]-r,center[1]-r,center[0]+r,center[1]+r],start=a,end=b,fill="#0a5c9e",width=1)
for d in G.DOORS:
    _id,o,c,(a,b),h,sw,(r1,r2),w=d
    if o=="V":
        hy=a if h=="a" else b; sx=1 if sw=="E" else -1
        hinge=(fx(c),fy(hy)); leaf=(fx(c+sx*w),fy(hy)); wall_end=(fx(c),fy(b if h=="a" else a))
    else:
        hx_=a if h=="a" else b; sy=1 if sw=="N" else -1
        hinge=(fx(hx_),fy(c)); leaf=(fx(hx_),fy(c+sy*w)); wall_end=(fx(b if h=="a" else a),fy(c))
    dr.line([hinge,leaf],fill="#0a5c9e",width=2)
    draw_arc(hinge,w*S,ang(hinge,leaf),ang(hinge,wall_end))
    mx,my=(hinge[0]+leaf[0]+wall_end[0])/3,(hinge[1]+leaf[1]+wall_end[1])/3
    dr.text((mx,my),_id,font=FB(13),fill="#0a5c9e",anchor="mm")
# текст
def T(x,y,s,size=12,bold=False,fill="#111",anchor="mm",rot=None):
    f=FB(size) if bold else F(size)
    if rot:
        bb=dr.textbbox((0,0),s,font=f); tw,th=bb[2]-bb[0]+8,bb[3]-bb[1]+8
        t=Image.new("RGBA",(tw,th),(0,0,0,0)); td=ImageDraw.Draw(t)
        td.text((4,4),s,font=f,fill=fill); t=t.rotate(rot,expand=True)
        img.paste(t,(int(fx(x)-t.width/2),int(fy(y)-t.height/2)),t)
    else:
        dr.text((fx(x),fy(y)),s,font=f,fill=fill,anchor=anchor)
def dims_area(k):
    n,x1,y1,x2,y2,z,p=G.ROOMS[k]
    return (x2-x1)/1000,(y2-y1)/1000,(x2-x1)*(y2-y1)/1e6
for k in G.ROOMS:
    if k=="ЗАЛ": continue
    n,x1,y1,x2,y2,z,p=G.ROOMS[k]; cx,cy=(x1+x2)/2,(y1+y2)/2
    if k=="ДУШ": cx=2900
    w,l,a=dims_area(k)
    lines=n.split("\n")
    T(cx,cy+150,lines[0],13,True)
    if len(lines)>1: T(cx,cy+50,lines[1],10,True)
    T(cx,cy-150,f"{w:.2f} × {l:.2f} м",10)
    T(cx,cy-300,f"S = {a:.2f} м²",10,False,"#223344")
T(9200,2500,"БАССЕЙНОВЫЙ ЗАЛ",16,True,"#114455")
T(9200,1500,"13.10 × 17.20 м   S = 225.32 м² (с дорожками и зоной отдыха)",10.5,False,"#114455")
T(13150,7900,"БАССЕЙН",19,True,"#ffffff")
T(13150,7000,"10.00 × 10.00 м",13,True,"#ffffff")
T(13150,6200,"глубина 1.40 м   V = 140 м³",11,False,"#ffffff")
T(13150,16550,"ЗОНА ОТДЫХА / LOUNGE",13,True,"#2f6b23")
T(13150,16200,"13.10 × 2.20 м   S = 28.82 м² (открытая зона, визуальная связь с водой)",10,False,"#2f6b23")
T(7050,4200,"1.55",12,True,"#bb0000",rot=90)
T(18925,7800,"1.55",12,True,"#bb0000",rot=90)
T(14500,1550,"проход 2.50 м",11,False,"#bb0000")
T(14800,14400,"проход 2.50 м",11,False,"#bb0000")
# размерные линии
def dimh(x1,x2,y,label,side=1):
    dr.line([fx(x1),fy(y),fx(x2),fy(y)],fill="#000",width=1)
    for xx in (x1,x2): dr.line([fx(xx),fy(y-200),fx(xx),fy(y+200)],fill="#000",width=1)
    T((x1+x2)/2,y+side*130,label,12,True)
def dimv(y1,y2,x,label):
    dr.line([fx(x),fy(y1),fx(x),fy(y2)],fill="#000",width=1)
    for yy in (y1,y2): dr.line([fx(x-200),fy(yy),fx(x+200),fy(yy)],fill="#000",width=1)
    T(x,fy((y1+y2)/2) and (y1+y2)/2,label,12,True,rot=90)
dimh(0,6500,-700,"6.50"); dimh(6500,20000,-700,"13.50"); dimh(0,20000,-1500,"20 000")
dimv(0,12900,-800,"12.90"); dimv(12900,17800,-800,"4.90"); dimv(0,17800,-1500,"17 800")
dimh(8150,18150,2100,"10 000",side=-1); dimv(2800,12800,19150,"10 000")
T(-2500,900,"У Л И Ц А",15,True,"#333333",rot=90)
T(14000,18800 if False else 18700,"У Л И Ц А   (технический въезд)",14,True,"#333333")
# север
dr.line([fx(-1300),fy(15600),fx(-1300),fy(17400)],fill="#000",width=2)
dr.polygon([(fx(-1300),fy(17400)),(fx(-1300)-7,fy(17400)+20),(fx(-1300)+7,fy(17400)+20)],fill="#000")
T(-1300,14900,"С",14,True)
# маршруты
def arrow(p1,p2,color,w=4,dash=None):
    x1,y1=fx(p1[0]),fy(p1[1]);x2,y2=fx(p2[0]),fy(p2[1])
    if dash: dashline([x1,y1],[x2,y2],color,w,10,6)
    else: dr.line([x1,y1,x2,y2],fill=color,width=w)
    ang_=math.atan2(y2-y1,x2-x1)
    L=13;a=0.42
    p1_=(x2-L*math.cos(ang_-a),y2-L*math.sin(ang_-a)); p2_=(x2-L*math.cos(ang_+a),y2-L*math.sin(ang_+a))
    dr.polygon([(x2,y2),p1_,p2_],fill=color)
B="#0046c7"; R="#d21f1f"
main=[(-1900,1700),(-150,1700),(1500,1700),(2750,1650),(4600,1600),(4800,2850),
      (4700,4600),(4800,6450),(4200,7900),(6500,7700),(7375,7800)]
for i in range(len(main)-1): arrow(main[i],main[i+1],B)
for st,dr_,ins in [((4200,7900),(2150,9150),(1300,11100)),((4200,7900),(3600,9150),(3600,11100)),((4200,7900),(5400,9150),(5400,11100))]:
    arrow(st,dr_,B,3,"d"); arrow(dr_,ins,B,3,"d")
tail=[(7375,7800),(7375,14050),(12500,14050),(13150,15750)]
for i in range(len(tail)-1): arrow(tail[i],tail[i+1],B)
t=[(2000,18850),(2000,17850),(1900,15600),(3450,15600),(4900,15200),(6500,14400),(7375,14450)]
for i in range(len(t)-1): arrow(t[i],t[i+1],R)
# легенда
LX=ML+2000+45; LY=MT+36
dr.text((LX,LY-16),"ЛЕГЕНДА",font=FB(16),fill="#000")
ly=LY+16
def leg(fill,label):
    global ly
    dr.rectangle([LX,ly-2,LX+22,ly+12],fill=fill,outline="#888")
    dr.text((LX+28,ly+2),label,font=F(12),fill="#111"); ly+=21
leg("#e6f4fc","Бассейновый зал / дорожки")
leg("#f2fbff","Дорожки у бассейна")
leg("#4db3e6","Чаша бассейна 10×10, h=1.40")
leg("#d8f0cd","Зона отдыха (открытая)")
leg("#f6efdd","Сухие помещения")
leg("#cfe8f7","Мокрые помещения (душ)")
leg("#ffd9b8","Бани (парная/сауна/хамам)")
leg("#dddddd","Технические помещения")
ly+=8
dr.line([LX,ly+5,LX+26,ly+5],fill="#111",width=8); dr.text((LX+32,ly),"стена 300 / 200 / 100",font=F(12)); ly+=24
dr.line([LX,ly+5,LX+24,ly+5],fill="#0a5c9e",width=2)
dr.arc([LX+12,ly-7,LX+36,ly+17],start=90,end=180,fill="#0a5c9e",width=1)
dr.text((LX+32,ly),"дверь: полотно + направление",font=F(12)); ly+=18
dr.text((LX+32,ly),"открывания (проём в стене)",font=F(12)); ly+=26
dr.line([LX,ly+5,LX+26,ly+5],fill=B,width=4)
dr.polygon([(LX+26,ly+5),(LX+14,ly),(LX+14,ly+10)],fill=B)
dr.text((LX+32,ly),"маршрут ПОСЕТИТЕЛЯ",font=F(12),fill=B); ly+=24
dr.line([LX,ly+5,LX+26,ly+5],fill=R,width=4)
dr.polygon([(LX+26,ly+5),(LX+14,ly),(LX+14,ly+10)],fill=R)
dr.text((LX+32,ly),"маршрут ТЕХПЕРСОНАЛА",font=F(12),fill=R); ly+=30
dr.text((LX,ly),"Входы: D1 — главный (1200),",font=FB(12)); ly+=17
dr.text((LX,ly),"D10 — технический (1000)",font=FB(12)); ly+=24
dr.text((LX,ly),"Площади вычислены из геометрии.",font=F(11)); ly+=22
dr.text((LX,ly),"⚠ Габарит 20.00 × 15.00 м из ТЗ",font=F(11),fill="#bb0000"); ly+=16
dr.text((LX,ly),"не выполняет проходы бассейна:",font=F(11),fill="#bb0000"); ly+=16
dr.text((LX,ly),"1.25 / 2.20 м вместо 1.50 / 2.50 м.",font=F(11),fill="#bb0000"); ly+=16
dr.text((LX,ly),"Предложена глубина 17.80 м.",font=F(11),fill="#bb0000"); ly+=16

# штамп
TY=MT+1780+45
dr.text((ML+2000,TY),"БАННЫЙ SPA-КОМПЛЕКС — Функциональная планировка. Этап 1",font=FB(15),fill="#000",anchor="ra")
dr.text((ML+2000,TY+22),"Согласованная геометрия 20.00 × 17.80 м (356.0 м²). Предложение к утверждению.",font=F(12),fill="#222",anchor="ra")
dr.text((ML,TY),"ПЛАН СХ-1",font=FB(14),fill="#000")
dr.text((ML,TY+22),"Посетитель: улица→тамбур→холл→раздевалка→душ→бани→зал→лаунж   |   Тех.: улица→инженерная→насосная→зал",font=F(11),fill="#222")
img.save("spa_stage1/plan_v1_20x17.8.png")
print("PNG saved:", img.size)
