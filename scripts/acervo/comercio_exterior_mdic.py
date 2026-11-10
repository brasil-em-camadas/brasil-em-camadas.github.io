"""Acervo: comércio exterior do Brasil (Comex Stat, MDIC/SECEX). Exportações e importações de bens por país, no Brasil
e em cada estado. Um pacote por ano fechado e um por trimestre (nos anos fechados também, para comparar o mesmo trecho).

Uso:
    python scripts/acervo/comercio_exterior_mdic.py           todo mês (GitHub): períodos novos e conferência dos preliminares
    python scripts/acervo/comercio_exterior_mdic.py --tudo    carga inicial: todos os anos desde 1997
    --bruto PASTA      guarda (e reaproveita) as respostas da API nessa pasta
    --anos 2024,2025   só esses anos

Fonte: API do Comex Stat (api-comexstat.mdic.gov.br), mês a mês desde jan/1997. A soma de meses é exata (conferido:
a soma dos 12 meses de 2025 dá o mesmo total, em dólares, da consulta anual). Só usa a biblioteca padrão.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import comum as C  # noqa: E402
import comex_api as A  # noqa: E402

DESDE = 1997

CFG = {
    "id": "comercio-exterior-mdic",
    "titulo": "Comércio exterior (Comex Stat, MDIC)",
    "descricao": ("Exportações e importações de bens do Brasil e de cada estado, por país de destino ou de origem: valor "
                  "em dólares (US$ FOB) e peso líquido, por ano e por trimestre, desde 1997."),
    "fonte": {"orgao": "MDIC", "orgao_nome": "Ministério do Desenvolvimento, Indústria, Comércio e Serviços (MDIC), "
                                            "Secretaria de Comércio Exterior (SECEX)",
              "orgao_site": "https://www.gov.br/mdic/",
              "titulo": "MDIC/SECEX, Comex Stat (estatísticas do comércio exterior brasileiro de bens)",
              "consulta": A.API + "/general", "catalogo": "https://comexstat.mdic.gov.br/",
              "licenca": "dados abertos publicados pelo MDIC; a licença não está escrita no Comex Stat (citar a fonte: "
                         "MDIC/SECEX, Comex Stat)"},
    "nivel": "Oficial · API",
    "palavras_chave": ["comércio exterior", "exportação", "importação", "balança comercial", "Comex Stat", "MDIC",
                       "SECEX", "países", "destinos", "origens", "estados", "dólares", "série histórica", "dados abertos"],
    "periodicidade": "mensal na fonte; o acervo guarda anos e trimestres",
    "medida": "fluxo: o que foi exportado ou importado no período",
    "como_vira_ano": "o trimestre é a soma dos 3 meses, e o ano é a soma dos 12 (a soma é exata)",
    "niveis": {"brasil": "Brasil", "uf": "estados (estado de origem do produto na exportação e de destino na importação)"},
    "atraso_meses": 1,
    "serie_filtro": {"pais": "total"},   # serie_uf.csv só com o total de cada estado (os países ficam nos pacotes)   # o mês sai no começo do mês seguinte
    "metodo": ("Números do Comex Stat como o MDIC publica na API, mês a mês, somados por trimestre e por ano pelo projeto. "
               "Valor FOB em dólares americanos (o valor da mercadoria posta a bordo, sem frete e seguro internacionais), no "
               "valor de cada mês, sem converter para reais e sem descontar a inflação; peso líquido em quilos. O estado é a "
               "\"UF do produto\" do Comex Stat: na exportação, o estado de origem da mercadoria; na importação, o estado de "
               "destino (não é o endereço da empresa que fez a operação). O total do Brasil vem da própria API (consulta "
               "sem estado) e inclui o que não tem estado: não declarado, consumo de bordo, café de estados diversos, "
               "reexportação e outros. Uma linha por lugar e país, e a linha 'total' com todos os países."),
    "avisos": [
        "Só bens (mercadorias); serviços, turismo e investimentos não entram.",
        "Um país que não aparece num lugar não teve nada registrado naquele período. Um país com exportação e sem "
        "importação (ou o contrário) tem 0 na outra coluna: zero registrado pela fonte.",
        "País: o código do Comex Stat (coluna pais) e, quando existe, o código ISO 3166 de três letras (pais_iso3). A "
        "lista dos países do período, com os nomes, está na ficha (itens). Países que deixaram de existir (Alemanha "
        "Oriental, Antilhas Holandesas…) e destinos que não são países (provisão de navios e aeronaves, a designar…) "
        "ficam com o código do Comex Stat e sem ISO.",
        "O Comex Stat traz também operações com \"Brasil\" como país de destino ou de origem (código 105) e com a "
        "\"Internação na Zona Franca de Manaus\" (código 100); elas ficam nas tabelas como a fonte publica.",
        "Os números são os da base atual do Comex Stat, que a SECEX revisa: podem diferir dos divulgados na época.",
        "Dólares de cada mês: para comparar anos distantes, o peso é mais firme que o valor, porque o dólar também perde "
        "valor com a inflação e os preços das mercadorias mudam.",
    ],
}


def campos(nivel):
    c = [C.Campo("codigo_ibge", "string", "Código do IBGE", descricao="1 = Brasil; 2 dígitos = estado")]
    if nivel == "uf":
        c.append(C.Campo("uf", "string", "Estado (sigla)"))
    c += [C.Campo("pais", "string", "País (código do Comex Stat)", descricao="'total' = todos os países"),
          C.Campo("pais_iso3", "string", "País (ISO 3166, três letras)", descricao="vazio quando não há código ISO"),
          C.Campo("exportacao_us_fob", "integer", "Exportação, valor", "US$ FOB", "dólares de cada mês, como a fonte publica"),
          C.Campo("exportacao_kg", "integer", "Exportação, peso líquido", "kg"),
          C.Campo("importacao_us_fob", "integer", "Importação, valor", "US$ FOB", "dólares de cada mês, como a fonte publica"),
          C.Campo("importacao_kg", "integer", "Importação, peso líquido", "kg")]
    return c


def ler_ano(ano, ate, bruto):
    """Respostas da API de um ano: {(fluxo, nível): linhas}."""
    out = {}
    for fl in ("export", "import"):
        for por in (True, False):
            nome = f"{fl}_{'uf' if por else 'br'}_{ano}.json.gz"
            out[(fl, "uf" if por else "br")], _ = A.consulta(fl, f"{ano}-01", f"{ano}-{ate:02d}", por, bruto, nome)
    return out


def somar(resp, meses, nome_cod, uf_sigla):
    """{nível: {(lugar, código do país): [exp_fob, exp_kg, imp_fob, imp_kg]}} para os meses pedidos; e o que ficou sem
    estado ({sigla especial: [exp_fob, imp_fob]})."""
    tot = {"br": {}, "uf": {}}
    especiais = {}
    desconhecidos = set()
    for (fl, niv), linhas in resp.items():
        k = 0 if fl == "export" else 2
        for l in linhas:
            if int(l["monthNumber"]) not in meses:
                continue
            cod = nome_cod.get(l["country"])
            if cod is None:
                desconhecidos.add(l["country"])
                continue
            fob, kg = A.numero(l.get("metricFOB")), A.numero(l.get("metricKG"))
            if niv == "uf":
                uf = uf_sigla.get(l["state"])
                if uf not in A.UF_IBGE:
                    e = especiais.setdefault(uf or l["state"], [0, 0])
                    e[k // 2] += fob
                    continue
                lugar = uf
            else:
                lugar = "BR"
            v = tot[niv].setdefault((lugar, cod), [0, 0, 0, 0])
            v[k] += fob
            v[k + 1] += kg
    if desconhecidos:
        raise ValueError(f"países sem código na lista do Comex Stat: {sorted(desconhecidos)}")
    return tot, especiais


def linhas_tabela(t, nivel, paises):
    """Uma linha por lugar e país (com a linha 'total' primeiro em cada lugar)."""
    por_lugar = {}
    for (lugar, cod), v in t.items():
        if any(v):
            por_lugar.setdefault(lugar, {})[cod] = v
    saida = []
    lugares = ["BR"] if nivel == "brasil" else sorted(A.UF_IBGE, key=lambda s: A.UF_IBGE[s])
    for lugar in lugares:
        ps = por_lugar.get(lugar, {})
        total = [sum(v[i] for v in ps.values()) for i in range(4)]
        base = [C.CODIGO_BRASIL] if nivel == "brasil" else [A.UF_IBGE[lugar], lugar]
        saida.append(base + ["total", ""] + total)
        for cod in sorted(ps):
            saida.append(base + [cod, paises[cod]["iso3"]] + ps[cod])
    return saida


def itens_do_periodo(t, paises):
    cods = sorted({cod for (_, cod), v in t.items() if any(v)})
    return [{"pais": c, "nome": paises[c]["nome"], "pais_iso3": paises[c]["iso3"]} for c in cods]


def avisos_do_periodo(tbr, tuf, especiais):
    out = []
    eb = sum(v[0] for v in tbr.values())
    ib = sum(v[2] for v in tbr.values())
    eu = sum(v[0] for v in tuf.values())
    iu = sum(v[2] for v in tuf.values())
    nomes = {"ND": "não declarada", "CB": "consumo de bordo", "ED": "estados diversos (café)", "EX": "exterior",
             "MN": "mercadoria nacionalizada", "RE": "reexportação", "ZN": "zona não declarada"}
    for txt, b, u, i in (("exportações", eb, eu, 0), ("importações", ib, iu, 1)):
        if b and b != u:
            partes = sorted(((v[i], k) for k, v in especiais.items() if v[i]), reverse=True)
            det = "; ".join(f"{nomes.get(k, k)}: US$ {C.br(v)}" for v, k in partes[:5])
            out.append(f"{txt.capitalize()}: os estados somam US$ {C.br(u)}, {f"{100 * u / b:.1f}".replace(".", ",")}% do total do Brasil "
                       f"(US$ {C.br(b)}); o resto não tem estado na fonte ({det}).")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tudo", action="store_true", help="todos os anos (carga inicial)")
    ap.add_argument("--anos", help="só estes anos, separados por vírgula")
    ap.add_argument("--bruto", help="pasta para guardar e reaproveitar as respostas da API")
    a = ap.parse_args()
    dia = C.hoje().isoformat()
    at = A.atualizado()
    ult_ano, ult_mes = int(at["year"]), int(at["monthNumber"])
    arq = C.pasta_conjunto(CFG) / "conjunto.json"
    import json
    velho = (json.loads(arq.read_text(encoding="utf-8")).get("estado_da_fonte") or {}) if arq.exists() else {}
    estado = {"atualizado_em": at["updated"], "ultimo_mes": f"{ult_ano}-{ult_mes:02d}"}
    paises = A.tabela_paises(atualizar=True)
    nome_cod = {p["nome"]: c for c, p in paises.items()}
    uf_sigla = {u["text"]: u["uf"] for u in A.ufs()}
    existentes = set(C.pacotes(CFG))
    if a.anos:
        anos = [int(x) for x in a.anos.split(",")]
    elif a.tudo:
        anos = list(range(DESDE, ult_ano + 1))
    elif velho.get("atualizado_em") == at["updated"] and existentes:
        anos = []   # a base não mudou desde a última conferência
    else:
        prelim = {C.periodo(p)["ano"] for p in existentes if C.ficha_atual(CFG, p)["situacao"] == "preliminar"}
        faltam = {ano for ano in range(DESDE, ult_ano + 1) if str(ano) not in existentes and ano < ult_ano}
        anos = sorted(prelim | faltam | {ult_ano})
    print(f"[acervo/comex] base de {at['updated']}, até {ult_mes:02d}/{ult_ano}; anos a conferir: {anos}")
    resultados = {}
    for ano in anos:
        ate = 12 if ano < ult_ano else ult_mes
        resp = ler_ano(ano, ate, a.bruto)
        periodos = [(f"{ano}-T{t}", [3 * t - 2, 3 * t - 1, 3 * t]) for t in range(1, 5) if 3 * t <= ate]
        if ate == 12:
            periodos.append((str(ano), list(range(1, 13))))
        for p, meses in periodos:
            tot, esp = somar(resp, set(meses), nome_cod, uf_sigla)
            tabelas = {"brasil": (campos("brasil"), linhas_tabela(tot["br"], "brasil", paises)),
                       "uf": (campos("uf"), linhas_tabela(tot["uf"], "uf", paises))}
            extra = {"coletado_em": dia,
                     "consulta": f"{A.API}/general (fluxos export e import, de {ano}-{meses[0]:02d} a {ano}-{meses[-1]:02d}, "
                                 f"detalhes country e state, métricas metricFOB e metricKG)",
                     "itens": itens_do_periodo(tot["br"], paises),
                     "avisos": avisos_do_periodo(tot["br"], tot["uf"], esp)}
            resultados[p] = C.gravar_pacote(CFG, p, tabelas, extra)
    cons = C.consolidar(CFG)
    if cons:
        resultados.update({p: "consolidado agora" for p in cons})
    C.atualizar_conjunto(CFG, conferido_em=dia, estado=estado)
    C.registrar(CFG, resultados)


if __name__ == "__main__":
    main()
