# Semantic Error Catalogue — QuerySearch NER (V1 baseline)

Scope: genuine **semantic classification** errors that runtime preprocessing does
NOT fix. Preprocessing (lowercase, punctuation/whitespace normalization) solves
surface-form problems only; the errors below are about the model assigning the
wrong label to a correctly-identified span. These are the scoped input for a
future **semantic-focused** NER iteration — no training changes are made now.

Baseline: `models/v1/model-best` (Overall F1 0.881 on V1-style test).
All probes below were run through the production flow: **preprocess -> NER**
(so casing/punctuation are already normalized; the errors are purely semantic).

## CORRECTION (diagnosis update)

An earlier version of this file claimed hypertension and pneumonia were *seen*
DISEASE concepts that the model learned incorrectly. **That was wrong.** A
read-only diagnosis (src/diagnose_concept.py + bank/audit inspection) established:

- hypertension and pneumonia are **NOT in the terminology bank** (neither DISEASE,
  SYMPTOM, nor CONDITION).
- They occur **0 times** in the V1 training data.
- They were **REJECTED during terminology review**
  (`reviewed_terminology_corrected.json`, note: "not sufficiently well-defined as
  a V1 DISEASE") — every variant, from both DISEASE and SYMPTOM source columns.

Therefore their SYMPTOM predictions are **unseen-concept generalization behavior**,
exactly like migraine / tuberculosis / obesity — NOT a seen-concept learning bug.

## All five are the same phenomenon: unseen terms default to SYMPTOM

| Query (normalized) | Concept | Model label | Intended | In bank? | In training? |
|---|---|---|---|---|---|
| treatment for hypertension | hypertension | SYMPTOM | DISEASE | ❌ rejected | 0× |
| treatment for pneumonia | pneumonia | SYMPTOM | DISEASE | ❌ rejected | 0× |
| drugs for migraine | migraine | SYMPTOM | DISEASE | ❌ unseen file | 0× |
| drugs for tuberculosis | tuberculosis | SYMPTOM | DISEASE | ❌ unseen file | 0× |
| what is suitable for obesity | obesity | SYMPTOM | CONDITION | ❌ unseen file | 0× |

Probes confirm the SYMPTOM prediction is **stable across contexts** (treatment for /
medicine for / X with <symptom>), consistent with an untrained concept defaulting
to SYMPTOM rather than context-driven confusion.

## Previously-suspect items now CORRECT under preprocess -> NER

These were failing on raw input but are handled correctly once normalized —
so they are NOT semantic errors; they were surface-form issues:

| Query (normalized) | Concept | Model label | Correct | Status |
|---|---|---|---|---|
| medicine for adolescents | adolescents | CONDITION | CONDITION | ✅ correct |
| ...patients undergoing dialysis | dialysis | CONDITION | CONDITION | ✅ correct |
| ...help with palpitations | palpitations | SYMPTOM | SYMPTOM | ✅ correct |
| treatment for gout | gout | DISEASE | DISEASE | ✅ correct (unseen, generalized well) |

## Patterns / root-cause hypotheses (for the future iteration)

0. **Two separate questions** (do not conflate):
   (a) TERMINOLOGY decision — should hypertension/pneumonia be approved DISEASE
       concepts in the bank at all? They were deliberately rejected in V1.
   (b) GENERALIZATION — can the model label *unseen* disease names as DISEASE?
       migraine / tuberculosis / obesity stay in unseen_eval_concepts.json as the
       honest held-out test and must NOT be added to training.
1. **Unseen DISEASE -> SYMPTOM default** (all five). The model's
   fallback for unfamiliar single-word medical terms skews SYMPTOM.
3. **Unseen CONDITION -> SYMPTOM/other** (obesity). The 8-concept CONDITION
   vocabulary is thin; unseen conditions generalize poorly.

## Root-cause evidence (src/analyze_label_bias.py, read-only, on data/training_v1)

The SYMPTOM bias for unseen concepts has a concrete, data-driven cause:

**1. Single-word morphology strongly associates with SYMPTOM in training.**
   - DISEASE: 41 concepts, only **13 single-word** (32%); avg length **22.8** chars;
     dominated by long/technical multi-word names (e.g. "complicated urinary tract
     infections", "acid α-glucosidase deficiency").
   - SYMPTOM: 44 concepts, **22 single-word** (50%); avg length **13.4** chars;
     short everyday words (headache, nausea, cough, fever, dizziness).
   - So an unseen SHORT single word (hypertension, pneumonia, migraine, obesity)
     looks morphologically far more like a SYMPTOM than like the model's DISEASE
     examples. This is the primary driver.

**2. Trigger-context words overlap but lean the wrong way for short queries.**
   - Strong DISEASE-only triggers: "treatment for", "used for", "indicated",
     "prescribed", "first line", "options for treating".
   - Strong SYMPTOM-only triggers: "relieve", "relief", "help/helps with",
     "something for", "anything for", "remedy", "manage".
   - Shared/ambiguous: "for", "what", "drugs", "medicine(s)", "to", "how", "can".
   - "medicine for X" leans SYMPTOM (medicine D7 / S19); "treatment for X" leans
     DISEASE (D39 / S7). So the exact probe phrasing matters, but with a short
     unseen word the morphology bias (point 1) dominates and pushes SYMPTOM.

**Initial hypothesis (morphology drives the error) — REFUTED by controlled test.**

## Causality test (src/diagnose_morphology.py, read-only) — morphology is NOT the cause

Held context constant (4 fixed templates), varied only the concept, grouped by
label x word-shape. Results:

- SEEN concepts: **100%** accuracy in every cell — incl. seen short single-word
  DISEASE (anaemia, angina, stroke, sinusitis, leukopenia, thrombocytopenia).
  => short-single-word does NOT cause the error for trained concepts.
- PROBE (unseen, throwaway — NOT migraine/tuberculosis/obesity):
    - unseen DISEASE single-word: **0.90** (measles, malaria, cholera, eczema,
      leukaemia mostly -> DISEASE correctly)
    - unseen DISEASE multi-word: **0.67** (the total failure was "parkinsons
      disease" -> SYMPTOM, a MULTI-word term)
    - unseen SYMPTOM single & multi: 1.0

If morphology drove the bias, unseen SHORT diseases would fail and MULTI-word
would pass. The OPPOSITE occurred. **Morphology (word-shape) is not the driver.**

**Revised conclusion (stated at the confidence the evidence supports):**

The remaining DISEASE->SYMPTOM errors are **concept-specific unseen-concept
generalization failures.** The model generalizes correctly to many unseen short
diseases (measles/malaria/cholera/eczema ~0.90) but fails on a specific subset
(hypertension, pneumonia, migraine, tuberculosis). 

What is ESTABLISHED:
  - Word-shape (short single word) is NOT the cause (controlled test above).
  - The failures are specific to certain concepts, not a systematic rule.
  - "Add more short single-word diseases" would NOT reliably fix this (those
    already generalize at ~0.90).

What is a HYPOTHESIS, not verified:
  - Static-vector (en_core_web_md) similarity may explain why certain unseen
    words inherit SYMPTOM vs DISEASE. This is plausible but has NOT been
    experimentally confirmed here; do not treat it as a proven cause.

Implication: forcing the NER model to correctly classify every unseen medical
term's semantic class may be the wrong goal. The downstream Dictionary / Entity
Resolution layer can be the authority on "what canonical concept / type is this
span," while NER's job is to reliably FIND the medical span. See
data/evaluation/ner_dictionary_boundary.md.

## Candidate remedies (NOT applied yet — for discussion)

- Add more DISEASE training contexts that place diseases next to symptoms, so the
  model learns to keep the disease as DISEASE (targets hypertension/pneumonia).
- Broaden CONDITION training vocabulary/phrasing (targets obesity-type unseen).
- Do NOT use aggressive surface augmentation — the controlled experiment showed
  it regresses this small model (Overall 0.881 -> 0.776 on identical data).
- Consider whether some of these (migraine, tuberculosis) are acceptable unseen-
  generalization limits rather than fixable without adding them to the bank.

## What is explicitly out of scope for the surface/preprocessing layer

- Casing, punctuation, whitespace, trailing "?" — all handled by `src/preprocess.py`.
- Entity boundary trimming (e.g. dropping trailing "?") — handled by preprocessing.
