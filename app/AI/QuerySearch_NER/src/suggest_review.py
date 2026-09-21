"""
suggest_review.py — Stage A review helper (Option C: pre-suggestion pass).

Reads the candidate terminology (data/terminology/candidates.json) and writes
SUGGESTED review decisions into data/terminology/reviewed_terminology.json.

It does the obvious ~80% so human review is small. Final decisions are yours.

Suggestion outcomes written to `review_status`:
    APPROVED   genuine concept with the right label (reviewed_label = label)
    RELABEL    genuine concept, wrong label       (reviewed_label = corrected)
    REJECTED   not a useful NER concept           (reviewed_label = "")
    ""         UNSURE / borderline — left blank for manual review

KEY GUARDRAIL (per instruction):
    Morphology alone is NOT authoritative. Words like "failure", "infection",
    or "syndrome" are only signals. Unless a concept matches a curated exact-term
    lexicon, borderline cases are left UNSURE rather than force-relabeled.

Rules implemented:
  REJECT  numeric/dose/lab fragments; numeric age thresholds (age >65 years);
          monitoring/instruction prose; exact drug/brand/generic names (from CSV);
          "symptoms of X" wrappers; long clause fragments.
  APPROVE the 16 HIGH condition cues -> CONDITION;
          elderly / paediatric / pediatric -> CONDITION;
          exact hits in the curated SYMPTOM lexicon -> SYMPTOM.
  RELABEL only via curated exact-term lexicons:
          curated DISEASE terms -> DISEASE (regardless of source column);
          curated SYMPTOM terms -> SYMPTOM (regardless of source column).
  UNSURE  everything else (including morphology-only signals), with a note.

This never edits concept / source_drug / source_column. It only sets
review_status, reviewed_label, and appends a reason to notes.

Usage:
    python -m src.suggest_review \
        --candidates data/terminology/candidates.json \
        --drug-csv "sample_drug_data_sanofi (1).csv" \
        --output data/terminology/reviewed_terminology.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

VALID_LABELS = {"DISEASE", "SYMPTOM", "CONDITION"}

# --- CONDITION: word-based states approved for V1 ---------------------------
CONDITION_APPROVE = {
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
}

# Multi-word canonical condition cues used for the CONTAINMENT rule (safe to
# substring-match because they are specific; bare "renal"/"hepatic" are NOT here).
CONDITION_CANONICAL_MULTIWORD = [
    "renal impairment",
    "renal insufficiency",
    "hepatic impairment",
    "hepatic insufficiency",
    "impaired renal function",
    "impaired hepatic function",
    "pregnancy",
    "pregnant",
    "lactation",
    "lactating",
    "breast-feeding",
    "breastfeeding",
    "elderly",
    "paediatric",
    "pediatric",
]

# --- Curated exact-term lexicons (authoritative for RELABEL/APPROVE) --------
# Expanded conservatively from the ACTUAL candidate data. Every term here is a
# named diagnosis or a genuine patient complaint. Ambiguous items (e.g.
# "cardiac disease", "cognitive disorders", "allergic reactions", "fluid
# retention") are deliberately NOT included — they stay UNSURE for manual review.
DISEASE_TERMS = {
    # cardiometabolic / cardiovascular
    "hypertension",
    "essential hypertension",
    "mild to moderate hypertension",
    "atrial fibrillation",
    "atrial flutter",
    "myocardial infarction",
    "acute coronary syndrome",
    "unstable angina",
    "angina",
    "hypertensive crisis",
    "heart failure",
    "cardiac failure",
    "ventricular fibrillation",
    "ventricular tachycardia",
    "supraventricular tachycardia",
    "sick sinus syndrome",
    "stroke",
    "transient ischemic attack",
    "peripheral neuropathy",
    "nephropathy",
    "deep vein thrombosis",
    "pulmonary embolism",
    # infections
    "meningitis",
    "acute bacterial meningitis",
    "urinary tract infection",
    "complicated urinary tract infections",
    "upper respiratory tract infection",
    "recurrent respiratory infections",
    "pneumonia",
    "community-acquired pneumonia and nosocomial pneumonia",
    "sinusitis",
    "pharyngitis",
    "nasopharyngitis",
    "conjunctivitis",
    "proctitis",
    "peritonitis",
    "capd related peritonitis",
    "complicated intra-abdominal infections",
    "complicated skin and soft tissue infections",
    # haematology / oncology
    "anaemia",
    "anemia",
    "thrombocytopenia",
    "neutropenia",
    "leukopenia",
    "breast cancer",
    "chronic gvhd",
    # renal / hepatic (as diagnoses, not treatment-state conditions)
    "renal failure",
    "acute renal failure",
    "respiratory failure",
    "severe respiratory failure",
    "hepatorenal syndrome",
    "melas syndrome",
    "stevens-johnson syndrome",
    "nephrotic syndrome",
    # endocrine / other
    "diabetes mellitus",
    "type 2 diabetes mellitus",
    "type ii diabetes mellitus",
    "asthma",
    "epilepsy",
    "insomnia",
    "multiple sclerosis",
    "rheumatoid arthritis",
    "atopic dermatitis",
    "moderate-to-severe atopic dermatitis",
    "seizures",
    "wolff-parkinson-white syndrome",
}

SYMPTOM_TERMS = {
    # pain complaints
    "headache",
    "abdominal pain",
    "back pain",
    "joint pain",
    "muscle pain",
    "muscle or bone pain",
    "bone pain",
    "chest pain",
    "pain",
    # respiratory
    "cough",
    "tickling cough",
    "non-productive tickling cough",
    "shortness of breath",
    "breathlessness",
    "dyspnoea",
    "dyspnea",
    "wheezing",
    "nasal congestion",
    # gastrointestinal
    "nausea",
    "vomiting",
    "diarrhoea",
    "diarrhea",
    "constipation",
    "flatulence",
    "dry mouth",
    "dryness of the mouth",
    "dysphagia",
    "loss of appetite",
    "anorexia",
    "metallic taste",
    "sores in the mouth",
    # general / constitutional
    "fatigue",
    "asthenia",
    "weakness",
    "lassitude",
    "malaise",
    "fever",
    "pyrexia",
    "chills",
    "rigors",
    "sweating",
    "restlessness",
    "sleepiness",
    "somnolence",
    "dizziness",
    "tremor",
    "intense thirst",
    "ravenous hunger",
    # skin
    "pruritus",
    "pruritus ani",
    "itching",
    "rash",
    "urticaria",
    "erythema",
    "redness",
    "dry skin",
    "hair loss",
    "alopecia",
    "flushing",
    "swelling",
    "oedema",
    "peripheral edema",
    "ankle swelling",
    "nail changes",
    # musculoskeletal / neuro
    "arthralgia",
    "myalgia",
    "stiffness",
    "leg cramps",
    "muscle weakness",
    "difficulty walking",
    "irritability",
    "agitation",
    "aggression",
    "anxiety",
    "hallucinations",
    "delusions",
    # cardiac sensations
    "palpitations",
    "tachycardia",
    "bradycardia",
    "irregular pulse",
    "rapid heart rate",
    # other complaints
    "visual impairment",
    "weight gain",
    "hematuria",
    "urinary frequency",
    "abdominal distension",
    "post haemorrhoidectomy pain",
    "post-haemorrhoidectomy pain",
}

# --- Reject signals ---------------------------------------------------------
INSTRUCTION_MONITORING = re.compile(
    r"\b(monitor|monitoring|administer|administered|blood test|blood tests|"
    r"perform|assess|inform|discontinue|recommended|caution|consult|"
    r"see section|refer to|take|store|dose|dosage|adjust)\b",
    re.IGNORECASE,
)
NUMERIC_AGE_THRESHOLD = re.compile(
    r"\bage\b.*\d|\d+\s*years|\byears? (?:and )?(?:older|above|of age)\b", re.IGNORECASE
)
# Wrapper / prose phrases that are not clean concepts (the underlying disease
# or symptom is the real concept, so reject the wrapper).
WRAPPER_PROSE = re.compile(
    r"^(symptoms of|signs of|signs and symptoms of|progressive symptoms of|"
    r"treatment of|secondary prevention of|support of|prevention of)\b"
    r"|\bsymptoms$|\bsigns$",
    re.IGNORECASE,
)
# Drug-class / pharmacology tokens that are not DISEASE/SYMPTOM/CONDITION.
DRUG_CLASS_TOKENS = {
    "glp-1", "sglt2", "dpp-4", "dpp-4 inhibitors or gliptins", "sulfonylurea",
    "glinide", "inhibitors or gliflozins", "receptor agonist", "ert",
    "non-betacytotropic oral antidiabetics", "pci", "cll", "mps i", "rrms",
    "stemi", "tia", "new mi", "recent mi", "st-elevation ami",
    "type 1", "type 2", "type 3", "type i", "type ii", "type iii",
    "physical exercise", "cancer surgery",
}
SYMPTOMS_OF_WRAPPER = WRAPPER_PROSE
UNIT_LAB = re.compile(
    r"\b(mg|ml|mcg|μg|ug|m2|m²|ml/min|uln|mmol|mg/l|/min|%)\b|[<>]\s*\d", re.IGNORECASE
)
LONG_PHRASE_WORDS = 6


# Canonicalization for CONDITION concepts: map any phrase CONTAINING one of
# these cues to the clean canonical concept. We keep the terminology bank as
# concepts, not sentences (per review rule). Order matters — most specific /
# multi-word cues first so "impaired renal function" wins over bare matches.
CONDITION_CANONICAL_MAP = [
    ("impaired renal function", "renal impairment"),
    ("impaired hepatic function", "hepatic impairment"),
    ("renal impairment", "renal impairment"),
    ("renal insufficiency", "renal impairment"),
    ("renal dysfunction", "renal impairment"),
    ("hepatic impairment", "hepatic impairment"),
    ("hepatic insufficiency", "hepatic impairment"),
    ("liver function", "hepatic impairment"),
    ("breast-feeding", "breast-feeding"),
    ("breastfeeding", "breast-feeding"),
    ("lactating", "lactation"),
    ("lactation", "lactation"),
    ("pregnant", "pregnancy"),
    ("pregnancy", "pregnancy"),
    ("trimester", "pregnancy"),
    ("elderly", "elderly"),
    ("geriatric", "elderly"),
    ("paediatric", "paediatric"),
    ("pediatric", "paediatric"),
    ("neonat", "paediatric"),
    ("dialysis", "dialysis"),
    ("hemodialysis", "dialysis"),
    ("haemodialysis", "dialysis"),
]


def canonical_condition(text: str) -> str | None:
    """Return the clean canonical CONDITION concept a phrase maps to, or None."""
    low = text.lower()
    for cue, canonical in CONDITION_CANONICAL_MAP:
        if cue in low:
            return canonical
    return None


def normalize(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:•\t\"'")


def load_drug_names(csv_path: Path) -> set[str]:
    """Build a lowercase set of drug/brand/generic name tokens from the CSV."""
    names: set[str] = set()
    if not csv_path or not csv_path.exists():
        return names
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for col in ("drug_name", "brand_name", "generic_name"):
                val = (row.get(col) or "").strip()
                if not val or val.upper() == "NA":
                    continue
                # Split on separators, strip trademark marks and suffixes.
                for part in re.split(r"[+/,]", val):
                    part = re.sub(r"[®™©]", "", part)
                    part = re.sub(r"\b(SR|XR|IP|r-DNA origin|Forte|SoloStar|Jr|Suspension|"
                                  r"Extended Release|Prolonged Release|Sustained Release)\b",
                                  "", part, flags=re.IGNORECASE)
                    part = normalize(part).lower()
                    if len(part) >= 3:
                        names.add(part)
    return names


def word_count(s: str) -> int:
    return len(s.split())


def suggest(entry: dict, drug_names: set[str]) -> tuple[str, str, str]:
    """Return (review_status, reviewed_label, reason)."""
    concept = entry["concept"]
    norm = entry.get("normalized_concept") or concept.lower()
    norm = norm.strip()
    low = norm
    src_label = entry["label"]

    # --- REJECT rules -------------------------------------------------------
    if UNIT_LAB.search(concept):
        return "REJECTED", "", "numeric/unit/lab fragment"
    if NUMERIC_AGE_THRESHOLD.search(concept):
        return "REJECTED", "", "numeric age threshold — handle as filter logic later"
    if INSTRUCTION_MONITORING.search(concept):
        return "REJECTED", "", "instruction/monitoring prose, not a concept"
    if WRAPPER_PROSE.search(concept):
        return "REJECTED", "", "wrapper/prose phrase — underlying concept is what matters"
    if norm in DRUG_CLASS_TOKENS:
        return "REJECTED", "", "drug-class / pharmacology / abbreviation token, not a concept"
    if norm in drug_names:
        return "REJECTED", "", "drug/brand/generic name, not an NER concept"
    if word_count(concept) > LONG_PHRASE_WORDS:
        return "REJECTED", "", "long clause fragment"

    # --- APPROVE: curated CONDITION states ----------------------------------
    if norm in CONDITION_APPROVE:
        if src_label == "CONDITION":
            return "APPROVED", "CONDITION", "curated condition state"
        return "RELABEL", "CONDITION", "curated condition state (source column differed)"

    # CONDITION containment: a short (non-prose) phrase that contains a canonical
    # multi-word condition cue is a modified form of a real condition
    # (e.g. "Severe renal impairment" -> "renal impairment"). Suggest APPROVE and
    # note the canonical form for the reviewer to normalize. Guarded to short
    # phrases only, so sentences / "renal failure and death" don't slip through.
    if word_count(concept) <= 4:
        for cue in CONDITION_CANONICAL_MULTIWORD:
            if cue in norm:
                return "APPROVED", "CONDITION", f"contains condition cue '{cue}' — consider normalizing to '{cue}'"

    # --- Curated exact-term lexicons (authoritative) ------------------------
    if norm in DISEASE_TERMS:
        if src_label == "DISEASE":
            return "APPROVED", "DISEASE", "curated disease term"
        return "RELABEL", "DISEASE", "curated disease term (source column differed)"

    if norm in SYMPTOM_TERMS:
        if src_label == "SYMPTOM":
            return "APPROVED", "SYMPTOM", "curated symptom term"
        return "RELABEL", "SYMPTOM", "curated symptom term (source column differed)"

    # --- REJECT obvious non-concepts in the noisy CONDITION prose columns ----
    # (contraindications / warnings_precautions are free text). These rules are
    # structural, not semantic: abbreviations, sentence/prose, and long phrases.
    if src_label == "CONDITION":
        # All-caps / abbreviation tokens (AGEP, AIH, ATL, AUC, ARDS, ...).
        if re.fullmatch(r"[A-Z0-9\-]{2,6}", concept):
            return "REJECTED", "", "abbreviation / acronym, not a condition concept"
        # Sentence/prose signals (verbs, clause markers, header language).
        if re.search(
            r"\b(is|are|was|were|may|must|should|can|cause|causes|caused|raises|"
            r"crosses|removed|reported|occur|occurs|exposed|contraindicated|"
            r"avoid|abstain|change over|appear|appearance|available data|"
            r"black box|warning|precaution)\b",
            low,
        ):
            return "REJECTED", "", "prose/sentence, not a clean condition concept"
        # Long noun phrases from prose columns.
        if word_count(concept) > 4:
            return "REJECTED", "", "long phrase from prose column, not a clean concept"

    # --- UNSURE: morphology signals are advisory only -----------------------
    morph = None
    if re.search(r"\b(cancer|carcinoma|syndrome|failure|infection|infarction|"
                 r"fibrillation|meningitis|arrhythmia|stenosis)\b", low):
        morph = "morphology suggests DISEASE — confirm manually"
    reason = "borderline — manual review needed"
    if morph:
        reason = morph
    return "", "", reason


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-suggest review decisions for candidate terminology (Option C).")
    parser.add_argument("--candidates", type=Path, default=Path("data/terminology/candidates.json"))
    parser.add_argument("--drug-csv", type=Path, default=Path("sample_drug_data_sanofi (1).csv"))
    parser.add_argument("--output", type=Path, default=Path("data/terminology/reviewed_terminology.json"))
    args = parser.parse_args()

    with args.candidates.open("r", encoding="utf-8") as f:
        candidates = json.load(f)

    drug_names = load_drug_names(args.drug_csv)

    out_rows: list[dict] = []
    counts = {"APPROVED": 0, "RELABEL": 0, "REJECTED": 0, "UNSURE": 0}

    for entry in candidates:
        status, reviewed_label, reason = suggest(entry, drug_names)
        if reviewed_label and reviewed_label not in VALID_LABELS:
            reviewed_label = ""  # safety
        counts["UNSURE" if status == "" else status] += 1

        base_note = entry.get("review_reason", "")
        note = f"[suggested: {status or 'UNSURE'}] {reason}"
        if base_note:
            note = f"{note} | extractor: {base_note}"

        # Canonicalize: keep the CONCEPT, not the sentence. For APPROVED CONDITION
        # rows whose phrase wraps a canonical cue, set normalized_concept to the
        # clean concept (original `concept` is left untouched for audit).
        normalized_concept = entry.get("normalized_concept", entry["concept"].lower())
        if status == "APPROVED" and reviewed_label == "CONDITION":
            canon = canonical_condition(entry["concept"])
            if canon and canon != normalized_concept:
                note = f"{note} | normalized '{normalized_concept}' -> '{canon}'"
                normalized_concept = canon

        out_rows.append({
            "label": entry["label"],
            "concept": entry["concept"],
            "normalized_concept": normalized_concept,
            "source_drug": entry.get("source_drug", ""),
            "source_column": entry.get("source_column", ""),
            "review_status": status,        # "" == UNSURE, awaiting your decision
            "reviewed_label": reviewed_label,
            "notes": note,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(out_rows, f, ensure_ascii=False, indent=2)

    total = len(out_rows)
    print("Suggestion pass complete (final decisions are yours):")
    print(f"  APPROVED : {counts['APPROVED']}")
    print(f"  RELABEL  : {counts['RELABEL']}")
    print(f"  REJECTED : {counts['REJECTED']}")
    print(f"  UNSURE   : {counts['UNSURE']}  <- manual review needed (review_status is blank)")
    print(f"  TOTAL    : {total}")
    print(f"\n  Written -> {args.output}")
    print("  Review UNSURE rows and correct any wrong suggestions, then we proceed.")


if __name__ == "__main__":
    main()
