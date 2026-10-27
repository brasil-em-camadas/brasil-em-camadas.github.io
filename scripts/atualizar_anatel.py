"""Atualiza a telefonia e a internet do mapa (Anatel): celular por estado e por município, 5G, velocidade medida e banda larga fixa.

Fontes: dados abertos da Anatel (licença CC-BY), listados no Portal Brasileiro de Dados Abertos (dados.gov.br):
1. Índice Brasileiro de Conectividade (IBC), atualizado uma vez por ano:
   https://www.anatel.gov.br/dadosabertos/paineis_de_dados/meu_municipio/ibc.zip
   - IBC_UF_indicadores_originais.csv (por estado) e IBC_municipios_indicadores_originais.csv (por município);
   - "Cobertura Pop. 4G5G": parte dos moradores coberta pelo sinal 4G ou 5G. É uma estimativa da Anatel feita com as
     antenas licenciadas das operadoras e um modelo de propagação do sinal (não é medição no local);
   - "Fibra" (por estado): parte dos municípios com rede de fibra óptica de transporte (backhaul);
   - "Adensamento Estações" (por estado): estações rádio base (antenas de celular) por 10 mil habitantes.
2. Presença da telefonia móvel (RQUAL), atualizada todo mês:
   https://www.anatel.gov.br/dadosabertos/paineis_de_dados/infraestrutura/smp_mun_atendidos.zip
   - Tabela_Municipios_Atendidos_SMP_v2.csv: para cada mês, operadora, município e tecnologia (2G a 5G), "SIM" ou "NÃO".
3. Medidas de velocidade da telefonia móvel (RQUAL, indicador IND4), um trimestre por vez (≈ 1 GB):
   https://www.anatel.gov.br/dadosabertos/paineis_de_dados/qualidade/medidas_qoe_smp.zip
   - Dados_QoE.csv: cada teste de velocidade (download e upload, em Mbps), feito no celular de quem tem o programa de
     medição instalado e autorizou os testes, com operadora, tecnologia (3G, 4G, 5G) e município. Aqui viram medianas
     (metade dos testes deu mais, metade deu menos) por município, estado e Brasil. Se o arquivo da Anatel for o mesmo
     da última vez (mesmo tamanho e data), o robô nem baixa.
4. Meu Município, cobertura da telefonia móvel, uma vez por ano:
   https://www.anatel.gov.br/dadosabertos/paineis_de_dados/meu_municipio/meu_municipio.zip
   - Meu_Municipio_Cobertura.csv: "% moradores cobertos" por operadora e tecnologia. É previsão da Anatel (antenas
     licenciadas + modelo de propagação ITU-R P.1812-5 + setores do Censo 2010), não medição. Aqui: o 5G.
5. Acessos da banda larga fixa, todo mês (≈ 1 GB; o robô lê só os dois arquivos de dentro do zip que usa, por pedidos
   de intervalo de bytes):
   https://www.anatel.gov.br/dadosabertos/paineis_de_dados/acessos/acessos_banda_larga_fixa.zip
   - Densidade_Banda_Larga_Fixa.csv: acessos por 100 habitantes (Brasil, estado, município), a conta oficial da Anatel;
   - Acessos_Banda_Larga_Fixa_<ano>.csv: cada linha = empresa, município, meio de acesso, velocidade contratada, acessos.
   O último mês costuma chegar incompleto (as empresas pequenas informam depois); por isso vale o mês mais recente que
   tenha pelo menos 99% da densidade do Brasil no mês anterior.

Roda sozinho no GitHub Actions (site.yml), junto com os outros robôs, e também à mão:
    python scripts/atualizar_anatel.py
    python scripts/atualizar_anatel.py --cache PASTA   (PASTA com os arquivos já baixados: ibc.zip, smp_mun_atendidos.zip,
        medidas_qoe_smp.zip, meu_municipio.zip, Densidade_Banda_Larga_Fixa.csv e Acessos_Banda_Larga_Fixa_<ano>.csv)
    python scripts/atualizar_anatel.py --so velocidade,banda_larga   (só alguns passos)
Só usa a biblioteca padrão. Se a Anatel falhar ou mandar algo incompleto, os arquivos antigos ficam.
Saídas em site/data/celular/ (a pasta guarda tudo o que vem da Anatel, inclusive a banda larga fixa):
  estados.json          pintura dos estados e ficha (IBC) + quantos municípios de cada estado têm 5G (RQUAL)
  municipios.json       sinal 4G/5G de cada município, no ponto da sede (IBC)
  5g.json               municípios com 5G e as operadoras, no ponto da sede (RQUAL)
  velocidade.json       velocidade medida no celular, por município (mediana dos testes)
  velocidade_uf.json    a mesma coisa por estado e no Brasil (pintura e ficha)
  cobertura_5g.json     moradores com sinal 5G (previsão), por município
  cobertura_5g_uf.json  a mesma coisa por estado e no Brasil, ponderada pela população do Censo 2022
  banda_larga.json      banda larga fixa por município (densidade, fibra, velocidade contratada, empresas)
  banda_larga_uf.json   a mesma coisa por estado e no Brasil
  robo.json             resultado de cada passo
"""
import argparse
import array
import csv
import io
import json
import re
import shutil
import struct
import sys
import tempfile
import time
import urllib.request
import zipfile
import zlib
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "data" / "celular"
SEDES = RAIZ / "scripts" / "dados" / "sedes_municipais.csv"
POPULACAO = RAIZ / "site" / "data" / "luzes" / "municipios.json"   # Censo 2022 por município (atualizar_ibge.py)
BASE = "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/"
IBC_ZIP, RQUAL_ZIP = "meu_municipio/ibc.zip", "infraestrutura/smp_mun_atendidos.zip"
VEL_ZIP, MM_ZIP, BL_ZIP = "qualidade/medidas_qoe_smp.zip", "meu_municipio/meu_municipio.zip", "acessos/acessos_banda_larga_fixa.zip"
CATALOGO = {"ibc": "https://dados.gov.br/dados/conjuntos-dados/meu-municipio---indice-brasileiro-de-conectividade",
            "rqual": "https://dados.gov.br/dados/conjuntos-dados/infraestrutura---presenca-da-telefonia-movel---rqual"}
CATALOGO_VEL = "https://dados.gov.br/dados/conjuntos-dados/qualidade---medidas-de-velocidade---telefonia-movel"
CATALOGO_MM = "https://dados.gov.br/dados/conjuntos-dados/meu-municipio---acessos-e-cobertura-de-telecomunicacoes"
CATALOGO_BL = ["https://dados.gov.br/dados/conjuntos-dados/acessos---banda-larga-fixa-densidade-por-100-habitantes",
               "https://dados.gov.br/dados/conjuntos-dados/acessos---banda-larga-fixa"]
UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
      "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
      "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS",
      "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
OPERADORAS = {"CLARO": "Claro", "VIVO": "Vivo", "TIM": "TIM", "OI": "Oi", "ALGAR": "Algar", "BRISANET": "Brisanet",
              "UNIFIQUE": "Unifique", "SERCOMTEL": "Sercomtel", "SUMICITY": "Sumicity", "IEZ": "IEZ!", "NEXTEL": "Nextel", "LIGUE": "Ligue"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
FONTE_IBC = "Anatel, Índice Brasileiro de Conectividade (IBC)"
FONTE_RQUAL = "Anatel, presença da telefonia móvel nos municípios (RQUAL)"
NOTA = ("estimativa da Anatel a partir das antenas licenciadas e de um modelo de propagação do sinal, "
        "não medição no local; moradores cobertos pelo sinal 4G ou 5G de qualquer operadora")
AGENTE = {"User-Agent": "Mozilla/5.0 (compatible; brasil-em-camadas; dados abertos)"}
POSICAO = "sede de cada município (IBGE, Localidades do Brasil 2022)"


def baixar(caminho, cache):
    if cache:
        return (Path(cache) / Path(caminho).name).read_bytes()
    for i in range(4):
        try:
            req = urllib.request.Request(BASE + caminho, headers=AGENTE)
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception:
            if i == 3:
                raise
            time.sleep(10 * (i + 1))


def tabela(z, nome):
    """Lê um CSV da Anatel (UTF-8 com BOM, separado por ponto e vírgula) de dentro do zip."""
    return csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="utf-8-sig", newline=""), delimiter=";")


def numero(t):
    t = (t or "").strip()
    return float(t.replace(".", "").replace(",", ".")) if t.count(",") == 1 and t.count(".") >= 1 else (float(t.replace(",", ".")) if t else None)


def sedes():
    return {r["codigo_ibge"]: r for r in csv.DictReader(SEDES.open(encoding="utf-8"))}


def ler(nome):
    try:
        return json.loads((SAIDA / nome).read_text(encoding="utf-8"))
    except Exception:
        return None


def gravar(nome, dados):
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / nome).write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def r1(x):
    return None if x is None else round(x, 1)


def mes_ano(ano, mes):
    return f"{MESES[mes - 1]}/{ano}"


# ---------- arquivos grandes: cabeçalho, download para o disco e leitura de um arquivo de dentro de um zip remoto ----------

def cabecalho(caminho):
    """Tamanho e data do arquivo na Anatel, sem baixar (para saber se mudou desde a última vez)."""
    req = urllib.request.Request(BASE + caminho, headers=AGENTE, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return {"tamanho": int(r.headers.get("Content-Length") or 0), "modificado": r.headers.get("Last-Modified") or ""}


def baixar_para(caminho, destino):
    for i in range(4):
        try:
            req = urllib.request.Request(BASE + caminho, headers=AGENTE)
            with urllib.request.urlopen(req, timeout=300) as r, open(destino, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 22)
            return destino
        except Exception:
            if i == 3:
                raise
            time.sleep(15 * (i + 1))


def faixa(url, a, b):
    """Bytes de a até b (inclusive) do arquivo remoto; o servidor precisa aceitar pedidos por intervalo (206)."""
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={**AGENTE, "Range": f"bytes={a}-{b}"})
            with urllib.request.urlopen(req, timeout=300) as r:
                if r.status != 206:
                    raise RuntimeError(f"o servidor não aceitou pedido por intervalo (status {r.status})")
                return r.read()
        except RuntimeError:
            raise
        except Exception:
            if i == 3:
                raise
            time.sleep(10 * (i + 1))


def membros_remotos(url):
    """Lista os arquivos de dentro de um zip remoto lendo só o fim dele (diretório central; aceita ZIP64).
    Devolve {nome: (posição do cabeçalho local, tamanho comprimido, método)}."""
    req = urllib.request.Request(url, headers=AGENTE, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        tam = int(r.headers["Content-Length"])
    fim = faixa(url, max(0, tam - 70000), tam - 1)
    i = fim.rfind(b"PK\x05\x06")
    if i < 0:
        raise ValueError("fim do zip não encontrado")
    n, cd_tam, cd_off = struct.unpack("<HII", fim[i + 10:i + 20])
    if 0xFFFFFFFF in (cd_tam, cd_off) or n == 0xFFFF:
        j = fim.rfind(b"PK\x06\x06")
        n, cd_tam, cd_off = struct.unpack("<QQQ", fim[j + 32:j + 56])
    cd = faixa(url, cd_off, cd_off + cd_tam - 1)
    p, membros = 0, {}
    while p + 46 <= len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        metodo = struct.unpack("<H", cd[p + 10:p + 12])[0]
        csize, usize = struct.unpack("<II", cd[p + 20:p + 28])
        nlen, xlen, clen = struct.unpack("<HHH", cd[p + 28:p + 34])
        off = struct.unpack("<I", cd[p + 42:p + 46])[0]
        nome = cd[p + 46:p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen:p + 46 + nlen + xlen]
        if 0xFFFFFFFF in (csize, usize, off):
            q = 0
            while q + 4 <= len(extra):
                hid, hl = struct.unpack("<HH", extra[q:q + 4])
                if hid == 1:
                    vals, k = list(struct.unpack("<" + "Q" * (hl // 8), extra[q + 4:q + 4 + hl // 8 * 8])), 0
                    if usize == 0xFFFFFFFF:
                        usize, k = vals[k], k + 1
                    if csize == 0xFFFFFFFF:
                        csize, k = vals[k], k + 1
                    if off == 0xFFFFFFFF:
                        off = vals[k]
                q += 4 + hl
        membros[nome] = (off, csize, metodo)
        p += 46 + nlen + xlen + clen
    return membros


def linhas_remotas(url, membro):
    """Lê, em pedaços, um arquivo de dentro de um zip remoto e devolve as linhas (bytes), sem gravar no disco."""
    off, csize, metodo = membro
    h = faixa(url, off, off + 29)
    if h[:4] != b"PK\x03\x04" or metodo not in (0, 8):
        raise ValueError("arquivo de dentro do zip em formato inesperado")
    nlen, xlen = struct.unpack("<HH", h[26:30])
    ini, fim = off + 30 + nlen + xlen, off + 30 + nlen + xlen + csize
    d = zlib.decompressobj(-15) if metodo == 8 else None
    resto, pos, passo = b"", ini, 16 << 20
    while pos < fim:
        bloco = faixa(url, pos, min(fim, pos + passo) - 1)
        pos += len(bloco)
        dados = resto + (d.decompress(bloco) if d else bloco)
        partes = dados.split(b"\n")
        resto = partes.pop()
        yield from partes
    if d:
        resto += d.flush()
    if resto:
        yield from resto.split(b"\n")


def linhas_locais(arquivo):
    with open(arquivo, "rb") as f:
        for linha in io.BufferedReader(f, 1 << 22):
            yield linha.rstrip(b"\n")


def leitor(linhas):
    """Transforma linhas (bytes) de um CSV da Anatel em dicionários, como o csv.DictReader."""
    texto = (l.decode("utf-8-sig" if i == 0 else "utf-8", "replace").rstrip("\r") for i, l in enumerate(linhas))
    return csv.DictReader(texto, delimiter=";")


# ---------- IBC e RQUAL ----------

def ibc(cache):
    """Pintura dos estados e camada por município, do IBC (último ano com os 27 estados completos)."""
    z = zipfile.ZipFile(io.BytesIO(baixar(IBC_ZIP, cache)))
    uf = [r for r in tabela(z, "IBC_UF_indicadores_originais.csv") if (r.get("UF") or "").strip() in UF.values()]
    anos = sorted({r["Ano"] for r in uf if r["Ano"].isdigit()})
    ano = next(a for a in reversed(anos) if sum(1 for r in uf if r["Ano"] == a and numero(r["Cobertura Pop. 4G5G"]) is not None) == 27)
    valores = {}
    for r in uf:
        if r["Ano"] != ano:
            continue
        cob, fibra, erb, ind = (numero(r[k]) for k in ("Cobertura Pop. 4G5G", "Fibra", "Adensamento Estações", "IBC"))
        if not 0 < cob <= 1:
            raise ValueError(f"cobertura fora do esperado em {r['UF']}: {r['Cobertura Pop. 4G5G']}")
        valores[r["UF"].strip()] = {"valor": round(cob * 100, 1), "ibc": ind, "fibra": round(fibra * 100) if fibra is not None else None,
                                    "erb_10mil": round(erb, 1) if erb is not None else None}
    s = sedes()
    mun = []
    for r in tabela(z, "IBC_municipios_indicadores_originais.csv"):
        if r["Ano"] != ano:
            continue
        k, cob = r["Código Município"].strip(), numero(r["Cobertura Pop. 4G5G"])
        if k in s and cob is not None:
            mun.append([round(float(s[k]["longitude"]), 4), round(float(s[k]["latitude"]), 4), round(cob * 100, 1), s[k]["nome"], UF[k[:2]], k])
    if len(mun) < 5500:
        raise ValueError(f"só {len(mun)} municípios no IBC {ano}")
    mun.sort(key=lambda m: -m[2])   # os de sinal mais fraco por último: ficam desenhados por cima
    hoje = date.today().isoformat()
    fx = {"95% ou mais": sum(m[2] >= 95 for m in mun), "80 a 95%": sum(80 <= m[2] < 95 for m in mun),
          "50 a 80%": sum(50 <= m[2] < 80 for m in mun), "menos de 50%": sum(m[2] < 50 for m in mun)}
    gravar("municipios.json", {
        "meta": {"titulo": "Sinal 4G/5G por município", "referencia": ano, "fonte": FONTE_IBC + f" {ano}: população coberta por 4G ou 5G",
                 "nota": NOTA, "posicao": POSICAO, "nivel": "api",
                 "atualizado_em": hoje, "consulta": BASE + IBC_ZIP, "catalogo": CATALOGO["ibc"], "faixas": fx},
        "campos": ["lon", "lat", "cobertura_4g5g_pct", "nome", "uf", "codigo_ibge"], "municipios": mun})
    print(f"[celular] IBC {ano}: 27 estados, {len(mun)} municípios; faixas {fx}")
    return {"referencia": ano, "atualizado_em": hoje, "valores": valores}


def rqual(cache):
    """Municípios com 5G no último mês da tabela de presença da telefonia móvel."""
    z = zipfile.ZipFile(io.BytesIO(baixar(RQUAL_ZIP, cache)))
    ultimo, d = (0, 0), {}   # a tabela traz todos os meses desde 2013: guarda só o mais recente
    for r in tabela(z, "Tabela_Municipios_Atendidos_SMP_v2.csv"):
        m, a = r["Período"].strip().split("/")
        p = (int(a), int(m))
        if p < ultimo:
            continue
        if p > ultimo:
            ultimo, d = p, {}
        cod = r["Código IBGE"].strip()
        d.setdefault(cod, set())
        if r["Tecnologia"].strip() == "5G" and r["Presença"].strip().upper() == "SIM":
            d[cod].add(OPERADORAS.get(r["Operadora"].strip().upper(), r["Operadora"].strip().title()))
    ano, mes = ultimo
    if len(d) < 5500:
        raise ValueError(f"só {len(d)} municípios em {mes:02d}/{ano}")
    s = sedes()
    lista = [[round(float(s[k]["longitude"]), 4), round(float(s[k]["latitude"]), 4), s[k]["nome"], UF[k[:2]], ", ".join(sorted(ops)), k]
             for k, ops in d.items() if ops and k in s]
    lista.sort(key=lambda m: (m[3], m[2]))
    por_uf = {u: [0, 0] for u in UF.values()}
    for k, ops in d.items():
        u = UF.get(k[:2])
        if u:
            por_uf[u][1] += 1
            por_uf[u][0] += bool(ops)
    referencia, hoje = mes_ano(ano, mes), date.today().isoformat()
    gravar("5g.json", {
        "meta": {"titulo": "5G nos municípios", "referencia": referencia, "fonte": FONTE_RQUAL, "nivel": "api", "atualizado_em": hoje,
                 "nota": "município onde a Anatel registra o 5G presente, de pelo menos uma operadora; não quer dizer sinal em todo o município",
                 "posicao": POSICAO, "consulta": BASE + RQUAL_ZIP,
                 "catalogo": CATALOGO["rqual"], "municipios": len(lista), "total": len(d)},
        "campos": ["lon", "lat", "nome", "uf", "operadoras_5g", "codigo_ibge"], "municipios": lista})
    print(f"[celular] RQUAL {referencia}: 5G em {len(lista)} de {len(d)} municípios")
    return {"referencia": referencia, "atualizado_em": hoje, "municipios": len(lista), "total": len(d), "por_uf": por_uf}


def estados(r_ibc, r_rqual):
    """Junta as duas fontes num só arquivo para a pintura e a ficha. A parte que falhou fica como estava."""
    antigo = ler("estados.json") or {}
    base = r_ibc or ({"referencia": antigo["referencia"], "atualizado_em": antigo["atualizado_em"], "valores": antigo["valores"]}
                     if antigo.get("valores") else None)
    if not base:
        return False
    g5 = ({k: v for k, v in r_rqual.items() if k != "por_uf"} if r_rqual else antigo.get("cinco_g"))
    por_uf = r_rqual["por_uf"] if r_rqual else {u: v.get("g5") for u, v in antigo.get("valores", {}).items()}
    valores = {u: {**v, "g5": por_uf.get(u)} for u, v in base["valores"].items()}
    for v in valores.values():   # parte dos municípios do estado com 5G (pintura "Celular 5G")
        g = v.get("g5")
        v["g5_pct"] = round(g[0] / g[1] * 100, 1) if g and g[1] else None
    gravar("estados.json", {
        "titulo": "Sinal de celular 4G/5G", "unidade": "% da população com sinal", "referencia": base["referencia"],
        "fonte": FONTE_IBC + f" {base['referencia']}", "nivel": "api", "atualizado_em": base["atualizado_em"], "nota": NOTA,
        "consulta": [BASE + IBC_ZIP, BASE + RQUAL_ZIP], "catalogo": list(CATALOGO.values()),
        "campos": {"valor": "% dos moradores com sinal 4G ou 5G", "ibc": "Índice Brasileiro de Conectividade (0 a 100)",
                   "fibra": "% dos municípios com fibra óptica de transporte (backhaul)", "erb_10mil": "antenas (estações rádio base) por 10 mil habitantes",
                   "g5": "[municípios com 5G, municípios do estado]", "g5_pct": "% dos municípios do estado com 5G"},
        "cinco_g": g5, "valores": valores})
    return True


# ---------- velocidade medida no celular (RQUAL, IND4) ----------

NB = 30000   # histogramas de 0,1 Mbps, até 3.000 Mbps (o que passar disso fica na última casa)


def _hist():
    return array.array("q", bytes(8 * (NB + 1)))


def _mediana_hist(h):
    tot = sum(h)
    if not tot:
        return None
    acc = 0
    for i, c in enumerate(h):
        acc += c
        if acc * 2 >= tot:
            return round((i + 0.5) / 10, 1)


def _mediana(a):
    s = sorted(a)
    n = len(s)
    return round((s[(n - 1) // 2] + s[n // 2]) / 2, 1) if n else None


def velocidade(cache):
    """Mediana da velocidade medida no celular (download e upload) por município, estado e Brasil, no trimestre que a
    Anatel publica. Cada linha do arquivo é um teste; as velocidades de cada município ficam guardadas (4 bytes cada),
    as de estado e Brasil em histogramas de 0,1 Mbps."""
    antigo = ler("velocidade.json")
    tmp = None
    if cache:
        arq, cab = Path(cache) / Path(VEL_ZIP).name, None
    else:
        cab = cabecalho(VEL_ZIP)
        if antigo and antigo.get("meta", {}).get("arquivo") == cab and (SAIDA / "velocidade_uf.json").exists():
            print("[celular] velocidade: o arquivo da Anatel é o mesmo da última vez; ficam os números atuais")
            return "sem novidade"
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.close()
        arq = Path(tmp.name)
    try:
        if tmp:
            baixar_para(VEL_ZIP, tmp.name)
        t0 = time.time()
        arr, sub = {}, {}
        hist, hsub = {}, {}
        periodos, n, fora = set(), 0, 0
        with zipfile.ZipFile(arq) as z:
            nome = next(m for m in z.namelist() if m.lower().endswith(".csv"))
            f = io.BufferedReader(z.open(nome), buffer_size=1 << 22)
            col = {c: k for k, c in enumerate(f.readline().decode("utf-8-sig").strip().split(";"))}
            iP, iO, iC, iT, iD, iS = (col[c] for c in ("PERIODO", "PRESTADORA", "CODIGO IBGE", "TECNOLOGIA", "VELOCIDADE_DOWNLOAD", "VELOCIDADE_UPLOAD"))
            ultimo = None
            for linha in f:
                c = linha.rstrip(b"\r\n").split(b";")
                try:
                    v = float(c[iD])
                    cod = c[iC].decode()
                    uf = UF[cod[:2]]
                except (ValueError, IndexError, KeyError, UnicodeDecodeError):
                    fora += 1
                    continue
                if not 0 <= v <= 5000 or len(cod) != 7:
                    fora += 1
                    continue
                n += 1
                if c[iP] != ultimo:
                    ultimo = c[iP]
                    periodos.add(ultimo)
                op, tec = c[iO].decode().strip().upper(), c[iT].decode().strip().upper()
                k = (cod, op, tec)
                a = arr.get(k)
                if a is None:
                    a = arr[k] = array.array("f")
                a.append(v)
                b = int(v * 10)
                if b > NB:
                    b = NB
                for ch in ((uf, "*"), (uf, tec), (uf, op), ("BR", "*"), ("BR", tec), ("BR", op)):
                    h = hist.get(ch)
                    if h is None:
                        h = hist[ch] = _hist()
                    h[b] += 1
                try:
                    u = float(c[iS])
                except (ValueError, IndexError):
                    continue
                if 0 <= u <= 5000:
                    s = sub.get(cod)
                    if s is None:
                        s = sub[cod] = array.array("f")
                    s.append(u)
                    b = int(u * 10)
                    if b > NB:
                        b = NB
                    for ch in (uf, "BR"):
                        h = hsub.get(ch)
                        if h is None:
                            h = hsub[ch] = _hist()
                        h[b] += 1
    finally:
        if tmp:
            Path(tmp.name).unlink(missing_ok=True)
    if n < 1_000_000:
        raise ValueError(f"só {n} testes no arquivo")
    # período: "MM/AAAA" de cada teste → do primeiro ao último mês
    meses = sorted({(int(p[3:7]), int(p[:2])) for p in (x.decode() for x in periodos) if re.fullmatch(r"\d{2}/\d{4}", p)})
    (a0, m0), (a1, m1) = meses[0], meses[-1]
    referencia = f"{MESES[m0 - 1]} a {MESES[m1 - 1]}/{a1}" if a0 == a1 else f"{mes_ano(a0, m0)} a {mes_ano(a1, m1)}"
    trimestre = f"{(m1 - 1) // 3 + 1}º trimestre de {a1}" if a0 == a1 and m1 - m0 == 2 and m0 % 3 == 1 else None
    ops = sorted({k[1] for k in arr}, key=lambda o: -sum(len(a) for k, a in arr.items() if k[1] == o))
    # municípios
    s = sedes()
    porcod = {}
    for (cod, op, tec), a in arr.items():
        porcod.setdefault(cod, []).append((op, tec, a))
    mun, sem_sede = [], 0
    for cod, L in porcod.items():
        if cod not in s:
            sem_sede += 1
            continue
        tudo = array.array("f")
        por_tec, por_op = {}, {}
        for op, tec, a in L:
            tudo.extend(a)
            por_tec.setdefault(tec, array.array("f")).extend(a)
            por_op.setdefault(op, array.array("f")).extend(a)
        nt = len(tudo)
        mun.append([round(float(s[cod]["longitude"]), 4), round(float(s[cod]["latitude"]), 4), _mediana(tudo), nt,
                    round(len(por_tec.get("5G", ())) / nt * 100, 1),
                    _mediana(por_tec.get("4G", ())), _mediana(por_tec.get("5G", ())), _mediana(sub.get(cod, ())),
                    [[len(por_op[o]), _mediana(por_op[o])] if o in por_op else None for o in ops],
                    s[cod]["nome"], UF[cod[:2]], cod])
    if len(mun) < 5000:
        raise ValueError(f"só {len(mun)} municípios com testes")
    mun.sort(key=lambda m: -m[2])   # os mais lentos por último: ficam desenhados por cima
    LIM = [15, 25, 35, 50]
    fx = {"menos de 15 Mbps": sum(m[2] < 15 for m in mun), "15 a 25": sum(15 <= m[2] < 25 for m in mun),
          "25 a 35": sum(25 <= m[2] < 35 for m in mun), "35 a 50": sum(35 <= m[2] < 50 for m in mun), "50 Mbps ou mais": sum(m[2] >= 50 for m in mun)}

    def regiao(r):
        tot = hist.get((r, "*"))
        if not tot:
            return None
        nt = sum(tot)
        n5 = sum(hist[(r, "5G")]) if (r, "5G") in hist else 0
        return {"valor": _mediana_hist(tot), "testes": nt, "pct_5g": round(n5 / nt * 100, 1),
                "d4g": _mediana_hist(hist[(r, "4G")]) if (r, "4G") in hist else None,
                "d5g": _mediana_hist(hist[(r, "5G")]) if (r, "5G") in hist else None,
                "sub": _mediana_hist(hsub[r]) if r in hsub else None,
                "op": {OPERADORAS.get(o, o.title()): [sum(hist[(r, o)]), _mediana_hist(hist[(r, o)])] for o in ops if (r, o) in hist}}
    valores = {u: v for u, v in ((u, regiao(u)) for u in UF.values()) if v}
    brasil = regiao("BR")
    if len(valores) < 27:
        raise ValueError(f"só {len(valores)} estados com testes")
    hoje = date.today().isoformat()
    fonte = "Anatel, medidas de velocidade da telefonia móvel (RQUAL, indicador IND4)"
    nota = ("testes feitos nos celulares de quem tem o programa de medição da Anatel instalado e autorizou os testes "
            "(a experiência real de quem usa); mediana: metade dos testes deu mais que isso, metade deu menos")
    meta = {"titulo": "Velocidade medida do celular", "referencia": referencia, "trimestre": trimestre, "fonte": fonte, "nota": nota,
            "posicao": POSICAO, "nivel": "api", "atualizado_em": hoje, "consulta": BASE + VEL_ZIP, "catalogo": CATALOGO_VEL,
            "testes": n, "operadoras": [OPERADORAS.get(o, o.title()) for o in ops], "limites": LIM, "faixas": fx, "poucos_testes": 50}
    if cab:
        meta["arquivo"] = cab
    gravar("velocidade.json", {"meta": meta,
        "campos": ["lon", "lat", "mediana_mbps", "testes", "pct_testes_5g", "mediana_4g", "mediana_5g", "mediana_upload",
                   "operadoras ([testes, mediana] na ordem de meta.operadoras)", "nome", "uf", "codigo_ibge"],
        "municipios": mun})
    gravar("velocidade_uf.json", {"titulo": "Velocidade medida do celular", "unidade": "Mbps, mediana", "referencia": referencia,
        "trimestre": trimestre, "fonte": fonte, "nota": nota, "nivel": "api", "atualizado_em": hoje,
        "consulta": BASE + VEL_ZIP, "catalogo": CATALOGO_VEL,
        "campos": {"valor": "mediana do download (Mbps), todas as tecnologias", "testes": "número de testes",
                   "pct_5g": "% dos testes feitos no 5G", "d4g": "mediana no 4G", "d5g": "mediana no 5G",
                   "sub": "mediana do upload (Mbps)", "op": "por operadora: [testes, mediana]"},
        "brasil": brasil, "valores": valores})
    print(f"[celular] velocidade {referencia}: {n} testes ({fora} fora), {len(mun)} municípios ({sem_sede} sem sede), "
          f"Brasil {brasil['valor']} Mbps; faixas {fx}; {round(time.time() - t0)} s")
    return "ok"


# ---------- moradores com sinal 5G (Meu Município, cobertura) ----------

def populacao():
    """Código do IBGE → população do Censo 2022 (arquivo da luz População, que tem nome e UF da sede)."""
    L = json.loads(POPULACAO.read_text(encoding="utf-8"))
    por_nome = {(m[3], m[4]): m[2] for m in L["municipios"]}
    return {k: por_nome[(r["nome"], r["uf"])] for k, r in sedes().items() if (r["nome"], r["uf"]) in por_nome}


def cobertura5g(cache):
    """Parte dos moradores de cada município com sinal 5G (previsão da Anatel), no último ano do Meu Município, com a
    série dos anos anteriores; por estado e no Brasil, a média dos municípios ponderada pela população do Censo 2022."""
    z = zipfile.ZipFile(io.BytesIO(baixar(MM_ZIP, cache)))
    nome = next(m for m in z.namelist() if "cobertura" in m.lower() and m.lower().endswith(".csv"))
    serie, ops, det = {}, {}, {}
    for r in tabela(z, nome):
        if r["Tecnologia"].strip().upper() != "5G":
            continue
        cod, ano, mes = r["Código IBGE"].strip(), int(r["Ano"]), int(r["Mês"])
        if len(cod) != 7 or cod[:2] not in UF:
            continue
        m = numero(r["% moradores cobertos"])
        op = r["Operadora"].strip().upper()
        if op == "TODAS":
            serie.setdefault(cod, {})[ano] = m
            det.setdefault((ano, mes), {})[cod] = (m, numero(r["% domicílios cobertos"]), numero(r["% área coberta"]))
        elif m:
            ops.setdefault((ano, mes), {}).setdefault(cod, []).append((OPERADORAS.get(op, op.title()), m))
    ultimo = max(p for p, d in det.items() if sum(1 for v in d.values() if v[0] is not None) >= 5500)
    ano, mes = ultimo
    D, O, s, pop = det[ultimo], ops.get(ultimo, {}), sedes(), populacao()
    anos = sorted(a for a in {a for v in serie.values() for a in v} if a <= ano)
    mun = []
    for cod, (m, dom, area) in D.items():
        if cod not in s or m is None:
            continue
        o = sorted(O.get(cod, []), key=lambda x: -x[1])
        mun.append([round(float(s[cod]["longitude"]), 4), round(float(s[cod]["latitude"]), 4), r1(m), r1(dom), r1(area),
                    [[n, r1(v)] for n, v in o], [r1(serie[cod].get(a)) for a in anos], s[cod]["nome"], UF[cod[:2]], cod])
    if len(mun) < 5500:
        raise ValueError(f"só {len(mun)} municípios com a cobertura 5G de {mes:02d}/{ano}")
    mun.sort(key=lambda x: x[2])   # os de mais cobertura por último: o desenho mais forte por cima

    def regiao(cods):
        res = {}
        for a in anos:
            ac = [(serie[c].get(a), pop[c]) for c in cods if c in pop and serie.get(c, {}).get(a) is not None]
            tp = sum(p for _, p in ac)
            res[a] = round(sum(v * p for v, p in ac) / tp, 1) if tp else None
        com = sum(1 for c in cods if (D.get(c) or (0,))[0])
        return {"valor": res[ano], "municipios_com_5g": com, "municipios": len(cods), "serie": [res[a] for a in anos]}
    cods_uf = {}
    for c in D:
        cods_uf.setdefault(UF[c[:2]], []).append(c)
    valores = {u: regiao(c) for u, c in cods_uf.items()}
    brasil = regiao(list(D))
    if len(valores) < 27 or len(pop) < 5500:
        raise ValueError("faltam estados ou a população dos municípios")
    hoje, referencia = date.today().isoformat(), mes_ano(ano, mes)
    fonte = "Anatel, Meu Município: cobertura da telefonia móvel"
    nota = ("previsão da Anatel, não medição: o sinal é calculado com as antenas licenciadas das operadoras e um modelo de "
            "propagação (ITU-R P.1812-5), e os moradores vêm dos setores do Censo 2010")
    gravar("cobertura_5g.json", {
        "meta": {"titulo": "Moradores com sinal 5G", "referencia": referencia, "anos": anos, "fonte": fonte, "nota": nota,
                 "posicao": POSICAO, "nivel": "api", "atualizado_em": hoje, "consulta": BASE + MM_ZIP, "catalogo": CATALOGO_MM,
                 "faixas": {"sem sinal 5G": sum(m[2] == 0 for m in mun), "menos de 25%": sum(0 < m[2] < 25 for m in mun),
                            "25 a 50%": sum(25 <= m[2] < 50 for m in mun), "50 a 80%": sum(50 <= m[2] < 80 for m in mun),
                            "80% ou mais": sum(m[2] >= 80 for m in mun)}},
        "campos": ["lon", "lat", "pct_moradores", "pct_domicilios", "pct_area", "operadoras [[nome, % moradores]]",
                   "serie (% moradores em cada um de meta.anos)", "nome", "uf", "codigo_ibge"],
        "municipios": mun})
    gravar("cobertura_5g_uf.json", {"titulo": "Moradores com sinal 5G", "unidade": "% dos moradores", "referencia": referencia,
        "anos": anos, "fonte": fonte, "nota": nota + "; por estado e no Brasil, média dos municípios ponderada pela população do Censo 2022 (conta do site)",
        "nivel": "api", "atualizado_em": hoje, "consulta": BASE + MM_ZIP, "catalogo": CATALOGO_MM,
        "campos": {"valor": "% dos moradores com sinal 5G", "municipios_com_5g": "municípios com algum sinal 5G",
                   "municipios": "municípios do estado", "serie": "% dos moradores em cada um dos anos"},
        "brasil": brasil, "valores": valores})
    print(f"[celular] 5G {referencia}: {len(mun)} municípios, Brasil {brasil['valor']}% dos moradores; anos {anos}")
    return "ok"


# ---------- banda larga fixa ----------

def banda_larga(cache):
    """Densidade oficial (acessos por 100 habitantes) e, do mesmo mês, o perfil dos acessos de cada município: fibra,
    rádio ou satélite, velocidade contratada (mediana), quantas empresas e quanto vem das empresas pequenas."""
    url = BASE + BL_ZIP
    if cache:
        dens_linhas = linhas_locais(Path(cache) / "Densidade_Banda_Larga_Fixa.csv")
    else:
        membros = membros_remotos(url)
        nome = next(m for m in membros if m.lower().startswith("densidade") and m.lower().endswith(".csv"))
        dens_linhas = linhas_remotas(url, membros[nome])
    dens = {}   # (ano, mês) → {"Brasil": x, "UF": {...}, "mun": {...}}
    for r in leitor(dens_linhas):
        try:
            p, v = (int(r["Ano"]), int(r["Mês"])), numero(r["Densidade"])
        except (TypeError, ValueError):
            continue
        if v is None:
            continue
        d, nivel = dens.setdefault(p, {"UF": {}, "mun": {}}), (r.get("Nível Geográfico Densidade") or "").strip().lower()
        if nivel == "brasil":
            d["Brasil"] = v
        elif nivel == "uf":
            d["UF"][r["UF"].strip()] = v
        elif nivel.startswith("munic"):
            d["mun"][r["Código IBGE"].strip()] = v
    meses = sorted(p for p, d in dens.items() if d.get("Brasil") and len(d["UF"]) == 27 and len(d["mun"]) >= 5500)
    ok = [p for i, p in enumerate(meses) if i and meses[i - 1] == (p[0] - (p[1] == 1), 12 if p[1] == 1 else p[1] - 1)
          and dens[p]["Brasil"] >= 0.99 * dens[meses[i - 1]]["Brasil"]
          and dens[p]["Brasil"] <= 1.05 * dens[meses[i - 1]]["Brasil"]]   # mês completo e sem salto estranho
    if not ok:
        raise ValueError("nenhum mês completo na densidade")
    ano, mes = ok[-1]
    D = dens[(ano, mes)]
    if cache:
        ac_linhas = linhas_locais(next(Path(cache).glob(f"Acessos_Banda_Larga_Fixa_{ano}.csv")))
    else:
        nome = next(m for m in membros if re.fullmatch(rf"Acessos_Banda_Larga_Fixa_{ano}\.csv", m))
        ac_linhas = linhas_remotas(url, membros[nome])
    ag = {}
    for r in leitor(ac_linhas):
        if r.get("Mês") != str(mes) or r.get("Ano") != str(ano):
            continue
        try:
            a = int(r["Acessos"])
        except (TypeError, ValueError):
            continue
        cod = (r.get("Código IBGE Município") or "").strip()
        if a <= 0 or cod[:2] not in UF:
            continue
        meio, vel = r["Meio de Acesso"].strip(), numero(r["Velocidade"])
        for k in (cod, UF[cod[:2]], "BR"):
            g = ag.get(k)
            if g is None:
                g = ag[k] = {"a": 0, "fibra": 0, "semfio": 0, "peq": 0, "emp": set(), "vel": {}}
            g["a"] += a
            if meio == "Fibra":
                g["fibra"] += a
            elif meio in ("Rádio", "Satélite"):
                g["semfio"] += a
            if r["Porte da Prestadora"].strip() == "Pequeno Porte":
                g["peq"] += a
            g["emp"].add(r["CNPJ"].strip())
            if vel is not None:
                g["vel"][vel] = g["vel"].get(vel, 0) + a

    def perfil(k):
        g = ag.get(k)
        if not g:
            return None
        tot, acc, med = sum(g["vel"].values()), 0, None
        for v in sorted(g["vel"]):
            acc += g["vel"][v]
            if acc * 2 >= tot:
                med = v
                break
        return {"acessos": g["a"], "fibra": round(g["fibra"] / g["a"] * 100, 1), "semfio": round(g["semfio"] / g["a"] * 100, 1),
                "pequenas": round(g["peq"] / g["a"] * 100, 1), "empresas": len(g["emp"]),
                "vel": round(med) if med and med >= 10 else (round(med, 1) if med is not None else None)}
    s = sedes()
    mun = []
    for cod, dv in D["mun"].items():
        if cod not in s:
            continue
        p = perfil(cod) or {}
        mun.append([round(float(s[cod]["longitude"]), 4), round(float(s[cod]["latitude"]), 4), r1(dv), p.get("acessos", 0),
                    p.get("fibra"), p.get("semfio"), p.get("vel"), p.get("empresas", 0), p.get("pequenas"), s[cod]["nome"], UF[cod[:2]], cod])
    if len(mun) < 5500:
        raise ValueError(f"só {len(mun)} municípios na banda larga de {mes:02d}/{ano}")
    mun.sort(key=lambda m: -m[2])   # os de menos acessos por último: ficam desenhados por cima
    valores = {u: {"valor": r1(v), **(perfil(u) or {})} for u, v in D["UF"].items() if u in UF.values()}
    hoje, referencia = date.today().isoformat(), mes_ano(ano, mes)
    fonte = "Anatel, acessos da banda larga fixa (densidade por 100 habitantes e acessos por empresa e município)"
    nota = ("acesso = cada contrato de internet fixa em cada endereço (casa ou empresa); densidade: acessos por 100 habitantes, "
            f"a conta oficial da Anatel; {referencia} é o mês completo mais recente (o último costuma chegar incompleto)")
    meta = {"titulo": "Banda larga fixa", "referencia": referencia, "fonte": fonte, "nota": nota, "posicao": POSICAO,
            "nivel": "api", "atualizado_em": hoje, "consulta": url, "catalogo": CATALOGO_BL,
            "faixas": {"menos de 5": sum(m[2] < 5 for m in mun), "5 a 10": sum(5 <= m[2] < 10 for m in mun),
                       "10 a 20": sum(10 <= m[2] < 20 for m in mun), "20 a 30": sum(20 <= m[2] < 30 for m in mun),
                       "30 ou mais": sum(m[2] >= 30 for m in mun)}}
    gravar("banda_larga.json", {"meta": meta,
        "campos": ["lon", "lat", "acessos_por_100_hab", "acessos", "pct_fibra", "pct_radio_satelite", "velocidade_contratada_mediana_mbps",
                   "empresas", "pct_acessos_empresas_pequenas", "nome", "uf", "codigo_ibge"],
        "municipios": mun})
    gravar("banda_larga_uf.json", {"titulo": "Banda larga fixa", "unidade": "acessos por 100 habitantes", "referencia": referencia,
        "fonte": fonte, "nota": nota, "nivel": "api", "atualizado_em": hoje, "consulta": url, "catalogo": CATALOGO_BL,
        "campos": {"valor": "acessos por 100 habitantes (Anatel)", "acessos": "acessos em serviço", "fibra": "% dos acessos por fibra óptica",
                   "semfio": "% por rádio ou satélite", "pequenas": "% dos acessos em empresas de pequeno porte",
                   "empresas": "empresas com acessos (CNPJ)", "vel": "velocidade contratada, mediana (Mbps)"},
        "brasil": {"valor": r1(D["Brasil"]), **(perfil("BR") or {})}, "valores": valores})
    print(f"[celular] banda larga {referencia}: {len(mun)} municípios, Brasil {r1(D['Brasil'])} por 100 hab., "
          f"{perfil('BR')['acessos'] if perfil('BR') else '?'} acessos")
    return "ok"


PASSOS = {"ibc": ibc, "rqual": rqual, "velocidade": velocidade, "cobertura5g": cobertura5g, "banda_larga": banda_larga}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", help="pasta com os arquivos já baixados (ver o começo deste arquivo)")
    ap.add_argument("--so", help="só estes passos, separados por vírgula: " + ", ".join(PASSOS))
    args = ap.parse_args()
    escolha = args.so.split(",") if args.so else list(PASSOS)
    antigo = (ler("robo.json") or {}).get("passos", {})
    passos, res = {}, {}
    for nome, f in PASSOS.items():
        if nome not in escolha:
            if nome in antigo:
                passos[nome] = antigo[nome]
            continue
        try:
            res[nome] = f(args.cache)
            passos[nome] = res[nome] if isinstance(res[nome], str) else "ok"
        except Exception as e:
            print(f"[celular] {nome} falhou, mantendo o arquivo anterior: {e}")
            passos[nome] = f"falhou (ficou o arquivo anterior): {str(e)[:120]}"
    if "ibc" in escolha or "rqual" in escolha:
        passos["estados"] = "ok" if estados(res.get("ibc"), res.get("rqual")) else "sem dados"
    elif "estados" in antigo:
        passos["estados"] = antigo["estados"]
    gravar("robo.json", {"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "passos": passos})
    sys.exit(0 if any(v in ("ok", "sem novidade") for v in passos.values()) else 1)
