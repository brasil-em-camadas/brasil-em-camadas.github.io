"""Atualiza as linhas de transmissão e as subestações do mapa, do Webmap da EPE.

Desde 22/10/2026 as usinas (e a soma de cada estado) vêm do SIGA, o cadastro de geração da ANEEL, que é atualizado todo
dia (scripts/atualizar_aneel.py); a EPE estava em out/2024 e registrava os 14.000 MW de Itaipu inteira.

Fonte: EPE (Empresa de Pesquisa Energética, ligada ao Ministério de Minas e Energia), serviço público de mapas
"Sistema Elétrico Existente": https://gisepeprd2.epe.gov.br/arcgis/rest/services/SMA/Webmap_EPE_Sistema_Eletrico_Existente/MapServer
Camadas usadas: 8 subestações e 9 linhas de transmissão (as camadas 0 a 7, de usinas, não são mais usadas).

Roda sozinho no GitHub Actions (site.yml), junto com os outros robôs, e também à mão:
    python scripts/atualizar_epe.py
Só usa a biblioteca padrão. Se a EPE falhar ou responder algo incompleto, os arquivos antigos ficam.
Saídas em site/data/energia/: linhas.json, subestacoes.json e robo.json (resultado de cada passo).
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
FONTE = "EPE, Webmap (sistema elétrico existente)"


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


def subestacoes():
    feats = consultar(8, "Nome,Ano_Opera,Tensao,Concession")
    if len(feats) != contar(8):
        raise ValueError(f"subestações: vieram {len(feats)} de {contar(8)}")
    saida = []
    for f in feats:
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        tensoes = " ".join((p.get("Tensao") or "").split())
        kvs = [int(x) for x in tensoes.replace(",", "/").split("/") if x.strip().isdigit()]
        props = {"n": " ".join((p.get("Nome") or "").split()), "t": tensoes, "kv": max(kvs) if kvs else 0}
        ano = (p.get("Ano_Opera") or "").strip()
        if ano.isdigit():
            props["ano"] = int(ano)
        agente = " ".join((p.get("Concession") or "").split())
        if agente and agente != "-":
            props["c"] = agente
        x, y = g["coordinates"][:2]
        saida.append({"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [round(x, 4), round(y, 4)]}})
    if len(saida) < 500:
        raise ValueError(f"só {len(saida)} subestações")
    saida.sort(key=lambda f: f["properties"]["kv"])   # as de tensão mais alta por último: ficam por cima
    meta = {"titulo": "Subestações", "fonte": FONTE, "nivel": "api", "atualizado_em": date.today().isoformat(), "consulta": BASE + "/8",
            "nota": "subestações do sistema existente na base da EPE; tensão em kV (várias = os níveis de tensão da subestação)", "subestacoes": len(saida)}
    gravar("subestacoes.json", {"type": "FeatureCollection", "meta": meta, "features": saida})
    print(f"[energia] {len(saida)} subestações")


if __name__ == "__main__":
    passos = {}
    for nome, f in (("linhas", linhas), ("subestacoes", subestacoes)):
        try:
            f()
            passos[nome] = "ok"
        except Exception as e:
            print(f"[energia] {nome} falhou, mantendo o arquivo anterior: {e}")
            passos[nome] = f"falhou (ficou o arquivo anterior): {str(e)[:120]}"
    gravar("robo.json", {"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "passos": passos})
    sys.exit(0 if any(v == "ok" for v in passos.values()) else 1)
