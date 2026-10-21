"""Gera o contorno dos estados a partir da malha oficial do IBGE (Malha Municipal Digital, recorte por UF).

Fonte: IBGE, https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/
O IBGE pede a leitura da Nota Metodológica da malha (seção "Publicações" da página de Malhas Territoriais).

Roda só à mão, uma vez por ano, quando o IBGE publica a malha nova (os limites mudam raramente):
  pip install shapely pyproj pyshp numpy
  python scripts/gerar_contorno_estados.py            (usa a malha de 2025)
  python scripts/gerar_contorno_estados.py --ano 2026 --cache PASTA   (PASTA com o BR_UF_2026.zip já baixado)

Saídas em site/data/geo/:
  estados.json          contorno leve: abertura do globo, versão leve, robôs e relevo (desvio máximo de alguns km)
  estados_detalhe.json  contorno detalhado: o globo troca para ele quando alguém aproxima o mapa

Como é feito:
  1. Lê a malha de UFs do IBGE (1,2 milhão de pontos na de 2025).
  2. Confere se as divisas se encaixam (cada trecho de divisa igual nos dois estados). Onde não se encaixam
     (na de 2025, um trecho curto da divisa Maranhão–Piauí, no delta do Parnaíba), remonta as faces daquele
     par de estados e devolve cada pedaço ao estado que o contém.
  3. Tira as ilhotas e os furos com menos de 1 km² (as ilhas oceânicas pequenas têm marcador próprio no mapa).
  4. Simplifica tudo junto, mantendo as divisas idênticas nos dois lados (sem frestas nem sobreposições),
     em dois níveis, arredonda as coordenadas a 4 casas (~11 m) e acerta o sentido dos anéis (padrão GeoJSON).
  5. Guarda em cada estado a "caixa" do continente (sem ilhas oceânicas), para enquadrar o estado no mapa.
"""
import argparse
import io
import json
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import shapefile  # pyshp
import shapely
from pyproj import Geod
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import polygonize, unary_union

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "geo"
URL = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_{ano}/Brasil/BR_UF_{ano}.zip"
NIVEIS = {"estados.json": 0.02, "estados_detalhe.json": 0.003}   # tolerância da simplificação (graus)
CASAS = 4            # casas decimais das coordenadas (~11 m); com 3 casas alguns polígonos ficam inválidos
MIN_KM2 = 1.0        # ilhotas e furos menores que isso saem
LESTE_CONTINENTE = -34.6   # a ponta mais a leste do continente fica em -34,79; o que passa disso é ilha oceânica
GEOD = Geod(ellps="GRS80")  # SIRGAS 2000


def km2(g):
    return abs(GEOD.geometry_area_perimeter(g)[0]) / 1e6


def ler_malha(ano, cache):
    nome = f"BR_UF_{ano}.zip"
    if cache:
        dados = (Path(cache) / nome).read_bytes()
    else:
        req = urllib.request.Request(URL.format(ano=ano), headers={"User-Agent": "brasil-em-camadas (dados abertos)"})
        with urllib.request.urlopen(req, timeout=600) as r:
            dados = r.read()
    z = zipfile.ZipFile(io.BytesIO(dados))
    base = f"BR_UF_{ano}"
    leitor = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), shx=io.BytesIO(z.read(base + ".shx")),
                              dbf=io.BytesIO(z.read(base + ".dbf")), encoding="utf-8")
    estados = {}
    for sr in leitor.iterShapeRecords():
        d = sr.record.as_dict()
        estados[d["SIGLA_UF"]] = {"nome": d["NM_UF"], "codigo": d["CD_UF"], "area_km2": d["AREA_KM2"],
                                  "geom": shape(sr.shape.__geo_interface__)}
    if len(estados) != 27:
        raise SystemExit(f"a malha trouxe {len(estados)} UFs, esperado 27")
    return estados


def encaixar(estados):
    """Conserta os pares de estados cujas divisas não coincidem (ver o passo 2 lá em cima)."""
    siglas = sorted(estados)
    geoms = [estados[s]["geom"] for s in siglas]
    if shapely.coverage_is_valid(geoms):
        return []
    ruins = [s for s, e in zip(siglas, shapely.coverage_invalid_edges(geoms)) if e is not None and not e.is_empty]
    arvore = shapely.STRtree(geoms)
    pares = set()
    for s in ruins:
        g = estados[s]["geom"]
        for j in arvore.query(g.buffer(1e-6)):
            if siglas[j] != s and siglas[j] in ruins:
                pares.add(tuple(sorted((s, siglas[j]))))
    for a, b in sorted(pares):
        ga, gb = estados[a]["geom"], estados[b]["geom"]
        de_a, de_b = [], []
        for f in polygonize(unary_union([ga.boundary, gb.boundary])):
            p = f.representative_point()
            em_a, em_b = ga.contains(p), gb.contains(p)
            if em_a and em_b:
                (de_a if ga.intersection(f).area >= gb.intersection(f).area else de_b).append(f)
            elif em_a:
                de_a.append(f)
            elif em_b:
                de_b.append(f)
        estados[a]["geom"], estados[b]["geom"] = unary_union(de_a), unary_union(de_b)
    if not shapely.coverage_is_valid([estados[s]["geom"] for s in siglas]):
        raise SystemExit("as divisas continuam sem encaixe depois do conserto; conferir a malha à mão")
    return sorted(pares)


def limpar(g):
    partes = []
    for p in getattr(g, "geoms", [g]):
        if km2(p) < MIN_KM2:
            continue
        partes.append(Polygon(p.exterior, [i for i in p.interiors if km2(Polygon(i)) >= MIN_KM2]))
    return MultiPolygon(partes)


def caixa_continente(g):
    partes = [p for p in getattr(g, "geoms", [g]) if p.bounds[2] < LESTE_CONTINENTE]
    x0, y0, x1, y1 = unary_union(partes).bounds
    return [[round(x0, 3), round(y0, 3)], [round(x1, 3), round(y1, 3)]]


def gerar(ano, cache):
    estados = ler_malha(ano, cache)
    pontos_orig = int(sum(shapely.get_num_coordinates(e["geom"]) for e in estados.values()))
    consertos = encaixar(estados)
    siglas = sorted(estados)
    limpos = [limpar(estados[s]["geom"]) for s in siglas]
    if not shapely.coverage_is_valid(limpos):
        raise SystemExit("a malha deixou de se encaixar depois de tirar as ilhotas")
    for arquivo, tol in NIVEIS.items():
        simples = shapely.coverage_simplify(limpos, tol)
        simples = [shapely.transform(g, lambda c: np.round(c, CASAS)) for g in simples]
        # sentido padrão do GeoJSON (contorno externo anti-horário, furos horários), igual em todas as partes
        simples = [shapely.orient_polygons(g, exterior_cw=False) for g in simples]
        ruins = [s for s, g in zip(siglas, simples) if not g.is_valid]
        if ruins or not shapely.coverage_is_valid(simples):
            raise SystemExit(f"{arquivo}: polígonos inválidos depois de simplificar: {ruins}")
        desvio = max(shapely.hausdorff_distance(o.boundary, n.boundary) for o, n in zip(limpos, simples)) * 111.3
        feats = [{"type": "Feature",
                  "properties": {"sigla": s, "name": estados[s]["nome"], "codigo_ibg": estados[s]["codigo"],
                                 "area_km2": estados[s]["area_km2"], "caixa": caixa_continente(g)},
                  "geometry": mapping(g)} for s, g in zip(siglas, simples)]
        pontos = int(sum(shapely.get_num_coordinates(g) for g in simples))
        meta = {"fonte": f"IBGE, Malha Municipal Digital {ano} (unidades da federação, BR_UF_{ano})",
                "nivel": "manual", "baixado_em": date.today().isoformat(),
                "simplificacao": f"tolerância {tol}°, divisas idênticas nos dois lados; desvio máximo medido ≈ {desvio:.1f} km; "
                                 f"ilhotas e furos menores que {MIN_KM2:g} km² retirados",
                "pontos": pontos, "pontos_originais": pontos_orig,
                "consertos": [f"divisa {a}–{b} remontada (as linhas dos dois estados não coincidiam)" for a, b in consertos],
                "area_km2": "área oficial do IBGE (campo AREA_KM2 da malha), não a do desenho simplificado"}
        texto = json.dumps({"type": "FeatureCollection", "meta": meta, "features": feats}, ensure_ascii=False, separators=(",", ":"))
        (SAIDA / arquivo).write_text(texto, encoding="utf-8")
        print(f"{arquivo}: {pontos} pontos (de {pontos_orig}), {len(texto) // 1024} KB, desvio máximo ≈ {desvio:.1f} km")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ano", type=int, default=2025)
    ap.add_argument("--cache", help="pasta com o BR_UF_<ano>.zip já baixado")
    a = ap.parse_args()
    gerar(a.ano, a.cache)
