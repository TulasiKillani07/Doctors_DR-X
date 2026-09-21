"""
convert_v2.py — Convert V2 train/dev JSON datasets into spaCy DocBin binaries.

Reads:
  data/training_v2/train.json
  data/training_v2/dev.json

Produces:
  data/processed_v2/train.spacy
  data/processed_v2/dev.spacy

Ensures strict token alignment for every entity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import spacy
from spacy.tokens import DocBin

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.labels import ENTITY_LABELS, is_valid_label


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def records_to_docbin(nlp, records: list[dict]) -> tuple[DocBin, list[str]]:
    doc_bin = DocBin()
    errors: list[str] = []

    for rec in records:
        text = rec.get("query", "")
        doc = nlp.make_doc(text)
        spans = []
        for ent in rec.get("entities", []):
            label = ent["label"]
            start, end = ent["start"], ent["end"]
            if not is_valid_label(label):
                errors.append(f"unknown label {label!r} in {text!r}")
                continue
            if text[start:end] != ent["text"]:
                errors.append(f"offset mismatch in {text!r}: expected {ent['text']!r}, found {text[start:end]!r}")
                continue
            span = doc.char_span(start, end, label=label, alignment_mode="strict")
            if span is None:
                span = doc.char_span(start, end, label=label, alignment_mode="expand")
                if span is None:
                    errors.append(f"unalignable span [{start},{end}] in {text!r}")
                    continue
                errors.append(f"strict-misaligned (used expand) [{start},{end}]='{ent['text']}' in {text!r}")
            spans.append(span)
        doc.ents = spans
        doc_bin.add(doc)

    return doc_bin, errors


def main():
    parser = argparse.ArgumentParser(description="Convert V2 JSON datasets to spaCy DocBin.")
    parser.add_argument("--train", type=Path, default=PROJECT_ROOT / "data/training_v2/train.json")
    parser.add_argument("--dev", type=Path, default=PROJECT_ROOT / "data/training_v2/dev.json")
    parser.add_argument("--outdir", type=Path, default=PROJECT_ROOT / "data/processed_v2")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    nlp = spacy.blank("en")

    train_records = load_json(args.train)
    dev_records = load_json(args.dev)

    for name, recs in [("train", train_records), ("dev", dev_records)]:
        db, errors = records_to_docbin(nlp, recs)
        out_file = args.outdir / f"{name}.spacy"
        db.to_disk(out_file)
        print(f"Processed {name}: {len(recs)} docs -> {out_file} ({len(errors)} span alignment issues)")
        if errors:
            for err in errors[:10]:
                print(f"  [!] {err}")

    print(f"\n[OK] DocBin compilation completed successfully to {args.outdir}")


if __name__ == "__main__":
    main()
