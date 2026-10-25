"""Desenho dos ícones das outras camadas de pontos (versão de teste do mapa, diretriz God's Eye View): usinas por fonte,
poço de petróleo, antena de celular, pedágio, porto, refinaria, unidade de gás natural e terminal de GNL. Gera os caminhos
em 24 × 24 e imprime o bloco para acrescentar em ICONES, em site/icones.js. Feito à mão em 25/10/2026, com prévia em
medalhão escuro sobre o fundo escuro e sobre o ouro; só roda de novo se o desenho mudar.
Uso: python3 scripts/estudos/icones_camadas.py
Partes: "f" = preenchido; "s" = preenchido com contorno escuro de w em volta; "h" = preenchido em escuro (furo, janela);
"x" = risco escuro; "l" = risco na cor. Só usa a biblioteca padrão do Python."""
import json
import math
def f(x):
    s=f"{x:.2f}".rstrip('0').rstrip('.')
    return s if s not in ('-0','') else '0'
def P(p): return f"{f(p[0])} {f(p[1])}"
def circ(c,r): return f"M{f(c[0]-r)} {f(c[1])}a{f(r)} {f(r)} 0 1 0 {f(2*r)} 0a{f(r)} {f(r)} 0 1 0 {f(-2*r)} 0z"
def ell(c,rx,ry,rot):
    a=math.radians(rot); ux=(math.cos(a),math.sin(a))
    p0=(c[0]+rx*ux[0],c[1]+rx*ux[1]); p1=(c[0]-rx*ux[0],c[1]-rx*ux[1])
    return f"M{P(p0)}A{f(rx)} {f(ry)} {f(rot)} 1 0 {P(p1)}A{f(rx)} {f(ry)} {f(rot)} 1 0 {P(p0)}z"
def lerp(a,b,t): return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)
def norm(a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]; L=math.hypot(dx,dy); return (-dy/L, dx/L)
def add(a,b,k=1): return (a[0]+b[0]*k, a[1]+b[1]*k)
def folha(a,b,w,curva=0):
    """lente entre a e b; w = meia largura no meio; curva = deslocamento do meio (folha curva)"""
    n=norm(a,b); m=lerp(a,b,.5); m=add(m,n,curva)
    c1=add(m,n,w*1.9); c2=add(m,n,-w*1.9)
    return f"M{P(a)}Q{P(c1)} {P(b)}Q{P(c2)} {P(a)}z"
def capsula(a,b,r):
    n=norm(a,b)
    a1,a2,b1,b2=add(a,n,r),add(a,n,-r),add(b,n,r),add(b,n,-r)
    return f"M{P(a1)}L{P(b1)}A{f(r)} {f(r)} 0 0 0 {P(b2)}L{P(a2)}A{f(r)} {f(r)} 0 0 0 {P(a1)}z"
def raiz(a,b,r,curva=0):
    """raiz que afina: grossa em a (raio r), ponta em b"""
    n=norm(a,b); m=lerp(a,b,.45); m=add(m,n,curva)
    a1,a2=add(a,n,r),add(a,n,-r)
    c1=add(m,n,r*0.9); c2=add(m,n,-r*0.9)
    return f"M{P(a1)}Q{P(c1)} {P(b)}Q{P(c2)} {P(a2)}A{f(r)} {f(r)} 0 0 0 {P(a1)}z"
def linha(*pts): return "M"+"L".join(P(p) for p in pts)
def curva(a,c,b): return f"M{P(a)}Q{P(c)} {P(b)}"


def arco(c, r, a0, a1):
    p0=(c[0]+r*math.cos(math.radians(a0)), c[1]+r*math.sin(math.radians(a0)))
    p1=(c[0]+r*math.cos(math.radians(a1)), c[1]+r*math.sin(math.radians(a1)))
    grande = 1 if abs(a1-a0) > 180 else 0
    return f"M{P(p0)}A{f(r)} {f(r)} 0 {grande} 1 {P(p1)}"
I = {}
# hidrelétrica: gota com raio
I["hid"]=[["f","M12 2.4C12 2.4 4.6 10.6 4.6 15.4a7.4 7.4 0 0 0 14.8 0C19.4 10.6 12 2.4 12 2.4z"],
  ["h","M13.4 8.8L8.6 15.6h3.1l-1.1 5.4 4.9-7.6h-3.2l1.1-4.6z"]]
# eólica: cata-vento de três pás, torre fina
hub=(12,8.6)
pas=[]
for a in (-90,30,150):
    t=(hub[0]+7.6*math.cos(math.radians(a)), hub[1]+7.6*math.sin(math.radians(a)))
    pas.append(["f",folha(hub,t,1.25,0.7)])
I["eol"]=[["f","M11.1 10.2h1.8l.9 11.4h-3.6z"]]+pas+[["s",circ(hub,1.7),0.8],["l",linha((7,21.8),(17,21.8)),1.4]]
# solar: sol e painel em perspectiva com a grade
raios=[]
for a in range(0,360,45):
    p0=(6+3.1*math.cos(math.radians(a)),5.6+3.1*math.sin(math.radians(a))); p1=(6+4.4*math.cos(math.radians(a)),5.6+4.4*math.sin(math.radians(a)))
    raios.append(["l",linha(p0,p1),1.1])
I["sol"]=[["f",circ((6,5.6),2.1)]]+raios+[["f","M6.4 11.2h11.4l4.4 8.2H10.8z"],
  ["x",linha((10.2,11.2),(14.6,19.4)),0.9],["x",linha((14,11.2),(18.4,19.4)),0.9],["x",linha((8.6,15.3),(20,15.3)),0.9],
  ["l",linha((16.5,19.4),(16.5,22.2)),1.5],["l",linha((12.5,22.4),(20.5,22.4)),1.4]]
# biomassa: folha com nervuras
I["bio"]=[["f",folha((4.6,19.4),(20,4),4.6,0)],["x",linha((6.6,17.4),(17.4,6.6)),1.0],
  ["x",linha((10.4,13.6),(9.4,10.2)),0.8],["x",linha((10.4,13.6),(13.8,14.6)),0.8],["x",linha((13.8,10.2),(12.8,6.8)),0.8],["x",linha((13.8,10.2),(17.2,11.2)),0.8],
  ["l",linha((3.2,20.8),(5.6,18.4)),1.6]]
# termelétrica a combustível fóssil: fábrica com chaminé e fumaça
I["fos"]=[["f","M2.6 21.4V12.2l4.8 3V12.2l4.8 3V12.2l4.4 2.7v6.5z"],["f","M16.8 5.4h3.4v16h-3.4z"],
  ["h","M4.6 17h2v2h-2zM9.4 17h2v2h-2zM14.1 17h1.6v2h-1.6z"],
  ["f",circ((18.4,2.9),1.5)],["f",circ((21,1.9),1.0)],["l",linha((2,21.6),(22,21.6)),1.2]]
# nuclear: átomo
I["nuc"]=[["l",ell((12,12),9.6,3.5,0),1.35],["l",ell((12,12),9.6,3.5,60),1.35],["l",ell((12,12),9.6,3.5,-60),1.35],["f",circ((12,12),2)]]
# poço de petróleo: torre de perfuração
def em(y): return 12-5.9*(y-2.6)/18.8, 12+5.9*(y-2.6)/18.8
yA,yB,yC=8.4,14,19.2
(aL,aR),(bL,bR),(cL,cR)=em(yA),em(yB),em(yC)
I["poco"]=[["l",linha((12,2.6),(6.1,21.4)),1.7],["l",linha((12,2.6),(17.9,21.4)),1.7],
  ["l",linha((aL,yA),(aR,yA)),1.3],["l",linha((bL,yB),(bR,yB)),1.3],["l",linha((cL,yC),(cR,yC)),1.3],
  ["l",linha((aL,yA),(bR,yB)),0.9],["l",linha((aR,yA),(bL,yB)),0.9],["l",linha((bL,yB),(cR,yC)),0.9],["l",linha((bR,yB),(cL,yC)),0.9],
  ["f","M10.4 1.6h3.2v2.4h-3.2z"],["l",linha((3.6,21.6),(20.4,21.6)),1.8]]
# celular: torre com ondas
I["antena"]=[["f",circ((12,7.6),1.8)],["l",linha((12,9.4),(12,21.6)),1.8],["l",linha((12,12.6),(8.2,21.6)),1.3],["l",linha((12,12.6),(15.8,21.6)),1.3],
  ["l",linha((7.4,21.8),(16.6,21.8)),1.4],
  ["l",arco((12,7.6),4.2,-40,40),1.5],["l",arco((12,7.6),7.4,-36,36),1.5],["l",arco((12,7.6),4.2,140,220),1.5],["l",arco((12,7.6),7.4,144,216),1.5]]
# pedágio: cabine e cancela listrada
I["pedagio"]=[["f","M2.6 8.6L6.2 5.6l3.6 3H8.8v12.8H3.6V8.6z"],["h","M4.6 10.4h3.2v3.2H4.6z"],
  ["f","M9.8 11.6h12.2v2.8H9.8z"],["h","M12.2 11.6h1.8l-1 2.8h-1.8zM16 11.6h1.8l-1 2.8H15zM19.8 11.6h1.8l-1 2.8h-1.8z"],
  ["l",linha((2,21.6),(22,21.6)),1.4]]
# porto: âncora
I["ancora"]=[["l",circ((12,4.6),2.1),1.6],["l",linha((12,6.7),(12,20.8)),2],["l",linha((7.8,10),(16.2,10)),1.9],
  ["l","M4.8 13.6C5.2 18.6 8.6 21 12 21s6.8-2.4 7.2-7.4",1.9],["f","M2.8 15.2l2-3.6 2.4 3.4z"],["f","M21.2 15.2l-2-3.6-2.4 3.4z"]]
# refinaria: torres de destilação e tanque
I["refinaria"]=[["f","M4.6 21.4V8.2a2 2 0 0 1 4 0v13.2z"],["f","M10.6 21.4V4.6a1.8 1.8 0 0 1 3.6 0v16.8z"],
  ["f","M15.8 21.4v-5.4a3 3 0 0 1 6 0v5.4z"],
  ["x",linha((4.6,12.4),(8.6,12.4)),0.8],["x",linha((4.6,16.4),(8.6,16.4)),0.8],["x",linha((10.6,9),(14.2,9)),0.8],["x",linha((10.6,13.2),(14.2,13.2)),0.8],["x",linha((10.6,17.4),(14.2,17.4)),0.8],
  ["l",linha((8.6,10.6),(10.6,10.6)),1.1],["l",linha((14.2,13.6),(17.6,13.6)),1.1],["l",linha((2.4,21.6),(21.6,21.6)),1.4]]
# unidade de processamento de gás natural: chama
I["upgn"]=[["f","M12 2.2c.8 3.6 6.4 6.6 6.4 12.4a6.4 6.4 0 0 1-12.8 0c0-3.2 1.7-5.4 3.4-6.8.2 2.2 1 3.6 2.4 4.3C11.6 9.4 11 5.6 12 2.2z"],
  ["h","M12 12.6c.5 2 3 3.2 3 5.8a3 3 0 0 1-6 0c0-1.6.8-2.7 1.6-3.4.2 1 .6 1.6 1.2 2-.3-1.6-.2-3 .2-4.4z"]]
# terminal de GNL: navio-tanque com as esferas
I["gnl"]=[["f","M1.8 14.2h20.4l-2.8 5.6H4.6z"],["s",ell((6.6,14.2),2.6,2.6,0),0.8],["s",ell((11.6,14.2),2.6,2.6,0),0.8],["s",ell((16.6,14.2),2.6,2.6,0),0.8],
  ["f","M18.8 9.6h2.6v4.6h-2.6z"],["l","M2.4 22.2q2-1.4 4 0t4 0 4 0 4 0 4 0",1.2]]

NOMES = {"hid": "hidrelétrica: gota com raio", "eol": "eólica: cata-vento de três pás", "sol": "solar: sol e painel",
  "bio": "térmica a biomassa: folha com nervuras", "fos": "térmica fóssil: fábrica com chaminé e fumaça", "nuc": "nuclear: átomo",
  "poco": "poço de petróleo: torre de perfuração", "antena": "celular: torre com ondas", "pedagio": "pedágio: cabine e cancela",
  "ancora": "porto: âncora", "refinaria": "refinaria: torres de destilação e tanque", "upgn": "unidade de processamento de gás natural: chama",
  "gnl": "terminal de GNL: navio com os tanques esféricos"}
for k in NOMES:
    print(f"  /* {NOMES[k]} */\n  {k}: [\n    " + ",\n    ".join(json.dumps(p, ensure_ascii=False) for p in I[k]) + "],")
