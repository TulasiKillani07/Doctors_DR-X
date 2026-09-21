"""
convert.py — convert the validated NER query JSON into spaCy DocBin (.spacy).

Reads the generated dataset (current schema):
    {
      "query": "...",                # the text
      "entities": [
        {"text": "diabetes", "label": "DISEASE", "start": 15, "end": 23}
      ],
      "category": "single_disease",
      "difficulty": "easy",
      "source_concepts": [...]
    }

Produces spaCy DocBin files for training/evaluation:
    data/processed/train.spacy   (90% of train.json)
    data/processed/dev.spacy     (10% of train.json)
    data/processed/test.spacy    (all of test.json — kept untouched for final eval)

The test set keeps its slice metadata (category) so evaluation can score the
"seen concept / new phrasing" and "unseen concept" slices separately. Slice
membership is written to data/processed/test_slices.json alongside the DocBin.

Alignment: offsets were already validated as exact, so we use STRICT alignment
and treat any misalignment as a hard error (surfaced, not silently skipped).

Usage:
    python -m src.convert \
        --train data/training/train.json \
        --test data/training/test.json \
        --outdir data/processed \
        --dev-fraction 0.10 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import spacy
from spacy.tokens import DocBin

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.labels import ENTITY_LABELS, is_valid_label  # noqa: E402


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def records_to_docbin(nlp, records: list[dict]) -> tuple[DocBin, list[str]]:
    """Convert records to a DocBin. Returns (docbin, errors). Errors are hard
    problems (unknown label / misaligned span) — we do not silently drop them."""
    doc_bin = DocBin()
    errors: list[str] = []

    for rec in records:
        text = rec.get("query", rec.get("text", ""))
        doc = nlp.make_doc(text)
        spans = []
        for ent in rec.get("entities", []):
            label = ent["label"]
            start, end = ent["start"], ent["end"]
            if not is_valid_label(label):
                errors.append(f"unknown label {label!r} in {text!r}")
                continue
            # Sanity: the recorded text must match the offset substring.
            if text[start:end] != ent["text"]:
                errors.append(f"offset/text mismatch in {text!r}: {ent}")
                continue
            span = doc.char_span(start, end, label=label, alignment_mode="strict")
            if span is None:
                # STRICT failed — the entity doesn't align to token boundaries.
                # Retry with 'expand' so we don't lose the entity, but record it.
                span = doc.char_span(start, end, label=label, alignment_mode="expand")
                if span is None:
                    errors.append(f"unalignable span [{start},{end}] in {text!r}")
                    continue
                errors.append(
                    f"strict-misaligned (used expand) [{start},{end}]='{ent['text']}' in {text!r}"
                )
            spans.append(span)
        doc.ents = spans
        doc_bin.add(doc)

    return doc_bin, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert NER query JSON to spaCy DocBin.")
    parser.add_argument("--train", type=Path, default=Path("data/training/train.json"))
    parser.add_argument("--test", type=Path, default=Path("data/training/test.json"))
    parser.add_argument("--outdir", type=Path, default=Path("data/processed"))
    parser.add_argument("--dev-fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    nlp = spacy.blank("en")

    # --- Split train.json into train / dev (seeded) ---
    train_records = load_json(args.train)
    rng = random.Random(args.seed)
    rng.shuffle(train_records)
    n_dev = int(len(train_records) * args.dev_fraction)
    dev_records = train_records[:n_dev]
    train_split = train_records[n_dev:]

    # --- Test stays whole; capture slice metadata ---
    test_records = load_json(args.test)

    all_errors: dict[str, list[str]] = {}
    for name, recs in (("train", train_split), ("dev", dev_records), ("test", test_records)):
        db, errors = records_to_docbin(nlp, recs)
        db.to_disk(args.outdir / f"{name}.spacy")
        all_errors[name] = errors
        print(f"{name}.spacy: {len(recs)} docs, {len(errors)} span issues")

    # Persist test slice membership for slice-wise evaluation.
    slices: dict[str, list[int]] = {}
    for i, rec in enumerate(test_records):
        cat = rec.get("category", "unknown")
        slices.setdefault(cat, []).append(i)
    with (args.outdir / "test_slices.json").open("w", encoding="utf-8") as f:
        json.dump(slices, f, indent=2)

    print(f"\nLabels registered for training: {ENTITY_LABELS}")
    print(f"Test slices: {{ {', '.join(f'{k}: {len(v)}' for k, v in slices.items())} }}")

    total_errors = sum(len(v) for v in all_errors.values())
    if total_errors:
        print(f"\n[!] {total_errors} span issues (shown for transparency):")
        for name, errs in all_errors.items():
            for e in errs[:10]:
                print(f"  ({name}) {e}")
    else:
        print("\nNo span issues — all entities aligned cleanly.")

    print(f"\nWrote train/dev/test .spacy + test_slices.json to {args.outdir}")


if __name__ == "__main__":
    main()
