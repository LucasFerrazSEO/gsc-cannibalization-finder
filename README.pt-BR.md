[English](README.md) · **Português (Brasil)**

# gsc-cannibalization-finder

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) ![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)

`gsc-cannibalization-finder` é uma ferramenta gratuita, de código aberto e
de linha de comando, que lê um export do Google Search Console com as
dimensões consulta e página juntas e lista as consultas em que duas ou mais
URLs do mesmo site dividem impressões. Para cada uma, mostra como
impressões e cliques se dividem, a posição média de cada URL e uma
severidade, e ainda ordena os pares de páginas que mais dividem consultas.
Roda offline na sua máquina, e nenhum dado é enviado para servidor nenhum.

## Sumário

- [Contexto](#contexto)
- [O que a ferramenta verifica](#o-que-a-ferramenta-verifica)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Uso](#uso)
- [Perguntas frequentes](#perguntas-frequentes)
- [Limitações](#limitações)
- [Método e origem](#método-e-origem)
- [Como contribuir](#como-contribuir)
- [Autor](#autor)
- [Licença](#licença)

## Contexto

Quando a Home, uma página de serviço e uma página de região aparecem para
a mesma consulta, o site pode estar competindo consigo mesmo: as
impressões se dividem, cada URL fica um pouco abaixo de onde uma URL forte
ficaria sozinha, e a página que você quer posicionar nem sempre é a que o
Google escolhe. A interface do Search Console não mostra isso de forma
direta, porque o export padrão separa consultas e páginas em abas
diferentes. Com as dimensões consulta e página juntas (API do Search
Console, Looker Studio ou export em massa para o BigQuery), a sobreposição
aparece.

Dividir uma consulta nem sempre é problema. Duas URLs do mesmo domínio na
mesma página de resultados podem ser um bom resultado. A ferramenta aponta
candidatos para revisão humana; ela não decide o que fundir, redirecionar
ou reescrever.

## O que a ferramenta verifica

1. **Consultas com 2 ou mais URLs.** Cada URL precisa de pelo menos
   `--min-impressions` impressões (padrão 10) para contar, assim uma
   aparição isolada não vira ruído.
2. **Divisão de impressões e cliques.** A participação (%) de cada URL na
   consulta e a posição média de cada uma, ponderada por impressões quando
   a mesma consulta e URL aparecem em várias linhas (por data ou
   dispositivo).
3. **Severidade.**
   - **ALTA**: a segunda URL tem pelo menos `--share` das impressões
     (padrão 20%) e as duas primeiras estão a menos de 10 posições uma da
     outra.
   - **MÉDIA**: só uma das duas condições vale.
   - **BAIXA**: nenhuma das duas vale.
   Esses limiares são padrões ajustáveis, escolhidos para triagem, e não
   um número oficial do Google.
4. **Pares de URLs.** Quais pares de páginas dividem mais consultas,
   quantas delas têm severidade ALTA e as impressões envolvidas.
5. **Exclusão de marca.** `--brand "termo1,termo2"` tira as consultas que
   contêm esses termos, porque consulta de marca costuma mostrar várias
   URLs de propósito.

Os nomes de coluna são reconhecidos em inglês e em português ("Consultas
principais", "Página", "Cliques", "Impressões", "CTR", "Posição"), com
separador `,` ou `;` e decimal com vírgula ou ponto. No export em massa do
BigQuery (colunas `url` e `sum_top_position`), a posição é calculada como
`sum_top_position / impressões + 1`. A coluna de CTR é ignorada e
recalculada a partir de cliques e impressões.

## Requisitos

Python 3.9 ou mais recente. Só biblioteca padrão, sem dependência externa.

## Instalação

```bash
git clone https://github.com/LucasFerrazSEO/gsc-cannibalization-finder.git
cd gsc-cannibalization-finder
```

## Uso

**1. Exporte consulta e página juntas** pela API do Search Console, pelo
Looker Studio ou pelo BigQuery, em CSV. O arquivo precisa de uma coluna de
consulta, uma de página, impressões e posição (cliques são opcionais).

**2. Rode a ferramenta.**

```bash
python gsc_cannibalization_finder.py examples/gsc-export-example.csv --brand "example"
```

**3. Leia o relatório.** Saída real do arquivo de exemplo em `examples/`,
que usa `example.com` e números inventados (dados fictícios):

```
=== gsc-cannibalization-finder: examples/gsc-export-example.csv ===
13 linha(s) lida(s), 5 consulta(s) distinta(s), 2 linha(s) de marca excluída(s)
Critério: 2+ URLs com >= 10 impressões cada | ALTA = 2ª URL >= 20% das impressões e diferença de posição < 10
4 consulta(s) dividida(s) | ALTA 2 | MÉDIA 1 | BAIXA 1 | 5 par(es) de URLs

  ALTA   "criação de sites"  3 URLs, 2.618 impr., 2ª URL com 42,8%, dif. posição 2,2
            56,5% impr.  27,9% cliques  pos.   9,4  https://example.com/
            42,8% impr.  72,1% cliques  pos.   7,2  https://example.com/servicos/criacao-de-sites/
             0,7% impr.   0,0% cliques  pos.  38,5  https://example.com/blog/quanto-custa-um-site/
  ALTA   "agência de seo em curitiba"  2 URLs, 790 impr., 2ª URL com 48,1%, dif. posição 1,6
            51,9% impr.  56,2% cliques  pos.   8,3  https://example.com/
            48,1% impr.  43,8% cliques  pos.   9,9  https://example.com/regioes/curitiba/
  MÉDIA  "consultoria de seo"  2 URLs, 1.040 impr., 2ª URL com 13,5%, dif. posição 5,9
            86,5% impr.  88,0% cliques  pos.   6,1  https://example.com/servicos/consultoria-de-seo/
            13,5% impr.  12,0% cliques  pos.  12,0  https://example.com/
  BAIXA  "quanto custa um site"  2 URLs, 2.145 impr., 2ª URL com 4,4%, dif. posição 11,4
            95,6% impr.  95,2% cliques  pos.   4,2  https://example.com/blog/quanto-custa-um-site/
             4,4% impr.   4,8% cliques  pos.  15,6  https://example.com/servicos/criacao-de-sites/

-- PARES DE URLs QUE MAIS DIVIDEM CONSULTAS --
  2 consulta(s), 1 ALTA, 3.283 impr.
      https://example.com/blog/quanto-custa-um-site/
      https://example.com/servicos/criacao-de-sites/
      ex.: criação de sites; quanto custa um site
  1 consulta(s), 1 ALTA, 2.600 impr.
      https://example.com/
      https://example.com/servicos/criacao-de-sites/
      ex.: criação de sites
  ...

(Consulta dividida nem sempre é problema: duas URLs do mesmo site na SERP podem ser bom sinal. Revisão humana decide.)
```

**4. Ajuste os limiares** ao tamanho do seu site.

```bash
python gsc_cannibalization_finder.py export.csv --min-impressions 50 --share 30 --top 50
```

**5. Salve o resultado** para uma planilha ou outro script. `--csv` grava
uma linha por consulta e URL; `--json` grava consultas e pares. Use `-`
para imprimir na tela.

```bash
python gsc_cannibalization_finder.py export.csv --csv consultas.csv --json relatorio.json
```

**6. Use em CI ou em rotina agendada.** Com `--strict`, o código de saída
é 1 quando existe pelo menos uma consulta de severidade ALTA.

```bash
python gsc_cannibalization_finder.py export.csv --strict
```

## Perguntas frequentes

**Posso usar o export padrão da interface do Search Console?**
Sozinho, não. O export da interface separa consultas e páginas em abas
diferentes, sem o cruzamento das duas. Use a API do Search Console, o
Looker Studio ou o export em massa para o BigQuery, que devolvem as duas
dimensões na mesma linha.

**Consulta com severidade ALTA significa que preciso fundir ou redirecionar páginas?**
Não. Significa que a consulta merece uma olhada. Duas URLs na mesma página
de resultados podem ser um bom resultado, e uma página de serviço e um
artigo podem atender intenções diferentes por trás das mesmas palavras. A
decisão fica com quem conhece o site.

**Por que os limiares são 10 impressões, 20% e 10 posições?**
São padrões de triagem, não regras do Google. Dez impressões filtram
aparições isoladas, 20% indica que a segunda URL leva uma fatia visível, e
10 posições equivalem mais ou menos a uma página de resultados. Ajuste com
`--min-impressions` e `--share` conforme os seus dados.

**A ferramenta é gratuita e precisa de internet?**
É gratuita e de código aberto, sob a licença MIT. Ela só lê o arquivo
local que você passa; nenhum dado sai da sua máquina.

## Limitações

O Search Console omite consultas anonimizadas e arredonda alguns números,
e o resultado herda essas lacunas. A posição média é um agregado e esconde
a variação por dispositivo, país e data. A ferramenta não lê as páginas,
então não sabe dizer se duas URLs respondem à mesma intenção. A exclusão
de marca é uma busca simples por trecho de texto.

## Método e origem

A ferramenta nasceu da regra de canibalização usada no
[lucasferrazseo.com](https://lucasferrazseo.com) para impedir que a Home,
as páginas de serviço e as páginas de região disputem a mesma consulta:
cada página tem o próprio termo-alvo, e a sobreposição é conferida nos
dados do Search Console. Aqui ela está generalizada para uso público, sem
regras específicas de um site.

## Como contribuir

Relatos de erro e sugestões são bem-vindos pelas [Issues do GitHub](https://github.com/LucasFerrazSEO/gsc-cannibalization-finder/issues).

## Autor

[Lucas Ferraz](https://lucasferraz.com) é especialista em SEO, criação de sites e Generative Engine Optimization e fundador da [Lucas Ferraz SEO](https://lucasferrazseo.com).

## Licença

MIT. Veja o arquivo [LICENSE](LICENSE).
