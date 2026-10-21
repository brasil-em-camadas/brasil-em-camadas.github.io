"""Gera as rodovias e as ferrovias do mapa a partir da Base Cartográfica Contínua do Brasil 1:250.000 (BC250) do IBGE.

Fonte: IBGE, BC250 versão 2025 (arquivo bc_250_shapefiles_2026_03_03.zip, ~800 MB), em
https://geoftp.ibge.gov.br/cartas_e_mapas/bases_cartograficas_continuas/bc250/versao2025/shapefiles/
Na versão 2025, o IBGE atualizou a sigla e a jurisdição das rodovias federais e estaduais com dados do DNIT
(documentação técnica da BC250, 04/12/2025).

Roda só à mão, quando sair uma versão nova da BC250 (a cada dois anos, mais ou menos):
  pip install shapely pyproj pyshp numpy
  python scripts/gerar_transportes_ibge.py --cache PASTA   (PASTA com o zip da BC250 já baixado)
  python scripts/gerar_transportes_ibge.py                 (baixa os ~800 MB do IBGE)

Saídas em site/data/geo/:
  rodovias.json             rodovias federais (sigla BR ou jurisdição federal), construídas, pavimentadas ou não
  rodovias_estaduais.json   rodovias estaduais pavimentadas (sigla do estado, ex.: SP-330)
  ferrovias.json            ferrovias em operação e em obras (sem metrô, aeromóvel, abandonadas e destruídas),
                            cortadas na divisa dos estados, com os km de cada estado
  portos.json               complexos portuários (marítimos e fluviais), com o estado de cada um
"""
import argparse
import io
import json
import re
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import shapefile  # pyshp
import shapely
from pyproj import Geod
from shapely.geometry import mapping, shape
from shapely.ops import linemerge

RAIZ = Path(__file__).resolve().parent.parent
GEO = RAIZ / "site" / "data" / "geo"
URL = "https://geoftp.ibge.gov.br/cartas_e_mapas/bases_cartograficas_continuas/bc250/versao2025/shapefiles/bc_250_shapefiles_2026_03_03.zip"
ZIP = "bc_250_shapefiles_2026_03_03.zip"
VERSAO = "BC250 versão 2025"
TOL_ROD = 0.004   # simplificação das rodovias (graus, ~450 m)
TOL_FER = 0.002   # ferrovias (~220 m)
GEOD = Geod(ellps="GRS80")

# operadoras das ferrovias: a BC250 escreve o mesmo nome de vários jeitos ("FCA", "Fca", "S.A."); fica um nome só
OPERADORAS = {
    "FCA": "Ferrovia Centro-Atlântica (FCA)", "FTL": "Ferrovia Transnordestina Logística (FTL)",
    "TLSA": "Transnordestina Logística (TLSA)", "EFVM": "Estrada de Ferro Vitória a Minas (EFVM)",
    "EFC": "Estrada de Ferro Carajás (EFC)", "VLI": "VLI (Valor da Logística Integrada)",
    "RMS": "Rumo Malha Sul", "RMO": "Rumo Malha Oeste", "RMP": "Rumo Malha Paulista", "RMC": "Rumo Malha Central (Norte-Sul)",
    "RMN": "Rumo Malha Norte", "MRS": "MRS Logística", "EFPO": "Estrada de Ferro Paraná Oeste (Ferroeste)",
    "FTC": "Ferrovia Tereza Cristina", "EFJU": "Estrada de Ferro Juruti", "EFJ": "Estrada de Ferro Jari",
    "EFT": "Estrada de Ferro Trombetas", "FSA": "Ferrovia Sul Atlântico", "CFN": "Companhia Ferroviária do Nordeste",
    "EFCJ": "Estrada de Ferro Campos do Jordão",
}
SEM_SIGLA = [(r"vit[óo]ria.{0,4}minas", "EFVM"), (r"tra[sn]+nordestina", "TLSA"), (r"centro-atl[âa]ntica", "FCA"),
             (r"valor da log", "VLI")]
URBANOS = re.compile(r"^(metr[ôo]|metrofor)", re.I)   # metrô e VLT ficam de fora, mesmo quando o tipo do trecho não foi informado


def operadora(nome):
    n = re.sub(r"\s+", " ", nome or "").strip()
    if not n:
        return "operadora não informada"
    if n.lower().startswith("cptm"):
        return "CPTM (trens metropolitanos de São Paulo)"
    if "nova transnordestina" in n.lower():
        return "Nova Transnordestina (em obras)"
    m = re.search(r"-\s*([A-Za-z]+)\s*$", n)
    if m and m.group(1).upper() in OPERADORAS:
        return OPERADORAS[m.group(1).upper()]
    for padrao, sigla in SEM_SIGLA:
        if re.search(padrao, n, re.I):
            return OPERADORAS[sigla]
    if n.lower() == "ferrovia norte-sul":
        return "Ferrovia Norte-Sul"
    return n.replace("Frro", "Ferro")


def ler(z, base):
    leitor = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), shx=io.BytesIO(z.read(base + ".shx")),
                              dbf=io.BytesIO(z.read(base + ".dbf")), encoding="utf-8")
    for sr in leitor.iterShapeRecords():
        yield sr.record.as_dict(), shape(sr.shape.__geo_interface__)


def km(g):
    return sum(GEOD.geometry_length(x) for x in getattr(g, "geoms", [g])) / 1000


def simples(g, tol, casas=3):
    return shapely.transform(shapely.simplify(g, tol, preserve_topology=False), lambda c: np.round(c, casas))


def gravar(arquivo, meta, feats):
    texto = json.dumps({"type": "FeatureCollection", "meta": meta, "features": feats}, ensure_ascii=False, separators=(",", ":"))
    (GEO / arquivo).write_text(texto, encoding="utf-8")
    print(f"{arquivo}: {len(feats)} feições, {len(texto) // 1024} KB")


def rodovias(z):
    grupos = defaultdict(list)
    for d, g in ler(z, "rod_trecho_rodoviario_l"):
        s = d["sigla"].strip()
        federal = s.startswith("BR-") or d["jurisdicao"] == "Federal"
        estadual = bool(re.match(r"^[A-Z]{2}-\d", s)) and not federal
        pav = d["revestimen"] == "Pavimentado"
        if d["situacaofi"] in ("Abandonada", "Destruída", "Planejada") or not (federal or (estadual and pav)):
            continue
        dupla = d["canteirodi"] == "Sim" or (d["nrpistas"] or 0) >= 2
        conc = d["concession"].strip()
        conc = "" if conc in ("", "Não") else ("concessionada" if conc.upper() == "ANTT" else conc)   # "ANTT" é a agência, não a concessionária
        if not conc and d["administra"] == "Concessionada":
            conc = "concessionada"
        grupos[("F" if federal else "E", s, int(pav), int(dupla), conc)].extend(getattr(g, "geoms", [g]))
    estados = json.loads((GEO / "estados_detalhe.json").read_text(encoding="utf-8"))["features"]
    ufs = [(f["properties"]["sigla"], shape(f["geometry"])) for f in estados]
    arvore = shapely.STRtree([g for _, g in ufs])
    por_uf = defaultdict(lambda: [0.0, 0.0, 0.0])   # rodovia federal por estado: [total, pavimentada, pista dupla]
    saidas = {"F": [], "E": []}
    extensao = {"F": 0.0, "E": 0.0, "F_pav": 0.0}
    for (tipo, s, pav, dupla, conc), linhas in sorted(grupos.items()):
        g = linemerge(linhas)
        k = km(g)
        extensao[tipo] += k
        if tipo == "F" and pav:
            extensao["F_pav"] += k
        if tipo == "F":
            for i in arvore.query(g):
                parte = g.intersection(ufs[i][1])
                if parte.is_empty:
                    continue
                kp = km(parte)
                v = por_uf[ufs[i][0]]
                v[0] += kp
                v[1] += kp if pav else 0
                v[2] += kp if dupla else 0
        g = simples(g, TOL_ROD)
        if g.is_empty:
            continue
        props = {"s": s, "p": pav, "d": dupla}
        if conc:
            props["c"] = conc
        saidas[tipo].append({"type": "Feature", "properties": props, "geometry": mapping(g)})
    fonte = f"IBGE, Base Cartográfica Contínua 1:250.000 ({VERSAO}); sigla e jurisdição atualizadas pelo IBGE com dados do DNIT"
    base = {"fonte": fonte, "nivel": "manual", "baixado_em": date.today().isoformat(),
            "simplificacao": f"tolerância {TOL_ROD}° (~450 m); coordenadas com 3 casas (~110 m)"}
    gravar("rodovias.json", {**base, "titulo": "Rodovias federais", "km": round(extensao["F"]), "km_pavimentados": round(extensao["F_pav"]),
                             "nota": "rodovias com sigla BR ou de jurisdição federal; inclui trechos em que a BR coincide com uma rodovia estadual",
                             "campos": {"s": "sigla", "p": "pavimentada (1/0)", "d": "pista dupla (1/0)", "c": "concessionária"},
                             "km_por_uf": {u: [round(a) for a in v] for u, v in sorted(por_uf.items())},
                             "km_por_uf_campos": ["total", "pavimentada", "pista dupla"]}, saidas["F"])
    gravar("rodovias_estaduais.json", {**base, "titulo": "Rodovias estaduais pavimentadas", "km": round(extensao["E"])}, saidas["E"])


def ferrovias(z):
    estados = json.loads((GEO / "estados_detalhe.json").read_text(encoding="utf-8"))["features"]
    ufs = [(f["properties"]["sigla"], shape(f["geometry"])) for f in estados]
    arvore = shapely.STRtree([g for _, g in ufs])
    grupos = defaultdict(list)
    for d, g in ler(z, "fer_trecho_ferroviario_l"):
        if (d["tipotrecho"] in ("Trecho para metrô", "Trecho para aeromóvel") or d["situacaofi"] in ("Abandonada", "Destruída")
                or URBANOS.match((d["nome"] or "").strip())):
            continue
        obra = d["situacaofi"] == "Em construção"
        grupos[(operadora(d["nome"]), int(obra), d["bitola"] or "")].extend(getattr(g, "geoms", [g]))
    trechos, km_uf, km_obra = [], defaultdict(float), 0.0
    for (op, obra, bitola), linhas in sorted(grupos.items()):
        g = linemerge(linhas)
        for i in arvore.query(g):
            uf, poli = ufs[i]
            parte = g.intersection(poli)
            if parte.is_empty or parte.length == 0:
                continue
            k = km(parte)
            if obra:
                km_obra += k
            else:
                km_uf[uf] += k
            s = simples(parte, TOL_FER)
            for linha in getattr(s, "geoms", [s]):
                if linha.geom_type == "LineString" and len(linha.coords) >= 2:
                    t = {"uf": uf, "l": [list(c) for c in linha.coords], "op": op}
                    if obra:
                        t["obra"] = 1
                    if bitola and bitola != "Desconhecida":
                        t["b"] = bitola.replace("  ", " ")
                    trechos.append(t)
    meta = {"fonte": f"IBGE, Base Cartográfica Contínua 1:250.000 ({VERSAO})", "nivel": "manual", "baixado_em": date.today().isoformat(),
            "titulo": "Ferrovias", "km_em_operacao": round(sum(km_uf.values())), "km_em_obras": round(km_obra),
            "nota": "sem metrô, aeromóvel, linhas abandonadas e destruídas; trechos de situação não informada entram como existentes"}
    dados = {"meta": meta, "km_por_uf": {k: round(v) for k, v in sorted(km_uf.items(), key=lambda x: -x[1])}, "trechos": trechos}
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    (GEO / "ferrovias.json").write_text(texto, encoding="utf-8")
    print(f"ferrovias.json: {len(trechos)} trechos, {meta['km_em_operacao']} km em operação, {meta['km_em_obras']} km em obras, {len(texto) // 1024} KB")


def portos(z):
    estados = json.loads((GEO / "estados_detalhe.json").read_text(encoding="utf-8"))["features"]
    ufs = [(f["properties"]["sigla"], shape(f["geometry"])) for f in estados]
    arvore = shapely.STRtree([g for _, g in ufs])
    lista = []
    for d, g in ler(z, "hdv_complexo_portuario_p"):
        if d["situacaofi"] in ("Abandonada", "Destruída") or d["operaciona"] == "Não":
            continue
        p = g if g.geom_type == "Point" else g.centroid
        # porto fica na costa ou na margem do rio: vale o estado mais próximo (até ~20 km)
        i = arvore.nearest(p)
        uf = ufs[i][0] if ufs[i][1].distance(p) < 0.2 else ""
        item = {"n": re.sub(r"\s+", " ", d["nome"]).strip() or "Porto sem nome na base", "c": [round(p.x, 4), round(p.y, 4)], "uf": uf}
        if d["tipocomple"] == "Porto organizado":
            item["org"] = 1
        if d["situacaofi"] == "Em construção":
            item["obra"] = 1
        lista.append(item)
    lista.sort(key=lambda x: (x["uf"], x["n"]))
    (GEO / "portos.json").write_text(json.dumps(lista, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"portos.json: {len(lista)} complexos portuários ({sum(1 for x in lista if x.get('org'))} portos organizados)")


def main(cache):
    if cache:
        dados = (Path(cache) / ZIP).read_bytes()
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "brasil-em-camadas (dados abertos)"})
        with urllib.request.urlopen(req, timeout=3600) as r:
            dados = r.read()
    z = zipfile.ZipFile(io.BytesIO(dados))
    rodovias(z)
    ferrovias(z)
    portos(z)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", help=f"pasta com o {ZIP} já baixado")
    main(ap.parse_args().cache)
