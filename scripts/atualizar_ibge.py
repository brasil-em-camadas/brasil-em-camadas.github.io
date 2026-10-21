"""Atualiza as camadas que vêm das APIs do IBGE (SIDRA e agregados).

Roda sozinho no GitHub Actions (ver .github/workflows/site.yml) e também à mão:
    python scripts/atualizar_ibge.py

Regra de segurança: se a API falhar ou devolver algo estranho (menos de 27 estados),
o arquivo antigo NÃO é apagado. O site continua com o último dado bom e a data dele.
Só usa a biblioteca padrão do Python, sem instalar nada.
"""
import csv
import gzip
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

DADOS = Path(__file__).resolve().parent.parent / "site" / "data"
SIDRA = "https://apisidra.ibge.gov.br/values"

# Código IBGE de cada estado -> sigla
UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
      "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
      "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS",
      "50": "MS", "51": "MT", "52": "GO", "53": "DF"}

# Cada camada: consulta SIDRA + texto que aparece no site.
# Códigos conferidos na API em 2026-10-17. Na tabela 5457, a classificação 782 com código 0 é o "Total" das lavouras.
CAMADAS = [
    {
        "arquivo": "populacao.json",
        "consulta": "/t/4709/n3/all/v/93/p/2022",
        "titulo": "População residente",
        "unidade": "habitantes",
        "fonte": "IBGE, Censo Demográfico 2022 (tabela SIDRA 4709)",
    },
    {
        "arquivo": "agricultura.json",
        "consulta": "/t/5457/n3/all/v/215/p/last%201/c782/0",
        "titulo": "Valor da produção agrícola",
        "unidade": "mil R$",
        "fonte": "IBGE, Produção Agrícola Municipal (tabela SIDRA 5457, total das lavouras)",
    },
]


def baixar(consulta):
    req = urllib.request.Request(SIDRA + consulta + "?formato=json",
                                 headers={"User-Agent": "brasil-em-camadas (dados abertos)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def interpretar(linhas):
    """A SIDRA devolve uma lista: a 1ª linha diz o que cada coluna é, as demais são os dados.
    Procuramos as colunas pelo nome, não pela posição, para não quebrar se a ordem mudar."""
    cab, dados = linhas[0], linhas[1:]
    col_uf = next(k for k, v in cab.items() if v.startswith("Unidade da Federação (Código)"))
    col_ano = next((k for k, v in cab.items() if v in ("Ano (Código)", "Ano")), None)
    valores, ano = {}, None
    for l in dados:
        sigla = UF.get(l.get(col_uf, ""))
        v = l.get("V", "")
        if not sigla:
            continue
        try:
            valores[sigla] = int(float(v))
        except ValueError:
            continue  # "-", "..." e "X" são códigos da SIDRA para dado ausente ou sigiloso
        if col_ano:
            ano = l[col_ano]
    return valores, ano


def atualizar(c):
    destino = DADOS / c["arquivo"]
    try:
        valores, ano = interpretar(baixar(c["consulta"]))
    except Exception as e:  # rede, formato, qualquer coisa: mantém o arquivo antigo
        print(f"[{c['arquivo']}] falhou, mantendo o anterior: {e}")
        return False
    if len(valores) < 27:
        print(f"[{c['arquivo']}] só vieram {len(valores)} estados, mantendo o anterior")
        return False
    novo = {
        "titulo": c["titulo"], "unidade": c["unidade"], "referencia": ano or "",
        "fonte": c["fonte"], "nivel": "api", "atualizado_em": date.today().isoformat(),
        "consulta": SIDRA + c["consulta"], "valores": valores,
    }
    destino.write_text(json.dumps(novo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{c['arquivo']}] ok: {len(valores)} estados, referência {ano}")
    return True


# População de cada município, para a camada "Luzes à noite · População" da página 3D.
# A posição de cada município é a sede (a cidade). As coordenadas ficam em scripts/dados/sedes_municipais.csv
# (IBGE, Localidades do Brasil 2022; gerado por scripts/gerar_sedes_municipais.py); a população vem da API do IBGE.
MUNICIPIOS = {
    "arquivo": "luzes/municipios.json",
    "consulta": "/t/4709/n6/all/v/93/p/2022",
    "fonte": "IBGE, Censo Demográfico 2022 (tabela SIDRA 4709), população de cada município",
    "posicao": "sede de cada município (IBGE, Localidades do Brasil 2022)",
}
SEDES = Path(__file__).resolve().parent / "dados" / "sedes_municipais.csv"


def atualizar_municipios(c=MUNICIPIOS):
    destino = DADOS / c["arquivo"]
    try:
        linhas = baixar(c["consulta"])
        cab = linhas[0]
        col = next(k for k, v in cab.items() if v.startswith("Município (Código)"))
        pop = {l[col]: int(l["V"]) for l in linhas[1:] if l.get("V", "").isdigit()}
    except Exception as e:
        print(f"[{c['arquivo']}] falhou, mantendo o anterior: {e}")
        return False
    sedes = {r["codigo_ibge"]: r for r in csv.DictReader(SEDES.open(encoding="utf-8"))}
    m = [[round(float(sedes[k]["longitude"]), 4), round(float(sedes[k]["latitude"]), 4), v, sedes[k]["nome"], k[:2]]
         for k, v in pop.items() if k in sedes]
    if len(m) < 5500:  # o Brasil tem 5.570 municípios; bem menos que isso = algo errado
        print(f"[{c['arquivo']}] só {len(m)} municípios, mantendo o anterior")
        return False
    m.sort(key=lambda x: x[2])  # os maiores por último: ficam desenhados por cima
    novo = {"titulo": "População por município", "referencia": "2022", "fonte": c["fonte"], "posicao": c["posicao"],
            "nivel": "api", "atualizado_em": date.today().isoformat(), "consulta": SIDRA + c["consulta"],
            "total": sum(x[2] for x in m), "campos": ["lon", "lat", "populacao", "nome", "uf"],
            "municipios": [x[:4] + [UF.get(x[4], "")] for x in m]}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(novo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[{c['arquivo']}] ok: {len(m)} municípios, total {novo['total']}")
    return True


# Pecuária e aquicultura: IBGE, Pesquisa da Pecuária Municipal (PPM). Códigos conferidos na API em 2026-10-21:
# - tabela 3939 = efetivo dos rebanhos (variável 105, em cabeças); classificação 79 = tipo de rebanho;
# - tabela 3940 = aquicultura (variável 215 = valor da produção, em mil R$); classificação 654 = tipo de produto (0 = Total).
# A aquicultura vai em valor porque cada produto tem uma unidade (peixe em kg, alevino em milheiros etc.): não dá para somar quantidades.
REBANHOS = {"2670": "bovino", "32794": "suino", "32796": "galinaceos", "2677": "ovino", "2681": "caprino"}
PECUARIA = {
    "estados": "/t/3939/n3/all/v/105/p/last%201/c79/" + ",".join(REBANHOS),
    "aquicultura": "/t/3940/n3/all/v/215/p/last%201/c654/all",
    "municipios": "/t/3939/n6/all/v/105/p/last%201/c79/2670",
}
AQUI_SOMAS = {"0", "79366"}  # "Total" e "Peixes" (soma de várias espécies) ficam fora da escolha do produto principal
FONTE_PPM = "IBGE, Pesquisa da Pecuária Municipal (tabelas SIDRA 3939 e 3940)"


def coluna(cab, nome):
    return next(k for k, v in cab.items() if v == nome)


def numero(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None  # "-" (zero), "..." e "X" (sigiloso) da SIDRA: sem número


def atualizar_pecuaria():
    """Grava pecuaria/estados.json (pintura e ficha de cada estado) e pecuaria/municipios.json (pontos do mapa).
    Cada arquivo só é trocado se a resposta da API parecer completa."""
    pasta = DADOS / "pecuaria"
    pasta.mkdir(parents=True, exist_ok=True)
    hoje = date.today().isoformat()
    ok_estados = ok_mun = False
    try:
        reb, aq = baixar(PECUARIA["estados"]), baixar(PECUARIA["aquicultura"])
        cab = reb[0]
        c_uf, c_tipo, c_ano = coluna(cab, "Unidade da Federação (Código)"), coluna(cab, "Tipo de rebanho (Código)"), coluna(cab, "Ano")
        val, ano = {}, None
        for l in reb[1:]:
            s, t = UF.get(l[c_uf]), REBANHOS.get(l[c_tipo])
            if s and t:
                val.setdefault(s, {})[t] = numero(l["V"])
                ano = l[c_ano]
        cab = aq[0]
        a_uf, a_cod, a_nome, a_ano = (coluna(cab, "Unidade da Federação (Código)"), coluna(cab, "Tipo de produto da aquicultura (Código)"),
                                      coluna(cab, "Tipo de produto da aquicultura"), coluna(cab, "Ano"))
        ano_aq = None
        for l in aq[1:]:
            s, n = UF.get(l[a_uf]), numero(l["V"])
            if not s or s not in val or n is None:
                continue
            ano_aq = l[a_ano]
            if l[a_cod] == "0":
                val[s]["aquicultura_mil_rs"] = n
            elif l[a_cod] not in AQUI_SOMAS and n > val[s].get("aquicultura_principal_mil_rs", 0):
                val[s]["aquicultura_principal"], val[s]["aquicultura_principal_mil_rs"] = l[a_nome], n
        for v in val.values():
            v["valor"] = v.get("bovino")
        if sum(1 for v in val.values() if v.get("bovino")) < 27:
            raise ValueError(f"só {len(val)} estados com rebanho bovino")
        novo = {"titulo": "Rebanho bovino", "unidade": "cabeças", "referencia": ano or "", "aquicultura_referencia": ano_aq or "",
                "fonte": FONTE_PPM, "nivel": "api", "atualizado_em": hoje,
                "consulta": [SIDRA + PECUARIA["estados"], SIDRA + PECUARIA["aquicultura"]],
                "total_bovino": sum(v["bovino"] for v in val.values()), "valores": val}
        (pasta / "estados.json").write_text(json.dumps(novo, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[pecuaria/estados.json] ok: 27 estados, rebanhos de {ano}, aquicultura de {ano_aq}")
        ok_estados = True
    except Exception as e:
        print(f"[pecuaria/estados.json] falhou, mantendo o anterior: {e}")
    try:
        linhas = baixar(PECUARIA["municipios"])
        cab = linhas[0]
        c_mun, c_ano = coluna(cab, "Município (Código)"), coluna(cab, "Ano")
        bois = {l[c_mun]: numero(l["V"]) for l in linhas[1:]}
        ano = linhas[1][c_ano] if len(linhas) > 1 else ""
        sedes = {r["codigo_ibge"]: r for r in csv.DictReader(SEDES.open(encoding="utf-8"))}
        m = [[round(float(sedes[k]["longitude"]), 4), round(float(sedes[k]["latitude"]), 4), v, sedes[k]["nome"], UF.get(k[:2], "")]
             for k, v in bois.items() if v and k in sedes]
        if len(m) < 5000:  # quase todo município tem algum gado; bem menos que isso = resposta incompleta
            raise ValueError(f"só {len(m)} municípios")
        m.sort(key=lambda x: -x[2])  # os maiores primeiro: os pequenos ficam desenhados por cima e continuam visíveis
        novo = {"meta": {"titulo": "Rebanho bovino por município", "referencia": ano, "fonte": "IBGE, Pesquisa da Pecuária Municipal (tabela SIDRA 3939)",
                         "posicao": MUNICIPIOS["posicao"], "nivel": "api", "atualizado_em": hoje, "consulta": SIDRA + PECUARIA["municipios"],
                         "total": sum(x[2] for x in m), "municipios_com_gado": len(m)},
                "campos": ["lon", "lat", "cabecas", "nome", "uf"], "municipios": m}
        (pasta / "municipios.json").write_text(json.dumps(novo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[pecuaria/municipios.json] ok: {len(m)} municípios, {novo['meta']['total']} cabeças, ano {ano}")
        ok_mun = True
    except Exception as e:
        print(f"[pecuaria/municipios.json] falhou, mantendo o anterior: {e}")
    return [ok_estados, ok_mun]


# Lavouras: IBGE, Produção Agrícola Municipal (PAM), tabela 5457, pela API de agregados (v3), que responde bem mais enxuta
# que a SIDRA quando são milhares de municípios. Valor da produção (variável 215, mil R$) e quantidade produzida (214, em
# toneladas; os produtos marcados com * na tabela, como abacaxi e coco-da-baía, vêm em mil frutos). Café: só o "Total"
# (Arábica e Canephora são partes dele e contariam em dobro). A API às vezes responde compactada (gzip) mesmo sem pedir.
# Por município, a API não aceita vários produtos numa consulta só: vai um produto por vez (83 consultas, ~60 MB).
# A PAM sai uma vez por ano; se o ano não mudou, a parte dos municípios não é baixada de novo.
AGREGADOS = "https://servicodados.ibge.gov.br/api/v3/agregados/5457"
FONTE_PAM = "IBGE, Produção Agrícola Municipal (tabela 5457)"
CAFE_PARTES = {"40140", "40141"}
PINTURA_LAVOURA = {"40124": "soja", "40122": "milho", "40106": "cana", "40139": "cafe"}
GRUPO_LAVOURA = {"40124": "soja", "40122": "milho", "40106": "cana", "40139": "cafe", "40119": "mandioca",
                 "40136": "banana", "40112": "feijao", "40102": "arroz"}
SIGLA_COD = {v: k for k, v in UF.items()}


def pedir_json(url, tentativas=4):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "brasil-em-camadas (dados abertos)", "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=180) as r:
                b = r.read()
            return json.loads((gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b).decode("utf-8"))
        except Exception:
            if i == tentativas - 1:
                raise
            time.sleep(5 * (i + 1))


def agregado(variavel, localidades, categoria="all"):
    """[(código do produto, nome do produto, código do lugar, ano, valor em texto)] do último ano da tabela 5457."""
    d = pedir_json(f"{AGREGADOS}/periodos/-1/variaveis/{variavel}?localidades={localidades}&classificacao=782%5B{categoria}%5D")
    saida = []
    for r in d[0]["resultados"]:
        (cid, nome), = r["classificacoes"][0]["categoria"].items()
        for s in r["series"]:
            (ano, v), = s["serie"].items()
            saida.append((cid, nome, s["localidade"]["id"], ano, v))
    return saida


def nome_curto(n):
    """'Soja (em grão)' -> 'Soja'; 'Café (em grão) Total' -> 'Café'; 'Abacaxi*' -> 'Abacaxi'."""
    n = n.replace("*", "").replace(" Total", "").strip()
    return re.sub(r"\s*\([^)]*\)$", "", n).strip()


def atualizar_lavouras():
    """lavouras/estados.json (pinturas por lavoura e ficha) e lavouras/municipios.json (principal lavoura de cada município)."""
    pasta = DADOS / "lavouras"
    pasta.mkdir(parents=True, exist_ok=True)
    hoje = date.today().isoformat()
    ok_e = ok_m = False
    ano, produtos = None, {}
    try:
        val, qtd = agregado(215, "N3%5Ball%5D"), agregado(214, "N3%5Ball%5D")
        ano = max(a for *_, a, _ in val)
        q = {(c, l): numero(v) for c, _, l, a, v in qtd if a == ano}
        por_uf = {}
        for c, n, l, a, v in val:
            s, x = UF.get(l), numero(v)
            if a != ano or not s or c in CAFE_PARTES:
                continue
            produtos[c] = n
            e = por_uf.setdefault(s, {"total": None, "itens": []})
            if c == "0":
                e["total"] = x
            elif x:
                e["itens"].append((c, x))
        valores = {}
        for s, e in por_uf.items():
            cod = SIGLA_COD[s]
            item = {"valor": e["total"]}
            for c, chave in PINTURA_LAVOURA.items():
                item[chave] = q.get((c, cod)) or None   # zero ou sem dado: sem produção (cinza no mapa)
            item["principais"] = [[nome_curto(produtos[c]), x, q.get((c, cod)), "mil frutos" if produtos[c].endswith("*") else "t"]
                                  for c, x in sorted(e["itens"], key=lambda t: -t[1])[:5]]
            valores[s] = item
        if sum(1 for v in valores.values() if v["valor"]) < 27:
            raise ValueError(f"só {len(valores)} estados com valor da produção")
        novo = {"titulo": "Lavouras", "unidade": "toneladas", "referencia": ano, "fonte": FONTE_PAM, "nivel": "api", "atualizado_em": hoje,
                "consulta": [f"{AGREGADOS}/periodos/-1/variaveis/215?localidades=N3[all]&classificacao=782[all]",
                             f"{AGREGADOS}/periodos/-1/variaveis/214?localidades=N3[all]&classificacao=782[all]"],
                "campos": {"valor": "valor da produção das lavouras (mil R$)", "soja": "toneladas", "milho": "toneladas", "cana": "toneladas",
                           "cafe": "toneladas (café em grão, arábica e canephora)",
                           "principais": "[lavoura, valor (mil R$), quantidade, unidade] das 5 de maior valor"},
                "valores": valores}
        (pasta / "estados.json").write_text(json.dumps(novo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[lavouras/estados.json] ok: {len(valores)} estados, {ano}")
        ok_e = True
    except Exception as e:
        print(f"[lavouras/estados.json] falhou, mantendo o anterior: {e}")
    try:
        destino = pasta / "municipios.json"
        antigo = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else None
        if not ano or not produtos:
            raise ValueError("sem a lista de produtos do ano (a parte dos estados falhou)")
        if antigo and antigo["meta"].get("referencia") == ano and "--forcar" not in sys.argv:
            print(f"[lavouras/municipios.json] já está com {ano}; não baixei de novo")
            return [ok_e, True]
        cats = ["0"] + [c for c in produtos if c != "0"]
        with ThreadPoolExecutor(4) as ex:
            partes = list(ex.map(lambda c: agregado(215, "N6%5Ball%5D", c), cats))
        total, por_mun = {}, {}
        for c, linhas in zip(cats, partes):
            for _, _, l, a, v in linhas:
                x = numero(v)
                if a != ano or not x:
                    continue
                if c == "0":
                    total[l] = x
                else:
                    por_mun.setdefault(l, {})[c] = x
        sedes = {r["codigo_ibge"]: r for r in csv.DictReader(SEDES.open(encoding="utf-8"))}
        m = []
        for k, d in por_mun.items():
            if k not in sedes:
                continue
            c = max(d, key=d.get)
            m.append([round(float(sedes[k]["longitude"]), 4), round(float(sedes[k]["latitude"]), 4), total.get(k) or sum(d.values()),
                      GRUPO_LAVOURA.get(c, "outras"), nome_curto(produtos[c]), d[c], sedes[k]["nome"], UF.get(k[:2], "")])
        if len(m) < 5000:
            raise ValueError(f"só {len(m)} municípios com lavoura")
        m.sort(key=lambda x: -x[2])   # os maiores primeiro: os pequenos ficam desenhados por cima
        grupos = {}
        for x in m:
            grupos[x[3]] = grupos.get(x[3], 0) + 1
        novo = {"meta": {"titulo": "Principal lavoura de cada município", "referencia": ano, "fonte": FONTE_PAM + ", valor da produção de cada lavoura",
                         "posicao": MUNICIPIOS["posicao"], "nivel": "api", "atualizado_em": hoje,
                         "consulta": f"{AGREGADOS}/periodos/-1/variaveis/215?localidades=N6[all]&classificacao=782[<produto>]",
                         "regra": "a lavoura de maior valor da produção no município; o tamanho do ponto mostra o valor de todas as lavouras",
                         "municipios": len(m), "por_grupo": grupos},
                "campos": ["lon", "lat", "valor_total_mil_rs", "grupo", "principal", "principal_mil_rs", "nome", "uf"], "municipios": m}
        destino.write_text(json.dumps(novo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[lavouras/municipios.json] ok: {len(m)} municípios, {ano}; {grupos}")
        ok_m = True
    except Exception as e:
        print(f"[lavouras/municipios.json] falhou, mantendo o anterior: {e}")
    return [ok_e, ok_m]


if __name__ == "__main__":
    nomes = [c["arquivo"] for c in CAMADAS] + [MUNICIPIOS["arquivo"], "pecuaria/estados.json", "pecuaria/municipios.json",
                                               "lavouras/estados.json", "lavouras/municipios.json"]
    ok = [atualizar(c) for c in CAMADAS] + [atualizar_municipios()] + atualizar_pecuaria() + atualizar_lavouras()
    # registro da execução (como o petroleo/robo.json): dá para conferir cada passo sem abrir o log do GitHub
    from datetime import datetime, timezone
    (DADOS / "robo_ibge.json").write_text(json.dumps({
        "rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "passos": {n: ("ok" if o else "falhou (ficou o arquivo anterior)") for n, o in zip(nomes, ok)}}, ensure_ascii=False), encoding="utf-8")
    # Só falha o robô se NADA atualizou, para alguém ser avisado por e-mail pelo GitHub.
    sys.exit(0 if any(ok) else 1)
