"""Desenhos para a aba do navegador (favicon) do Brasil em Camadas, em SVG de 64 × 64, ouro sobre escuro.
Opções (27/10/2026): A, três camadas em losango; B, o Brasil; C, globo em faixas; D, o Brasil em camadas inclinadas;
E, o Brasil cortado em três faixas; F, três folhas com o Brasil, empilhadas (a recomendada). O contorno do Brasil vem de
site/data/geo/estados.json (sem as ilhas), alisado e simplificado. Grava site/aba/icone_<letra>.svg.
Rodar da raiz do repositório:  python scripts/estudos/icone_aba.py
Os PNG (32 e 180 px) foram feitos no navegador sem cabeça (Playwright), a partir do SVG."""
import json, math
from shapely.geometry import shape
from shapely.ops import unary_union
E = json.load(open('site/data/geo/estados.json', encoding='utf-8'))
br = unary_union([shape(f['geometry']) for f in E['features']]).buffer(0)
if br.geom_type == 'MultiPolygon':
    br = max(br.geoms, key=lambda g: g.area)   # só o continente (sem as ilhas)
br = br.buffer(0.35).buffer(-0.35).simplify(0.32)   # contorno liso, sem recortes pequenos
k = math.cos(math.radians(14))
x0, y0, x1, y1 = br.bounds
def caminho(geo, cx, cy, larg, achata=1.0):
    """contorno do Brasil centrado em (cx, cy), com largura larg (unidades do SVG); achata < 1 = visto inclinado"""
    w, h = (x1 - x0) * k, (y1 - y0)
    s = larg / w
    pts = [((x - x0) * k * s - larg / 2 + cx, (y1 - y) * s * achata - h * s * achata / 2 + cy) for x, y in geo.exterior.coords]
    return 'M' + 'L'.join(f'{a:.1f} {b:.1f}' for a, b in pts) + 'Z'
ESC, OURO, OURO2, OURO3, OURO4 = '#0b1215', '#f6cd5c', '#d9a23a', '#a9772d', '#6f5233'
fundo = f'<rect width="64" height="64" rx="14" fill="{ESC}"/>'
def svg(corpo, f=fundo):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{f}{corpo}</svg>'
# A: três camadas (placas em losango, vistas de lado)
def placa(cy, cor):
    return f'<path d="M32 {cy - 11}L56 {cy}L32 {cy + 11}L8 {cy}Z" fill="{cor}" stroke="{ESC}" stroke-width="3" stroke-linejoin="round"/>'
A = svg(placa(43, OURO4) + placa(33, OURO2) + placa(23, OURO))
# B: o Brasil em ouro
B = svg(f'<path d="{caminho(br, 32.5, 32.5, 50)}" fill="{OURO}" stroke="#fff1bf" stroke-width="1.2" stroke-linejoin="round"/>')
# C: globo em faixas (camadas), do ouro aceso ao fundo
faixas = ''.join(f'<rect x="6" y="{6 + i * 13}" width="52" height="11" fill="{c}"/>' for i, c in enumerate((OURO, OURO2, OURO3, OURO4)))
C = svg(f'<defs><clipPath id="g"><circle cx="32" cy="32" r="25"/></clipPath></defs><g clip-path="url(#g)">{faixas}</g>'
        f'<circle cx="32" cy="32" r="25" fill="none" stroke="#fff1bf" stroke-opacity=".55" stroke-width="1.2"/>')
# D: o Brasil em camadas (três silhuetas inclinadas, empilhadas)
D = svg(''.join(f'<path d="{caminho(br, 32, cy, 50, 0.52)}" fill="{c}" stroke="{ESC}" stroke-width="2.4" stroke-linejoin="round"/>'
                for cy, c in ((44, OURO4), (35, OURO2), (26, OURO))))
for nome, s in zip('abcd', (A, B, C, D)):
    open(f'site/aba/icone_{nome}.svg', 'w').write(s)
print('ok', br.geom_type, len(br.exterior.coords), 'pontos')
# E: o Brasil cortado em três faixas (camadas), do ouro aceso (norte) ao ouro fundo (sul)
cam = caminho(br, 32.5, 32.5, 50)
faixasE = ''.join(f'<rect x="0" y="{y}" width="64" height="{h}" fill="{c}"/>' for y, h, c in ((0, 23.2, OURO), (25.4, 12.2, OURO2), (39.8, 30, OURO3)))
E_ = svg(f'<defs><clipPath id="b"><path d="{cam}"/></clipPath></defs><g clip-path="url(#b)">{faixasE}</g>')
# F: três folhas com o Brasil, empilhadas (as de baixo mais escuras, deslocadas para baixo e para a direita)
F_ = svg(''.join(f'<path d="{caminho(br, 30 + d, 30 + d, 46)}" fill="{c}" stroke="{ESC}" stroke-width="1.6" stroke-linejoin="round"/>'
                 for d, c in ((5.2, OURO4), (2.6, OURO2), (0, OURO))))
open('site/aba/icone_e.svg', 'w').write(E_); open('site/aba/icone_f.svg', 'w').write(F_)
