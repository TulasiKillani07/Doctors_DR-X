"""
split_data.py — split annotated JSONL into train / dev / test sets.

Stage 3 of the pipeline. Takes a single annotations JSONL file and splits it
into train / dev / test JSONL files under data/splits/.

Usage:
    python -m src.split_data \
        --input data/annotations/queries.jsonl \
        --outdir data/splits \
        --train 0.7 --dev 0.15 --test 0.15 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Split annotations into train/dev/test.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--train", type=float, default=0.7)
    parser.add_argument("--dev", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    total = args.train + args.dev + args.test
    if abs(total - 1.0) > 1e-6:
        raise SystemExit(f"train+dev+test must sum to 1.0 (got {total})")

    records = read_jsonl(args.input)
    random.Random(args.seed).shuffle(records)

    n = len(records)
    n_train = int(n * args.train)
    n_dev = int(n * args.dev)

    train = records[:n_train]
    dev = records[n_train:n_train + n_dev]
    test = records[n_train + n_dev:]

    write_jsonl(args.outdir / "train.jsonl", train)
    write_jsonl(args.outdir / "dev.jsonl", dev)
    write_jsonl(args.outdir / "test.jsonl", test)

    print(f"Total: {n}  ->  train: {len(train)}, dev: {len(dev)}, test: {len(test)}")


if __name__ == "__main__":
    main()
