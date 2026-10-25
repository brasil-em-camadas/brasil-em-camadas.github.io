"""Fluxo de veículos nas rodovias federais (DNIT, VMDa 2025) e pista dupla (DNIT, SNV de outubro de 2026), para a versão
de teste do mapa (25/10/2026; tarefas "fluxo de carga do DNIT" e "pista dupla pelo SNV").

Fontes (os arquivos do DNIT só abrem de dentro do Brasil; foram baixados pelo notebook do Edu em 23 e 25/10/2026):
  DNIT, Plano Nacional de Contagem de Tráfego (servicos.dnit.gov.br/dadospnct), Volume Médio Diário Anual 2025:
    "(Camada VGeo) VMDa - Modelagem 2025.zip" (desenho dos 37.469 links da rede usada na modelagem, com o VMDa total) e
    "VMDa 2025.xlsx" (os 8.222 trechos federais do SNV 202401A, com o VMDa por categoria de veículo do PNCT e por sentido;
    mesma chave ID = id_pnct). O VMDa 2025 é uma estimativa por modelagem a partir de 703 pontos de contagem, não uma
    contagem em cada trecho (Nota Técnica VMDa 2025). Categorias A a H = ônibus e caminhões; I = carros e utilitários;
    J = motos.
  DNIT, Sistema Nacional de Viação, versão 202610A (20/10/2026), "202610A.zip": trechos federais com a situação da
    superfície; DUP = duplicada, EOD = em obra de duplicação. Trechos coincidentes (a mesma pista com duas siglas) entram
    no desenho, mas uma vez só na soma dos km.

Roda à mão:
  pip install shapely pyproj pyshp numpy openpyxl
  python scripts/gerar_vmda_snv.py --cache PASTA   (PASTA com VMDa_VGeo_2025.zip, "VMDa 2025.xlsx" e 202610A.zip)
Saídas: site/data/trafego/vmda.json e site/data/geo/pista_dupla.json
"""
import argparse
import collections
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import openpyxl
import shapefile  # pyshp
import shapely
from pyproj import Geod
from shapely.geometry import mapping, shape

RAIZ = Path(__file__).resolve().parent.parent
SITE = RAIZ / "site" / "data"
GEOD = Geod(ellps="GRS80")


def km(g):
    return sum(GEOD.geometry_length(x) for x in getattr(g, "geoms", [g])) / 1000


def simples(g, tol, casas=3):
    return shapely.transform(shapely.simplify(g, tol, preserve_topology=False), lambda c: np.round(c, casas))


def ler_zip_shp(caminho, nome=None):
    z = zipfile.ZipFile(caminho)
    shp = [n for n in z.namelist() if n.endswith(".shp") and (nome is None or nome in n)][0][:-4]
    return shapefile.Reader(shp=io.BytesIO(z.read(shp + ".shp")), shx=io.BytesIO(z.read(shp + ".shx")),
                            dbf=io.BytesIO(z.read(shp + ".dbf")), encoding="utf-8")


def gravar(caminho, meta, feats):
    texto = json.dumps({"type": "FeatureCollection", "meta": meta, "features": feats}, ensure_ascii=False, separators=(",", ":"))
    caminho.write_text(texto, encoding="utf-8")
    print(f"{caminho.name}: {len(feats)} feições, {len(texto) // 1024} KB")


def vmda(cache):
    wb = openpyxl.load_workbook(cache / "VMDa 2025.xlsx", read_only=True)
    ws = wb["VMDa2025_SNV202401A"]
    linhas = ws.iter_rows(values_only=True)
    cab = list(next(linhas)); ix = {k: i for i, k in enumerate(cab)}
    planilha = {}
    for r in linhas:
        if r[0] is None:
            continue
        tot = float(r[ix["VMDa_C"]] or 0) + float(r[ix["VMDa_D"]] or 0)
        pes = sum(float(r[ix[c + "_" + s]] or 0) for c in "ABCDEFGH" for s in "CD")
        planilha[int(r[0])] = (tot, pes)
    feats, kmt, refs = [], 0.0, 0
    leitor = ler_zip_shp(cache / "VMDa_VGeo_2025.zip")
    for sr in leitor.iterShapeRecords():
        d = sr.record.as_dict()
        if not d["vmda_total"] or d["jurisdicao"] != "Federal":
            continue
        g = shape(sr.shape.__geo_interface__)
        kmt += km(g)
        tot, pes = planilha.get(d["id_pnct"], (None, None))
        p = round(pes / tot * 100) if tot else -1
        refs += d["classifica"] == "Referencial"
        gs = simples(g, 0.003)
        if gs.is_empty:
            continue
        feats.append({"type": "Feature", "properties": {"v": int(d["vmda_total"]), "p": p, "br": d["codigo_br"], "u": d["unidade_fe"],
                      **({"r": 1} if d["classifica"] == "Referencial" else {})}, "geometry": mapping(gs)})
    # os de mais tráfego por cima
    feats.sort(key=lambda f: f["properties"]["v"])
    meta = {"titulo": "Fluxo nas rodovias federais", "nivel": "manual", "gerado_em": date.today().isoformat(),
            "fonte": "DNIT, Plano Nacional de Contagem de Tráfego, VMDa 2025 (camada VGeo e planilha por categoria, base SNV 202401A)",
            "referencia": "2025", "nota": "estimativa do DNIT por modelagem, a partir de 703 pontos de contagem; não é contagem em cada trecho",
            "campos": {"v": "veículos por dia, nos dois sentidos (VMDa)", "p": "% de ônibus e caminhões (categorias A a H do PNCT); -1 = sem dado",
                       "br": "rodovia", "u": "UF", "r": "trecho com contagem usada como referência na modelagem"},
            "km": round(kmt), "trechos": len(feats), "trechos_referencia": refs}
    gravar(SITE / "trafego" / "vmda.json", meta, feats)


def pista_dupla(cache):
    leitor = ler_zip_shp(cache / "202610A.zip")
    feats = []
    km_uf = collections.defaultdict(lambda: [0.0, 0.0])
    for sr in leitor.iterShapeRecords():
        d = sr.record.as_dict()
        sit = d["sg_legenda"]
        if sit not in ("DUP", "EOD"):
            continue
        g = shape(sr.shape.__geo_interface__)
        if d["desc_coinc"] in ("-", ""):
            km_uf[d["sg_uf"]][0 if sit == "DUP" else 1] += float(d["vl_extensa"] or 0)
        gs = simples(g, 0.002)
        if gs.is_empty:
            continue
        feats.append({"type": "Feature", "properties": {"d": 1 if sit == "DUP" else 2, "br": "BR-" + d["vl_br"], "u": d["sg_uf"]},
                      "geometry": mapping(gs)})
    tot = [round(sum(v[0] for v in km_uf.values())), round(sum(v[1] for v in km_uf.values()))]
    meta = {"titulo": "Pista dupla nas rodovias federais", "nivel": "manual", "gerado_em": date.today().isoformat(),
            "fonte": "DNIT, Sistema Nacional de Viação (SNV), versão 202610A, de 20/10/2026", "referencia": "out/2026",
            "campos": {"d": "1 = duplicada; 2 = em obra de duplicação", "br": "rodovia", "u": "UF"},
            "km_por_uf": {u: [round(v[0]), round(v[1])] for u, v in sorted(km_uf.items())}, "km_por_uf_campos": ["duplicada", "em obra de duplicação"],
            "km_total": tot, "nota": "km do próprio SNV (extensão de cada trecho); trechos coincidentes (mesma pista com duas siglas) contam uma vez"}
    gravar(SITE / "geo" / "pista_dupla.json", meta, feats)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, required=True)
    a = ap.parse_args()
    vmda(a.cache)
    pista_dupla(a.cache)
