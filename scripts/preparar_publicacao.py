"""Prepara a pasta site/ para ir ao ar: põe o endereço completo do site onde a internet exige.

Regra do projeto (domínio próprio): os links internos são sempre relativos; o endereço completo só aparece onde a
internet exige (robots.txt, sitemap.xml, link canônico, prévia de compartilhamento e dados estruturados para os
buscadores). Ele fica escrito num lugar só, scripts/dados/endereco_do_site.txt, e este script o coloca nesses arquivos
na hora de publicar (passo "Preparar para os buscadores" do .github/workflows/site.yml). Nada disso fica guardado no
repositório: robots.txt e sitemap.xml só existem na cópia publicada, e as páginas continuam com endereços relativos.

O que faz na pasta (por padrão, site/):
1. robots.txt: todos os robôs liberados (buscadores e robôs das IAs) e o endereço do sitemap.
2. sitemap.xml: as páginas que devem aparecer na busca, com a data dos dados (a mesma do selo "Dados atualizados
   em", isto é, a última vez que um robô buscou dados com sucesso). A versão leve (2d/) tem noindex e fica fora.
3. Nas páginas .html, troca o endereço relativo do link canônico e da prévia de compartilhamento (og:url, og:image,
   twitter:image) pelo endereço completo, calculado a partir da posição de cada página.

Uso, na pasta do repositório:
    python scripts/preparar_publicacao.py              (prepara site/)
    python scripts/preparar_publicacao.py --pasta X    (prepara uma cópia, para testar)
Só usa a biblioteca padrão.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import escape

RAIZ = Path(__file__).resolve().parent.parent
ENDERECO = RAIZ / "scripts" / "dados" / "endereco_do_site.txt"
# Páginas que entram no sitemap (caminho dentro de site/). A versão leve (2d/index.html) tem noindex e fica fora.
NA_BUSCA = ["index.html"]
# Tags cujo endereço precisa ser completo: (expressão que acha a tag, atributo com o endereço).
TAGS = [
    (r'<link\b[^>]*\brel="canonical"[^>]*>', "href"),
    (r'<meta\b[^>]*\bproperty="og:url"[^>]*>', "content"),
    (r'<meta\b[^>]*\bproperty="og:image"[^>]*>', "content"),
    (r'<meta\b[^>]*\bname="twitter:image"[^>]*>', "content"),
]


def endereco():
    """O endereço do site, com barra no fim (ex.: https://brasil-em-camadas.github.io/)."""
    linhas = [l.strip() for l in ENDERECO.read_text(encoding="utf-8").splitlines()]
    linhas = [l for l in linhas if l and not l.startswith("#")]
    if len(linhas) != 1 or not re.fullmatch(r"https://[a-z0-9.-]+(/[^\s]*)?", linhas[0]):
        sys.exit(f"[publicação] {ENDERECO.name} precisa ter uma linha só com o endereço (https://...); achei {linhas!r}")
    return linhas[0].rstrip("/") + "/"


def data_dos_dados(pasta):
    """Data (AAAA-MM-DD) da última vez que algum robô buscou dados com sucesso: a mesma regra do selo do site."""
    datas = []
    for f in sorted((pasta / "data").rglob("robo*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if any(str(v).startswith("ok") for v in (d.get("passos") or {}).values()):
            datas.append(str(d.get("rodou_em", ""))[:10])
    datas = [x for x in datas if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)]
    return max(datas) if datas else None


def completar(html, endereco_da_pagina):
    """Troca os endereços relativos das tags de TAGS pelo endereço completo; os que já são completos ficam."""
    trocas = 0

    def na_tag(m, atributo):
        def no_atributo(a):
            nonlocal trocas
            valor = a.group(2)
            if re.match(r"https?://", valor):
                return a.group(0)
            trocas += 1
            return a.group(1) + urljoin(endereco_da_pagina, valor) + a.group(3)
        return re.sub(rf'(\b{atributo}=")([^"]*)(")', no_atributo, m.group(0), count=1)

    for padrao, atributo in TAGS:
        html = re.sub(padrao, lambda m, a=atributo: na_tag(m, a), html)
    return html, trocas


def principal():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pasta", default=str(RAIZ / "site"), help="pasta a preparar (padrão: site/)")
    pasta = Path(ap.parse_args().pasta)
    base = endereco()

    (pasta / "robots.txt").write_text(
        "# Brasil em Camadas: dados públicos, com a fonte, a data e o nível de confiança de cada número.\n"
        "# Todos os robôs são bem-vindos, inclusive os dos buscadores e os das IAs.\n"
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {base}sitemap.xml\n", encoding="utf-8")

    data = data_dos_dados(pasta)
    itens = []
    for p in NA_BUSCA:
        if not (pasta / p).exists():
            sys.exit(f"[publicação] a página {p}, listada em NA_BUSCA, não existe em {pasta}")
        loc = urljoin(base, re.sub(r"(^|/)index\.html$", r"\1", p))
        itens.append(f"  <url>\n    <loc>{escape(loc)}</loc>\n" + (f"    <lastmod>{data}</lastmod>\n" if data else "") + "  </url>\n")
    (pasta / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(itens) + "</urlset>\n", encoding="utf-8")

    total = 0
    for f in sorted(pasta.rglob("*.html")):
        rel = f.relative_to(pasta).as_posix()
        texto = f.read_text(encoding="utf-8")
        novo, trocas = completar(texto, urljoin(base, rel))
        if trocas:
            f.write_text(novo, encoding="utf-8")
            total += trocas
            print(f"[publicação] {rel}: {trocas} endereço(s) completado(s)")
    for p in NA_BUSCA:
        texto = (pasta / p).read_text(encoding="utf-8")
        if not re.search(r'<link\b[^>]*\brel="canonical"[^>]*\bhref="https://', texto):
            print(f"[publicação] aviso: {p} está no sitemap mas não tem link canônico")
    print(f"[publicação] endereço {base}; robots.txt e sitemap.xml ({len(itens)} página(s), dados de {data}); "
          f"{total} endereço(s) completado(s) nas páginas")


if __name__ == "__main__":
    principal()
