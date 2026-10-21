"""Atualiza a energia elétrica do mapa: usinas em operação e linhas de transmissão, do Webmap da EPE.

Fonte: EPE (Empresa de Pesquisa Energética, ligada ao Ministério de Minas e Energia), serviço público de mapas
"Sistema Elétrico Existente": https://gisepeprd2.epe.gov.br/arcgis/rest/services/SMA/Webmap_EPE_Sistema_Eletrico_Existente/MapServer
Camadas: 0 eólicas, 1 solares, 2 hidrelétricas (UHE), 3 PCH, 4 CGH, 5 térmicas a biomassa, 6 térmicas fósseis,
7 nucleares, 9 linhas de transmissão. A potência vem em kW; o estado vem do código CEG da ANEEL (ex.: EOL.CV.RJ.028730-0.01).
É geração centralizada: os painéis solares de telhado (geração distribuída) não estão na base.

Roda sozinho no GitHub Actions (site.yml), junto com os robôs do IBGE e da ANP, e também à mão:
    python scripts/atualizar_epe.py
Só usa a biblioteca padrão. Se a EPE falhar ou responder algo incompleto, os arquivos antigos ficam.
Saídas em site/data/energia/: usinas.json, linhas.json, estados.json e robo.json (resultado de cada passo).
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "energia"
BASE = "https://gisepeprd2.epe.gov.br/arcgis/rest/services/SMA/Webmap_EPE_Sistema_Eletrico_Existente/MapServer"
TIPOS = {0: "eol", 1: "sol", 2: "uhe", 3: "pch", 4: "cgh", 5: "bio", 6: "fos", 7: "nuc"}
NOMES = {"eol": "Eólica", "sol": "Solar", "uhe": "Hidrelétrica (UHE)", "pch": "Pequena central hidrelétrica (PCH)",
         "cgh": "Central geradora hidrelétrica (CGH)", "bio": "Termelétrica a biomassa", "fos": "Termelétrica fóssil", "nuc": "Nuclear"}
UFS = {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
       "RO", "RR", "RS", "SC", "SE", "SP", "TO"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
FONTE = "EPE, Webmap (sistema elétrico existente)"
# observações sobre registros da base que podem confundir (o número da EPE fica como está; o site mostra a observação ao lado)
OBS = [("Itaipu", "A EPE registra 14.000 MW, a potência da usina inteira; pelo tratado de Itaipu, metade da usina é do Paraguai.")]


def pedir(url, tentativas=4):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "brasil-em-camadas (dados abertos)"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if i == tentativas - 1:
                raise
            time.sleep(5 * (i + 1))


def consultar(camada, campos="*", extra=None):
    """Todas as feições de uma camada, em GeoJSON, de 2.000 em 2.000."""
    feats, inicio = [], 0
    while True:
        q = {"where": "1=1", "outFields": campos, "outSR": "4326", "f": "geojson", "orderByFields": "OBJECTID",
             "resultOffset": inicio, "resultRecordCount": 2000, **(extra or {})}
        d = pedir(f"{BASE}/{camada}/query?" + urllib.parse.urlencode(q))
        if "features" not in d:
            raise ValueError(f"camada {camada}: resposta sem feições: {str(d)[:200]}")
        lote = d["features"]
        feats += lote
        if len(lote) < 2000 and not d.get("exceededTransferLimit"):
            return feats
        inicio += len(lote)


def contar(camada):
    return pedir(f"{BASE}/{camada}/query?" + urllib.parse.urlencode({"where": "1=1", "returnCountOnly": "true", "f": "json"}))["count"]


def gravar(nome, dados):
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / nome).write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def dono(texto):
    t = " ".join((texto or "").split())
    return t[len("100% para "):] if t.startswith("100% para ") else t


def usinas():
    lista, ultimo = [], 0
    for camada, tipo in TIPOS.items():
        feats = consultar(camada)
        if len(feats) != contar(camada):
            raise ValueError(f"camada {camada}: vieram {len(feats)} de {contar(camada)}")
        for f in feats:
            p = {k.lower(): v for k, v in (f.get("properties") or {}).items()}
            g = f.get("geometry") or {}
            if g.get("type") != "Point" or not p.get("potencia"):
                continue
            ceg = (p.get("ceg") or "").strip()
            uf = ceg.split(".")[2] if ceg.count(".") >= 3 and ceg.split(".")[2] in UFS else ""
            ini = p.get("ini_oper")
            if ini:
                ultimo = max(ultimo, ini)
            extra = p.get("rio") or p.get("combust") or ""
            lista.append([round(g["coordinates"][0], 4), round(g["coordinates"][1], 4), round(p["potencia"]), tipo,
                          " ".join((p.get("nome") or "").split()), uf,
                          datetime.fromtimestamp(ini / 1000, timezone.utc).year if ini else None, dono(p.get("propriet")), extra.strip()])
    if len(lista) < 2000:
        raise ValueError(f"só {len(lista)} usinas")
    lista.sort(key=lambda u: -u[2])   # as maiores primeiro: as pequenas ficam desenhadas por cima
    observacoes = {u[4]: texto for u in lista for chave, texto in OBS if chave.lower() in u[4].lower()}
    ref = datetime.fromtimestamp(ultimo / 1000, timezone.utc)
    referencia = f"usinas em operação até {MESES[ref.month - 1]}/{ref.year}"
    meta = {"titulo": "Usinas de energia elétrica", "referencia": referencia, "fonte": FONTE, "nivel": "api",
            "atualizado_em": date.today().isoformat(), "consulta": BASE,
            "nota": "geração centralizada; os painéis solares de telhado (geração distribuída) não estão na base",
            "tipos": NOMES, "total_mw": round(sum(u[2] for u in lista) / 1000), "observacoes": observacoes}
    gravar("usinas.json", {"meta": meta, "campos": ["lon", "lat", "kw", "tipo", "nome", "uf", "ano", "dono", "rio_ou_combustivel"], "usinas": lista})
    # soma por estado, para pintar os estados e para a ficha
    por_uf = {}
    for u in lista:
        if not u[5]:
            continue
        v = por_uf.setdefault(u[5], {"valor": 0.0, "usinas": 0, **{t: 0.0 for t in NOMES}})
        v["valor"] += u[2] / 1000
        v[u[3]] += u[2] / 1000
        v["usinas"] += 1
    for u in lista:
        if u[4] in observacoes and u[5] in por_uf:
            por_uf[u[5]].setdefault("obs", []).append(observacoes[u[4]])
    for v in por_uf.values():
        for k in list(v):
            if isinstance(v[k], float):
                v[k] = round(v[k], 1)
    gravar("estados.json", {"titulo": "Potência elétrica instalada", "unidade": "MW", "referencia": referencia, "fonte": FONTE,
                            "nivel": "api", "atualizado_em": date.today().isoformat(), "nota": meta["nota"], "tipos": NOMES,
                            "total_mw": round(sum(v["valor"] for v in por_uf.values())), "valores": por_uf})
    print(f"[energia] {len(lista)} usinas, {meta['total_mw']} MW, {referencia}; {len(por_uf)} estados")


def linhas():
    feats = consultar(9, "Nome,Ano_Opera,Concession,Tensao", {"maxAllowableOffset": "0.003", "geometryPrecision": "3"})
    if len(feats) != contar(9):
        raise ValueError(f"linhas: vieram {len(feats)} de {contar(9)}")
    saida, km, ultimo = [], 0.0, 0
    for f in feats:
        p, g = f.get("properties") or {}, f.get("geometry")
        if not g or g.get("type") not in ("LineString", "MultiLineString") or not p.get("Tensao"):
            continue
        props = {"kv": int(p["Tensao"]), "n": " ".join((p.get("Nome") or "").split())}
        if p.get("Ano_Opera"):
            props["ano"] = p["Ano_Opera"]
            ultimo = max(ultimo, p["Ano_Opera"])
        if p.get("Concession"):
            props["c"] = " ".join(p["Concession"].split())
        saida.append({"type": "Feature", "properties": props, "geometry": g})
    if len(saida) < 1000:
        raise ValueError(f"só {len(saida)} linhas")
    meta = {"titulo": "Linhas de transmissão", "referencia": f"linhas em operação até {ultimo}", "fonte": FONTE, "nivel": "api",
            "atualizado_em": date.today().isoformat(), "consulta": BASE + "/9", "simplificacao": "~300 m (pedido ao próprio serviço da EPE)"}
    gravar("linhas.json", {"type": "FeatureCollection", "meta": meta, "features": saida})
    print(f"[energia] {len(saida)} linhas de transmissão")


if __name__ == "__main__":
    passos = {}
    for nome, f in (("usinas", usinas), ("linhas", linhas)):
        try:
            f()
            passos[nome] = "ok"
        except Exception as e:
            print(f"[energia] {nome} falhou, mantendo o arquivo anterior: {e}")
            passos[nome] = f"falhou (ficou o arquivo anterior): {str(e)[:120]}"
    gravar("robo.json", {"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "passos": passos})
    sys.exit(0 if any(v == "ok" for v in passos.values()) else 1)
