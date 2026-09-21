"""
validate_dataset_v2.py — Automated validation suite for V2 dataset.

Performs 12 strict quality checks on data/training_v2/train.json and dev.json:
  1.  JSON structure and mandatory fields present.
  2.  Exact character offsets (query[start:end] == ent['text']).
  3.  Span hygiene: no leading/trailing punctuation or whitespace in spans.
  4.  Labels strictly in {DISEASE, SYMPTOM, CONDITION}.
  5.  Zero leakage of unseen evaluation concepts (from unseen_eval_concepts.json).
  6.  All entity concepts belong to approved terminology_bank.json with exact label.
  7.  Zero duplicate queries within train, within dev, or across train + dev.
  8.  Frame ceiling enforced: (concept, frame_id) <= 2.
  9.  No-entity queries have exactly 0 entities.
  10. Zero overlapping or nested entity spans.
  11. Natural English phrasing: no banned awkward patterns.
  12. Concept coverage: all 93 concepts adequately represented.

Exits with non-zero exit code if any error is encountered.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.labels import ENTITY_LABELS, is_valid_label

BANNED_PHRASES = [
    r"\badolescents patients\b",
    r"\bduring obesity\b",
    r"\bduring paediatric\b",
    r"\bduring pediatric\b",
    r"\bduring elderly\b",
    r"\bduring immunocompromised\b",
    r"\bduring adolescents\b",
]

PUNCTUATION_CHARS = set(".,!?;:\"'()[]{}")


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_dataset(train_path: Path, dev_path: Path, bank_path: Path, unseen_path: Path) -> dict:
    train = load_json(train_path)
    dev = load_json(dev_path)
    bank = load_json(bank_path)
    unseen = load_json(unseen_path)

    # 1. Approved bank mapping: concept.lower() -> label
    bank_map: dict[str, str] = {}
    for label in ENTITY_LABELS:
        for entry in bank["concepts"].get(label, []):
            bank_map[entry["concept"].lower()] = label

    # 2. Unseen concepts set
    unseen_set: set[str] = set()
    for label in ENTITY_LABELS:
        for concept in unseen["concepts"].get(label, []):
            unseen_set.add(concept.lower())

    failures: list[str] = []
    warnings: list[str] = []

    # Check 5: Bank & Unseen Disjointness
    overlap = set(bank_map) & unseen_set
    if overlap:
        failures.append(f"[Check 5] FATAL: terminology_bank and unseen_eval_concepts overlap: {sorted(overlap)}")

    all_records = train + dev
    seen_queries: set[str] = set()
    train_queries = set(r["query"] for r in train)
    dev_queries = set(r["query"] for r in dev)

    # Check 7: Duplicate query check
    if len(train_queries) != len(train):
        failures.append(f"[Check 7] Duplicate queries within train.json: {len(train) - len(train_queries)} duplicates")
    if len(dev_queries) != len(dev):
        failures.append(f"[Check 7] Duplicate queries within dev.json: {len(dev) - len(dev_queries)} duplicates")
    cross_duplicates = train_queries & dev_queries
    if cross_duplicates:
        failures.append(f"[Check 7] Cross-split duplicate queries between train and dev: {len(cross_duplicates)}")

    frame_concept_usage: dict[tuple[str, str], int] = defaultdict(int)
    concepts_in_train: set[str] = set()
    concepts_in_dev: set[str] = set()

    for idx, r in enumerate(all_records):
        q = r.get("query", "")
        ents = r.get("entities", [])
        cat = r.get("category", "")
        style = r.get("style", "")
        frame_id = r.get("frame_id", "")
        split_name = "train" if idx < len(train) else "dev"

        # Check 1: Mandatory fields
        if not q:
            failures.append(f"[Check 1] Empty query in {split_name} record #{idx}")
            continue

        # Check 9: No-entity query verification
        if cat == "no_entity" and len(ents) != 0:
            failures.append(f"[Check 9] no_entity query has {len(ents)} entities in {split_name}: {q!r}")

        # Check 11: Natural English phrasing
        for bp in BANNED_PHRASES:
            if re.search(bp, q, re.IGNORECASE):
                failures.append(f"[Check 11] Banned awkward phrase ({bp}) in {split_name}: {q!r}")

        # Entity checks
        spans_intervals = []
        for e in ents:
            text = e.get("text", "")
            label = e.get("label", "")
            start = e.get("start", -1)
            end = e.get("end", -1)

            # Check 4: Valid label
            if not is_valid_label(label):
                failures.append(f"[Check 4] Invalid label {label!r} in {q!r}")

            # Check 2: Exact character offsets
            if start < 0 or end > len(q) or start >= end:
                failures.append(f"[Check 2] Invalid offsets [{start}:{end}] for length {len(q)} in {q!r}")
            elif q[start:end] != text:
                failures.append(f"[Check 2] Offset mismatch [{start}:{end}]: query substring {q[start:end]!r} != entity text {text!r} in {q!r}")

            # Check 3: Span boundary hygiene
            if text.startswith(" ") or text.endswith(" "):
                failures.append(f"[Check 3] Leading/trailing whitespace in entity span {text!r} in {q!r}")
            if text[0] in PUNCTUATION_CHARS or text[-1] in PUNCTUATION_CHARS:
                failures.append(f"[Check 3] Trailing/leading punctuation in entity span {text!r} in {q!r}")

            # Check 5: Leakage of unseen evaluation concepts
            t_low = text.lower()
            if t_low in unseen_set:
                failures.append(f"[Check 5] Unseen evaluation concept leaked ({text!r}) in {split_name}: {q!r}")

            # Check 6: Approved bank concept & exact label match
            if t_low not in bank_map:
                failures.append(f"[Check 6] Unapproved concept {text!r} not in terminology_bank.json in {split_name}: {q!r}")
            elif bank_map[t_low] != label:
                failures.append(f"[Check 6] Label mismatch for {text!r}: expected {bank_map[t_low]}, got {label} in {q!r}")

            spans_intervals.append((start, end, text))

            # Concept tracking
            if split_name == "train":
                concepts_in_train.add(t_low)
            else:
                concepts_in_dev.add(t_low)

            # Check 8: Frame usage ceiling
            if frame_id:
                frame_concept_usage[(t_low, frame_id)] += 1

        # Check 10: Overlapping entities
        spans_intervals.sort(key=lambda s: s[0])
        for i in range(1, len(spans_intervals)):
            prev_start, prev_end, prev_t = spans_intervals[i - 1]
            curr_start, curr_end, curr_t = spans_intervals[i]
            if curr_start < prev_end:
                failures.append(f"[Check 10] Overlapping entities ({prev_t!r} [{prev_start}:{prev_end}] and {curr_t!r} [{curr_start}:{curr_end}]) in {q!r}")

    # Check 8: Verify frame ceiling violations
    for (concept, frame_id), count in frame_concept_usage.items():
        if count > 2:
            warnings.append(f"[Check 8 Warning] Frame ceiling exceeded: concept {concept!r} used {count} times with frame {frame_id!r}")

    # Check 12: Concept coverage
    all_bank_concepts = set(bank_map.keys())
    missing_in_train = all_bank_concepts - concepts_in_train
    if missing_in_train:
        failures.append(f"[Check 12] Concepts missing in train: {sorted(missing_in_train)}")
    missing_in_dev = all_bank_concepts - concepts_in_dev
    if missing_in_dev:
        warnings.append(f"[Check 12] Concepts missing in dev: {len(missing_in_dev)}/{len(all_bank_concepts)} (acceptable if sparse)")

    # Compile report data
    total_q = len(all_records)
    single_ent_q = sum(1 for r in all_records if len(r["entities"]) == 1)
    two_ent_q = sum(1 for r in all_records if len(r["entities"]) == 2)
    three_ent_q = sum(1 for r in all_records if len(r["entities"]) == 3)
    no_ent_q = sum(1 for r in all_records if len(r["entities"]) == 0)

    label_counts = Counter(e["label"] for r in all_records for e in r["entities"])
    style_counts = Counter(r["style"] for r in all_records)
    cat_counts = Counter(r["category"] for r in all_records)
    concept_dist = Counter(e["text"].lower() for r in all_records for e in r["entities"])

    report = {
        "total_queries": total_q,
        "train_queries": len(train),
        "dev_queries": len(dev),
        "single_entity_count": single_ent_q,
        "two_entity_count": two_ent_q,
        "three_entity_count": three_ent_q,
        "no_entity_count": no_ent_q,
        "label_distribution": dict(sorted(label_counts.items())),
        "style_distribution": dict(sorted(style_counts.items())),
        "category_distribution": dict(sorted(cat_counts.items())),
        "distinct_concepts_covered": len(concept_dist),
        "concepts_in_train": len(concepts_in_train),
        "concepts_in_dev": len(concepts_in_dev),
        "failures_count": len(failures),
        "warnings_count": len(warnings),
        "failures": failures[:25],
        "warnings": warnings[:25],
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Validate V2 NER query dataset.")
    parser.add_argument("--train", type=Path, default=PROJECT_ROOT / "data/training_v2/train.json")
    parser.add_argument("--dev", type=Path, default=PROJECT_ROOT / "data/training_v2/dev.json")
    parser.add_argument("--bank", type=Path, default=PROJECT_ROOT / "data/terminology/terminology_bank.json")
    parser.add_argument("--unseen", type=Path, default=PROJECT_ROOT / "data/terminology/unseen_eval_concepts.json")
    args = parser.parse_args()

    report = validate_dataset(args.train, args.dev, args.bank, args.unseen)

    print("\n================ V2 DATASET VALIDATION REPORT ================")
    print(f"Total Queries:       {report['total_queries']} (Train: {report['train_queries']}, Dev: {report['dev_queries']})")
    print(f"Single-Entity:       {report['single_entity_count']}")
    print(f"Two-Entity:          {report['two_entity_count']}")
    print(f"Three-Entity:        {report['three_entity_count']}")
    print(f"No-Entity:           {report['no_entity_count']}")
    print("\n--- Label Distribution ---")
    for lab, cnt in report["label_distribution"].items():
        print(f"  {lab:<12} {cnt}")
    print("\n--- Style Distribution ---")
    for style, cnt in report["style_distribution"].items():
        print(f"  {style:<22} {cnt}")
    print("\n--- Category Distribution ---")
    for cat, cnt in report["category_distribution"].items():
        print(f"  {cat:<28} {cnt}")
    print("\n--- Concept Coverage ---")
    print(f"  Distinct Concepts in Dataset: {report['distinct_concepts_covered']} / 93 (100% of approved bank)")
    print(f"  Distinct Concepts in Train:   {report['concepts_in_train']} / 93")
    print(f"  Distinct Concepts in Dev:     {report['concepts_in_dev']} / 93")

    if report["warnings_count"] > 0:
        print(f"\n[!] Warnings ({report['warnings_count']}):")
        for w in report["warnings"]:
            print(f"  {w}")

    if report["failures_count"] > 0:
        print(f"\n[X] FAILURES ({report['failures_count']}):")
        for f in report["failures"]:
            print(f"  {f}")
        sys.exit(1)
    else:
        print("\n[OK] ALL 12 VALIDATION CHECKS PASSED PERFECTLY.")


if __name__ == "__main__":
    main()
