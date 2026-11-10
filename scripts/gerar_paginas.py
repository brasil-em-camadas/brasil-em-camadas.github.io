"""Gera as páginas de texto do site a partir dos registros, na hora de publicar (nada escrito à mão nelas):

- dados/index.html ("Dados para baixar") e dados/<conjunto>/index.html (uma por conjunto do acervo, com os arquivos de
  cada período, o "como citar", o botão "Excel em português" e a ficha schema.org do tipo Dataset para o Google Dataset
  Search, montada da ficha técnica dos pacotes);
- metodologia/index.html ("Metodologia e fontes"): de onde vem cada dado, como é calculado, o que é medição, estimativa
  ou conta do site, e os níveis de confiança;
- estados/index.html ("Estados em números") e estados/<estado>/index.html (uma por estado: os números que pintam o mapa,
  com a fonte, a data, o nível de confiança e a posição entre os estados, mais os detalhes da ficha e o link para o mapa
  já aberto no estado, ?uf=RS);
- llms.txt (um resumo do site para as IAs, com os endereços das páginas).

De onde vem o texto: site/data/fontes.json (níveis de confiança, naturezas, pinturas, luzes e camadas), os arquivos de
cada camada (fonte, referência, data, nota) e site/acervo/ (indice.json, conjunto.json de cada conjunto e a ficha técnica,
datapackage.json, de cada pacote). Assim não há duas versões: mudou o registro ou a ficha, a página muda na publicação
seguinte. O visual vem do style.css do mapa e de site/paginas/ (paginas.css e paginas.js).

Quem chama é o scripts/preparar_publicacao.py (que tem o endereço completo do site, usado só na ficha schema.org e no
llms.txt, como manda a regra do domínio próprio). As páginas não ficam guardadas no repositório: só existem na cópia
publicada (como o robots.txt e o sitemap.xml). Para ver numa cópia:
    python scripts/preparar_publicacao.py --pasta /tmp/copia   (numa cópia de site/; nunca na pasta do repositório)
Só usa a biblioteca padrão; precisa do Python 3.12 ou mais novo (aspas dentro das f-strings), o do Ubuntu do GitHub.
"""
import html
import json
import re
import unicodedata
from pathlib import Path

# Prévia: com True, as páginas saem com noindex, ficam fora do sitemap e o llms.txt não é publicado (foi assim até o Edu
# aprovar, em 09/11/2026). Desde então, False: as páginas entram na busca e o rodapé do mapa tem os links para elas.
PREVIA = False

# Páginas por estado ("<estado> em números", degrau 4 da busca): com True, prévia (noindex, fora do sitemap e do llms.txt,
# sem link no menu das outras páginas). Aprovadas pelo Edu em 09/11/2026: False.
PREVIA_ESTADOS = False

VERSAO_ESTILO = "55"     # style.css (o mesmo número do mapa)
VERSAO_PAGINAS = "2"     # paginas/paginas.css e paginas/paginas.js
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
                "novembro", "dezembro"]
NIVEL_NOME = {"brasil": "Brasil", "uf": "Estados", "municipio": "Municípios"}
LICENCA_CANONICA = "https://creativecommons.org/licenses/by/4.0/"


def e(t):
    return html.escape("" if t is None else str(t), quote=True)


def ler_json(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def data_br(d):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(d or ""))
    return f"{m[3]}/{m[2]}/{m[1]}" if m else (d or "")


def tamanho(b):
    if b is None:
        return ""
    if b < 1000:
        return f"{b} bytes"
    if b < 1_000_000:
        return f"{round(b / 1000):,} KB".replace(",", ".")
    return f"{b / 1_000_000:.1f} MB".replace(".", ",")


def numero(n):
    return f"{n:,}".replace(",", ".")


def chave(p):
    m = re.fullmatch(r"(\d{4})(?:-T([1-4]))?", p)
    return (int(m[1]), int(m[2]) if m[2] else 5) if m else (0, 0)


def posicao(C):
    return str(C.get("medida", "")).lower().startswith("posi")


def rotulo(C, p):
    """O nome do período como o mapa mostra: posição → o mês em que vale (dez/2022); fluxo e medianas → 2025, 3º tri 2026."""
    m = re.fullmatch(r"(\d{4})(?:-T([1-4]))?", p)
    if not m:
        return p
    q = int(m[2]) if m[2] else 4
    if posicao(C):
        return f"{MESES[q * 3 - 1]}/{m[1]}"
    return f"{q}º tri {m[1]}" if m[2] else m[1]


def json_ld(d):
    return json.dumps(d, ensure_ascii=False, indent=1).replace("</", "<\\/")


def links(urls):
    urls = [u for u in ([urls] if isinstance(urls, str) else (urls or [])) if u]
    return " · ".join(f'<a href="{e(u)}" rel="noopener">{e(re.sub(r"^https?://(www[.])?", "", u))}</a>' for u in urls)


# ---------- moldura comum ----------

def moldura(prof, titulo, descricao, corpo, atual, F, jsonld=None, previa=None):
    previa_pg = PREVIA if previa is None else previa
    r = "../" * prof
    nav = [("", "Mapa", None), ("dados/", "Dados para baixar", "dados"), ("metodologia/", "Metodologia e fontes", "metodologia")]
    if not PREVIA_ESTADOS or atual == "estados":
        nav.insert(1, ("estados/", "Estados", "estados"))
    ap = F.get("apoio") or {}
    apoio = (f' · <a href="{e(ap["link"])}" rel="noopener">{e(ap.get("texto", "Apoie este projeto"))}</a>'
             if ap.get("link") else "")
    previa = ('<p class="pg-previa">Página em prévia: ainda fora dos buscadores, aguardando aprovação.</p>' if previa_pg else "")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(titulo)} · Brasil em Camadas</title>
<meta name="description" content="{e(descricao)}">
{'<meta name="robots" content="noindex">' if previa_pg else ''}
<link rel="icon" href="{r}aba/icone_f.svg" type="image/svg+xml">
<link rel="icon" href="{r}aba/icone_f_32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{r}aba/icone_f_180.png">
<!-- busca e prévia de compartilhamento: aqui os endereços são relativos; o scripts/preparar_publicacao.py põe o endereço completo -->
<link rel="canonical" href="./">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Brasil em Camadas">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="{e(titulo)} · Brasil em Camadas">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="./">
<meta property="og:image" content="{r}previa/brasil-em-camadas.jpg?v=2">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="O Brasil no globo, aceso pelas luzes da população do Censo 2022, com o nome Brasil em Camadas">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{r}letras/letras.css?v=1">
<link rel="stylesheet" href="{r}style.css?v={VERSAO_ESTILO}">
<link rel="stylesheet" href="{r}paginas/paginas.css?v={VERSAO_PAGINAS}">
{f'<script type="application/ld+json">{chr(10)}{json_ld(jsonld)}{chr(10)}</script>' if jsonld else ''}
</head>
<body class="pg">
<header class="pg-topo">
  <a class="pg-marca" href="{r}">Brasil em Camadas</a>
  <nav class="pg-nav" aria-label="Páginas do site">{"".join(f'<a href="{r}{h}"{" aria-current=" + chr(34) + "page" + chr(34) if a == atual else ""}>{t}</a>' for h, t, a in nav)}</nav>
</header>
<main class="pg-main">
{previa}{corpo}
</main>
<footer class="pg-rodape">
  <p><b>Brasil em Camadas</b> · mapa do Brasil com dados verificáveis: cada número com a fonte, a data e o nível de confiança.{apoio}</p>
  <p>Privacidade: o site não usa cookies nem anúncios, e as visitas são contadas de forma anônima pelo GoatCounter, sem identificar ninguém.</p>
</footer>
<script src="{r}paginas/paginas.js?v={VERSAO_PAGINAS}" defer></script>
<script data-goatcounter="https://brasilemcamadas.goatcounter.com/count" async src="{r}vendor/count.js?v=1"></script>
</body>
</html>
"""


# ---------- leitura ----------

def ler(pasta):
    pasta = Path(pasta)
    F = ler_json(pasta / "data" / "fontes.json")
    meta = {}
    for x in F.get("pintura", []) + F.get("luzes", []) + F.get("camadas", []):
        arq = x.get("arquivo")
        if arq and arq not in meta and (pasta / "data" / arq).exists():
            try:
                d = ler_json(pasta / "data" / arq)
            except ValueError:
                d = {}
            m = d.get("meta") if isinstance(d, dict) and isinstance(d.get("meta"), dict) else (d if isinstance(d, dict) else {})
            meta[arq] = {k: m.get(k) for k in ("titulo", "fonte", "nivel", "referencia", "atualizado_em", "nota", "obs",
                                                "consulta", "catalogo", "unidade") if m.get(k) not in (None, "", [])}
    acervo = pasta / "acervo"
    conjuntos = []
    if (acervo / "indice.json").exists():
        indice = ler_json(acervo / "indice.json")
        for c in indice.get("conjuntos", []):
            C = ler_json(acervo / c["id"] / "conjunto.json")
            C["_indice"] = c
            C["_fichas"] = {p["periodo"]: ler_json(acervo / c["id"] / p["ficha"]) for p in C["pacotes"]}
            C["_ficha_bytes"] = {p["periodo"]: (acervo / c["id"] / p["ficha"]).stat().st_size for p in C["pacotes"]}
            conjuntos.append(C)
    else:
        indice = {}
    return F, meta, indice, conjuntos


# ---------- página de cada conjunto ----------

def descricao_conjunto(C):
    return f"{C['descricao']} Fonte: {C['fonte']['titulo']}. Em CSV, com ficha técnica por período; uso livre (CC BY 4.0)."


def cobertura(C):
    ps = sorted((p["periodo"] for p in C["pacotes"]), key=chave)
    anos = [p for p in ps if "-T" not in p]
    tri = [p for p in ps if "-T" in p]
    partes = []
    if anos:
        partes.append(f"{anos[0]} a {anos[-1]}, por ano" if len(anos) > 1 else f"{anos[0]}")
    if tri:
        partes.append(f"{'trimestres de ' if anos else ''}{rotulo(C, tri[0])} a {rotulo(C, tri[-1])}" if len(tri) > 1
                      else rotulo(C, tri[0]))
    return "; ".join(partes) + f" ({len(ps)} {'pacote' if len(ps) == 1 else 'pacotes'})"


def intervalo_iso(C):
    """temporalCoverage: do começo do primeiro período ao fim do último (ex.: 1974-01-01/2025-12-31)."""
    fichas = C["_fichas"].values()
    ini = min(f["inicio"] for f in fichas)
    fim = max(f["fim"] for f in fichas)
    return f"{ini}/{fim}"


def pagina_conjunto(C, base, F):
    cid = C["id"]
    url = f"{base}dados/{cid}/"
    pac = sorted(C["pacotes"], key=lambda p: chave(p["periodo"]), reverse=True)
    recente = pac[0]
    ficha_rec = C["_fichas"][recente["periodo"]]
    coletas = sorted({p["coletado_em"] for p in C["pacotes"] if p.get("coletado_em")})
    av_conj = set(C.get("avisos", []))
    pasta_rel = f"../../acervo/{cid}/"
    fonte = C["fonte"]
    org = fonte.get("orgao_nome") or fonte.get("orgao")
    titulo_curto = re.sub(r"\s*\(.*\)\s*$", "", C["titulo"])

    def arquivo(p, r, base_rel, nome_baixar):
        return (f'<a href="{e(base_rel + r["path"])}" download="{e(nome_baixar)}" data-csv="{e(nome_baixar)}">{e(r["path"])}</a>'
                f'<small>{tamanho(r.get("bytes"))}{" · " + numero(r["linhas"]) + " linhas" if r.get("linhas") else ""}</small>')

    linhas = []
    for p in pac:
        per = p["periodo"]
        f = C["_fichas"][per]
        recs = {r["name"]: r for r in f["resources"]}
        sit = (f'<span class="pg-sit pre">preliminar até {data_br(p["consolida_em"])}</span>' if p["situacao"] == "preliminar"
               else '<span class="pg-sit">consolidado</span>')
        extra = [a for a in f.get("avisos", []) if a not in av_conj]
        itens = ""
        if f.get("itens"):
            k = next(iter(f["itens"][0]))   # ex.: "lavoura"; a linha "total" não conta
            n = len([i for i in f["itens"] if i.get(k) != "total"])
            itens = f"<small>{n} {k}s pesquisadas (lista na ficha técnica)</small>" if k.endswith("a") else f"<small>{n} itens (lista na ficha técnica)</small>"
        det = extra
        antigas = "".join(f'<li>versão {a["versao"]}: <a href="{e(pasta_rel + a["ficha"])}">ficha técnica</a></li>'
                          for a in p.get("versoes_antigas", []))
        celulas = []
        for n in ("brasil", "uf", "municipio"):
            r = recs.get(n)
            celulas.append(f"<td>{arquivo(per, r, pasta_rel + per + '/', f'{cid}_{per}_{n}.csv')}</td>" if r else
                           '<td><small>—</small></td>')
        detalhes = (f'<details><summary>avisos deste período ({len(det)})</summary>'
                    f'<ul>{"".join(f"<li>{e(x)}</li>" for x in det)}</ul></details>') if det else ""
        linhas.append(
            f'<tr><th scope="row">{e(rotulo(C, per))}{f"<small>{e(per)}</small>" if rotulo(C, per) != per else ""}</th>'
            f'<td>{sit}<small>versão {p["versao"]} · coletado em {data_br(p["coletado_em"])}</small>{itens}{detalhes}'
            f'{f"<small>Versões antigas:</small><ul>{antigas}</ul>" if antigas else ""}</td>'
            + "".join(celulas) +
            f'<td><a href="{e(pasta_rel + p["ficha"])}">datapackage.json</a><small>{tamanho(C["_ficha_bytes"][per])}</small></td></tr>')

    # colunas na ordem das tabelas do período mais recente (estados, depois o que só existe nos municípios)
    ordem = [x["name"] for r in sorted(ficha_rec["resources"], key=lambda r: ("uf", "brasil", "municipio").index(r["name"])
                                       if r["name"] in ("uf", "brasil", "municipio") else 9) for x in r["schema"]["fields"]]
    ordem = list(dict.fromkeys(ordem))
    cols = sorted(C.get("colunas", []), key=lambda c: ordem.index(c["name"]) if c["name"] in ordem else len(ordem))
    colunas = "".join(
        f'<tr><th scope="row"><code>{e(c["name"])}</code></th><td>{e(c.get("title", ""))}'
        f'{f"<small>{e(c["description"])}</small>" if c.get("description") else ""}</td>'
        f'<td>{e(c.get("unidade", ""))}</td></tr>' for c in cols)
    marcas = ficha_rec.get("marcas", {})
    nomes_marca = {"numero": "número", "vazio": "célula vazia", "X": "X", "..": ".."}
    serie = Path(C.get("serie", "serie_uf.csv")).name
    serie_bytes = C.get("_serie_bytes")

    texto_citar = (f"BRASIL EM CAMADAS. {C['titulo']}: {cobertura(C).split(' (')[0]}. Dados originais: {fonte['titulo']}. "
                   f"Licença CC BY 4.0.")
    corpo = f"""<nav class="pg-trilha" aria-label="Você está em"><a href="../">Dados para baixar</a> / {e(titulo_curto)}</nav>
<h1>{e(C['titulo'])}</h1>
<p class="pg-lede">{e(C['descricao'])}</p>
<dl class="pg-fatos">
  <div><dt>Fonte</dt><dd>{e(fonte['titulo'])}.{f' <a href="{e(fonte["catalogo"])}" rel="noopener">Página oficial</a>' if fonte.get('catalogo') else ''}{f' · <a href="{e(fonte["consulta"])}" rel="noopener">consulta usada</a>' if fonte.get('consulta') else ''}</dd></div>
  <div><dt>Órgão</dt><dd>{f'<a href="{e(fonte["orgao_site"])}" rel="noopener">{e(org)}</a>' if fonte.get('orgao_site') else e(org)}</dd></div>
  <div><dt>Confiança</dt><dd>{pill(F, C.get('nivel_confianca'))}</dd></div>
  <div><dt>Períodos</dt><dd>{e(cobertura(C))}</dd></div>
  <div><dt>Lugares</dt><dd>{e(", ".join(C["niveis"].values()))}</dd></div>
  <div><dt>Atualização</dt><dd>último pacote coletado em {data_br(coletas[-1]) if coletas else "—"}; conferido pelo robô em {data_br(C.get('conferido_em'))} (todo mês)</dd></div>
  <div><dt>Licença</dt><dd>CC BY 4.0: use à vontade, citando o Brasil em Camadas e a fonte. Licença dos números na fonte: {e(C.get('licenca_da_fonte') or fonte.get('licenca') or '')}.</dd></div>
</dl>

<section class="pg-citar" aria-labelledby="t-citar">
  <h2 id="t-citar">Como citar</h2>
  <p id="citar" data-texto="{e(texto_citar)}">{e(texto_citar)} Disponível em: {e(url)}.</p>
  <button class="pg-botao" id="copiar" type="button" hidden>Copiar</button>
  <p class="fino">Cite também o período e a versão que você usou (estão na tabela abaixo e na ficha técnica de cada período).</p>
</section>

<section aria-labelledby="t-baixar">
  <h2 id="t-baixar">Baixar</h2>
  <fieldset class="pg-formato">
    <legend>Formato dos CSV</legend>
    <label><input type="radio" name="formato" value="csv" checked> CSV padrão (vírgula entre colunas, ponto nos decimais)</label>
    <label><input type="radio" name="formato" value="excel"> Excel em português (ponto e vírgula, vírgula nos decimais)</label>
    <small>O CSV padrão abre direto em Python, R e nas planilhas configuradas em inglês; o Excel em português converte na hora, no seu navegador.</small>
  </fieldset>
  <p class="pg-aviso-baixar" id="aviso-baixar" role="status"></p>
  <p>Todos os períodos de uma vez, por estado (e o Brasil, com <code>uf = BR</code>): <a href="{e(pasta_rel + serie)}" download="{e(cid)}_serie_uf.csv" data-csv="{e(cid)}_serie_uf.csv">{e(serie)}</a>{f' <small>{tamanho(serie_bytes)}</small>' if serie_bytes else ''}. A ficha do conjunto, com a lista dos pacotes: <a href="{e(pasta_rel)}conjunto.json">conjunto.json</a>.</p>
  <div class="pg-rolar"><table class="pg-tabela">
    <caption class="fino" style="caption-side:bottom;text-align:left;padding:8px 10px">Cada período é um pacote: a ficha técnica (datapackage.json) e as tabelas do Brasil, dos estados e, quando há, dos municípios.</caption>
    <thead><tr><th scope="col">Período</th><th scope="col">Situação</th><th scope="col">Brasil</th><th scope="col">Estados</th><th scope="col">Municípios</th><th scope="col">Ficha técnica</th></tr></thead>
    <tbody>
{chr(10).join(linhas)}
    </tbody>
  </table></div>
</section>

<section aria-labelledby="t-colunas">
  <h2 id="t-colunas">O que tem em cada coluna</h2>
  <div class="pg-rolar"><table class="pg-tabela">
    <thead><tr><th scope="col">Coluna</th><th scope="col">O que é</th><th scope="col">Unidade</th></tr></thead>
    <tbody>{colunas}</tbody>
  </table></div>
  <h3>Marcas nas células</h3>
  <ul>{"".join(f"<li><b>{e(nomes_marca.get(k, k))}</b>: {e(v)}</li>" for k, v in marcas.items())}</ul>
</section>

<section aria-labelledby="t-metodo">
  <h2 id="t-metodo">Método</h2>
  <p>{e(C.get('metodo'))}</p>
  <p><b>Medida:</b> {e(C.get('medida'))}. <b>Como vira ano:</b> {e(C.get('como_vira_ano'))}.</p>
  <p><b>Situação:</b> {e(C.get('consolidacao'))}; depois, consolidado. Se a fonte mudar um número, entra uma versão nova, com a nota do que mudou, e a antiga continua aqui para baixar.</p>
  <h3>Avisos</h3>
  <ul>{"".join(f"<li>{e(a)}</li>" for a in C.get("avisos", []))}</ul>
</section>

<section aria-labelledby="t-formato">
  <h2 id="t-formato">Formato</h2>
  <p>Os pacotes seguem o padrão aberto <a href="https://datapackage.org/" rel="noopener">Frictionless Data Package</a>: a ficha técnica descreve cada tabela e cada coluna e traz o tamanho e o hash (SHA-256) de cada arquivo, para conferir que é o arquivo publicado. Em Python, <code>pandas.read_csv</code> lê o endereço de qualquer CSV desta página; em R, <code>read.csv</code>. O nome dos municípios fica num arquivo só, <a href="../../acervo/municipios.csv">municipios.csv</a> (código do IBGE, nome, estado, posição da sede e ano de criação). Detalhes do formato: <a href="../../acervo/README.md">README do acervo</a>.</p>
</section>
"""
    # ficha schema.org Dataset (Google Dataset Search): montada da ficha técnica dos pacotes e do conjunto.json
    dist = [{"@type": "DataDownload", "name": f"{titulo_curto}: todos os períodos, Brasil e estados ({serie})",
             "encodingFormat": "text/csv", "contentUrl": f"{base}acervo/{cid}/{serie}"}]
    for n in ("brasil", "uf", "municipio"):
        r = {x["name"]: x for x in ficha_rec["resources"]}.get(n)
        if r:
            dist.append({"@type": "DataDownload", "name": f"{titulo_curto}: {rotulo(C, recente['periodo'])}, {NIVEL_NOME[n].lower()} ({r['path']})",
                         "encodingFormat": "text/csv", "contentUrl": f"{base}acervo/{cid}/{recente['periodo']}/{r['path']}",
                         "contentSize": tamanho(r.get("bytes"))})
    descricao_ld = (f"{C['descricao']} {C.get('metodo', '')} Dados originais: {fonte['titulo']} ({org}). "
                    f"Um pacote por período ({cobertura(C)}), em CSV, com ficha técnica no padrão Frictionless Data Package.")
    ld = {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "@id": url + "#conjunto",
        "name": C["titulo"],
        "description": descricao_ld[:4900],
        "url": url,
        "identifier": cid,
        "keywords": C.get("palavras_chave", []),
        "inLanguage": "pt-BR",
        "isAccessibleForFree": True,
        "license": LICENCA_CANONICA,
        "creditText": f"Brasil em Camadas, com dados do {fonte.get('orgao')} ({fonte['titulo']})",
        "creator": {"@type": "Organization", "name": org, **({"url": fonte["orgao_site"]} if fonte.get("orgao_site") else {})},
        "publisher": {"@type": "Organization", "name": "Brasil em Camadas", "url": base},
        "isBasedOn": fonte.get("catalogo") or fonte.get("consulta"),
        "measurementTechnique": C.get("metodo"),
        "temporalCoverage": intervalo_iso(C),
        "spatialCoverage": {"@type": "Place", "name": "Brasil: " + ", ".join(C["niveis"].values()),
                            "geo": {"@type": "GeoShape", "box": "-33.75 -73.99 5.27 -28.84"}},
        "variableMeasured": [{"@type": "PropertyValue", "name": c["name"], "description": c.get("title", ""),
                              **({"unitText": c["unidade"]} if c.get("unidade") else {})}
                             for c in C.get("colunas", []) if c.get("type") in ("integer", "number")],
        "dateModified": coletas[-1] if coletas else None,
        "datePublished": coletas[0] if coletas else None,
        "distribution": dist,
        "includedInDataCatalog": {"@type": "DataCatalog", "name": "Brasil em Camadas · dados para baixar", "url": f"{base}dados/"},
    }
    ld = {k: v for k, v in ld.items() if v not in (None, "", [])}
    return moldura(2, f"{titulo_curto} · dados para baixar", descricao_conjunto(C), corpo, "dados", F, ld)


def pill(F, rotulo_nivel):
    for k, n in (F.get("niveis") or {}).items():
        if n.get("nome") == rotulo_nivel or k == rotulo_nivel:
            return f'<span class="pill n-{e(k)}">{e(n["nome"])}</span>'
    return f'<span class="pill">{e(rotulo_nivel)}</span>'


# ---------- página "Dados para baixar" ----------

def pagina_dados(conjuntos, base, F, indice):
    cartoes = "".join(
        f'<a class="pg-cartao" href="{e(C["id"])}/"><b>{e(re.sub(r"\s*\(.*\)\s*$", "", C["titulo"]))}</b>'
        f'<span>{e(C["descricao"])}</span><em>{e(C["fonte"].get("orgao"))} · {e(cobertura(C))}</em></a>'
        for C in conjuntos)
    corpo = f"""<h1>Dados para baixar</h1>
<p class="pg-lede">Os números do mapa guardados por período, ano a ano ou trimestre a trimestre, desde o começo da série de cada fonte, para baixar em CSV. Cada período tem uma ficha técnica com a fonte, a data da coleta, a situação (preliminar ou consolidado) e o método. Uso livre (CC BY 4.0), citando o Brasil em Camadas e a fonte.</p>
<section aria-labelledby="t-conj">
  <h2 id="t-conj">Conjuntos</h2>
  <div class="pg-cartoes">{cartoes}</div>
</section>
<section aria-labelledby="t-como">
  <h2 id="t-como">Como os dados estão guardados</h2>
  <ul>
    <li>Um <b>conjunto</b> é um tipo de dado de uma fonte, medido sempre do mesmo jeito; um <b>pacote</b> é um período dele. Pacote publicado nunca é apagado nem sobrescrito: se a fonte muda um número, entra uma versão nova, e a antiga continua para baixar.</li>
    <li><b>Preliminar</b>: o período fechou há pouco e a fonte ainda pode revisar (o robô confere todo mês). <b>Consolidado</b>: passou o prazo de revisão da fonte.</li>
    <li>Tabelas em CSV, uma linha por lugar, com o código do IBGE; na página de cada conjunto, a opção <b>Excel em português</b> converte na hora (ponto e vírgula entre as colunas e vírgula nos decimais).</li>
    <li>Dinheiro no valor de cada ano, como a fonte publica, sem descontar a inflação.</li>
  </ul>
  <p>Para programas: a lista de conjuntos e períodos fica em <a href="../acervo/indice.json">indice.json</a>, os municípios em <a href="../acervo/municipios.csv">municipios.csv</a> e o formato completo no <a href="../acervo/README.md">README do acervo</a>. De onde vem cada número do mapa: <a href="../metodologia/">Metodologia e fontes</a>.</p>
</section>
"""
    ld = {"@context": "https://schema.org/", "@type": "DataCatalog", "@id": f"{base}dados/#catalogo",
          "name": "Brasil em Camadas · dados para baixar", "url": f"{base}dados/", "inLanguage": "pt-BR",
          "description": "Os números do mapa Brasil em Camadas guardados por período (ano ou trimestre), em CSV, com ficha técnica por período.",
          "publisher": {"@type": "Organization", "name": "Brasil em Camadas", "url": base},
          "license": LICENCA_CANONICA,
          "dataset": [{"@type": "Dataset", "@id": f"{base}dados/{C['id']}/#conjunto", "name": C["titulo"],
                       "description": descricao_conjunto(C), "url": f"{base}dados/{C['id']}/"} for C in conjuntos]}
    return moldura(1, "Dados para baixar",
                   "Os números do mapa Brasil em Camadas por período (ano ou trimestre), em CSV, com ficha técnica, fonte e "
                   "situação de cada período. Uso livre, citando a fonte.", corpo, "dados", F, ld)


# ---------- página "Metodologia e fontes" ----------

def pagina_metodologia(F, meta, conjuntos, data_dados):
    nat = F.get("naturezas") or {}

    def item(x, tipo):
        m = meta.get(x.get("arquivo"), {})
        nivel = x.get("nivel") or m.get("nivel") or "pendente"
        fonte = x.get("fonte") or m.get("fonte") or ""
        ref = m.get("referencia")
        partes = [f'<p>{e(fonte)}{"." if fonte and not fonte.endswith(".") else ""}'
                  f'{f" Referência: {e(ref)}." if ref else ""}'
                  f'{f" Atualizado em {data_br(m["atualizado_em"])}." if m.get("atualizado_em") else ""}</p>']
        # nas pinturas, a nota do arquivo é a mesma que o mapa mostra na ficha; nas camadas, o texto público é o do
        # fontes.json (a nota dos arquivos de camada é documentação para quem programa, com nomes de campos)
        if tipo == "pintura" and m.get("nota"):
            partes.append(f"<p>{e(m['nota'][0].upper() + m['nota'][1:])}.</p>")
        if tipo == "pintura" and m.get("obs"):
            partes.append(f"<p>{e(m['obs'])}</p>")
        if x.get("explica"):
            partes.append(f"<p>{e(x['explica'])}</p>")
        if x.get("conta"):
            partes.append(f"<p><b>Conta do site:</b> {e(x['conta'])}.</p>")
        if m.get("consulta") or m.get("catalogo"):
            partes.append(f'<p class="fino">{"Consulta: " + links(m.get("consulta")) if m.get("consulta") else ""}'
                          f'{" · " if m.get("consulta") and m.get("catalogo") else ""}'
                          f'{"Catálogo: " + links(m.get("catalogo")) if m.get("catalogo") else ""}</p>')
        if x.get("acervo"):
            C = next((c for c in conjuntos if c["id"] == x["acervo"]["conjunto"]), None)
            if C:
                partes.append(f'<p class="fino">Todos os períodos: <a href="../dados/{e(C["id"])}/">{e(C["titulo"])}</a>, nos dados para baixar.</p>')
        nats = "".join(f'<span class="pg-nat">{e(nat[n]["nome"])}</span>' for n in x.get("natureza", []) if n in nat)
        return (f'<article class="pg-item" id="{tipo}-{e(x["id"])}"><h3>{e(x["nome"])} {pill(F, nivel)}</h3>'
                f'{f"<p>{nats}</p>" if nats else ""}{"".join(partes)}</article>')

    pinturas = [p for p in F.get("pintura", []) if not p.get("teste")]
    luzes = [l for l in F.get("luzes", []) if not l.get("teste")]
    camadas = [c for c in F.get("camadas", []) if not c.get("teste")]
    por_min = []
    for k, nome in (F.get("ministerios") or {}).items():
        cs = [c for c in camadas if c.get("ministerio") == k]
        if cs:
            por_min.append(f'<h3 class="pg-grupo" id="camadas-{e(k)}">{e(nome)}</h3>' + "".join(item(c, "camada") for c in cs))
    acervo = "".join(
        f'<article class="pg-item" id="acervo-{e(C["id"])}"><h3><a href="../dados/{e(C["id"])}/">{e(C["titulo"])}</a> {pill(F, C.get("nivel_confianca"))}</h3>'
        f'<p>{e(C.get("metodo"))}</p><p><b>Medida:</b> {e(C.get("medida"))}. <b>Como vira ano:</b> {e(C.get("como_vira_ano"))}. '
        f'<b>Situação:</b> {e(C.get("consolidacao"))}.</p>'
        f'<ul>{"".join(f"<li>{e(a)}</li>" for a in C.get("avisos", []))}</ul></article>' for C in conjuntos)
    niveis = "".join(f'<li>{pill(F, k)} {e(n.get("explica"))}</li>' for k, n in (F.get("niveis") or {}).items())
    naturezas = "".join(f'<li><span class="pg-nat">{e(n["nome"])}</span> {e(n.get("explica"))}</li>' for n in nat.values())
    corpo = f"""<h1>Metodologia e fontes</h1>
<p class="pg-lede">De onde vem cada número do mapa, de quando é, como é calculado e o que é medição, estimativa ou conta do site. Esta página é feita, a cada publicação, do mesmo registro que o mapa usa (as fontes de cada pintura e camada) e das fichas técnicas do acervo: muda junto com o mapa. Nada é inventado: o que falta aparece como falta.</p>
<ul class="pg-indice">
  <li><a href="#niveis">Níveis de confiança</a></li>
  <li><a href="#naturezas">Medição, estimativa ou conta do site</a></li>
  <li><a href="#pinturas">Pinturas dos estados</a></li>
  <li><a href="#luzes">Luzes à noite</a></li>
  <li><a href="#camadas">Camadas do mapa</a></li>
  <li><a href="#acervo">Dados por período (acervo)</a></li>
  <li><a href="#atualizacao">Atualização</a></li>
</ul>
<section id="niveis" aria-labelledby="t-niveis">
  <h2 id="t-niveis">Níveis de confiança</h2>
  <p>Cada número do mapa aparece com um destes selos, ao lado da fonte e da data.</p>
  <ul>{niveis}</ul>
</section>
<section id="naturezas" aria-labelledby="t-nat">
  <h2 id="t-nat">Medição, estimativa ou conta do site</h2>
  <p>O selo diz quem publica o número; esta classificação diz como o número nasceu. Um mesmo dado pode ter duas (ex.: a fonte mede e o site faz a mediana).</p>
  <ul>{naturezas}</ul>
</section>
<section id="pinturas" aria-labelledby="t-pint">
  <h2 id="t-pint">Pinturas dos estados</h2>
  <p>A cor de cada estado: cinco faixas com o mesmo número de estados (do bege fosco ao ouro aceso); cinza frio = sem número; cinza escuro = nenhum ou, nas pinturas de total, menos de 0,1% do Brasil.</p>
  {"".join(item(p, "pintura") for p in pinturas)}
</section>
<section id="luzes" aria-labelledby="t-luzes">
  <h2 id="t-luzes">Luzes à noite</h2>
  {"".join(item(l, "luz") for l in luzes)}
</section>
<section id="camadas" aria-labelledby="t-cam">
  <h2 id="t-cam">Camadas do mapa</h2>
  <p>Por ministério, na ordem do filtro do mapa.</p>
  {"".join(por_min)}
</section>
<section id="acervo" aria-labelledby="t-acervo">
  <h2 id="t-acervo">Dados por período (acervo)</h2>
  <p>Os conjuntos guardados por período, com a ficha técnica de cada um, ficam em <a href="../dados/">Dados para baixar</a>.</p>
  {acervo}
</section>
<section id="atualizacao" aria-labelledby="t-atual">
  <h2 id="t-atual">Atualização</h2>
  <p>Os robôs do site buscam os dados nas fontes uma vez por mês; quando uma fonte falha, o mapa continua com os arquivos anteriores, e cada camada mostra a própria data no painel. Última busca com sucesso: {data_br(data_dados) or "—"}.</p>
</section>
"""
    return moldura(1, "Metodologia e fontes",
                   "De onde vem cada número do mapa Brasil em Camadas, como é calculado, o que é medição, estimativa ou conta "
                   "do site, e os níveis de confiança.", corpo, "metodologia", F)


# ---------- páginas por estado ("<estado> em números") ----------

REGIOES = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}   # 1º dígito do código do IBGE
DE = {"AC": "do", "AL": "de", "AM": "do", "AP": "do", "BA": "da", "CE": "do", "DF": "do", "ES": "do", "GO": "de", "MA": "do",
      "MG": "de", "MS": "de", "MT": "de", "PA": "do", "PB": "da", "PE": "de", "PI": "do", "PR": "do", "RJ": "do", "RN": "do",
      "RO": "de", "RR": "de", "RS": "do", "SC": "de", "SE": "de", "SP": "de", "TO": "do"}   # "no mapa do Pará", "de Minas Gerais"
EM = {"do": "no", "da": "na", "de": "em"}


def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def num(v, casas=1):
    """Número no jeito brasileiro: 10.882.965; 9.904,2; 94,4 (sem zeros sobrando no fim)."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer() and abs(v) >= 1000:
        v = int(v)
    s = f"{v:,.{casas}f}" if isinstance(v, float) else f"{v:,}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    if "," in s:
        s = s.rstrip("0").rstrip(",")
    return s


def reais_mil(v):
    """Valor em mil reais (como o IBGE publica) escrito por extenso: R$ 28,3 bilhões; R$ 984,5 milhões; R$ 820 mil."""
    if v is None:
        return ""
    r = v * 1000
    if r >= 1e9:
        return f"R$ {num(r / 1e9)} {'bilhão' if round(r / 1e9, 1) < 2 else 'bilhões'}"
    if r >= 1e6:
        return f"R$ {num(r / 1e6)} {'milhão' if round(r / 1e6, 1) < 2 else 'milhões'}"
    return f"R$ {num(round(v))} mil"


def com_unidade(texto, un):
    if not un:
        return texto
    if un == "mil R$":
        return texto
    if un.startswith("%"):
        return f"{texto}% {un[1:].strip()}".strip()
    return f"{texto} {un}"


def ler_estados(pasta):
    g = ler_json(Path(pasta) / "data" / "geo" / "estados.json")
    ests = []
    for f in g.get("features", []):
        q = f["properties"]
        ests.append({"sigla": q["sigla"], "nome": q["name"], "codigo": str(q.get("codigo_ibg", "")),
                     "regiao": REGIOES.get(str(q.get("codigo_ibg", ""))[:1], ""), "area": q.get("area_km2"),
                     "slug": slug(q["name"])})
    return sorted(ests, key=lambda x: (x["codigo"][:1], x["nome"]))


def valores_pintura(P, d, pop):
    """O mesmo número que pinta o mapa (como no app: per_capita = por 100 mil habitantes do Censo 2022)."""
    vs = {}
    for uf, v in (d.get("valores") or {}).items():
        if isinstance(v, dict):
            v = v.get(P.get("campo") or "valor")
        if P.get("por") == "per_capita":
            v = v / pop[uf] * 1e5 if (v is not None and pop.get(uf)) else None
        vs[uf] = v
    return vs


def brasil_pintura(P, d, pop):
    b = d.get("brasil")
    b = b.get("valor") if isinstance(b, dict) else b
    if b is None:
        return None
    if P.get("por") == "per_capita":
        tot = sum(pop.values())
        return b / tot * 1e5 if tot else None
    return b


def linhas_estado(uf, F, pasta, pop):
    """Uma linha por pintura do mapa: valor, parte do Brasil ou valor do Brasil, posição entre os estados, fonte e data."""
    mins = F.get("ministerios") or {}
    grupos = {}
    for P in F.get("pintura", []):
        if P.get("teste") or not P.get("arquivo"):
            continue
        caminho = Path(pasta) / "data" / P["arquivo"]
        if not caminho.exists():
            continue
        d = ler_json(caminho)
        vs = valores_pintura(P, d, pop)
        v = vs.get(uf)
        taxa = P.get("por") in ("per_capita", "percentual", "taxa")
        un = P.get("unidade") or d.get("unidade") or ""
        if P.get("por") == "per_capita":
            un = f"{d.get('unidade', '')} por 100 mil habitantes".strip()
        validos = {k: x for k, x in vs.items() if x is not None}
        if v is None:
            valor = f'<span class="pg-sem">{e(P.get("vazio") or "sem número")}</span>'
            extra = ""
            pos = ""
        else:
            texto = reais_mil(v) if un == "mil R$" else num(v if taxa or isinstance(v, int) else round(v, 1))
            valor = e(com_unidade(texto, un))
            if taxa:
                b = brasil_pintura(P, d, pop)
                extra = f"Brasil: {e(num(round(b, 1)))}" if b is not None else ""
            else:
                tot = sum(validos.values())
                extra = f"{e(num(round(v / tot * 100, 1)))}% do Brasil" if tot else ""
            n = len(validos)
            lugar = 1 + sum(1 for x in validos.values() if x > v)
            fora = 27 - n
            pos = f"{lugar}º de {n}" + (f' <small>(nos outros {fora}: {e(P.get("vazio") or "sem número")})</small>' if fora > 0 else "")
        fonte = e(d.get("fonte", ""))
        quando = " · ".join(x for x in [f"referência: {e(d['referencia'])}" if d.get("referencia") else "",
                                        f"buscado em {e(data_br(d['atualizado_em']))}" if d.get("atualizado_em") else ""] if x)
        linha = (f'<tr class="pg-l1"><th scope="row"><a href="../../metodologia/#pintura-{e(P["id"])}">{e(P["nome"])}</a></th>'
                 f'<td class="num">{valor}{f"<small>{extra}</small>" if extra else ""}</td>'
                 f'<td class="num">{pos}</td></tr>'
                 f'<tr class="pg-l2"><td colspan="3"><small>Fonte: {fonte}{" · " + quando if quando else ""} {pill(F, d.get("nivel"))}</small></td></tr>')
        grupos.setdefault(P.get("ministerio", ""), []).append(linha)
    corpo = []
    for k, nome in mins.items():
        if k in grupos:
            corpo.append(f'<tbody><tr class="pg-grupo-linha"><th colspan="3" scope="rowgroup">{e(nome)}</th></tr>{"".join(grupos[k])}</tbody>')
    return "".join(corpo)


def detalhes_estado(uf, pasta):
    """Blocos com o que a ficha do estado mostra além das pinturas (lavouras, rebanhos, energia, petróleo, defesa)."""
    dd = Path(pasta) / "data"
    blocos = []

    def fonte_de(d):
        partes = [e(d.get("fonte", ""))]
        if d.get("referencia"):
            partes.append(f"referência: {e(d['referencia'])}")
        return f'<p class="fino">Fonte: {" · ".join(partes)}.</p>'

    if (dd / "lavouras" / "estados.json").exists():
        d = ler_json(dd / "lavouras" / "estados.json")
        v = (d.get("valores") or {}).get(uf) or {}
        pr = v.get("principais") or []
        if pr:
            un = {"t": "toneladas", "mil frutos": "mil frutos", "mil cachos": "mil cachos"}
            linhas = "".join(f'<tr><th scope="row">{e(l[0])}</th><td class="num">{e(reais_mil(l[1]))}</td>'
                             f'<td class="num">{e(num(l[2]))} {e(un.get(l[3], l[3]) if len(l) > 3 else "")}</td></tr>' for l in pr)
            blocos.append(f"""<section aria-labelledby="t-lav">
  <h2 id="t-lav">Lavouras de maior valor</h2>
  <div class="pg-rolar"><table class="pg-tabela"><thead><tr><th>Lavoura</th><th>Valor da produção</th><th>Quantidade</th></tr></thead>
  <tbody>{linhas}</tbody></table></div>
  {fonte_de(d)}
</section>""")
    if (dd / "pecuaria" / "estados.json").exists():
        d = ler_json(dd / "pecuaria" / "estados.json")
        v = (d.get("valores") or {}).get(uf) or {}
        itens = [(k, n) for k, n in [("bovino", "Bovinos"), ("suino", "Suínos"), ("galinaceos", "Galinhas, galos, frangos e pintos"),
                                      ("ovino", "Ovinos"), ("caprino", "Caprinos")] if v.get(k) is not None]
        if itens:
            lis = "".join(f'<li>{e(n)}: <b>{e(num(v[k]))}</b> cabeças</li>' for k, n in itens)
            if v.get("aquicultura_mil_rs"):
                pr = (f' (a principal: {e(v["aquicultura_principal"])}, {e(reais_mil(v.get("aquicultura_principal_mil_rs")))})'
                      if v.get("aquicultura_principal") else "")
                lis += f'<li>Aquicultura (criação de peixes, camarão, ostras e outros): <b>{e(reais_mil(v["aquicultura_mil_rs"]))}</b> por ano{pr}</li>'
            blocos.append(f"""<section aria-labelledby="t-reb">
  <h2 id="t-reb">Rebanhos e aquicultura</h2>
  <ul>{lis}</ul>
  {fonte_de(d)}
</section>""")
    if (dd / "energia" / "estados.json").exists():
        d = ler_json(dd / "energia" / "estados.json")
        v = (d.get("valores") or {}).get(uf) or {}
        tipos = d.get("tipos") or {}
        itens = sorted(((k, v[k]) for k in tipos if (v.get(k) or 0) > 0), key=lambda x: -x[1])
        if itens and v.get("valor"):
            linhas = "".join(f'<tr><th scope="row">{e(tipos[k])}</th><td class="num">{e(num(round(mw, 1)))} MW</td>'
                             f'<td class="num">{e(num(round(mw / v["valor"] * 100, 1)))}%</td></tr>' for k, mw in itens)
            blocos.append(f"""<section aria-labelledby="t-ene">
  <h2 id="t-ene">Energia elétrica por fonte</h2>
  <p>{e(num(v.get("usinas")))} usinas em operação, com {e(num(round(v["valor"], 1)))} MW de potência no total.</p>
  <div class="pg-rolar"><table class="pg-tabela"><thead><tr><th>Fonte</th><th>Potência</th><th>Parte do estado</th></tr></thead>
  <tbody>{linhas}</tbody></table></div>
  {fonte_de(d)}{f'<p class="fino">{e(d["nota"][:1].upper() + d["nota"][1:])}.</p>' if d.get("nota") else ""}
</section>""")
    if (dd / "petroleo" / "producao_estados.json").exists():
        d = ler_json(dd / "petroleo" / "producao_estados.json")
        v = (d.get("valores") or {}).get(uf)
        if isinstance(v, dict) and v.get("valor"):
            blocos.append(f"""<section aria-labelledby="t-oleo">
  <h2 id="t-oleo">Petróleo e gás</h2>
  <ul><li>Petróleo: <b>{e(num(round(v.get("petroleo_bbl_dia") or 0)))}</b> barris por dia</li>
  <li>Gás natural: <b>{e(num(round(v.get("gas_mil_m3_dia") or 0)))}</b> mil m³ por dia</li>
  <li>Total: <b>{e(num(round(v["valor"])))}</b> barris de óleo equivalente (boe) por dia, em {e(num(v.get("pocos")))} poços produzindo</li></ul>
  {fonte_de(d)}
</section>""")
    if (dd / "defesa" / "estados.json").exists():
        d = ler_json(dd / "defesa" / "estados.json")
        v = (d.get("valores") or {}).get(uf)
        if isinstance(v, dict) and v.get("valor"):
            muns = ", ".join(f"{e(m)} ({n})" for m, n in (v.get("municipios") or []))
            blocos.append(f"""<section aria-labelledby="t-def">
  <h2 id="t-def">Indústria de defesa</h2>
  <p><b>{e(num(v["valor"]))}</b> {"empresa credenciada" if v["valor"] == 1 else "empresas credenciadas"} pelo Ministério da Defesa: {e(num(v.get("eed", 0)))} como empresa estratégica de defesa (EED) e {e(num(v.get("ed", 0)))} como empresa de defesa (ED).{f" Sedes: {muns}." if muns else ""}</p>
  {fonte_de(d)}
</section>""")
    return "".join(blocos)


def pagina_estado(E, ests, F, pasta, pop, base):
    uf, nome = E["sigla"], E["nome"]
    de = DE.get(uf, "de")
    em = EM[de]
    agro = ler_json(Path(pasta) / "data" / "agricultura.json") if (Path(pasta) / "data" / "agricultura.json").exists() else {}
    va = (agro.get("valores") or {}).get(uf)
    p = pop.get(uf)
    desc = (f"{nome} em números: população{f' de {num(round(p / 1e6, 1))} milhões' if p and p >= 1e6 else (f' de {num(p)}' if p else '')}"
            f" (Censo 2022), produção agrícola{f' de {reais_mil(va)}' if va else ''}, rebanhos, energia, internet e mais, "
            "com a fonte e a data de cada número.")
    outros = []
    for reg in REGIOES.values():
        xs = [x for x in ests if x["regiao"] == reg]
        if xs:
            outros.append(f'<li><b>{e(reg)}</b>: ' + ", ".join(
                (f'<a href="../{x["slug"]}/">{e(x["nome"])}</a>' if x["sigla"] != uf else f'<span aria-current="page">{e(x["nome"])}</span>')
                for x in xs) + "</li>")
    corpo = f"""<nav class="pg-trilha" aria-label="Você está em"><a href="../">Estados</a> / {e(nome)}</nav>
<h1>{e(nome)} em números</h1>
<p class="pg-lede">Os números que pintam o mapa Brasil em Camadas, para {"o" if uf == "DF" else "o estado " + e(de)} {e(nome)} ({e(uf)}, região {e(E["regiao"])}, {e(num(round(E["area"])) if E.get("area") else "")} km²), com a fonte, a data e o nível de confiança de cada um. A posição compara com os outros estados; a parte do Brasil é a soma dos estados.</p>
<p class="pg-abrir"><a class="pg-botao pg-botao-forte" href="../../?uf={e(uf)}">Abrir o mapa {e(em)} {e(nome)}</a> <a class="fino" href="../../2d/?uf={e(uf)}">ou na versão leve</a></p>
<section aria-labelledby="t-num">
  <h2 id="t-num">Números principais</h2>
  <div class="pg-rolar"><table class="pg-tabela pg-estado">
  <thead><tr><th>Dado</th><th>Valor</th><th>Posição entre os estados</th></tr></thead>
  {linhas_estado(uf, F, pasta, pop)}
  </table></div>
  <p class="fino">O que cada número quer dizer e como é calculado: <a href="../../metodologia/">Metodologia e fontes</a>. As séries por ano, para baixar: <a href="../../dados/">Dados para baixar</a>.</p>
</section>
{detalhes_estado(uf, pasta)}
<section aria-labelledby="t-mapa">
  <h2 id="t-mapa">No mapa</h2>
  <p>A ficha do estado no mapa tem também rodovias, ferrovias e portos, aeroportos e passageiros, pedágios, fronteira, limites do mar e as camadas de cada ministério, com os municípios. <a href="../../?uf={e(uf)}">Abrir o mapa {e(em)} {e(nome)}</a>.</p>
</section>
<section aria-labelledby="t-outros">
  <h2 id="t-outros">Outros estados</h2>
  <ul class="pg-estados">{"".join(outros)}</ul>
</section>
"""
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{nome} em números", "description": desc,
          "inLanguage": "pt-BR",
          "about": {"@type": "AdministrativeArea", "name": nome, "identifier": E["codigo"],
                    "containedInPlace": {"@type": "Country", "name": "Brasil"}},
          "isPartOf": {"@type": "WebSite", "name": "Brasil em Camadas", "url": base}}
    return moldura(2, f"{nome} em números", desc, corpo, "estados", F, ld, previa=PREVIA_ESTADOS)


def pagina_estados(ests, F, pop):
    grupos = []
    for reg in REGIOES.values():
        xs = [x for x in ests if x["regiao"] == reg]
        if xs:
            cartoes = "".join(f'<a class="pg-cartao" href="{e(x["slug"])}/"><b>{e(x["nome"])}</b>'
                              f'<span>{e(x["sigla"])} · {e(num(pop.get(x["sigla"])))} habitantes (Censo 2022)</span></a>' for x in xs)
            grupos.append(f'<h3 class="pg-grupo">{e(reg)}</h3><div class="pg-cartoes">{cartoes}</div>')
    corpo = f"""<h1>Estados em números</h1>
<p class="pg-lede">Uma página para cada estado e para o Distrito Federal, com os números que pintam o mapa: população, produção agrícola, rebanhos, energia, petróleo, celular e internet, indústria de defesa e eletropostos. Cada número com a fonte, a data, o nível de confiança e a posição entre os estados. As páginas se refazem a cada publicação, com os dados que os robôs do site buscam todo mês.</p>
<section aria-labelledby="t-est">
  <h2 id="t-est">Por região</h2>
  {"".join(grupos)}
</section>
"""
    return moldura(1, "Estados em números",
                   "População, agricultura, energia, internet e outros números de cada estado do Brasil, com a fonte e a "
                   "data de cada um.", corpo, "estados", F, previa=PREVIA_ESTADOS)


# ---------- llms.txt ----------

def llms(F, conjuntos, base, ests=None):
    linhas = [
        "# Brasil em Camadas", "",
        "> Mapa interativo do Brasil por estado (população, agricultura, energia, transportes, internet e mais), com a fonte, "
        "a data e o nível de confiança de cada número. Gratuito, sem anúncios; os dados se baixam por período, em CSV.", "",
        "O mapa é uma página de JavaScript (globo 3D e versão leve 2D). O texto e os dados ficam nas páginas abaixo, que não "
        "precisam de JavaScript.", "",
        "## Dados para baixar", "",
        f"- [Dados para baixar]({base}dados/): os conjuntos guardados por período, com ficha técnica e licença CC BY 4.0",
    ]
    for C in conjuntos:
        linhas.append(f"- [{C['titulo']}]({base}dados/{C['id']}/): {C['descricao']} {cobertura(C)}.")
    if ests and not PREVIA_ESTADOS:
        linhas += ["", "## Estados", "", f"- [Estados em números]({base}estados/): uma página por estado, com os números do mapa"]
        linhas += [f"- [{x['nome']} em números]({base}estados/{x['slug']}/)" for x in ests]
    linhas += ["", "## Metodologia", "",
               f"- [Metodologia e fontes]({base}metodologia/): de onde vem cada número, como é calculado, o que é medição, "
               "estimativa ou conta do site, e os níveis de confiança", "",
               "## Opcional", "",
               f"- [Formato do acervo]({base}acervo/README.md): como os pacotes são organizados (Frictionless Data Package)",
               f"- [Índice do acervo]({base}acervo/indice.json): lista de conjuntos e períodos, em JSON",
               f"- [Mapa]({base}): o globo interativo", ""]
    return "\n".join(linhas)


# ---------- tudo ----------

def gerar(pasta, base, data_dados=None):
    """Escreve as páginas na pasta (a cópia que vai para o ar). Devolve [(caminho, data)] das páginas para o sitemap
    (vazio na prévia)."""
    pasta = Path(pasta)
    F, meta, indice, conjuntos = ler(pasta)
    for C in conjuntos:
        s = pasta / "acervo" / C["id"] / Path(C.get("serie", "serie_uf.csv")).name
        C["_serie_bytes"] = s.stat().st_size if s.exists() else None
    paginas = []

    def grava(rel, texto, data):
        destino = pasta / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
        paginas.append((rel, data))

    if conjuntos:
        grava("dados/index.html", pagina_dados(conjuntos, base, F, indice),
              max(max(p["coletado_em"] for p in C["pacotes"]) for C in conjuntos))
        for C in conjuntos:
            grava(f"dados/{C['id']}/index.html", pagina_conjunto(C, base, F), max(p["coletado_em"] for p in C["pacotes"]))
    grava("metodologia/index.html", pagina_metodologia(F, meta, conjuntos, data_dados), data_dados)
    # estados: só entram no sitemap e no llms.txt quando saírem da prévia
    ests = ler_estados(pasta) if (pasta / "data" / "geo" / "estados.json").exists() else []
    pop = (ler_json(pasta / "data" / "populacao.json").get("valores") or {}) if (pasta / "data" / "populacao.json").exists() else {}
    feitas = len(paginas)
    if ests:
        grava("estados/index.html", pagina_estados(ests, F, pop), data_dados)
        for E in ests:
            grava(f"estados/{E['slug']}/index.html", pagina_estado(E, ests, F, pasta, pop, base), data_dados)
    de_estados = paginas[feitas:]
    if PREVIA_ESTADOS:
        del paginas[feitas:]
    if not PREVIA:
        (pasta / "llms.txt").write_text(llms(F, conjuntos, base, ests), encoding="utf-8")
    print(f"[páginas] {len(paginas)} página(s) geradas{' (prévia: noindex, fora do sitemap, sem llms.txt)' if PREVIA else ''}"
          f"; estados: {len(de_estados)}{' (prévia: noindex, fora do sitemap e do llms.txt)' if PREVIA_ESTADOS else ''}")
    return [] if PREVIA else paginas
