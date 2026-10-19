"""Gera as camadas marítimas do mapa a partir do Marine Regions (VLIZ, instituto belga de pesquisa do mar).

Base aberta internacional, licença CC-BY 4.0. O próprio Marine Regions avisa que os limites servem
para fins científicos e educativos e não têm valor legal; os limites legais estão nas cartas da Marinha.

Roda só quando acionado à mão (os limites mudam raramente):
  - no GitHub: aba Actions -> "Gerar limites marítimos" -> Run workflow;
  - ou no computador: pip install shapely pyproj  e  python scripts/gerar_limites_maritimos.py
    (com --cache PASTA, usa arquivos já baixados, com os nomes br_<camada>.json).

Saídas em site/data/geo/:
  zee.json                   Zona Econômica Exclusiva (das 12 às 200 milhas) e a linha do limite
                             (200 milhas e limites laterais com a Guiana Francesa e o Uruguai)
  mar_territorial.json       mar territorial (12 milhas), a linha das 12 milhas e as linhas de base retas
  zona_contigua.json         zona contígua (das 12 às 24 milhas) e a linha das 24 milhas
  plataforma_estendida.json  plataforma continental além das 200 milhas, por região e situação na ONU

Como é feito:
  1. Baixa só os polígonos do Brasil (serviço WFS do Marine Regions).
  2. Junta todas as bordas e remonta as áreas como um quebra-cabeça sem frestas: cada pedaço fica
     com uma única dona (águas interiores > mar territorial > zona contígua > ZEE > plataforma).
  3. Simplifica tudo junto (as bordas comuns continuam idênticas) e arredonda a ~100 m.
  4. Mede as áreas no elipsoide WGS84, sempre nos polígonos originais, antes de simplificar.

Margem Equatorial: o Marine Regions (versão 2, 2024) ainda traz o contorno pedido pelo Brasil em 2017.
A ONU (CLPC) aprovou o limite em 27/02/2025. Os 462 pontos do limite aprovado (Tabela 4 do Anexo I do resumo
das recomendações) estão em scripts/dados/clpc_margem_equatorial_2025.csv; o script confere cada ponto pela
distância ao anterior informada na própria tabela e corta a área pedida em 2017 por essa linha.
Região Sul: o contorno do Marine Regions coincide ponto a ponto com o resumo das recomendações de 2019
(conferido em 19/10/2026), por isso é usado direto.
"""
import argparse
import csv
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import shapely
from pyproj import Geod
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, mapping, shape
from shapely.ops import linemerge, polygonize, polylabel, split, unary_union

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "geo"
PONTOS_EQ = RAIZ / "scripts" / "dados" / "clpc_margem_equatorial_2025.csv"
WFS = "https://geo.vliz.be/geoserver/MarineRegions/wfs"
CAMADAS = {
    "eez": "iso_sov1='BRA'",
    "eez_12nm": "iso_sov1='BRA'",
    "eez_24nm": "iso_sov1='BRA'",
    "eez_internal_waters": "iso_sov1='BRA'",
    "eez_boundaries": "sovereign1='Brazil' OR sovereign2='Brazil'",
    "ecs": "iso_sov1='BRA'",
}
TOL = 0.004      # tolerância da simplificação, em graus (~450 m)
GRADE = 0.001    # arredondamento das coordenadas, em graus (~110 m)
GEOD = Geod(ellps="WGS84")
HOJE = date.today().isoformat()

CITA = {
    "eez": "Flanders Marine Institute (2023). Maritime Boundaries Geodatabase: Maritime Boundaries and "
           "Exclusive Economic Zones (200NM), version 12. https://doi.org/10.14284/632",
    "eez_12nm": "Flanders Marine Institute (2023). Maritime Boundaries Geodatabase: Territorial Seas (12NM), "
                "version 4. https://doi.org/10.14284/633",
    "eez_24nm": "Flanders Marine Institute (2023). Maritime Boundaries Geodatabase: Contiguous Zones (24NM), "
                "version 4. https://doi.org/10.14284/630",
    "eez_internal_waters": "Flanders Marine Institute (2023). Maritime Boundaries Geodatabase: Internal Waters, "
                           "version 4. https://doi.org/10.14284/631",
    "ecs": "Flanders Marine Institute (2024). Maritime Boundaries Geodatabase: Extended Continental Shelves, "
           "version 2. https://doi.org/10.14284/697",
}
CLPC_EQ = ("CLPC/ONU, resumo das recomendações sobre a Margem Equatorial (pedido revisto de 2017), aprovado "
           "em 27/02/2025, Anexo I, Tabela 4. https://static.un.org/Depts/los/clcs_new/submissions_files/"
           "bra02_rev17/20250227ComRecBrarev1summary.pdf")
LICENCA = "CC-BY 4.0 (Marine Regions, www.marineregions.org). Derivado simplificado; o original está no Marine Regions."
SEM_VALOR_LEGAL = "Sem valor legal: os limites oficiais estão nas cartas náuticas da Marinha do Brasil."


# ---------- leitura ----------
def baixar(camada, filtro, cache):
    if cache:
        return json.loads((Path(cache) / f"br_{camada}.json").read_text(encoding="utf-8"))
    q = urllib.parse.urlencode({"service": "WFS", "version": "1.0.0", "request": "GetFeature",
                                "outputFormat": "application/json", "typeName": f"MarineRegions:{camada}",
                                "CQL_FILTER": filtro})
    req = urllib.request.Request(f"{WFS}?{q}", headers={"User-Agent": "brasil-em-camadas"})
    with urllib.request.urlopen(req, timeout=600) as r:
        dados = json.load(r)
    print(f"baixado {camada}: {len(dados['features'])} feições")
    return dados


VERSOES = {"eez": "v12", "eez_12nm": "v4", "eez_24nm": "v4", "eez_internal_waters": "v4", "ecs": "v02"}


def conferir_versoes():
    """As citações e os textos do site dizem a versão; se o Marine Regions mudou de versão, para e avisa."""
    req = urllib.request.Request(f"{WFS}?service=WFS&version=2.0.0&request=GetCapabilities",
                                 headers={"User-Agent": "brasil-em-camadas"})
    with urllib.request.urlopen(req, timeout=300) as r:
        cap = r.read().decode("utf-8", "replace")
    for camada, v in VERSOES.items():
        i = cap.find(f"<Name>MarineRegions:{camada}</Name>")
        titulo = cap[i:i + 400].split("<Title>")[1].split("</Title>")[0] if i >= 0 else ""
        if f"({v}," not in titulo:
            raise SystemExit(f"Marine Regions mudou a camada {camada}: '{titulo}'. Atualize CITA, VERSOES e os textos "
                             "de site/data/fontes.json antes de gerar de novo.")


def poligonos(g):
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for x in getattr(g, "geoms", []) for p in poligonos(x)]


def multi(g):
    return MultiPolygon(poligonos(g))


def linhas(g):
    if isinstance(g, LineString):
        return [g] if not g.is_empty else []
    if isinstance(g, MultiLineString):
        return [x for x in g.geoms if not x.is_empty]
    return [p for x in getattr(g, "geoms", []) for p in linhas(x)]


def juntar(fc, filtro=None):
    return multi(unary_union([shapely.make_valid(shape(f["geometry"])) for f in fc["features"]
                              if filtro is None or filtro(f["properties"])]))


def km2(g):
    return round(abs(GEOD.geometry_area_perimeter(g)[0]) / 1e6)


def km(g):
    return GEOD.geometry_length(g) / 1000


# ---------- Margem Equatorial: limite aprovado pela ONU em 2025 ----------
# Pontas do limite (parágrafo 78 do resumo das recomendações): a oeste, o limite segue do ponto 002 na direção do
# ponto 001 da borda externa da margem até cruzar o limite com a França; a leste, segue do ponto 463 na direção do
# ponto 038 da borda externa até encontrar a linha das 200 milhas. Coordenadas da Tabela 3 do Anexo I.
OECM_001 = (-48.2507754, 8.7966534)
OECM_038 = (-34.3926737, -0.7877329)


def equatorial_aprovada(pedido, zee):
    """Corta a área pedida em 2017 pela linha do limite aprovado em 2025 e fica com a parte colada à ZEE."""
    if not PONTOS_EQ.exists():
        return None
    with PONTOS_EQ.open(encoding="utf-8") as f:
        linhas_csv = list(csv.DictReader(f))
    pts = [(float(r["longitude"]), float(r["latitude"])) for r in linhas_csv]
    # confere a cópia: a distância de cada ponto ao anterior tem de bater com a da tabela da ONU
    for a, b, r in zip(pts, pts[1:], linhas_csv[1:]):
        d = GEOD.inv(a[0], a[1], b[0], b[1])[2]
        if r["distancia_ao_anterior_m"] and abs(d - float(r["distancia_ao_anterior_m"])) > 0.5:
            raise SystemExit(f"ponto {r['ponto']} não confere com a distância da tabela da ONU")

    def alem(a, b):          # ponto além de b, na direção a -> b (meio segmento a mais)
        return tuple(np.add(b, np.subtract(b, a) * 0.5))
    limite = LineString([alem(pts[0], OECM_001), *pts, alem(pts[-1], OECM_038)])
    pedacos = poligonos(split(pedido, limite))
    colados = [p for p in pedacos if p.buffer(1e-6).intersection(zee.boundary).length > 0.5]
    if not colados:
        raise RuntimeError("o limite aprovado não cortou a área pedida como esperado")
    return multi(unary_union(colados)), limite


# ---------- principal ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", help="pasta com os arquivos br_<camada>.json já baixados")
    args = ap.parse_args()
    if not args.cache:
        conferir_versoes()
    D = {c: baixar(c, f, args.cache) for c, f in CAMADAS.items()}

    zee_mr, ts_mr, cz_mr, iw_mr = (juntar(D[c]) for c in ("eez", "eez_12nm", "eez_24nm", "eez_internal_waters"))
    rec = juntar(D["ecs"], lambda p: "Recommendation" in p["geoname"])
    pedido = juntar(D["ecs"], lambda p: "Submission" in p["geoname"])
    pedidos = sorted(pedido.geoms, key=lambda p: p.centroid.y)   # o do sul primeiro
    om, eq = multi(pedidos[0]), multi(pedidos[1])
    assert eq.centroid.y > -5 and om.centroid.y < -10, "a ordem das áreas pedidas mudou; conferir"

    eq_fonte, eq_limite_onu = "pedido", None
    r = equatorial_aprovada(eq, zee_mr)
    if r:
        eq, eq_limite_onu = r
        eq_fonte = "onu"

    # 1) quebra-cabeça sem frestas: junta as bordas, remonta as faces e dá a cada face uma única dona
    fontes = {"iw": iw_mr, "ts": ts_mr, "cz": cz_mr, "ze": zee_mr, "sul": rec, "eq": eq, "om": om}
    faces = list(polygonize(unary_union([g.boundary for g in fontes.values()])))
    pts = shapely.points([f.representative_point().coords[0] for f in faces])
    dona = np.array([""] * len(faces), dtype=object)
    for k in reversed(list(fontes)):            # a ordem do dicionário é a prioridade
        shapely.prepare(fontes[k])
        dona[shapely.contains(fontes[k], pts)] = k
    P = {k: multi(shapely.coverage_union_all([faces[i] for i in np.where(dona == k)[0]])) for k in fontes}
    assert shapely.coverage_is_valid(list(P.values()))

    # 2) áreas medidas nos polígonos inteiros, antes de simplificar
    A = {k: km2(g) for k, g in P.items()}
    A["zee"] = A["cz"] + A["ze"]                # ZEE legal: das 12 às 200 milhas
    A["ate200"] = A["ts"] + A["zee"]            # das linhas de base às 200 milhas
    print("áreas (km²):", A)

    # 3) simplificação conjunta + arredondamento; descarta frestas minúsculas (< 0,5 km²)
    chaves = list(P)
    S = dict(zip(chaves, shapely.coverage_simplify([P[k] for k in chaves], TOL)))
    for k in S:
        g = shapely.set_precision(S[k], GRADE)
        S[k] = MultiPolygon([p for p in poligonos(g) if km2(p) >= 0.5])

    def bordas_comuns(a, b):
        return linemerge(linhas(a.boundary.intersection(b.buffer(GRADE / 10))))

    def sem_bordas(a, *outras):
        g = a.boundary
        for o in outras:
            g = g.difference(o.buffer(GRADE / 10))
        return linemerge(linhas(g))

    zee_area = multi(shapely.coverage_union_all([S["cz"], S["ze"]]))
    lim_200 = sem_bordas(S["ze"], S["cz"], S["ts"], S["iw"])      # 200 milhas + limites laterais
    lim_12 = bordas_comuns(S["ts"], S["cz"])
    lim_24 = bordas_comuns(S["cz"], S["ze"])
    bases = linemerge([l for f in D["eez_boundaries"]["features"] if f["properties"]["line_type"] == "Straight baseline"
                       for l in linhas(shapely.set_precision(shape(f["geometry"]), GRADE))])

    def fc(features, meta):
        return {"type": "FeatureCollection", "meta": meta, "features": features}

    def feat(geom, **props):
        return {"type": "Feature", "properties": props, "geometry": mapping(geom)}

    def meta(cit, area_km2, **extra):
        return {"fonte": cit, "licenca": LICENCA, "baixado_em": HOJE, "area_km2": area_km2,
                "aviso": SEM_VALOR_LEGAL, "metodo": "scripts/gerar_limites_maritimos.py", **extra}

    saida = {
        "zee.json": fc([feat(zee_area, parte="area"), feat(lim_200, parte="limite")],
                       meta(CITA["eez"], A["zee"], area_ate_200_milhas_km2=A["ate200"],
                            explica="Faixa das 12 às 200 milhas, medida das linhas de base (Lei 8.617/1993, art. 6º).")),
        "mar_territorial.json": fc([feat(S["ts"], parte="area"), feat(lim_12, parte="limite"), feat(bases, parte="base")],
                                   meta(CITA["eez_12nm"], A["ts"],
                                        explica="12 milhas a partir das linhas de base; as linhas de base retas são as do Decreto 8.400/2015.")),
        "zona_contigua.json": fc([feat(S["cz"], parte="area"), feat(lim_24, parte="limite")],
                                 meta(CITA["eez_24nm"], A["cz"], explica="Faixa das 12 às 24 milhas.")),
    }

    # plataforma continental estendida: uma área por região, com a situação na ONU
    # (situação e áreas aproximadas: Marinha do Brasil, SECIRM/LEPLAC, página atualizada em 26/06/2026)
    REG = [
        ("sul", "Região Sul", "reconhecida", "limite aprovado pela CLPC (ONU) em março de 2019",
         "cerca de 170 mil km²", CITA["ecs"] + " (a partir do resumo das recomendações da CLPC, 2019)",
         "Marine Regions, versão 2 (2024), a partir das recomendações da CLPC de 2019"),
        ("eq", "Margem Equatorial", "reconhecida",
         "limite aprovado pela CLPC (ONU) em 27/02/2025" if eq_fonte == "onu" else
         "limite aprovado pela CLPC (ONU) em 2025; o desenho ainda é o do pedido de 2017, porque a base aberta não traz o contorno aprovado",
         "cerca de 360 mil km²", CLPC_EQ + "; fechamento na linha das 200 milhas do Marine Regions" if eq_fonte == "onu"
         else CITA["ecs"] + " (pedido revisto de 2017)",
         "CLPC (ONU), recomendações de 27/02/2025: 462 pontos do limite" if eq_fonte == "onu"
         else "Marine Regions, versão 2 (2024): contorno do pedido de 2017"),
        ("om", "Margens Oriental e Meridional", "em_analise", "pedido de dezembro de 2018, em análise na CLPC (ONU) desde fevereiro de 2025",
         "cerca de 1,5 milhão de km²", CITA["ecs"] + " (pedido revisto de 2018)",
         "Marine Regions, versão 2 (2024): contorno do pedido de 2018"),
    ]
    areas, limites, rotulos = [], [], []
    for k, nome, status, situacao, marinha, fonte, curta in REG:
        g = S[k]
        props = dict(id=k, nome=nome, status=status, situacao=situacao, area_km2=A[k], area_marinha=marinha,
                     fonte=fonte, fonte_curta=curta)
        areas.append(feat(g, parte="area", **props))
        outras = [S[o] for o in ("ze", "cz", "ts", "iw")]
        limites.append(feat(sem_bordas(g, *outras), parte="limite", id=k, status=status))
        maior = max(poligonos(g), key=lambda p: p.area)
        c = polylabel(maior, tolerance=0.05)
        rotulos.append(feat(Point(round(c.x, 2), round(c.y, 2)), parte="rotulo", id=k, status=status, nome=nome,
                            texto=f"{nome}\n{'reconhecida pela ONU' if status == 'reconhecida' else 'em análise na ONU'}"))
    saida["plataforma_estendida.json"] = fc(areas + limites + rotulos, {
        "fonte": CITA["ecs"], "licenca": LICENCA, "baixado_em": HOJE,
        "area_km2": A["sul"] + A["eq"] + A["om"], "area_reconhecida_km2": A["sul"] + A["eq"], "area_em_analise_km2": A["om"],
        "margem_equatorial": "limite aprovado pela ONU (2025)" if eq_fonte == "onu" else "contorno do pedido de 2017 (Marine Regions)",
        "aviso": SEM_VALOR_LEGAL, "metodo": "scripts/gerar_limites_maritimos.py",
        "situacao_fonte": "Marinha do Brasil, SECIRM/LEPLAC, página atualizada em 26/06/2026"})

    SAIDA.mkdir(parents=True, exist_ok=True)
    for nome, dados in saida.items():
        texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
        (SAIDA / nome).write_text(texto, encoding="utf-8")
        print(f"{nome}: {len(texto) / 1000:.0f} KB")
    print(f"limite das 200 milhas: {km(lim_200):,.0f} km; 12 milhas: {km(lim_12):,.0f} km; 24 milhas: {km(lim_24):,.0f} km")


if __name__ == "__main__":
    main()
