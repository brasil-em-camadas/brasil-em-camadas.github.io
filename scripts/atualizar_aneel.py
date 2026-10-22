"""Atualiza as usinas de energia elétrica do mapa pelo SIGA, o cadastro de geração da ANEEL (atualizado todo dia).

Fonte: ANEEL, dados abertos (https://dadosabertos.aneel.gov.br), conjunto "SIGA - Sistema de Informações de Geração da
ANEEL", arquivo siga-empreendimentos-geracao-diario.csv: cada usina com fase (operação, construção…), tipo (UHE, PCH, CGH,
EOL, UFV, UTE, UTN), origem e fonte do combustível, potência fiscalizada (kW), coordenadas, município, dono e data de
entrada em operação. O endereço do arquivo vem da API do catálogo (CKAN), porque pode mudar.

O que entra:
- no mapa: as usinas em operação com 1 MW ou mais (são mais de 99% da potência; as menores são quase todas solares,
  aos milhares, e lotariam o mapa);
- na soma de cada estado (pintura e ficha): todas as usinas em operação, de qualquer tamanho.
Itaipu: a ANEEL registra só a parte brasileira (7.000 MW); a usina inteira tem 14.000 MW, metade do Paraguai.
Os painéis de telhado e as pequenas usinas da micro e minigeração distribuída ficam em outro cadastro da ANEEL e não entram.

As linhas de transmissão e as subestações continuam vindo da EPE (scripts/atualizar_epe.py).
Roda sozinho no GitHub Actions (site.yml), junto com os outros robôs, e também à mão:
    python scripts/atualizar_aneel.py
    python scripts/atualizar_aneel.py --arquivo siga.csv   (arquivo já baixado)
Só usa a biblioteca padrão. Se a ANEEL falhar, os arquivos antigos ficam.
Saídas em site/data/energia/: usinas.json, estados.json e robo_aneel.json (resultado de cada passo).
"""
import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "energia"
CATALOGO = "https://dadosabertos.aneel.gov.br/api/3/action/package_show?id=siga-sistema-de-informacoes-de-geracao-da-aneel"
PAGINA = "https://dadosabertos.aneel.gov.br/dataset/siga-sistema-de-informacoes-de-geracao-da-aneel"
AGENTE = {"User-Agent": "Mozilla/5.0 (compatible; brasil-em-camadas; dados abertos)"}
NOMES = {"eol": "Eólica", "sol": "Solar", "uhe": "Hidrelétrica (UHE)", "pch": "Pequena central hidrelétrica (PCH)",
         "cgh": "Central geradora hidrelétrica (CGH)", "bio": "Termelétrica a biomassa", "fos": "Termelétrica fóssil", "nuc": "Nuclear"}
TIPO = {"UHE": "uhe", "PCH": "pch", "CGH": "cgh", "EOL": "eol", "UFV": "sol", "UTN": "nuc"}
UFS = {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
       "RO", "RR", "RS", "SC", "SE", "SP", "TO"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
FONTE = "ANEEL, SIGA (Sistema de Informações de Geração)"
MINIMO_KW = 1000
OBS = [("Itaipu", "A ANEEL registra a parte brasileira (7.000 MW); a usina inteira tem 14.000 MW, e a outra metade é do Paraguai.")]


def baixar(url, tentativas=4):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=240) as r:
                dados = r.read()
            if dados:
                return dados
        except Exception:
            if i == tentativas - 1:
                raise
        time.sleep(10 * (i + 1))
    raise ValueError(f"resposta vazia de {url}")


def endereco_csv():
    bruto = baixar(CATALOGO)
    try:
        d = json.loads(bruto)
    except ValueError:
        raise ValueError(f"o catálogo da ANEEL não respondeu em JSON: {' '.join(bruto[:300].decode('utf-8', 'replace').split())[:160]}")
    for r in d["result"]["resources"]:
        if (r.get("format") or "").upper() == "CSV" and "diario" in r["url"]:
            return r["url"]
    raise ValueError("o catálogo do SIGA não tem mais o CSV diário")


def numero(t):
    t = (t or "").strip()
    if not t:
        return 0.0
    return float(t.replace(".", "").replace(",", ".")) if "," in t else float(t)


def dono(texto):
    t = " ".join((texto or "").split())
    return t[len("100% para "):] if t.startswith("100% para ") else t


def principal(arquivo):
    passos = {}
    url = "arquivo local" if arquivo else endereco_csv()
    bruto = Path(arquivo).read_bytes() if arquivo else baixar(url)
    texto = bruto.decode("utf-8-sig") if bruto[:3] == b"\xef\xbb\xbf" else bruto.decode("utf-8", "replace")
    linhas = list(csv.DictReader(io.StringIO(texto, newline=""), delimiter=";"))
    passos["siga"] = "ok"
    gerado = max((r.get("DatGeracaoConjuntoDados") or "" for r in linhas), default="")
    usinas, por_uf, ultimo = [], {}, ""
    for r in linhas:
        if (r.get("DscFaseUsina") or "").strip() != "Operação":
            continue
        sig = (r.get("SigTipoGeracao") or "").strip().upper()
        tipo = TIPO.get(sig) or ("fos" if (r.get("DscOrigemCombustivel") or "").strip() == "Fóssil" else "bio" if sig == "UTE" else None)
        kw = numero(r.get("MdaPotenciaFiscalizadaKw"))
        uf = (r.get("SigUFPrincipal") or "").strip().upper()
        if not tipo or kw <= 0:
            continue
        ini = (r.get("DatEntradaOperacao") or "").strip()
        if ini and ini <= (gerado or "9999"):
            ultimo = max(ultimo, ini)
        if uf in UFS:
            v = por_uf.setdefault(uf, {"valor": 0.0, "usinas": 0, **{t: 0.0 for t in NOMES}})
            v["valor"] += kw / 1000
            v[tipo] += kw / 1000
            v["usinas"] += 1
        if kw < MINIMO_KW:
            continue
        try:
            lat, lon = numero(r.get("NumCoordNEmpreendimento")), numero(r.get("NumCoordEEmpreendimento"))
        except ValueError:
            continue
        if not (-35 < lat < 6 and -75 < lon < -28):
            continue
        if tipo in ("uhe", "pch", "cgh"):
            # sub-bacia hidrográfica, sem o número do código (ex.: "41 - Das Velhas - Sao Francisco" → "Das Velhas - Sao Francisco")
            extra = re.sub(r"^\d+\s*-\s*", "", " ".join((r.get("DscSubBacia") or "").split()))
        else:
            extra = " ".join((r.get("NomFonteCombustivel") or "").split())
        nome = " ".join((r.get("NomEmpreendimento") or "").split())
        usinas.append([round(lon, 4), round(lat, 4), round(kw), tipo, nome, uf if uf in UFS else "",
                       int(ini[:4]) if ini[:4].isdigit() else None, dono(r.get("DscPropriRegimePariticipacao")), extra])
    if len(usinas) < 2000 or len(por_uf) < 26:
        raise ValueError(f"só {len(usinas)} usinas no mapa e {len(por_uf)} estados")
    usinas.sort(key=lambda u: -u[2])   # as maiores primeiro: as pequenas ficam desenhadas por cima
    observacoes = {u[4]: texto for u in usinas for chave, texto in OBS if chave.lower() in u[4].lower()}
    for u in usinas:
        if u[4] in observacoes and u[5] in por_uf:
            por_uf[u[5]].setdefault("obs", []).append(observacoes[u[4]])
    for v in por_uf.values():
        for k in list(v):
            if isinstance(v[k], float):
                v[k] = round(v[k], 1)
    total_mw = round(sum(v["valor"] for v in por_uf.values()))
    no_mapa_mw = round(sum(u[2] for u in usinas) / 1000)
    a, m = (gerado[:4], gerado[5:7]) if len(gerado) >= 7 else ("", "")
    referencia = f"usinas em operação em {gerado[8:10]}/{m}/{a}" if len(gerado) == 10 else "usinas em operação"
    hoje = date.today().isoformat()
    nota = ("geração centralizada registrada na ANEEL; os painéis de telhado e as pequenas usinas da micro e minigeração "
            "distribuída ficam em outro cadastro e não entram")
    (SAIDA).mkdir(parents=True, exist_ok=True)
    (SAIDA / "usinas.json").write_text(json.dumps({
        "meta": {"titulo": "Usinas de energia elétrica", "referencia": referencia, "fonte": FONTE, "nivel": "api", "atualizado_em": hoje,
                 "consulta": url, "pagina": PAGINA, "nota": nota, "minimo_kw": MINIMO_KW, "tipos": NOMES, "total_mw": no_mapa_mw,
                 "total_mw_todas": total_mw, "usinas_todas": sum(v["usinas"] for v in por_uf.values()),
                 "observacoes": observacoes, "ultima_entrada_em_operacao": ultimo},
        "campos": ["lon", "lat", "kw", "tipo", "nome", "uf", "ano", "dono", "bacia_ou_combustivel"], "usinas": usinas},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (SAIDA / "estados.json").write_text(json.dumps({
        "titulo": "Potência elétrica instalada", "unidade": "MW", "referencia": referencia, "fonte": FONTE, "nivel": "api",
        "atualizado_em": hoje, "nota": nota, "tipos": NOMES, "total_mw": total_mw, "valores": por_uf},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    passos["usinas"] = f"ok, {len(usinas)} usinas no mapa ({no_mapa_mw} MW); {total_mw} MW em todas"
    print(f"[aneel] {referencia}: {len(usinas)} usinas de {MINIMO_KW // 1000} MW ou mais ({no_mapa_mw} MW); todas somam {total_mw} MW")
    return passos


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arquivo", help="CSV do SIGA já baixado")
    args = ap.parse_args()
    try:
        passos, ok = principal(args.arquivo), True
    except Exception as e:
        print(f"[aneel] falhou, mantendo os arquivos anteriores: {e}")
        passos, ok = {"usinas": f"falhou (ficaram os arquivos anteriores): {str(e)[:160]}"}, False
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "robo_aneel.json").write_text(json.dumps({"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                       "passos": passos}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sys.exit(0 if ok else 1)
