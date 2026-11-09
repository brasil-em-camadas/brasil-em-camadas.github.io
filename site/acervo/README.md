# Acervo de dados por período

O acervo guarda os números do Brasil em Camadas período a período, para baixar e comparar. O mapa mostra o período mais recente; aqui ficam todos, cada um com a fonte, a data da coleta e o nível de confiança.

Regra principal: **pacote publicado nunca é apagado nem sobrescrito.** Se a fonte mudar um número depois, entra uma versão nova do pacote, com a nota do que mudou, e a antiga continua aqui para baixar.

## Conjuntos e pacotes

- **Conjunto**: um tipo de dado de uma fonte, medido sempre do mesmo jeito (ex.: "Lavouras – IBGE"). Cada conjunto tem uma pasta.
- **Pacote**: um período de um conjunto (ex.: as lavouras de 2024). Cada pacote tem uma pasta dentro da do conjunto.

| Conjunto | Pasta | Fonte | Períodos |
|---|---|---|---|
| Lavouras (Produção Agrícola Municipal) | `lavouras-ibge/` | IBGE, tabela 5457 da SIDRA | anos desde 1974 (municípios desde 2010) |
| Banda larga fixa | `banda-larga-anatel/` | Anatel, acessos de banda larga fixa | anos desde 2007 (municípios desde 2010) e trimestres |
| Velocidade medida no celular | `velocidade-celular-anatel/` | Anatel, medidas de velocidade da telefonia móvel | trimestres desde o 2º de 2026 |

A lista sempre atualizada está em `indice.json`.

## Períodos

- **Ano fechado**: um pacote por ano (`2025`).
- **Ano em aberto**: um pacote por trimestre que já terminou (`2026-T1`, `2026-T2`…). Trimestre, não semestre: várias fontes já saem por trimestre, e um semestre é a soma de dois.
- Nas fontes mensais, os trimestres dos anos fechados também ficam guardados (só Brasil e estados), para comparar o mesmo trecho de anos diferentes. O mês a mês e os "últimos 12 meses" ficam só no mapa.
- O pacote só nasce quando a fonte tem o período inteiro.

**Como o número vira ano**
- *Fluxo* (o que se soma no período: produção, passageiros, exportação): o ano é a soma dos trimestres.
- *Posição* (o que existe numa data: rebanho, usinas, acessos de internet): o ano é a posição em dezembro, e o trimestre é a posição no último mês dele (março, junho, setembro, dezembro).
- Mediana, porcentagem e índice não se somam: a velocidade do celular, por exemplo, só existe por trimestre. Só há pacote anual quando a conta é certa.

## Situação e versões

- **Preliminar**: o período fechou há pouco e a fonte ainda pode revisar. O robô confere todo mês.
- **Consolidado**: a fonte declarou o número definitivo, ou passaram 12 meses da publicação do período. A publicação conta como o fim do período mais o atraso típico da fonte (PAM do IBGE: 9 meses; Anatel: 2 meses); a data em que o pacote vira consolidado fica na ficha (`consolida_em`).
- Se a fonte mudar um número, o pacote inteiro vai, sem mudar um byte, para `<período>/versoes/v1/` (depois `v2/`…), e a versão nova entra no lugar, com a nota do que mudou na ficha (ex.: "uf · SP · acessos: 1.234 → 1.240"). A única mudança permitida num pacote publicado, fora isso, é a situação passar de preliminar a consolidado na ficha, sem mexer nos dados.

## Arquivos

```
indice.json                     lista de conjuntos e períodos (o site lê daqui)
municipios.csv                  código, nome, estado e posição da sede de cada município (guardado uma vez só)
<conjunto>/conjunto.json        o que é, fonte, método, colunas e a lista de pacotes e versões (com o hash de cada ficha)
<conjunto>/serie_uf.csv         todos os períodos por estado (e Brasil, com uf = BR), gerado, para gráficos
<conjunto>/<período>/datapackage.json   ficha técnica do pacote
<conjunto>/<período>/brasil.csv         Brasil
<conjunto>/<período>/uf.csv             estados
<conjunto>/<período>/municipio.csv      municípios (quando o pacote tem)
<conjunto>/<período>/versoes/vN/        versões antigas, inteiras
```

## Tabelas (CSV)

- Uma linha por lugar, com o código do IBGE (`codigo_ibge`: `1` = Brasil, como na SIDRA; 2 dígitos = estado; 7 dígitos = município). Estados e municípios trazem também a sigla do estado (`uf`); o nome do município fica em `municipios.csv`.
- Quando o conjunto tem uma lista de itens (lavouras, por exemplo), é uma linha por lugar e item, e a lista dos itens do período fica na ficha (`itens`). Um item que não aparece num lugar teve zero registrado pela fonte; fora da lista, o item não foi pesquisado naquele período.
- Vírgula separa as colunas e ponto marca os decimais (o padrão dos programas); texto em UTF-8.
- Valores em dinheiro no valor de cada ano, como a fonte publica, sem descontar a inflação, e só a partir de 1994 (Plano Real). Quantidades desde o início da fonte.

**Marcas nas células**

| Célula | Quer dizer |
|---|---|
| número | o valor (0 é zero de verdade) |
| vazia | sem dado |
| `X` | a fonte esconde o número para não identificar empresas |
| `..` | não se aplica |

O total do Brasil vem da própria fonte, não da soma dos estados; quando não batem, a ficha mostra a diferença. Cada pacote traz só os municípios que existiam no período: num ano em que um município ainda não existia, ele não aparece (não se aplica), nunca como zero.

## Ficha técnica (`datapackage.json`)

Segue o padrão aberto [Frictionless Data Package](https://datapackage.org/) (perfil `tabular-data-package`), que abre direto em Python e R. Além dos campos do padrão, traz: período (`periodo`, `inicio`, `fim`), situação e versão (`situacao`, `consolida_em`, `versao`), data da coleta (`coletado_em`), fonte com o endereço da consulta (`fonte`), nível de confiança (`nivel_confianca`, e coluna por coluna quando a conta é do projeto), unidade de cada coluna (`unidade`), tipo de medida (`medida`), método, avisos, as marcas e as licenças. Cada arquivo do pacote vem com o tamanho (`bytes`) e o hash (`hash`, SHA-256), para conferir que é o arquivo publicado. A ficha não traz o endereço do site: o "como citar" é montado pela página de download.

Exemplo em Python, com a biblioteca `frictionless`:

```python
from frictionless import Package
pacote = Package("lavouras-ibge/2024/datapackage.json")
tabela = pacote.get_resource("uf").read_rows()
```

## Licença

Os pacotes são publicados sob a licença [Creative Commons Atribuição 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/deed.pt_BR): qualquer pessoa pode usar, citando o Brasil em Camadas e a fonte. Os números seguem também a licença da fonte, anotada na ficha.

## Para quem mantém

- Robôs: `scripts/acervo/` (um por conjunto; a parte comum em `comum.py`). Rodam todo mês no GitHub, depois dos robôs do mapa.
- Verificador: `scripts/acervo/verificar.py`. Confere a ficha de cada pacote contra os arquivos e, antes de publicar, que nenhum pacote que já estava no ar foi mudado ou apagado. Se achar problema, a publicação para.
- Pastas, nomes de arquivos e colunas não mudam depois de publicados. Uma coluna nova num período novo é permitida (a ficha de cada pacote diz quais colunas ele tem).
