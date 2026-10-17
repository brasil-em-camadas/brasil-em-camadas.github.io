# Brasil em Camadas

Mapa interativo do Brasil por estado. Cada dado mostra de onde veio, de quando é e seu nível de confiança. O que falta aparece como falta, nunca como estimativa disfarçada.

## Como o projeto está organizado

```
site/                 o site em si (é isto que vai para o ar)
  index.html          a página principal: o mapa em globo 3D
  style.css           o visual básico (usado pelas duas versões)
  3d/                 o motor do mapa 3D: app3d.js (funcionamento), 3d.css, MapLibre (vendor/) e letras do mapa (fontes/)
                      (3d/index.html só redireciona quem tinha o endereço antigo da página de teste)
  2d/                 versão leve em 2D (D3), para aparelhos que não abrem o globo
  data/fontes.json    o registro de todas as camadas: nome, ministério, fonte, nível de confiança
  data/*.json         os dados de cada camada
  data/geo/*.json     contornos, ferrovias, portos, aeroportos, ZEE
  data/relevo/        imagens de relevo do fundo (geradas por scripts/gerar_relevo.py)
  data/luzes/         população de cada município, para as "Luzes à noite" da página 3D
scripts/
  atualizar_ibge.py   robô que busca dados novos na API do IBGE
  gerar_relevo.py     gera as imagens de relevo (roda só quando acionado à mão)
  dados/              arquivos de apoio dos robôs (ex.: posição da sede de cada município)
.github/workflows/
  site.yml            agenda do robô e publicação automática no GitHub Pages
```

## Como o site se atualiza

Todo dia 3 de cada mês o GitHub executa o robô. Ele busca população (por estado e por município) e produção agrícola na API SIDRA do IBGE. Se a busca der certo, os arquivos de dados são trocados e o site é republicado. Se der errado, o dado antigo fica, com a data antiga, e o GitHub avisa por e-mail.

Para rodar na hora: aba **Actions** → **Atualizar dados e publicar** → **Run workflow**.

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

## Fontes e licenças dos dados

- IBGE (população, agricultura, contornos dos estados): dados públicos oficiais.
- Natural Earth (ferrovias, portos, aeroportos, contorno dos países e imagens de relevo): domínio público.
- Eletropostos: números da ABVE citados por veículos de imprensa, com a fonte indicada em cada estado.
- Luzes à noite: população de cada município pela API SIDRA do IBGE (Censo 2022); posição das sedes municipais da base aberta [municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) (licença MIT), cópia em `scripts/dados/`; iluminação noturna NASA Black Marble via GIBS (domínio público).

- Mapa 3D: imagem do planeta NASA Blue Marble via GIBS (domínio público); altitude do terreno Terrain Tiles na AWS (dados abertos); motor MapLibre GL JS 5.24.0 (licença BSD, cópia em `site/3d/vendor/`); letras Open Sans (licença Apache 2.0), do projeto openmaptiles/fonts.

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
