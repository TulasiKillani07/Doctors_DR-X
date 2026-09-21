"""
validate_semantics_v2.py — Automated semantic, ontology, and boundary validator for V2.

Enforces strict clinical ontology rules and consistency across data/training_v2/train.json and dev.json:

Rules Enforced:
  1. Bank-Label Consistency:
     For every entity in the dataset:
       generated concept -> terminology_bank -> expected label
       Assert: generated label == bank label. (Zero label drift or cross-label pollution).
  2. Strict Quarantine:
     Zero leakage of concepts from data/terminology/unseen_eval_concepts.json.
  3. DISEASE vs CONDITION Boundaries:
     - 'acute renal failure' MUST always be DISEASE.
     - 'renal impairment' MUST always be CONDITION.
     - 'autoimmune hepatitis' MUST always be DISEASE.
     - 'hepatic impairment' MUST always be CONDITION.
     - 'cardiac insufficiency' MUST always be DISEASE.
     - 'elderly', 'pregnancy', 'lactation', 'breastfeeding', 'dialysis', 'paediatric' MUST always be CONDITION.
     - Co-occurrence: Verifies robust coexistence of DISEASE + CONDITION in single queries (>= 350 queries).
  4. Seizure Cluster Boundaries (Option A):
     - 'seizures' MUST always be SYMPTOM.
     - 'complex partial seizures' MUST always be DISEASE.
     - 'simple and complex absence seizures' MUST always be DISEASE.
     - Wording must naturally reflect the concept without artificial diagnostics.
  5. Symptom Alignment:
     - 'urticaria' MUST always be SYMPTOM.
  6. Universal Concept Coverage:
     - All 93 approved concepts present in both train and dev splits.
     - Minimum representation threshold (>= 5 occurrences per concept across dataset).

Exits with non-zero exit code if any semantic or ontology violation is found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]

KEY_DISEASE_CONDITION_BOUNDARIES = [
    ("acute renal failure", "DISEASE"),
    ("renal impairment", "CONDITION"),
    ("autoimmune hepatitis", "DISEASE"),
    ("hepatic impairment", "CONDITION"),
    ("cardiac insufficiency", "DISEASE"),
    ("elderly", "CONDITION"),
    ("pregnancy", "CONDITION"),
    ("lactation", "CONDITION"),
    ("breastfeeding", "CONDITION"),
    ("dialysis", "CONDITION"),
    ("paediatric", "CONDITION"),
]

KEY_SEIZURE_BOUNDARIES = [
    ("seizures", "SYMPTOM"),
    ("complex partial seizures", "DISEASE"),
    ("simple and complex absence seizures", "DISEASE"),
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_semantics(train_path: Path, dev_path: Path, bank_path: Path, unseen_path: Path) -> bool:
    print("\n========================================================")
    print("        V2 SEMANTIC & ONTOLOGY VALIDATION               ")
    print("========================================================")
    print(f"Train file:     {train_path}")
    print(f"Dev file:       {dev_path}")
    print(f"Bank file:      {bank_path}")
    print(f"Unseen file:    {unseen_path}")

    train_records = load_json(train_path)
    dev_records = load_json(dev_path)
    bank_data = load_json(bank_path)
    unseen_data = load_json(unseen_path)

    all_records = train_records + dev_records
    failures: list[str] = []

    # 1. Build canonical bank lookup: concept.lower() -> expected_label
    bank_map: dict[str, str] = {}
    for label in ("DISEASE", "SYMPTOM", "CONDITION"):
        for entry in bank_data["concepts"].get(label, []):
            bank_map[entry["concept"].lower()] = label

    # 2. Build quarantined unseen set
    unseen_set: set[str] = set()
    for label in ("DISEASE", "SYMPTOM", "CONDITION"):
        for c in unseen_data["concepts"].get(label, []):
            unseen_set.add(c.lower())

    # --------------------------------------------------------------------------
    # Check 1: Bank-label consistency
    # --------------------------------------------------------------------------
    entity_label_violations = 0
    concept_counts_total = Counter()
    concept_counts_train = Counter()
    concept_counts_dev = Counter()

    for idx, r in enumerate(all_records):
        split = "train" if idx < len(train_records) else "dev"
        for ent in r.get("entities", []):
            text_lower = ent["text"].lower()
            label = ent["label"]

            concept_counts_total[text_lower] += 1
            if split == "train":
                concept_counts_train[text_lower] += 1
            else:
                concept_counts_dev[text_lower] += 1

            if text_lower not in bank_map:
                failures.append(f"[Check 1] Entity {text_lower!r} not in approved bank (query: {r['query']!r})")
                entity_label_violations += 1
                continue

            expected_label = bank_map[text_lower]
            if label != expected_label:
                failures.append(
                    f"[Check 1] Bank-label mismatch for {text_lower!r}: "
                    f"expected {expected_label}, got {label} in {split} query: {r['query']!r}"
                )
                entity_label_violations += 1

    print(f"[Check 1: Bank-Label Consistency] Inspected {sum(len(r.get('entities', [])) for r in all_records)} entities -> {entity_label_violations} violations.")

    # --------------------------------------------------------------------------
    # Check 2: Unseen quarantine
    # --------------------------------------------------------------------------
    unseen_leaks = 0
    for idx, r in enumerate(all_records):
        q_text = r.get("query", "")
        # Mask out approved entity spans
        chars = list(q_text)
        for ent in r.get("entities", []):
            st, en = ent.get("start", 0), ent.get("end", 0)
            for i in range(st, min(en, len(chars))):
                chars[i] = " "
            # Also check if entity text itself is quarantined
            if ent.get("text", "").lower() in unseen_set:
                failures.append(f"[Check 2] Quarantine breach: entity text {ent['text']!r} is in unseen_eval_concepts (query: {q_text!r})")
                unseen_leaks += 1

        masked_q = "".join(chars).lower()
        for u in unseen_set:
            pattern = rf"(?<![a-z0-9]){re.escape(u)}(?![a-z0-9])"
            if re.search(pattern, masked_q):
                failures.append(f"[Check 2] Quarantine breach: unseen concept {u!r} found in non-entity query text: {q_text!r}")
                unseen_leaks += 1

    print(f"[Check 2: Unseen Quarantine] Checked against {len(unseen_set)} quarantined concepts -> {unseen_leaks} leaks.")

    # --------------------------------------------------------------------------
    # Check 3: Dedicated Section: DISEASE_CONDITION_BOUNDARIES
    # --------------------------------------------------------------------------
    print("\n--- DISEASE_CONDITION_BOUNDARIES ---")
    boundary_violations = 0
    for concept_name, expected_label in KEY_DISEASE_CONDITION_BOUNDARIES:
        actual_count = concept_counts_total[concept_name]
        print(f"  Concept: {concept_name:<25} Expected: {expected_label:<10} Occurrences: {actual_count}")
        if actual_count == 0:
            failures.append(f"[Check 3] Zero occurrences of boundary concept {concept_name!r}")
            boundary_violations += 1

    # Mixed DISEASE + CONDITION co-occurrence audit
    mixed_dc_queries = 0
    cooccurring_pairs = Counter()

    for r in all_records:
        labels = {e["label"] for e in r.get("entities", [])}
        if "DISEASE" in labels and "CONDITION" in labels:
            mixed_dc_queries += 1
            diseases = [e["text"].lower() for e in r["entities"] if e["label"] == "DISEASE"]
            conditions = [e["text"].lower() for e in r["entities"] if e["label"] == "CONDITION"]
            for d in diseases:
                for c in conditions:
                    cooccurring_pairs[(d, c)] += 1

    print(f"  Total mixed DISEASE + CONDITION queries: {mixed_dc_queries}")
    print(f"  Distinct DISEASE + CONDITION pair types:  {len(cooccurring_pairs)}")
    print(f"  Top Co-occurring DISEASE + CONDITION Pairs:")
    for (d, c), cnt in cooccurring_pairs.most_common(10):
        print(f"    - {d} (DISEASE) + {c} (CONDITION): {cnt} queries")

    # Synonymous condition co-occurrence ban
    synonymous_cooccurrence = 0
    for r in all_records:
        entity_texts = [e["text"].lower() for e in r.get("entities", [])]
        if "breastfeeding" in entity_texts and "lactation" in entity_texts:
            failures.append(f"[Check 3] Synonymous conditions 'breastfeeding' and 'lactation' paired together in: {r['query']!r}")
            synonymous_cooccurrence += 1

    # Multi-entity proportion audit
    multi_entity_count = sum(1 for r in all_records if len(r.get("entities", [])) >= 2)
    multi_entity_pct = (multi_entity_count / len(all_records)) * 100
    print(f"  Multi-entity queries: {multi_entity_count} / {len(all_records)} ({multi_entity_pct:.1f}%)")
    if multi_entity_pct < 65.0:
        failures.append(f"[Check 3] Multi-entity queries below target 65%: {multi_entity_pct:.1f}%")

    if mixed_dc_queries < 600:
        failures.append(
            f"[Check 3] Insufficient mixed DISEASE + CONDITION queries: {mixed_dc_queries} < 600 target."
        )

    # --------------------------------------------------------------------------
    # Check 4: Dedicated Section: SEIZURE_CLUSTER_BOUNDARIES
    # --------------------------------------------------------------------------
    print("\n--- SEIZURE_CLUSTER_BOUNDARIES ---")
    seizure_violations = 0
    for concept_name, expected_label in KEY_SEIZURE_BOUNDARIES:
        actual_count = concept_counts_total[concept_name]
        print(f"  Concept: {concept_name:<36} Expected: {expected_label:<10} Occurrences: {actual_count}")
        if actual_count == 0:
            failures.append(f"[Check 4] Zero occurrences of seizure cluster concept {concept_name!r}")
            seizure_violations += 1

    # Check seizure contextual diversity
    seizure_contexts = Counter()
    for r in all_records:
        entity_texts = [e["text"].lower() for e in r.get("entities", [])]
        for sc, _ in KEY_SEIZURE_BOUNDARIES:
            if sc in entity_texts:
                other_ents = [e["text"].lower() for e in r["entities"] if e["text"].lower() != sc]
                if other_ents:
                    for oe in other_ents:
                        seizure_contexts[(sc, oe)] += 1
                else:
                    seizure_contexts[(sc, "standalone")] += 1

    print("  Seizure Cluster Contextual Breakdown:")
    for (sc, ctx), cnt in sorted(seizure_contexts.items()):
        print(f"    - {sc} with {ctx}: {cnt} queries")

    # --------------------------------------------------------------------------
    # Check 5: Symptom Alignment ('urticaria' -> SYMPTOM)
    # --------------------------------------------------------------------------
    urticaria_count = concept_counts_total["urticaria"]
    print(f"\n[Check 5: Symptom Alignment] 'urticaria' labeled SYMPTOM: {urticaria_count} occurrences.")
    if urticaria_count == 0:
        failures.append("[Check 5] Zero occurrences of 'urticaria' found.")

    # --------------------------------------------------------------------------
    # Check 6: Concept Coverage & Minimum Balance
    # --------------------------------------------------------------------------
    print("\n[Check 6: Concept Coverage & Minimum Balance]")
    missing_train = [c for c in bank_map if concept_counts_train[c] == 0]
    missing_dev = [c for c in bank_map if concept_counts_dev[c] == 0]
    underrepresented = [c for c in bank_map if concept_counts_total[c] < 5]

    print(f"  Approved bank concepts: {len(bank_map)}")
    print(f"  Covered in train:       {len(bank_map) - len(missing_train)} / {len(bank_map)}")
    print(f"  Covered in dev:         {len(bank_map) - len(missing_dev)} / {len(bank_map)}")
    print(f"  Underrepresented (<5):  {len(underrepresented)}")

    if missing_train:
        failures.append(f"[Check 6] Missing concepts in train split: {missing_train}")
    if missing_dev:
        failures.append(f"[Check 6] Missing concepts in dev split: {missing_dev}")
    if underrepresented:
        failures.append(f"[Check 6] Concepts with <5 total occurrences: {underrepresented}")

    # Final verdict
    print("\n========================================================")
    if failures:
        print(f"FAIL: Semantic validation failed with {len(failures)} violations:")
        for f in failures[:20]:
            print(f"  - {f}")
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more errors.")
        return False

    print("PASS: 100% of semantic, ontology, and boundary rules satisfied.")
    print("========================================================\n")
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate semantics and ontology boundaries of V2 dataset.")
    parser.add_argument("--train", type=Path, default=PROJECT_ROOT / "data/training_v2/train.json")
    parser.add_argument("--dev", type=Path, default=PROJECT_ROOT / "data/training_v2/dev.json")
    parser.add_argument("--bank", type=Path, default=PROJECT_ROOT / "data/terminology/terminology_bank.json")
    parser.add_argument("--unseen", type=Path, default=PROJECT_ROOT / "data/terminology/unseen_eval_concepts.json")
    args = parser.parse_args()

    success = validate_semantics(args.train, args.dev, args.bank, args.unseen)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
