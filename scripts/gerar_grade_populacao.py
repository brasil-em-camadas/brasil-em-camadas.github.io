"""Imagem da população em quadrados de 1 km (IBGE, grade estatística do Censo 2022) para a luz "População" do globo
(versão de teste, 25/10/2026; decisão do Edu de 21/10/2026: "grade estatística do Censo 2022"). Mostra onde as pessoas
moram de fato, inclusive na zona rural, em vez de concentrar tudo na sede do município.

Fonte: IBGE, Grade Estatística do Censo Demográfico 2022, quadrados de 1 km (BR1KM_20251002.zip, ~400 MB, versão de
02/10/2025), em geoftp.ibge.gov.br/recortes_para_fins_estatisticos/grade_estatistica/censo_2022/grade_1km/. Cada quadrado
traz o total de moradores (TOTAL) e de domicílios; o nome do quadrado ("1KME5189N7749") dá a posição na projeção de Albers
do IBGE, então não é preciso ler os desenhos (1,2 GB): só a tabela.

A imagem fica na projeção de Mercator (a do mapa), com ~2,1 km por pixel no equador; cada pixel soma os quadrados cujo
centro cai nele. O brilho segue o logaritmo dos moradores (as cidades pequenas também aparecem), com um halo suave em
volta (desfoque), nas cores da luz "População" do site; o fundo é transparente.

Roda à mão:
  pip install numpy pyproj pillow scipy
  python scripts/gerar_grade_populacao.py --cache PASTA   (PASTA com o zip; se faltar, é baixado)
Saídas: site/data/luzes/grade_populacao.webp e grade_populacao.json (cantos, fonte e totais)
"""
import argparse
import json
import math
import struct
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import gaussian_filter

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "luzes"
URL = "https://geoftp.ibge.gov.br/recortes_para_fins_estatisticos/grade_estatistica/censo_2022/grade_1km/BR1KM_20251002.zip"
ZIP = "BR1KM_20251002.zip"
ALBERS = ("+proj=aea +lat_0=-12 +lon_0=-54 +lat_1=-2 +lat_2=-22 +x_0=5000000 +y_0=10000000 +ellps=GRS80 +units=m +no_defs")
# recorte da imagem (graus): o Brasil com as ilhas oceânicas
OESTE, LESTE, SUL, NORTE = -74.2, -28.6, -34.0, 5.6
LARGURA = 2400
# cores da luz "População" do site (do laranja escuro ao branco), pela intensidade 0 a 1
RAMPA = [(0.0, (110, 55, 10)), (0.25, (215, 125, 35)), (0.5, (255, 190, 80)), (0.8, (255, 232, 170)), (1.0, (255, 252, 235))]


def merc(lat):
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def ler_grade(cache):
    p = cache / ZIP
    if not p.exists():
        print("baixando", URL)
        urllib.request.urlretrieve(URL, p)
    dbf = cache / "BR1KM.dbf"
    if not dbf.exists():
        with zipfile.ZipFile(p) as z:
            z.extract("BR1KM.dbf", cache)
    with open(dbf, "rb") as f:
        h = f.read(32)
        n, hl, rl = struct.unpack("<IHH", h[4:12])
        campos, off = {}, 1
        while True:
            d = f.read(32)
            if d[0] == 0x0D:
                break
            campos[d[:11].split(b"\0")[0].decode()] = (off, d[16]); off += d[16]
    mm = np.memmap(dbf, dtype=np.uint8, mode="r", offset=hl, shape=(n, rl))
    o, t = campos["TOTAL"]
    tot = np.char.strip(np.array(mm[:, o:o + t]).view(f"S{t}").ravel())
    tot = np.where(tot == b"", b"0", tot).astype(np.int64)
    ok = tot > 0
    o, t = campos["nome_1KM"]
    nome = np.char.strip(np.array(mm[ok, o:o + t]).view(f"S{t}").ravel()).astype("U20")
    partes = np.char.partition(np.char.lstrip(nome, "1KME"), "N")
    E, N = partes[:, 0].astype(np.int64), partes[:, 2].astype(np.int64)
    return E, N, tot[ok], int(n), int(tot.sum())


def colorir(v):
    out = np.zeros(v.shape + (3,), np.float32)
    xs = [r[0] for r in RAMPA]
    for c in range(3):
        out[..., c] = np.interp(v, xs, [r[1][c] for r in RAMPA])
    return out


def main(cache):
    cache.mkdir(parents=True, exist_ok=True)
    E, N, pop, nq, total = ler_grade(cache)
    print(f"{nq} quadrados, {len(pop)} com moradores, {total} moradores")
    lon, lat = Transformer.from_crs(ALBERS, "EPSG:4674", always_xy=True).transform((E + 0.5) * 1000.0, (N + 0.5) * 1000.0)
    y0, y1 = merc(NORTE), merc(SUL)
    altura = int(round(LARGURA * (y0 - y1) / math.radians(LESTE - OESTE)))
    px = ((lon - OESTE) / (LESTE - OESTE) * LARGURA).astype(np.int64)
    py = ((y0 - merc(lat)) / (y0 - y1) * altura).astype(np.int64)
    dentro = (px >= 0) & (px < LARGURA) & (py >= 0) & (py < altura)
    soma = np.zeros((altura, LARGURA), np.float64)
    np.add.at(soma, (py[dentro], px[dentro]), pop[dentro])
    print("fora do recorte:", int((~dentro).sum()), "quadrados;", "pixel mais cheio:", int(soma.max()))
    # brilho: logaritmo dos moradores por pixel (até ~5 moradores = 0; 500 mil ou mais = 1), com curva que guarda o
    # brilho forte para as cidades, mais um halo desfocado em volta das áreas cheias
    v = np.clip((np.log1p(soma) - math.log1p(5)) / (math.log1p(5e5) - math.log1p(5)), 0, 1)
    halo = gaussian_filter(v ** 2, 2.5) * 0.9 + gaussian_filter(v ** 2, 8) * 0.7
    i = np.clip(v ** 1.25 * 0.9 + halo * 0.55, 0, 1)
    rgb = colorir(i)
    alfa = np.clip(i * 2.6, 0, 1) ** 0.8
    alfa[alfa < 0.03] = 0
    img = np.dstack([rgb, alfa[..., None] * 255]).astype(np.uint8)
    SAIDA.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img, "RGBA").save(SAIDA / "grade_populacao.webp", quality=82, method=6)
    meta = {"titulo": "População em quadrados de 1 km", "fonte": "IBGE, Grade Estatística do Censo Demográfico 2022 (quadrados de 1 km, versão de 02/10/2025)",
            "nivel": "manual", "gerado_em": date.today().isoformat(), "arquivo": "grade_populacao.webp",
            "cantos": [[OESTE, NORTE], [LESTE, NORTE], [LESTE, SUL], [OESTE, SUL]], "pixels": [LARGURA, altura],
            "quadrados": nq, "quadrados_com_moradores": int(len(pop)), "moradores": total,
            "nota": "cada pixel (~2 km) soma os quadrados de 1 km cujo centro cai nele; brilho pelo logaritmo dos moradores"}
    (SAIDA / "grade_populacao.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("grade_populacao.webp", (SAIDA / "grade_populacao.webp").stat().st_size // 1024, "KB;", LARGURA, "x", altura)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=Path("cache_grade"))
    main(ap.parse_args().cache)
