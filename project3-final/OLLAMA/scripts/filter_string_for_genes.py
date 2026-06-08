#!/usr/bin/env python3
"""Filtra arquivos STRING para os genes presentes em gold_geo_nodes.csv.

Uso (na raiz do repositório):
  python ollama/scripts/filter_string_for_genes.py
  python ollama/scripts/filter_string_for_genes.py --genes data/gold/gold_geo_nodes.csv
"""

from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path

OLLAMA_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = OLLAMA_DIR.parent
DEFAULT_STRING_DIR = OLLAMA_DIR / "knowledge" / "string"


def load_gene_symbols(genes_csv: Path) -> tuple[set[str], set[str]]:
    symbols: set[str] = set()
    geneids: set[str] = set()
    with genes_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            symbol = row.get("symbol", "").strip()
            geneid = row.get("geneid", "").strip()
            if symbol:
                symbols.add(symbol)
            if geneid:
                geneids.add(geneid)
    return symbols, geneids


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def filter_protein_info(
    input_path: Path,
    output_path: Path,
    symbols: set[str],
) -> tuple[set[str], set[str], list[str]]:
    """Retorna (string_ids encontrados, símbolos encontrados, símbolos ausentes)."""
    string_ids: set[str] = set()
    found_symbols: set[str] = set()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open_text(input_path) as src, output_path.open("w", encoding="utf-8") as dst:
        header = src.readline()
        if not header.startswith("#"):
            raise ValueError(f"Cabeçalho inesperado em {input_path}")
        dst.write(header)

        for line in src:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.split("\t", 3)
            if len(cols) < 2:
                continue
            string_id, preferred_name = cols[0], cols[1]
            if preferred_name not in symbols:
                continue
            dst.write(line)
            string_ids.add(string_id)
            found_symbols.add(preferred_name)

    missing_symbols = sorted(symbols - found_symbols)
    return string_ids, found_symbols, missing_symbols


def filter_enrichment_terms(
    input_path: Path,
    output_path: Path,
    string_ids: set[str],
) -> int:
    rows = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open_text(input_path) as src, output_path.open("w", encoding="utf-8") as dst:
        header = src.readline()
        if not header.startswith("#"):
            raise ValueError(f"Cabeçalho inesperado em {input_path}")
        dst.write(header)

        for line in src:
            if line.startswith("#") or not line.strip():
                continue
            string_id = line.split("\t", 1)[0]
            if string_id not in string_ids:
                continue
            dst.write(line)
            rows += 1
    return rows


def resolve_input(base_dir: Path, stem: str) -> Path:
    for name in (f"{stem}.txt.gz", f"{stem}.txt"):
        path = base_dir / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"Arquivo não encontrado: {base_dir}/{stem}.txt[.gz]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Filtra arquivos STRING para genes gold")
    parser.add_argument(
        "--genes",
        type=Path,
        default=Path("data/gold/gold_geo_nodes.csv"),
        help="CSV com colunas symbol e geneid (relativo à raiz do repo)",
    )
    parser.add_argument(
        "--string-dir",
        type=Path,
        default=DEFAULT_STRING_DIR,
        help="Pasta com arquivos STRING",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="gold_genes",
        help="Sufixo dos arquivos de saída",
    )
    args = parser.parse_args()

    genes_csv = args.genes if args.genes.is_absolute() else (REPO_ROOT / args.genes).resolve()
    string_dir = args.string_dir if args.string_dir.is_absolute() else (REPO_ROOT / args.string_dir).resolve()

    symbols, geneids = load_gene_symbols(genes_csv)
    print(f"[+] Genes de interesse: {len(geneids)} geneids, {len(symbols)} símbolos únicos")

    info_in = resolve_input(string_dir, "9606.protein.info.v12.0")
    enrich_in = resolve_input(string_dir, "9606.protein.enrichment.terms.v12.0")

    info_out = string_dir / f"9606.protein.info.v12.0.{args.suffix}.txt"
    enrich_out = string_dir / f"9606.protein.enrichment.terms.v12.0.{args.suffix}.txt"

    print(f"[+] Filtrando {info_in.name} -> {info_out.name}")
    string_ids, found_symbols, missing = filter_protein_info(info_in, info_out, symbols)

    print(f"[+] Filtrando {enrich_in.name} -> {enrich_out.name}")
    enrich_rows = filter_enrichment_terms(enrich_in, enrich_out, string_ids)

    print()
    print(f"  Símbolos encontrados no STRING: {len(found_symbols)}/{len(symbols)}")
    print(f"  IDs STRING mapeados:            {len(string_ids)}")
    print(f"  Linhas enrichment filtradas:    {enrich_rows:,}")
    print(f"  protein.info filtrado:          {info_out}")
    print(f"  enrichment filtrado:            {enrich_out}")

    if missing:
        missing_path = string_dir / f"string_symbols_missing_{args.suffix}.txt"
        missing_path.write_text("\n".join(missing) + "\n", encoding="utf-8")
        print(f"  Símbolos ausentes no STRING:    {len(missing)} -> {missing_path.name}")
        for symbol in missing[:15]:
            print(f"    - {symbol}")
        if len(missing) > 15:
            print(f"    ... e mais {len(missing) - 15}")


if __name__ == "__main__":
    main()
