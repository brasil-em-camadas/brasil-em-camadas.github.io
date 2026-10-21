"""Gera scripts/dados/sedes_municipais.csv, a posição da sede (a cidade) de cada município, com a base oficial do IBGE.

Fonte: IBGE, Localidades do Brasil 2022 (Censo 2022), arquivo Localidades_UFs_shp.zip em
https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/localidades/Localidades_do_Brasil/2022/
Cada sede é a localidade cujo código é igual ao código do município: as cidades ("Sede Municipal"),
Brasília ("Capital Federal") e Fernando de Noronha ("Distrito Estadual").

Usado pelo robô do IBGE (atualizar_ibge.py) para pôr no mapa a população e o rebanho de cada município.
Roda só à mão, quando o IBGE publicar uma base de localidades nova:
  pip install pyshp
  python scripts/gerar_sedes_municipais.py            (baixa do IBGE)
  python scripts/gerar_sedes_municipais.py --cache PASTA   (PASTA com o Localidades_UFs_shp.zip já baixado)

Municípios criados depois da base do IBGE continuam com a posição que já estava no arquivo, marcados na coluna "fonte".
"""
import argparse
import csv
import io
import urllib.request
import zipfile
from pathlib import Path

import shapefile  # pyshp

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / "scripts" / "dados" / "sedes_municipais.csv"
URL = "https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/localidades/Localidades_do_Brasil/2022/Localidades_UFs_shp.zip"
FONTE = "IBGE, Localidades do Brasil 2022"


def baixar(cache):
    if cache:
        return (Path(cache) / "Localidades_UFs_shp.zip").read_bytes()
    req = urllib.request.Request(URL, headers={"User-Agent": "brasil-em-camadas (dados abertos)"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def sedes_ibge(dados):
    z = zipfile.ZipFile(io.BytesIO(dados))
    sedes = {}
    for nome in sorted(n for n in z.namelist() if n.endswith(".shp")):
        base = nome[:-4]
        leitor = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), shx=io.BytesIO(z.read(base + ".shx")),
                                  dbf=io.BytesIO(z.read(base + ".dbf")), encoding="utf-8")
        for rec in leitor.records():
            d = rec.as_dict()
            if d["CD_LOCALID"] == d["CD_MUN"]:
                sedes[d["CD_MUN"]] = {"codigo_ibge": d["CD_MUN"], "nome": d["NM_MUN"], "latitude": f"{d['LAT_LOCALI']:.4f}",
                                      "longitude": f"{d['LONG_LOCAL']:.4f}", "uf": d["SIGLA_UF"], "fonte": FONTE}
    return sedes


def main(cache):
    sedes = sedes_ibge(baixar(cache))
    if len(sedes) < 5500:
        raise SystemExit(f"só {len(sedes)} sedes na base do IBGE; algo mudou no arquivo")
    antigas = {}
    if ARQ.exists():
        antigas = {r["codigo_ibge"]: r for r in csv.DictReader(ARQ.open(encoding="utf-8"))}
    mantidas = []
    for k, r in antigas.items():
        if k not in sedes:   # município criado depois da base do IBGE: fica a posição que já havia
            sedes[k] = {"codigo_ibge": k, "nome": r["nome"], "latitude": r["latitude"], "longitude": r["longitude"],
                        "uf": r.get("uf", ""), "fonte": r.get("fonte") or "base aberta municipios-brasileiros (MIT)"}
            mantidas.append(f"{r['nome']} ({k})")
    with ARQ.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["codigo_ibge", "nome", "latitude", "longitude", "uf", "fonte"])
        w.writeheader()
        for k in sorted(sedes):
            w.writerow(sedes[k])
    print(f"{len(sedes)} sedes gravadas em {ARQ.relative_to(RAIZ)}; mantidas da base anterior: {mantidas or 'nenhuma'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", help="pasta com o Localidades_UFs_shp.zip já baixado")
    main(ap.parse_args().cache)
