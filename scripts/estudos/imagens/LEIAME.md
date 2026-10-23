# Estudos de visual guardados (não vão para o ar)

Imagens do laboratório de texturas e dos testes de relevo de 22/10/2026, guardadas para uso futuro (pedido do Edu).
Todas em Mercator, recorte de -75 a -28 de longitude e de 6 a -34,5 de latitude (o mesmo do relevo do site).

| Arquivo | O que é |
|---|---|
| `holograma_sem.jpg`, `ouro_sem.jpg`, `verde_sem.jpg` | as três texturas sem pintura |
| `holograma_reb.jpg`, `ouro_reb.jpg`, `verde_reb.jpg` | as três texturas pintadas pelo rebanho bovino (IBGE, PPM 2025) |
| `*_luz_populacao.jpg` | cada textura com a luz "População" (IBGE, Censo 2022), como no globo |
| `*_luz_noturna.jpg` | cada textura com a "Iluminação noturna" (NASA Black Marble 2016, domínio público) |
| `comparar_luzes.jpg` | painel: texturas nas colunas (holograma, ouro, verde), luzes nas linhas (população, noturna) |
| `comparar_holograma_ouro_rebanho.jpg` | holograma e ouro lado a lado, com a pintura do rebanho |
| `globo_holograma_textura.png`, `globo_holograma_rebanho.png` | o holograma aplicado no globo da versão de teste |
| `relevo_blocos_rebanho.png` | estados em blocos (descartado: paredes nas divisas) |
| `relevo_ondas_*.png` | estados em ondas, sem paredes (descartado: "não está ficando bom") |

Para refazer: `python3 scripts/estudos/texturas.py site/data <saída>` (texturas) e
`python3 scripts/estudos/texturas_luzes.py site/data <saída>` (com as luzes; baixa os ladrilhos da NASA). Precisam de numpy e Pillow.
A textura do holograma usada no globo de teste é `site/data/relevo/holograma.webp` (`scripts/estudos/terra_holograma.py`).
