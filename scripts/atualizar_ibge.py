"""Atualiza as camadas que vêm da API SIDRA do IBGE.

Roda sozinho no GitHub Actions (ver .github/workflows/site.yml) e também à mão:
    python scripts/atualizar_ibge.py

Regra de segurança: se a API falhar ou devolver algo estranho (menos de 27 estados),
o arquivo antigo NÃO é apagado. O site continua com o último dado bom e a data dele.
Só usa a biblioteca padrão do Python, sem instalar nada.
"""
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


if __name__ == "__main__":
    ok = [atualizar(c) for c in CAMADAS]
    # Só falha o robô se NADA atualizou, para alguém ser avisado por e-mail pelo GitHub.
    sys.exit(0 if any(ok) else 1)
