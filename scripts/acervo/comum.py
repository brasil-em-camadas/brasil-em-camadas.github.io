"""Parte comum dos robôs do acervo (site/acervo/): grava pacotes, versões, fichas técnicas e índices.

O formato está descrito em site/acervo/README.md. Resumo do que este módulo garante:
- conjunto = um tipo de dado de uma fonte; pacote = um período de um conjunto (pasta site/acervo/<conjunto>/<período>/);
- pacote publicado nunca é apagado nem sobrescrito: se a fonte mudar um número, o pacote atual vai inteiro, sem
  mudar um byte, para <período>/versoes/vN/ e a versão nova entra no lugar, com a nota do que mudou;
- a única mudança permitida num pacote publicado é a situação passar de "preliminar" a "consolidado" na ficha
  (datapackage.json), sem mexer nos dados; o verificador (verificar.py) confere tudo isso antes de publicar;
- tudo é determinístico: rodar duas vezes com os mesmos dados da fonte não muda nenhum arquivo de pacote.
Só usa a biblioteca padrão do Python.
"""
import csv
import hashlib
import io
import json
import os
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ACERVO = RAIZ / "site" / "acervo"
SEDES = RAIZ / "scripts" / "dados" / "sedes_municipais.csv"
FORMATO = "Brasil em Camadas · acervo de dados por período, formato 1 (ver README.md desta pasta)"

UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
      "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
      "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS",
      "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
CODIGO_BRASIL = "1"   # como na SIDRA do IBGE (nível territorial N1)

# Municípios instalados depois de 2010 (os demais já existiam): num ano anterior, ficam fora do pacote
# ("não se aplica"), nunca como zero. Fonte: IBGE (a própria SIDRA só traz dados deles a partir desses anos).
INSTALADO_EM = {"1504752": 2013, "4212650": 2013, "4220000": 2013, "4314548": 2013, "5006275": 2013,  # 5 municípios de 2013
                "5101837": 2025}   # Boa Esperança do Norte (MT), o 5.571º

LICENCA = {"name": "CC-BY-4.0", "title": "Creative Commons Atribuição 4.0 Internacional",
           "path": "https://creativecommons.org/licenses/by/4.0/deed.pt_BR"}
EDITOR = {"title": "Brasil em Camadas", "role": "publisher"}

NIVEIS = ("brasil", "uf", "municipio")
# colunas que identificam a linha: o lugar e, quando o conjunto tem uma lista de itens, o item (lavoura, país)
CHAVES = ("codigo_ibge", "lavoura", "pais")
ARQUIVO = {"brasil": "brasil.csv", "uf": "uf.csv", "municipio": "municipio.csv"}
MARCAS = ["", "X", ".."]   # vazio = sem dado; X = a fonte esconde o número; .. = não se aplica

MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# ---------- datas e períodos ----------

def hoje():
    return datetime.now(timezone.utc).date()


def ultimo_dia(ano, mes):
    return (date(ano + mes // 12, mes % 12 + 1, 1) - date.resolution)


def somar_meses(d, n):
    """Mesmo dia (ou o último do mês) n meses depois."""
    m = d.month - 1 + n
    a, m = d.year + m // 12, m % 12 + 1
    return min(date(a, m, d.day), ultimo_dia(a, m)) if d.day <= 28 else ultimo_dia(a, m)


def periodo(p):
    """'2025' (ano) ou '2026-T1' (trimestre) → dados do período."""
    m = re.fullmatch(r"(\d{4})(?:-T([1-4]))?", p)
    if not m:
        raise ValueError(f"período inválido: {p}")
    ano = int(m.group(1))
    if m.group(2):
        t = int(m.group(2))
        return {"periodo": p, "tipo": "trimestre", "ano": ano, "trimestre": t,
                "inicio": date(ano, 3 * t - 2, 1), "fim": ultimo_dia(ano, 3 * t), "meses": [3 * t - 2, 3 * t - 1, 3 * t],
                "nome": f"{t}º trimestre de {ano}"}
    return {"periodo": p, "tipo": "ano", "ano": ano, "trimestre": None, "inicio": date(ano, 1, 1), "fim": date(ano, 12, 31),
            "meses": list(range(1, 13)), "nome": str(ano)}


def ordem_periodo(p):
    i = periodo(p)
    return (i["ano"], i["trimestre"] or 0)


def situacao(cfg, p, dia=None):
    """Preliminar até 12 meses depois da publicação do período pela fonte; depois, consolidado.
    A publicação conta como o fim do período + o atraso típico da fonte (cfg['atraso_meses'])."""
    fim = periodo(p)["fim"]
    consolida = somar_meses(fim, cfg["atraso_meses"] + 12)
    return ("consolidado" if (dia or hoje()) >= consolida else "preliminar"), consolida.isoformat()


# ---------- municípios ----------

def sedes():
    return {r["codigo_ibge"]: r for r in csv.DictReader(SEDES.open(encoding="utf-8"))}


def municipios_do_ano(ano):
    """Códigos dos municípios que existiam no ano (lista do IBGE menos os instalados depois)."""
    return sorted(c for c in sedes() if INSTALADO_EM.get(c, 0) <= ano)


def gravar_municipios():
    """site/acervo/municipios.csv: códigos, nomes e posição das sedes, guardado uma vez só para todos os conjuntos."""
    linhas = [["codigo_ibge", "nome", "uf", "latitude", "longitude", "existe_desde"]]
    for c, r in sorted(sedes().items()):
        linhas.append([c, r["nome"], r["uf"], r["latitude"], r["longitude"], str(INSTALADO_EM.get(c, ""))])
    b = io.StringIO()
    csv.writer(b, lineterminator="\n").writerows(linhas)
    escrever_se_mudou(ACERVO / "municipios.csv", b.getvalue().encode("utf-8"))


# ---------- células e tabelas ----------

def celula(v, casas=None):
    """Valor de uma célula no CSV: número com ponto decimal; vazio = sem dado; 'X' e '..' passam como estão."""
    if v is None:
        return ""
    if isinstance(v, bool):
        raise TypeError("valor lógico numa tabela")
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v:   # NaN
            return ""
        t = f"{v:.{casas if casas is not None else 6}f}"
        t = t.rstrip("0").rstrip(".") if "." in t else t
        return "0" if t in ("-0", "") else t
    return str(v)


class Campo:
    """Uma coluna: nome (minúsculas, sem acento), tipo (integer, number ou string), título, unidade e descrição.
    nivel = nível de confiança da coluna quando difere do pacote (ex.: conta do projeto)."""

    def __init__(self, nome, tipo, titulo, unidade=None, descricao=None, casas=None, nivel=None):
        if not re.fullmatch(r"[a-z0-9_]+", nome):
            raise ValueError(f"nome de coluna inválido: {nome}")
        self.nome, self.tipo, self.titulo, self.unidade = nome, tipo, titulo, unidade
        self.descricao, self.casas, self.nivel = descricao, casas, nivel

    def ficha(self):
        f = {"name": self.nome, "type": self.tipo, "title": self.titulo}
        if self.descricao:
            f["description"] = self.descricao
        if self.unidade:
            f["unidade"] = self.unidade
        if self.nivel:
            f["nivel"] = self.nivel
        return f


def tabela_csv(campos, linhas):
    """Bytes do CSV (UTF-8, vírgula entre colunas, ponto decimal, uma linha por registro, \\n no fim de cada linha)."""
    b = io.StringIO()
    w = csv.writer(b, lineterminator="\n")
    w.writerow([c.nome for c in campos])
    for l in linhas:
        if isinstance(l, dict):
            l = [l.get(c.nome) for c in campos]
        if len(l) != len(campos):
            raise ValueError("linha com número errado de colunas")
        w.writerow([celula(v, c.casas) for v, c in zip(l, campos)])
    return b.getvalue().encode("utf-8")


def ler_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def sha256(b):
    return "sha256:" + hashlib.sha256(b).hexdigest()


def escrever_se_mudou(caminho, b):
    caminho = Path(caminho)
    if caminho.exists() and caminho.read_bytes() == b:
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_bytes(b)
    os.replace(tmp, caminho)
    return True


def json_bytes(d):
    return (json.dumps(d, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


# ---------- download de arquivo grande ----------

def baixar_grande(url, destino, agente, tentativas=6):
    """Baixa um arquivo grande para o disco. Se a conexão cair, continua de onde parou (pedido de intervalo de bytes)
    e, no fim, confere o tamanho com o que o servidor informou (como no robô da ANAC: sem essa conferência, uma
    conexão cortada passa despercebida, porque o Python devolve "fim do arquivo" sem erro)."""
    import time
    import urllib.request
    destino = Path(destino)
    destino.write_bytes(b"")
    total, erro = None, None
    for i in range(tentativas):
        feito = destino.stat().st_size
        cab = dict(agente)
        if feito:
            cab["Range"] = f"bytes={feito}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=300) as r:
                if feito and r.status != 206:
                    destino.write_bytes(b"")
                    feito = 0
                faixa = r.headers.get("Content-Range") or ""
                if "/" in faixa and faixa.rsplit("/", 1)[1].isdigit():
                    total = int(faixa.rsplit("/", 1)[1])
                elif r.headers.get("Content-Length"):
                    total = feito + int(r.headers["Content-Length"])
                with open(destino, "ab") as f:
                    while bloco := r.read(1 << 20):
                        f.write(bloco)
            if total is None:
                return destino.stat().st_size
        except Exception as e:
            erro = e
        feito = destino.stat().st_size
        if total is not None and feito >= total:
            return feito
        print(f"[acervo] o download parou em {feito / 1e6:.0f} de {(total or 0) / 1e6:.0f} MB; continuando ({erro or 'conexão encerrada'})")
        time.sleep(10 * (i + 1))
    raise ValueError(f"download incompleto: {destino.stat().st_size} de {total} bytes ({erro or 'conexão encerrada'})")


# ---------- números em português (só nas notas para pessoas) ----------

def br(v):
    if v is None or v == "":
        return "vazio"
    try:
        x = float(v)
    except ValueError:
        return str(v)
    if x == int(x) and "." not in str(v):
        return f"{int(x):,}".replace(",", ".")
    return f"{x:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".").rstrip("0").rstrip(",")


# ---------- pacotes ----------

def pasta_conjunto(cfg):
    return ACERVO / cfg["id"]


def ficha_atual(cfg, p):
    arq = pasta_conjunto(cfg) / p / "datapackage.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None


def _chave(campos):
    return [i for i, c in enumerate(campos) if c in CHAVES] or [0]


def rotulo(chave):
    """('35',) → 'SP'; ('4314902', 'soja') → 'Porto Alegre/RS · soja'; ('1',) → 'Brasil'."""
    global _SEDES
    if _SEDES is None:
        _SEDES = sedes()
    cod, resto = chave[0], list(chave[1:])
    if cod == CODIGO_BRASIL:
        nome = "Brasil"
    elif len(cod) == 2 and cod in UF:
        nome = UF[cod]
    else:
        s = _SEDES.get(cod) if _SEDES else None
        nome = f"{s['nome']}/{s['uf']} ({cod})" if s else cod
    return " · ".join([nome] + resto)


_SEDES = None


def diferencas(nome_nivel, antigo, novo, limite=40):
    """Nota do que mudou entre duas tabelas (listas de linhas com cabeçalho). Ex.: 'uf · SP · acessos: 1.234 → 1.240'."""
    ca, cn = antigo[0], novo[0]
    notas = []
    if ca != cn:
        notas.append(f"{nome_nivel}: colunas mudaram ({len(ca)} → {len(cn)})")
    ka, kn = _chave(ca), _chave(cn)
    ia = {tuple(l[i] for i in ka): l for l in antigo[1:]}
    inn = {tuple(l[i] for i in kn): l for l in novo[1:]}
    sai = sorted(set(ia) - set(inn))
    entra = sorted(set(inn) - set(ia))
    if sai:
        notas.append(f"{nome_nivel}: {len(sai)} linha(s) saíram (ex.: {rotulo(sai[0])})")
    if entra:
        notas.append(f"{nome_nivel}: {len(entra)} linha(s) entraram (ex.: {rotulo(entra[0])})")
    mud = []
    for k in sorted(set(ia) & set(inn)):
        a, n = dict(zip(ca, ia[k])), dict(zip(cn, inn[k]))
        for c in cn:
            if c in ca and a.get(c) != n.get(c):
                mud.append(f"{nome_nivel} · {rotulo(k)} · {c}: {br(a.get(c))} → {br(n.get(c))}")
    if mud:
        notas += mud[:limite]
        if len(mud) > limite:
            notas.append(f"{nome_nivel}: mais {len(mud) - limite} célula(s) mudaram (total {len(mud)})")
    return notas


def gravar_pacote(cfg, p, tabelas, extra):
    """Grava o pacote do período p, se ele for novo ou se os dados mudaram (aí entra uma versão nova).

    tabelas: {nível: (campos, linhas)} com nível em brasil, uf, municipio.
    extra: o que é próprio deste período: coletado_em, consulta (endereço exato usado), avisos (lista), metodo (texto a
    mais), itens (lista dos itens do período, ex.: lavouras pesquisadas), nivel (de confiança, se diferente do conjunto).
    Devolve 'novo', 'igual' ou 'versão N'."""
    info = periodo(p)
    pasta = pasta_conjunto(cfg) / p
    bytes_novos = {n: tabela_csv(*tabelas[n]) for n in NIVEIS if n in tabelas}
    atual = ficha_atual(cfg, p)
    versao, mudancas = 1, []
    if atual:
        iguais = (set(r["name"] for r in atual["resources"]) == set(bytes_novos)
                  and all((pasta / ARQUIVO[n]).read_bytes() == b for n, b in bytes_novos.items()))
        if iguais:
            return "igual"
        versao = atual["versao"] + 1
        for n in NIVEIS:
            velho = ler_csv(pasta / ARQUIVO[n]) if (pasta / ARQUIVO[n]).exists() and n in [r["name"] for r in atual["resources"]] else None
            novo = list(csv.reader(io.StringIO(bytes_novos[n].decode("utf-8")))) if n in bytes_novos else None
            if velho and novo:
                mudancas += diferencas(n, velho, novo)
            elif velho:
                mudancas.append(f"{n}: a tabela saiu")
            elif novo:
                mudancas.append(f"{n}: a tabela entrou")
        # a versão atual vai inteira, sem mudar um byte, para versoes/vN/
        destino = pasta / "versoes" / f"v{atual['versao']}"
        if destino.exists():
            raise RuntimeError(f"{destino} já existe")
        destino.mkdir(parents=True)
        for r in atual["resources"]:
            os.replace(pasta / r["path"], destino / r["path"])
        os.replace(pasta / "datapackage.json", destino / "datapackage.json")
    sit, consolida = situacao(cfg, p)
    recursos = []
    for n, b in bytes_novos.items():
        campos = tabelas[n][0]
        recursos.append({
            "name": n, "path": ARQUIVO[n], "profile": "tabular-data-resource", "title": cfg["niveis"][n],
            "format": "csv", "mediatype": "text/csv", "encoding": "utf-8", "bytes": len(b), "hash": sha256(b),
            "dialect": {"delimiter": ",", "header": True},
            "schema": {"fields": [c.ficha() for c in campos], "missingValues": MARCAS,
                       "primaryKey": [c.nome for c in campos if c.nome in CHAVES]},
            "linhas": len(tabelas[n][1])})
    ficha = {
        "profile": "tabular-data-package",
        "name": f"{cfg['id']}-{p.lower()}",
        "title": f"{cfg['titulo']} · {info['nome']}",
        "description": cfg["descricao"],
        "version": f"{versao}.0.0",
        "periodo": p, "tipo_de_periodo": info["tipo"], "inicio": info["inicio"].isoformat(), "fim": info["fim"].isoformat(),
        "situacao": sit, "consolida_em": consolida, "versao": versao,
        "coletado_em": extra["coletado_em"],
        "fonte": {**cfg["fonte"], "consulta": extra.get("consulta") or cfg["fonte"].get("consulta")},
        "nivel_confianca": extra.get("nivel") or cfg["nivel"],
        "medida": cfg["medida"],
        "metodo": cfg["metodo"] + ((" " + extra["metodo"]) if extra.get("metodo") else ""),
        "avisos": list(cfg.get("avisos", [])) + list(extra.get("avisos", [])),
        "marcas": {"numero": "valor (0 é zero de verdade)", "vazio": "sem dado", "X": "a fonte esconde o número",
                   "..": "não se aplica"},
        "licenses": [LICENCA],
        "licenca_da_fonte": cfg["fonte"].get("licenca"),
        "sources": [{"title": cfg["fonte"]["titulo"], "path": extra.get("consulta") or cfg["fonte"].get("consulta")}],
        "contributors": [EDITOR],
        "formato": FORMATO,
    }
    if extra.get("itens"):
        ficha["itens"] = extra["itens"]
    if mudancas:
        ficha["mudancas"] = {"desde_a_versao": versao - 1, "notas": mudancas}
    ficha["resources"] = recursos
    pasta.mkdir(parents=True, exist_ok=True)
    for n, b in bytes_novos.items():
        escrever_se_mudou(pasta / ARQUIVO[n], b)
    escrever_se_mudou(pasta / "datapackage.json", json_bytes(ficha))
    return "novo" if versao == 1 else f"versão {versao}"


def consolidar(cfg, dia=None):
    """Passa a 'consolidado' os pacotes preliminares que já passaram do prazo (só a ficha muda; os dados não)."""
    feitos = []
    for pasta in sorted(pasta_conjunto(cfg).glob("*/datapackage.json")):
        f = json.loads(pasta.read_text(encoding="utf-8"))
        if f["situacao"] == "preliminar" and situacao(cfg, f["periodo"], dia)[0] == "consolidado":
            f["situacao"] = "consolidado"
            f["consolidado_em"] = (dia or hoje()).isoformat()
            escrever_se_mudou(pasta, json_bytes(f))
            feitos.append(f["periodo"])
    return feitos


# ---------- conjunto.json, serie_uf.csv e indice.json ----------

def pacotes(cfg):
    base = pasta_conjunto(cfg)
    ps = [d.name for d in base.iterdir() if d.is_dir() and re.fullmatch(r"\d{4}(-T[1-4])?", d.name)] if base.exists() else []
    return sorted(ps, key=ordem_periodo)


def atualizar_conjunto(cfg, conferido_em=None, estado=None):
    """Refaz conjunto.json e serie_uf.csv a partir das pastas dos pacotes, e depois o indice.json.
    estado: o que o robô precisa lembrar da fonte entre uma execução e outra (ex.: data e CRC de cada arquivo)."""
    base = pasta_conjunto(cfg)
    velho = json.loads((base / "conjunto.json").read_text(encoding="utf-8")) if (base / "conjunto.json").exists() else {}
    lista, colunas = [], {}
    serie_campos, serie = None, []
    com_dado = {}   # período → colunas com pelo menos um número nos estados (para o campo sem_dado; o site lê daqui)
    for p in pacotes(cfg):
        fb = (base / p / "datapackage.json").read_bytes()
        f = json.loads(fb)
        antigas = []
        for v in sorted((base / p / "versoes").glob("v*/datapackage.json"), key=lambda x: int(x.parent.name[1:])):
            vb = v.read_bytes()
            antigas.append({"versao": json.loads(vb)["versao"], "ficha": f"{p}/versoes/{v.parent.name}/datapackage.json",
                            "hash": sha256(vb), "bytes": len(vb)})
        lista.append({"periodo": p, "tipo": f["tipo_de_periodo"], "versao": f["versao"], "situacao": f["situacao"],
                      "consolida_em": f["consolida_em"], "coletado_em": f["coletado_em"],
                      "niveis": [r["name"] for r in f["resources"]], "ficha": f"{p}/datapackage.json",
                      "hash": sha256(fb), "bytes": len(fb) + sum(r["bytes"] for r in f["resources"]),
                      "versoes_antigas": antigas})
        for r in f["resources"]:
            for c in r["schema"]["fields"]:
                colunas.setdefault(c["name"], {k: c[k] for k in ("name", "type", "title", "unidade", "description") if k in c})
        # série por estado (e Brasil), só a versão atual de cada pacote
        for n in ("brasil", "uf"):
            if n not in [r["name"] for r in f["resources"]]:
                continue
            t = ler_csv(base / p / ARQUIVO[n])
            cab = t[0]
            if n == "uf":
                com_dado[p] = {c for i, c in enumerate(cab) if any(len(l) > i and l[i] not in MARCAS for l in t[1:])}
            if serie_campos is None:
                serie_campos = []
            for c in cab:
                if c not in serie_campos:
                    serie_campos.append(c)
            filtro = cfg.get("serie_filtro") or {}   # ex.: {"pais": "total"}: só as linhas de total na série
            for l in t[1:]:
                d = dict(zip(cab, l))
                if any(d.get(k) != v for k, v in filtro.items()):
                    continue
                if n == "brasil":
                    d["uf"] = "BR"
                d["periodo"] = p
                serie.append(d)
    # sem_dado: colunas numéricas do conjunto sem nenhum número nos estados naquele período (ausentes do pacote ou só
    # com marcas), para o seletor de período do mapa não oferecer um período vazio (ex.: valor antes de 1994)
    numericas = [c["name"] for c in colunas.values() if c.get("type") in ("integer", "number")]
    for e in lista:
        e["sem_dado"] = [c for c in numericas if c not in com_dado.get(e["periodo"], set())]
    conj = {"formato": FORMATO, "id": cfg["id"], "titulo": cfg["titulo"], "descricao": cfg["descricao"],
            "fonte": cfg["fonte"], "nivel_confianca": cfg["nivel"], "periodicidade": cfg["periodicidade"],
            "medida": cfg["medida"], "como_vira_ano": cfg["como_vira_ano"], "niveis": cfg["niveis"],
            "consolidacao": f"preliminar até 12 meses depois da publicação do período; a publicação conta como o fim do "
                            f"período + {cfg['atraso_meses']} meses (o atraso típico da fonte)",
            "metodo": cfg["metodo"], "avisos": cfg.get("avisos", []),
            **({"quebras": cfg["quebras"]} if cfg.get("quebras") else {}),
            **({"palavras_chave": cfg["palavras_chave"]} if cfg.get("palavras_chave") else {}), "licenca": LICENCA,
            "licenca_da_fonte": cfg["fonte"].get("licenca"),
            "conferido_em": conferido_em or velho.get("conferido_em"),
            "colunas": list(colunas.values()), "serie": "serie_uf.csv", "pacotes": lista}
    if estado is not None or velho.get("estado_da_fonte"):
        conj["estado_da_fonte"] = estado if estado is not None else velho["estado_da_fonte"]
    escrever_se_mudou(base / "conjunto.json", json_bytes(conj))
    if serie_campos:
        chave = ["periodo", "codigo_ibge", "uf"]
        # ordem das colunas: a do pacote mais recente; colunas que só existiram antes vão para o fim
        ordem = []
        for p in reversed(pacotes(cfg)):
            arq = base / p / ARQUIVO["uf"]
            if arq.exists():
                for c in ler_csv(arq)[0]:
                    if c not in ordem:
                        ordem.append(c)
        campos = chave + [c for c in ordem + serie_campos if c not in chave]
        campos = list(dict.fromkeys(campos))
        serie.sort(key=lambda d: (ordem_periodo(d["periodo"]), d["codigo_ibge"] != CODIGO_BRASIL, d["codigo_ibge"], d.get("lavoura", ""), d.get("pais", "")))
        b = io.StringIO()
        w = csv.writer(b, lineterminator="\n")
        w.writerow(campos)
        for d in serie:
            w.writerow([d.get(c, "") for c in campos])
        escrever_se_mudou(base / "serie_uf.csv", b.getvalue().encode("utf-8"))
    atualizar_indice()
    return conj


def atualizar_indice():
    gravar_municipios()
    conjuntos = []
    for arq in sorted(ACERVO.glob("*/conjunto.json")):
        c = json.loads(arq.read_text(encoding="utf-8"))
        ps = [x["periodo"] for x in c["pacotes"]]
        conjuntos.append({"id": c["id"], "titulo": c["titulo"], "fonte": c["fonte"]["orgao"], "pasta": f"{c['id']}/",
                          "periodicidade": c["periodicidade"], "niveis": c["niveis"],
                          "anos": [p for p in ps if "-T" not in p], "trimestres": [p for p in ps if "-T" in p],
                          "mais_recente": max(ps, key=ordem_periodo) if ps else None, "conferido_em": c.get("conferido_em")})
    escrever_se_mudou(ACERVO / "indice.json", json_bytes({
        "formato": FORMATO, "licenca": LICENCA, "municipios": "municipios.csv", "conjuntos": conjuntos}))


def registrar(cfg, resultados):
    """Resumo da execução (aparece no registro do GitHub)."""
    por = {}
    for p, r in resultados.items():
        por.setdefault(r, []).append(p)
    for r, ps in por.items():
        print(f"[acervo/{cfg['id']}] {r}: {len(ps)} pacote(s) ({', '.join(ps[:6])}{'…' if len(ps) > 6 else ''})")
