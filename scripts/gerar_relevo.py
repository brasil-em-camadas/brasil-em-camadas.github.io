"""Gera as imagens de relevo do fundo do mapa a partir do Natural Earth (domínio público).

Roda no GitHub Actions (.github/workflows/relevo.yml), só quando acionado à mão.
Não precisa rodar de novo, a não ser para mudar a região ou a resolução.

Saídas em site/data/relevo/:
  cor.webp     relevo colorido (Natural Earth II, 1:50m) para a região em volta do Brasil
  sombra.webp  relevo sombreado em cinza (1:10m), só a área do Brasil, mais detalhado
  relevo.json  os limites geográficos de cada imagem, para o site posicioná-las

As imagens originais vêm em latitude/longitude simples. O mapa do site usa a projeção
de Mercator, então cada imagem é reprojetada aqui para encaixar exatamente no desenho.
"""
import io
import json
import math
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SAIDA = Path(__file__).resolve().parent.parent / "site" / "data" / "relevo"
ESPELHOS = [
    "https://naciscdn.org/naturalearth/{p}",
    "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/{p}",
]


def baixar(caminho):
    erros = []
    for base in ESPELHOS:
        url = base.format(p=caminho)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "atlas-brasil-aberto"})
            with urllib.request.urlopen(req, timeout=600) as r:
                dados = r.read()
            print(f"baixado {url} ({len(dados) / 1e6:.1f} MB)")
            return dados
        except Exception as e:
            erros.append(f"{url}: {e}")
    raise RuntimeError("não foi possível baixar:\n" + "\n".join(erros))


def abrir_tif(zip_bytes):
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    nome = next(n for n in z.namelist() if n.lower().endswith((".tif", ".tiff")))
    print("abrindo", nome)
    return Image.open(io.BytesIO(z.read(nome)))


def merc(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def para_mercator(img, oeste, leste, sul, norte, px_grau):
    """Recorta a região e reprojeta de lat/lon para Mercator, com interpolação bilinear."""
    W, H = img.size
    ow = round((leste - oeste) * px_grau)
    yN, yS = merc(norte), merc(sul)
    oh = round(ow * (yN - yS) / math.radians(leste - oeste))
    lon = oeste + (np.arange(ow) + 0.5) * (leste - oeste) / ow
    y = yN - (np.arange(oh) + 0.5) * (yN - yS) / oh
    lat = np.degrees(np.arctan(np.sinh(y)))
    cx = (lon + 180) / 360 * W - 0.5
    ry = (90 - lat) / 180 * H - 0.5
    c0 = np.clip(np.floor(cx).astype(int), 0, W - 1); c1 = np.clip(c0 + 1, 0, W - 1)
    r0 = np.clip(np.floor(ry).astype(int), 0, H - 1); r1 = np.clip(r0 + 1, 0, H - 1)
    fc = (cx - np.floor(cx)).astype(np.float32); fr = (ry - np.floor(ry)).astype(np.float32)
    x_a, x_b, y_a, y_b = c0.min(), c1.max() + 1, r0.min(), r1.max() + 1
    a = np.asarray(img.crop((x_a, y_a, x_b, y_b)), dtype=np.float32)
    if a.ndim == 2:
        a = a[..., None]
    c0 -= x_a; c1 -= x_a; r0 -= y_a; r1 -= y_a
    fc = fc[None, :, None]
    topo = a[r0][:, c0] * (1 - fc) + a[r0][:, c1] * fc
    base = a[r1][:, c0] * (1 - fc) + a[r1][:, c1] * fc
    out = topo * (1 - fr)[:, None, None] + base * fr[:, None, None]
    out = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(out[..., 0] if out.shape[2] == 1 else out)


def oceano_transparente(img):
    """No Natural Earth II sem água, o oceano e os lagos são quase brancos (252,251,252).
    Viram transparentes, com borda suave, para o fundo escuro do site aparecer."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    soma = a.sum(2)
    alfa = np.clip((752 - soma) / 30, 0, 1) * 255
    return Image.fromarray(np.dstack([a, alfa]).astype(np.uint8), "RGBA")


def realcar_sombra(img):
    """O relevo do Brasil é suave. Põe o terreno plano em cinza médio (128) e aumenta o contraste,
    para a imagem funcionar como camada de 'luz e sombra' sobre as cores do mapa."""
    a = np.asarray(img.convert("L"), dtype=np.float32)
    v, n = np.unique(a.astype(int), return_counts=True)
    plano = v[n.argmax()]
    return Image.fromarray(np.clip(128 + (a - plano) * 2.6, 0, 255).astype(np.uint8), "L")


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    info = {"gerado_em": date.today().isoformat()}

    # 1) relevo colorido da região (América do Sul, parte das Américas e costa da África)
    cor = abrir_tif(baixar("50m/raster/NE2_50M_SR.zip")).convert("RGB")
    caixa = dict(oeste=-120, leste=30, sul=-58, norte=34)
    img = oceano_transparente(para_mercator(cor, px_grau=26, **caixa))
    img.save(SAIDA / "cor.webp", "WEBP", quality=74, alpha_quality=80, method=6)
    info["cor"] = {"arquivo": "cor.webp", **caixa, "fonte": "Natural Earth II com relevo sombreado, escala 1:50 milhões"}
    print("cor.webp", img.size, f"{(SAIDA / 'cor.webp').stat().st_size / 1e6:.2f} MB")
    del cor, img

    # 2) relevo sombreado, mais detalhado, só no Brasil
    sombra = abrir_tif(baixar("10m/raster/SR_HR.zip")).convert("L")
    caixa = dict(oeste=-75, leste=-28, sul=-34.5, norte=6)
    img = realcar_sombra(para_mercator(sombra, px_grau=60, **caixa))
    img.save(SAIDA / "sombra.webp", "WEBP", quality=70, method=6)
    info["sombra"] = {"arquivo": "sombra.webp", **caixa, "fonte": "Natural Earth, relevo sombreado, escala 1:10 milhões"}
    print("sombra.webp", img.size, f"{(SAIDA / 'sombra.webp').stat().st_size / 1e6:.2f} MB")

    (SAIDA / "relevo.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
