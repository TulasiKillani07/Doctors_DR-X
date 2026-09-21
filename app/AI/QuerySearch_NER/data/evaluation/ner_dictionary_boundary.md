# NER → Dictionary / Entity Resolution — layer responsibility boundary

Purpose: decide what NER must do vs what the downstream Dictionary / Entity
Resolution layer should own, so we don't force the NER model to be a full medical
ontology classifier. This is an architecture note, not a code change.

## The decisive evidence: span is right, only the label is wrong

Probe (preprocess -> NER on models/model-best), for the known failing concepts:

| Query | NER span found? | NER label | Correct type |
|---|---|---|---|
| show medicines for **hypertension** | ✅ "hypertension" | SYMPTOM ❌ | DISEASE |
| treatment for **pneumonia** with fever | ✅ "pneumonia" | SYMPTOM ❌ | DISEASE |
| drugs for **migraine** and nausea | ✅ "migraine" | SYMPTOM ❌ | DISEASE |
| what is suitable for **obesity** during pregnancy | ✅ "obesity" | SYMPTOM ❌ | CONDITION |
| medicine for **tuberculosis** | ✅ "tuberculosis" | SYMPTOM ❌ | DISEASE |

In EVERY failing case the NER correctly **located the medical span**. Only the
**type label** is wrong. Span detection (the hard part) succeeds; type assignment
(which a dictionary can provide authoritatively) is the only failure.

## Proposed responsibility split

```
Raw query
   ↓
Preprocessing            how the query is written (casing/punct/whitespace)
   ↓
NER                      FIND the medical span(s) in the query
   ↓  (span, provisional label)
Dictionary / Entity      WHAT canonical concept + authoritative type is this span?
Resolution               - exact / alias / fuzzy match against controlled vocab
   ↓                       - the dictionary's type OVERRIDES the NER label
Canonical concept + type
   ↓
Intent / Field mapping / Search
```

### NER's job (span-finding)
- Detect that a span of the query is a medical concept and roughly which of
  DISEASE / SYMPTOM / CONDITION it is.
- Be robust at BOUNDARIES (helped by preprocessing) and at RECALL (find the span).
- It does NOT need to perfectly classify every unseen term's ontology class.

### Dictionary / Entity Resolution's job (authoritative typing)
- Map the detected span to a canonical concept via exact / alias / fuzzy match.
- When the dictionary knows the concept, its TYPE is authoritative and overrides
  the NER label. e.g. NER says "hypertension"=SYMPTOM; dictionary knows
  hypertension = DISEASE -> final = DISEASE.
- This makes concept-specific NER label errors harmless AS LONG AS the span was
  found and the concept is in the dictionary.

## What this means for the current errors

- hypertension / pneumonia / migraine / tuberculosis / obesity: NER finds the
  span; a downstream dictionary containing these concepts fixes the type. No NER
  retraining required to make Global Search correct on them.
- The residual risk shifts to: (a) does NER FIND the span (recall), and (b) is the
  concept IN the dictionary. Both are more tractable/controllable than forcing NER
  to be an ontology classifier.

## Open questions to decide before building the dictionary layer

1. Dictionary source of truth: the same Sanofi-derived controlled vocabulary +
   any authoritative disease/condition list. (This is later-phase per the plan.)
2. Override policy: does the dictionary ALWAYS override NER type when it recognizes
   the concept, or only when confidence is high?
3. What happens when NER finds a span the dictionary does NOT know? (keep NER label
   as a fallback, or mark as unresolved for the LLM/response layer.)
4. What happens when the dictionary knows a concept NER did NOT tag? (dictionary
   can also run as a scanner; NER + dictionary are complementary recall sources.)

## Follow-up findings (larger probe run)

**A. Preprocessing whitespace — NOT a bug (false alarm).** Terminal output
appeared to show "pneumoniain" / "duringpregnancy", but character-level checks
confirm `normalize_query` preserves spaces correctly ("pneumonia in elderly
patients", "during pregnancy"). The artifact was PowerShell line-wrapping in the
console, not the preprocessor. No fix needed.

**B. NER type is CONTEXT-SENSITIVE, not a fixed per-concept error.**
  - tuberculosis -> DISEASE in "with fever during pregnancy", "in immunocompromised
    patients"; but SYMPTOM in bare "medicine for tuberculosis".
  - asthma -> DISEASE in "with fever"; but SYMPTOM in "and shortness of breath".
  This is further reason NOT to patch individual concepts with ad-hoc training
  sentences. The provisional label genuinely varies with surrounding context.

**C. Gate-1 limitation is real and must be respected.**
  hypertension / pneumonia / migraine / obesity are OUTSIDE the governed V1
  vocabulary. Under Gate 1 (Tier A only), the dictionary MUST return UNRESOLVED
  for them — it must NOT relabel them to DISEASE using outside medical knowledge.
  Fixing them is a TERMINOLOGY decision (add to governed vocab), not something the
  resolver may do implicitly.

**D. Span recall is NOT yet proven sufficient.** The probe shows spans are usually
  found, but we have NOT measured span RECALL systematically. Measure it
  separately before relying on "NER finds the span" as an architectural guarantee.

## Recommendation

For V1 NER: treat the model as a **span finder with a provisional type**, not a
final ontology classifier. Do NOT retrain to chase concept-specific type errors.
Address type authority in the Dictionary / Entity Resolution layer, where a
controlled vocabulary can be corrected/audited deterministically. Revisit NER
training only if SPAN RECALL (not type) proves insufficient.
