"""Laboratório de texturas do Brasil em Camadas: desenha o Brasil em três texturas (holograma, ouro sobre preto e o
verde de hoje), com e sem a pintura do rebanho bovino, para comparar antes de aplicar no mapa.

Tudo em Mercator, no mesmo recorte do relevo sombreado do site (data/relevo/sombra.webp: -75 a -28 de longitude,
6 a -34,5 de latitude). Saídas: <saida>/<textura>_<reb|sem>.png e .jpg.
Uso: python3 scripts/estudos/texturas.py site/data <pasta de saída>
Estudo de 22/10/2026 (laboratório de texturas, pedido do Edu). Não vai para o ar; precisa de numpy e Pillow.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

DADOS, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
O, L, N, S = -75.0, -28.0, 6.0, -34.5
F = 0.5
W, H = int(2820 * F), int(2568 * F)


def ym(lat):
    lat = max(min(lat, 85), -85)
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


YN, YS = ym(N), ym(S)


def proj(lon, lat):
    return ((lon - O) / (L - O) * W, (YN - ym(lat)) / (YN - YS) * H)


def aneis(g):
    for pl in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]):
        yield pl


estados = json.loads((DADOS / "geo/estados_detalhe.json").read_text())
mundo = json.loads((DADOS / "geo/mundo.json").read_text())
reb = json.loads((DADOS / "pecuaria/estados.json").read_text())["valores"]
aero = json.loads((DADOS / "aeroportos/aeroportos.json").read_text())["aeroportos"]

# ---------- máscaras ----------
ufs = [f["properties"]["sigla"] for f in estados["features"]]
area = {f["properties"]["sigla"]: f["properties"].get("area_km2", 0) for f in estados["features"]}
rot = Image.new("L", (W, H), 0)   # índice do estado (1..27)
dr = ImageDraw.Draw(rot)
for f in sorted(estados["features"], key=lambda f: -area[f["properties"]["sigla"]]):
    k = ufs.index(f["properties"]["sigla"]) + 1
    for pl in aneis(f["geometry"]):
        dr.polygon([proj(*c) for c in pl[0]], fill=k)
        for buraco in pl[1:]:
            dr.polygon([proj(*c) for c in buraco], fill=0)
idx = np.array(rot)
br = (idx > 0).astype(np.float32)

viz = Image.new("L", (W, H), 0)
dv = ImageDraw.Draw(viz)
for f in mundo["features"]:
    if f["properties"].get("NAME_PT") == "Brasil":
        continue
    for pl in aneis(f["geometry"]):
        dv.polygon([proj(*c) for c in pl[0]], fill=255)
vizinhos = np.array(viz).astype(np.float32) / 255 * (1 - br)

# divisas entre estados e contorno do Brasil (trechos usados por um estado só)
uso = {}
for f in estados["features"]:
    for pl in aneis(f["geometry"]):
        for r in pl:
            for a, b in zip(r, r[1:]):
                k = (tuple(a), tuple(b)) if tuple(a) < tuple(b) else (tuple(b), tuple(a))
                uso[k] = uso.get(k, 0) + 1


def linhas(sozinho, largura):
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    for f in estados["features"]:
        for pl in aneis(f["geometry"]):
            for r in pl:
                atual = []
                for a, b in zip(r, r[1:]):
                    k = (tuple(a), tuple(b)) if tuple(a) < tuple(b) else (tuple(b), tuple(a))
                    if (uso[k] == 1) == sozinho:
                        if not atual:
                            atual = [proj(*a)]
                        atual.append(proj(*b))
                    elif atual:
                        d.line(atual, fill=255, width=largura, joint="curve"); atual = []
                if atual:
                    d.line(atual, fill=255, width=largura, joint="curve")
    return np.array(im).astype(np.float32) / 255


divisas = linhas(False, 1)
contorno = linhas(True, 2)
contorno_largo = linhas(True, 3)

viz_borda = Image.new("L", (W, H), 0)
dvb = ImageDraw.Draw(viz_borda)
for f in mundo["features"]:
    if f["properties"].get("NAME_PT") == "Brasil":
        continue
    for pl in aneis(f["geometry"]):
        dvb.line([proj(*c) for c in pl[0]], fill=255, width=1)
viz_borda = np.array(viz_borda).astype(np.float32) / 255 * (1 - br)

# relevo sombreado (0 a 1) e "arestas" do relevo
sombra = np.array(Image.open(DADOS / "relevo/sombra.webp").convert("L").resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
gy, gx = np.gradient(sombra)
aresta = np.clip(np.hypot(gx, gy) * 9, 0, 1)
rng = np.random.default_rng(7)
grao = np.array(Image.fromarray((rng.random((H, W)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255 - 0.5

# pintura: quintis do rebanho bovino
vals = {s: (reb.get(s) or {}).get("bovino") for s in ufs}
ordem = sorted(v for v in vals.values() if v is not None)
cortes = [ordem[int(p * (len(ordem) - 1))] for p in (0.2, 0.4, 0.6, 0.8)]
classe = np.zeros(28, dtype=np.int16) - 1
for i, s in enumerate(ufs):
    v = vals[s]
    if v is not None:
        classe[i + 1] = sum(1 for c in cortes if v > c)
cls = classe[idx]   # -1 fora do Brasil ou sem dado

# aeroportos com voos de passageiros
pts = [(proj(a[0], a[1]), a[6]) for a in aero if a[6] >= 50000]


def pontos(escala, nucleo=True):
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    for (x, y), p in sorted(pts, key=lambda t: -t[1]):
        r = (1.3 + math.sqrt(p) / 6930 * 4.2) * escala
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return np.array(im).astype(np.float32) / 255


nucleos, halos = pontos(1.0), pontos(2.2)


def borrar(a, raio):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(raio))
    return np.array(im).astype(np.float32) / 255


def cor(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255


def sobre(c, rgb, alfa):
    a = np.clip(alfa, 0, 1)[..., None]
    return c * (1 - a) + rgb * a


def luz(c, rgb, alfa):   # brilho somado (tela): nunca escurece
    a = np.clip(alfa, 0, 1)[..., None]
    return 1 - (1 - c) * (1 - rgb * a)


def salvar(c, nome):
    im = Image.fromarray((np.clip(c, 0, 1) * 255).astype(np.uint8))
    im.save(SAIDA / f"{nome}.png")
    im.convert("RGB").save(SAIDA / f"{nome}.jpg", quality=88, optimize=True, progressive=True)


yy = np.linspace(0, 1, H)[:, None] * np.ones((1, W))
xx = np.ones((H, 1)) * np.linspace(0, 1, W)[None, :]
vinheta = np.clip(1 - ((xx - 0.47) ** 2 + (yy - 0.45) ** 2) * 1.6, 0, 1)


def holograma(pintar):
    c = np.zeros((H, W, 3), np.float32) + cor("#020912")
    c = sobre(c, cor("#06213a"), 0.55 * vinheta)
    c = sobre(c, cor("#0b2f44"), vizinhos * (0.35 + 0.25 * sombra))
    c = luz(c, cor("#1d8fb8"), viz_borda * 0.35)
    c = sobre(c, cor("#08304a"), br * 0.5)
    c = luz(c, cor("#2fc4ee"), br * (0.04 + 0.30 * aresta))
    if pintar:
        alfa = np.choose(np.clip(cls, 0, 4), [0.03, 0.08, 0.15, 0.24, 0.36]) * (cls >= 0)
        c = luz(c, cor("#2ed0ff"), alfa * (0.55 + 0.5 * sombra + 0.9 * aresta))
    c = luz(c, cor("#62dcff"), borrar(divisas, 1.8) * 0.6)
    c = luz(c, cor("#b0f4ff"), divisas * 0.8)
    c = luz(c, cor("#1fc8ff"), borrar(contorno_largo, 14) * 0.55)
    c = luz(c, cor("#3fdcff"), borrar(contorno_largo, 5) * 0.9)
    c = luz(c, cor("#d8fbff"), contorno)
    c = luz(c, cor("#5be0ff"), borrar(halos, 3.5) * 0.9)
    c = luz(c, cor("#f2feff"), nucleos)
    return c


def ouro(pintar):
    c = np.zeros((H, W, 3), np.float32) + cor("#050504")
    c = sobre(c, cor("#0d0b08"), 0.8 * vinheta)
    terra = (0.22 + 0.95 * sombra + 0.16 * grao)
    c = sobre(c, cor("#1a1915") * terra[..., None] / 1.05, vizinhos)
    c = sobre(c, cor("#221e17") * (terra[..., None] * 1.15), br)
    c = luz(c, cor("#7a5a24"), viz_borda * 0.45)
    if pintar:
        alfa = np.choose(np.clip(cls, 0, 4), [0.03, 0.07, 0.13, 0.21, 0.31]) * (cls >= 0)
        c = luz(c, cor("#f0b85a"), alfa * (0.45 + 0.9 * sombra + 0.25 * grao))
    c = luz(c, cor("#c98b2a"), borrar(divisas, 1.8) * 0.45)
    c = luz(c, cor("#f0c06a"), divisas * 0.7)
    c = luz(c, cor("#d9932c"), borrar(contorno_largo, 14) * 0.5)
    c = luz(c, cor("#f2b54a"), borrar(contorno_largo, 5) * 0.95)
    c = luz(c, cor("#ffe6ae"), contorno)
    c = luz(c, cor("#ffbe55"), borrar(halos, 3.5) * 0.9)
    c = luz(c, cor("#fff4d6"), nucleos)
    return c


def verde(pintar):
    base = Image.open(DADOS / "relevo/cor.webp").convert("RGBA")
    bw, bh = base.size
    ymn, yms = ym(34), ym(-58)
    x0, x1 = (O + 120) / 150 * bw, (L + 120) / 150 * bw
    y0, y1 = (ymn - YN) / (ymn - yms) * bh, (ymn - YS) / (ymn - yms) * bh
    base = np.array(base.crop((round(x0), round(y0), round(x1), round(y1))).resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
    alfa_base = base[..., 3:4]
    mar = np.zeros((H, W, 3), np.float32) + cor("#0a2232")
    c = sobre(mar, base[..., :3] * 0.62, alfa_base[..., 0])
    if pintar:
        rampa = [cor(h) for h in ("#e6f0b0", "#b5d98b", "#7cbd6a", "#3f9450", "#14612f")]
        for k in range(5):
            c = sobre(c, rampa[k], (cls == k) * 0.86)
    c = sobre(c, cor("#f0ecdc"), divisas * 0.55)
    c = luz(c, cor("#f0be5a"), borrar(contorno_largo, 5) * 0.55)
    c = sobre(c, cor("#f2c96a"), contorno)
    c = luz(c, cor("#a9bdf7"), borrar(halos, 3) * 0.7)
    c = sobre(c, cor("#dfe6ff"), nucleos)
    return c


for nome, fn in (("holograma", holograma), ("ouro", ouro), ("verde", verde)):
    for pintar in (True, False):
        salvar(fn(pintar), f"{nome}_{'reb' if pintar else 'sem'}")
        print("ok", nome, pintar)
print("cortes do rebanho:", cortes)
