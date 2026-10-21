"""Gera as imagens de relevo do fundo do mapa a partir do Natural Earth (domínio público).

Roda no GitHub Actions (.github/workflows/relevo.yml), só quando acionado à mão.
Não precisa rodar de novo, a não ser para mudar a região ou a resolução.

Saídas em site/data/relevo/:
  mundo.webp   relevo colorido do mundo todo, em baixa resolução (fica por baixo)
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
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
SAIDA = Path(__file__).resolve().parent.parent / "site" / "data" / "relevo"
GEO = SAIDA.parent / "geo"
ESPELHOS = [
    "https://naciscdn.org/naturalearth/{p}",
    "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/{p}",
]


def baixar(caminho):
    erros = []
    for base in ESPELHOS:
        url = base.format(p=caminho)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "brasil-em-camadas"})
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


def oceano_transparente(img, ilha_min=0):
    """No Natural Earth II sem água, o oceano e os lagos são quase brancos (252,251,252).
    Viram transparentes, com borda suave, para o fundo escuro do site aparecer.
    Ilhas menores que `ilha_min` pixels também somem: nessa resolução elas viram quadradinhos,
    e o contorno vetorial dos países continua mostrando onde estão."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    soma = a.sum(2)
    alfa = np.clip((752 - soma) / 30, 0, 1) * 255
    if ilha_min:
        rot, n = ndimage.label(alfa > 127)
        areas = ndimage.sum(np.ones_like(rot), rot, index=np.arange(1, n + 1))
        pequenas = np.isin(rot, np.nonzero(areas < ilha_min)[0] + 1)
        alfa[ndimage.binary_dilation(pequenas, iterations=2)] = 0
    return Image.fromarray(np.dstack([a, alfa]).astype(np.uint8), "RGBA")


def molde_terra(tamanho, oeste, leste, sul, norte):
    """Desenha, na mesma grade da imagem, a terra firme dos contornos vetoriais do site
    (países e estados). Serve de molde: o relevo só aparece onde o mapa vetorial tem terra.
    Isso apaga as ilhas que a imagem do Natural Earth desenha infladas, em blocos."""
    ow, oh = tamanho
    yN, yS = merc(norte), merc(sul)
    def px(pt):
        lon, lat = pt[0], max(min(pt[1], 85), -85)
        return ((lon - oeste) / (leste - oeste) * ow, (yN - merc(lat)) / (yN - yS) * oh)
    def desenhar(arq):
        m = Image.new("L", (ow, oh), 0)
        d = ImageDraw.Draw(m)
        for f in json.loads((GEO / arq).read_text(encoding="utf-8"))["features"]:
            g = f["geometry"]
            if not g:
                continue
            polis = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            for anel_ext, *buracos in polis:
                d.polygon([px(p) for p in anel_ext], fill=255)
                for b in buracos:
                    d.polygon([px(p) for p in b], fill=0)
        return m
    # outros países (contorno grosseiro do Natural Earth): um pouco alargados, para o relevo não ficar com fresta na costa
    paises = desenhar("mundo.json").filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1))
    # Brasil: contorno do IBGE, preciso; os estados cobrem a terra no mapa, então o relevo para exatamente na costa
    # (antes era alargado como os países e aparecia como uma faixa clara no mar, ao longo da costa)
    arq_br = "estados_detalhe.json" if (GEO / "estados_detalhe.json").exists() else "estados.json"
    brasil = desenhar(arq_br).filter(ImageFilter.GaussianBlur(0.6))
    return Image.fromarray(np.maximum(np.asarray(paises), np.asarray(brasil)))


def aplicar_molde(img, caixa):
    m = np.asarray(molde_terra(img.size, **caixa), dtype=np.float32) / 255
    a = np.asarray(img, dtype=np.float32)
    a[..., 3] *= m
    return Image.fromarray(a.astype(np.uint8), "RGBA")


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

    cor = abrir_tif(baixar("50m/raster/NE2_50M_SR.zip")).convert("RGB")

    # 1) relevo colorido do mundo todo, leve, para quem arrasta o mapa para longe do Brasil
    caixa = dict(oeste=-180, leste=180, sul=-60, norte=84)
    img = aplicar_molde(oceano_transparente(para_mercator(cor, px_grau=10, **caixa), ilha_min=50), caixa)
    img.save(SAIDA / "mundo.webp", "WEBP", quality=72, alpha_quality=80, method=6)
    info["mundo"] = {"arquivo": "mundo.webp", **caixa, "fonte": "Natural Earth II com relevo sombreado, escala 1:50 milhões"}
    print("mundo.webp", img.size, f"{(SAIDA / 'mundo.webp').stat().st_size / 1e6:.2f} MB")

    # 2) relevo colorido detalhado da região (América do Sul, parte das Américas e costa da África)
    caixa = dict(oeste=-120, leste=30, sul=-58, norte=34)
    img = aplicar_molde(oceano_transparente(para_mercator(cor, px_grau=26, **caixa), ilha_min=320), caixa)
    img.save(SAIDA / "cor.webp", "WEBP", quality=74, alpha_quality=80, method=6)
    info["cor"] = {"arquivo": "cor.webp", **caixa, "fonte": "Natural Earth II com relevo sombreado, escala 1:50 milhões"}
    print("cor.webp", img.size, f"{(SAIDA / 'cor.webp').stat().st_size / 1e6:.2f} MB")
    del cor, img

    # 3) relevo sombreado, mais detalhado, só no Brasil
    sombra = abrir_tif(baixar("10m/raster/SR_HR.zip")).convert("L")
    caixa = dict(oeste=-75, leste=-28, sul=-34.5, norte=6)
    img = realcar_sombra(para_mercator(sombra, px_grau=60, **caixa))
    img.save(SAIDA / "sombra.webp", "WEBP", quality=70, method=6)
    info["sombra"] = {"arquivo": "sombra.webp", **caixa, "fonte": "Natural Earth, relevo sombreado, escala 1:10 milhões"}
    print("sombra.webp", img.size, f"{(SAIDA / 'sombra.webp').stat().st_size / 1e6:.2f} MB")

    (SAIDA / "relevo.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
