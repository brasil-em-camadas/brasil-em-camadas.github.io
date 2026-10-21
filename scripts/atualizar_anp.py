"""Atualiza as camadas de petróleo e gás com dados oficiais da ANP.

Roda sozinho no GitHub Actions (ver .github/workflows/site.yml) e também à mão:
    python scripts/atualizar_anp.py

De onde vem cada coisa:
  - posição dos poços, polígono do pré-sal, campos e unidades de produção: servidor de mapas da ANP
    (GeoServer do GeoMapsANP, serviço WFS);
  - produção de cada poço: dados abertos da ANP, página "Fase de Desenvolvimento e Produção"
    (mar: um arquivo por ano, mês a mês; terra: um arquivo por trimestre).

Período: o último mês que já tem dados de terra E de mar publicados (a ANP publica o mar antes).
O nome do poço liga a produção à posição. A soma nacional foi conferida com o Boletim Mensal da ANP
(junho de 2026: 5,839 contra 5,842 milhões de boe/dia).

Óleo equivalente (boe): convenção da ANP, 1.000 m³ de gás = 1 m³ de petróleo = 6,2898 barris.

Regra de segurança (igual ao robô do IBGE): se algo falhar ou vier estranho, o arquivo antigo NÃO é
apagado. O site continua com o último dado bom e a data dele. Só usa a biblioteca padrão do Python.
"""
import calendar
import csv
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "site" / "data"
SAIDA = DADOS / "petroleo"
WFS = "https://geomaps.anp.gov.br/geoserver/wfs"
PAGINA = ("https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/fase-de-desenvolvimento-e-producao")
BBL = 6.2898          # barris por m³
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36 "
      "brasil-em-camadas (dados abertos)")
HOJE = date.today().isoformat()
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
ETAPAS = {"Produção", "Desenvolvimento", "Fase de Reabilitação"}   # campos "Em Devolução" ficam de fora


# ---------- rede ----------
def baixar(url, tentativas=5):
    """O www.gov.br às vezes devolve resposta vazia; tentar de novo resolve."""
    erro = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=600) as r:
                dados = r.read()
            if dados:
                return dados
            erro = "resposta vazia"
        except Exception as e:
            erro = e
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"não foi possível baixar {url}: {erro}")


def wfs(camada, propriedades=None):
    q = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": camada,
         "outputFormat": "application/json"}
    if propriedades:
        q["propertyName"] = ",".join(propriedades)
    dados = json.loads(baixar(WFS + "?" + urllib.parse.urlencode(q)).decode("utf-8"))
    print(f"  {camada}: {len(dados['features'])} feições")
    return dados["features"]


def ler_csv(url):
    texto = baixar(url).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texto)))


def num(x):
    x = (x or "").strip()
    return float(x.replace(".", "").replace(",", ".")) if x else 0.0


# ---------- arquivos de produção mais novos ----------
def arquivos_de_producao():
    """Lê a página da ANP e acha o arquivo anual do mar e o trimestral da terra mais recentes."""
    html = baixar(PAGINA).decode("utf-8", "replace")
    links = set(re.findall(r'href="([^"]+\.csv)"', html))
    mar = {int(m.group(1)): u for u in links if (m := re.search(r"/pm/producao-mar-(\d{4})\.csv$", u))}
    terra = {(int(m.group(1)), int(m.group(2))): u for u in links
             if (m := re.search(r"producao_por_poco_terra_(\d{4})_(\d)_trim\.csv$", u))}
    if not mar or not terra:
        raise RuntimeError("não achei os arquivos de produção na página da ANP (o endereço ou o nome mudou?)")
    return mar, terra


def escolher_mes(mar, terra):
    """Último mês presente nos dois: terra (trimestral, sai depois) e mar (anual, mês a mês)."""
    for (ano, tri) in sorted(terra, reverse=True)[:3]:
        linhas_t = ler_csv(terra[(ano, tri)])
        meses_t = {r["[Mês/Ano]"] for r in linhas_t}
        if ano not in mar:
            continue
        linhas_m = ler_csv(mar[ano])
        comuns = meses_t & {r["[Mês/Ano]"] for r in linhas_m}
        if comuns:
            mes = max(comuns, key=lambda s: (int(s[3:]), int(s[:2])))
            fontes = {"mar": mar[ano], "terra": terra[(ano, tri)]}
            return mes, [r for r in linhas_m + linhas_t if r["[Mês/Ano]"] == mes], fontes
    raise RuntimeError("não há mês com dados de terra e de mar ao mesmo tempo")


# ---------- geometria (sem bibliotecas externas) ----------
def simplificar(anel, tol):
    """Douglas-Peucker num anel fechado; tol em graus."""
    if len(anel) < 5:
        return anel
    def dist(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5
    manter = [False] * len(anel)
    manter[0] = manter[-1] = True
    pilha = [(0, len(anel) - 1)]
    while pilha:
        i, j = pilha.pop()
        maior, k = 0, None
        for m in range(i + 1, j):
            d = dist(anel[m], anel[i], anel[j])
            if d > maior:
                maior, k = d, m
        if k is not None and maior > tol:
            manter[k] = True
            pilha += [(i, k), (k, j)]
    novo = [p for p, ok in zip(anel, manter) if ok]
    return novo if len(novo) >= 4 else anel


def geom_leve(g, tol=0.001):
    r = lambda a: [[round(x, 4), round(y, 4)] for x, y in simplificar([tuple(p[:2]) for p in a], tol)]
    if g["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [r(a) for a in g["coordinates"]]}
    if g["type"] == "MultiPolygon":
        return {"type": "MultiPolygon", "coordinates": [[r(a) for a in p] for p in g["coordinates"]]}
    return g


def gravar(nome, dados):
    SAIDA.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    (SAIDA / nome).write_text(texto, encoding="utf-8")
    print(f"[petroleo/{nome}] ok: {len(texto) / 1000:.0f} KB")


def mes_extenso(mes):
    return f"{MESES[int(mes[:2]) - 1]} de {mes[3:]}"


# ---------- camadas ----------
def producao():
    """Poços em produção (pontos) e a soma por estado (para pintar os estados)."""
    mar, terra = arquivos_de_producao()
    mes, linhas, fontes = escolher_mes(mar, terra)
    dias = calendar.monthrange(int(mes[3:]), int(mes[:2]))[1]
    pocos = {f["properties"]["name"]: f for f in
             wfs("sisroc:well_view_geoanp", ["name", "bacia_nome", "nome_ambiente", "SHAPE"]) if f.get("geometry")}
    sigla = {f["properties"]["name"]: f["properties"]["sigla"] for f in
             json.loads((DADOS / "geo" / "estados.json").read_text(encoding="utf-8"))["features"]}

    soma = {}
    for r in linhas:
        nome = r["[Poço]"].strip()
        oleo = num(r["[Produção de Óleo (m³)]"]) + num(r["[Produção de Condensado (m³)]"])
        gas = num(r["[Produção de Gás Associado (Mm³)]"]) + num(r["[Produção de Gás Não Associado (Mm³)]"])
        if oleo + gas <= 0:
            continue
        s = soma.setdefault(nome, {"oleo": 0.0, "gas": 0.0, "campo": r["[Campo]"].strip(),
                                   "uf": sigla.get(r["[Estado]"].strip(), ""), "amb": r["[Ambiente]"].strip()})
        s["oleo"] += oleo
        s["gas"] += gas

    pontos, sem_posicao, por_uf, sem_uf = [], 0.0, {}, 0.0
    for nome, s in soma.items():
        bbl = s["oleo"] * BBL / dias                      # barris de petróleo por dia
        gas = s["gas"] / dias                             # mil m³ de gás por dia
        boe = (s["oleo"] + s["gas"]) * BBL / dias         # barris de óleo equivalente por dia
        u = s["uf"]
        if u:
            t = por_uf.setdefault(u, [0.0, 0.0, 0.0, 0])
            t[0] += boe; t[1] += bbl; t[2] += gas; t[3] += 1
        else:
            sem_uf += boe
        f = pocos.get(nome)
        if not f:
            sem_posicao += boe
            continue
        x, y = f["geometry"]["coordinates"][:2]
        pontos.append([round(x, 4), round(y, 4), round(boe, 1), round(bbl, 1), round(gas, 2), nome, s["campo"], u,
                       "M" if s["amb"].upper().startswith("MAR") else "T"])

    total = sum(t[0] for t in por_uf.values()) + sem_uf
    cobre = 1 - sem_posicao / total if total else 0
    if total < 1e6 or len(pontos) < 1000 or cobre < 0.95:   # o Brasil produz vários milhões de boe/dia
        raise RuntimeError(f"resultado estranho: total {total:,.0f} boe/d, {len(pontos)} poços, posição para {cobre:.1%}")
    pontos.sort(key=lambda p: p[2])   # os maiores por último: ficam desenhados por cima
    ref = mes_extenso(mes)
    fonte = "ANP: produção por poço (dados abertos) e posição dos poços (servidor de mapas GeoMapsANP)"
    gravar("pocos.json", {
        "meta": {"titulo": "Poços em produção", "referencia": ref, "mes": mes, "fonte": fonte, "nivel": "api",
                 "atualizado_em": HOJE, "arquivos": fontes, "servico": WFS + " (sisroc:well_view_geoanp)",
                 "total_boe_d": round(total), "pocos": len(pontos),
                 "producao_sem_posicao_boe_d": round(sem_posicao), "producao_sem_estado_boe_d": round(sem_uf),
                 "conversao": "boe = barril de óleo equivalente; 1.000 m³ de gás = 1 m³ de petróleo = 6,2898 barris (convenção da ANP)"},
        "campos": ["lon", "lat", "boe_dia", "petroleo_bbl_dia", "gas_mil_m3_dia", "poco", "campo", "uf", "ambiente"],
        "pocos": pontos})
    gravar("producao_estados.json", {
        "titulo": "Produção de petróleo e gás", "unidade": "boe/dia", "referencia": ref, "nivel": "api",
        "fonte": "ANP, produção por poço (dados abertos); no mar, a ANP atribui a produção ao estado em frente ao campo",
        "atualizado_em": HOJE, "arquivos": fontes,
        "valores": {u: {"valor": round(t[0]), "petroleo_bbl_dia": round(t[1]), "gas_mil_m3_dia": round(t[2]),
                        "pocos": t[3]} for u, t in sorted(por_uf.items())},
        "total_boe_dia": round(total)})
    print(f"  produção de {ref}: {total / 1e6:.3f} milhões de boe/dia em {len(pontos)} poços; posição para {cobre:.2%}")


def presal():
    f = wfs("sisroc:presal_shp_geoanp")
    if len(f) != 1:
        raise RuntimeError(f"esperava 1 polígono do pré-sal, vieram {len(f)}")
    g = f[0]["geometry"]
    anel = g["coordinates"][0][0] if g["type"] == "MultiPolygon" else g["coordinates"][0]
    xs, ys = [p[0] for p in anel], [p[1] for p in anel]
    gravar("presal.json", {
        "type": "FeatureCollection",
        "meta": {"fonte": "ANP, servidor de mapas GeoMapsANP (sisroc:presal_shp_geoanp)", "nivel": "api",
                 "atualizado_em": HOJE,
                 "lei": "Lei 12.351/2010, art. 2º, IV, e Anexo: os 11 vértices coincidem com o desenho da ANP (conferido em 21/10/2026)"},
        "features": [{"type": "Feature", "properties": {"parte": "area"}, "geometry": geom_leve(g, 0)},
                     {"type": "Feature", "properties": {"parte": "rotulo", "texto": "PRÉ-SAL"},
                      "geometry": {"type": "Point", "coordinates": [round(sum(xs) / len(xs), 2), round(sum(ys) / len(ys), 2)]}}]})


def campos():
    fs = [f for f in wfs("sisroc:campos_gishub_db") if (f["properties"].get("etapa") or "").strip() in ETAPAS]
    if len(fs) < 200:
        raise RuntimeError(f"só {len(fs)} campos")
    sai = []
    for f in fs:
        p = f["properties"]
        sai.append({"type": "Feature", "geometry": geom_leve(f["geometry"]),
                    "properties": {"nome": (p.get("name") or "").strip(), "etapa": p["etapa"].strip(),
                                   "operador": (p.get("operador") or "").strip(), "bacia": (p.get("nome_bacia") or "").strip(),
                                   "fluido": (p.get("fluido_pri") or "").strip().capitalize(),
                                   "inicio": (p.get("dat_inicio") or "").strip()}})
    gravar("campos.json", {"type": "FeatureCollection",
                           "meta": {"fonte": "ANP, servidor de mapas GeoMapsANP (sisroc:campos_gishub_db)", "nivel": "api",
                                    "atualizado_em": HOJE, "etapas": sorted(ETAPAS),
                                    "nota": "campos em devolução ficam de fora"},
                           "features": sai})


def plataformas():
    fs = wfs("geoanp:unidade_de_producao")
    if len(fs) < 100:
        raise RuntimeError(f"só {len(fs)} unidades de produção")
    hoje = date.today()
    sai = []
    for f in fs:
        p = f["properties"]
        # "CAMPO(dd/mm/aaaa), OUTRO(dd/mm/aaaa)": desde quando a unidade atende cada campo
        atende = [(c.strip(), d) for c, d in re.findall(r"([^,(]+)\((\d{2}/\d{2}/\d{4})\)", p.get("DESC_ATENDIMENTOS") or "")]
        datas = [date(int(d[6:]), int(d[3:5]), int(d[:2])) for _, d in atende]
        prevista = bool(datas) and min(datas) > hoje
        cap = p.get("QTD_PROCESSAMENTO_PETROLEO") or 0
        sai.append({"type": "Feature", "geometry": f["geometry"],
                    "properties": {"nome": (p.get("NOM_INSTALACAO") or "").strip(), "tipo": (p.get("DESC_TIPO_UEP") or "").strip(),
                                   "operador": (p.get("NOM_PROPRIETARIO") or "").strip(),
                                   "lamina_m": int(float(p["MED_DISTANCIA_LAMINA"])) if str(p.get("MED_DISTANCIA_LAMINA") or "").strip().replace(".", "").isdigit() else None,
                                   "capacidade_bbl_dia": cap if cap > 0 else None,
                                   "atende": ", ".join(f"{c.title()} ({d})" for c, d in atende), "prevista": prevista}})
    gravar("plataformas.json", {"type": "FeatureCollection",
                                "meta": {"fonte": "ANP, servidor de mapas GeoMapsANP (geoanp:unidade_de_producao)", "nivel": "api",
                                         "atualizado_em": HOJE,
                                         "nota": "prevista = todas as datas de atendimento ainda no futuro; capacidade de processamento de petróleo em barris por dia, como cadastrada na ANP"},
                                "features": sai})


if __name__ == "__main__":
    from datetime import datetime, timezone
    ok, relato = [], {}
    for passo in (producao, presal, campos, plataformas):
        print(f"[{passo.__name__}]")
        try:
            passo()
            ok.append(True)
            relato[passo.__name__] = "ok"
        except Exception as e:   # rede, formato, qualquer coisa: mantém o arquivo antigo
            print(f"[{passo.__name__}] falhou, mantendo o anterior: {e}")
            ok.append(False)
            relato[passo.__name__] = f"falhou: {str(e)[:300]}"
    # registro da última execução (mostra se o robô conseguiu falar com a ANP, mesmo quando o dado não mudou)
    gravar("robo.json", {"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "passos": relato})
    # Só falha se NADA atualizou. No site.yml este passo não derruba a publicação dos outros dados.
    sys.exit(0 if any(ok) else 1)
