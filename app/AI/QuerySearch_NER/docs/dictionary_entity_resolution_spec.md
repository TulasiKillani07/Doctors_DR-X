# Dictionary + Entity Resolution — Design Spec (v0, pre-implementation)

Status: **DESIGN-REVIEW ARTIFACT — NOT an implementation contract.** No code yet.
This spec defines the layer that sits AFTER NER in the QuerySearch pipeline. The
six decisions below are **explicit review gates**: each must be locked one-by-one
before any code is written. The "v1 direction" entries are PROPOSED positions for
review, NOT assumptions to implement against.

Hard v1 constraint:
> **No semantic / vector matching in Entity Resolution for v1.**
> Introducing it now would make it impossible to tell whether an error originated
> in NER, normalization, fuzzy matching, or semantic retrieval. Keep the layer
> deterministic and auditable so failures are attributable to a single stage.

## Where this layer sits

```
Raw query
   ↓
Preprocessing          (done)  how the query is written
   ↓
NER (V1, frozen)       (done)  FIND medical span(s) + PROVISIONAL type
   ↓  spans: [(text, start, end, ner_label)]
Dictionary + Entity Resolution   (THIS SPEC)
   ↓  resolved: [(span, canonical_concept, type, source, confidence, status)]
Intent / Field mapping / Search  (later phases)
```

Architectural boundary (the two branches this layer must implement):

```
NER
  ├── span + provisional type
  ↓
Dictionary / Entity Resolution
  ├── governed match    → canonical concept + AUTHORITATIVE type
  └── no governed match → UNRESOLVED + provisional NER type (fallback)
  ↓
Resolved Entity Set
```

Established basis (from NER diagnosis): for the failing concepts, NER **found the
span correctly** and only the TYPE was wrong. So this layer's core value is
turning a correctly-located span into a **canonical concept + trusted type**.

## Review gates (lock one-by-one before coding)

| # | Decision | v1 direction (PROPOSED, for review) | Status |
|---|---|---|---|
| 1 | Vocabulary scope | Tier A controlled vocabulary only | open |
| 2 | Normalization | Canonical concept + explicit aliases | open |
| 3 | Matching | Exact → alias → threshold-gated fuzzy → unresolved | open |
| 4 | Type override | Exact/alias may override NER; fuzzy advisory only | open |
| 5 | Independent dictionary scan | Yes; evaluate false-positive behavior | open |
| 6 | UNRESOLVED handling | **Deliberately OPEN** until downstream intent/field mapping is designed | open |

No gate is locked yet. These are the review agenda, not decisions made.

## Core principle (refined)

The dictionary's type is **authoritative ONLY for concepts in our governed,
controlled vocabulary**. For spans that are not in the controlled vocabulary, the
dictionary does NOT invent a type; it returns an **unresolved** status and we fall
back to the NER provisional label (or defer to a later layer). We do not claim
authority over arbitrary medical terms until governance/source is defined.

---

## 1. Source of truth

Two tiers, kept separate and labeled by provenance:

| Tier | Source | Governs | Authority |
|---|---|---|---|
| **A. Controlled vocabulary** | Our reviewed `terminology_bank.json` (Sanofi-drug-sheet-derived, human-reviewed) + brand/manufacturer/dosage-form dictionary values | DISEASE / SYMPTOM / CONDITION concepts + closed dictionary entities (BRAND, MANUFACTURER, DOSAGE_FORM, ROUTE) | **Authoritative** — type overrides NER |
| **B. Extended medical vocabulary** (optional, later) | A curated external medical list (e.g. approved disease/condition lexicon) | broader medical terms not in the drug sheet | **Advisory** — only if we adopt a governance policy for it |

DECISION NEEDED:
- (1a) Do we include an extended medical vocabulary (Tier B) in v1 of this layer,
  or restrict to Tier A (controlled vocabulary) only? Recommendation: **Tier A only
  for v1**; add Tier B later with explicit governance.

Provenance is stored per entry (`source`) so every resolution is auditable.

---

## 2. Normalization (query span ↔ dictionary key)

Both the incoming span and the dictionary keys are normalized before matching,
reusing the SAME normalization as `src/preprocess.py` where possible:

- lowercase, collapse whitespace, strip punctuation (already done upstream)
- canonicalization to a preferred form, e.g.:
  - `renal insufficiency` / `impaired renal function` → `renal impairment`
  - `haemodialysis` / `hemodialysis` → `dialysis`
  - `breast-feeding` ↔ `breastfeeding`
- these canonical maps ALREADY EXIST in `finalize_terminology.py`
  (CONDITION_CANONICAL) — reuse them as the resolution normalization table.

DECISION NEEDED:
- (2a) Is normalization symmetric (apply to both query span and dictionary keys)
  or do we pre-expand the dictionary with all known aliases? Recommendation:
  **store canonical + alias list per concept; match normalized span against both.**

---

## 3. Matching strategy (tiered, most-precise-first)

```
span
 ↓  1. EXACT match on canonical form            (highest confidence)
 ↓  2. ALIAS match (known synonyms/spellings)   (high)
 ↓  3. FUZZY match (edit distance / token)      (medium; threshold-gated)
 ↓  4. no match                                 → UNRESOLVED
```

- Exact/alias: deterministic, auditable, preferred.
- Fuzzy: gated by a similarity threshold; used for typos/minor variants
  (e.g. `hypertention` → `hypertension`). Must log the match + score.
- Semantic/vector matching: EXPLICITLY OUT OF SCOPE for v1 (revisit later).

DECISIONS NEEDED:
- (3a) Fuzzy match algorithm + threshold (e.g. Levenshtein ratio ≥ 0.9?).
- (3b) Do we allow fuzzy matching on short concepts (risk: "gout" ~ "goute")?
  Recommendation: **disable fuzzy for very short tokens** to avoid false hits.

---

## 4. Type override policy

When a span resolves to a controlled-vocabulary (Tier A) concept:

- The dictionary type **OVERRIDES** the NER provisional label.
- Example: NER "hypertension" = SYMPTOM; dictionary has hypertension = DISEASE
  → final type = **DISEASE**, `source = dictionary`, `overrode_ner = true`.

Override is gated by match tier:
- EXACT / ALIAS match → override.
- FUZZY match → override only if score ≥ high threshold; otherwise flag for review
  and keep NER label as provisional.

DECISION NEEDED:
- (4a) Should FUZZY matches be allowed to override NER type at all, or only
  exact/alias? Recommendation: **only exact/alias override; fuzzy is advisory.**

---

## 5. Dictionary as an independent scanner (NER-missed concepts)

NER and the dictionary are complementary recall sources. Even if NER misses a
span, the dictionary can scan the (normalized) query for known controlled-vocab
concepts.

- Run dictionary scan over the full query, not only over NER spans.
- Merge results: union of NER spans and dictionary-found spans.
- Conflict handling when spans overlap: prefer the longer span; if same span,
  prefer dictionary type (Tier A) over NER type.

DECISION NEEDED:
- (5a) Enable independent dictionary scanning in v1, or only resolve NER spans?
  Recommendation: **enable scanning** — it directly improves recall and is
  deterministic. But measure false positives on no-entity queries.

---

## 6. Unresolved concepts (span found, not in dictionary) — DECISION LEFT OPEN

When NER finds a span the dictionary cannot resolve (Tier A miss, no acceptable
fuzzy match):

- Status = `UNRESOLVED`.
- Keep the NER provisional label as a fallback, **clearly marked as provisional**.
- Do NOT fabricate a canonical concept or authoritative type.

This gate is **deliberately left OPEN** — UNRESOLVED behavior depends on the
eventual intent / field-mapping / search design that does not exist yet. Locking
it now would be premature.

Key distinction to preserve regardless of the final decision:
- An UNRESOLVED term MAY be useful for **logging / analytics / future vocabulary
  expansion** (it tells us what real queries contain that our controlled vocab
  lacks).
- An UNRESOLVED term MUST NOT **silently become a trusted database filter**. It
  has no governed type; treating it as a confirmed DISEASE/SYMPTOM/CONDITION
  filter would fabricate authority we haven't established.

Options to revisit when the downstream pipeline is designed (6a):
- use the provisional NER label for a *broadened / best-effort* search only,
- or exclude from structured filters and let the response/LLM layer handle it,
- or route to a clarification prompt.
Do not decide until intent/field mapping is on the table.

---

## Output contract (proposed)

Each resolved entity:

```json
{
  "span_text": "hypertension",
  "start": 20,
  "end": 32,
  "ner_label": "SYMPTOM",
  "canonical_concept": "hypertension",
  "resolved_type": "DISEASE",
  "match": "exact",           // exact | alias | fuzzy | none
  "match_score": 1.0,
  "source": "controlled_vocab",
  "status": "resolved",        // resolved | unresolved
  "overrode_ner": true
}
```

## Explicitly out of scope for this layer (v1)

- Semantic/vector matching.
- Organization-based access filtering (belongs to the DRX/MRX security layer).
- Intent detection and DB-field mapping (later phases).
- Real database lookups (mock/controlled data only until MRX integration).

## Review agenda — lock these gates one-by-one before any code

Each gate is reviewed and locked individually. Proposed v1 directions are for
discussion only; none is an implementation assumption.

- Gate 1 — Vocabulary scope: Tier A controlled vocabulary only (proposed).
- Gate 2 — Normalization: canonical concept + explicit aliases (proposed).
- Gate 3 — Matching: exact → alias → threshold-gated fuzzy → unresolved (proposed).
    - open sub-points: fuzzy algorithm + threshold; fuzzy on short tokens?
- Gate 4 — Type override: exact/alias may override NER; fuzzy advisory (proposed).
- Gate 5 — Independent dictionary scan: yes, with false-positive evaluation (proposed).
- Gate 6 — UNRESOLVED handling: LEFT OPEN (depends on downstream design).

Hard constraint (not a gate): no semantic/vector matching in v1.

Nothing is implemented until the relevant gate is explicitly locked.
