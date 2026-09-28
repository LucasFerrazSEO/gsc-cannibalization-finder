#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gsc-cannibalization-finder: aponta consultas do Google Search Console em que
duas ou mais URLs do mesmo site dividem impressões, para revisão humana.

O QUE FAZ
    Lê um CSV com as dimensões consulta + página (export da API do Search
    Console, do Looker Studio, do BigQuery ou planilha montada a partir da
    interface) e, para cada consulta com 2 ou mais URLs acima de
    --min-impressions (padrão 10) cada, calcula:

    - número de URLs que aparecem para a consulta;
    - divisão de impressões e de cliques entre elas (%);
    - posição média de cada URL (média ponderada por impressões quando a
      mesma consulta + URL aparece em várias linhas, por data ou dispositivo);
    - severidade:
        ALTA  quando a segunda URL tem >= --share (padrão 20%) das impressões
              da consulta E a diferença de posição entre as duas primeiras
              é menor que 10;
        MÉDIA quando só uma das duas condições acima vale;
        BAIXA quando nenhuma vale.

    Também agrupa por par de URLs: quais pares de páginas dividem mais
    consultas, com a soma de impressões envolvidas.

MÉTODO
    Colunas reconhecidas em inglês e em português ("Consultas principais",
    "Página", "Cliques", "Impressões", "CTR", "Posição"), separador , ou ;
    detectado sozinho, decimal com vírgula ou ponto. No export em massa do
    BigQuery (colunas url e sum_top_position), a posição é calculada como
    sum_top_position / impressões + 1. O CTR do arquivo é ignorado e
    recalculado a partir de cliques e impressões. Limiares são padrões
    ajustáveis, não números oficiais do Google.

USO
    python gsc_cannibalization_finder.py export.csv
    python gsc_cannibalization_finder.py export.csv --min-impressions 50 --share 30
    python gsc_cannibalization_finder.py export.csv --brand "minha marca,marca"
    python gsc_cannibalization_finder.py export.csv --csv saida.csv --json saida.json
    python gsc_cannibalization_finder.py export.csv --strict   # código de saída 1 se houver ALTA

LIMITAÇÕES
    Dividir uma consulta nem sempre é problema: duas URLs do mesmo domínio na
    mesma SERP podem ser um bom resultado. A ferramenta aponta candidatos para
    revisão humana, não decide o que fazer. O Search Console omite consultas
    anonimizadas e arredonda dados; o resultado herda essas lacunas. O export
    padrão da interface do Search Console separa consultas e páginas em abas
    diferentes, sem o cruzamento consulta + página, e por isso não serve
    sozinho.

Autor: Lucas Ferraz (lucasferraz.com), dependência zero, só biblioteca padrão.
Licença: MIT.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import unicodedata
from collections import defaultdict
from itertools import combinations


def _chave(nome: str) -> str:
    """Normaliza nome de coluna: minúsculas, sem acento, sem pontuação."""
    nome = unicodedata.normalize("NFKD", nome.strip().lstrip("﻿"))
    nome = "".join(c for c in nome if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", nome).strip()


ALIASES = {
    "query": {"query", "queries", "top queries", "search query", "consulta",
              "consultas", "consultas principais", "consulta de pesquisa"},
    "page": {"page", "pages", "top pages", "url", "landing page", "pagina",
             "paginas", "paginas principais", "pagina de destino"},
    "clicks": {"clicks", "url clicks", "cliques", "cliques no url"},
    "impressions": {"impressions", "impressoes"},
    "position": {"position", "average position", "avg position", "posicao",
                 "posicao media"},
    "sum_top_position": {"sum top position"},
}


def mapeia_colunas(cabecalho: list[str]) -> dict[str, int]:
    mapa: dict[str, int] = {}
    for i, nome in enumerate(cabecalho):
        k = _chave(nome)
        for campo, nomes in ALIASES.items():
            if k in nomes and campo not in mapa:
                mapa[campo] = i
    return mapa


def para_numero(valor: str, decimal: str = "auto") -> float:
    """Converte '1.234', '1,234', '11,3', '5,6%' ou '3.0' em float."""
    s = (valor or "").strip().replace("%", "").replace(" ", "").replace(" ", "")
    if not s or s in {"-", "--"}:
        return 0.0
    if decimal == "comma":
        s = s.replace(".", "").replace(",", ".")
    elif decimal == "dot":
        s = s.replace(",", "")
    elif "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def le_csv(caminho: str) -> tuple[list[str], list[list[str]]]:
    if caminho == "-":
        texto = sys.stdin.read()
    else:
        with open(caminho, encoding="utf-8-sig", newline="") as fh:
            texto = fh.read()
    linhas = [l for l in texto.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not linhas:
        return [], []
    amostra = "\n".join(linhas[:5])
    sep = ";" if amostra.count(";") > amostra.count(",") else ","
    if "\t" in linhas[0] and linhas[0].count("\t") > linhas[0].count(sep):
        sep = "\t"
    leitor = list(csv.reader(io.StringIO("\n".join(linhas)), delimiter=sep))
    return leitor[0], leitor[1:]


def agrega(cabecalho, linhas, decimal, marcas):
    mapa = mapeia_colunas(cabecalho)
    faltam = [c for c in ("query", "page", "impressions") if c not in mapa]
    if "position" not in mapa and "sum_top_position" not in mapa:
        faltam.append("position")
    if faltam:
        raise ValueError(
            "coluna(s) obrigatória(s) não encontrada(s): " + ", ".join(faltam)
            + ". Cabeçalho lido: " + " | ".join(cabecalho)
            + ". O arquivo precisa das dimensões consulta + página juntas "
              "(API, Looker Studio ou BigQuery).")
    # (consulta, página) -> [cliques, impressões, soma posição*impressões]
    dados: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    marcas_excluidas = 0
    for row in linhas:
        if len(row) <= max(mapa.values()):
            continue
        q = row[mapa["query"]].strip()
        p = row[mapa["page"]].strip()
        if not q or not p:
            continue
        ql = q.lower()
        if marcas and any(m in ql for m in marcas):
            marcas_excluidas += 1
            continue
        impr = para_numero(row[mapa["impressions"]], decimal)
        cliques = para_numero(row[mapa["clicks"]], decimal) if "clicks" in mapa else 0.0
        if "sum_top_position" in mapa:
            soma_pos = para_numero(row[mapa["sum_top_position"]], decimal) + impr
        else:
            soma_pos = para_numero(row[mapa["position"]], decimal) * impr
        d = dados[(q, p)]
        d[0] += cliques
        d[1] += impr
        d[2] += soma_pos
    return dados, marcas_excluidas


def analisa(dados, min_impr, share_min):
    por_consulta: dict[str, list[dict]] = defaultdict(list)
    for (q, p), (cl, im, sp) in dados.items():
        por_consulta[q].append({"page": p, "clicks": cl, "impressions": im,
                                "position": (sp / im) if im else 0.0})
    achados = []
    pares: dict[tuple[str, str], dict] = {}
    for q, urls in por_consulta.items():
        validas = [u for u in urls if u["impressions"] >= min_impr]
        if len(validas) < 2:
            continue
        validas.sort(key=lambda u: (-u["impressions"], u["position"]))
        tot_i = sum(u["impressions"] for u in validas)
        tot_c = sum(u["clicks"] for u in validas)
        for u in validas:
            u["impressions_pct"] = round(100 * u["impressions"] / tot_i, 1) if tot_i else 0.0
            u["clicks_pct"] = round(100 * u["clicks"] / tot_c, 1) if tot_c else 0.0
            u["position"] = round(u["position"], 1)
        segunda = validas[1]["impressions_pct"]
        gap = abs(validas[0]["position"] - validas[1]["position"])
        cond_share = segunda >= share_min
        cond_pos = gap < 10
        sev = "ALTA" if (cond_share and cond_pos) else ("MÉDIA" if (cond_share or cond_pos) else "BAIXA")
        achados.append({"query": q, "severity": sev, "urls_count": len(validas),
                        "impressions": tot_i, "clicks": tot_c,
                        "second_url_share_pct": segunda,
                        "position_gap": round(gap, 1), "urls": validas})
        for a, b in combinations(sorted(u["page"] for u in validas), 2):
            par = pares.setdefault((a, b), {"page_a": a, "page_b": b, "queries": 0,
                                            "high": 0, "impressions": 0.0, "examples": []})
            par["queries"] += 1
            par["high"] += sev == "ALTA"
            par["impressions"] += sum(u["impressions"] for u in validas if u["page"] in (a, b))
            if len(par["examples"]) < 3:
                par["examples"].append(q)
    ordem = {"ALTA": 0, "MÉDIA": 1, "BAIXA": 2}
    achados.sort(key=lambda a: (ordem[a["severity"]], -a["impressions"]))
    lista_pares = sorted(pares.values(), key=lambda p: (-p["queries"], -p["high"], -p["impressions"]))
    return achados, lista_pares


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def _dec(n: float, largura: int = 0) -> str:
    """Número com uma casa decimal e vírgula, no padrão pt-BR."""
    return f"{n:{largura}.1f}".replace(".", ",")


def escreve_csv(destino: str, achados) -> None:
    fh = sys.stdout if destino == "-" else open(destino, "w", encoding="utf-8", newline="")
    try:
        w = csv.writer(fh)
        w.writerow(["query", "severity", "urls_count", "second_url_share_pct", "position_gap",
                    "page", "clicks", "impressions", "impressions_pct", "clicks_pct", "position"])
        for a in achados:
            for u in a["urls"]:
                w.writerow([a["query"], a["severity"], a["urls_count"], a["second_url_share_pct"],
                            a["position_gap"], u["page"], int(u["clicks"]), int(u["impressions"]),
                            u["impressions_pct"], u["clicks_pct"], u["position"]])
    finally:
        if fh is not sys.stdout:
            fh.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Aponta consultas do Search Console divididas entre 2+ URLs do mesmo site.")
    ap.add_argument("arquivo", help="CSV com consulta + página (ou '-' para entrada padrão)")
    ap.add_argument("--min-impressions", type=float, default=10,
                    help="impressões mínimas de cada URL para contar na consulta (padrão 10)")
    ap.add_argument("--share", type=float, default=20,
                    help="%% mínimo de impressões da segunda URL para severidade ALTA (padrão 20)")
    ap.add_argument("--brand", default="",
                    help="termos de marca separados por vírgula; consultas que os contêm são excluídas")
    ap.add_argument("--top", type=int, default=20, help="quantas consultas e pares mostrar (padrão 20)")
    ap.add_argument("--decimal", choices=["auto", "comma", "dot"], default="auto",
                    help="separador decimal dos números (padrão: detecção automática)")
    ap.add_argument("--csv", metavar="ARQUIVO", help="grava uma linha por consulta + URL ('-' para a tela)")
    ap.add_argument("--json", metavar="ARQUIVO", help="grava consultas e pares em JSON ('-' para a tela)")
    ap.add_argument("--strict", action="store_true",
                    help="código de saída 1 se houver qualquer consulta ALTA (padrão: só relata)")
    args = ap.parse_args()
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    try:
        cabecalho, linhas = le_csv(args.arquivo)
    except OSError as exc:
        print(f"Não consegui ler {args.arquivo}: {exc}", file=sys.stderr)
        sys.exit(2)
    if not cabecalho:
        print("Arquivo vazio.", file=sys.stderr)
        sys.exit(2)

    marcas = [m.strip().lower() for m in args.brand.split(",") if m.strip()]
    try:
        dados, excluidas = agrega(cabecalho, linhas, args.decimal, marcas)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(2)

    achados, pares = analisa(dados, args.min_impressions, args.share)
    cont = {s: sum(a["severity"] == s for a in achados) for s in ("ALTA", "MÉDIA", "BAIXA")}
    consultas = len({q for q, _ in dados})

    if args.csv:
        escreve_csv(args.csv, achados)
    if args.json:
        saida = json.dumps({"queries": achados, "pairs": pares}, ensure_ascii=False, indent=2)
        if args.json == "-":
            print(saida)
        else:
            with open(args.json, "w", encoding="utf-8") as fh:
                fh.write(saida)
    if "-" in (args.csv, args.json):
        sys.exit(1 if (args.strict and cont["ALTA"]) else 0)

    print(f"\n=== gsc-cannibalization-finder: {args.arquivo} ===")
    print(f"{len(linhas)} linha(s) lida(s), {consultas} consulta(s) distinta(s)"
          + (f", {excluidas} linha(s) de marca excluída(s)" if marcas else ""))
    print(f"Critério: 2+ URLs com >= {args.min_impressions:g} impressões cada | "
          f"ALTA = 2ª URL >= {args.share:g}% das impressões e diferença de posição < 10")
    print(f"{len(achados)} consulta(s) dividida(s) | ALTA {cont['ALTA']} | "
          f"MÉDIA {cont['MÉDIA']} | BAIXA {cont['BAIXA']} | {len(pares)} par(es) de URLs\n")

    if not achados:
        print("  Nenhuma consulta dividida entre URLs com esses limiares.")
    for a in achados[:args.top]:
        print(f"  {a['severity']:<5}  \"{a['query']}\"  {a['urls_count']} URLs, "
              f"{_fmt(a['impressions'])} impr., 2ª URL com {_dec(a['second_url_share_pct'])}%, "
              f"dif. posição {_dec(a['position_gap'])}")
        for u in a["urls"]:
            print(f"           {_dec(u['impressions_pct'], 5)}% impr. {_dec(u['clicks_pct'], 5)}% cliques  "
                  f"pos. {_dec(u['position'], 5)}  {u['page']}")
    if len(achados) > args.top:
        print(f"  ... mais {len(achados) - args.top} consulta(s) (use --top ou --csv)")

    if pares:
        print("\n-- PARES DE URLs QUE MAIS DIVIDEM CONSULTAS --")
        for p in pares[:args.top]:
            print(f"  {p['queries']} consulta(s), {p['high']} ALTA, {_fmt(p['impressions'])} impr.")
            print(f"      {p['page_a']}\n      {p['page_b']}")
            print("      ex.: " + "; ".join(p["examples"]))

    print("\n(Consulta dividida nem sempre é problema: duas URLs do mesmo site na SERP "
          "podem ser bom sinal. Revisão humana decide.)")
    sys.exit(1 if (args.strict and cont["ALTA"]) else 0)


if __name__ == "__main__":
    main()
