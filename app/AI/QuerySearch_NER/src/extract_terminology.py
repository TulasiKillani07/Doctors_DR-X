"""
extract_terminology.py — Stage A of the NER dataset pipeline (JSON-only, precision-focused).

Reads the Sanofi drug CSV and produces a CANDIDATE terminology bank of
DISEASE / SYMPTOM / CONDITION concepts, each with a source reference and a
proposed label + confidence + review reason so the list is auditable.

Output is JSON/JSONL ONLY — no CSV anywhere in this pipeline.

Design principles:
  - Optimize for HIGH-QUALITY candidates, not maximum count.
  - The extractor PROPOSES a candidate label and a reason/confidence.
    It NEVER decides the final label. A human confirms in reviewed_terminology.json.
  - Ambiguous cases (e.g. a clinical diagnosis appearing in a CONDITION-source
    column) are explicitly flagged for review.
  - Nothing here enters the training data.

Label -> source column mapping (V1, locked):
    DISEASE    <- indications
    SYMPTOM    <- symptoms
    CONDITION  <- pregnancy_lactation, renal_dose_adjustment,
                  hepatic_dose_adjustment, contraindications, warnings_precautions

    Intentionally EXCLUDED from V1 terminology extraction:
      - therapeutic_category  (specialty names -> dictionary layer, not DISEASE)
      - side_effects          (broad adverse-event taxonomy, not patient complaints)
    These columns remain untouched in the source CSV for later use.

Outputs (in --outdir, default data/terminology/):
    disease_candidates.json
    symptom_candidates.json
    condition_candidates.json
    candidates.json               (combined)
    reviewed_terminology.json     (pre-populated review sheet; you fill status)

Usage:
    python -m src.extract_terminology \
        --input "sample_drug_data_sanofi (1).csv" \
        --outdir data/terminology
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

# Which CSV columns feed which candidate label (V1, locked).
LABEL_SOURCE_COLUMNS: dict[str, list[str]] = {
    "DISEASE": ["indications"],
    "SYMPTOM": ["symptoms"],
    "CONDITION": [
        "pregnancy_lactation",
        "renal_dose_adjustment",
        "hepatic_dose_adjustment",
        "contraindications",
        "warnings_precautions",
    ],
}

EMPTY_VALUES = {"", "na", "n/a", "none", "not applicable", "not stated", "not known"}

# CONDITION cue terms: reliably indicate a treatment-use condition/state.
CONDITION_CUES = [
    "pregnancy",
    "lactation",
    "breast-feeding",
    "breastfeeding",
    "renal impairment",
    "impaired renal function",
    "renal insufficiency",
    "hepatic impairment",
    "impaired hepatic function",
    "hepatic insufficiency",
    "elderly",
    "paediatric",
    "pediatric",
    "immunocompromised",
    "dialysis",
    "hemodialysis",
    "haemodialysis",
]

# Terms that, if a CONDITION-column phrase contains them, likely name a clinical
# DISEASE/diagnosis rather than a treatment-use condition -> flag for review.
DISEASE_LIKE_IN_CONDITION = [
    "failure",
    "disease",
    "syndrome",
    "cancer",
    "carcinoma",
    "infection",
    "bleeding",
    "haemorrhage",
    "hemorrhage",
    "stenosis",
    "infarction",
    "arrhythmia",
]

SPLIT_PATTERN = re.compile(
    r"[;,\.\u2022\n\r]|\(|\)|\bincluding\b|\bsuch as\b|\band/or\b", re.IGNORECASE
)

LEADING_JUNK = re.compile(
    r"^(and|or|as|alone|are|is|was|were|with|without|when|where|which|that|the|a|an|"
    r"in|on|of|for|to|by|at|after|before|during|combined|combination|adjunct|"
    r"administered|used|use|do|does|can|may|must|not|other|prior|following)\b",
    re.IGNORECASE,
)

LONG_PHRASE_WORDS = 6


def normalize(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" -:•\t\"'")
    return text


def is_empty(value: str) -> bool:
    return value is None or normalize(value).lower() in EMPTY_VALUES


def has_alpha(text: str) -> bool:
    return bool(re.search(r"[a-zA-Z]", text))


def is_numeric_or_dosing_junk(text: str) -> bool:
    low = text.lower()
    if re.search(r"\d", low) and re.search(
        r"\b(mg|ml|mcg|μg|ug|g|l|m2|m²|min|ml/min|uln|ast|alt|kg|mmol|mg/l|/min|%)\b", low
    ):
        return True
    if re.match(r"^\s*[<>]?\d", low) and len(low.split()) <= 4:
        return True
    return False


def looks_like_fragment(text: str) -> bool:
    if LEADING_JUNK.match(text):
        return True
    if not has_alpha(text):
        return True
    return False


def candidate_phrases(cell: str) -> list[str]:
    parts = SPLIT_PATTERN.split(cell)
    out: list[str] = []
    for p in parts:
        p = normalize(p)
        if not p or p.lower() in EMPTY_VALUES:
            continue
        if len(p) < 3:
            continue
        if is_numeric_or_dosing_junk(p):
            continue
        if looks_like_fragment(p):
            continue
        out.append(p)
    return out


def extract_condition_cues(cell: str) -> list[str]:
    low = cell.lower()
    return [cue for cue in CONDITION_CUES if cue in low]


def word_count(phrase: str) -> int:
    return len(phrase.split())


def assess(label: str, phrase: str, is_cue: bool) -> tuple[str, str]:
    wc = word_count(phrase)
    low = phrase.lower()

    if label == "CONDITION":
        if is_cue:
            return "HIGH", "matched known condition cue term"
        if any(term in low for term in DISEASE_LIKE_IN_CONDITION):
            return "LOW", "may be a clinical diagnosis (DISEASE), not a treatment-use condition — REVIEW"
        if wc > LONG_PHRASE_WORDS:
            return "LOW", "long phrase, likely a clause fragment"
        return "MEDIUM", "phrase from condition-source column"

    if wc > LONG_PHRASE_WORDS:
        return "LOW", "long phrase, likely a clause fragment"
    if wc <= 1:
        return "MEDIUM", "single-word candidate — confirm it is a real concept"
    return "MEDIUM", f"phrase from {label.lower()}-source column"


def _conf_rank(conf: str) -> int:
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(conf, 0)


def _write_json(path: Path, data: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract high-quality candidate NER terminology from the drug CSV (JSON output).")
    parser.add_argument("--input", required=True, type=Path, help="Path to the Sanofi drug CSV.")
    parser.add_argument("--outdir", type=Path, default=Path("data/terminology"))
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    seen: dict[tuple[str, str], dict] = {}

    with args.input.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        available = set(reader.fieldnames or [])
        for row in reader:
            drug = normalize(row.get("drug_name", "") or "")
            for label, columns in LABEL_SOURCE_COLUMNS.items():
                for col in columns:
                    if col not in available:
                        continue
                    cell = row.get(col, "") or ""
                    if is_empty(cell):
                        continue

                    proposals: list[tuple[str, bool]] = []
                    if label == "CONDITION":
                        for cue in extract_condition_cues(cell):
                            proposals.append((cue, True))
                        for p in candidate_phrases(cell):
                            if word_count(p) <= LONG_PHRASE_WORDS:
                                proposals.append((p, False))
                    else:
                        for p in candidate_phrases(cell):
                            proposals.append((p, False))

                    for phrase, is_cue in proposals:
                        norm = phrase.lower()
                        key = (label, norm)
                        if key in seen:
                            continue
                        confidence, reason = assess(label, phrase, is_cue)
                        seen[key] = {
                            "label": label,
                            "concept": phrase,
                            "normalized_concept": norm,
                            "source_drug": drug,
                            "source_column": col,
                            "confidence": confidence,
                            "review_reason": reason,
                        }

    rows = sorted(
        seen.values(),
        key=lambda r: (r["label"], -_conf_rank(r["confidence"]), r["normalized_concept"]),
    )

    # Combined + per-label candidate JSON files.
    _write_json(args.outdir / "candidates.json", rows)

    summary: dict[str, dict[str, int]] = {}
    for label in LABEL_SOURCE_COLUMNS:
        label_rows = [r for r in rows if r["label"] == label]
        summary[label] = {
            "total": len(label_rows),
            "HIGH": sum(1 for r in label_rows if r["confidence"] == "HIGH"),
            "MEDIUM": sum(1 for r in label_rows if r["confidence"] == "MEDIUM"),
            "LOW": sum(1 for r in label_rows if r["confidence"] == "LOW"),
        }
        _write_json(args.outdir / f"{label.lower()}_candidates.json", label_rows)

    # Pre-populated review sheet (JSON). Reviewer fills review_status / reviewed_label / notes.
    reviewed = args.outdir / "reviewed_terminology.json"
    review_rows = [
        {
            "label": r["label"],
            "concept": r["concept"],
            "normalized_concept": r["normalized_concept"],
            "source_drug": r["source_drug"],
            "source_column": r["source_column"],
            "review_status": "",          # APPROVED / REJECTED / RELABEL
            "reviewed_label": "",          # final label if APPROVED/RELABEL
            "notes": r["review_reason"],   # seed with the extractor's reason
        }
        for r in rows
    ]
    _write_json(reviewed, review_rows)

    print("Stage A — candidate terminology (JSON, FOR REVIEW, not training data):")
    for label, c in summary.items():
        print(f"  {label:<10} total={c['total']:<5} HIGH={c['HIGH']:<4} MEDIUM={c['MEDIUM']:<4} LOW={c['LOW']}")
    print(f"\n  Combined      -> {args.outdir / 'candidates.json'}")
    print(f"  Review sheet  -> {reviewed}")
    print("\nNext: review candidates, set review_status (APPROVED/REJECTED/RELABEL) and "
          "reviewed_label. Query generation uses APPROVED concepts only.")


if __name__ == "__main__":
    main()
