"""Acervo: banda larga fixa da Anatel (acessos por município, meio de acesso, velocidade e empresa), por trimestre e ano.

Uso:
    python scripts/acervo/banda_larga_anatel.py                todo mês (GitHub): se o zip da Anatel mudou, relê e confere
    python scripts/acervo/banda_larga_anatel.py --zip ARQUIVO  usa o zip já baixado (carga inicial ou teste)

Fonte: acessos_banda_larga_fixa.zip (≈ 1 GB) dos dados abertos da Anatel, com um arquivo por ano (ou por dois anos) de
acessos e o arquivo de densidade. Banda larga é posição (o que existe numa data): o trimestre é o último mês dele
(março, junho, setembro, dezembro) e o ano é dezembro. Pacotes: um por ano fechado (Brasil, estados e, desde 2010,
municípios), um por trimestre dos anos fechados (Brasil e estados) e um por trimestre já terminado do ano em aberto
(com municípios). De 2007 a 2010 a Anatel só tem os meses que fecham trimestre.
Se o zip for o mesmo da última vez (tamanho e data), o robô não baixa nada: só confere os prazos (preliminar →
consolidado). Se mudou, refaz todos os períodos; um pacote só muda (versão nova) se algum número mudou.
Só usa a biblioteca padrão.
"""
import argparse
import csv
import io
import json
import re
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402

URL = "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/acessos/acessos_banda_larga_fixa.zip"
AGENTE = {"User-Agent": "Mozilla/5.0 (compatible; brasil-em-camadas; dados abertos)"}
DESDE_MUNICIPIO = 2010
DESDE_VELOCIDADE = 2021   # a velocidade contratada exata (coluna "Velocidade") só existe desde 2021

CFG = {
    "id": "banda-larga-anatel",
    "titulo": "Banda larga fixa (Anatel)",
    "descricao": ("Acessos de internet fixa em serviço (contratos em casas e empresas) no Brasil, em cada estado e (desde "
                  "2010) em cada município, com o meio de acesso, a faixa de velocidade, as empresas e a densidade "
                  "(acessos por 100 habitantes), no último mês de cada trimestre e de cada ano."),
    "fonte": {"orgao": "Anatel", "titulo": "Anatel, Acessos – Banda Larga Fixa (dados abertos)",
              "consulta": URL, "catalogo": "https://dados.gov.br/dados/conjuntos-dados/acessos---banda-larga-fixa",
              "licenca": "Creative Commons Atribuição (CC BY), como informado no Portal Brasileiro de Dados Abertos"},
    "nivel": "Oficial · API",
    "periodicidade": "mensal na fonte; no acervo, por trimestre e por ano",
    "medida": "posição: acessos em serviço no último mês do período",
    "como_vira_ano": "posição em dezembro; o trimestre é o seu último mês (março, junho, setembro ou dezembro)",
    "niveis": {"brasil": "Brasil", "uf": "estados", "municipio": "municípios (desde 2010; nos trimestres, só no ano em aberto)"},
    "atraso_meses": 2,
    "metodo": ("Soma das linhas do arquivo de acessos da Anatel (cada linha: empresa, município, meio de acesso, faixa de "
               "velocidade e número de acessos) no último mês do período. O total de acessos do Brasil vem do arquivo de "
               "totais da própria Anatel. A densidade é a da Anatel (arquivo de densidade). Contas do projeto: empresas "
               "(CNPJs distintos com pelo menos um acesso no lugar) e velocidade contratada mediana (metade dos acessos "
               "tem velocidade contratada maior, metade menor, pela velocidade de cada linha)."),
    "avisos": [
        "Acesso = cada contrato de internet fixa num endereço (casa ou empresa); não é o número de pessoas com internet.",
        "Meio de acesso e faixa de velocidade são os que cada empresa informou à Anatel.",
        "O último mês costuma chegar incompleto (as empresas pequenas informam depois): o trimestre em aberto só entra "
        "quando o mês dele tem pelo menos 99% (e no máximo 105%) dos acessos do mês anterior, e fica preliminar.",
        "A Anatel revisa meses antigos de vez em quando; quando um número muda, entra uma versão nova do pacote.",
        "Município sem nenhuma linha no arquivo: 0 acessos registrados pela Anatel.",
        "Ausência na base não significa ausência real: são os acessos que as empresas informaram à Anatel.",
    ],
}

MEIOS = {"Fibra": "acessos_fibra", "Cabo Coaxial": "acessos_cabo_coaxial", "Cabo Metálico": "acessos_cabo_metalico",
         "Rádio": "acessos_radio", "Satélite": "acessos_satelite"}   # o resto vai para acessos_outros_meios
FAIXAS = {"0Kbps a 64Kbps": "acessos_ate_512k", "64Kbps a 512Kbps": "acessos_ate_512k", "0Kbps a 512Kbps": "acessos_ate_512k",
          "512kbps a 2Mbps": "acessos_512k_a_2m", "2Mbps a 12Mbps": "acessos_2m_a_12m",
          "12Mbps a 34Mbps": "acessos_12m_a_34m", "2Mbps a 34Mbps": "acessos_2m_a_34m", "> 34Mbps": "acessos_acima_34m"}
CONTAS = (["acessos"] + list(MEIOS.values()) + ["acessos_outros_meios", "acessos_ate_512k", "acessos_512k_a_2m",
          "acessos_2m_a_12m", "acessos_12m_a_34m", "acessos_2m_a_34m", "acessos_acima_34m", "acessos_pequeno_porte"])
POS = {k: i for i, k in enumerate(CONTAS)}


def campos(nivel, ano, faixas_antigas):
    c = [C.Campo("codigo_ibge", "string", "Código do IBGE do lugar",
                 descricao={"brasil": "1 = Brasil (como na SIDRA do IBGE)", "uf": "código do estado (2 dígitos)",
                            "municipio": "código do município (7 dígitos); nome e posição em ../../municipios.csv"}[nivel])]
    if nivel != "brasil":
        c.append(C.Campo("uf", "string", "Sigla do estado"))
    c += [C.Campo("acessos", "integer", "Acessos em serviço", "acessos",
                  "no Brasil, o total da própria Anatel" if nivel == "brasil" else None),
          C.Campo("acessos_fibra", "integer", "Acessos por fibra óptica", "acessos"),
          C.Campo("acessos_cabo_coaxial", "integer", "Acessos por cabo coaxial (TV a cabo)", "acessos"),
          C.Campo("acessos_cabo_metalico", "integer", "Acessos por cabo metálico (linha telefônica, xDSL)", "acessos"),
          C.Campo("acessos_radio", "integer", "Acessos por rádio", "acessos"),
          C.Campo("acessos_satelite", "integer", "Acessos por satélite", "acessos"),
          C.Campo("acessos_outros_meios", "integer", "Acessos por outros meios", "acessos",
                  "outro, híbrido, LTE ou indeterminado, como a empresa informou"),
          C.Campo("acessos_ate_512k", "integer", "Acessos com velocidade contratada até 512 kbps", "acessos"),
          C.Campo("acessos_512k_a_2m", "integer", "Acessos de 512 kbps a 2 Mbps", "acessos")]
    if faixas_antigas:
        c.append(C.Campo("acessos_2m_a_34m", "integer", "Acessos de 2 a 34 Mbps", "acessos",
                         "até 2010 a Anatel não separava 2 a 12 e 12 a 34 Mbps"))
    else:
        c += [C.Campo("acessos_2m_a_12m", "integer", "Acessos de 2 a 12 Mbps", "acessos"),
              C.Campo("acessos_12m_a_34m", "integer", "Acessos de 12 a 34 Mbps", "acessos")]
    c += [C.Campo("acessos_acima_34m", "integer", "Acessos acima de 34 Mbps", "acessos"),
          C.Campo("acessos_pequeno_porte", "integer", "Acessos em empresas de pequeno porte", "acessos",
                  "porte da empresa como a Anatel classifica"),
          C.Campo("empresas", "integer", "Empresas com acessos no lugar", "empresas",
                  "CNPJs distintos com pelo menos um acesso (conta do projeto)")]
    if ano >= DESDE_VELOCIDADE:
        c.append(C.Campo("velocidade_contratada_mediana_mbps", "number", "Velocidade contratada, mediana", "Mbps",
                         "metade dos acessos tem velocidade contratada maior, metade menor (conta do projeto)", casas=3))
    c.append(C.Campo("acessos_por_100_hab", "number", "Densidade: acessos por 100 habitantes", "acessos por 100 habitantes",
                     "a conta da Anatel, arredondada a 2 casas; vazia quando a Anatel não publicou um número coerente", casas=2))
    return c


# ---------- leitura do zip ----------

def numero(t):
    t = (t or "").strip()
    if not t:
        return None
    return float(t.replace(".", "").replace(",", ".")) if t.count(",") == 1 and "." in t else float(t.replace(",", "."))


def ler_total(z):
    tot = {}
    for l in z.read("Acessos_Banda_Larga_Fixa_Total.csv").decode("utf-8-sig").splitlines()[1:]:
        a, m, v = l.split(";")
        tot[(int(a), int(m))] = int(v)
    return tot


def ler_densidade(z, meses):
    dens = {p: {"Brasil": None, "UF": {}, "mun": {}} for p in meses}
    f = io.TextIOWrapper(z.open("Densidade_Banda_Larga_Fixa.csv"), encoding="utf-8-sig", newline="")
    for r in csv.DictReader(f, delimiter=";"):
        try:
            p = (int(r["Ano"]), int(r["Mês"]))
        except (TypeError, ValueError):
            continue
        if p not in dens:
            continue
        v = numero(r["Densidade"])
        if v is None:
            continue
        nivel, d = (r.get("Nível Geográfico Densidade") or "").strip().lower(), dens[p]
        if nivel == "brasil":
            d["Brasil"] = v
        elif nivel == "uf" and (r.get("UF") or "").strip():
            d["UF"][r["UF"].strip()] = v
        elif nivel.startswith("munic") and (r.get("Código IBGE") or "").strip():
            d["mun"][r["Código IBGE"].strip()] = v
    return dens


def densidade_coerente(d, acessos_br, acessos_uf):
    """A densidade do mês só vale se bater com os acessos: a população que ela implica (acessos ÷ densidade) tem de ser
    a de um país (150 a 250 milhões) e a soma das dos estados tem de bater com a do Brasil (±3%)."""
    if not d["Brasil"] or len(d["UF"]) != 27 or len(d["mun"]) < 4000:
        return False, "incompleta no arquivo da Anatel"
    pop = acessos_br / (d["Brasil"] / 100)
    if not 150e6 <= pop <= 250e6:
        return False, f"o número do Brasil ({d['Brasil']:.2f}) não bate com os acessos"
    soma = 0
    for uf, v in d["UF"].items():
        a = acessos_uf.get(uf)
        if not a or not v:
            return False, f"sem acessos ou densidade em {uf}"
        p = a / (v / 100)
        if not 0.2e6 <= p <= 60e6:
            return False, f"o número de {uf} ({v:.2f}) não bate com os acessos"
        soma += p
    if abs(soma - pop) > 0.03 * pop:
        return False, "os estados não batem com o Brasil"
    return True, None


def agregar(z, meses_uf, meses_mun):
    """Lê os arquivos de acessos e soma, para cada mês pedido, por município (só os meses de municípios), estado e Brasil.
    Devolve {mês: {lugar: [contas...]}}, {mês: {lugar: set(CNPJ)}}, {mês: {lugar: {velocidade: acessos}}} e as
    categorias vistas."""
    contas, emp, vel, vistos = {}, {}, {}, {}
    arquivos = sorted(m for m in z.namelist() if re.fullmatch(r"Acessos_Banda_Larga_Fixa_\d{4}(-\d{4})?\.csv", m))
    t0 = time.time()
    for nome in arquivos:
        f = io.BufferedReader(z.open(nome), 1 << 22)
        cab = f.readline().decode("utf-8-sig").strip().split(";")
        i = {k: cab.index(k) for k in ("Ano", "Mês", "CNPJ", "Porte da Prestadora", "Código IBGE Município",
                                       "Faixa de Velocidade", "Meio de Acesso", "Acessos")}
        iv = cab.index("Velocidade") if "Velocidade" in cab else None
        n = 0
        for linha in f:
            c = linha.rstrip(b"\r\n").split(b";")
            try:
                p = (int(c[i["Ano"]]), int(c[i["Mês"]]))
            except (ValueError, IndexError):
                continue
            if p not in meses_uf:
                continue
            try:
                a = int(c[i["Acessos"]])
            except ValueError:
                continue
            if a <= 0:
                continue
            cod = c[i["Código IBGE Município"]].decode().strip()
            if cod[:2] not in C.UF:
                raise ValueError(f"{nome}: linha sem município válido ({cod!r})")
            uf = C.UF[cod[:2]]
            meio = c[i["Meio de Acesso"]].decode("utf-8", "replace").strip()
            faixa = c[i["Faixa de Velocidade"]].decode("utf-8", "replace").strip()
            if faixa not in FAIXAS:
                raise ValueError(f"{nome}: faixa de velocidade desconhecida {faixa!r}")
            vi = vistos.setdefault(p, {})
            vi[meio] = vi.get(meio, 0) + a
            k_meio = POS[MEIOS.get(meio, "acessos_outros_meios")]
            k_faixa = POS[FAIXAS[faixa]]
            peq = c[i["Porte da Prestadora"]].strip() == b"Pequeno Porte"
            cnpj = c[i["CNPJ"]].strip()
            v = None
            if iv is not None:
                try:
                    v = numero(c[iv].decode())
                except ValueError:
                    v = None
            lugares = (cod, uf, C.CODIGO_BRASIL) if p in meses_mun else (uf, C.CODIGO_BRASIL)
            cm, em, vm = contas.setdefault(p, {}), emp.setdefault(p, {}), vel.setdefault(p, {})
            for lugar in lugares:
                x = cm.get(lugar)
                if x is None:
                    x = cm[lugar] = [0] * len(CONTAS)
                    em[lugar] = set()
                    vm[lugar] = {}
                x[0] += a
                x[k_meio] += a
                x[k_faixa] += a
                if peq:
                    x[POS["acessos_pequeno_porte"]] += a
                em[lugar].add(cnpj)
                if v is not None and v >= 0:
                    vm[lugar][v] = vm[lugar].get(v, 0) + a
            n += 1
        print(f"[acervo/banda larga] {nome}: {n} linhas usadas ({round(time.time() - t0)} s)")
    return contas, emp, vel, vistos


def mediana(dist):
    tot = sum(dist.values())
    if not tot:
        return None
    acc = 0
    for v in sorted(dist):
        acc += dist[v]
        if acc * 2 >= tot:
            return v


# ---------- montagem ----------

def linha(lugar, nivel, x, empresas, dist, ano, dens, faixas_antigas, vazio=False):
    """vazio: município novo ainda sem nenhuma linha no arquivo (sem dado, não zero)."""
    d = {"codigo_ibge": lugar}
    if nivel != "brasil":
        d["uf"] = C.UF[lugar[:2]]
    for k in CONTAS:
        if faixas_antigas and k in ("acessos_2m_a_12m", "acessos_12m_a_34m"):
            continue
        if not faixas_antigas and k == "acessos_2m_a_34m":
            continue
        d[k] = None if vazio else (x[POS[k]] if x else 0)
    d["empresas"] = None if vazio else (len(empresas) if empresas else 0)
    if ano >= DESDE_VELOCIDADE:
        d["velocidade_contratada_mediana_mbps"] = mediana(dist) if dist else None
    d["acessos_por_100_hab"] = round(dens, 2) if dens is not None else None
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zip", help="zip da Anatel já baixado")
    a = ap.parse_args()
    dia = C.hoje().isoformat()
    velho = (C.pasta_conjunto(CFG) / "conjunto.json")
    estado_velho = json.loads(velho.read_text(encoding="utf-8")).get("estado_da_fonte") if velho.exists() else None
    tmp = None
    req = urllib.request.Request(URL, headers=AGENTE, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        estado = {"arquivo": URL.rsplit("/", 1)[1], "tamanho": int(r.headers.get("Content-Length") or 0),
                  "modificado": r.headers.get("Last-Modified")}
    if a.zip:
        arq = Path(a.zip)
        if arq.stat().st_size != estado["tamanho"]:   # o zip daqui não é o que está na Anatel agora
            estado = {"arquivo": arq.name, "tamanho": arq.stat().st_size, "modificado": None}
    else:
        if estado_velho and estado_velho.get("tamanho") == estado["tamanho"] and estado_velho.get("modificado") == estado["modificado"]:
            cons = C.consolidar(CFG)
            C.atualizar_conjunto(CFG, conferido_em=dia)
            print(f"[acervo/banda larga] o zip da Anatel é o mesmo da última vez; consolidados agora: {cons or 'nenhum'}")
            return
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.close()
        arq = Path(tmp.name)
        C.baixar_grande(URL, arq, AGENTE)
    try:
        with zipfile.ZipFile(arq) as z:
            membros = {i.filename: {"crc": f"{i.CRC:08x}", "tamanho": i.file_size,
                                    "data": "%04d-%02d-%02d" % i.date_time[:3]} for i in z.infolist()}
            estado["membros"] = membros
            total = ler_total(z)
            ultimo = max(total)
            anos = sorted({p[0] for p in total})

            def pronto(p):   # mês que já pode virar pacote: há um mês depois dele ou ele está completo
                y, m = p
                return p in total and (y < ultimo[0] or (y, m + 1) in total or completo(total, p))
            fechados = [y for y in anos if pronto((y, 12))]
            aberto = ultimo[0] if ultimo[0] not in fechados else None
            meses_uf = {(y, m) for y in anos for m in (3, 6, 9, 12) if pronto((y, m))}
            # trimestres que já saíram com municípios (do tempo em que o ano estava em aberto) continuam com eles
            ja_com_mun = {p for p in C.pacotes(CFG) if "-T" in p
                          and "municipio" in [r["name"] for r in C.ficha_atual(CFG, p)["resources"]]}
            meses_mun = ({(y, 12) for y in fechados if y >= DESDE_MUNICIPIO} | {p for p in meses_uf if p[0] == aberto}
                         | {(int(p[:4]), 3 * int(p[-1])) for p in ja_com_mun})
            print(f"[acervo/banda larga] meses de {min(total)} a {ultimo}; ano em aberto: {aberto}; "
                  f"{len(meses_uf)} meses de fim de trimestre")
            contas, emp, vel, vistos = agregar(z, meses_uf, meses_mun)
            dens = ler_densidade(z, meses_uf)
    finally:
        if tmp:
            Path(tmp.name).unlink(missing_ok=True)
    resultados = {}
    for (y, m) in sorted(meses_uf):
        pers = []
        if m == 12 and y in fechados:
            pers.append(str(y))
        pers.append(f"{y}-T{m // 3}")
        cm, em, vm = contas.get((y, m), {}), emp.get((y, m), {}), vel.get((y, m), {})
        faixas_antigas = y <= 2010
        acessos_uf = {k: v[0] for k, v in cm.items() if len(k) == 2 and k.isalpha()}
        br_fonte = total[(y, m)]
        ok, motivo = densidade_coerente(dens[(y, m)], br_fonte, acessos_uf)
        D = dens[(y, m)] if ok else {"Brasil": None, "UF": {}, "mun": {}}
        avisos = []
        if not ok:
            avisos.append(f"Densidade vazia em {C.MESES_PT[m - 1]}/{y}: {motivo}.")
        soma_br = cm.get(C.CODIGO_BRASIL, [0])[0]
        if abs(soma_br - br_fonte) > 0.01 * br_fonte:   # leitura incompleta: não grava nada deste mês
            raise ValueError(f"{m}/{y}: a soma das linhas ({soma_br}) não bate com o total da Anatel ({br_fonte})")
        if soma_br != br_fonte:
            avisos.append(f"Brasil: a Anatel dá {C.br(br_fonte)} acessos no total de {C.MESES_PT[m - 1]}/{y}; a soma das "
                          f"linhas do arquivo dá {C.br(soma_br)} (as outras colunas do Brasil são somas das linhas).")
        if faixas_antigas:
            avisos.append("Até 2010, a Anatel juntava 2 a 34 Mbps numa faixa só (acessos_2m_a_34m) e separava até 64 kbps "
                          "e de 64 a 512 kbps (aqui somados em acessos_ate_512k).")
        if y <= 2010:
            avisos.append("De 2007 a 2010, a Anatel só tem os meses que fecham trimestre (março, junho, setembro e dezembro).")
        x_br = cm.get(C.CODIGO_BRASIL)
        if x_br is None:
            raise ValueError(f"{m}/{y}: nenhum acesso lido")
        b_l = linha(C.CODIGO_BRASIL, "brasil", x_br, em.get(C.CODIGO_BRASIL), vm.get(C.CODIGO_BRASIL), y, D["Brasil"], faixas_antigas)
        b_l["acessos"] = br_fonte
        u_l = [linha(cod, "uf", cm.get(C.UF[cod]), em.get(C.UF[cod]), vm.get(C.UF[cod]), y, D["UF"].get(C.UF[cod]), faixas_antigas)
               for cod in sorted(C.UF)]
        mun_l, avisos_mun = None, []
        if (y, m) in meses_mun:
            lugares = set(C.municipios_do_ano(y))
            com_dado = {k for k in cm if len(k) == 7}
            fora = sorted(com_dado - lugares)
            if fora:
                avisos_mun.append(f"Municípios com acessos fora da lista do IBGE para {y}, mantidos como a Anatel publica: {', '.join(fora)}.")
            novos = sorted(c for c in lugares - com_dado if c in C.INSTALADO_EM)
            if novos:
                avisos_mun.append(f"Município(s) novo(s) ainda sem nenhuma linha no arquivo da Anatel em {C.MESES_PT[m - 1]}/{y}: "
                              f"{', '.join(novos)} (instalado em {', '.join(str(C.INSTALADO_EM[c]) for c in novos)}). Ficam vazios, não "
                              "zero: os acessos de lá provavelmente ainda estavam registrados no município de onde ele saiu.")
            mun_l = [linha(cod, "municipio", cm.get(cod), em.get(cod), vm.get(cod), y, D["mun"].get(cod), faixas_antigas,
                           vazio=cod in novos)
                     for cod in sorted(lugares | com_dado)]
            sem = sum(1 for d in mun_l if d["acessos"] == 0)
            if sem:
                avisos_mun.append(f"{sem} município(s) sem nenhum acesso registrado pela Anatel em {C.MESES_PT[m - 1]}/{y} (0).")
        outros = sorted(k or "(em branco)" for k in vistos.get((y, m), {}) if k not in MEIOS)
        for p in pers:
            tabelas = {"brasil": (campos("brasil", y, faixas_antigas), [b_l]), "uf": (campos("uf", y, faixas_antigas), u_l)}
            com_mun = mun_l is not None and (p == str(y) or y == aberto or p in ja_com_mun)
            if com_mun:
                tabelas["municipio"] = (campos("municipio", y, faixas_antigas), mun_l)
            extra = {"coletado_em": dia, "consulta": URL,
                     "metodo": f"Mês usado: {C.MESES_PT[m - 1]}/{y}.",
                     "avisos": avisos + (avisos_mun if com_mun else [])
                     + ([f"Outros meios, nos arquivos da Anatel: {', '.join(outros)}."] if outros else [])}
            resultados[p] = C.gravar_pacote(CFG, p, tabelas, extra)
    cons = C.consolidar(CFG)
    if cons:
        resultados.update({p: "consolidado agora" for p in cons})
    C.atualizar_conjunto(CFG, conferido_em=dia, estado=estado)
    C.registrar(CFG, resultados)


def completo(total, p):
    """O mês tem de 99% a 105% dos acessos do mês anterior (o último costuma chegar incompleto)."""
    y, m = p
    ant = (y, m - 1) if m > 1 else (y - 1, 12)
    if ant not in total:
        ant = (y, m - 3) if m > 3 else (y - 1, 12 + m - 3)   # 2007 a 2010: só os meses que fecham trimestre
    return ant in total and 0.99 * total[ant] <= total[p] <= 1.05 * total[ant]


if __name__ == "__main__":
    main()
