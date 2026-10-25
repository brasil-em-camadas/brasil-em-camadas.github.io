"""Fronteira terrestre do Brasil por tipo (rio ou lagoa, seca, seca na mata) e passagens de fronteira (cidades gêmeas),
com o trecho das estradas do outro lado. Feito para a versão de teste do mapa em 25/10/2026 (pedidos do Edu de 23/10/2026:
"contorno do Brasil pelo tipo de fronteira" e "ligações por estrada com os países vizinhos").

Fontes:
  IBGE, BC250 versão 2025 (bc_250_shapefiles_2026_03_03.zip, ~800 MB): países (lml_pais_a; a linha de fronteira é a
    divisa entre o Brasil e cada vizinho), hidrografia (hid_massa_dagua_a, hid_trecho_drenagem_l) e rodovias
    (rod_trecho_rodoviario_l)
  IBGE, Monitoramento da Cobertura e Uso da Terra, grade de 1 km, série revisada (Cobertura_uso_terra_Brasil_serie_revisada.zip,
    ~430 MB): classe 6 = vegetação florestal, em 2020
  IBGE, Municípios da Faixa de Fronteira e Cidades Gêmeas 2024 (lista oficial das 33 cidades gêmeas: Portaria MDR nº 2.507,
    de 05/10/2021)
  scripts/dados/cidades_gemeas.csv: cidade do outro lado e tipo de ligação de cada par, com a fonte de cada linha
  Natural Earth, ne_10m_roads (domínio público): estradas dos países vizinhos (desenho aproximado)

Como cada trecho da fronteira é classificado (peças de ~250 m):
  rio ou lagoa  a peça fica a menos de 60 m de uma massa d'água ou a menos de 200 m de um rio da BC250; trechos de água
                curtos (menos de ~2 km: a linha só cruza um riacho) viram secos, e secos curtos (menos de ~1,5 km) entre
                águas viram água (ilhas, desenho)
  mata          peça seca em que a vegetação florestal ocupa metade ou mais dos quadrados de 1 km em volta (5 × 5 km)
  seca          as outras (campo, pasto, lavoura, cidade)
As extensões medidas no desenho ficam no "meta"; as oficiais, por país, são as do IBGE (Anuário Estatístico 2023,
tabela 1.1.2.2, com os números das comissões demarcadoras do Itamaraty).

Roda à mão:
  pip install shapely pyproj pyshp numpy xlrd
  python scripts/gerar_fronteira.py --cache PASTA   (PASTA com os arquivos; os que faltarem são baixados)
Saídas em site/data/geo/: fronteira_tipos.json e passagens.json
"""
import argparse
import collections
import csv
import io
import json
import math
import pickle
import struct
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import shapefile  # pyshp
import shapely
import shapely.ops
import xlrd
from pyproj import Geod, Transformer
from shapely.geometry import LineString, MultiLineString, Point, mapping, shape
from shapely.strtree import STRtree

RAIZ = Path(__file__).resolve().parent.parent
GEO = RAIZ / "site" / "data" / "geo"
DADOS = RAIZ / "scripts" / "dados"
GEOD = Geod(ellps="GRS80")
ARQ = {
    "bc250": ("bc_250_shapefiles_2026_03_03.zip",
              "https://geoftp.ibge.gov.br/cartas_e_mapas/bases_cartograficas_continuas/bc250/versao2025/shapefiles/bc_250_shapefiles_2026_03_03.zip"),
    "uso": ("Cobertura_uso_terra_Brasil_serie_revisada.zip",
            "https://geoftp.ibge.gov.br/informacoes_ambientais/cobertura_e_uso_da_terra/monitoramento/grade_estatistica/serie_revisada_2022/vetores_compactados/Brasil/Cobertura_uso_terra_Brasil_serie_revisada.zip"),
    "gemeas": ("Mun_Faixa_de_Fronteira_Cidades_Gemeas_2024.xls",
               "https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/municipios_da_faixa_de_fronteira/2024/Mun_Faixa_de_Fronteira_Cidades_Gemeas_2024.xls"),
    "ne": ("ne_10m_roads.zip", "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip"),
}
# projeção da grade estatística do IBGE (Albers, SIRGAS 2000): os quadrados de 1 km têm o nome "1KME<x km>N<y km>"
AEA = Transformer.from_crs("EPSG:4674", "+proj=aea +lat_0=-12 +lon_0=-54 +lat_1=-2 +lat_2=-22 +x_0=5000000 +y_0=10000000 "
                           "+ellps=GRS80 +units=m +no_defs", always_xy=True)
PAISES = {"URU": "Uruguai", "ARG": "Argentina", "PAR": "Paraguai", "BOL": "Bolívia", "PER": "Peru", "COL": "Colômbia",
          "VEN": "Venezuela", "GUY": "Guiana", "SUR": "Suriname", "GUF": "Guiana Francesa (França)"}
# extensão oficial da fronteira com cada país, em km (IBGE, Anuário Estatístico do Brasil 2023, tabela 1.1.2.2)
OFICIAL = {"VEN": 2199, "GUY": 1606, "SUR": 593, "GUF": 730, "URU": 1068, "ARG": 1261, "PAR": 1365, "BOL": 3423, "PER": 2995, "COL": 1644}
FONTES_PARES = {
    "UFSM2025": "Fabiane e Spinelli (2025), Cidades gêmeas brasileiras: espaços contraditórios de integração, Geografia Ensino & Pesquisa (UFSM), "
                "v. 26, quadro 1 (fontes do quadro: IDESF, 2021; Caye e Rukert, 2020)",
    "FURB2024": "Porto (2024), Observações de campo nas fronteiras Brasil/Venezuela e Brasil/Guiana, Revista Brasileira de Desenvolvimento "
                "Regional (FURB), v. 12, n. 3",
    "AMAZONIA2022": "Portal Amazônia, Saiba quais cidades-gêmeas são encontradas na Amazônia Internacional (09/06/2022)",
    "UFGD2016": "Fernandes (2016), Entre-Lugar (UFGD), v. 7, n. 13",
    "PONTAPORA2024": "Prefeitura de Ponta Porã, Lei municipal nº 4.651, de 27/09/2024",
    "CB2025": "Correio Braziliense, Cidades na fronteira do Brasil com Paraguai (dez/2025)",
}
FONTES_CURTAS = {"UFSM2025": "Fabiane e Spinelli, UFSM (2025)", "FURB2024": "Porto, FURB (2024)", "AMAZONIA2022": "Portal Amazônia (2022)",
                 "UFGD2016": "Fernandes, UFGD (2016)", "PONTAPORA2024": "Lei municipal de Ponta Porã (2024)", "CB2025": "Correio Braziliense (2025)"}
PASSO = 0.0025          # comprimento das peças da fronteira (graus, ~250-280 m)
AGUA_M, AGUA_D = 60, 200  # metros até uma massa d'água / até um rio para a peça contar como fronteira em água


def baixar(cache, chave):
    nome, url = ARQ[chave]
    p = cache / nome
    if not p.exists():
        print("baixando", url)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Brasil em Camadas)"})
        with urllib.request.urlopen(req, timeout=600) as r, open(p, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
    return p


def leitor(z, base, encoding="utf-8"):
    return shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), shx=io.BytesIO(z.read(base + ".shx")),
                            dbf=io.BytesIO(z.read(base + ".dbf")), encoding=encoding)


def km(g):
    return sum(GEOD.geometry_length(x) for x in getattr(g, "geoms", [g])) / 1000


def km_seg(a, b):
    return GEOD.line_length([a[0], b[0]], [a[1], b[1]]) / 1000


def grade_uso(cache):
    """grade de 1 km com a classe de 2020 (numpy, linhas = y em km, colunas = x em km)"""
    npz = cache / "uso2020_grade.npz"
    if npz.exists():
        g = np.load(npz)
        return g["G"], int(g["e0"]), int(g["n0"])
    dbf = cache / "Cobertura_uso_terra_Brasil_serie_revisada.dbf"
    if not dbf.exists():
        with zipfile.ZipFile(baixar(cache, "uso")) as z:
            z.extract("Cobertura_uso_terra_Brasil_serie_revisada.dbf", cache)
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
    o, t = campos["INDICE_GRE"]; idx = np.char.strip(np.array(mm[:, o:o + t]).view(f"S{t}").ravel()).astype("U20")
    o, t = campos["USO2020"]; uso = np.char.strip(np.array(mm[:, o:o + t]).view(f"S{t}").ravel()).astype(np.int16)
    partes = np.char.partition(np.char.lstrip(idx, "1KME"), "N")
    E, N = partes[:, 0].astype(np.int32), partes[:, 2].astype(np.int32)
    e0, n0 = int(E.min()), int(N.min())
    G = np.zeros((N.max() - n0 + 1, E.max() - e0 + 1), np.int8)
    G[N - n0, E - e0] = uso
    np.savez_compressed(npz, G=G, e0=e0, n0=n0)
    return G, e0, n0


def linhas_fronteira(z):
    paises = {}
    for sr in leitor(z, "lml_pais_a").iterShapeRecords():
        d = sr.record.as_dict(); paises[d["codiso3166"]] = shape(sr.shape.__geo_interface__)
    br = paises["BRA"]
    linhas = {}
    for k in PAISES:
        inter = br.boundary.intersection(paises[k].buffer(0.0005))
        partes = [g for g in getattr(inter, "geoms", [inter]) if g.geom_type == "LineString"]
        partes += [l for g in getattr(inter, "geoms", [inter]) if g.geom_type == "MultiLineString" for l in g.geoms]
        linhas[k] = shapely.ops.linemerge(partes)
    return br, {k: paises[k] for k in PAISES}, linhas


def hidrografia(z, zona):
    shapely.prepare(zona)
    bx = zona.bounds
    out = {}
    for base in ("hid_massa_dagua_a", "hid_trecho_drenagem_l"):
        r = leitor(z, base); achados = []
        for i, s in enumerate(r.iterShapes()):
            b = s.bbox
            if b[2] < bx[0] or b[0] > bx[2] or b[3] < bx[1] or b[1] > bx[3]:
                continue
            g = shape(s.__geo_interface__)
            if zona.intersects(g):
                achados.append((i, g))
        out[base] = [(r.record(i).as_dict(), g) for i, g in achados]
        print(base, "perto da fronteira:", len(achados))
    return out


def classificar(linhas, hid, G, e0, n0):
    massas, drens = hid["hid_massa_dagua_a"], hid["hid_trecho_drenagem_l"]
    tm, td = STRtree([g for _, g in massas]), STRtree([g for _, g in drens])
    pecas = collections.defaultdict(list)
    for pais, ln in linhas.items():
        for parte in getattr(ln, "geoms", [ln]):
            L = parte.length; n = max(2, int(L / PASSO))
            for i in range(n):
                a, b = parte.interpolate(i * L / n), parte.interpolate((i + 1) * L / n)
                m = Point((a.x + b.x) / 2, (a.y + b.y) / 2)
                dm, rm = 9.0, None
                for j in tm.query(m.buffer(0.01)):
                    dd = massas[j][1].distance(m)
                    if dd < dm: dm, rm = dd, massas[j][0]
                ddr, rd = 9.0, None
                for j in td.query(m.buffer(0.01)):
                    dd = drens[j][1].distance(m)
                    if dd < ddr: ddr, rd = dd, drens[j][0]
                dm, ddr = dm * 111000, ddr * 111000
                if dm < AGUA_M:
                    nome = (rm["nome"] or (rd["nome"] if rd and ddr < AGUA_D else "")).strip()
                    t = "lagoa" if rm["tipomassad"] in ("Lago/Lagoa", "Laguna") or nome.lower().startswith(("lagoa", "lago ", "laguna")) else "rio"
                elif ddr < AGUA_D:
                    t, nome = "rio", (rd["nome"] or "").strip()
                else:
                    t, nome = "seca", ""
                pecas[(pais, id(parte))].append(dict(pais=pais, a=(a.x, a.y), b=(b.x, b.y), t=t, n=nome))
    def corridas(lst, f):
        out = []
        for p in lst:
            k = f(p)
            if out and out[-1][0] == k: out[-1][1].append(p)
            else: out.append([k, [p]])
        return out
    for lst in pecas.values():
        agua = lambda p: "agua" if p["t"] != "seca" else "seca"
        for i, (k, ps) in enumerate(cs := corridas(lst, agua)):
            if k == "agua" and len(ps) < 8 and 0 < i < len(cs) - 1:
                for p in ps: p["t"], p["n"] = "seca", ""
        for i, (k, ps) in enumerate(cs := corridas(lst, agua)):
            if k == "seca" and len(ps) < 6 and 0 < i < len(cs) - 1:
                v = cs[i - 1][1][-1]
                for p in ps: p["t"], p["n"] = v["t"], v["n"]
        for p in lst:
            if p["t"] != "seca":
                continue
            x, y = AEA.transform((p["a"][0] + p["b"][0]) / 2, (p["a"][1] + p["b"][1]) / 2)
            E, N = int(x // 1000) - e0, int(y // 1000) - n0
            jan = G[max(0, N - 2):N + 3, max(0, E - 2):E + 3].ravel()
            jan = jan[jan > 0]
            if len(jan) and (jan == 6).sum() / len(jan) >= 0.5:
                p["t"] = "mata"
        for i, (k, ps) in enumerate(cs := corridas(lst, lambda p: p["t"])):
            if k in ("mata", "seca") and len(ps) < 11 and 0 < i < len(cs) - 1 and cs[i - 1][0] in ("mata", "seca"):
                for p in ps: p["t"] = cs[i - 1][0]
    return pecas


def gravar(nome, meta, feats):
    texto = json.dumps({"type": "FeatureCollection", "meta": meta, "features": feats}, ensure_ascii=False, separators=(",", ":"))
    (GEO / nome).write_text(texto, encoding="utf-8")
    print(f"{nome}: {len(feats)} feições, {len(texto) // 1024} KB")


def arredonda(g, tol=0.0025, casas=3):
    return shapely.transform(shapely.simplify(g, tol, preserve_topology=False), lambda c: np.round(c, casas))


def fronteira_tipos(pecas):
    feats, medida = [], collections.defaultdict(lambda: collections.defaultdict(float))
    for lst in pecas.values():
        run = []
        def fecha():
            if not run: return
            g = arredonda(LineString([run[0]["a"]] + [p["b"] for p in run]))
            if not g.is_empty and g.length > 0:
                feats.append({"type": "Feature", "properties": {"t": run[0]["t"], "n": run[0]["n"], "p": run[0]["pais"]},
                              "geometry": mapping(g)})
        for p in lst:
            medida[p["pais"]][p["t"]] += km_seg(p["a"], p["b"])
            if run and (run[-1]["t"], run[-1]["n"]) != (p["t"], p["n"]):
                fecha(); run = []
            run.append(p)
        fecha()
    return feats, {k: {t: round(v) for t, v in d.items()} for k, d in medida.items()}


def passagens(z, cache, br, viz, linhas, pecas):
    borda = shapely.union_all(list(linhas.values()))
    zona = borda.buffer(0.03); shapely.prepare(zona)
    # rodovias que chegam perto da fronteira (contatos: cruzam a linha ou terminam a menos de ~450 m dela)
    contatos = []
    r = leitor(z, "rod_trecho_rodoviario_l")
    for sr in r.iterShapeRecords():
        g = shape(sr.shape.__geo_interface__)
        if not zona.intersects(g) or g.distance(borda) > 0.012:
            continue
        d = sr.record.as_dict()
        pts = [q for q in getattr(g.intersection(borda), "geoms", [g.intersection(borda)]) if q.geom_type == "Point"]
        for l in getattr(g, "geoms", [g]):
            for c in (l.coords[0], l.coords[-1]):
                if Point(c).distance(borda) < 0.004: pts.append(Point(c))
        peso = (3 if d["jurisdicao"] == "Federal" else 2 if d["jurisdicao"].startswith("Estadual") else 1) + (1 if d["revestimen"].startswith("Pav") else 0)
        for q in pts:
            contatos.append(dict(p=shapely.ops.nearest_points(borda, q)[0], sigla=d["sigla"], peso=peso))
    print("contatos de rodovias com a fronteira:", len(contatos))
    # municípios (para achar a passagem de cidades gêmeas com a sede longe da fronteira, como Cáceres)
    with open(DADOS / "cidades_gemeas.csv", encoding="utf-8") as f:
        codigos = {l["codigo_ibge"] for l in csv.DictReader(f)}
    mun = {}
    r = leitor(z, "lml_municipio_a")
    for i, rec in enumerate(r.iterRecords()):
        if rec["geocodigo"] in codigos: mun[rec["geocodigo"]] = shape(r.shape(i).__geo_interface__)
    sedes = {}
    with open(DADOS / "sedes_municipais.csv", encoding="utf-8") as f:
        for l in csv.DictReader(f): sedes[l["codigo_ibge"]] = Point(float(l["longitude"]), float(l["latitude"]))
    sh = xlrd.open_workbook(baixar(cache, "gemeas")).sheets()[0]
    h = sh.row_values(0)
    oficiais = {str(sh.row_values(i)[0]) for i in range(1, sh.nrows) if str(sh.row_values(i)[h.index("CID_GEMEA")]).strip()}
    with open(DADOS / "cidades_gemeas.csv", encoding="utf-8") as f:
        pares = list(csv.DictReader(f))
    faltam = oficiais - {p["codigo_ibge"] for p in pares}
    if faltam:
        raise SystemExit(f"cidades gêmeas oficiais sem par em cidades_gemeas.csv: {sorted(faltam)}")
    cod_pais = {v: k for k, v in PAISES.items()}
    tc = STRtree([c["p"] for c in contatos])
    todas = [p for lst in pecas.values() for p in lst]
    tpe = STRtree([Point((p["a"][0] + p["b"][0]) / 2, (p["a"][1] + p["b"][1]) / 2) for p in todas])
    pontos, notas = [], []
    for par in pares:
        if par["ligacao"].startswith("sem ligação direta"):
            # Guaíra: a passagem é a de Mundo Novo; vira uma nota na passagem que leva à mesma cidade do outro lado
            notas.append((par["cidade_vizinha"], f"{par['municipio']} ({par['uf']}) também é cidade gêmea de {par['cidade_vizinha']}: {par['ligacao']}"))
            continue
        k = cod_pais[par["pais"]]
        sede, area = sedes[par["codigo_ibge"]], mun.get(par["codigo_ibge"])
        caixa = shapely.geometry.box(*area.bounds).buffer(0.02) if area is not None else sede.buffer(0.25)
        cand = [contatos[j] for j in tc.query(caixa)]
        cand = [c for c in cand if linhas[k].distance(c["p"]) < 0.002 and (c["p"].distance(sede) < 0.25 or (area is not None and area.distance(c["p"]) < 0.02))]
        if cand:
            c = max(cand, key=lambda c: (c["peso"], -c["p"].distance(sede)))
            ponto, sigla = c["p"], c["sigla"]
        else:
            ponto, sigla = shapely.ops.nearest_points(linhas[k], sede)[0], ""
        # tipo da fronteira no ponto
        perto = todas[int(tpe.nearest(ponto))]
        pontos.append(dict(p=ponto, k=k, par=par, sigla=sigla, tipo=perto["t"], rio=perto["n"]))
    # junta pares no mesmo ponto (ex.: Barracão e Dionísio Cerqueira; Brasiléia e Epitaciolândia)
    grupos = []
    for q in pontos:
        for g in grupos:
            if g["p"].distance(q["p"]) < 0.03:
                g["itens"].append(q); break
        else:
            grupos.append(dict(p=q["p"], k=q["k"], itens=[q]))
    # estradas do outro lado (Natural Earth), até ~45 km da passagem
    ne = []
    tpass = STRtree([g["p"] for g in grupos])
    with zipfile.ZipFile(baixar(cache, "ne")) as zne:
        base = [n for n in zne.namelist() if n.endswith(".shp")][0][:-4]
        r = leitor(zne, base, "latin-1")
        for s in r.iterShapes():
            b = s.bbox
            if b[2] < -82 or b[0] > -30 or b[3] < -40 or b[1] > 12: continue   # só a América do Sul
            g = shape(s.__geo_interface__)
            if len(tpass.query(g.buffer(0.1))): ne.append(g)
    feats = []
    for g in grupos:
        P = g["p"]; pais = viz[g["k"]]
        circ = P.buffer(0.42)
        estradas = []
        for e in ne:
            if e.distance(P) > 0.05: continue
            parte = e.intersection(pais).intersection(circ)
            for l in getattr(parte, "geoms", [parte]):
                if l.geom_type != "LineString" or l.length < 0.01: continue
                if l.distance(P) > 0.05: continue
                # a linha começa na passagem: corta no ponto mais perto e liga os dois lados ao ponto
                s = l.project(P)
                for pedaco in (shapely.ops.substring(l, s, 0), shapely.ops.substring(l, s, l.length)):
                    if pedaco.length < 0.01: continue
                    coords = list(pedaco.coords)
                    if Point(coords[-1]).distance(P) < Point(coords[0]).distance(P): coords = coords[::-1]
                    estradas.append(LineString([(P.x, P.y)] + coords))
        for l in estradas:
            gg = arredonda(l, 0.003)
            if gg.length > 0.02:
                feats.append({"type": "Feature", "properties": {"k": "estrada", "p": g["k"]}, "geometry": mapping(gg)})
        itens = g["itens"]
        brs = sorted({f"{q['par']['municipio']} ({q['par']['uf']})" for q in itens})
        vz = sorted({f"{q['par']['cidade_vizinha']} ({q['par']['pais']})" for q in itens})
        lig = next((q["par"]["ligacao"] for q in itens if q["par"]["ligacao"]), "")
        tipo, rio = itens[0]["tipo"], itens[0]["rio"]
        fonte = sorted({q["par"]["fonte"] for q in itens})
        siglas = sorted({q["sigla"] for q in itens if q["sigla"]})
        nota = "; ".join(t for viz_, t in notas if any(q["par"]["cidade_vizinha"] == viz_ for q in itens))
        feats.append({"type": "Feature", "properties": {"k": "passagem", "p": g["k"], "br": " e ".join(brs), "viz": " e ".join(vz),
                      "lig": lig, "t": tipo, "rio": rio, "rod": ", ".join(siglas), "f": ",".join(fonte), "estradas": len(estradas),
                      **({"nota": nota} if nota else {})},
                      "geometry": {"type": "Point", "coordinates": [round(g["p"].x, 4), round(g["p"].y, 4)]}})
    print("passagens:", len(grupos))
    return feats


def main(cache):
    cache.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(baixar(cache, "bc250"))
    br, viz, linhas = linhas_fronteira(z)
    pk = cache / f"pecas_{PASSO}_{AGUA_M}_{AGUA_D}.pkl"   # a classificação demora uns minutos; fica guardada no cache
    if pk.exists():
        pecas = pickle.loads(pk.read_bytes())
    else:
        hid = hidrografia(z, shapely.union_all(list(linhas.values())).buffer(0.03))
        G, e0, n0 = grade_uso(cache)
        pecas = classificar(linhas, hid, G, e0, n0)
        pk.write_bytes(pickle.dumps(dict(pecas)))
    feats, medida = fronteira_tipos(pecas)
    tot = collections.defaultdict(float)
    for d in medida.values():
        for t, v in d.items(): tot[t] += v
    hoje = date.today().isoformat()
    gravar("fronteira_tipos.json", {
        "titulo": "Fronteira terrestre por tipo", "nivel": "calculado", "gerado_em": hoje,
        "fonte": "IBGE, BC250 versão 2025 (países e hidrografia) e Monitoramento da Cobertura e Uso da Terra (grade de 1 km, 2020); "
                 "classificação feita pelo projeto (scripts/gerar_fronteira.py)",
        "tipos": {"rio": "em rio", "lagoa": "em lagoa", "seca": "seca (campo, pasto, lavoura ou cidade)", "mata": "seca, na mata"},
        "paises": PAISES, "km_oficial": OFICIAL, "km_oficial_fonte": "IBGE, Anuário Estatístico do Brasil 2023, tabela 1.1.2.2",
        "km_desenho": medida, "km_desenho_total": {t: round(v) for t, v in tot.items()},
        "nota": "extensões medidas no desenho da BC250 (1:250.000), aproximadas; a soma não bate com a oficial porque o desenho é "
                "simplificado e as pontas de cada país (tríplices fronteiras) foram cortadas pelo projeto"}, feats)
    pf = passagens(z, cache, br, viz, linhas, pecas)
    gravar("passagens.json", {
        "titulo": "Passagens de fronteira (cidades gêmeas)", "nivel": "manual", "gerado_em": hoje,
        "fonte": "IBGE, Municípios da Faixa de Fronteira e Cidades Gêmeas 2024 (Portaria MDR nº 2.507/2021); cidade do outro lado "
                 "e ligação: scripts/dados/cidades_gemeas.csv; ponto e rodovia: IBGE, BC250; estradas do outro lado: Natural Earth "
                 "(ne_10m_roads, domínio público, desenho aproximado)",
        "fontes_pares": FONTES_PARES, "fontes_curtas": FONTES_CURTAS}, pf)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=Path("cache_fronteira"))
    main(ap.parse_args().cache)
