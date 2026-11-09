"""Verificador do acervo: impede que um pacote publicado seja apagado ou sobrescrito.

Uso:
    python scripts/acervo/verificar.py                  confere só a integridade de site/acervo/ (ficha × arquivos)
    python scripts/acervo/verificar.py --git HEAD~1     e também que nada do acervo daquele commit foi mudado ou apagado
    python scripts/acervo/verificar.py --publicado      e também contra o que está no ar (endereço em
                                                        scripts/dados/endereco_do_site.txt + "acervo/")
Sai com erro (código 1) se achar qualquer problema; no GitHub, isso barra a publicação.

O que é permitido mudar num pacote publicado: nada nos dados. A ficha (datapackage.json) só pode trocar a situação
de "preliminar" para "consolidado" (e ganhar a data da consolidação). Se a fonte mudar um número, o pacote inteiro vai
para <período>/versoes/vN/, sem mudar um byte, e a versão nova entra no lugar: o verificador confere que a versão
antiga está lá, idêntica. conjunto.json, serie_uf.csv, indice.json e municipios.csv são índices refeitos a cada
execução e podem mudar. Só usa a biblioteca padrão.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ACERVO = RAIZ / "site" / "acervo"
PERIODO = re.compile(r"\d{4}(-T[1-4])?")


def sha(b):
    return "sha256:" + hashlib.sha256(b).hexdigest()


def ler_json(b):
    return json.loads(b.decode("utf-8"))


# ---------- integridade local ----------

def conferir_pacote(pasta, entrada, onde, erros, permitidos):
    ficha = pasta / "datapackage.json"
    if not ficha.exists():
        erros.append(f"{onde}: falta datapackage.json")
        return
    b = ficha.read_bytes()
    if entrada is not None and sha(b) != entrada["hash"]:
        erros.append(f"{onde}: datapackage.json não bate com o conjunto.json")
    f = ler_json(b)
    if entrada is not None and (f.get("versao") != entrada["versao"]):
        erros.append(f"{onde}: versão da ficha ({f.get('versao')}) × conjunto.json ({entrada['versao']})")
    nomes = {"datapackage.json"} | set(permitidos)
    for r in f.get("resources", []):
        arq = pasta / r["path"]
        nomes.add(r["path"])
        if not arq.exists():
            erros.append(f"{onde}: falta {r['path']}")
            continue
        rb = arq.read_bytes()
        if len(rb) != r["bytes"] or sha(rb) != r["hash"]:
            erros.append(f"{onde}: {r['path']} não é o arquivo descrito na ficha (tamanho ou hash)")
    sobra = sorted(x.name for x in pasta.iterdir() if x.name not in nomes)
    if sobra:
        erros.append(f"{onde}: arquivos fora da ficha: {', '.join(sobra)}")


def integridade():
    erros = []
    if not ACERVO.exists():
        return erros, {}
    indice = ACERVO / "indice.json"
    if not indice.exists():
        return [f"falta {indice.relative_to(RAIZ)}"], {}
    ids = [c["id"] for c in ler_json(indice.read_bytes())["conjuntos"]]
    pastas = sorted(p.parent.name for p in ACERVO.glob("*/conjunto.json"))
    if sorted(ids) != pastas:
        erros.append(f"indice.json lista {sorted(ids)}, mas as pastas com conjunto.json são {pastas}")
    if not (ACERVO / "municipios.csv").exists():
        erros.append("falta municipios.csv")
    locais = {}
    for cid in pastas:
        base = ACERVO / cid
        conj = ler_json((base / "conjunto.json").read_bytes())
        locais[cid] = conj
        listados = {p["periodo"]: p for p in conj["pacotes"]}
        no_disco = {d.name for d in base.iterdir() if d.is_dir()}
        estranhas = sorted(d for d in no_disco if not PERIODO.fullmatch(d))
        if estranhas:
            erros.append(f"{cid}: pastas que não são período: {', '.join(estranhas)}")
        no_disco = {d for d in no_disco if PERIODO.fullmatch(d)}
        if set(listados) != no_disco:
            erros.append(f"{cid}: conjunto.json × pastas: faltam {sorted(no_disco - set(listados))}, "
                         f"sobram {sorted(set(listados) - no_disco)}")
        for p, e in listados.items():
            pasta = base / p
            if not pasta.exists():
                continue
            conferir_pacote(pasta, e, f"{cid}/{p}", erros, ["versoes"] if e["versoes_antigas"] else [])
            antigas = {a["versao"]: a for a in e["versoes_antigas"]}
            if sorted(antigas) != list(range(1, e["versao"])):
                erros.append(f"{cid}/{p}: versão {e['versao']}, mas as antigas listadas são {sorted(antigas)}")
            vs = pasta / "versoes"
            no_disco_v = sorted(x.name for x in vs.iterdir()) if vs.exists() else []
            if no_disco_v != sorted(f"v{k}" for k in antigas):
                erros.append(f"{cid}/{p}: pastas de versão {no_disco_v} × listadas {sorted(antigas)}")
            for k, a in antigas.items():
                if (vs / f"v{k}").exists():
                    conferir_pacote(vs / f"v{k}", a, f"{cid}/{p}/versoes/v{k}", erros, [])
    return erros, locais


# ---------- comparação com o que já foi publicado ----------

class Git:
    def __init__(self, rev):
        self.rev = rev
        r = subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "--verify", rev + "^{commit}"], capture_output=True)
        if r.returncode:
            raise SystemExit(f"não achei o commit {rev} (no GitHub, o checkout precisa de fetch-depth: 2)")

    def __str__(self):
        return f"commit {self.rev}"

    def get(self, caminho):
        r = subprocess.run(["git", "-C", str(RAIZ), "show", f"{self.rev}:site/acervo/{caminho}"], capture_output=True)
        return r.stdout if r.returncode == 0 else None


class Publicado:
    def __init__(self, base):
        self.base = base if base.endswith("/") else base + "/"
        self.marca = str(int(time.time()))   # fura o cache do GitHub Pages (10 min)

    def __str__(self):
        return f"site no ar ({self.base})"

    def get(self, caminho):
        for i in range(4):
            try:
                req = urllib.request.Request(f"{self.base}{caminho}?v={self.marca}",
                                             headers={"User-Agent": "brasil-em-camadas (verificador do acervo)"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                erro = e
            except Exception as e:
                erro = e
            time.sleep(5 * (i + 1))
        raise SystemExit(f"não consegui ler {self.base}{caminho}: {erro}")


def so_consolidou(antes, depois):
    """A única mudança permitida numa ficha publicada: preliminar → consolidado (com a data)."""
    a, d = ler_json(antes), ler_json(depois)
    if a.get("situacao") != "preliminar" or d.get("situacao") != "consolidado":
        return False
    for x in (a, d):
        x.pop("situacao", None)
        x.pop("consolidado_em", None)
    return a == d


def comparar(ref, locais):
    erros = []
    bi = ref.get("indice.json")
    if bi is None:
        return erros, 0
    n = 0
    for c in ler_json(bi)["conjuntos"]:
        cid = c["id"]
        bc = ref.get(f"{cid}/conjunto.json")
        if bc is None:
            erros.append(f"{ref}: {cid} está no indice.json, mas falta o conjunto.json")
            continue
        if cid not in locais:
            erros.append(f"o conjunto {cid}, publicado, sumiu")
            continue
        loc = {p["periodo"]: p for p in locais[cid]["pacotes"]}
        for p in ler_json(bc)["pacotes"]:
            n += 1
            onde, e = f"{cid}/{p['periodo']}", loc.get(p["periodo"])
            if e is None:
                erros.append(f"{onde}: pacote publicado sumiu")
                continue
            if e["versao"] < p["versao"]:
                erros.append(f"{onde}: a versão voltou de {p['versao']} para {e['versao']}")
                continue
            if e["versao"] == p["versao"]:
                atual = e["hash"]
            else:
                velha = next((a for a in e["versoes_antigas"] if a["versao"] == p["versao"]), None)
                if velha is None:
                    erros.append(f"{onde}: a versão {p['versao']}, publicada, não está em versoes/")
                    continue
                atual = velha["hash"]
            if atual != p["hash"]:
                antes = ref.get(f"{cid}/{p['ficha']}")
                caminho = e["ficha"] if e["versao"] == p["versao"] else velha["ficha"]
                depois = (ACERVO / cid / caminho).read_bytes()
                if antes is None or not so_consolidou(antes, depois):
                    erros.append(f"{onde}: a versão {p['versao']}, publicada, foi mudada")
            for a in p["versoes_antigas"]:
                la = next((x for x in e["versoes_antigas"] if x["versao"] == a["versao"]), None)
                if la is None or la["hash"] != a["hash"]:
                    erros.append(f"{onde}: a versão antiga {a['versao']} sumiu ou foi mudada")
    return erros, n


def endereco():
    for l in (RAIZ / "scripts" / "dados" / "endereco_do_site.txt").read_text(encoding="utf-8").splitlines():
        l = l.strip()
        if l and not l.startswith("#"):
            return l.rstrip("/") + "/acervo/"
    raise SystemExit("endereço do site não encontrado")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--git", action="append", default=[], help="commit a comparar (pode repetir)")
    ap.add_argument("--publicado", nargs="?", const="", default=None, help="comparar com o site no ar (endereço opcional)")
    a = ap.parse_args()
    erros, locais = integridade()
    refs = [Git(r) for r in a.git]
    if a.publicado is not None:
        refs.append(Publicado(a.publicado or endereco()))
    resumo = [f"{sum(len(c['pacotes']) for c in locais.values())} pacote(s) em {len(locais)} conjunto(s)"]
    for r in refs:
        e, n = comparar(r, locais)
        erros += e
        resumo.append(f"{n} pacote(s) conferidos contra {r}")
    if erros:
        print("[acervo] PROBLEMAS:")
        for e in erros:
            print("  - " + e)
        sys.exit(1)
    print("[acervo] tudo certo: " + "; ".join(resumo))


if __name__ == "__main__":
    main()
