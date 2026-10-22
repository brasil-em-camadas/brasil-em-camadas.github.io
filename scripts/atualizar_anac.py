"""Atualiza os aeroportos do mapa (ANAC): aeródromos públicos e passageiros dos últimos 12 meses.

Fontes: dados abertos da ANAC (https://sistemas.anac.gov.br/dadosabertos/):
1. Aeródromos públicos: Aerodromos/Aeródromos Públicos/Lista de aeródromos públicos/AerodromosPublicos.csv
   (código OACI, nome, município servido, UF, coordenadas, situação; a ANAC atualiza toda semana).
2. Dados estatísticos do transporte aéreo: Voos e operações aéreas/Dados Estatísticos do Transporte Aéreo/
   Dados_Estatisticos.csv (cerca de 360 MB; cada linha = empresa, mês, aeroporto de origem e de destino, com
   passageiros pagos e grátis e carga). O robô lê o arquivo aos poucos, sem guardar tudo na memória.

Cálculo: passageiros de um aeroporto = os que embarcaram (aeroporto de origem) + os que desembarcaram (aeroporto de
destino) nos 12 meses mais recentes do arquivo, em voos domésticos e internacionais, regulares ou não; é a mesma conta
de "passageiros embarcados e desembarcados" que os aeroportos divulgam (quem faz conexão conta duas vezes).
Carga = carga paga + grátis + correio, em toneladas, embarcada e desembarcada.

Roda sozinho no GitHub Actions (site.yml), junto com os outros robôs, e também à mão:
    python scripts/atualizar_anac.py
    python scripts/atualizar_anac.py --cache PASTA   (PASTA com AerodromosPublicos.csv e Dados_Estatisticos.csv)
Só usa a biblioteca padrão. Se a ANAC falhar, os arquivos antigos ficam. Saídas em site/data/aeroportos/:
  aeroportos.json  aeródromos públicos em funcionamento, com os passageiros e a carga de 12 meses
  robo.json        resultado de cada passo
"""
import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "aeroportos"
BASE = "https://sistemas.anac.gov.br/dadosabertos/"
PUBLICOS = "Aerodromos/Aeródromos Públicos/Lista de aeródromos públicos/AerodromosPublicos.csv"
ESTATISTICOS = "Voos e operações aéreas/Dados Estatísticos do Transporte Aéreo/Dados_Estatisticos.csv"
AGENTE = {"User-Agent": "Mozilla/5.0 (compatible; brasil-em-camadas; dados abertos)"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
UF = {"Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF",
      "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA", "Mato Grosso": "MT", "Mato Grosso do Sul": "MS", "Minas Gerais": "MG",
      "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE", "Piauí": "PI", "Rio de Janeiro": "RJ",
      "Rio Grande do Norte": "RN", "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR", "Santa Catarina": "SC",
      "São Paulo": "SP", "Sergipe": "SE", "Tocantins": "TO"}
MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "d'", "em"}


def url(caminho):
    return BASE + urllib.parse.quote(caminho)


def abrir(caminho, cache):
    """Resposta aberta (para ler aos poucos) ou o arquivo da pasta de cache."""
    if cache:
        return open(Path(cache) / Path(caminho).name, "rb")
    for i in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url(caminho), headers=AGENTE), timeout=300)
        except Exception:
            if i == 3:
                raise
            time.sleep(15 * (i + 1))


def titulo(t):
    """Nome em maiúsculas vira forma normal ("HORÁCIO DE MATTOS" → "Horácio de Mattos"); o resto fica como está."""
    t = re.sub(r"\s+", " ", (t or "").strip())
    if t != t.upper():
        return t
    def cap(p):   # maiúscula no começo e depois de "/" e "-" ("galeão/val de cans" → "Galeão/Val de Cans")
        return re.sub(r"(^|[/\-(])(\w)", lambda m: m.group(1) + m.group(2).upper(), p)
    palavras = []
    for i, p in enumerate(t.lower().split(" ")):
        palavras.append(p if (i and p in MINUSCULAS) else cap(p))
    return " ".join(palavras)


def numero(t):
    t = (t or "").strip()
    if not t:
        return 0.0
    return float(t.replace(".", "").replace(",", ".")) if "," in t else float(t)


def aerodromos(cache):
    with abrir(PUBLICOS, cache) as r:
        bruto = r.read()
    texto = bruto.decode("utf-8-sig") if bruto[:3] == b"\xef\xbb\xbf" else bruto.decode("latin-1")
    primeira, resto = texto.split("\n", 1)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", primeira)
    lista = {}
    for r in csv.DictReader(io.StringIO(resto, newline=""), delimiter=";"):
        if (r.get("Situação") or "").strip() != "Cadastrado":
            continue
        oaci = (r.get("Código OACI") or "").strip().upper()
        uf = UF.get((r.get("UF") or "").strip())
        try:
            lat, lon = float(r["LATGEOPOINT"].replace(",", ".")), float(r["LONGEOPOINT"].replace(",", "."))
        except (KeyError, ValueError):
            continue
        if not oaci or not uf or not (-35 < lat < 6 and -75 < lon < -28):
            continue
        lista[oaci] = {"lon": round(lon, 4), "lat": round(lat, 4), "nome": titulo(r["Nome"]),
                       "municipio": titulo(r.get("Município Servido") or r.get("Município")), "uf": uf}
    if len(lista) < 300:
        raise ValueError(f"só {len(lista)} aeródromos públicos em funcionamento")
    return lista, (m.group(1) if m else None)


def movimento(cache):
    """Passageiros e carga por aeroporto e mês, lendo o arquivo grande aos poucos (só os 3 últimos anos)."""
    ano_min = date.today().year - 2
    soma = {}   # (oaci, ano, mes) -> [passageiros, carga_kg]
    with abrir(ESTATISTICOS, cache) as r:
        texto = io.TextIOWrapper(r, encoding="utf-8-sig", newline="")
        primeira = texto.readline()   # "Atualizado em: AAAA-MM-DD"; se um dia sair, a primeira linha já é o cabeçalho
        if primeira.lower().startswith("atualizado"):
            leitor = csv.DictReader(texto, delimiter=";")
        else:
            leitor = csv.DictReader(texto, fieldnames=next(csv.reader([primeira], delimiter=";")), delimiter=";")
        linhas = 0
        for row in leitor:
            linhas += 1
            try:
                ano, mes = int(row["ANO"]), int(row["MES"])
            except (TypeError, ValueError):
                continue
            if ano < ano_min:
                continue
            pax = numero(row.get("PASSAGEIROS_PAGOS")) + numero(row.get("PASSAGEIROS_GRATIS"))
            carga = numero(row.get("CARGA_PAGA_KG")) + numero(row.get("CARGA_GRATIS_KG")) + numero(row.get("CORREIO_KG"))
            if not pax and not carga:
                continue
            for lado in ("AEROPORTO_DE_ORIGEM_SIGLA", "AEROPORTO_DE_DESTINO_SIGLA"):
                k = ((row.get(lado) or "").strip().upper(), ano, mes)
                if k[0]:
                    v = soma.setdefault(k, [0.0, 0.0])
                    v[0] += pax
                    v[1] += carga
    if linhas < 100000:
        raise ValueError(f"só {linhas} linhas nos dados estatísticos")
    return soma


def principal(cache):
    passos = {}
    lista, atualizado = aerodromos(cache)
    passos["aerodromos"] = f"ok, {len(lista)}"
    soma = movimento(cache)
    meses = sorted({(a, m) for _, a, m in soma})
    janela = set(meses[-12:])
    if len(janela) < 12:
        raise ValueError(f"só {len(janela)} meses nos dados estatísticos")
    total = {}
    for (oaci, a, m), (pax, carga) in soma.items():
        if (a, m) in janela:
            v = total.setdefault(oaci, [0.0, 0.0])
            v[0] += pax
            v[1] += carga
    passos["estatisticos"] = "ok"
    saida = []
    for oaci, a in lista.items():
        pax, carga = total.get(oaci, (0, 0))
        saida.append([a["lon"], a["lat"], oaci, a["nome"], a["municipio"], a["uf"], round(pax), round(carga / 1000)])
    saida.sort(key=lambda x: (-x[6], x[3]))
    (a0, m0), (a1, m1) = min(janela), max(janela)
    referencia = f"{MESES[m0 - 1]}/{a0} a {MESES[m1 - 1]}/{a1}"
    por_uf = {}
    for x in saida:
        v = por_uf.setdefault(x[5], {"aerodromos": 0, "com_passageiros": 0, "passageiros": 0, "maiores": []})
        v["aerodromos"] += 1
        if x[6] >= 1000:
            v["com_passageiros"] += 1
            v["passageiros"] += x[6]
            if len(v["maiores"]) < 3:
                v["maiores"].append([x[3], x[2], x[6]])
    # aeroportos brasileiros (prefixos OACI SB, SD, SI, SJ, SN, SS, SW) com movimento que não estão na lista dos públicos
    fora = sorted(((k, round(v[0])) for k, v in total.items() if k[:2] in ("SB", "SD", "SI", "SJ", "SN", "SS", "SW")
                   and k not in lista and v[0] >= 10000), key=lambda x: -x[1])
    hoje = date.today().isoformat()
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "aeroportos.json").write_text(json.dumps({
        "meta": {"titulo": "Aeroportos", "fonte": "ANAC, dados abertos: aeródromos públicos e dados estatísticos do transporte aéreo",
                 "referencia": referencia, "nivel": "api", "atualizado_em": hoje, "lista_atualizada_em": atualizado,
                 "consulta": [url(PUBLICOS), url(ESTATISTICOS)],
                 "metodo": "passageiros embarcados e desembarcados (pagos e grátis) nos 12 meses mais recentes; carga paga, grátis e correio, em toneladas",
                 "aerodromos": len(saida), "com_passageiros": sum(1 for x in saida if x[6] >= 1000),
                 "passageiros": sum(x[6] for x in saida), "fora_da_lista": fora[:20], "por_uf": por_uf},
        "campos": ["lon", "lat", "codigo_oaci", "nome", "municipio_servido", "uf", "passageiros_12_meses", "carga_t_12_meses"],
        "aeroportos": saida}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    passos["aeroportos"] = f"ok, {len(saida)} aeródromos, {sum(1 for x in saida if x[6] >= 1000)} com passageiros"
    print(f"[anac] {referencia}: {len(saida)} aeródromos públicos; {sum(x[6] for x in saida) / 1e6:.1f} milhões de passageiros; "
          f"fora da lista com movimento: {fora[:8]}")
    return passos


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", help="pasta com AerodromosPublicos.csv e Dados_Estatisticos.csv")
    args = ap.parse_args()
    try:
        passos, ok = principal(args.cache), True
    except Exception as e:
        print(f"[anac] falhou, mantendo os arquivos anteriores: {e}")
        passos, ok = {"aeroportos": f"falhou (ficaram os arquivos anteriores): {str(e)[:160]}"}, False
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "robo.json").write_text(json.dumps({"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                 "passos": passos}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sys.exit(0 if ok else 1)
