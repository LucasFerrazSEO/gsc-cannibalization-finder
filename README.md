**English** · [Português (Brasil)](README.pt-BR.md)

# gsc-cannibalization-finder

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) ![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)

`gsc-cannibalization-finder` is a free, open source command-line tool that
reads a Google Search Console export with the query and page dimensions
together and lists the queries where two or more URLs of the same site
split impressions. For each one it shows how impressions and clicks are
divided, the average position of each URL and a severity label, and it
also ranks the pairs of pages that share the most queries. It runs offline
on your machine, and no data is sent to any server.

The tool prints its report in Brazilian Portuguese.

## Contents

- [Background](#background)
- [What it checks](#what-it-checks)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [FAQ](#faq)
- [Limitations](#limitations)
- [Methodology](#methodology)
- [Contributing](#contributing)
- [Author](#author)
- [License](#license)

## Background

When the home page, a service page and a location page all show up for the
same query, the site may be competing with itself: impressions are split,
each URL sits a little lower than a single strong URL would, and the page
you want to rank is not always the one Google picks. The Search Console
interface does not show this directly, because its default export puts
queries and pages in separate tabs. With the query and page dimensions
together (Search Console API, Looker Studio or the BigQuery bulk export),
the overlap becomes visible.

Splitting a query is not always a problem. Two URLs from the same domain
on the same results page can be a good outcome. This tool points to
candidates for human review; it does not decide what to merge, redirect or
rewrite.

## What it checks

1. **Queries with 2 or more URLs.** Each URL needs at least
   `--min-impressions` impressions (default 10) for the query to count, so
   one-off impressions do not create noise.
2. **Impression and click split.** The share (%) of each URL within the
   query, plus the average position of each one, weighted by impressions
   when the same query and URL appear on several rows (by date or device).
3. **Severity.**
   - **ALTA** (high): the second URL has at least `--share` of the
     impressions (default 20%) and the first two URLs are less than 10
     positions apart.
   - **MÉDIA** (medium): only one of those two conditions holds.
   - **BAIXA** (low): neither holds.
   These thresholds are adjustable defaults chosen for review, not an
   official Google number.
4. **Pairs of URLs.** Which pairs of pages share the most queries, how many
   of those are high severity and the impressions involved.
5. **Brand exclusion.** `--brand "term1,term2"` drops queries containing
   those terms, since brand queries often show several URLs on purpose.

Column names are recognized in English and Portuguese ("Consultas
principais", "Página", "Cliques", "Impressões", "CTR", "Posição"), with
`,` or `;` as separator and comma or dot as decimal mark. In the BigQuery
bulk export (columns `url` and `sum_top_position`), position is computed
as `sum_top_position / impressions + 1`. The CTR column is ignored and
recalculated from clicks and impressions.

## Requirements

Python 3.9 or newer. Standard library only, no external dependencies.

## Installation

```bash
git clone https://github.com/LucasFerrazSEO/gsc-cannibalization-finder.git
cd gsc-cannibalization-finder
```

## Usage

**1. Export query and page together** from the Search Console API, Looker
Studio or BigQuery, as CSV. The file needs a query column, a page column,
impressions and position (clicks are optional).

**2. Run the tool.**

```bash
python gsc_cannibalization_finder.py examples/gsc-export-example.csv --brand "example"
```

**3. Read the report.** Real output from the example file in `examples/`,
which uses `example.com` and made-up numbers (fictitious data). The tool
prints its report in Brazilian Portuguese.

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

The numbers are displayed in Brazilian format (dot for thousands, comma for
decimals).

**4. Adjust the thresholds** for your site size.

```bash
python gsc_cannibalization_finder.py export.csv --min-impressions 50 --share 30 --top 50
```

**5. Save the result** for a spreadsheet or another script. `--csv` writes
one row per query and URL; `--json` writes queries and pairs. Use `-` to
print to the screen.

```bash
python gsc_cannibalization_finder.py export.csv --csv queries.csv --json report.json
```

**6. Use it in CI or a scheduled job.** With `--strict`, the exit code is 1
when there is at least one high-severity query.

```bash
python gsc_cannibalization_finder.py export.csv --strict
```

## FAQ

**Can I use the default export from the Search Console interface?**
Not on its own. The interface export puts queries and pages in separate
tabs, without the query and page pairing. Use the Search Console API,
Looker Studio or the BigQuery bulk export, which can return both
dimensions on the same row.

**Does a high-severity query mean I must merge or redirect pages?**
No. It means the query deserves a look. Two URLs on the same results page
can be a good result, and a service page and a blog post may serve
different intents behind the same words. The decision stays with a person
who knows the site.

**Why are the thresholds 10 impressions, 20% and 10 positions?**
They are defaults for review, not rules from Google. Ten impressions
filters out one-off appearances, 20% means the second URL is taking a
visible slice, and 10 positions is roughly one results page. Change them
with `--min-impressions` and `--share` to fit your data.

**Is the tool free and does it need an internet connection?**
It is free and open source under the MIT license. It only reads the local
file you pass to it; no data leaves your machine.

## Limitations

Search Console omits anonymized queries and rounds some figures, so the
result inherits those gaps. Average position is an aggregate and hides
variation by device, country and date. The tool does not read the pages,
so it cannot tell whether two URLs answer the same intent. Brand exclusion
is a simple substring match.

## Methodology

The tool comes from the cannibalization rule used at
[lucasferrazseo.com](https://lucasferrazseo.com) to keep the home page,
the service pages and the location pages from competing for the same
query, where each page has its own target term and the overlap is checked
in Search Console data. It is generalized here for public use, with no
site-specific rules.

## Contributing

Bug reports and suggestions are welcome through [GitHub Issues](https://github.com/LucasFerrazSEO/gsc-cannibalization-finder/issues).

## Author

[Lucas Ferraz](https://lucasferraz.com) is an SEO, website development and Generative Engine Optimization specialist and the founder of [Lucas Ferraz SEO](https://lucasferrazseo.com).

## License

MIT. See [LICENSE](LICENSE).
