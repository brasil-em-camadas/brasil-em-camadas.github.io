# Brasil em Camadas

Mapa interativo do Brasil por estado. Cada dado mostra de onde veio, de quando é e seu nível de confiança. O que falta aparece como falta, nunca como estimativa disfarçada.

## Como o projeto está organizado

```
site/                 o site em si (é isto que vai para o ar)
  index.html          a página principal: o mapa em globo 3D
  style.css           o visual básico (usado pelas duas versões)
  letras/             as letras do site (Barlow, Big Shoulders Display, JetBrains Mono), guardadas aqui, sem Google Fonts
  3d/                 o motor do mapa 3D: app3d.js (funcionamento), 3d.css, MapLibre (vendor/) e letras do mapa (fontes/)
                      (3d/index.html só redireciona quem tinha o endereço antigo da página de teste)
  2d/                 versão leve em 2D (D3, cópia em 2d/vendor/), para aparelhos que não abrem o globo
  vendor/count.js     script do contador de visitas (GoatCounter, licença ISC), guardado aqui
  data/fontes.json    o registro de todas as camadas: nome, ministério, fonte, nível de confiança
  data/*.json         os dados de cada camada
  data/geo/*.json     contornos, ferrovias, portos, aeroportos e limites do mar (ZEE, mar territorial,
                      zona contígua, plataforma continental estendida)
  data/relevo/        imagens de relevo do fundo (geradas por scripts/gerar_relevo.py)
  data/petroleo/      poços em produção, produção por estado, campos, plataformas e pré-sal (robô da ANP)
  data/energia/       usinas, linhas de transmissão e potência por estado (robô da EPE)
  data/celular/       sinal 4G/5G por estado e por município e municípios com 5G (robô da Anatel)
  data/luzes/         população de cada município, para as "Luzes à noite" da página 3D
scripts/
  atualizar_ibge.py   robô que busca dados novos na API do IBGE
  atualizar_epe.py    robô que busca usinas e linhas de transmissão no Webmap da EPE
  atualizar_anp.py    robô que busca petróleo e gás na ANP (produção por poço e servidor de mapas)
  atualizar_anatel.py robô que busca a telefonia celular nos dados abertos da Anatel (sinal 4G/5G e 5G nos municípios)
  gerar_relevo.py     gera as imagens de relevo (roda só quando acionado à mão)
  gerar_limites_maritimos.py  gera os limites do mar a partir do Marine Regions (roda só à mão)
  gerar_contorno_estados.py   gera o contorno dos estados a partir da malha oficial do IBGE (roda só à mão, uma vez por ano)
  gerar_sedes_municipais.py   gera a posição oficial das sedes municipais (IBGE, Localidades do Brasil 2022; roda só à mão)
  gerar_transportes_ibge.py   gera rodovias, ferrovias e portos a partir da base cartográfica 1:250.000 do IBGE (BC250; roda só à mão)
  dados/              arquivos de apoio dos robôs (ex.: posição da sede de cada município)
.github/workflows/
  site.yml            agenda do robô e publicação automática no GitHub Pages
```

## Como o site se atualiza

Todo dia 3 de cada mês o GitHub executa o robô. Ele busca população (por estado e por município), produção agrícola, rebanhos (por estado e o gado bovino de cada município) e aquicultura na API SIDRA do IBGE, energia elétrica na EPE (usinas em operação e linhas de transmissão), telefonia celular na Anatel (sinal 4G/5G, atualizado pela Anatel uma vez por ano, e municípios com 5G, todo mês) e petróleo e gás na ANP: a produção de cada poço no último mês que já tem dados de terra e de mar (o mar sai todo mês, a terra por trimestre), a posição dos poços, os campos, as plataformas e o polígono do pré-sal. Se a ANP falhar, os arquivos antigos ficam e o site é publicado mesmo assim, com a data antiga à vista. Se a busca der certo, os arquivos de dados são trocados e o site é republicado. Cada robô deixa o resultado de cada passo em `site/data/robo_ibge.json`, `site/data/petroleo/robo.json`, `site/data/energia/robo.json` e `site/data/celular/robo.json`, para conferir sem abrir o registro do GitHub. Se der errado, o dado antigo fica, com a data antiga, e o GitHub avisa por e-mail.

Para rodar na hora: aba **Actions** → **Atualizar dados e publicar** → **Run workflow**.

O contorno dos estados vem da Malha Municipal Digital do IBGE (recorte por UF, versão 2025), simplificado em dois níveis: `estados.json` (leve, usado na abertura, na versão leve e pelos robôs) e `estados_detalhe.json` (o globo troca para ele quando alguém aproxima o mapa). As divisas ficam idênticas nos dois lados, sem frestas. Quando o IBGE publicar a malha nova: `pip install shapely pyproj pyshp numpy` e `python scripts/gerar_contorno_estados.py --ano AAAA`; depois, rodar "Gerar relevo do mapa" no GitHub, porque o relevo é recortado pelo contorno.

Os limites do mar não entram no robô mensal, porque mudam raramente. Para refazer (versão nova do Marine Regions ou nova área aprovada pela ONU): `pip install shapely pyproj` e `python scripts/gerar_limites_maritimos.py`. O script confere a versão de cada camada e para sozinho se ela mudou, para lembrar de atualizar as citações e os textos em `site/data/fontes.json`. A Margem Equatorial usa o limite aprovado pela ONU em 2025, porque o Marine Regions ainda traz só o pedido de 2017: os 462 pontos da Tabela 4 do Anexo I do [resumo das recomendações da CLPC](https://static.un.org/Depts/los/clcs_new/submissions_files/bra02_rev17/20250227ComRecBrarev1summary.pdf) estão em `scripts/dados/clpc_margem_equatorial_2025.csv`, e o script confere cada ponto pela distância ao anterior que a própria tabela informa.

## Níveis de confiança

| Nível | Significado |
|---|---|
| Oficial · API | Vem da API do órgão oficial e atualiza sozinho |
| Oficial · manual | Arquivo oficial inserido à mão, com a data do download |
| Imprensa / entidade | Número público de terceiros, sempre com fonte e data |
| Base aberta internacional | Base mundial aberta, real porém menos detalhada |
| Estimado / calculado | Calculado pelo projeto, com o método explicado |
| Em apuração | Ainda sem dado; o campo fica vazio |

## Como acrescentar uma camada

1. Coloque o arquivo de dados em `site/data/`.
2. Registre a camada em `site/data/fontes.json` com nome, ministério, fonte e nível.
3. Se a fonte tiver API, acrescente a consulta em `scripts/atualizar_ibge.py` (ou crie um robô parecido).
4. Se o arquivo for grande e a camada começar desligada, marque `"sob_demanda": true` em `fontes.json`: o arquivo só é baixado quando alguém liga a camada. No globo, registre a conversão em `SOB` (`site/3d/app3d.js`); na versão leve, a função de desenho em `DESENHA` (`site/2d/app.js`).

## Fontes e licenças dos dados

- IBGE (população, agricultura, pecuária e aquicultura, contornos dos estados): dados públicos oficiais. Pecuária: Pesquisa da Pecuária Municipal, tabelas SIDRA 3939 (rebanhos) e 3940 (aquicultura).
- EPE (Empresa de Pesquisa Energética), Webmap do sistema elétrico existente: usinas e linhas de transmissão (dados públicos do governo federal).
- IBGE, base cartográfica 1:250.000 (BC250, versão 2025): rodovias federais e estaduais pavimentadas, ferrovias e portos. Dados públicos oficiais.
- Anatel, dados abertos (licença CC-BY, catálogo no dados.gov.br): Índice Brasileiro de Conectividade (IBC; população coberta por 4G ou 5G por estado e por município, fibra óptica e antenas por estado), em `paineis_de_dados/meu_municipio/ibc.zip`, e presença da telefonia móvel (RQUAL; tecnologias de cada operadora em cada município, todo mês), em `paineis_de_dados/infraestrutura/smp_mun_atendidos.zip`. O sinal é estimado pela Anatel a partir das antenas licenciadas, não é medição.
- Natural Earth (aeroportos, contorno dos países e imagens de relevo): domínio público.
- Eletropostos: números da ABVE citados por veículos de imprensa, com a fonte indicada em cada estado.
- Petróleo e gás: ANP. Produção por poço nos dados abertos (página "Fase de Desenvolvimento e Produção") e posição dos poços, campos, unidades de produção e polígono do pré-sal no servidor de mapas do GeoMapsANP. Dados abertos do governo federal: uso livre, citando a fonte (Decreto 8.777/2016, art. 2º, III). A soma nacional foi conferida com o Boletim Mensal da Produção da ANP; o polígono do pré-sal foi conferido com o Anexo da Lei 12.351/2010. Óleo equivalente (boe) pela convenção da ANP: 1.000 m³ de gás = 1 m³ de petróleo = 6,2898 barris.
- Limites do mar: Marine Regions, do Flanders Marine Institute (VLIZ, Bélgica), licença CC-BY 4.0. ZEE versão 12 ([doi:10.14284/632](https://doi.org/10.14284/632)), mar territorial versão 4 ([doi:10.14284/633](https://doi.org/10.14284/633)), zona contígua versão 4 ([doi:10.14284/630](https://doi.org/10.14284/630)), águas interiores versão 4 ([doi:10.14284/631](https://doi.org/10.14284/631)), todas de 2023, e plataforma continental estendida versão 2, de 2024 ([doi:10.14284/697](https://doi.org/10.14284/697)). O site usa um derivado simplificado só do Brasil; o original fica no Marine Regions, que pede para não ser redistribuído em outros lugares. Os desenhos não têm valor legal. Margem Equatorial: pontos do limite publicados pela CLPC/ONU (documento público das Nações Unidas). Situação de cada área da plataforma na ONU (CLPC): página do LEPLAC da Marinha (SECIRM).
- Luzes à noite: população de cada município pela API SIDRA do IBGE (Censo 2022); posição das sedes municipais do IBGE (Localidades do Brasil 2022), em `scripts/dados/sedes_municipais.csv`, gerado por `scripts/gerar_sedes_municipais.py`; iluminação noturna NASA Black Marble via GIBS (domínio público).

- Versão leve: biblioteca D3 7.8.5 (licença ISC), cópia em `site/2d/vendor/`. Contador de visitas: script `count.js` do GoatCounter (licença ISC), cópia em `site/vendor/`; a contagem continua indo para `brasilemcamadas.goatcounter.com`.
- Letras do site: Barlow, Big Shoulders Display e JetBrains Mono, licença SIL Open Font License 1.1; cópias dos pacotes Fontsource 5.3.0 (as mesmas versões do Google Fonts) em `site/letras/`, com as licenças. Só os conjuntos latin e latin-ext e os pesos usados.
- Mapa 3D: imagem do planeta NASA Blue Marble via GIBS (domínio público); altitude do terreno Terrain Tiles na AWS (dados abertos); motor MapLibre GL JS 5.24.0 (licença BSD, cópia em `site/3d/vendor/`); letras Open Sans (licença Apache 2.0), do projeto openmaptiles/fonts.

## Contagem de visitas

As páginas (principal e versão leve) contam visitas com o [GoatCounter](https://www.goatcounter.com/), painel em `brasilemcamadas.goatcounter.com`. Ele não usa cookies e não guarda endereço IP nem identificador de quem visita; o site avisa isso no rodapé. Navegadores automáticos e testes em `localhost` não são contados.

## Domínio próprio (para o futuro)

O site foi feito para mudar de endereço sem reescrever nada:

- Todos os links internos são relativos (`data/...`, `../style.css`). Nenhum arquivo do site cita `brasil-em-camadas.github.io`.
- O botão de apoio e os textos de fonte ficam em `site/data/fontes.json`, não espalhados pelo código.

Quando houver um domínio (ex.: `brasilemcamadas.com.br`):

1. Registrar o domínio (para `.com.br`, no Registro.br).
2. No GitHub: **Settings → Pages → Custom domain**, digitar o domínio e salvar. Marcar **Enforce HTTPS** quando liberar.
3. No painel do domínio, criar os apontamentos que o GitHub mostrar (registros `A` para os IPs do GitHub Pages e `CNAME` do `www` para `brasil-em-camadas.github.io`).
4. Esperar a propagação (de minutos a um dia). O endereço antigo continua funcionando e passa a redirecionar para o novo.

Detalhe: as preferências de cada visitante (tamanho da letra, painel recolhido) ficam guardadas por endereço; no domínio novo elas começam do zero uma vez.

## Licença

O código está sob a licença MIT (arquivo `LICENSE`): qualquer pessoa pode usar e modificar, desde que mantenha o aviso de autoria. Os dados seguem as licenças das próprias fontes, listadas acima.
