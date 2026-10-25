"""Desenho dos ícones das lavouras (versão de teste do mapa): gera os caminhos em 24 × 24 e escreve o bloco ICONES
de site/icones.js. Feito à mão em 24/10/2026, com prévia em medalhão escuro; só roda de novo se o desenho mudar.
Uso: python3 scripts/estudos/icones_lavouras.py   (imprime o bloco para colar em site/icones.js)
Partes: "f" = preenchido; "s" = preenchido com contorno escuro de w em volta; "x" = risco escuro; "l" = risco na cor.
Só usa a biblioteca padrão do Python."""
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


I = {}
# soja: vagem com três grãos, na diagonal, com a ponta e o cabinho
g=[(7.6,16.4),(12,12),(16.4,7.6)]
I["soja"]=[["f",capsula(g[0],g[2],2.7)]]+[["f",circ(c,3.35)] for c in g]+[
  ["f","M14.6 6.2L21 3 17.8 9.4z"],["l",linha((7,17),(3.6,20.4)),1.5],
  ["x",curva((9.9,14.1),(10.4,13.3),(9.6,12.6)),0.9],["x",curva((14.3,9.7),(14.8,8.9),(14,8.2)),0.9]]# milho: espiga com grãos (riscos escuros) e duas palhas abertas
I["milho"]=[["f",ell((12,9.6),4.4,7.3,0)],
  ["x",linha((7.8,6.6),(16.2,6.6)),0.75],["x",linha((7.6,9.6),(16.4,9.6)),0.75],["x",linha((8,12.6),(16,12.6)),0.75],
  ["x",linha((12,2.6),(12,16)),0.75],["x",curva((9.6,3.6),(9,9.6),(9.8,15.8)),0.65],["x",curva((14.4,3.6),(15,9.6),(14.2,15.8)),0.65],
  ["s","M12 21.6C8.4 21 5.4 17.6 4.6 10.6C7.8 13 9.8 15.6 12 21.6z",1.3],
  ["s","M12 21.6C15.6 21 18.6 17.6 19.4 10.6C16.2 13 14.2 15.6 12 21.6z",1.3]]# cana: dois colmos com nós e folhas compridas
I["cana"]=[["f",capsula((8.6,21.2),(9.8,3.6),1.65)],["f",capsula((14.4,21.2),(15.2,6.4),1.65)],
  ["x",linha((6.6,8.2),(11.8,8)),0.85],["x",linha((6.8,13.4),(12,13.2)),0.85],["x",linha((7,18.4),(12.2,18.2)),0.85],
  ["x",linha((12.6,11),(17,10.8)),0.85],["x",linha((12.7,16),(17.1,15.8)),0.85],
  ["s",folha((10,6.4),(20.8,2.6),1.3,-1.2),1.1],["s",folha((15.2,10),(21.4,14.6),1.1,-0.8),1.1],["s",folha((9,11),(3,7.4),1,0.8),1.1]]# café: grão oval inclinado, com o sulco em S
I["cafe"]=[["f",ell((12,12),6.3,8.7,35)],["x","M16.1 5.8C12.4 8.6 14.6 11.4 12 12.6C9.4 13.8 11.4 16.6 7.9 18.2",1.5]]
def raiz2(a,b,r,curva=0):
    """raiz gorda: quase a mesma grossura até 60% e afina no fim; ponta arredondada"""
    n=norm(a,b); a1,a2=add(a,n,r),add(a,n,-r)
    m1=add(lerp(a,b,.55),n,curva); m2=add(lerp(a,b,.85),n,curva*.6)
    c1=add(m1,n,r*1.05); c2=add(m2,n,r*.75); d1=add(m2,n,-r*.75); d2=add(m1,n,-r*1.05)
    return f"M{P(a1)}C{P(c1)} {P(c2)} {P(b)}C{P(d1)} {P(d2)} {P(a2)}A{f(r)} {f(r)} 0 0 0 {P(a1)}z"
I["mandioca"]=[["f",raiz2((13.2,5.4),(3.2,14.6),2.4,0.3)],["s",raiz2((17,8.6),(3.8,20),3.0,0.4),1.1],
  ["s",raiz2((19.2,13.8),(8.6,21.6),2.5,0.3),1.1],
  ["x",circ((17,8.6),1.5),0.9],["x",circ((19.2,13.8),1.2),0.9],["x",circ((13.2,5.4),1.1),0.9],
  ["x",linha((9.8,11.4),(11.4,13.6)),0.75],["x",linha((12.4,15.8),(13.6,18)),0.75]]
# banana: duas bananas com cabo estreito
I["banana"]=[["f","M6.4 4.8C3.4 12.8 9.4 21.4 20.6 18.4L21 16.6C12.6 16.6 8.4 11 9.2 4.6z"],
  ["s","M9.8 4.4C8.8 11.4 13.6 15.4 21 14L21.4 12.2C15 12.2 11.8 8.6 12.6 4z",1.2],
  ["f","M6.6 5L7.8 1.8h3.6l1.4 2.8z"]]
# feijão: dois grãos em forma de rim (o de trás menor), com o olho (hilo)
def rim(cx,cy,w,h,ang):
    pts=[(-1,0),(-1,-.62),(-.55,-1),(0,-1),(.55,-1),(1,-.62),(1,0),(1,.62),(.6,1),(.22,1),(.12,.62),(0,.5),(-.12,.62),(-.22,1),(-.6,1),(-1,.62)]
    a=math.radians(ang)
    def T(p): x,y=p[0]*w/2,p[1]*h/2; return (cx+x*math.cos(a)-y*math.sin(a), cy+x*math.sin(a)+y*math.cos(a))
    q=[T(p) for p in pts]
    # curva suave pelos pontos: quadráticas com pontos médios
    s=f"M{P(lerp(q[-1],q[0],.5))}"
    for i in range(len(q)):
        s+=f"Q{P(q[i])} {P(lerp(q[i],q[(i+1)%len(q)],.5))}"
    return s+"z"
I["feijao"]=[["f",rim(14.6,9.6,11.6,7.6,-28)],["s",rim(10,14.6,13.4,8.8,-12),1.2],
  ["x",ell((10.4,17.8),1.3,0.62,-12),0.9]]
# arroz: haste que se curva e pende, com os grãos ao longo da ponta
def bez(p0,p1,p2,p3,t):
    u=1-t; return tuple(u**3*a+3*u*u*t*b+3*u*t*t*c+t**3*d for a,b,c,d in zip(p0,p1,p2,p3))
def tan(p0,p1,p2,p3,t):
    u=1-t; return tuple(3*u*u*(b-a)+6*u*t*(c-b)+3*t*t*(d-c) for a,b,c,d in zip(p0,p1,p2,p3))
B=((6,22),(6.4,13),(9.6,5.6),(14.6,4.6)); B2=((14.6,4.6),(18.4,3.8),(20.4,7),(19.6,12.4))
gr=[]
for k,(bz,t,lado) in enumerate([(B,.62,1),(B,.78,-1),(B,.9,1),(B2,.15,-1),(B2,.35,1),(B2,.52,-1),(B2,.7,1),(B2,.86,-1),(B2,1.0,0)]):
    p=bez(*bz,t); d=tan(*bz,t); ang=math.degrees(math.atan2(d[1],d[0]))
    n=(-math.sin(math.radians(ang)),math.cos(math.radians(ang)))
    c=(p[0]+n[0]*1.5*lado+ d[0]/math.hypot(*d)*0.6, p[1]+n[1]*1.5*lado+d[1]/math.hypot(*d)*0.6)
    gr.append(["f",ell(c,2.3,1.05,ang+30*lado)])
I["arroz"]=[["l",f"M{P(B[0])}C{P(B[1])} {P(B[2])} {P(B[3])}C{P(B2[1])} {P(B2[2])} {P(B2[3])}",1.2]]+gr+[
  ["s",folha((6.2,21.6),(15.6,15.4),1.2,0.8),1.0],["s",folha((6,21.6),(2.6,11),1.0,-0.5),1.0]]
# outras lavouras: muda com duas folhas
I["outras"]=[["l",linha((12,21.4),(12,11.6)),1.8],["s",folha((12,14.6),(4,8.4),2.6,0.6),1.0],["s",folha((12,11.8),(19.8,4.4),2.9,-0.6),1.0],
  ["l",linha((7.6,21.4),(16.4,21.4)),1.6]]

for k in ["soja", "milho", "cana", "cafe", "mandioca", "banana", "feijao", "arroz", "outras"]:
    print(f"  {k}: [\n    " + ",\n    ".join(json.dumps(p, ensure_ascii=False) for p in I[k]) + "],")
