# Textura "holograma" só da terra do Brasil (fundo transparente), na resolução do relevo do site, para o globo de teste.
import json, math, sys
import numpy as np
from PIL import Image, ImageDraw
D = sys.argv[1]; OUT = sys.argv[2]
O, L, N, S = -75.0, -28.0, 6.0, -34.5
W, H = 2820, 2568
ym = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(max(min(lat, 85), -85)) / 2))
YN, YS = ym(N), ym(S)
pr = lambda lo, la: ((lo - O) / (L - O) * W, (YN - ym(la)) / (YN - YS) * H)
est = json.load(open(D + "/geo/estados_detalhe.json"))
m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m)
for f in est["features"]:
    g = f["geometry"]
    for pl in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]):
        d.polygon([pr(*c) for c in pl[0]], fill=255)
br = np.array(m).astype(np.float32) / 255
sombra = np.array(Image.open(D + "/relevo/sombra.webp").convert("L")).astype(np.float32) / 255
gy, gx = np.gradient(sombra); aresta = np.clip(np.hypot(gx, gy) * 18, 0, 1)
base = np.array([8, 48, 74], np.float32) / 255; cia = np.array([47, 196, 238], np.float32) / 255
t = np.clip(0.15 + 0.55 * aresta + 0.2 * sombra, 0, 1)[..., None]
cor = base * (1 - t) + cia * t
alfa = br * np.clip(0.55 + 0.35 * aresta, 0, 1)
img = np.dstack([cor * 255, alfa * 255]).astype(np.uint8)
Image.fromarray(img, "RGBA").save(OUT, "WEBP", quality=82, method=6)
print("ok", OUT)
