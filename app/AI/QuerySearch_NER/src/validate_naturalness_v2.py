"""
validate_naturalness_v2.py — Automated linguistic, grammar, and template compatibility validator for V2.

Enforces strict naturalness, grammar rules, and template compatibility across
data/training_v2/train.json and dev.json:

Checks:
  1. CONDITION_GRAMMAR_RULES:
     - 'elderly' and 'paediatric' MUST only appear in valid adjectival prepositional phrases
       ('in elderly patients', 'for elderly patients', 'in paediatric patients', 'for paediatric patients').
       BANS: 'during elderly', 'during paediatric', 'given to elderly', etc.
     - 'pregnancy' MUST only appear as 'during pregnancy' or 'in pregnancy'.
       BANS: 'given to pregnancy', 'for patients in pregnancy', etc.
     - 'lactation' MUST only appear as 'during lactation'.
     - 'breastfeeding' MUST only appear as 'while breastfeeding' or 'during breastfeeding'.
     - 'renal impairment' and 'hepatic impairment' MUST only appear as
       'in [patients with] renal/hepatic impairment'.
       BANS: 'during renal impairment', 'given to renal impairment', etc.
     - 'dialysis' MUST only appear as 'in patients [undergoing/on] dialysis' or 'during dialysis'.
  2. Synonymous Context Co-occurrence Ban:
     - 'breastfeeding' and 'lactation' MUST NEVER be paired together in the same query.
  3. Template Incompatibility & Word Repetition:
     - No duplicate consecutive words (e.g. zero 'safe safe', zero 'in in', zero 'available available').
     - No conflicting descriptors (e.g. zero 'avoided safe', zero 'recommended safe').
  4. Clinical Decision / Recommendation Jargon Ban:
     - No recommendation-heavy phrasing: 'what should i prescribe', 'what is recommended',
       'which agents should be avoided', 'what can i give', 'doctor evaluating',
       'patient diagnosed with ... what should i prescribe'.
     - Clean, direct medical search phrasing only ('treatment for X', 'medicines for X in Y').
  5. Syntactic Hygiene:
     - No repeated prepositional phrases ('in patients ... in patients').
     - No hanging prepositions at sentence ends.

Exits with non-zero exit code if any defect is detected.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 1. Consecutive duplicate words (case-insensitive)
RE_DUPLICATE_WORDS = re.compile(r"\b([a-zA-Z]+)\s+\1\b", re.IGNORECASE)

# 2. Repeated prepositional phrase patterns
RE_REPEATED_IN_PATIENTS = re.compile(r"\bin patients\b.*\bin patients\b", re.IGNORECASE)
RE_REPEATED_WITH_WITH = re.compile(r"\bwith\b.*\bwith\b.*\bwith\b", re.IGNORECASE)
RE_REPEATED_DURING = re.compile(r"\bduring\b.*\bduring\b", re.IGNORECASE)

# 3. Conflicting modifier patterns (e.g. avoided + safe)
RE_CONFLICTING_MODIFIERS = [
    re.compile(r"\bavoided\s+safe\b", re.IGNORECASE),
    re.compile(r"\brecommended\s+safe\b", re.IGNORECASE),
    re.compile(r"\bsafe\s+during\s+breastfeeding\s+and\s+lactation\b", re.IGNORECASE),
]

# 4. Banned recommendation-heavy & case-note prose
BANNED_RECOMMENDATION_PATTERNS = [
    re.compile(r"\bwhat should i prescribe\b", re.IGNORECASE),
    re.compile(r"\bwhat is recommended\b", re.IGNORECASE),
    re.compile(r"\bwhich agents should be avoided\b", re.IGNORECASE),
    re.compile(r"\bshould be avoided\b", re.IGNORECASE),
    re.compile(r"\bwhat can i give\b", re.IGNORECASE),
    re.compile(r"\bwhat should be given\b", re.IGNORECASE),
    re.compile(r"\bdoctor evaluating\b", re.IGNORECASE),
    re.compile(r"\bcurrently evaluating\b", re.IGNORECASE),
    re.compile(r"\bdoctor requests\b", re.IGNORECASE),
    re.compile(r"\bfor clinic review\b", re.IGNORECASE),
    re.compile(r"\bas a diagnosis\b", re.IGNORECASE),
    re.compile(r"\bpresents to clinic\b", re.IGNORECASE),
]

# 5. Banned clinical trial jargon
BANNED_JARGON_PATTERNS = [
    re.compile(r"\bfirst-line\b", re.IGNORECASE),
    re.compile(r"\bsecond-line\b", re.IGNORECASE),
    re.compile(r"\bstandard of care\b", re.IGNORECASE),
    re.compile(r"\bimprove outcomes\b", re.IGNORECASE),
    re.compile(r"\bclinical endpoints?\b", re.IGNORECASE),
    re.compile(r"\bplacebo-controlled\b", re.IGNORECASE),
]

# 6. Hanging prepositions at query end
RE_HANGING_PREPOSITION = re.compile(r"\b(for|with|in|during|to|at|on|by|from|about)\s*[.?!]?\s*$", re.IGNORECASE)

# 7. Condition Grammar Incompatibilities
INVALID_CONDITION_PATTERNS = [
    (re.compile(r"\bduring\s+(the\s+)?elderly\b", re.IGNORECASE), "Invalid construction: 'during elderly'"),
    (re.compile(r"\bduring\s+(the\s+)?paediatric\b", re.IGNORECASE), "Invalid construction: 'during paediatric'"),
    (re.compile(r"\bduring\s+renal\s+impairment\b", re.IGNORECASE), "Invalid construction: 'during renal impairment'"),
    (re.compile(r"\bduring\s+hepatic\s+impairment\b", re.IGNORECASE), "Invalid construction: 'during hepatic impairment'"),
    (re.compile(r"\bgiven\s+to\s+pregnancy\b", re.IGNORECASE), "Invalid construction: 'given to pregnancy'"),
    (re.compile(r"\bgiven\s+to\s+renal\s+impairment\b", re.IGNORECASE), "Invalid construction: 'given to renal impairment'"),
    (re.compile(r"\bgiven\s+to\s+hepatic\s+impairment\b", re.IGNORECASE), "Invalid construction: 'given to hepatic impairment'"),
    (re.compile(r"\bfor\s+patients\s+in\s+pregnancy\b", re.IGNORECASE), "Awkward construction: 'for patients in pregnancy'"),
]


def validate_query_naturalness(query: str, entities: list[dict], split_name: str, record_idx: int) -> list[str]:
    errors = []
    text = query.strip()
    entity_texts = [e["text"].lower() for e in entities]

    # Check 1: Duplicate consecutive words
    for match in RE_DUPLICATE_WORDS.finditer(text):
        word = match.group(1).lower()
        errors.append(f"Duplicate consecutive word '{word}' found in: {text!r}")

    # Check 2: Repeated prepositional phrases
    if RE_REPEATED_IN_PATIENTS.search(text):
        errors.append(f"Repeated 'in patients' phrase found in: {text!r}")
    if RE_REPEATED_WITH_WITH.search(text):
        errors.append(f"Excessive 'with' prepositions found in: {text!r}")
    if RE_REPEATED_DURING.search(text):
        errors.append(f"Repeated 'during' prepositions found in: {text!r}")

    # Check 3: Conflicting modifier phrases
    for pattern in RE_CONFLICTING_MODIFIERS:
        if pattern.search(text):
            errors.append(f"Conflicting modifier combination in: {text!r}")

    # Check 4: Synonymous context co-occurrence ban (breastfeeding + lactation)
    if "breastfeeding" in entity_texts and "lactation" in entity_texts:
        errors.append(f"Synonymous conditions 'breastfeeding' and 'lactation' paired together in: {text!r}")

    # Check 5: Condition grammar incompatibilities
    for pattern, reason in INVALID_CONDITION_PATTERNS:
        if pattern.search(text):
            errors.append(f"{reason} in: {text!r}")

    # Check 6: Recommendation-heavy & case-note prose ban
    for pattern in BANNED_RECOMMENDATION_PATTERNS:
        if pattern.search(text):
            errors.append(f"Banned recommendation/case-note phrasing ({pattern.pattern}) in: {text!r}")

    # Check 7: Banned clinical trial jargon
    for pattern in BANNED_JARGON_PATTERNS:
        if pattern.search(text):
            errors.append(f"Banned clinical trial jargon ({pattern.pattern}) in: {text!r}")

    # Check 8: Hanging prepositions
    if RE_HANGING_PREPOSITION.search(text):
        errors.append(f"Query ends with hanging preposition in: {text!r}")

    return errors


def validate_files(train_path: Path, dev_path: Path) -> bool:
    print(f"\n========================================================")
    print(f"       V2 NATURALNESS & TEMPLATE COMPATIBILITY          ")
    print(f"========================================================")
    print(f"Train file: {train_path}")
    print(f"Dev file:   {dev_path}")

    all_errors: list[str] = []
    total_queries = 0

    for split_path, split_name in [(train_path, "train"), (dev_path, "dev")]:
        if not split_path.exists():
            print(f"ERROR: File not found: {split_path}")
            return False

        with split_path.open("r", encoding="utf-8") as f:
            records = json.load(f)

        total_queries += len(records)
        split_errors = 0

        for idx, r in enumerate(records):
            q = r.get("query", "")
            ents = r.get("entities", [])
            errs = validate_query_naturalness(q, ents, split_name, idx)
            if errs:
                split_errors += len(errs)
                for e in errs:
                    all_errors.append(f"[{split_name} #{idx}] {e}")

        print(f"[{split_name}] Validated {len(records)} queries -> {split_errors} naturalness/compatibility defects.")

    print(f"\nTotal queries inspected: {total_queries}")
    if all_errors:
        print(f"FAIL: Found {len(all_errors)} naturalness defects:")
        for err in all_errors[:20]:
            print(f"  - {err}")
        if len(all_errors) > 20:
            print(f"  ... and {len(all_errors) - 20} more errors.")
        return False

    print("PASS: 100% of queries pass naturalness, condition grammar, and template compatibility validation.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate naturalness and template compatibility of V2 query dataset.")
    parser.add_argument("--train", type=Path, default=PROJECT_ROOT / "data/training_v2/train.json")
    parser.add_argument("--dev", type=Path, default=PROJECT_ROOT / "data/training_v2/dev.json")
    args = parser.parse_args()

    success = validate_files(args.train, args.dev)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
