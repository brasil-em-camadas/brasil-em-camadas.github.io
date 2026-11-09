"""Acervo: lavouras do IBGE (Produção Agrícola Municipal, PAM, tabela 5457 da SIDRA). Um pacote por ano.

Uso:
    python scripts/acervo/lavouras_ibge.py                 todo mês (GitHub): ano novo da PAM e conferência dos preliminares
    python scripts/acervo/lavouras_ibge.py --tudo          carga inicial: todos os anos (Brasil e estados desde 1974,
                                                           municípios desde 2010)
    --bruto PASTA   guarda (e reaproveita) as respostas da SIDRA nessa pasta
    --anos 2024,2025   só esses anos

Fonte: apisidra.ibge.gov.br (a API de valores da SIDRA). A API de agregados (servicodados.ibge.gov.br), que o robô do
mapa usa, não abre daqui desde 06/11/2026 e falhou no GitHub em 03/11/2026; a SIDRA abre dos dois lugares.
Uma consulta aceita até 100 mil valores: por município, vai uma variável e 17 lavouras de cada vez.
Só usa a biblioteca padrão.
"""
import argparse
import gzip
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402

SIDRA = "https://apisidra.ibge.gov.br/values"
AGENTE = {"User-Agent": "brasil-em-camadas (dados abertos)", "Accept-Encoding": "gzip"}
VARIAVEIS = {"8331": "area_plantada_ha", "216": "area_colhida_ha", "214": "quantidade", "112": "rendimento",
             "215": "valor_mil_reais"}
DESDE_MUNICIPIO = 2010
DESDE_VALOR = 1994      # Plano Real: valores em dinheiro só a partir daqui (antes, moedas antigas)
DESDE_AREA_PLANTADA = 1988

CFG = {
    "id": "lavouras-ibge",
    "titulo": "Lavouras (IBGE, Produção Agrícola Municipal)",
    "descricao": ("Área plantada e colhida, quantidade produzida, rendimento médio e valor da produção de cada lavoura "
                  "temporária e permanente, no Brasil, em cada estado e (desde 2010) em cada município, por ano."),
    "fonte": {"orgao": "IBGE", "orgao_nome": "Instituto Brasileiro de Geografia e Estatística (IBGE)",
              "orgao_site": "https://www.ibge.gov.br/",
              "titulo": "IBGE, Produção Agrícola Municipal (PAM), tabela 5457 da SIDRA",
              "consulta": SIDRA + "/t/5457", "catalogo": "https://sidra.ibge.gov.br/tabela/5457",
              "licenca": "uso livre, desde que citada a fonte (IBGE)"},
    "nivel": "Oficial · API",
    # palavras para a busca (página do conjunto e ficha schema.org Dataset)
    "palavras_chave": ["agricultura", "produção agrícola", "lavouras", "PAM", "IBGE", "soja", "milho", "cana-de-açúcar",
                       "café", "área plantada", "área colhida", "rendimento", "valor da produção", "estados",
                       "municípios", "série histórica", "dados abertos"],
    "periodicidade": "anual",
    "medida": "fluxo: o que foi plantado, colhido e produzido no ano civil",
    "como_vira_ano": "a PAM já é anual (ano civil); não há trimestres",
    "niveis": {"brasil": "Brasil", "uf": "estados", "municipio": "municípios (desde 2010)"},
    "atraso_meses": 9,   # a PAM de um ano sai por volta de setembro do ano seguinte
    "metodo": ("Números da PAM como o IBGE publica na tabela 5457 (uma linha por lugar e lavoura). O IBGE levanta os dados "
               "em cada município com entidades públicas e privadas, produtores e técnicos (não é medição no campo nem "
               "estimativa do site). O total do Brasil vem da própria SIDRA, não da soma dos estados."),
    "avisos": [
        "Uma lavoura que não aparece num lugar teve zero registrado pela fonte naquele ano. A lista das lavouras "
        "pesquisadas no ano está na ficha (itens); fora dela, a lavoura não foi pesquisada.",
        "A linha 'total' traz a soma do IBGE para todas as lavouras (área e valor); quantidade e rendimento não se somam "
        "entre produtos diferentes ('..', não se aplica).",
        "Café arábica e café canephora (desde 2012) são partes do café; não somar com a linha 'cafe'.",
        "Rendimento: quilos por hectare; nas lavouras contadas em mil frutos (ou mil cachos), frutos (ou cachos) por hectare.",
        "Ausência na base não significa ausência real: a PAM registra o que o IBGE levantou em cada município.",
        # achado em 09/11/2026 ao comparar períodos no mapa: a SIDRA chama a lavoura de "Café (em grão) Total" em todos
        # os anos, mas as publicações da PAM dizem "Café (em coco)" (1982, 1992) e "Café (beneficiado)" (2002), e o
        # rendimento do Brasil cai à metade de 2001 (1.557 kg/ha) para 2002 (1.101), sem quebra de safra
        "Café: até 2001, a quantidade é de café em coco (o fruto seco, com a casca); desde 2002, de café beneficiado "
        "(em grão, sem a casca), que pesa cerca de metade. A SIDRA usa o mesmo nome nos dois casos. As quantidades e "
        "os rendimentos de antes e de depois de 2002 não se comparam.",
    ],
    # quebras na série: o mapa não compara um período de antes com um de depois (valem para estas colunas e lavouras)
    "quebras": [
        {"desde": "2002", "colunas": ["quantidade", "rendimento"], "filtro": {"lavoura": "cafe"},
         "aviso": "Café: até 2001, café em coco (com a casca); desde 2002, café beneficiado (em grão), que pesa cerca de "
                  "metade. As quantidades de antes e de depois de 2002 não se comparam."},
    ],
}

# lavoura (código do IBGE na classificação 782) → nome curto usado no acervo (fica fixo mesmo se o IBGE mudar o nome)
LAVOURA = {
    "0": "total", "40129": "abacate", "40092": "abacaxi", "83388": "abobora", "45982": "acai", "83399": "acerola",
    "40329": "alfafa_fenada", "83389": "alface", "40130": "algodao_arboreo", "40099": "algodao_herbaceo", "40100": "alho",
    "40101": "amendoim", "40102": "arroz", "40103": "aveia", "40131": "azeitona", "40136": "banana",
    "40104": "batata_doce", "40105": "batata_inglesa", "40137": "borracha_latex_coagulado",
    "40468": "borracha_latex_liquido", "40138": "cacau", "40139": "cafe", "40140": "cafe_arabica",
    "40141": "cafe_canephora", "40330": "caju", "40106": "cana_de_acucar", "40331": "cana_para_forragem",
    "83390": "canola", "40142": "caqui", "40143": "castanha_de_caju", "40107": "cebola", "83391": "cenoura",
    "40108": "centeio", "40109": "cevada", "40144": "cha_da_india", "83392": "chuchu", "40145": "coco_da_baia",
    "83400": "cupuacu", "40146": "dende", "40147": "erva_mate", "40110": "ervilha", "40111": "fava",
    "40112": "feijao", "40148": "figo", "40113": "fumo", "83395": "gergelim", "40114": "girassol", "40149": "goiaba",
    "83401": "graviola", "40150": "guarana", "83393": "inhame", "40115": "juta", "40151": "laranja", "40152": "limao",
    "40116": "linho", "40260": "maca", "40117": "malva", "40261": "mamao", "40118": "mamona", "40119": "mandioca",
    "40262": "manga", "40263": "maracuja", "40264": "marmelo", "40120": "melancia", "40121": "melao",
    "40122": "milho", "83394": "milho_verde", "83396": "morango", "40265": "noz", "40266": "palmito", "40267": "pera",
    "40268": "pessego", "40269": "pimenta_do_reino", "83397": "pimentao", "40123": "rami", "83398": "repolho",
    "40270": "sisal", "40124": "soja", "40125": "sorgo", "40271": "tangerina", "40126": "tomate", "40127": "trigo",
    "40128": "triticale", "40272": "tungue", "40273": "urucum", "40274": "uva",
}
# Unidade da quantidade. A SIDRA diz "Toneladas" para todas, mas o próprio IBGE avisa (nota da tabela e documento
# "Mudança da unidade de medida das frutíferas", sidra.ibge.gov.br/content/documentos/pam/AlteracoesUnidadesMedidaFrutas.pdf):
# abacaxi e coco-da-baía são contados em mil frutos; até 2000, estas 17 frutas também (a banana, em mil cachos).
MIL_FRUTOS_SEMPRE = {"40092", "40145"}
FRUTAS_ATE_2000 = {"40129", "40136", "40142", "40148", "40149", "40151", "40152", "40260", "40261", "40262", "40263",
                   "40264", "40120", "40121", "40267", "40268", "40271"}
CAJU = "40330"   # pesquisado até 1987; contado em frutos (questionário da PAM de 1985: "a forma de levantamento será o fruto")


ASTERISCO = set()   # lavouras que a SIDRA marca com * (contadas em mil frutos), preenchido pelos nomes da consulta


def nome_curto(nome, usados):
    """Nome curto para uma lavoura nova na PAM: 'Feijão-fradinho (em grão)' → 'feijao_fradinho'."""
    n = unicodedata.normalize("NFKD", nome.replace("*", "")).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\s*\(em gr[aã]o\)", "", n)
    n = re.sub(r"[^a-z0-9]+", "_", n).strip("_")
    base, k = n, 2
    while n in usados:
        n, k = f"{base}_{k}", k + 1
    return n


def unidade(prod, ano):
    if prod == "0":
        return ".."
    if prod in MIL_FRUTOS_SEMPRE or prod == CAJU or prod in ASTERISCO:
        return "mil frutos"
    if prod in FRUTAS_ATE_2000 and ano <= 2000:
        return "mil cachos" if prod == "40136" else "mil frutos"
    return "t"


def campos(nivel, ano):
    c = [C.Campo("codigo_ibge", "string", "Código do IBGE do lugar",
                 descricao={"brasil": "1 = Brasil (como na SIDRA)", "uf": "código do estado (2 dígitos)",
                            "municipio": "código do município (7 dígitos); nome e posição em ../../municipios.csv"}[nivel])]
    if nivel != "brasil":
        c.append(C.Campo("uf", "string", "Sigla do estado"))
    c += [C.Campo("lavoura", "string", "Lavoura (nome curto; a lista com o nome do IBGE está em itens, na ficha)"),
          C.Campo("area_plantada_ha", "integer", "Área plantada ou destinada à colheita", "hectares",
                  "na SIDRA desde 1988; antes, vazio"),
          C.Campo("area_colhida_ha", "integer", "Área colhida", "hectares"),
          C.Campo("quantidade", "integer", "Quantidade produzida", "ver unidade_quantidade"),
          C.Campo("unidade_quantidade", "string", "Unidade da quantidade", None, "t (toneladas), mil frutos ou mil cachos"),
          C.Campo("rendimento", "integer", "Rendimento médio da produção", "kg por hectare (ou frutos/cachos por hectare)",
                  "quilos por hectare; quando a quantidade está em mil frutos (ou mil cachos), frutos (ou cachos) por hectare")]
    if ano >= DESDE_VALOR:
        c.append(C.Campo("valor_mil_reais", "integer", "Valor da produção", "mil reais",
                         "em reais do próprio ano, como a fonte publica (sem descontar a inflação)"))
    return c


# ---------- SIDRA ----------

def pedir(url, bruto=None, nome=None):
    if bruto and nome and (Path(bruto) / nome).exists():
        return json.loads((Path(bruto) / nome).read_bytes())
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers=AGENTE)
            with urllib.request.urlopen(req, timeout=300) as r:
                b = r.read()
            b = gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b
            d = json.loads(b)
            if not isinstance(d, list):
                raise ValueError("resposta inesperada")
            if bruto and nome:
                Path(bruto).mkdir(parents=True, exist_ok=True)
                (Path(bruto) / nome).write_bytes(b)
            return d
        except Exception as e:
            if i == 4:
                raise
            print(f"  [sidra] tentativa {i + 1} falhou ({e}); de novo em {10 * (i + 1)} s")
            time.sleep(10 * (i + 1))


def sem_cabecalho(d):
    return d[1:] if d and d[0].get("NC", "").startswith("Nível") else d


def brasil_todos(bruto):
    """Nível Brasil, todos os anos e lavouras, com os nomes (1 consulta, ~22 mil valores)."""
    url = f"{SIDRA}/t/5457/n1/all/v/{','.join(VARIAVEIS)}/p/all/c782/all?formato=json"
    d = pedir(url, bruto, "n1_todos.json")
    return sem_cabecalho(d), url


def estados(anos, bruto):
    linhas = []
    for k in range(0, len(anos), 8):
        parte = anos[k:k + 8]
        url = f"{SIDRA}/t/5457/n3/all/v/{','.join(VARIAVEIS)}/p/{','.join(map(str, parte))}/c782/all/f/c/h/n?formato=json"
        linhas += sem_cabecalho(pedir(url, bruto, f"n3_{parte[0]}.json" if len(parte) == 8 or parte[0] >= 2022 else f"n3_{parte[0]}_{len(parte)}.json"))
    return linhas


def municipios(ano, prods, bruto):
    linhas = []
    for v in VARIAVEIS:
        for k in range(0, len(prods), 17):
            parte = prods[k:k + 17]
            url = f"{SIDRA}/t/5457/n6/all/v/{v}/p/{ano}/c782/{','.join(parte)}/f/c/h/n?formato=json"
            linhas += sem_cabecalho(pedir(url, bruto, f"n6_{ano}_{v}_p{parte[0]}_{len(parte)}.json"))
    return linhas


def carregar_bruto_municipios(ano, bruto):
    """Respostas já baixadas (qualquer divisão por lavouras): n6_<ano>_*.json."""
    linhas = []
    for f in sorted(Path(bruto).glob(f"n6_{ano}_*.json")):
        linhas += sem_cabecalho(json.loads(f.read_bytes()))
    return linhas


# ---------- montagem das tabelas ----------

def converter(v):
    """Símbolos da SIDRA → marcas do acervo: '-' (zero absoluto) = 0; '...' (não disponível) = vazio;
    '..' (não se aplica) = '..'; 'X' (sigiloso) = 'X'; '0' (positivo arredondado para zero) fica 0, com aviso."""
    if v == "-":
        return 0
    if v == "...":
        return None
    if v in ("..", "X"):
        return v
    return int(v)


def montar(linhas, ano, nivel, pesquisadas, lugares):
    """linhas da SIDRA (com códigos) → linhas do CSV, uma por lugar e lavoura."""
    col_lugar = "D1C"
    val, arred = {}, []
    for l in linhas:
        if l["D3C"] != str(ano):
            continue
        val[(l[col_lugar], l["D4C"], l["D2C"])] = l["V"]
        if l["V"] == "0":
            arred.append((l[col_lugar], LAVOURA.get(l["D4C"], l["D4C"]), VARIAVEIS[l["D2C"]]))
    cps = campos(nivel, ano)
    nomes = [c.nome for c in cps]
    usadas = [v for v, n in VARIAVEIS.items() if n in nomes]
    saida, fora = [], []
    presentes = {k[0] for k in val}
    # A SIDRA não lista o município sem nenhuma informação no ano (nota 1 da tabela 5457): ele entra com tudo vazio.
    ausentes = [l for l in lugares if l not in presentes]
    if nivel != "municipio" and ausentes:
        raise ValueError(f"{nivel}: faltam {ausentes} na resposta da SIDRA ({ano})")
    if len(ausentes) > 100:
        raise ValueError(f"{len(ausentes)} municípios ausentes na resposta da SIDRA ({ano}): resposta incompleta?")
    extras = sorted(presentes - set(lugares))
    for lugar in extras:   # lugar com dado fora da lista (ex.: município antes da data de instalação que temos)
        if any(val.get((lugar, p, v), "...") not in ("...", "..", "-") for p in pesquisadas for v in usadas):
            fora.append(lugar)
    ordem = sorted(pesquisadas, key=lambda p: (p != "0", LAVOURA[p]))
    for lugar in sorted(set(lugares) | set(fora)):
        for p in ordem:
            r = {v: converter(val.get((lugar, p, v), "...")) for v in usadas}
            if p != "0" and all(x in (0, None) for x in r.values()) and any(x == 0 for x in r.values()):
                continue   # lavoura com zero (e nada mais) registrado pela fonte: não entra
            d = {"codigo_ibge": lugar, "lavoura": LAVOURA[p], "unidade_quantidade": unidade(p, ano)}
            if nivel != "brasil":
                d["uf"] = C.UF[lugar[:2]]
            for v, nome in VARIAVEIS.items():
                if nome in nomes:
                    d[nome] = r[v]
            if p == "0":
                d["quantidade"] = d["rendimento"] = ".."
            saida.append(d)
    return cps, saida, arred, fora, ausentes


def conferir_soma(mun, uf, ano):
    """A soma dos municípios tem de bater com o estado (área colhida do total): senão a resposta veio incompleta."""
    soma = {}
    for d in mun:
        if d["lavoura"] == "total" and isinstance(d["area_colhida_ha"], int):
            soma[d["uf"]] = soma.get(d["uf"], 0) + d["area_colhida_ha"]
    for d in uf:
        if d["lavoura"] == "total" and isinstance(d["area_colhida_ha"], int) and d["area_colhida_ha"]:
            s = soma.get(d["uf"], 0)
            if abs(s - d["area_colhida_ha"]) > 0.01 * d["area_colhida_ha"]:
                raise ValueError(f"{ano}, {d['uf']}: soma dos municípios {s} × estado {d['area_colhida_ha']} (área colhida)")


def pesquisadas_no_ano(br_linhas, ano):
    """Lavouras pesquisadas no ano: as que têm alguma área colhida (mesmo zero) no Brasil."""
    return sorted({l["D4C"] for l in br_linhas if l["D3C"] == str(ano) and l["D2C"] == "216" and l["V"] != "..."},
                  key=lambda p: (p != "0", LAVOURA.get(p, p)))


def avisos_do_ano(ano, ps, ps_antes, nomes, arred, fora, br_linhas, uf_linhas):
    a = []
    if ano < DESDE_AREA_PLANTADA:
        a.append(f"Área plantada: a SIDRA só tem desde {DESDE_AREA_PLANTADA} (vazio neste ano).")
    if ano < DESDE_VALOR:
        a.append(f"Valor da produção fora deste pacote: antes de {DESDE_VALOR} a fonte publica em moedas antigas "
                 "(cruzeiro, cruzado…), que não se comparam com o real.")
    if ano <= 2000 and any(p in FRUTAS_ATE_2000 for p in ps):
        a.append("Até 2000, a quantidade de 17 frutas (abacate, banana, caqui, figo, goiaba, laranja, limão, maçã, mamão, "
                 "manga, maracujá, marmelo, melancia, melão, pera, pêssego e tangerina) era contada em mil frutos (a banana, "
                 "em mil cachos); a partir de 2001, em toneladas. Para comparar com 2001 em diante, é preciso converter "
                 "(o IBGE publicou a tabela de conversão: sidra.ibge.gov.br/content/documentos/pam/AlteracoesUnidadesMedidaFrutas.pdf).")
    if CAJU in ps:
        a.append("Caju (pesquisado até 1987): a tabela não diz a unidade; o questionário da PAM de 1985 manda contar o fruto, "
                 "e o rendimento (dezenas de milhares por hectare) só faz sentido em frutos: unidade registrada como mil frutos.")
    if ps_antes is not None:
        entra = [nomes[p] for p in ps if p not in ps_antes and p != "0"]
        sai = [nomes[p] for p in ps_antes if p not in ps and p != "0"]
        if entra or sai:
            t = f"Lavouras pesquisadas mudaram em relação a {ano - 1}"
            if entra:
                t += f"; entraram ({len(entra)}): {', '.join(entra)}"
            if sai:
                t += f"; saíram ({len(sai)}): {', '.join(sai)}"
            a.append(t + ". O total do ano inclui as que entraram.")
    if arred:
        ex = ", ".join(f"{C.rotulo((l,))} · {p} · {v}" for l, p, v in arred[:3])
        a.append(f"Na fonte, 0 (sem o traço) é um valor positivo menor que meia unidade, arredondado para zero; aqui fica 0 "
                 f"({len(arred)} célula(s), ex.: {ex}).")
    if fora:
        a.append(f"Municípios com dado antes da data de instalação que o acervo usa, mantidos como a fonte publica: "
                 f"{', '.join(C.rotulo((x,)) for x in fora)}.")
    # Brasil da fonte × soma dos estados (área colhida e valor do total)
    for v, nome in (("216", "área colhida total"), ("215", "valor total")):
        if v == "215" and ano < DESDE_VALOR:
            continue
        b = next((l["V"] for l in br_linhas if l["D3C"] == str(ano) and l["D4C"] == "0" and l["D2C"] == v), None)
        s = [l["V"] for l in uf_linhas if l["D3C"] == str(ano) and l["D4C"] == "0" and l["D2C"] == v]
        if b and b.isdigit() and s and all(x.isdigit() for x in s) and int(b) != sum(map(int, s)):
            a.append(f"Brasil ({nome}): a fonte dá {C.br(b)}; a soma dos estados dá {C.br(sum(map(int, s)))}.")
    return a


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tudo", action="store_true", help="todos os anos (carga inicial)")
    ap.add_argument("--anos", help="só estes anos, separados por vírgula")
    ap.add_argument("--bruto", help="pasta para guardar e reaproveitar as respostas da SIDRA")
    a = ap.parse_args()
    dia = C.hoje().isoformat()
    br_linhas, url_br = brasil_todos(a.bruto)
    nomes = {l["D4C"]: l["D4N"].replace("*", "").strip() for l in br_linhas}
    ASTERISCO.update(l["D4C"] for l in br_linhas if "*" in l["D4N"])
    # lavoura nova na PAM: ganha um nome curto, guardado no conjunto.json para não mudar nunca mais
    arq = C.pasta_conjunto(CFG) / "conjunto.json"
    novas = dict((json.loads(arq.read_text(encoding="utf-8")).get("estado_da_fonte") or {}).get("lavouras_novas", {})) if arq.exists() else {}
    for c in sorted(set(nomes) - set(LAVOURA) - set(novas)):
        novas[c] = nome_curto(nomes[c], set(LAVOURA.values()) | set(novas.values()))
        print(f"[acervo/lavouras] lavoura nova na SIDRA: {c} {nomes[c]} → {novas[c]}")
    LAVOURA.update(novas)
    anos_fonte = sorted({int(l["D3C"]) for l in br_linhas if l["D2C"] == "216" and l["D4C"] == "0" and l["V"].isdigit()})
    existentes = {int(p) for p in C.pacotes(CFG)}
    if a.anos:
        anos = [int(x) for x in a.anos.split(",")]
    elif a.tudo:
        anos = anos_fonte
    else:   # todo mês: anos novos + preliminares
        prelim = {int(p) for p in C.pacotes(CFG) if C.ficha_atual(CFG, p)["situacao"] == "preliminar"}
        anos = sorted((set(anos_fonte) - existentes) | prelim)
    print(f"[acervo/lavouras] anos na fonte: {anos_fonte[0]}–{anos_fonte[-1]}; a conferir: {anos}")
    uf_linhas = estados(anos, a.bruto) if anos else []
    resultados = {}
    sedes_uf = sorted(C.UF)
    for ano in anos:
        ps = pesquisadas_no_ano(br_linhas, ano)
        ps_antes = pesquisadas_no_ano(br_linhas, ano - 1) if ano - 1 in anos_fonte else None
        tabelas, arred_tudo, fora_tudo, ausentes_txt = {}, [], [], None
        for nivel, linhas, lugares in (("brasil", br_linhas, [C.CODIGO_BRASIL]), ("uf", uf_linhas, sedes_uf)):
            cps, saida, arred, fora, _ = montar(linhas, ano, nivel, ps, lugares)
            tabelas[nivel] = (cps, saida)
            arred_tudo += arred
        if ano >= DESDE_MUNICIPIO:
            atual = C.ficha_atual(CFG, str(ano))
            mudou_cima = True
            if atual and not a.tudo and not a.anos:
                pasta = C.pasta_conjunto(CFG) / str(ano)
                mudou_cima = any((pasta / C.ARQUIVO[n]).read_bytes() != C.tabela_csv(*tabelas[n]) for n in ("brasil", "uf"))
            if atual and not mudou_cima:
                resultados[str(ano)] = "igual"   # Brasil e estados iguais: não baixa os municípios de novo
                continue
            mun = carregar_bruto_municipios(ano, a.bruto) if a.bruto else []
            if not mun:
                mun = municipios(ano, ps, a.bruto)
            cps, saida, arred, fora, ausentes = montar(mun, ano, "municipio", ps, C.municipios_do_ano(ano))
            conferir_soma(saida, tabelas["uf"][1], ano)
            tabelas["municipio"] = (cps, saida)
            arred_tudo += arred
            fora_tudo += fora
            if ausentes:
                ausentes_txt = (f"{len(ausentes)} município(s) não aparecem na SIDRA neste ano (sem nenhuma informação, nota 1 da "
                                f"tabela 5457) e entram com as células vazias: {', '.join(C.rotulo((x,)) for x in ausentes[:12])}{'…' if len(ausentes) > 12 else ''}.")
            else:
                ausentes_txt = None
        itens = [{"lavoura": LAVOURA[p], "codigo_ibge_produto": p, "nome_ibge": nomes[p],
                  "unidade_quantidade": unidade(p, ano)} for p in ps]
        extra = {"coletado_em": dia, "consulta": f"{SIDRA}/t/5457/n1/all/v/{','.join(VARIAVEIS)}/p/{ano}/c782/all",
                 "itens": itens,
                 "avisos": avisos_do_ano(ano, ps, ps_antes, nomes, arred_tudo, fora_tudo, br_linhas, uf_linhas)
                 + ([ausentes_txt] if ausentes_txt else [])}
        resultados[str(ano)] = C.gravar_pacote(CFG, str(ano), tabelas, extra)
    cons = C.consolidar(CFG)
    if cons:
        resultados.update({p: "consolidado agora" for p in cons})
    C.atualizar_conjunto(CFG, conferido_em=dia, estado={"lavouras_novas": novas} if novas else None)
    C.registrar(CFG, resultados)


if __name__ == "__main__":
    main()
