"""Texturas do laboratório com as luzes à noite do site: População (IBGE, Censo 2022, brilho espalhado como no globo)
e Iluminação noturna (NASA Black Marble 2016, ladrilhos do GIBS). Usa as funções de texturas.py (mesma pasta).
Uso: python3 scripts/estudos/texturas_luzes.py <pasta site/data> <saida>"""
import io
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2]]
sys.path.insert(0, str(Path(__file__).parent))
import texturas as R  # noqa: E402  (desenha também as seis texturas sem luz)

D, OUT = Path(sys.argv[1]), Path(sys.argv[2])
W, H = R.W, R.H

# ---------- luz "População": um brilho por município, como no globo (peso pelo logaritmo da população) ----------
import json  # noqa: E402
mun = json.loads((D / "luzes/municipios.json").read_text())["municipios"]
dens = np.zeros((H, W), np.float32)
pts = Image.new("L", (W, H), 0)
dp = ImageDraw.Draw(pts)
xs = [7.6, 9.9, 12.2, 14.5, 16.3]
ys = [0, 0.12, 0.45, 0.85, 1]
for m in mun:
    x, y = R.proj(m[0], m[1])
    if not (0 <= x < W and 0 <= y < H):
        continue
    dens[int(y), int(x)] += float(np.interp(math.log(m[2] + 1), xs, ys))
    r = 0.35 + math.sqrt(m[2]) / 3500 * 3.2
    dp.ellipse([x - r, y - r, x + r, y + r], fill=255)
calor = np.array(Image.fromarray(np.clip(dens * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))).astype(np.float32) / 255
calor = np.clip(calor * 22, 0, 1)
pontos = np.array(pts.filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32) / 255
paleta_x = [0, 0.08, 0.25, 0.5, 0.8, 1]
paleta = np.array([[0, 0, 0], [110, 55, 10], [215, 125, 35], [255, 190, 80], [255, 232, 170], [255, 252, 235]], np.float32) / 255
cor_calor = np.stack([np.interp(calor, paleta_x, paleta[:, k]) for k in range(3)], -1)
alfa_calor = np.interp(calor, paleta_x, [0, 0.35, 0.7, 0.9, 1, 1])


def luz_pop(c, k=0.5):
    c = c * k
    c = 1 - (1 - c) * (1 - cor_calor * alfa_calor[..., None])
    return R.luz(c, R.cor("#ffe4a8"), pontos * 0.9)


# ---------- luz "Iluminação noturna": NASA Black Marble (2016), mosaico de ladrilhos no zoom 6 ----------
URL = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_Black_Marble/default/2016-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png"
Z = 6
n = 2 ** Z
tx = lambda lon: (lon + 180) / 360 * n
ty = lambda lat: (1 - R.ym(lat) / math.pi) / 2 * n
x0, x1, y0, y1 = int(tx(R.O)), int(tx(R.L)), int(ty(R.N)), int(ty(R.S))
mosaico = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
for X in range(x0, x1 + 1):
    for Y in range(y0, y1 + 1):
        with urllib.request.urlopen(URL.format(z=Z, x=X, y=Y), timeout=60) as r:
            mosaico.paste(Image.open(io.BytesIO(r.read())).convert("RGB"), ((X - x0) * 256, (Y - y0) * 256))
caixa = ((tx(R.O) - x0) * 256, (ty(R.N) - y0) * 256, (tx(R.L) - x0) * 256, (ty(R.S) - y0) * 256)
noite = np.array(mosaico.crop(tuple(round(v) for v in caixa)).resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
brilho = np.clip((noite.mean(-1) - 0.08) * 1.6, 0, 1)


def luz_noite(c, k=0.45):
    c = c * k
    return 1 - (1 - c) * (1 - noite * brilho[..., None] * 1.2)


saidas = {}
for nome, fn in (("holograma", R.holograma), ("ouro", R.ouro), ("verde", R.verde)):
    base = fn(False)
    for luz, f in (("populacao", luz_pop), ("noturna", luz_noite)):
        R.salvar(f(base, 0.28 if nome == "verde" else 0.5), f"{nome}_luz_{luz}")
        saidas[(nome, luz)] = OUT / f"{nome}_luz_{luz}.jpg"
        print("ok", nome, luz)

# painel de comparação: linhas = luzes, colunas = texturas
s = 0.42
w, h = int(W * s), int(H * s)
painel = Image.new("RGB", (w * 3 + 20, h * 2 + 10), (0, 0, 0))
for i, luz in enumerate(("populacao", "noturna")):
    for j, nome in enumerate(("holograma", "ouro", "verde")):
        painel.paste(Image.open(saidas[(nome, luz)]).resize((w, h), Image.LANCZOS), (j * (w + 10), i * (h + 10)))
painel.save(OUT / "comparar_luzes.jpg", quality=86)
print("painel ok")
