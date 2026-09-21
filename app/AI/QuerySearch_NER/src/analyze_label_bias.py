"""
analyze_label_bias.py — READ-ONLY analysis of why unseen concepts default to
SYMPTOM. Compares the DISEASE vs SYMPTOM (vs CONDITION) representation in the V1
training data along dimensions that could bias generalization:

  - number of distinct concepts per label and number of training entity spans
  - concept morphology: word count, single-word vs multi-word, avg length,
    common suffixes (-itis, -emia, -osis, -pathy, pain, ...)
  - the template/context words each label appears with (the trigger phrases)
  - overlap of context words between DISEASE and SYMPTOM (ambiguous triggers)

Changes nothing. Reads data/training_v1/train.json by default.

Usage:
    python -m src.analyze_label_bias --train data/training_v1/train.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

SUFFIXES = ["itis", "emia", "aemia", "osis", "pathy", "oma", "ia", "algia",
            "cancer", "pain", "failure", "syndrome", "disease", "infection",
            "deficiency", "disorder"]


def load(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def concept_stats(concepts: list[str]) -> dict:
    wc = Counter(len(c.split()) for c in concepts)
    single = sum(1 for c in concepts if len(c.split()) == 1)
    avg_len = round(sum(len(c) for c in concepts) / max(1, len(concepts)), 1)
    suffix_hits = Counter()
    for c in concepts:
        cl = c.lower()
        for s in SUFFIXES:
            if cl.endswith(s):
                suffix_hits[s] += 1
                break
    return {
        "distinct_concepts": len(concepts),
        "single_word": single,
        "multi_word": len(concepts) - single,
        "avg_char_len": avg_len,
        "word_count_hist": dict(sorted(wc.items())),
        "suffix_distribution": dict(suffix_hits.most_common()),
    }


def context_words(records, label) -> Counter:
    """Words appearing in queries that contain exactly one entity of `label`
    (isolates the trigger context)."""
    ctr = Counter()
    for r in records:
        labels = [e["label"] for e in r["entities"]]
        if labels.count(label) == 1 and len(set(labels)) == 1:
            concept = next(e["text"].lower() for e in r["entities"] if e["label"] == label)
            text = r["query"].lower().replace(concept, " ")
            for w in re.findall(r"[a-z]+", text):
                ctr[w] += 1
    return ctr


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only DISEASE vs SYMPTOM bias analysis.")
    parser.add_argument("--train", type=Path, default=Path("data/training_v1/train.json"))
    args = parser.parse_args()

    records = load(args.train)

    # Distinct concepts + span counts per label.
    concepts = {"DISEASE": set(), "SYMPTOM": set(), "CONDITION": set()}
    span_counts = Counter()
    for r in records:
        for e in r["entities"]:
            concepts[e["label"]].add(e["text"].lower())
            span_counts[e["label"]] += 1

    print(f"Training file: {args.train}  ({len(records)} records)\n")
    print("=== per-label counts ===")
    for lab in ("DISEASE", "SYMPTOM", "CONDITION"):
        print(f"  {lab}: {len(concepts[lab])} distinct concepts, {span_counts[lab]} entity spans")

    print("\n=== concept morphology ===")
    for lab in ("DISEASE", "SYMPTOM", "CONDITION"):
        s = concept_stats(sorted(concepts[lab]))
        print(f"\n  {lab}")
        for k, v in s.items():
            print(f"    {k}: {v}")

    # Context/trigger words per label + overlap.
    dis_ctx = context_words(records, "DISEASE")
    sym_ctx = context_words(records, "SYMPTOM")
    print("\n=== top DISEASE trigger context words (single-DISEASE queries) ===")
    print("  " + ", ".join(f"{w}:{n}" for w, n in dis_ctx.most_common(15)))
    print("\n=== top SYMPTOM trigger context words (single-SYMPTOM queries) ===")
    print("  " + ", ".join(f"{w}:{n}" for w, n in sym_ctx.most_common(15)))

    shared = set(dis_ctx) & set(sym_ctx)
    print(f"\n=== context words shared by BOTH DISEASE and SYMPTOM triggers ({len(shared)}) ===")
    # sort by combined frequency
    ranked = sorted(shared, key=lambda w: -(dis_ctx[w] + sym_ctx[w]))
    print("  " + ", ".join(f"{w}(D{dis_ctx[w]}/S{sym_ctx[w]})" for w in ranked[:20]))

    dis_only = set(dis_ctx) - set(sym_ctx)
    sym_only = set(sym_ctx) - set(dis_ctx)
    print(f"\n=== DISEASE-only trigger words ({len(dis_only)}) ===")
    print("  " + ", ".join(sorted(dis_only, key=lambda w: -dis_ctx[w])[:15]))
    print(f"\n=== SYMPTOM-only trigger words ({len(sym_only)}) ===")
    print("  " + ", ".join(sorted(sym_only, key=lambda w: -sym_ctx[w])[:15]))


if __name__ == "__main__":
    main()
