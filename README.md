# Brasil em Camadas

Mapa interativo do Brasil por estado. Cada dado mostra de onde veio, de quando é e seu nível de confiança. O que falta aparece como falta, nunca como estimativa disfarçada.

## Como o projeto está organizado

```
site/                 o site em si (é isto que vai para o ar)
  index.html          a página
  style.css           o visual
  app.js              o funcionamento do mapa
  data/fontes.json    o registro de todas as camadas: nome, ministério, fonte, nível de confiança
  data/*.json         os dados de cada camada
  data/geo/*.json     contornos, ferrovias, portos, aeroportos, ZEE
  data/relevo/        imagens de relevo do fundo (geradas por scripts/gerar_relevo.py)
scripts/
  atualizar_ibge.py   robô que busca dados novos na API do IBGE
  gerar_relevo.py     gera as imagens de relevo (roda só quando acionado à mão)
.github/workflows/
  site.yml            agenda do robô e publicação automática no GitHub Pages
```

## Como o site se atualiza

Todo dia 3 de cada mês o GitHub executa o robô. Ele busca população e produção agrícola na API SIDRA do IBGE. Se a busca der certo, os arquivos de dados são trocados e o site é republicado. Se der errado, o dado antigo fica, com a data antiga, e o GitHub avisa por e-mail.

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

## Licença

O código está sob a licença MIT (arquivo `LICENSE`): qualquer pessoa pode usar e modificar, desde que mantenha o aviso de autoria. Os dados seguem as licenças das próprias fontes, listadas acima.
