"""Robô do comércio exterior (Comex Stat, MDIC/SECEX) para o mapa: os 12 meses mais recentes.

Grava:
  site/data/comex/estados.json   exportações e importações de cada estado (pintura e ficha), com os principais
                                 destinos e origens, e o total do Brasil (balança comercial)
  site/data/comex/paises.json    o que cada país compra do Brasil e vende ao Brasil, no total e por estado
                                 (pintura dos países no globo); baixado só quando a camada é ligada
  site/data/comex/robo.json      registro da execução
Se a API falhar, os arquivos antigos ficam (e o registro diz que falhou).
Opção --bruto PASTA: guarda e reaproveita as respostas da API. Só usa a biblioteca padrão.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comex_api as A  # noqa: E402

PASTA = A.RAIZ / "site" / "data" / "comex"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
FONTE = "MDIC/SECEX, Comex Stat (estatísticas do comércio exterior brasileiro de bens)"
CATALOGO = "https://comexstat.mdic.gov.br/"
NOTA = ("valor FOB em dólares (a mercadoria posta a bordo, sem frete e seguro internacionais), soma dos 12 meses mais "
        "recentes; só bens, sem serviços. Estado = \"UF do produto\" do Comex Stat: na exportação, o estado de origem da "
        "mercadoria; na importação, o estado de destino (não é o endereço da empresa)")


def gravar(nome, d):
    PASTA.mkdir(parents=True, exist_ok=True)
    tmp = PASTA / (nome + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(PASTA / nome)


def pais_de_verdade(c, paises):
    """Com código ISO e fora o próprio Brasil (o Comex Stat traz também operações com "Brasil" como país)."""
    return paises[c]["iso3"] not in ("", "BRA")


def principais(d, k, n=5):
    """Os n países com mais valor na posição k ([exp, imp]): [[código, valor], ...]."""
    return [[c, v[k]] for c, v in sorted(d.items(), key=lambda x: -x[1][k]) if v[k] > 0][:n]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bruto", help="pasta para guardar e reaproveitar as respostas da API")
    a = ap.parse_args()
    agora = datetime.now(timezone.utc)
    registro = {"rodou_em": agora.strftime("%Y-%m-%dT%H:%M:%SZ"), "passos": {}}
    try:
        at = A.atualizado()
        ano, mes = int(at["year"]), int(at["monthNumber"])
        a0, m0 = (ano, mes - 11) if mes == 12 else (ano - 1, mes + 1)
        de, ate = f"{a0}-{m0:02d}", f"{ano}-{mes:02d}"
        ref = f"{MESES[m0 - 1]}/{a0} a {MESES[mes - 1]}/{ano}"
        paises = A.tabela_paises(atualizar=True)
        nome_cod = {p["nome"]: c for c, p in paises.items()}
        uf_sigla = {u["text"]: u["uf"] for u in A.ufs()}
        br, uf, sem_estado = {}, {}, {"exp": 0, "imp": 0}
        kg = {"exp": 0, "imp": 0}
        consultas = []
        for fl, k in (("export", 0), ("import", 1)):
            for por in (False, True):
                nome = f"mapa_{fl}_{'uf' if por else 'br'}_{de}_{ate}.json.gz"
                linhas, corpo = A.consulta(fl, de, ate, por, a.bruto, nome)
                consultas.append(corpo)
                meses = {(l["year"], l["monthNumber"]) for l in linhas}
                if len(meses) != 12:
                    raise ValueError(f"{fl}: a resposta tem {len(meses)} meses, não 12")
                for l in linhas:
                    cod = nome_cod.get(l["country"])
                    if cod is None:
                        raise ValueError(f"país sem código na lista do Comex Stat: {l['country']}")
                    v = A.numero(l["metricFOB"])
                    if not por:
                        br.setdefault(cod, [0, 0])[k] += v
                        kg["exp" if k == 0 else "imp"] += A.numero(l["metricKG"])
                        continue
                    s = uf_sigla.get(l["state"])
                    if s not in A.UF_IBGE:
                        sem_estado["exp" if k == 0 else "imp"] += v
                        continue
                    uf.setdefault(s, {}).setdefault(cod, [0, 0])[k] += v
        ex_br = sum(v[0] for v in br.values())
        im_br = sum(v[1] for v in br.values())
        # sem estado = total do Brasil (consulta sem estado) menos a soma dos 27 estados
        sem_estado = {"exp": ex_br - sum(v[0] for d in uf.values() for v in d.values()),
                      "imp": im_br - sum(v[1] for d in uf.values() for v in d.values())}
        meta = {"fonte": FONTE, "referencia": ref, "de": de, "ate": ate, "nivel": "api", "unidade": "US$ FOB",
                "atualizado_em": agora.date().isoformat(), "base_atualizada_em": at["updated"],
                "consulta": A.API + "/general", "catalogo": CATALOGO, "nota": NOTA}
        nomes = {c: paises[c]["nome"] for c in set(br) | {c for d in uf.values() for c in d}}
        valores = {}
        for s in sorted(A.UF_IBGE, key=lambda x: A.UF_IBGE[x]):
            d = uf.get(s, {})
            x, i = sum(v[0] for v in d.values()), sum(v[1] for v in d.values())
            valores[s] = {"valor": x, "imp": i, "saldo": x - i,
                          "destinos": principais(d, 0), "origens": principais(d, 1),
                          "n_destinos": sum(1 for c, v in d.items() if v[0] > 0 and pais_de_verdade(c, paises))}
        estados = {"titulo": "Exportações", "unidade": "US$ FOB", "referencia": ref, "fonte": FONTE,
                   "nota": NOTA, "nivel": "api", "atualizado_em": meta["atualizado_em"],
                   "base_atualizada_em": at["updated"], "consulta": A.API + "/general", "catalogo": CATALOGO,
                   "campos": {"valor": "exportações (US$ FOB)", "imp": "importações (US$ FOB)",
                              "saldo": "exportações menos importações", "destinos": "5 maiores destinos [país, US$]",
                              "origens": "5 maiores origens das importações [país, US$]",
                              "n_destinos": "países que compraram do estado"},
                   "brasil": {"valor": ex_br, "imp": im_br, "saldo": ex_br - im_br, "exp_kg": kg["exp"],
                              "imp_kg": kg["imp"], "destinos": principais(br, 0), "origens": principais(br, 1),
                              "n_destinos": sum(1 for c, v in br.items() if v[0] > 0 and pais_de_verdade(c, paises)),
                              "sem_estado": sem_estado},
                   "paises": {c: [nomes[c], paises[c]["iso3"]] for c in sorted(nomes)},
                   "valores": valores}
        gravar("estados.json", estados)
        registro["passos"]["estados.json"] = "ok"
        mundo = {**meta, "campos": {"paises": "código do Comex Stat → [nome, ISO3, exportação, importação]",
                                     "por_uf": "estado → código → [exportação, importação]"},
                 "paises": {c: [paises[c]["nome"], paises[c]["iso3"], v[0], v[1]] for c, v in sorted(br.items())},
                 "por_uf": {s: {c: v for c, v in sorted(d.items())} for s, d in sorted(uf.items())}}
        gravar("paises.json", mundo)
        registro["passos"]["paises.json"] = "ok"
        print(f"[comex] {ref}: exportações US$ {ex_br / 1e9:.1f} bi, importações US$ {im_br / 1e9:.1f} bi, "
              f"{len(br)} países; sem estado: US$ {sem_estado['exp'] / 1e9:.2f} bi (exp.), {sem_estado['imp'] / 1e9:.2f} bi (imp.)")
    except Exception as e:
        print(f"[comex] falhou: {e}")
        for n in ("estados.json", "paises.json"):
            registro["passos"].setdefault(n, "falhou (ficou o arquivo anterior)")
    gravar("robo.json", registro)


if __name__ == "__main__":
    main()
