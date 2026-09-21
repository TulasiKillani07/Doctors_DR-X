"""
finalize_terminology.py — turn the human-reviewed terminology into the clean bank.

Reads the corrected review file (the audit/source-of-truth of human decisions)
and produces the clean, deduplicated CONSUMPTION layer that the query generator
will use.

Input : data/terminology/reviewed_terminology_corrected.json  (untouched)
Output: data/terminology/terminology_bank.json                (generated)

Rules applied:
  1. Keep only rows with review_status in {APPROVED, RELABEL}. The final label
     is `reviewed_label` (source column never determines it).
  2. Fix the known encoding artifact:  "Î±" -> "α".
  3. CONDITION deduplication to canonical forms:
        breastfeeding      <- breastfeeding, breast-feeding
        dialysis           <- dialysis, hemodialysis, haemodialysis
        renal impairment   <- renal impairment, renal insufficiency, impaired renal function
        hepatic impairment <- hepatic impairment, hepatic insufficiency, impaired hepatic function
        paediatric         <- paediatric, pediatric
     (elderly, lactation, pregnancy already canonical)
  4. Flag ambiguous concepts with `needs_final_check: true` so they are NOT
     silently treated as gold before the V1 SYMPTOM/DISEASE/CONDITION check.

The corrected review file is never modified — it stays the audit record.

Usage:
    python -m src.finalize_terminology \
        --input data/terminology/reviewed_terminology_corrected.json \
        --output data/terminology/terminology_bank.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

VALID_LABELS = {"DISEASE", "SYMPTOM", "CONDITION"}
KEEP_STATUSES = {"APPROVED", "RELABEL"}

# Encoding artifact fix (mojibake for the Greek alpha).
ENCODING_FIXES = {
    "Î±": "α",
}

# CONDITION canonicalization: normalized_concept substring -> canonical concept.
# Order matters (most specific first).
CONDITION_CANONICAL = [
    ("impaired renal function", "renal impairment"),
    ("renal insufficiency", "renal impairment"),
    ("renal impairment", "renal impairment"),
    ("impaired hepatic function", "hepatic impairment"),
    ("hepatic insufficiency", "hepatic impairment"),
    ("hepatic impairment", "hepatic impairment"),
    ("breast-feeding", "breastfeeding"),
    ("breastfeeding", "breastfeeding"),
    ("haemodialysis", "dialysis"),
    ("hemodialysis", "dialysis"),
    ("dialysis", "dialysis"),
    ("paediatric", "paediatric"),
    ("pediatric", "paediatric"),
    ("lactation", "lactation"),
    ("pregnancy", "pregnancy"),
    ("elderly", "elderly"),
]

# Concepts that were flagged for a final semantic check against the V1 label
# definitions before being treated as ground truth (surfaced, not silently trusted).
NEEDS_FINAL_CHECK = {
    "hyperglycemia",
    "hypoglycemia",
    "respiratory failure",
    "cardiomegaly",
    "cardiac insufficiency",
    "biliary obstructive disorders",
    "rheumatic diseases",
    "thyroid dysfunction",
    "acute renal failure",
    "seizures",
    "swelling",
    "swelling of hands/feet/legs/weight gain",
    "change or absence of menstrual period",
    "weight gain or loss",
}

# Final human decisions for the flagged concepts. Applied case-insensitively
# against the canonical `concept` value. Value is either a label
# (DISEASE / SYMPTOM / CONDITION) to keep/relabel, or "DROP" to remove.
# Resolving a concept here also clears its needs_final_check flag.
FINAL_DECISIONS: dict[str, str] = {
    # keep / relabel
    "acute renal failure": "DISEASE",
    "cardiac insufficiency": "DISEASE",
    "cardiomegaly": "DISEASE",
    "respiratory failure": "DISEASE",
    "thyroid dysfunction": "DISEASE",
    # hyperglycemia / hypoglycemia are lab/measurement findings, treated as
    # DISEASE (named metabolic states), not self-reported SYMPTOMs.
    "hyperglycemia": "DISEASE",
    "hypoglycemia": "DISEASE",
    "seizures": "SYMPTOM",
    "swelling": "SYMPTOM",
    # drop
    "biliary obstructive disorders": "DROP",
    "rheumatic diseases": "DROP",
    "change or absence of menstrual period": "DROP",
    "swelling of hands/feet/legs/weight gain": "DROP",
    "weight gain or loss": "DROP",
}
# Normalize keys to lowercase for case-insensitive lookup.
FINAL_DECISIONS = {k.lower(): v for k, v in FINAL_DECISIONS.items()}


def apply_encoding_fixes(text: str) -> str:
    for bad, good in ENCODING_FIXES.items():
        text = text.replace(bad, good)
    return text


def canonical_condition(normalized: str) -> str:
    low = normalized.lower()
    for cue, canonical in CONDITION_CANONICAL:
        if cue in low:
            return canonical
    return normalized  # fall back to whatever the reviewer set


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize the reviewed terminology into a clean bank.")
    parser.add_argument("--input", type=Path, default=Path("data/terminology/reviewed_terminology_corrected.json"))
    parser.add_argument("--output", type=Path, default=Path("data/terminology/terminology_bank.json"))
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as f:
        reviewed = json.load(f)

    # label -> {canonical_concept: entry}
    banks: dict[str, dict[str, dict]] = {"DISEASE": {}, "SYMPTOM": {}, "CONDITION": {}}
    skipped_bad_label = 0

    for row in reviewed:
        status = (row.get("review_status") or "").strip().upper()
        if status not in KEEP_STATUSES:
            continue

        label = (row.get("reviewed_label") or "").strip().upper()
        if label not in VALID_LABELS:
            skipped_bad_label += 1
            continue

        concept = apply_encoding_fixes(
            (row.get("normalized_concept") or row.get("concept") or "").strip()
        )
        if not concept:
            continue

        if label == "CONDITION":
            concept = canonical_condition(concept)

        # Apply final human decisions (case-insensitive on the canonical concept).
        decision = FINAL_DECISIONS.get(concept.lower())
        resolved = False
        if decision is not None:
            if decision == "DROP":
                continue  # remove from the bank
            if decision in VALID_LABELS:
                label = decision  # keep or relabel
                resolved = True

        key = concept.lower()
        if key in banks[label]:
            # Already have this canonical concept — record the extra source.
            banks[label][key]["source_variants"].append({
                "concept": row.get("concept", ""),
                "source_drug": row.get("source_drug", ""),
                "source_column": row.get("source_column", ""),
            })
            continue

        banks[label][key] = {
            "concept": concept,
            "label": label,
            # Flagged only if it still needs a check AND has not been resolved.
            "needs_final_check": (key in NEEDS_FINAL_CHECK) and not resolved,
            "source_variants": [{
                "concept": row.get("concept", ""),
                "source_drug": row.get("source_drug", ""),
                "source_column": row.get("source_column", ""),
            }],
        }

    # Build sorted output grouped by label.
    output = {
        "labels": sorted(VALID_LABELS),
        "counts": {},
        "needs_final_check_count": 0,
        "concepts": {},
    }
    for label in ("DISEASE", "SYMPTOM", "CONDITION"):
        entries = sorted(banks[label].values(), key=lambda e: e["concept"].lower())
        output["concepts"][label] = entries
        output["counts"][label] = len(entries)
        output["needs_final_check_count"] += sum(1 for e in entries if e["needs_final_check"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("Terminology bank finalized (clean consumption layer):")
    for label in ("DISEASE", "SYMPTOM", "CONDITION"):
        print(f"  {label:<10} {output['counts'][label]} concepts")
    print(f"  needs_final_check flagged: {output['needs_final_check_count']}")
    if skipped_bad_label:
        print(f"  skipped rows with invalid reviewed_label: {skipped_bad_label}")
    print(f"\n  Written -> {args.output}")
    print("  (reviewed_terminology_corrected.json left untouched as the audit record)")


if __name__ == "__main__":
    main()
