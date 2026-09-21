"""
data_prep.py — collect and normalize raw medical queries.

Stage 1 of the pipeline. Reads raw query text (one query per line) from
data/raw/, cleans/normalizes it, and writes a de-duplicated list ready to be
annotated.

This does NOT annotate. It only prepares clean query text.

Usage:
    python -m src.data_prep --input data/raw/queries.txt --output data/raw/queries_clean.txt
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def normalize_query(text: str) -> str:
    """Light normalization: trim, collapse internal whitespace."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def load_queries(input_path: Path) -> list[str]:
    """Load raw queries, one per line, skipping blanks."""
    lines = input_path.read_text(encoding="utf-8").splitlines()
    return [ln for ln in (normalize_query(x) for x in lines) if ln]


def dedupe(queries: list[str]) -> list[str]:
    """Remove exact duplicates while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare raw medical queries.")
    parser.add_argument("--input", required=True, type=Path, help="Raw queries file (one per line).")
    parser.add_argument("--output", required=True, type=Path, help="Where to write cleaned queries.")
    args = parser.parse_args()

    queries = dedupe(load_queries(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(queries) + "\n", encoding="utf-8")
    print(f"Wrote {len(queries)} cleaned, de-duplicated queries -> {args.output}")


if __name__ == "__main__":
    main()
