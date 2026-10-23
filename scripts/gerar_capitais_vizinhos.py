"""Capitais dos países vizinhos, para o mapa: site/data/geo/capitais_vizinhos.json.

Fonte: Natural Earth, Populated Places 1:10 milhões (domínio público), arquivo GeoJSON do repositório oficial no GitHub.
Pega as capitais nacionais ("Admin-0 capital") dos países da América do Sul que aparecem no mapa e Caiena (Guiana
Francesa, que é uma região da França, não um país). A Bolívia tem duas: La Paz (sede do governo) e Sucre (capital
constitucional). Chile e Equador não fazem fronteira com o Brasil, mas aparecem no mapa e entram também.
Nomes em português. Só roda à mão (as capitais não mudam): python3 scripts/gerar_capitais_vizinhos.py
Só usa a biblioteca padrão do Python.
"""
import datetime
import json
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places_simple.geojson"
SAIDA = Path(__file__).resolve().parent.parent / "site/data/geo/capitais_vizinhos.json"

# país no Natural Earth → (nome do país em português, com a preposição, e se faz fronteira com o Brasil)
PAISES = {
    "Argentina": ("da Argentina", True), "Uruguay": ("do Uruguai", True), "Paraguay": ("do Paraguai", True),
    "Bolivia": ("da Bolívia", True), "Peru": ("do Peru", True), "Colombia": ("da Colômbia", True),
    "Venezuela": ("da Venezuela", True), "Guyana": ("da Guiana", True), "Suriname": ("do Suriname", True),
    "Ecuador": ("do Equador", False), "Chile": ("do Chile", False),
}
NOMES = {"Montevideo": "Montevidéu", "Asunción": "Assunção", "Bogota": "Bogotá", "Cayenne": "Caiena"}
NOTAS = {
    "La Paz": "Sede do governo da Bolívia (a capital constitucional é Sucre)",
    "Sucre": "Capital constitucional da Bolívia (o governo fica em La Paz)",
    "Cayenne": "Capital da Guiana Francesa, região ultramarina da França (não é um país)",
}

req = urllib.request.Request(URL, headers={"User-Agent": "brasil-em-camadas"})
with urllib.request.urlopen(req, timeout=120) as r:
    dados = json.load(r)

capitais = []
for f in dados["features"]:
    p = f["properties"]
    pais, nome = p.get("adm0name"), p.get("name")
    nacional = pais in PAISES and p.get("featurecla") == "Admin-0 capital"
    if not (nacional or nome == "Cayenne" and pais == "France"):
        continue
    lon, lat = f["geometry"]["coordinates"]
    capitais.append({
        "n": NOMES.get(nome, nome),
        "c": [round(lon, 3), round(lat, 3)],
        "d": NOTAS.get(nome) or "Capital " + PAISES[pais][0],
        "fronteira": nome == "Cayenne" or PAISES[pais][1],
    })
capitais.sort(key=lambda c: -c["c"][1])   # do norte para o sul
esperadas = {"Buenos Aires", "Montevidéu", "Assunção", "La Paz", "Sucre", "Lima", "Bogotá", "Caracas", "Georgetown",
             "Paramaribo", "Caiena", "Quito", "Santiago"}
achadas = {c["n"] for c in capitais}
if achadas != esperadas:
    raise SystemExit(f"capitais diferentes do esperado: faltam {esperadas - achadas}, sobram {achadas - esperadas}")

saida = {
    "meta": {
        "fonte": "Natural Earth, Populated Places 1:10 milhões (domínio público)",
        "nivel": "base",
        "endereco": URL,
        "atualizado_em": datetime.date.today().isoformat(),
        "nota": "Bolívia: La Paz é a sede do governo e Sucre a capital constitucional. Caiena é a capital da Guiana "
                "Francesa, região ultramarina da França. Chile e Equador não fazem fronteira com o Brasil.",
    },
    "capitais": capitais,
}
SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", SAIDA, len(capitais), "capitais")
