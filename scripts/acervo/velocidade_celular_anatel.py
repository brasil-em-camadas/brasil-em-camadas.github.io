"""Acervo: velocidade medida no celular (Anatel, medidas de velocidade da telefonia móvel). Um pacote por trimestre.

Uso:
    python scripts/acervo/velocidade_celular_anatel.py

Não baixa nada: lê o que o robô da Anatel (scripts/atualizar_anatel.py, passo "velocidade") calculou dos testes do
trimestre, em site/data/celular/velocidade.json e velocidade_uf.json, e guarda o trimestre no acervo. Por isso roda
logo depois daquele robô. A Anatel só deixa no ar o trimestre mais recente (o arquivo de cada teste, ≈ 1 GB, é
trocado a cada trimestre): o acervo é o lugar onde os trimestres passados continuam existindo.
Mediana não se soma: não há pacote anual. Só usa a biblioteca padrão.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402

DADOS = C.RAIZ / "site" / "data" / "celular"

CFG = {
    "id": "velocidade-celular-anatel",
    "titulo": "Velocidade medida no celular (Anatel)",
    "descricao": ("Mediana da velocidade de download e de upload nos testes feitos nos celulares, no Brasil, em cada "
                  "estado e em cada município, por trimestre, com o 4G, o 5G e cada operadora."),
    "fonte": {"orgao": "Anatel", "orgao_nome": "Agência Nacional de Telecomunicações (Anatel)",
              "orgao_site": "https://www.gov.br/anatel/",
              "titulo": "Anatel, medidas de velocidade da telefonia móvel (RQUAL, indicador IND4)",
              "consulta": "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/qualidade/medidas_qoe_smp.zip",
              "catalogo": "https://dados.gov.br/dados/conjuntos-dados/qualidade---medidas-de-velocidade---telefonia-movel",
              "licenca": "Creative Commons Atribuição (CC BY), como informado no Portal Brasileiro de Dados Abertos"},
    "nivel": "Oficial · API",
    # palavras para a busca (página do conjunto e ficha schema.org Dataset)
    "palavras_chave": ["velocidade da internet móvel", "celular", "4G", "5G", "testes de velocidade", "download", "upload",
                       "mediana", "Claro", "TIM", "Vivo", "Anatel", "estados", "municípios", "dados abertos"],
    "periodicidade": "trimestral",
    "medida": "mediana dos testes do trimestre (não se soma: não há pacote anual)",
    "como_vira_ano": "não vira: mediana não se soma, então só existem pacotes por trimestre",
    "niveis": {"brasil": "Brasil", "uf": "estados", "municipio": "municípios"},
    "atraso_meses": 2,   # o 2º trimestre de 2026 saiu em 11/08/2026
    "metodo": ("Cada linha do arquivo da Anatel é um teste de velocidade (download e upload, em Mbps) feito no celular de "
               "quem tem o programa de medição instalado e autorizou os testes, com operadora, tecnologia e município. "
               "Conta do projeto: as medianas (metade dos testes deu mais, metade deu menos), exatas no município e com "
               "precisão de 0,1 Mbps no estado e no Brasil (feitas de todos os testes, não da média dos municípios), e a "
               "parte dos testes feita no 5G."),
    "avisos": [
        "É medição de verdade (a experiência de quem usa), mas não uma amostra planejada: onde há poucos testes a mediana "
        "é pouco firme. O mapa só pinta município com 50 testes ou mais e marca operadora com menos de 30; aqui os números "
        "ficam todos, com a contagem de testes ao lado.",
        "Todas as tecnologias: inclui 3G e outras; o 4G e o 5G também aparecem separados.",
        "Município sem nenhum teste no trimestre: 0 testes e medianas vazias.",
        "A Anatel publica só o trimestre mais recente; o acervo guarda cada um quando sai.",
    ],
}


def campos(nivel, operadoras):
    c = [C.Campo("codigo_ibge", "string", "Código do IBGE do lugar",
                 descricao={"brasil": "1 = Brasil (como na SIDRA do IBGE)", "uf": "código do estado (2 dígitos)",
                            "municipio": "código do município (7 dígitos); nome e posição em ../../municipios.csv"}[nivel])]
    if nivel != "brasil":
        c.append(C.Campo("uf", "string", "Sigla do estado"))
    c += [C.Campo("testes", "integer", "Testes de velocidade no trimestre", "testes"),
          C.Campo("download_mediana_mbps", "number", "Download, mediana (todas as tecnologias)", "Mbps", casas=1),
          C.Campo("download_4g_mediana_mbps", "number", "Download no 4G, mediana", "Mbps", casas=1),
          C.Campo("download_5g_mediana_mbps", "number", "Download no 5G, mediana", "Mbps", casas=1),
          C.Campo("pct_testes_5g", "number", "Parte dos testes feita no 5G", "%", casas=1),
          C.Campo("upload_mediana_mbps", "number", "Upload, mediana (todas as tecnologias)", "Mbps", casas=1)]
    for o in operadoras:
        s = re.sub(r"[^a-z0-9]+", "_", o.lower()).strip("_")
        c += [C.Campo(f"{s}_testes", "integer", f"{o}: testes", "testes"),
              C.Campo(f"{s}_download_mediana_mbps", "number", f"{o}: download, mediana", "Mbps", casas=1)]
    return c


def main():
    v = json.loads((DADOS / "velocidade.json").read_text(encoding="utf-8"))
    vu = json.loads((DADOS / "velocidade_uf.json").read_text(encoding="utf-8"))
    meta = v["meta"]
    m = re.fullmatch(r"(\d)º trimestre de (\d{4})", meta.get("trimestre") or "")
    if not m:   # o arquivo da Anatel não cobre um trimestre inteiro: não nasce pacote
        print(f"[acervo/velocidade] o arquivo não é de um trimestre inteiro ({meta.get('referencia')}); nada a guardar")
        return
    p = f"{m.group(2)}-T{m.group(1)}"
    if vu.get("referencia") != meta.get("referencia"):
        raise SystemExit("velocidade.json e velocidade_uf.json são de períodos diferentes")
    ops = meta["operadoras"]
    nomes_op = {o: re.sub(r"[^a-z0-9]+", "_", o.lower()).strip("_") for o in ops}

    def regiao(cod, r):
        d = {"codigo_ibge": cod, "testes": r["testes"], "download_mediana_mbps": r["valor"],
             "download_4g_mediana_mbps": r.get("d4g"), "download_5g_mediana_mbps": r.get("d5g"),
             "pct_testes_5g": r.get("pct_5g"), "upload_mediana_mbps": r.get("sub")}
        if cod != C.CODIGO_BRASIL:
            d["uf"] = C.UF[cod]
        for o in ops:
            t, med = (r.get("op") or {}).get(o) or (0, None)
            d[f"{nomes_op[o]}_testes"], d[f"{nomes_op[o]}_download_mediana_mbps"] = t, med
        return d
    brasil = [regiao(C.CODIGO_BRASIL, vu["brasil"])]
    sigla_cod = {s: c for c, s in C.UF.items()}
    if len(vu["valores"]) != 27:
        raise SystemExit(f"só {len(vu['valores'])} estados em velocidade_uf.json")
    ufs = [regiao(sigla_cod[s], r) for s, r in sorted(vu["valores"].items(), key=lambda x: sigla_cod[x[0]])]
    ic = v["campos"].index("codigo_ibge")
    por_cod = {x[ic]: x for x in v["municipios"]}
    ano = int(m.group(2))
    lugares = sorted(set(C.municipios_do_ano(ano)) | set(por_cod))
    mun, sem = [], 0
    for cod in lugares:
        x = por_cod.get(cod)
        d = {"codigo_ibge": cod, "uf": C.UF[cod[:2]]}
        if x is None:
            sem += 1
            d.update({"testes": 0})
            for o in ops:
                d[f"{nomes_op[o]}_testes"] = 0
        else:
            _, _, med, nt, pct5, m4, m5, sub, por_op = x[:9]
            d.update({"testes": nt, "download_mediana_mbps": med, "download_4g_mediana_mbps": m4,
                      "download_5g_mediana_mbps": m5, "pct_testes_5g": pct5, "upload_mediana_mbps": sub})
            for o, q in zip(ops, por_op):
                d[f"{nomes_op[o]}_testes"], d[f"{nomes_op[o]}_download_mediana_mbps"] = (q if q else (0, None))
        mun.append(d)
    avisos = [f"Trimestre: {meta['referencia']} ({C.br(meta['testes'])} testes no arquivo da Anatel). "
              f"Operadoras com testes: {', '.join(ops)}."]
    if sem:
        avisos.append(f"{sem} município(s) sem nenhum teste no trimestre.")
    extra = {"coletado_em": meta["atualizado_em"], "consulta": meta.get("consulta"), "avisos": avisos,
             "metodo": f"Arquivo da Anatel lido: {meta.get('arquivo', {}).get('tamanho', '?')} bytes, "
                       f"de {meta.get('arquivo', {}).get('modificado', '?')}."}
    tabelas = {"brasil": (campos("brasil", ops), brasil), "uf": (campos("uf", ops), ufs),
               "municipio": (campos("municipio", ops), mun)}
    resultados = {p: C.gravar_pacote(CFG, p, tabelas, extra)}
    cons = C.consolidar(CFG)
    if cons:
        resultados.update({x: "consolidado agora" for x in cons})
    C.atualizar_conjunto(CFG, conferido_em=C.hoje().isoformat())
    C.registrar(CFG, resultados)


if __name__ == "__main__":
    main()
