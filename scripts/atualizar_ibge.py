"""Atualiza as camadas que vêm da API SIDRA do IBGE.

Roda sozinho no GitHub Actions (ver .github/workflows/site.yml) e também à mão:
    python scripts/atualizar_ibge.py

Regra de segurança: se a API falhar ou devolver algo estranho (menos de 27 estados),
o arquivo antigo NÃO é apagado. O site continua com o último dado bom e a data dele.
Só usa a biblioteca padrão do Python, sem instalar nada.
"""
import csv
import json
import sys
import urllib.request
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
# (base aberta "municipios-brasileiros", licença MIT); a população vem da API do IBGE.
MUNICIPIOS = {
    "arquivo": "luzes/municipios.json",
    "consulta": "/t/4709/n6/all/v/93/p/2022",
    "fonte": "IBGE, Censo Demográfico 2022 (tabela SIDRA 4709), população de cada município",
    "posicao": "sede de cada município (base aberta municipios-brasileiros, derivada de dados do IBGE)",
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


if __name__ == "__main__":
    ok = [atualizar(c) for c in CAMADAS] + [atualizar_municipios()] + atualizar_pecuaria()
    # Só falha o robô se NADA atualizou, para alguém ser avisado por e-mail pelo GitHub.
    sys.exit(0 if any(ok) else 1)
