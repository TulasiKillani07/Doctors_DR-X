"""
diagnose_morphology.py — READ-ONLY controlled test of whether word-shape
(short single word) CAUSES the DISEASE->SYMPTOM error, vs. it being driven by
train membership / lexical patterns.

Design: hold the query CONTEXT constant (a fixed set of templates) and vary only
the concept, grouped by (label x word-shape). Compare accuracy across cells.

Two concept pools:
  SEEN  = concepts actually in the V1 training bank (model was trained on them).
  PROBE = held-out real concepts NOT in the bank and NOT the reserved unseen-eval
          concepts (migraine/tuberculosis/obesity). These are a THROWAWAY probe
          used only in this diagnostic; they are NOT added to any bank or training.

Key comparisons:
  - SEEN DISEASE single-word: if the model gets these RIGHT, then "short single
    word" alone does NOT cause the error -> train membership dominates.
  - PROBE DISEASE single-word vs PROBE DISEASE multi-word: does the unseen error
    rate depend on word-shape? (isolates morphology effect for UNSEEN terms)

Changes nothing. Loads models/model-best and runs preprocess->NER.

Usage:
    python -m src.diagnose_morphology --model models/model-best
"""

from __future__ import annotations

import argparse
from pathlib import Path

import spacy

from src.preprocess import normalize_query

# Context templates held constant across all concepts.
TEMPLATES = ["treatment for {X}", "medicine for {X}", "drugs for {X}", "what is used for {X}"]

# SEEN concepts (in the V1 bank) grouped by label x shape.
SEEN = {
    ("DISEASE", "single"): ["anaemia", "angina", "stroke", "sinusitis", "conjunctivitis",
                             "leukopenia", "thrombocytopenia"],
    ("DISEASE", "multi"): ["breast cancer", "acute renal failure", "respiratory failure",
                           "complicated urinary tract infections"],
    ("SYMPTOM", "single"): ["headache", "nausea", "fever", "dizziness",
                            "vomiting", "fatigue"],
    ("SYMPTOM", "multi"): ["abdominal pain", "bone pain", "muscle weakness"],
}

# PROBE concepts: real terms, NOT in bank, NOT the reserved unseen-eval set.
# Throwaway diagnostic only. Deliberately excludes migraine/tuberculosis/obesity.
PROBE = {
    ("DISEASE", "single"): ["measles", "malaria", "cholera", "eczema", "leukaemia"],
    ("DISEASE", "multi"): ["parkinsons disease", "coronary artery disease",
                           "inflammatory bowel disease"],
    ("SYMPTOM", "single"): ["itchiness", "wheeze", "bloating", "chills"],
    ("SYMPTOM", "multi"): ["chest tightness", "muscle cramps"],
}


def predict_label(nlp, concept: str, template: str) -> str | None:
    """Return the predicted label for the concept span, or None if not detected."""
    raw = template.format(X=concept)
    pre = normalize_query(raw)
    doc = nlp(pre.normalized)
    cl = concept.lower()
    for ent in doc.ents:
        if ent.text.lower() == cl:
            return ent.label_
    # partial: any ent overlapping the concept
    for ent in doc.ents:
        if cl in ent.text.lower() or ent.text.lower() in cl:
            return ent.label_ + "*"
    return None


def eval_pool(nlp, pool: dict) -> dict:
    results = {}
    for (label, shape), concepts in pool.items():
        correct = 0
        total = 0
        detail = []
        for c in concepts:
            preds = [predict_label(nlp, c, t) for t in TEMPLATES]
            # majority prediction across the fixed templates
            hit = sum(1 for p in preds if p == label)
            total += len(TEMPLATES)
            correct += hit
            # dominant prediction
            from collections import Counter
            dom = Counter(str(p) for p in preds).most_common(1)[0][0]
            detail.append(f"{c}: {dom} ({hit}/{len(TEMPLATES)} correct)")
        results[(label, shape)] = {
            "accuracy": round(correct / total, 3) if total else 0.0,
            "n_concepts": len(concepts),
            "detail": detail,
        }
    return results


def print_results(title, res):
    print(f"\n================ {title} ================")
    for (label, shape), r in res.items():
        print(f"\n  {label} / {shape}-word  — label-accuracy {r['accuracy']} "
              f"(over {r['n_concepts']} concepts x {len(TEMPLATES)} templates)")
        for d in r["detail"]:
            print(f"    {d}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only morphology causality test.")
    parser.add_argument("--model", type=Path, default=Path("models/model-best"))
    args = parser.parse_args()

    nlp = spacy.load(args.model)

    seen_res = eval_pool(nlp, SEEN)
    probe_res = eval_pool(nlp, PROBE)

    print_results("SEEN concepts (in V1 bank) — tests train-membership effect", seen_res)
    print_results("PROBE concepts (unseen, throwaway) — tests morphology effect on UNSEEN", probe_res)

    print("\n================ INTERPRETATION GUIDE ================")
    print("  If SEEN DISEASE/single accuracy is HIGH: short-single-word alone does")
    print("    NOT cause the error; train membership dominates.")
    print("  If PROBE DISEASE/single << PROBE DISEASE/multi accuracy: morphology")
    print("    (short single word) DOES drive the unseen SYMPTOM bias.")
    print("  If PROBE DISEASE single AND multi both fail equally: the bias is about")
    print("    unseen-ness generally, not word-shape.")


if __name__ == "__main__":
    main()
