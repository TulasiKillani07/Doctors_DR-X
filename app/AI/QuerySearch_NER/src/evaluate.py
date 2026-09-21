"""
evaluate.py — evaluate the trained NER model with Precision / Recall / F1.

Scores the held-out test set (data/training/test.json) three ways:
  1. OVERALL (all test queries)  — overall + per-label P/R/F1
  2. SEEN CONCEPTS / NEW PHRASING slice (category == test_seen_concept_new_phrasing)
  3. UNSEEN CONCEPTS slice          (category == test_unseen_concept)

The seen-vs-unseen comparison shows whether the model learned entity boundaries
and semantic patterns (generalizes to new phrasings AND new concepts) rather
than merely memorizing the training terminology bank.

Reads test.json directly (keeping per-record category), builds gold/pred
Examples, and uses spaCy's Scorer for span-level NER metrics.

Usage:
    python -m src.evaluate --model models/model-best --test data/training/test.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import spacy
from spacy.tokens import DocBin  # noqa: F401  (kept for compatibility)
from spacy.training import Example
from spacy.scorer import Scorer

SEEN = "test_seen_concept_new_phrasing"
UNSEEN = "test_unseen_concept"


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_examples(nlp, records: list[dict]) -> list[Example]:
    examples = []
    for rec in records:
        text = rec.get("query", rec.get("text", ""))
        gold = nlp.make_doc(text)
        spans = []
        for e in rec.get("entities", []):
            span = gold.char_span(e["start"], e["end"], label=e["label"], alignment_mode="expand")
            if span is not None:
                spans.append(span)
        gold.ents = spans
        pred = nlp(text)
        examples.append(Example(pred, gold))
    return examples


def score(nlp, records: list[dict]) -> dict:
    examples = build_examples(nlp, records)
    scorer = Scorer()
    return scorer.score(examples)


def print_block(title: str, n: int, scores: dict) -> None:
    print(f"\n=== {title}  (n={n}) ===")
    p, r, f = scores.get("ents_p"), scores.get("ents_r"), scores.get("ents_f")
    def fmt(x): return f"{x:.3f}" if isinstance(x, (int, float)) else "n/a"
    print(f"  {'':<12} {'P':>7} {'R':>7} {'F1':>7}")
    print(f"  {'OVERALL':<12} {fmt(p):>7} {fmt(r):>7} {fmt(f):>7}")
    per_type = scores.get("ents_per_type") or {}
    for label in ("DISEASE", "SYMPTOM", "CONDITION"):
        s = per_type.get(label)
        if s:
            print(f"  {label:<12} {s['p']:>7.3f} {s['r']:>7.3f} {s['f']:>7.3f}")
        else:
            print(f"  {label:<12} {'--':>7} {'--':>7} {'--':>7}  (no gold entities in slice)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate NER model with slice-wise P/R/F1.")
    parser.add_argument("--model", type=Path, default=Path("models/model-best"))
    parser.add_argument("--test", type=Path, default=Path("data/training/test.json"))
    args = parser.parse_args()

    nlp = spacy.load(args.model)
    records = load_json(args.test)

    seen = [r for r in records if r.get("category") == SEEN]
    unseen = [r for r in records if r.get("category") == UNSEEN]

    print(f"Model: {args.model}")
    print(f"Test records: {len(records)}  (seen={len(seen)}, unseen={len(unseen)})")

    print_block("OVERALL", len(records), score(nlp, records))
    print_block("SEEN CONCEPTS / NEW PHRASING", len(seen), score(nlp, seen))
    print_block("UNSEEN CONCEPTS", len(unseen), score(nlp, unseen))

    print("\nNote: the SEEN slice tests language generalization on known concepts;")
    print("the UNSEEN slice tests whether the model generalizes to concepts never")
    print("seen in training (the stronger test of learned patterns vs memorization).")


if __name__ == "__main__":
    main()
