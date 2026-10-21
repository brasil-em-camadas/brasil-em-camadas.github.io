"""Atualiza o tráfego nas praças de pedágio das rodovias federais concedidas (ANTT).

Fonte: dados abertos da ANTT (licença Creative Commons Atribuição), catálogo em https://dados.antt.gov.br:
1. "Praça de Pedágio" (conjunto praca-de-pedagio): cada praça com concessionária, rodovia, km, município, UF,
   situação e coordenadas.
2. "Volume de Tráfego nas Praças de Pedágio" (conjunto volume-trafego-praca-pedagio), arquivo "Mensal consolidado"
   de cada ano: veículos por mês, praça, sentido, tipo de cobrança, categoria (eixos) e tipo de veículo
   (Passeio, Comercial, Moto). São os números que as concessionárias informam à ANTT.

Cálculo (feito pelo projeto, explicado no site):
- Janela: os 12 meses mais recentes que a ANTT já publicou.
- Uma praça no mapa = registros do cadastro com a mesma concessionária, rodovia e km (ex.: "Jacareí Norte" e
  "Jacareí Sul", ou as combinações de entrada e saída do pedágio sem cancela, o free flow, que ficam no mesmo pórtico).
  Validadores ficam separados das praças.
- Mês usado: o total do mês fica entre metade e 1,6 vez a mediana dos meses da praça. Assim saem os meses
  incompletos (início de cobrança, mês ainda sendo informado) e os que trazem lançamentos de outro mês.
- Veículos por dia = soma dos meses usados ÷ dias desses meses. Veículos comerciais = caminhões e ônibus.
- Dado que não fecha: quando mais de 40% do volume aparece como motos (nas rodovias federais concedidas, as motos
  são cerca de 2% do total), o número não é usado e a praça aparece sem tamanho, com a explicação.

Roda sozinho no GitHub Actions (site.yml), junto com os outros robôs, e também à mão:
    python scripts/atualizar_antt.py
    python scripts/atualizar_antt.py --cache PASTA   (PASTA com os CSV já baixados, com o nome original)
Só usa a biblioteca padrão. O servidor da ANTT às vezes demora: o robô espera e tenta de novo.
Se a ANTT falhar, os arquivos antigos ficam. Saídas em site/data/trafego/:
  pedagios.json  praças com veículos por dia e parte de veículos comerciais, no ponto da praça
  robo.json      resultado de cada passo
"""
import argparse
import calendar
import csv
import io
import json
import re
import statistics
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "trafego"
API = "https://dados.antt.gov.br/api/3/action/package_show?id="
CONJ_PRACAS, CONJ_VOLUME = "praca-de-pedagio", "volume-trafego-praca-pedagio"
CATALOGO = "https://dados.antt.gov.br/dataset/"
AGENTE = {"User-Agent": "Mozilla/5.0 (compatible; brasil-em-camadas; dados abertos)"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIRECAO = {"norte", "sul", "leste", "oeste", "crescente", "decrescente"}
UFS = {"RO", "AC", "AM", "RR", "PA", "AP", "TO", "MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA",
       "MG", "ES", "RJ", "SP", "PR", "SC", "RS", "MS", "MT", "GO", "DF"}


def baixar(url, cache=None, tentativas=4):
    if cache:
        return (Path(cache) / url.rsplit("/", 1)[-1]).read_bytes()
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=180) as r:
                dados = r.read()
            if dados:
                return dados
        except Exception:
            if i == tentativas - 1:
                raise
        time.sleep(15 * (i + 1))
    raise ValueError(f"resposta vazia de {url}")


def recursos(conjunto):
    """Arquivos CSV de um conjunto do catálogo da ANTT: [(nome, endereço)]."""
    d = json.loads(baixar(API + conjunto))
    return [(r.get("name") or "", r["url"]) for r in d["result"]["resources"] if (r.get("format") or "").upper() == "CSV"]


def tabela(dados):
    """CSV da ANTT: latin-1, separado por ponto e vírgula (às vezes com BOM)."""
    texto = dados.decode("utf-8-sig") if dados[:3] == b"\xef\xbb\xbf" else dados.decode("latin-1")
    return list(csv.DictReader(io.StringIO(texto, newline=""), delimiter=";"))


def numero(t):
    t = (t or "").strip().replace(" ", "")
    if not t:
        return 0.0
    return float(t.replace(".", "").replace(",", ".")) if "," in t else float(t)


def coord(t):
    return float((t or "").strip().replace(",", "."))


def nome_do_grupo(registros):
    """Nome comum das praças do grupo, sem o sentido ("Jacareí Norte" + "Jacareí Sul" = "Jacareí")."""
    nomes = [r["praca_de_pedagio"].split() for r in registros]
    if len(nomes) == 1:
        return " ".join(nomes[0])
    comum = []
    for palavras in zip(*nomes):
        if all(p == palavras[0] for p in palavras):
            comum.append(palavras[0])
        else:
            break
    while comum and (comum[-1].lower() in DIRECAO or comum[-1] in ("-", "–")):
        comum.pop()
    return " ".join(comum) or " ".join(nomes[0])


def rodovia(t):
    t = (t or "").strip().upper()
    m = re.fullmatch(r"BR-?(\d{1,3})", t)
    return f"BR-{int(m.group(1)):03d}" if m else t


def principal(cache):
    passos = {}
    if cache:
        arq_pracas = sorted(Path(cache).glob("dados-dos-pracas-de-pedagio*.csv"))[-1].name
        arqs_vol = sorted(p.name for p in Path(cache).glob("volume-trafego-praca-pedagio-*_mensal_consolidado.csv"))[-2:]
        url_pracas, urls_vol = CATALOGO + arq_pracas, [CATALOGO + a for a in arqs_vol]
    else:
        url_pracas = recursos(CONJ_PRACAS)[0][1]
        anuais = []
        for nome, url in recursos(CONJ_VOLUME):
            m = re.search(r"(20\d\d)\s+Mensal consolidado", nome, re.I)
            if m:
                anuais.append((int(m.group(1)), url))
        urls_vol = [u for _, u in sorted(anuais)[-2:]]
        if not urls_vol:
            raise ValueError("o catálogo não tem mais os arquivos \"Mensal consolidado\"")
    passos["catalogo"] = "ok"
    pracas = [r for r in tabela(baixar(url_pracas, cache)) if (r.get("situacao") or "").strip().lower() == "ativo"]
    if len(pracas) < 100:
        raise ValueError(f"só {len(pracas)} praças ativas no cadastro")
    volume = []
    for u in urls_vol:
        volume += tabela(baixar(u, cache))
    passos["arquivos"] = "ok"
    # janela: os 12 meses mais recentes publicados
    def mes(r):
        m, a = r["mes_ano"].strip().split("/")
        return int(a), int(m)
    meses = sorted({mes(r) for r in volume})
    janela = set(meses[-12:])
    if len(janela) < 6:
        raise ValueError(f"só {len(janela)} meses de volume")
    serie = {}   # (concessionária, praça) -> {mês: {tipo: veículos}}
    for r in volume:
        m = mes(r)
        if m not in janela:
            continue
        k = (r["concessionaria"].strip().upper(), r["praca"].strip())
        tipo = (r["tipo_de_veiculo"] or "").strip().capitalize()
        d = serie.setdefault(k, {}).setdefault(m, {})
        d[tipo] = d.get(tipo, 0.0) + numero(r["volume_total"])
    # praças do mapa: mesma concessionária, rodovia e km (validadores à parte)
    grupos = {}
    for r in pracas:
        val = r["praca_de_pedagio"].strip().lower().startswith("validador")
        k = (r["concessionaria"].strip().upper(), r["rodovia"].strip(), r["km_m"].strip(), val)
        grupos.setdefault(k, []).append(r)
    lista, casadas, sem_dado, incompletas = [], 0, 0, 0
    for (conc, rod, km, val), rs in grupos.items():
        por_mes = {}
        achou = False
        for r in rs:
            s = serie.get((conc, r["praca_de_pedagio"].strip()))
            if not s:
                continue
            achou = True
            for m, tipos in s.items():
                d = por_mes.setdefault(m, {})
                for t, x in tipos.items():
                    d[t] = d.get(t, 0.0) + x
        casadas += achou
        totais = {m: sum(d.values()) for m, d in por_mes.items()}
        usados = []
        if totais:
            med = statistics.median(totais.values())
            usados = sorted(m for m, x in totais.items() if med > 0 and 0.5 * med <= x <= 1.6 * med)
        soma = {}
        for m in usados:
            for t, x in por_mes[m].items():
                soma[t] = soma.get(t, 0.0) + x
        total = sum(soma.values())
        dias = sum(calendar.monthrange(a, m)[1] for a, m in usados)
        aviso = 0
        if not total or not dias:
            aviso, veic, com = 1, None, None
            sem_dado += 1
        elif soma.get("Moto", 0) / total > 0.4:
            aviso, veic, com = 2, None, None
            incompletas += 1
        else:
            veic, com = round(total / dias), round(soma.get("Comercial", 0) / total * 100, 1)
        lat = round(statistics.mean(coord(r["latitude"]) for r in rs), 5)
        lon = round(statistics.mean(coord(r["longitude"]) for r in rs), 5)
        uf = rs[0]["uf"].strip().upper()
        km_txt = f"{float(km.replace(',', '.')):g}".replace(".", ",") if re.fullmatch(r"[\d.,]+", km) else km
        periodo = (f"{MESES[usados[0][1] - 1]}/{usados[0][0]} a {MESES[usados[-1][1] - 1]}/{usados[-1][0]}" if usados else "")
        lista.append([lon, lat, nome_do_grupo(rs), conc, rodovia(rod), km_txt, rs[0]["municipal"].strip(), uf if uf in UFS else "",
                      veic, com, len(usados), periodo, aviso, 1 if val else 0])
    lista.sort(key=lambda p: -(p[8] or 0))   # as mais movimentadas primeiro: ficam desenhadas por baixo
    a0, m0 = min(janela); a1, m1 = max(janela)
    referencia = f"{MESES[m0 - 1]}/{a0} a {MESES[m1 - 1]}/{a1}"
    com_numero = [p for p in lista if p[8]]
    hoje = date.today().isoformat()
    faixas = {"menos de 25%": sum(p[9] < 25 for p in com_numero), "25 a 40%": sum(25 <= p[9] < 40 for p in com_numero),
              "40 a 55%": sum(40 <= p[9] < 55 for p in com_numero), "55% ou mais": sum(p[9] >= 55 for p in com_numero)}
    por_uf = {}
    for p in lista:
        if p[7]:
            v = por_uf.setdefault(p[7], {"pracas": 0, "maior": None})
            v["pracas"] += 1
            if p[8] and (not v["maior"] or p[8] > v["maior"][1]):
                v["maior"] = [p[2], p[8], p[4], p[5], p[6], p[3]]   # praça, veículos/dia, rodovia, km, município, concessionária
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "pedagios.json").write_text(json.dumps({
        "meta": {"titulo": "Tráfego nos pedágios federais", "fonte": "ANTT, dados abertos: praças de pedágio e volume de tráfego nas praças",
                 "referencia": referencia, "nivel": "api", "atualizado_em": hoje, "licenca": "Creative Commons Atribuição",
                 "consulta": [url_pracas, *urls_vol], "catalogo": [CATALOGO + CONJ_PRACAS, CATALOGO + CONJ_VOLUME],
                 "metodo": ("média de veículos por dia nos meses da janela cujo total fica entre metade e 1,6 vez a mediana "
                            "dos meses da praça; veículos comerciais = caminhões e ônibus; praças com mais de 40% de motos "
                            "no volume informado ficam sem número"),
                 "pracas": len(lista), "com_numero": len(com_numero), "sem_dado": sem_dado, "dado_incompleto": incompletas,
                 "faixas_comerciais": faixas, "por_uf": por_uf},
        "campos": ["lon", "lat", "praca", "concessionaria", "rodovia", "km", "municipio", "uf", "veiculos_por_dia",
                   "pct_comerciais", "meses_usados", "periodo", "aviso (0 ok, 1 sem volume na janela, 2 dado que não fecha)", "validador"],
        "pracas": lista}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    passos["pracas"] = f"ok, {len(lista)} praças ({casadas} com volume; {incompletas} com dado que não fecha)"
    print(f"[antt] {referencia}: {len(lista)} praças no mapa, {len(com_numero)} com número; faixas {faixas}")
    return passos


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", help="pasta com os CSV já baixados")
    args = ap.parse_args()
    try:
        passos, ok = principal(args.cache), True
    except Exception as e:
        print(f"[antt] falhou, mantendo os arquivos anteriores: {e}")
        passos, ok = {"pracas": f"falhou (ficaram os arquivos anteriores): {str(e)[:160]}"}, False
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "robo.json").write_text(json.dumps({"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                 "passos": passos}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sys.exit(0 if ok else 1)
