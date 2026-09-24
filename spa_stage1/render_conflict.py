# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFont
F  = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
FB = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
ML,MT,S=90,100,0.1
W,H=ML*2+2000+460,MT+1500+190
img=Image.new("RGB",(W,H),"white"); dr=ImageDraw.Draw(img)
def fx(x): return ML+x*S
def fy(y): return MT+(15000-y)*S
def rr(x1,y1,x2,y2,**kw): dr.rectangle([fx(x1),fy(y2),fx(x2),fy(y1)],**kw)
def hm(x1,x2,y,lbl,c="#000"):
    dr.line([fx(x1),fy(y),fx(x2),fy(y)],fill=c,width=1)
    for xx in (x1,x2): dr.line([fx(xx),fy(y-150),fx(xx),fy(y+150)],fill=c,width=1)
    dr.text((fx((x1+x2)/2),fy(y+130)),lbl,font=FB(12),fill=c,anchor="mm")
def vm(y1,y2,x,lbl,c="#000"):
    dr.line([fx(x),fy(y1),fx(x),fy(y2)],fill=c,width=1)
    for yy in (y1,y2): dr.line([fx(x-150),fy(yy),fx(x+150),fy(yy)],fill=c,width=1)
    t=Image.new("RGBA",(160,20),(0,0,0,0)); td=ImageDraw.Draw(t); td.text((10,0),lbl,font=FB(12),fill=c)
    t=t.rotate(90,expand=True); img.paste(t,(int(fx(x))-10,int(fy((y1+y2)/2))-80),t)
dr.text((ML,50),"ПРОВЕРКА ИСХОДНОЙ СХЕМЫ ТЗ: здание 20.00 × 15.00 м, зал 13.0 × 15.0 (по осям)",font=FB(18),fill="#000")
rr(0,0,20000,15000,fill="#f4f4f4",outline="#111",width=4)
rr(300,300,6900,14700,fill="#f6efdd")
rr(6900,300,7100,14700,fill="#1a1a1a")
rr(7100,300,19700,14700,fill="#e6f4fc",outline="#1a1a1a",width=2)
rr(8400,2500,18400,12500,fill="#4db3e6")
dr.rectangle([fx(8400),fy(12500),fx(18400),fy(2500)],outline="#c00000",width=3)
dr.text((fx(13400),fy(7500)),"БАССЕЙН 10×10",font=FB(16),fill="#fff",anchor="mm")
t=Image.new("RGBA",(500,26),(0,0,0,0)); td=ImageDraw.Draw(t)
td.text((10,2),"СЕРВИСНО-БАННЫЙ БЛОК 7.00 (по осям)",font=FB(14),fill="#333")
t=t.rotate(90,expand=True); img.paste(t,(int(fx(3600))-14,int(fy(7500))-250),t)
dr.text((fx(13400),fy(1770)),"2.20 м  ✗ (треб. 2.50)",font=FB(14),fill="#c00000",anchor="mm")
dr.text((fx(13400),fy(13400)),"боковой проход: 2.20 м  ✗ (треб. 2.50)",font=FB(14),fill="#c00000",anchor="mm")
def rotlabel(x,y,lbl,c="#c00000",size=13):
    t=Image.new("RGBA",(120,22),(0,0,0,0)); td=ImageDraw.Draw(t); td.text((6,1),lbl,font=FB(size),fill=c)
    t=t.rotate(90,expand=True); img.paste(t,(int(fx(x))-11,int(fy(y))-60),t)
rotlabel(7750,7500,"1.25 ✗"); rotlabel(19050,7500,"1.25 ✗")
hm(7100,19700,-600,"13.00 (по осям)"); vm(0,15000,-700,"15.00 (по осям)")
hm(0,20000,-1400,"20 000")
LX=ML+2000+40; ly=MT+30
dr.text((LX,ly),"ИТОГ ПРОВЕРКИ: ОШИБКА",font=FB(17),fill="#c00000"); ly+=34
lines=[("Чистый габарит зала: 12.50 × 14.40 м",0),("(осевые 13.0 / 15.0 минус стены 200/300)",0),("",0),
("Торцевые проходы: 1.25 / 1.25 м < 1.50  ✗",1),
("Боковые проходы:  2.20 / 2.20 м < 2.50  ✗",1),("",0),
("Боковые 2.50 м требуют чистой глубины",0),
("10.00+2.50+2.50 = 15.00 м, а всё здание",0),
("даёт максимум 14.40 м.",0),
("⇒ в глубине 15.0 м требование не",0),
("   выполняется НИ ПРИ КАКОЙ планировке.",0),("",0),
("Разворот боковых по ширине 20 м:",0),
("зал 15.50 осевых → блок 4.50 м —",0),
("программа ≈ 80 м² туда не помещается.",0),("",0),
("Бюджет согласованной схемы ≈ 356 м².",0),
("ВЫВОД: глубина 15.00 → 17.80 м",1),
("(см. план СХ-1), либо сокращать программу.",1),
("",0),("Проходы проверены математически,",0),("см. REPORT.md, gen_checks.py",0)]
for txt,red in lines:
    dr.text((LX,ly),txt,font=F(13),fill="#c00000" if red else "#111"); ly+=21
img.save("spa_stage1/conflict_20x15.png"); print("conflict PNG", img.size)
