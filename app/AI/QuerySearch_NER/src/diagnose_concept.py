"""
diagnose_concept.py — READ-ONLY diagnosis of how specific concepts are
represented in the training data. Changes nothing.

Answers, per concept:
  1. how many training examples contain it
  2. which query categories it appears in
  3. what words occur around it (esp. symptom-adjacent contexts)
  4. whether its annotation is consistently the expected label
  5. any competing/confusing patterns (same surface used with another label)

Also prints a small comparison against reference diseases that the model gets
right, to see if representation differs.

Usage:
    python -m src.diagnose_concept --train data/training_v1/train.json \
        --concepts hypertension pneumonia --reference asthma diabetes mellitus stroke
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def analyze(records: list[dict], concept: str) -> dict:
    c = concept.lower()
    matches = []
    for r in records:
        for e in r["entities"]:
            if e["text"].lower() == c:
                matches.append(r)
                break
    cats = Counter(r["category"] for r in matches)
    labels = Counter(
        e["label"] for r in matches for e in r["entities"] if e["text"].lower() == c
    )
    # co-occurring entity labels in the same query (adjacency)
    co_labels = Counter()
    for r in matches:
        for e in r["entities"]:
            if e["text"].lower() != c:
                co_labels[e["label"]] += 1
    # surrounding words (whole query text, minus the concept)
    context_words = Counter()
    for r in matches:
        for w in r["query"].lower().replace(c, " ").split():
            context_words[w] += 1
    return {
        "count": len(matches),
        "categories": dict(cats),
        "labels_assigned": dict(labels),
        "cooccurring_entity_labels": dict(co_labels),
        "top_context_words": context_words.most_common(12),
        "sample_queries": [r["query"] for r in matches[:8]],
    }


def competing_surface(records: list[dict], concept: str) -> dict:
    """Check if the same surface string is EVER labeled something else, or if a
    substring/superstring relationship could confuse the model."""
    c = concept.lower()
    other_labels = Counter()
    for r in records:
        for e in r["entities"]:
            t = e["text"].lower()
            if t == c and e["label"]:
                pass
            if c in t and t != c:
                other_labels[(t, e["label"])] += 1
    return {"superstrings_containing_concept": dict(other_labels)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only training representation diagnosis.")
    parser.add_argument("--train", type=Path, default=Path("data/training_v1/train.json"))
    parser.add_argument("--concepts", nargs="+", default=["hypertension", "pneumonia"])
    parser.add_argument("--reference", nargs="+", default=["asthma", "stroke", "breast cancer"])
    args = parser.parse_args()

    records = load(args.train)
    print(f"Training file: {args.train}  ({len(records)} records)\n")

    print("================ TARGET CONCEPTS ================")
    for concept in args.concepts:
        a = analyze(records, concept)
        comp = competing_surface(records, concept)
        print(f"\n### {concept!r}")
        print(f"  count in train: {a['count']}")
        print(f"  categories: {a['categories']}")
        print(f"  label assigned to it: {a['labels_assigned']}")
        print(f"  co-occurring entity labels: {a['cooccurring_entity_labels']}")
        print(f"  top context words: {a['top_context_words']}")
        print(f"  competing superstrings: {comp['superstrings_containing_concept']}")
        print("  sample queries:")
        for q in a["sample_queries"]:
            print(f"    - {q}")

    print("\n================ REFERENCE DISEASES (model gets right) ================")
    for concept in args.reference:
        a = analyze(records, concept)
        print(f"\n### {concept!r}")
        print(f"  count in train: {a['count']}")
        print(f"  categories: {a['categories']}")
        print(f"  label assigned: {a['labels_assigned']}")
        print(f"  co-occurring entity labels: {a['cooccurring_entity_labels']}")


if __name__ == "__main__":
    main()
