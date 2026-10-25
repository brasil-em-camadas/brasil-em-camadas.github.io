"""Fundos de página do Brasil em Camadas (versão de teste, pedido do Edu em 25/10/2026: "um fundo inteiro, talvez com um
   efeito de profundidade, talvez formas geométricas"). Gera três opções em 2400 × 1500 (WebP, para site/fundos/):
   A = facetas (triângulos com luz e sombra), B = chão de hexágonos em perspectiva com brilho no horizonte,
   C = camadas de vidro (placas translúcidas; as de trás borradas, as da frente nítidas com borda dourada).
   Uso: python3 scripts/estudos/fundos.py  (grava fundo_a/b/c.webp e .png na pasta atual). Precisa de numpy, scipy e Pillow."""
import numpy as np, math, random
from PIL import Image, ImageDraw, ImageFilter
from scipy.spatial import Delaunay
W, H, S = 2400, 1500, 2          # tamanho final e supersample
WS, HS = W*S, H*S
CX, CY = 0.40, 0.46              # onde fica o globo (fração da tela)
def hexc(h): h=h.lstrip('#'); return np.array([int(h[i:i+2],16) for i in (0,2,4)], float)
def radial(cols, stops, cx=CX, cy=CY, w=WS, h=HS, sx=1.0, sy=1.0):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((x/w-cx)/sx)**2 + ((y/h-cy)/sy)**2*(h/w)**2*1.0) / 0.75
    out = np.zeros((h, w, 3), np.float32)
    for c in range(3):
        out[..., c] = np.interp(d, stops, [col[c] for col in cols])
    return out
def vinheta(img, forca=0.55):
    h, w = img.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((x/w-0.5)*1.0)**2 + ((y/h-0.5)*1.0)**2) / 0.707
    return img * (1 - forca*np.clip(d, 0, 1)**2.2)[..., None]
def salvar(arr, nome):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    im.save(nome + '.webp', quality=82, method=6); im.save(nome + '.png')
    print(nome, im.size)
random.seed(7); np.random.seed(7)
NAVY = [hexc('#123447'), hexc('#0a1d29'), hexc('#05101a'), hexc('#02070c')]
ST = [0, 0.35, 0.75, 1.3]
# ---------- A: facetas (low-poly) ----------
def opcao_a():
    base = radial(NAVY, ST)
    nx, ny = 30, 19
    pts = []
    for j in range(ny+1):
        for i in range(nx+1):
            x = i/nx; y = j/ny
            if 0 < i < nx: x += (np.random.rand()-.5)/nx*0.9
            if 0 < j < ny: y += (np.random.rand()-.5)/ny*0.9
            pts.append((x*WS, y*HS))
    pts = np.array(pts); tri = Delaunay(pts)
    # relevo suave para dar a cada faceta uma inclinação
    def alt(p): x, y = p[:,0]/WS, p[:,1]/HS
    hgt = (np.sin(pts[:,0]/WS*7.1+1.3)*0.5 + np.cos(pts[:,1]/HS*5.3+0.4)*0.5 + np.sin((pts[:,0]/WS+pts[:,1]/HS)*9.7)*0.35 + np.random.rand(len(pts))*0.6) * 120
    luz = np.array([-0.55, -0.65, 0.52]); luz /= np.linalg.norm(luz)
    img = Image.new('RGB', (WS, HS)); dr = ImageDraw.Draw(img)
    arr_base = base
    linhas = []
    for s in tri.simplices:
        p = pts[s]; z = hgt[s]
        v1 = np.array([p[1,0]-p[0,0], p[1,1]-p[0,1], z[1]-z[0]]); v2 = np.array([p[2,0]-p[0,0], p[2,1]-p[0,1], z[2]-z[0]])
        n = np.cross(v1, v2); n /= (np.linalg.norm(n)+1e-9)
        if n[2] < 0: n = -n
        lam = 0.80 + 0.45*max(0.0, float(np.dot(n, luz)))
        c = p.mean(0).astype(int); c[0] = min(c[0], WS-1); c[1] = min(c[1], HS-1)
        col = arr_base[c[1], c[0]] * lam
        dr.polygon([tuple(q) for q in p], fill=tuple(int(v) for v in np.clip(col, 0, 255)))
        linhas.append(p)
    arr = np.asarray(img).astype(np.float32)
    # arestas douradas bem fracas, mais visíveis perto do centro
    lay = Image.new('L', (WS, HS), 0); dl = ImageDraw.Draw(lay)
    for p in linhas:
        dl.line([tuple(p[0]), tuple(p[1]), tuple(p[2]), tuple(p[0])], fill=255, width=2)
    a = np.asarray(lay).astype(np.float32)/255
    y, x = np.mgrid[0:HS, 0:WS].astype(np.float32)
    perto = np.clip(1 - np.sqrt(((x/WS-CX))**2 + ((y/HS-CY)*0.62)**2)/0.7, 0, 1)
    ouro = hexc('#f2c069')
    alfa = (a * (0.035 + 0.06*perto))[..., None]
    arr = arr*(1-alfa) + ouro*alfa
    salvar(vinheta(arr, 0.5), 'fundo_a')
# ---------- B: grade hexagonal em perspectiva ----------
def opcao_b():
    y, x = np.mgrid[0:HS, 0:WS].astype(np.float32)
    hor = 0.60*HS
    ceu = np.zeros((HS, WS, 3), np.float32)
    t = np.clip(y/hor, 0, 1)
    for c, (a0, a1) in enumerate(zip(hexc('#02060b'), hexc('#0d2633'))):
        ceu[..., c] = a0 + (a1-a0)*t**2.2
    # chão: escurece para perto
    tc = np.clip((y-hor)/(HS-hor), 0, 1)
    for c, (a0, a1) in enumerate(zip(hexc('#0b222e'), hexc('#03090f'))):
        ceu[..., c] = np.where(y > hor, a0 + (a1-a0)*tc**0.7, ceu[..., c])
    # brilho no horizonte
    gl = np.exp(-((y-hor)/(0.05*HS))**2) * np.exp(-((x-CX*WS)/(0.55*WS))**2)
    ceu += (hexc('#3a6b72')*0.55)[None, None, :]*gl[..., None]*0.55
    ceu += (hexc('#f2c069'))[None, None, :]*(np.exp(-((y-hor)/(0.012*HS))**2)*np.exp(-((x-CX*WS)/(0.35*WS))**2))[..., None]*0.10
    # hexágonos no plano do chão (x, z), câmera a altura hc
    lay = Image.new('L', (WS, HS), 0); dl = ImageDraw.Draw(lay)
    f = 1.15*WS; hc = 1.0; R = 0.32
    def proj(px, pz):
        return (CX*WS + f*px/pz, hor + f*hc/pz)
    dx = R*math.sqrt(3); dz = R*1.5
    for row in range(-2, 220):
        z0 = 0.9 + row*dz
        for col in range(-150, 151):
            cx_ = col*dx + (dx/2 if row % 2 else 0); cz = z0
            if cz < 0.9: continue
            if abs(cx_) > cz*1.6 + 6: continue
            verts = [(cx_ + R*math.cos(math.radians(60*k+30)), cz + R*math.sin(math.radians(60*k+30))) for k in range(7)]
            if min(v[1] for v in verts) <= 0.5: continue
            pp = [proj(*v) for v in verts]
            dist = cz
            a = max(0.0, min(1.0, 1.15 - dist/34))**1.3
            if a < 0.02: continue
            dl.line(pp, fill=int(255*a), width=max(2, int(6/ max(1, dist/3))))
    m = np.asarray(lay).astype(np.float32)/255
    m = np.where(y > hor+2, m, 0)
    # some para os lados e perto do horizonte
    lat = np.exp(-((x-CX*WS)/(0.75*WS))**2)
    perto_h = np.clip((y-hor)/(0.03*HS), 0, 1)
    alfa = (m*lat*perto_h*0.62)[..., None]
    arr = ceu*(1-alfa) + hexc('#e6b450')*alfa
    salvar(vinheta(arr, 0.45), 'fundo_b')
# ---------- C: camadas de vidro ----------
def opcao_c():
    arr = radial(NAVY, ST)
    planos = []
    rnd = random.Random(11)
    # (centro x, centro y, largura, altura, giro, profundidade 0 = longe .. 1 = perto)
    lista = [(0.08, 0.20, 0.38, 0.22, -14, 0.15), (0.80, 0.12, 0.42, 0.20, 9, 0.2), (0.70, 0.80, 0.50, 0.24, -7, 0.3),
             (0.12, 0.78, 0.46, 0.26, 12, 0.45), (0.92, 0.48, 0.30, 0.40, -18, 0.55), (0.02, 0.50, 0.26, 0.46, 16, 0.65),
             (0.50, 1.02, 0.80, 0.22, 3, 0.8), (0.42, -0.04, 0.70, 0.16, -4, 0.9)]
    for (cx, cy, w, h, ang, d) in lista:
        lay = Image.new('RGBA', (WS, HS), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        cxp, cyp = cx*WS, cy*HS; ww, hh = w*WS/2, h*HS/2
        a = math.radians(ang); ca, sa = math.cos(a), math.sin(a)
        # quadrilátero levemente em perspectiva (um lado menor)
        k = 0.86
        cant = [(-ww*k, -hh), (ww*k, -hh), (ww, hh), (-ww, hh)]
        q = [(cxp + u*ca - v*sa, cyp + u*sa + v*ca) for u, v in cant]
        fill_a = int(255*(0.035 + 0.06*d)); edge_a = int(255*(0.10 + 0.40*d))
        dl.polygon(q, fill=(110, 170, 190, fill_a))
        cor_borda = (242, 192, 105, edge_a) if d > 0.5 else (140, 200, 214, edge_a)
        dl.line(q + [q[0]], fill=cor_borda, width=max(2, int(2 + 3*d)))
        # luz na aresta de cima (vidro)
        dl.line([q[0], q[1]], fill=(255, 236, 190, int(edge_a*0.9)), width=max(2, int(2 + 3*d)))
        blur = (1 - d)*26*S/2
        if blur > 0.5: lay = lay.filter(ImageFilter.GaussianBlur(blur))
        la = np.asarray(lay).astype(np.float32)
        al = la[..., 3:4]/255
        arr = arr*(1-al) + la[..., :3]*al
    salvar(vinheta(arr, 0.5), 'fundo_c')
opcao_a(); opcao_b(); opcao_c()
