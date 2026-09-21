# Annotation Guidelines — QuerySearch NER

These guidelines define how to annotate **doctor-style medical search queries**
for the custom NER model. This model is the first layer of the larger
QuerySearch understanding pipeline; its only job is to recognize open-ended
medical concepts in queries.

Keep annotations consistent across people and over time by following these rules.

> Labels are defined in `config/labels.py`. Update that file first if the schema
> ever changes, then update this document.

## 1. What we annotate

We annotate spans in short, natural-language search queries a doctor might type,
such as:

- "Suggest drugs for breast cancer during pregnancy"
- "Which drugs are contraindicated during pregnancy?"
- "Drugs for abdominal pain"
- "Safe medication in renal impairment"

We only tag spans that clearly belong to one of the three labels. Everything else
(verbs, question words, filler like "suggest", "which drugs are") is left untagged.

We do **not** tag drug names, brands, manufacturers, dosage forms, or routes here.
Those are handled by the dictionary layer in a later phase.

## 2. Entity labels

| Label       | Meaning                                                         | Examples |
|-------------|-----------------------------------------------------------------|----------|
| `DISEASE`   | A diagnosed illness / pathology that is being treated           | breast cancer, asthma, hypertension, diabetes, rheumatoid arthritis |
| `SYMPTOM`   | A symptom or complaint the patient experiences                  | abdominal pain, headache, cough, fever, nausea |
| `CONDITION` | A physiological state / context that affects drug choice but is not itself the illness being treated | pregnancy, lactation, renal impairment, hepatic impairment, elderly, pediatric |

## 3. DISEASE vs CONDITION (the key distinction)

This is the hardest and most important boundary. Use this test:

- **DISEASE** = *what is being treated*. It's a named illness or pathology.
  The doctor is usually looking for drugs **for** it.
  - "drugs for **breast cancer**" → breast cancer = DISEASE
  - "treatment of **asthma**" → asthma = DISEASE

- **CONDITION** = *the context or state the patient is in* that modifies which
  drug is safe/appropriate. It is not the thing being cured.
  - "safe during **pregnancy**" → pregnancy = CONDITION
  - "dose in **renal impairment**" → renal impairment = CONDITION
  - "medication for **elderly** patients" → elderly = CONDITION

Rule of thumb: if removing the term still leaves a complete "treat X" target,
it's probably a CONDITION modifier. If the term *is* the treatment target, it's a
DISEASE.

Mixed example — "Suggest drugs for breast cancer during pregnancy":
- breast cancer → DISEASE (what we're treating)
- pregnancy → CONDITION (the context that constrains the choice)

## 4. SYMPTOM vs DISEASE

- A **symptom** is what the patient feels/reports; a **disease** is a diagnosis.
  - "abdominal pain" → SYMPTOM
  - "peptic ulcer" → DISEASE
- If a query names a well-known complaint phrase ("abdominal pain",
  "lower back pain", "shortness of breath"), tag the whole phrase as SYMPTOM.
- If a term can be read as both, prefer DISEASE when it names a diagnosis,
  SYMPTOM when it describes a felt complaint.

## 5. Span boundary rules

- **Tag the full meaningful phrase, not just the head noun.**
  - "rheumatoid arthritis" → one DISEASE span (not just "arthritis").
  - "renal impairment" → one CONDITION span.
  - "shortness of breath" → one SYMPTOM span.
- **Do not include leading/trailing filler**, articles, possessives, or
  prepositions unless they are part of the canonical name.
  - In "safe during pregnancy", tag only `pregnancy`, not "during pregnancy".
- **Match exact character offsets** — spans must align to real substrings of the
  query. No overlapping spans.
- One query can contain zero, one, or several entities of different labels.

## 6. Ambiguity & edge cases

- If unsure, flag the example for review rather than guessing.
- Be consistent: once you make a boundary decision, apply it everywhere.
- When DISEASE vs CONDITION is genuinely ambiguous, prefer the reading implied by
  the query intent (what is being treated vs the patient's context).

## 7. Annotation format

Annotations are stored as **JSONL** (one JSON object per line) in this folder,
e.g. `queries.jsonl`. Each line:

```json
{"text": "Suggest drugs for breast cancer during pregnancy", "entities": [[18, 31, "DISEASE"], [39, 48, "CONDITION"]]}
```

- `text`: the raw query string.
- `entities`: a list of `[start_char, end_char, LABEL]` triples using Python-style
  character offsets (end exclusive), matching spaCy's expectations.

`src/convert.py` turns this JSONL into spaCy `.spacy` binary files for training,
and warns on unknown labels or misaligned spans.
