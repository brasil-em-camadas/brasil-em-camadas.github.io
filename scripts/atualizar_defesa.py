"""Atualiza a indústria de defesa do mapa: empresas credenciadas pelo Ministério da Defesa (ED e EED).

Fonte: Ministério da Defesa, "Relação geral de empresas credenciadas como ED & EED" (planilha .xlsx), na página
https://www.gov.br/defesa/pt-br/assuntos/industria-de-defesa/comissao-mista-da-industria-de-defesa-cmid-1/empresas-de-defesa-ed-e-empresas-estrategicas-de-defesa-eed
A planilha junta as portarias de credenciamento publicadas no Diário Oficial da União e é revista depois das reuniões
da Comissão Mista da Indústria de Defesa (CMID). O nome do arquivo muda a cada revisão
(ex.: lista-de-empresas-credenciadas-03-09-26-rev.xlsx), por isso o robô lê a página e segue o link da planilha.

- ED, Empresa de Defesa: empresa que fabrica produtos de defesa ou faz parte da cadeia que os produz, credenciada pelo
  Ministério da Defesa (Decreto 7.970/2013, art. 7º).
- EED, Empresa Estratégica de Defesa: ED credenciada por ato do ministro, com sede, administração e produção no Brasil,
  conhecimento tecnológico próprio (ou em parceria com instituição de pesquisa) e controle nacional; pode usar o regime
  tributário especial da indústria de defesa, o RETID (Lei 12.598/2012, arts. 2º e 7º a 11).

Município: a planilha traz cidade e UF. Quando a cidade não é o nome de um município (bairro, distrito, nome do estado,
erro de digitação), vale a correção de scripts/dados/defesa_municipios.csv, feita à mão e com o motivo de cada uma.
Correção com CNPJ vale só para aquela empresa; sem CNPJ, vale para a cidade e UF escritas daquele jeito.
A empresa sem correção entra na contagem do estado, fica sem ponto no mapa e aparece no robo.json para alguém corrigir.

Roda sozinho no GitHub Actions (site.yml), junto com os outros robôs, e também à mão:
    python scripts/atualizar_defesa.py
    python scripts/atualizar_defesa.py --arquivo lista.xlsx   (planilha já baixada)
Só usa a biblioteca padrão. Se o Ministério falhar ou mandar algo estranho, os arquivos antigos ficam.
Saídas em site/data/defesa/:
  estados.json   pintura e ficha: empresas credenciadas por estado (EED e ED) e os municípios com mais empresas
  empresas.json  municípios com empresas credenciadas, no ponto da sede, com a lista das empresas
  robo.json      resultado de cada passo e as empresas que ficaram sem município
"""
import argparse
import csv
import io
import json
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "defesa"
SEDES = RAIZ / "scripts" / "dados" / "sedes_municipais.csv"
CORRECOES = RAIZ / "scripts" / "dados" / "defesa_municipios.csv"
PAGINA = ("https://www.gov.br/defesa/pt-br/assuntos/industria-de-defesa/comissao-mista-da-industria-de-defesa-cmid-1/"
          "empresas-de-defesa-ed-e-empresas-estrategicas-de-defesa-eed")
FONTE = "Ministério da Defesa, relação geral das empresas credenciadas como ED e EED"
UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
      "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
      "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS",
      "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
AGENTE = {"User-Agent": "Mozilla/5.0 (compatible; brasil-em-camadas; dados abertos)"}


def baixar(url, tentativas=5):
    """O www.gov.br às vezes devolve resposta vazia; tentar de novo resolve."""
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=120) as r:
                dados = r.read()
            if dados:
                return dados
        except Exception:
            if i == tentativas - 1:
                raise
        time.sleep(5 * (i + 1))
    raise ValueError(f"resposta vazia de {url}")


def norm(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def limpo(t):
    return re.sub(r"\s+", " ", str(t or "").replace("\xa0", " ")).strip()


def achar_planilha(pagina):
    """Link da planilha na página do Ministério (o nome do arquivo muda a cada revisão)."""
    links = [unescape(h) for h in re.findall(r'href="([^"]+)"', pagina)]
    bons = [h for h in links if "lista-de-empresas-credenciadas" in h.lower() and ".xls" in h.lower()]
    if not bons:
        bons = [h for h in links if "empresas-de-defesa" in h.lower() and h.lower().split("?")[0].endswith((".xlsx", ".xls"))]
    if not bons:
        raise ValueError("a página não tem mais o link da planilha")
    return urljoin(PAGINA + "/", bons[0])


def ler_xlsx(dados):
    """Primeira aba de uma planilha .xlsx, como {número da linha: {coluna: valor}} (só biblioteca padrão)."""
    z = zipfile.ZipFile(io.BytesIO(dados))
    textos = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(M + "si"):
            textos.append("".join(t.text or "" for t in si.iter(M + "t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rid = wb.find(f"{M}sheets/{M}sheet").get(R_ID)
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    alvo = next(r.get("Target") for r in rels if r.get("Id") == rid)
    alvo = alvo.lstrip("/")
    caminho = alvo if alvo.startswith("xl/") else "xl/" + alvo
    linhas = {}
    for row in ET.fromstring(z.read(caminho)).iter(M + "row"):
        cel = {}
        for c in row.iter(M + "c"):
            letras = re.match(r"[A-Z]+", c.get("r")).group(0)
            col = 0
            for ch in letras:
                col = col * 26 + ord(ch) - 64
            t, v = c.get("t"), c.find(M + "v")
            if t == "s":
                val = textos[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(M + "t"))
            elif v is None or v.text is None:
                val = None
            elif t in ("str", "e"):
                val = v.text
            elif t == "b":
                val = v.text == "1"
            else:
                n = float(v.text)
                val = int(n) if n.is_integer() else n
            if val not in (None, ""):
                cel[col] = val
        if cel:
            linhas[int(row.get("r"))] = cel
    return linhas


def data_excel(v):
    if isinstance(v, (int, float)) and 20000 < v < 80000:
        return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", limpo(v))
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None


def empresas_da_planilha(linhas):
    """Empresas, totais conferidos e a data da revisão ("Atualizada em 03/09/2026 - 49ª Reunião da CMID")."""
    COLS = {"empresas": "nome", "empresa": "nome", "cidade": "cidade", "uf": "uf", "cnpj": "cnpj", "classificacao": "classe"}
    cab, col = None, {}
    for n in sorted(linhas):
        txt = {c: norm(v) for c, v in linhas[n].items() if isinstance(v, str)}
        if {"empresas", "uf", "cnpj"} <= set(txt.values()) or {"empresa", "uf", "cnpj"} <= set(txt.values()):
            cab = n
            for c, t in txt.items():
                if t in COLS:
                    col[COLS[t]] = c
                elif "portaria" in t:
                    col["portaria"] = c
                elif t.startswith("data"):
                    col["data"] = c
                elif t in ("n", "no", "qtd"):
                    col["num"] = c
            break
    faltam = {"nome", "cidade", "uf", "cnpj", "classe"} - set(col)
    if cab is None or faltam:
        raise ValueError(f"cabeçalho da planilha mudou (faltam {sorted(faltam) or 'todas'})")
    empresas, totais, revisao = [], {}, None
    for n in sorted(linhas):
        cel = linhas[n]
        for v in cel.values():
            if isinstance(v, str) and (m := re.search(r"Atualizada em (\d{1,2}/\d{1,2}/\d{4})(.*)", v)):
                revisao = (data_excel(m.group(1)), limpo(m.group(2)).lstrip("-– ").strip())
        if n <= cab:
            continue
        primeiro = limpo(cel.get(min(cel)))
        if primeiro.upper().startswith("TOTAL"):
            num = [v for v in cel.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
            rot = norm(primeiro)
            chave = "total" if "ed eed" in rot else "eed" if "estrategicas" in rot else "ed"
            if num:
                totais[chave] = int(num[-1])
            continue
        nome, classe = limpo(cel.get(col["nome"])), limpo(cel.get(col["classe"])).upper()
        if not nome or classe not in ("EED", "ED"):
            continue
        empresas.append({"nome": nome, "classe": classe, "cidade": limpo(cel.get(col["cidade"])),
                         "uf": limpo(cel.get(col["uf"])).upper(), "cnpj": re.sub(r"\D", "", str(cel.get(col["cnpj"], ""))),
                         "portaria": limpo(cel.get(col.get("portaria"))), "data": data_excel(cel.get(col.get("data")))})
    if len(empresas) < 100:
        raise ValueError(f"só {len(empresas)} empresas na planilha")
    conta = {"ed": sum(e["classe"] == "ED" for e in empresas), "eed": sum(e["classe"] == "EED" for e in empresas)}
    conta["total"] = len(empresas)
    for k, v in totais.items():
        if v != conta[k]:
            raise ValueError(f"a planilha diz {v} no total {k.upper()}, mas tem {conta[k]} linhas")
    return empresas, conta, revisao


def municipios(empresas):
    """Liga cada empresa ao código do município no IBGE (correção à mão > nome e UF da planilha > correção pela cidade)."""
    sedes = {r["codigo_ibge"]: r for r in csv.DictReader(SEDES.open(encoding="utf-8"))}
    por_nome = {(norm(r["nome"]), r["uf"]): k for k, r in sedes.items()}
    por_cnpj, por_cidade = {}, {}
    for r in csv.DictReader(CORRECOES.open(encoding="utf-8")):
        if r["codigo_ibge"] not in sedes:
            raise ValueError(f"código {r['codigo_ibge']} da correção não existe")
        if r["cnpj"].strip():
            por_cnpj[re.sub(r"\D", "", r["cnpj"])] = (r["codigo_ibge"], r["motivo"])
        else:
            por_cidade[(norm(r["cidade"]), r["uf"].strip().upper())] = (r["codigo_ibge"], r["motivo"])
    for e in empresas:
        chave = (norm(e["cidade"]), e["uf"])
        cod, motivo = por_cnpj.get(e["cnpj"]) or ((por_nome[chave], None) if chave in por_nome else por_cidade.get(chave, (None, None)))
        e["codigo"], e["motivo"] = cod, motivo
        if cod:
            e["uf"] = UF[cod[:2]]
    return sedes


def gravar(nome, dados):
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / nome).write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def principal(arquivo):
    passos = {}
    if arquivo:
        url, dados = "arquivo local", Path(arquivo).read_bytes()
    else:
        url = achar_planilha(baixar(PAGINA).decode("utf-8", "replace"))
        passos["pagina"] = "ok"
        dados = baixar(url)
    empresas, conta, revisao = empresas_da_planilha(ler_xlsx(dados))
    passos["planilha"] = "ok"
    sedes = municipios(empresas)
    data_lista, reuniao = revisao or (None, "")
    referencia = f"lista de {'/'.join(reversed(data_lista.split('-')))}" if data_lista else "lista sem data"
    if reuniao:
        referencia += f" ({re.sub(r'Reuni', 'reuni', reuniao)})"
    hoje = date.today().isoformat()
    # municípios com empresas, no ponto da sede; os de mais empresas primeiro (ficam desenhados por baixo)
    grupos = {}
    for e in empresas:
        if e["codigo"]:
            grupos.setdefault(e["codigo"], []).append(e)
    lista = []
    for cod, es in grupos.items():
        s = sedes[cod]
        es.sort(key=lambda e: (e["classe"] != "EED", e["nome"]))
        lista.append([round(float(s["longitude"]), 4), round(float(s["latitude"]), 4), s["nome"], UF[cod[:2]], cod,
                      [[e["nome"], e["classe"]] for e in es]])
    lista.sort(key=lambda m: (-len(m[5]), m[2]))
    sem = [e for e in empresas if not e["codigo"]]
    corrigidas = [e for e in empresas if e["motivo"]]
    nota = ("o ponto fica na sede do município informado na lista, não no endereço da empresa; a contagem é de "
            "credenciamentos (cada CNPJ credenciado conta uma vez, e uma empresa pode ter filial credenciada à parte)")
    meta = {"titulo": "Indústria de defesa", "fonte": FONTE, "referencia": referencia, "data_lista": data_lista,
            "nivel": "api", "atualizado_em": hoje, "consulta": url, "pagina": PAGINA,
            "posicao": "sede de cada município (IBGE, Localidades do Brasil 2022)", "nota": nota,
            **conta, "municipios": len(lista), "sem_municipio": len(sem), "corrigidas": len(corrigidas)}
    gravar("empresas.json", {"meta": meta, "campos": ["lon", "lat", "municipio", "uf", "codigo_ibge", "empresas: [nome, EED ou ED]"],
                             "municipios": lista})
    # estados: total, EED, ED e os municípios com mais empresas (estado sem empresa credenciada fica de fora)
    valores = {}
    for e in empresas:
        if e["uf"] not in UF.values():
            continue
        v = valores.setdefault(e["uf"], {"valor": 0, "eed": 0, "ed": 0, "sem_municipio": 0, "_m": {}})
        v["valor"] += 1
        v[e["classe"].lower()] += 1
        if e["codigo"]:
            nome = sedes[e["codigo"]]["nome"]
            v["_m"][nome] = v["_m"].get(nome, 0) + 1
        else:
            v["sem_municipio"] += 1
    for v in valores.values():
        v["municipios"] = sorted(v.pop("_m").items(), key=lambda x: (-x[1], x[0]))[:6]
    gravar("estados.json", {"titulo": "Empresas de defesa credenciadas", "unidade": "empresas", "referencia": referencia,
                            "fonte": FONTE, "nivel": "api", "atualizado_em": hoje, "data_lista": data_lista,
                            "consulta": url, "pagina": PAGINA, **conta, "fora_dos_estados": sum(e["uf"] not in UF.values() for e in empresas),
                            "campos": {"valor": "empresas credenciadas (ED e EED)", "eed": "empresas estratégicas de defesa",
                                       "ed": "empresas de defesa", "municipios": "[município, empresas] dos que têm mais",
                                       "sem_municipio": "empresas do estado que a lista traz sem município reconhecível"},
                            "valores": valores})
    passos["municipios"] = "ok" if not sem else f"ok, {len(sem)} sem município (ver sem_municipio)"
    print(f"[defesa] {referencia}: {conta['total']} empresas ({conta['eed']} EED, {conta['ed']} ED) em {len(lista)} municípios; "
          f"{len(corrigidas)} com cidade corrigida, {len(sem)} sem município")
    return passos, sem


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arquivo", help="planilha .xlsx já baixada")
    arq = ap.parse_args().arquivo
    try:
        passos, sem = principal(arq)
        ok = True
    except Exception as e:
        print(f"[defesa] falhou, mantendo os arquivos anteriores: {e}")
        passos, sem, ok = {"planilha": f"falhou (ficaram os arquivos anteriores): {str(e)[:160]}"}, [], False
    gravar("robo.json", {"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "passos": passos,
                         "sem_municipio": [[e["nome"], e["cidade"], e["uf"], e["cnpj"]] for e in sem]})
    sys.exit(0 if ok else 1)
