"""Cliente da API do Comex Stat (MDIC/SECEX): exportações e importações do Brasil por país e por estado.

Usado pelo robô do mapa (atualizar_comex.py) e pelo do acervo (acervo/comercio_exterior_mdic.py).
API: https://api-comexstat.mdic.gov.br (documentação em /docs). Sem chave. Limite de pedidos: com pedidos seguidos,
a API responde 429 ("tente novamente em 10 segundos"); o cliente espera cada vez mais (até 90 s) e tenta de novo.
A API devolve a lista vazia quando o período de uma consulta passa de um ano para outro: o cliente faz um pedido por ano.
Só usa a biblioteca padrão do Python.
"""
import csv
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api-comexstat.mdic.gov.br"
AGENTE = {"User-Agent": "brasil-em-camadas (dados abertos)", "Content-Type": "application/json",
          "Accept-Encoding": "gzip"}
RAIZ = Path(__file__).resolve().parents[1]
PAISES_CSV = RAIZ / "scripts" / "dados" / "comex_paises.csv"   # código do país no Comex Stat → ISO 3166 (alfa-3)

# Estado no Comex Stat ("UF do produto") → sigla. Os códigos do Comex Stat não são os do IBGE; a sigla é a mesma.
# Fora dos 27 estados (entram só no total do Brasil): ND não declarada, CB consumo de bordo, ED estados diversos (café),
# EX exterior, MN mercadoria nacionalizada, RE reexportação, ZN zona não declarada.
UF_IBGE = {"RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17", "MA": "21", "PI": "22",
           "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27", "SE": "28", "BA": "29", "MG": "31", "ES": "32",
           "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53"}

_ultimo = [0.0]


def _pedir(metodo, caminho, corpo=None, tentativas=12):
    url = API + caminho
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    erro = None
    for i in range(tentativas):
        espera = 3.0 - (time.time() - _ultimo[0])
        if espera > 0:
            time.sleep(espera)
        try:
            req = urllib.request.Request(url, data=dados, headers=AGENTE, method=metodo)
            with urllib.request.urlopen(req, timeout=300) as r:
                b = r.read()
            _ultimo[0] = time.time()
            b = gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b
            d = json.loads(b)
            if "error" in d:
                raise ValueError(f"{d['error'].get('code')}: {d['error'].get('message')}")
            return d
        except urllib.error.HTTPError as e:
            _ultimo[0] = time.time()
            erro = f"HTTP {e.code}"
        except Exception as e:
            _ultimo[0] = time.time()
            erro = str(e)
        # 429 = muitos pedidos seguidos: a API pede 10 s, mas depois de muitos pedidos só libera mais tarde
        time.sleep(min(15 * (i + 1), 90) if "429" in erro else 10 * (i + 1))
    raise RuntimeError(f"Comex Stat não respondeu ({caminho}): {erro}")


def atualizado():
    """Data da última atualização da base e o mês mais recente: {'updated': '2026-11-06', 'year': '2026', 'monthNumber': '10'}."""
    return _pedir("GET", "/general/dates/updated")["data"]


def paises():
    """Lista dos países do Comex Stat: [{'id': '160', 'text': 'China'}, ...]."""
    return _pedir("GET", "/tables/countries?language=pt")["data"]["list"]


def pais(codigo):
    return _pedir("GET", f"/tables/countries/{codigo}")["data"]


def ufs():
    """[{'text': 'Acre', 'id': '12', 'uf': 'AC'}, ...] (inclui os 'estados' especiais: ND, CB, ED, EX…)."""
    return _pedir("GET", "/tables/uf?language=pt")["data"]


def consulta(fluxo, de, ate, por_estado, bruto=None, nome=None):
    """Valor FOB (US$) e peso (kg) por mês e país (e estado, se por_estado), de 'AAAA-MM' a 'AAAA-MM'.
    Devolve (linhas, corpo do pedido)."""
    corpo = {"flow": fluxo, "monthDetail": True, "period": {"from": de, "to": ate}, "filters": [],
             "details": ["country", "state"] if por_estado else ["country"], "metrics": ["metricFOB", "metricKG"]}
    if bruto and nome and (Path(bruto) / nome).exists():
        return json.loads(gzip.decompress((Path(bruto) / nome).read_bytes())), corpo
    # a API devolve a lista vazia quando o período passa de um ano para outro: um pedido por ano
    linhas = []
    for ano in range(int(de[:4]), int(ate[:4]) + 1):
        c = {**corpo, "period": {"from": de if ano == int(de[:4]) else f"{ano}-01", "to": ate if ano == int(ate[:4]) else f"{ano}-12"}}
        linhas += _pedir("POST", "/general?language=pt", c)["data"]["list"]
    if bruto and nome:
        Path(bruto).mkdir(parents=True, exist_ok=True)
        (Path(bruto) / nome).write_bytes(gzip.compress(json.dumps(linhas, ensure_ascii=False).encode("utf-8")))
    return linhas, corpo


def tabela_paises(atualizar=False):
    """Código do Comex Stat → {'nome', 'iso3'}. Guarda em scripts/dados/comex_paises.csv; país novo na lista da API é
    consultado um a um (a API dá o código ISO só na ficha de cada país) e acrescentado ao arquivo."""
    tab = {}
    if PAISES_CSV.exists():
        for r in csv.DictReader(PAISES_CSV.open(encoding="utf-8")):
            tab[r["codigo"]] = {"nome": r["nome"], "iso3": r["iso3"]}
    if atualizar:
        mudou = False
        for p in paises():
            if p["id"] not in tab:
                f = pais(p["id"])
                tab[p["id"]] = {"nome": p["text"], "iso3": f.get("coPaisIsoa3") or ""}
                mudou = True
                print(f"[comex] país novo na lista do Comex Stat: {p['id']} {p['text']} ({tab[p['id']]['iso3'] or 'sem ISO'})")
            elif tab[p["id"]]["nome"] != p["text"]:
                tab[p["id"]]["nome"] = p["text"]
                mudou = True
        if mudou:
            gravar_tabela_paises(tab)
    return tab


def gravar_tabela_paises(tab):
    PAISES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PAISES_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["codigo", "nome", "iso3"])
        for c in sorted(tab):
            w.writerow([c, tab[c]["nome"], tab[c]["iso3"]])


def numero(v):
    return int(v) if v not in (None, "") else 0
