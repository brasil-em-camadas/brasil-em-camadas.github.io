"""Atualiza a telefonia celular do mapa (Anatel): sinal 4G/5G por estado e por município, e os municípios com 5G.

Fontes: dados abertos da Anatel (licença CC-BY), listados no Portal Brasileiro de Dados Abertos (dados.gov.br):
1. Índice Brasileiro de Conectividade (IBC), atualizado uma vez por ano:
   https://www.anatel.gov.br/dadosabertos/paineis_de_dados/meu_municipio/ibc.zip
   - IBC_UF_indicadores_originais.csv (por estado) e IBC_municipios_indicadores_originais.csv (por município);
   - "Cobertura Pop. 4G5G": parte dos moradores coberta pelo sinal 4G ou 5G. É uma estimativa da Anatel feita com as
     antenas licenciadas das operadoras e um modelo de propagação do sinal (não é medição no local);
   - "Fibra" (por estado): parte dos municípios com rede de fibra óptica de transporte (backhaul);
   - "Adensamento Estações" (por estado): estações rádio base (antenas de celular) por 10 mil habitantes.
2. Presença da telefonia móvel (RQUAL), atualizada todo mês:
   https://www.anatel.gov.br/dadosabertos/paineis_de_dados/infraestrutura/smp_mun_atendidos.zip
   - Tabela_Municipios_Atendidos_SMP_v2.csv: para cada mês, operadora, município e tecnologia (2G a 5G), "SIM" ou "NÃO".

Roda sozinho no GitHub Actions (site.yml), junto com os outros robôs, e também à mão:
    python scripts/atualizar_anatel.py
    python scripts/atualizar_anatel.py --cache PASTA   (PASTA com os dois .zip já baixados)
Só usa a biblioteca padrão. Se a Anatel falhar ou mandar algo incompleto, os arquivos antigos ficam.
Saídas em site/data/celular/:
  estados.json     pintura dos estados e ficha (IBC) + quantos municípios de cada estado têm 5G (RQUAL)
  municipios.json  sinal 4G/5G de cada município, no ponto da sede (IBC)
  5g.json          municípios com 5G e as operadoras, no ponto da sede (RQUAL)
  robo.json        resultado de cada passo
"""
import argparse
import csv
import io
import json
import sys
import time
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "celular"
SEDES = RAIZ / "scripts" / "dados" / "sedes_municipais.csv"
BASE = "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/"
IBC_ZIP, RQUAL_ZIP = "meu_municipio/ibc.zip", "infraestrutura/smp_mun_atendidos.zip"
CATALOGO = {"ibc": "https://dados.gov.br/dados/conjuntos-dados/meu-municipio---indice-brasileiro-de-conectividade",
            "rqual": "https://dados.gov.br/dados/conjuntos-dados/infraestrutura---presenca-da-telefonia-movel---rqual"}
UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
      "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
      "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS",
      "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
OPERADORAS = {"CLARO": "Claro", "VIVO": "Vivo", "TIM": "TIM", "OI": "Oi", "ALGAR": "Algar"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
FONTE_IBC = "Anatel, Índice Brasileiro de Conectividade (IBC)"
FONTE_RQUAL = "Anatel, presença da telefonia móvel nos municípios (RQUAL)"
NOTA = ("estimativa da Anatel a partir das antenas licenciadas e de um modelo de propagação do sinal, "
        "não medição no local; moradores cobertos pelo sinal 4G ou 5G de qualquer operadora")


def baixar(caminho, cache):
    if cache:
        return (Path(cache) / Path(caminho).name).read_bytes()
    for i in range(4):
        try:
            req = urllib.request.Request(BASE + caminho, headers={"User-Agent": "Mozilla/5.0 (compatible; brasil-em-camadas; dados abertos)"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception:
            if i == 3:
                raise
            time.sleep(10 * (i + 1))


def tabela(z, nome):
    """Lê um CSV da Anatel (UTF-8 com BOM, separado por ponto e vírgula) de dentro do zip."""
    return csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="utf-8-sig", newline=""), delimiter=";")


def numero(t):
    t = (t or "").strip()
    return float(t.replace(".", "").replace(",", ".")) if t.count(",") == 1 and t.count(".") >= 1 else (float(t.replace(",", ".")) if t else None)


def sedes():
    return {r["codigo_ibge"]: r for r in csv.DictReader(SEDES.open(encoding="utf-8"))}


def ler(nome):
    try:
        return json.loads((SAIDA / nome).read_text(encoding="utf-8"))
    except Exception:
        return None


def gravar(nome, dados):
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / nome).write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def ibc(cache):
    """Pintura dos estados e camada por município, do IBC (último ano com os 27 estados completos)."""
    z = zipfile.ZipFile(io.BytesIO(baixar(IBC_ZIP, cache)))
    uf = [r for r in tabela(z, "IBC_UF_indicadores_originais.csv") if (r.get("UF") or "").strip() in UF.values()]
    anos = sorted({r["Ano"] for r in uf if r["Ano"].isdigit()})
    ano = next(a for a in reversed(anos) if sum(1 for r in uf if r["Ano"] == a and numero(r["Cobertura Pop. 4G5G"]) is not None) == 27)
    valores = {}
    for r in uf:
        if r["Ano"] != ano:
            continue
        cob, fibra, erb, ind = (numero(r[k]) for k in ("Cobertura Pop. 4G5G", "Fibra", "Adensamento Estações", "IBC"))
        if not 0 < cob <= 1:
            raise ValueError(f"cobertura fora do esperado em {r['UF']}: {r['Cobertura Pop. 4G5G']}")
        valores[r["UF"].strip()] = {"valor": round(cob * 100, 1), "ibc": ind, "fibra": round(fibra * 100) if fibra is not None else None,
                                    "erb_10mil": round(erb, 1) if erb is not None else None}
    s = sedes()
    mun = []
    for r in tabela(z, "IBC_municipios_indicadores_originais.csv"):
        if r["Ano"] != ano:
            continue
        k, cob = r["Código Município"].strip(), numero(r["Cobertura Pop. 4G5G"])
        if k in s and cob is not None:
            mun.append([round(float(s[k]["longitude"]), 4), round(float(s[k]["latitude"]), 4), round(cob * 100, 1), s[k]["nome"], UF[k[:2]], k])
    if len(mun) < 5500:
        raise ValueError(f"só {len(mun)} municípios no IBC {ano}")
    mun.sort(key=lambda m: -m[2])   # os de sinal mais fraco por último: ficam desenhados por cima
    hoje = date.today().isoformat()
    fx = {"95% ou mais": sum(m[2] >= 95 for m in mun), "80 a 95%": sum(80 <= m[2] < 95 for m in mun),
          "50 a 80%": sum(50 <= m[2] < 80 for m in mun), "menos de 50%": sum(m[2] < 50 for m in mun)}
    gravar("municipios.json", {
        "meta": {"titulo": "Sinal 4G/5G por município", "referencia": ano, "fonte": FONTE_IBC + f" {ano}: população coberta por 4G ou 5G",
                 "nota": NOTA, "posicao": "sede de cada município (IBGE, Localidades do Brasil 2022)", "nivel": "api",
                 "atualizado_em": hoje, "consulta": BASE + IBC_ZIP, "catalogo": CATALOGO["ibc"], "faixas": fx},
        "campos": ["lon", "lat", "cobertura_4g5g_pct", "nome", "uf", "codigo_ibge"], "municipios": mun})
    print(f"[celular] IBC {ano}: 27 estados, {len(mun)} municípios; faixas {fx}")
    return {"referencia": ano, "atualizado_em": hoje, "valores": valores}


def rqual(cache):
    """Municípios com 5G no último mês da tabela de presença da telefonia móvel."""
    z = zipfile.ZipFile(io.BytesIO(baixar(RQUAL_ZIP, cache)))
    ultimo, d = (0, 0), {}   # a tabela traz todos os meses desde 2013: guarda só o mais recente
    for r in tabela(z, "Tabela_Municipios_Atendidos_SMP_v2.csv"):
        m, a = r["Período"].strip().split("/")
        p = (int(a), int(m))
        if p < ultimo:
            continue
        if p > ultimo:
            ultimo, d = p, {}
        cod = r["Código IBGE"].strip()
        d.setdefault(cod, set())
        if r["Tecnologia"].strip() == "5G" and r["Presença"].strip().upper() == "SIM":
            d[cod].add(OPERADORAS.get(r["Operadora"].strip().upper(), r["Operadora"].strip().title()))
    ano, mes = ultimo
    if len(d) < 5500:
        raise ValueError(f"só {len(d)} municípios em {mes:02d}/{ano}")
    s = sedes()
    lista = [[round(float(s[k]["longitude"]), 4), round(float(s[k]["latitude"]), 4), s[k]["nome"], UF[k[:2]], ", ".join(sorted(ops)), k]
             for k, ops in d.items() if ops and k in s]
    lista.sort(key=lambda m: (m[3], m[2]))
    por_uf = {u: [0, 0] for u in UF.values()}
    for k, ops in d.items():
        u = UF.get(k[:2])
        if u:
            por_uf[u][1] += 1
            por_uf[u][0] += bool(ops)
    referencia, hoje = f"{MESES[mes - 1]}/{ano}", date.today().isoformat()
    gravar("5g.json", {
        "meta": {"titulo": "5G nos municípios", "referencia": referencia, "fonte": FONTE_RQUAL, "nivel": "api", "atualizado_em": hoje,
                 "nota": "município onde a Anatel registra o 5G presente, de pelo menos uma operadora; não quer dizer sinal em todo o município",
                 "posicao": "sede de cada município (IBGE, Localidades do Brasil 2022)", "consulta": BASE + RQUAL_ZIP,
                 "catalogo": CATALOGO["rqual"], "municipios": len(lista), "total": len(d)},
        "campos": ["lon", "lat", "nome", "uf", "operadoras_5g", "codigo_ibge"], "municipios": lista})
    print(f"[celular] RQUAL {referencia}: 5G em {len(lista)} de {len(d)} municípios")
    return {"referencia": referencia, "atualizado_em": hoje, "municipios": len(lista), "total": len(d), "por_uf": por_uf}


def estados(r_ibc, r_rqual):
    """Junta as duas fontes num só arquivo para a pintura e a ficha. A parte que falhou fica como estava."""
    antigo = ler("estados.json") or {}
    base = r_ibc or ({"referencia": antigo["referencia"], "atualizado_em": antigo["atualizado_em"], "valores": antigo["valores"]}
                     if antigo.get("valores") else None)
    if not base:
        return False
    g5 = ({k: v for k, v in r_rqual.items() if k != "por_uf"} if r_rqual else antigo.get("cinco_g"))
    por_uf = r_rqual["por_uf"] if r_rqual else {u: v.get("g5") for u, v in antigo.get("valores", {}).items()}
    valores = {u: {**v, "g5": por_uf.get(u)} for u, v in base["valores"].items()}
    gravar("estados.json", {
        "titulo": "Sinal de celular 4G/5G", "unidade": "% da população com sinal", "referencia": base["referencia"],
        "fonte": FONTE_IBC + f" {base['referencia']}", "nivel": "api", "atualizado_em": base["atualizado_em"], "nota": NOTA,
        "consulta": [BASE + IBC_ZIP, BASE + RQUAL_ZIP], "catalogo": list(CATALOGO.values()),
        "campos": {"valor": "% dos moradores com sinal 4G ou 5G", "ibc": "Índice Brasileiro de Conectividade (0 a 100)",
                   "fibra": "% dos municípios com fibra óptica de transporte (backhaul)", "erb_10mil": "antenas (estações rádio base) por 10 mil habitantes",
                   "g5": "[municípios com 5G, municípios do estado]"},
        "cinco_g": g5, "valores": valores})
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", help="pasta com ibc.zip e smp_mun_atendidos.zip já baixados")
    cache = ap.parse_args().cache
    passos, res = {}, {}
    for nome, f in (("ibc", ibc), ("rqual", rqual)):
        try:
            res[nome] = f(cache)
            passos[nome] = "ok"
        except Exception as e:
            print(f"[celular] {nome} falhou, mantendo o arquivo anterior: {e}")
            passos[nome] = f"falhou (ficou o arquivo anterior): {str(e)[:120]}"
    passos["estados"] = "ok" if estados(res.get("ibc"), res.get("rqual")) else "sem dados"
    gravar("robo.json", {"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "passos": passos})
    sys.exit(0 if passos["ibc"] == "ok" or passos["rqual"] == "ok" else 1)
