"""Contorno dos países para a camada "Comércio com o mundo" (site/data/comex/mundo.json). Só roda à mão.

Fonte: Natural Earth, Admin 0 – Countries, escala 1:50 milhões (domínio público), do repositório oficial no GitHub.
A escala 1:50 milhões tem os países pequenos que importam no comércio (Singapura, Hong Kong, Malta…), que a de
1:110 milhões (o mundo.json do fundo do globo) não tem. Cada país leva o código ISO 3166 de três letras, o mesmo que
o Comex Stat dá a cada país, e o nome em português do Natural Earth. O Brasil fica de fora.
Contornos simplificados em conjunto (sem frestas entre vizinhos) e arredondados a 0,01°.
Precisa de: pip install shapely (GEOS 3.12 ou mais novo).
Uso: python scripts/gerar_paises_mundo.py [--arquivo ne_50m_admin_0_countries.geojson]
"""
import argparse
import json
import urllib.request
from pathlib import Path

import shapely
from shapely.geometry import mapping, shape

URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
       "ne_50m_admin_0_countries.geojson")
SAIDA = Path(__file__).resolve().parents[1] / "site" / "data" / "comex" / "mundo.json"
TOLERANCIA = 0.07   # graus

# Natural Earth sem código ISO (-99) ou com unidade à parte: código usado pelo Comex Stat (o país que o Brasil reconhece)
ISO_FIXO = {"SOL": "SOM",   # Somalilândia → Somália
            "CYN": "CYP",   # Chipre do Norte → Chipre
            "KOS": "XKX",   # Kosovo (código provisório usado pela União Europeia e pelo Banco Mundial)
            "KAS": None}    # Glaciar de Siachen: sem país


def arredondar(g, casas=2):
    return shapely.set_precision(g, 10 ** -casas, mode="pointwise")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arquivo", help="GeoJSON do Natural Earth já baixado")
    a = ap.parse_args()
    if a.arquivo:
        d = json.loads(Path(a.arquivo).read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(URL, timeout=120) as r:
            d = json.loads(r.read())
    feicoes = []
    for f in d["features"]:
        p = f["properties"]
        iso = p["ISO_A3_EH"] if p["ISO_A3_EH"] != "-99" else p["ADM0_A3"]
        iso = ISO_FIXO.get(p["ADM0_A3"], iso)
        if not iso or iso == "BRA":
            continue
        feicoes.append((iso, p["NAME_PT"], shape(f["geometry"])))
    geoms = shapely.coverage_simplify([g for _, _, g in feicoes], TOLERANCIA)
    saida = []
    for (iso, nome, _), g in zip(feicoes, geoms):
        g = arredondar(shapely.make_valid(g))
        if g.is_empty:
            continue
        g = shapely.make_valid(g)
        if g.geom_type == "GeometryCollection":
            g = shapely.union_all([x for x in g.geoms if x.geom_type in ("Polygon", "MultiPolygon")])
        saida.append({"type": "Feature", "properties": {"i": iso, "n": nome}, "geometry": mapping(g)})
    fc = {"type": "FeatureCollection",
          "meta": {"fonte": "Natural Earth, Admin 0 – Countries, 1:50 milhões (domínio público)", "url": URL,
                   "simplificacao_graus": TOLERANCIA, "codigos": "ISO 3166 alfa-3 (campo i), como no Comex Stat",
                   "ajustes": "Somalilândia junto da Somália, Chipre do Norte junto de Chipre, Kosovo = XKX; Brasil fora"},
          "features": saida}
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(saida)} países, {SAIDA.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
