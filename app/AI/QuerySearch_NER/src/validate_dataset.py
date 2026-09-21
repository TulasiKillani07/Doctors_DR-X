"""
validate_dataset.py — final dataset-quality gate before NER training.

Validates the generated train/test JSON against the terminology bank and the
unseen eval concepts. Exits non-zero if any check fails, so it can gate training.

Checks:
  1.  labels are DISEASE / SYMPTOM / CONDITION only
  2.  every TRAIN entity concept exists in the terminology bank with the SAME label
      (approved terminology only; no accidental relabeling)
  3.  every entity offset is exact (query[start:end] == text)
  4.  no duplicate queries (across train + test)
  5.  no_entity category has zero entities
  6.  no unseen concept appears in TRAIN
  7.  train/test concept separation: unseen-concept test rows use only unseen concepts
  8.  natural English phrasing: no "adolescents patients", "during obesity",
      "during paediatric", "during elderly", "given to <noun-state>"
  9.  test unseen entities correspond to the unseen eval concepts
  10. bank and unseen vocabularies are disjoint

Usage:
    python -m src.validate_dataset \
        --train data/training/train.json \
        --test data/training/test.json \
        --bank data/terminology/terminology_bank.json \
        --unseen data/terminology/unseen_eval_concepts.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

VALID_LABELS = {"DISEASE", "SYMPTOM", "CONDITION"}

BAD_PHRASES = [
    r"\badolescents patients\b",
    r"\bduring obesity\b",
    r"\bduring paediatric\b",
    r"\bduring pediatric\b",
    r"\bduring elderly\b",
    r"\bduring immunocompromised\b",
    r"\bduring adolescents\b",
    r"\bgiven to (pregnancy|lactation|breastfeeding|dialysis|renal impairment|hepatic impairment|obesity)\b",
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def bank_label_map(bank: dict) -> dict[str, str]:
    """concept(lower) -> label, from the terminology bank."""
    out = {}
    for label in VALID_LABELS:
        for entry in bank.get("concepts", {}).get(label, []):
            out[entry["concept"].lower()] = label
    return out


def unseen_label_map(unseen: dict) -> dict[str, str]:
    out = {}
    for label in VALID_LABELS:
        for concept in unseen.get("concepts", {}).get(label, []):
            out[concept.lower()] = label
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated NER dataset before training.")
    parser.add_argument("--train", type=Path, default=Path("data/training/train.json"))
    parser.add_argument("--test", type=Path, default=Path("data/training/test.json"))
    parser.add_argument("--bank", type=Path, default=Path("data/terminology/terminology_bank.json"))
    parser.add_argument("--unseen", type=Path, default=Path("data/terminology/unseen_eval_concepts.json"))
    args = parser.parse_args()

    train = load_json(args.train)
    test = load_json(args.test)
    bank = load_json(args.bank)
    unseen = load_json(args.unseen)

    bank_map = bank_label_map(bank)
    unseen_map = unseen_label_map(unseen)
    all_records = train + test

    failures: list[str] = []

    # 10. disjoint vocabularies
    overlap = set(bank_map) & set(unseen_map)
    if overlap:
        failures.append(f"[10] bank/unseen overlap: {sorted(overlap)}")

    # 1. labels
    for r in all_records:
        for e in r["entities"]:
            if e["label"] not in VALID_LABELS:
                failures.append(f"[1] invalid label {e['label']!r} in: {r['query']!r}")

    # 3. offsets
    for r in all_records:
        for e in r["entities"]:
            s, en = e["start"], e["end"]
            if s < 0 or en > len(r["query"]) or r["query"][s:en] != e["text"]:
                failures.append(f"[3] offset mismatch in: {r['query']!r} ({e})")

    # 4. duplicate queries
    seen = {}
    for r in all_records:
        seen[r["query"]] = seen.get(r["query"], 0) + 1
    dupes = [q for q, c in seen.items() if c > 1]
    if dupes:
        failures.append(f"[4] {len(dupes)} duplicate queries, e.g. {dupes[:3]}")

    # 5. no_entity -> zero entities
    for r in all_records:
        if r["category"] == "no_entity" and r["entities"]:
            failures.append(f"[5] no_entity has entities: {r['query']!r}")

    # 2. TRAIN entities correspond to bank with same label; 6. no unseen in train
    for r in train:
        for e in r["entities"]:
            concept = e["text"].lower()
            if concept in unseen_map:
                failures.append(f"[6] unseen concept {e['text']!r} in TRAIN: {r['query']!r}")
            elif concept not in bank_map:
                failures.append(f"[2] TRAIN entity {e['text']!r} not in bank: {r['query']!r}")
            elif bank_map[concept] != e["label"]:
                failures.append(
                    f"[2] relabeling: {e['text']!r} is {e['label']} but bank says "
                    f"{bank_map[concept]}: {r['query']!r}"
                )

    # 9. test unseen entities correspond to unseen concepts
    for r in test:
        if r["category"] != "test_unseen_concept":
            continue
        for e in r["entities"]:
            concept = e["text"].lower()
            if concept not in unseen_map:
                failures.append(f"[9] unseen-test entity {e['text']!r} not in unseen set: {r['query']!r}")
            elif unseen_map[concept] != e["label"]:
                failures.append(
                    f"[9] unseen-test relabel: {e['text']!r} is {e['label']} but unseen set says "
                    f"{unseen_map[concept]}: {r['query']!r}"
                )

    # 8. natural English phrasing
    for r in all_records:
        for pat in BAD_PHRASES:
            if re.search(pat, r["query"], re.IGNORECASE):
                failures.append(f"[8] unnatural phrasing /{pat}/ in: {r['query']!r}")

    # Report
    print(f"Records: train={len(train)}, test={len(test)}, total={len(all_records)}")
    print(f"Bank concepts: {len(bank_map)}  |  Unseen concepts: {len(unseen_map)}")
    if not failures:
        print("\nALL CHECKS PASSED — dataset is training-ready.")
        return
    print(f"\nFAILURES: {len(failures)}")
    for f in failures[:50]:
        print(f"  {f}")
    if len(failures) > 50:
        print(f"  ... and {len(failures) - 50} more")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
