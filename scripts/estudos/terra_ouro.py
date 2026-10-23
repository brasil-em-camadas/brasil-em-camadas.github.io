"""Relevo da terra do Brasil para o ouro da versão de teste (versão D, escolha do Edu em 23/10/2026).

Gera uma imagem que fica POR CIMA da cor dos estados no globo: sombra (preto translúcido) e luz (dourado claro
translúcido), tiradas do relevo sombreado do site (data/relevo/sombra.webp, Natural Earth 1:10 milhões). Usa só o
detalhe do relevo (a diferença para a média em volta, num raio de ~20 km), sem a altitude: assim o Pantanal e as
planícies não ficam mais escuros que o resto, o que pareceria "menos" na escala de luz. Lagos e represas (valor 0 no
relevo) ficam lisos. Fora do Brasil, transparente.

No globo, a imagem vale até o zoom 5 e some até o zoom 7, onde o relevo sombreado de altitude (Terrain Tiles) já
mostra mais detalhe. Mesmo recorte e resolução do holograma (Mercator, -75 a -28 de longitude, 6 a -34,5 de latitude).

Uso: python3 scripts/estudos/terra_ouro.py site/data site/data/relevo/ouro_relevo.webp
Precisa de numpy e Pillow.
"""
import json
import math
import sys

import numpy as np
from PIL import Image, ImageDraw

D, SAIDA = sys.argv[1], sys.argv[2]
O, L, N, S = -75.0, -28.0, 6.0, -34.5
W, H = 2820, 2568          # resolução do relevo sombreado
ym = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(max(min(lat, 85), -85)) / 2))
YN, YS = ym(N), ym(S)
pr = lambda lo, la: ((lo - O) / (L - O) * W, (YN - ym(la)) / (YN - YS) * H)

# terra do Brasil (contorno detalhado do IBGE)
est = json.load(open(D + "/geo/estados_detalhe.json"))
m = Image.new("L", (W, H), 0)
d = ImageDraw.Draw(m)
for f in est["features"]:
    g = f["geometry"]
    for pl in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]):
        d.polygon([pr(*c) for c in pl[0]], fill=255)
        for buraco in pl[1:]:
            d.polygon([pr(*c) for c in buraco], fill=0)
br = np.asarray(m).astype(np.float32) / 255

# relevo sombreado (0 a 1); água = 0 → preenchida com a média em volta, para não criar bordas falsas
s = np.asarray(Image.open(D + "/relevo/sombra.webp").convert("L")).astype(np.float32) / 255
agua = s <= 0.004
valido = (~agua).astype(np.float32)


def caixa(a, r, eixo):
    """média móvel de largura 2r+1 ao longo de um eixo (soma acumulada), com a borda repetida"""
    p = np.pad(a, [(r + 1, r) if e == eixo else (0, 0) for e in range(2)], mode="edge")
    c = np.cumsum(p, axis=eixo, dtype=np.float64)
    hi = np.take(c, range(2 * r + 1, c.shape[eixo]), axis=eixo)
    lo = np.take(c, range(0, c.shape[eixo] - 2 * r - 1), axis=eixo)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def borrar(a, sigma):
    """desfoque quase gaussiano: três médias móveis em cada direção"""
    r = max(1, int(round(sigma * 0.9)))
    for _ in range(3):
        a = caixa(caixa(a, r, 0), r, 1)
    return a


soma = borrar(s * valido, 6)
peso = borrar(valido, 6)
cheio = np.where(agua, soma / np.maximum(peso, 1e-3), s)
detalhe = cheio - borrar(cheio, 11)              # só o detalhe: encostas ao sol (+) e à sombra (−)
detalhe[agua] = 0
dentro = detalhe[br > 0.5]
g = 0.85 / max(abs(np.percentile(dentro, 1.5)), abs(np.percentile(dentro, 98.5)))
r = np.clip(detalhe * g, -1, 1)

# metade da resolução (a mesma do holograma): média de 2 × 2
def meia(a):
    return a.reshape(H // 2, 2, W // 2, 2).mean(axis=(1, 3))


r2, br2 = meia(r), meia(br)
sombra_a = np.clip(-r2, 0, 1) * 0.65            # preto translúcido nas encostas à sombra
luz_a = np.clip(r2, 0, 1) * 0.34                # dourado claro nas encostas ao sol
alfa = np.where(r2 < 0, sombra_a, luz_a) * br2
# cor: do quase preto (sombra) ao dourado claro (luz), passando suave pelo zero (onde o alfa é quase nada), o que
# deixa o arquivo menor; o alfa vai em degraus de 4 (diferença invisível, arquivo ~20% menor)
t = np.clip((r2 + 0.12) / 0.24, 0, 1)[..., None]
cor = np.array([10, 6, 2], np.float32) * (1 - t) + np.array([255, 228, 172], np.float32) * t
a8 = np.clip(np.round(alfa * 255 / 4) * 4, 0, 255)
img = np.dstack([cor, a8[..., None]]).astype(np.uint8)
Image.fromarray(img, "RGBA").save(SAIDA, "WEBP", quality=80, alpha_quality=100, method=6)
print("ok", SAIDA, img.shape, "pixels com alfa > 0:", int((alfa > 0.01).sum()))
