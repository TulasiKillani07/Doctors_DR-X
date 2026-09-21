"""
generate_queries.py — Stage B: coverage-based NER query generation.

Generates realistic doctor-style search queries from the finalized terminology
bank, annotated with exact character offsets, category, difficulty, and the
source concepts used. Output is JSON.

SOURCE-OF-TRUTH FLOW (strictly enforced):
    terminology_bank.json        -> TRAIN queries + the "seen concepts" TEST portion
    unseen_eval_concepts.json    -> the "unseen concepts" TEST portion ONLY

The two vocabularies must NOT overlap; the generator asserts zero overlap before
generating and refuses to run otherwise. Unseen concepts never appear in TRAIN.

Design:
  - Deterministic, seeded (reproducible runs).
  - Curated natural templates per category, with variation in connector words,
    question/command form, entity position, and light filler, so the data is
    not repetitive template-matching.
  - Every concept is inserted verbatim, so character offsets are exact.
  - no_entity queries contain NO DISEASE/SYMPTOM/CONDITION spans. Dictionary
    terms (injection, tablet, Sanofi, manufacturer, ...) stay unlabeled — they
    belong to later layers, not V1 NER.
  - difficult_boundary_cases preserve exact labels (e.g. "acute renal failure"
    = DISEASE vs "renal impairment" = CONDITION).

Output files (in --outdir, default data/training/):
    train.json
    test.json
    coverage_matrix.json
    all_generated.json   (train + test combined, for inspection)

Usage:
    python -m src.generate_queries \
        --bank data/terminology/terminology_bank.json \
        --unseen data/terminology/unseen_eval_concepts.json \
        --outdir data/training \
        --train 800 --test-seen 75 --test-unseen 75 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

# --------------------------------------------------------------------------
# Template banks. {X} is the entity slot. Each template is a natural phrasing
# a doctor might type into a search box. Variation across position + form.
# --------------------------------------------------------------------------

DISEASE_TEMPLATES = [
    "drugs for {X}",
    "medicines for {X}",
    "medication for {X}",
    "treatment for {X}",
    "treatment options for {X}",
    "what drugs are used for {X}",
    "which drug is used for {X}",
    "which drugs are used for {X}",
    "what can be used to treat {X}",
    "what is prescribed for {X}",
    "what is used to treat {X}",
    "{X} treatment",
    "{X} drugs",
    "{X} medication",
    "{X} treatment options",
    "how to treat {X}",
    "how is {X} treated",
    "recommended treatment for {X}",
    "best medicine for {X}",
    "first line treatment for {X}",
    "drugs indicated for {X}",
    "options for treating {X}",
]

SYMPTOM_TEMPLATES = [
    "drugs for {X}",
    "medicine for {X}",
    "medicines for {X}",
    "what helps with {X}",
    "treatment for {X}",
    "what can be used for {X}",
    "anything for {X}",
    "something for {X}",
    "relief for {X}",
    "what can I give for {X}",
    "{X} relief",
    "how to manage {X}",
    "how to relieve {X}",
    "medicine to relieve {X}",
    "what relieves {X}",
    "drugs to help with {X}",
    "remedy for {X}",
]

# Condition phrasing classes. A condition concept is either a "noun_state"
# (reads naturally after "during"/"in", e.g. "during pregnancy",
# "in renal impairment") or a "patient_descriptor" (an adjective describing a
# patient group, e.g. "elderly", "paediatric" -> "elderly patients").
# The ENTITY SPAN always covers only the raw concept word, never the trailing
# "patients". This is achieved by rendering the phrase and locating the concept.
CONDITION_PHRASING = {
    "pregnancy": "noun_state",
    "lactation": "noun_state",
    "breastfeeding": "noun_state",
    "dialysis": "noun_state",
    "renal impairment": "noun_state",
    "hepatic impairment": "noun_state",
    "elderly": "patient_descriptor",
    "paediatric": "patient_descriptor",
}
DEFAULT_CONDITION_PHRASING = "noun_state"


def condition_phrase(concept: str) -> str:
    """Render a condition concept into a natural phrase; span stays on the concept."""
    kind = CONDITION_PHRASING.get(concept.lower(), DEFAULT_CONDITION_PHRASING)
    if kind == "patient_descriptor":
        return f"{concept} patients"
    return concept


# Condition templates are phrasing-aware. {Cphrase} is the rendered condition.
#   NOUN-STATE conditions (pregnancy, renal impairment, ...) read naturally after
#   "during"/"in" and are NOT a patient group, so "given to <state>" is avoided.
#   PATIENT-DESCRIPTOR conditions (elderly, paediatric) render as "<X> patients"
#   and read naturally with "in/for <X> patients" and "given to <X> patients".
# Noun-state templates that read naturally with BOTH "during" and "in"
# (temporal/physiological states like pregnancy, lactation, dialysis).
CONDITION_TEMPLATES_NOUN_STATE = [
    "drugs safe during {Cphrase}",
    "medication during {Cphrase}",
    "drug use in {Cphrase}",
    "treatment during {Cphrase}",
    "which drugs can be used in {Cphrase}",
    "safe medication in {Cphrase}",
    "dose adjustment in {Cphrase}",
    "is this drug safe in {Cphrase}",
    "drugs suitable for use in {Cphrase}",
    "recommended drugs in {Cphrase}",
]
# States that read with "in" but NOT "during" (e.g. renal impairment, obesity).
CONDITION_TEMPLATES_STATE_IN = [
    "drug use in {Cphrase}",
    "which drugs can be used in {Cphrase}",
    "safe medication in {Cphrase}",
    "dose adjustment in {Cphrase}",
    "is this drug safe in {Cphrase}",
    "drugs suitable for use in {Cphrase}",
    "recommended drugs in {Cphrase}",
    "treatment in {Cphrase}",
]

# Extra natural phrasings for "dialysis" specifically (patients undergoing/on/
# receiving dialysis). The entity span stays on "dialysis" only.
CONDITION_TEMPLATES_DIALYSIS_EXTRA = [
    "which treatment is suitable for patients undergoing {Cphrase}",
    "which medicine can be used by patients on {Cphrase}",
    "what is appropriate for patients receiving {Cphrase}",
    "drugs for patients undergoing {Cphrase}",
    "medication for patients on {Cphrase}",
]
CONDITION_TEMPLATES_DESCRIPTOR = [
    "drugs suitable for {Cphrase}",
    "medication for {Cphrase}",
    "what can be given to {Cphrase}",
    "recommended drugs for {Cphrase}",
    "safe medication for {Cphrase}",
    "which drugs can be used in {Cphrase}",
    "treatment options for {Cphrase}",
    "dose adjustment for {Cphrase}",
]


# Phrasing class for the unseen test conditions (explicit, grammatical):
#   obesity      -> noun_state  ("in obesity", "during obesity" avoided via NS set below)
#   adolescents  -> group_in    ("in adolescents", "for adolescents"); no "during", no "patients"
#   immunocompromised -> patient_descriptor ("immunocompromised patients")
#   geriatric patients -> patient_descriptor (already a group)
UNSEEN_PHRASING = {
    "obesity": "state_in",          # "in obesity", never "during obesity"
    "adolescents": "group_in",       # "in adolescents", "for adolescents"
    "immunocompromised": "patient_descriptor",
    "geriatric patients": "patient_descriptor",
}

# Templates for a plural patient group that reads with "in/for X" (no "during",
# no appended "patients"). Used for "adolescents".
CONDITION_TEMPLATES_GROUP_IN = [
    "drugs suitable for {Cphrase}",
    "medication for {Cphrase}",
    "which drugs can be used in {Cphrase}",
    "recommended drugs for {Cphrase}",
    "safe medication in {Cphrase}",
    "treatment options for {Cphrase}",
    "dose adjustment in {Cphrase}",
]


def condition_templates_for(concept: str, unseen: bool = False) -> list[str]:
    """Return the template list appropriate to the concept's phrasing class."""
    if unseen:
        kind = UNSEEN_PHRASING.get(concept.lower(), "noun_state")
    else:
        kind = CONDITION_PHRASING.get(concept.lower(), DEFAULT_CONDITION_PHRASING)
    if kind == "patient_descriptor":
        return CONDITION_TEMPLATES_DESCRIPTOR
    if kind == "group_in":
        return CONDITION_TEMPLATES_GROUP_IN
    if kind == "state_in":
        return CONDITION_TEMPLATES_STATE_IN
    # "dialysis" gets its noun-state templates PLUS the patient-undergoing phrasings,
    # but ONLY when surface variation is on (dialysis-extra was added in iter-2).
    if concept.lower() == "dialysis" and _SURFACE_VARIATION:
        return CONDITION_TEMPLATES_NOUN_STATE + CONDITION_TEMPLATES_DIALYSIS_EXTRA
    return CONDITION_TEMPLATES_NOUN_STATE

# Multi-entity templates: {D}=disease, {S}=symptom, {C}=condition.
DISEASE_SYMPTOM_TEMPLATES = [
    "treatment for {D} with {S}",
    "drugs for {D} presenting with {S}",
    "medication for {D} and {S}",
    "what can be used for {D} with {S}",
    "{D} with {S} treatment",
    "managing {D} with {S}",
]

# Multi-entity condition templates, phrasing-aware. "_NS" = noun-state (during/in
# a state), "_PD" = patient-descriptor (in/for <X> patients). Selected per concept.
DISEASE_CONDITION_NS = [
    "treatment for {D} during {Cphrase}",
    "drugs for {D} in {Cphrase}",
    "{D} treatment in {Cphrase}",
    "what can be used for {D} in {Cphrase}",
    "safe drugs for {D} during {Cphrase}",
    "managing {D} in {Cphrase}",
]
DISEASE_CONDITION_PD = [
    "treatment for {D} in {Cphrase}",
    "drugs for {D} in {Cphrase}",
    "{D} treatment for {Cphrase}",
    "what can be used for {D} in {Cphrase}",
    "safe drugs for {D} in {Cphrase}",
    "managing {D} in {Cphrase}",
]
SYMPTOM_CONDITION_NS = [
    "treatment for {S} during {Cphrase}",
    "medicine for {S} in {Cphrase}",
    "what helps with {S} in {Cphrase}",
    "drugs for {S} during {Cphrase}",
    "relief for {S} in {Cphrase}",
]
SYMPTOM_CONDITION_PD = [
    "treatment for {S} in {Cphrase}",
    "medicine for {S} in {Cphrase}",
    "what helps with {S} in {Cphrase}",
    "drugs for {S} in {Cphrase}",
    "relief for {S} in {Cphrase}",
]
DISEASE_SYMPTOM_CONDITION_NS = [
    "what can be used for {D} with {S} during {Cphrase}",
    "treatment for {D} with {S} in {Cphrase}",
    "drugs for {D} and {S} during {Cphrase}",
    "managing {D} with {S} in {Cphrase}",
]
DISEASE_SYMPTOM_CONDITION_PD = [
    "what can be used for {D} with {S} in {Cphrase}",
    "treatment for {D} with {S} in {Cphrase}",
    "drugs for {D} and {S} in {Cphrase}",
    "managing {D} with {S} in {Cphrase}",
]


def is_descriptor(concept: str) -> bool:
    return CONDITION_PHRASING.get(concept.lower(), DEFAULT_CONDITION_PHRASING) == "patient_descriptor"

MULTI_SAME_DISEASE = [
    "drugs for {A} and {B}",
    "treatment for {A} and {B}",
    "what is used for {A} and {B}",
    "medication for both {A} and {B}",
]
MULTI_SAME_SYMPTOM = [
    "medicine for {A} and {B}",
    "what helps with {A} and {B}",
    "something for {A} and {B}",
    "relief for {A} and {B}",
]
MULTI_SAME_CONDITION = [
    "drugs safe in {Aphrase} and {Bphrase}",
    "medication for {Aphrase} and {Bphrase}",
    "what can be used in {Aphrase} and {Bphrase}",
]

# no_entity: NO DISEASE/SYMPTOM/CONDITION spans. Some include dictionary terms
# (injection, tablet, Sanofi, manufacturer, capsule) which must stay UNLABELED.
NO_ENTITY_QUERIES = [
    "what drugs are available",
    "show me some treatment options",
    "which medicines are available",
    "what are the available options",
    "show available drugs",
    "find injections",
    "show me Sanofi products",
    "which products are available",
    "show the available medicines",
    "list all tablets",
    "show capsules from this manufacturer",
    "what can you recommend",
    "give me some options",
    "search for medicines",
    "show me the drug list",
    "list available injections",
    "show me all capsules",
    "which tablets do you have",
    "find products by this manufacturer",
    "show me the latest drugs",
    "what medicines can I search",
    "browse available treatments",
    "show all available products",
    "list the medicines you have",
    "what is in the catalogue",
    "show me syrups",
    "find oral tablets",
    "display the drug catalogue",
    "any new medicines available",
    "show me the product list",
]


class EvenSampler:
    """Yields items with even coverage: every item is used once before any repeats.
    Reshuffles each full pass (seeded) so distribution stays balanced but varied."""

    def __init__(self, items: list[str], rng: random.Random):
        self._items = list(items)
        self._rng = rng
        self._pool: list[str] = []

    def next(self) -> str:
        if not self._pool:
            self._pool = list(self._items)
            self._rng.shuffle(self._pool)
        return self._pool.pop()


def load_bank(path: Path) -> dict[str, list[str]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    out = {"DISEASE": [], "SYMPTOM": [], "CONDITION": []}
    for label in out:
        for entry in data.get("concepts", {}).get(label, []):
            out[label].append(entry["concept"])
    return out


def load_unseen(path: Path) -> dict[str, list[str]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    concepts = data.get("concepts", {})
    return {
        "DISEASE": list(concepts.get("DISEASE", [])),
        "SYMPTOM": list(concepts.get("SYMPTOM", [])),
        "CONDITION": list(concepts.get("CONDITION", [])),
    }


def assert_no_overlap(bank: dict[str, list[str]], unseen: dict[str, list[str]]) -> None:
    bank_all = {c.lower() for label in bank for c in bank[label]}
    unseen_all = {c.lower() for label in unseen for c in unseen[label]}
    overlap = bank_all & unseen_all
    if overlap:
        raise SystemExit(
            f"ABORT: unseen eval concepts overlap the training bank: {sorted(overlap)}. "
            "Unseen test vocabulary must stay disjoint from terminology_bank.json."
        )


def find_span(query: str, concept: str) -> tuple[int, int] | None:
    idx = query.find(concept)
    if idx < 0:
        # try case-insensitive, but we insert verbatim so this is a safety net
        low = query.lower().find(concept.lower())
        if low < 0:
            return None
        return low, low + len(concept)
    return idx, idx + len(concept)


def make_entity(query: str, concept: str, label: str) -> dict | None:
    span = find_span(query, concept)
    if span is None:
        return None
    start, end = span
    return {"text": query[start:end], "label": label, "start": start, "end": end}


# Module-level RNG for surface-form variation (set in main() for reproducibility).
_VARY_RNG: random.Random | None = None
# Master switch for ALL iteration-2 surface variation. When False, generation
# reproduces the true V1 baseline: no '?' variation, no capitalization, and no
# dialysis-extra templates. Set in main() from --surface-variation.
_SURFACE_VARIATION: bool = True

# Fraction of NON-no_entity queries that become question-form (trailing '?').
QUESTION_FRACTION = 0.45
# Fraction that get a leading capital (natural sentence casing).
CAPITALIZE_FRACTION = 0.4


def surface_variation(query: str, category: str) -> str:
    """Apply realistic surface variation: question-mark endings and casing.
    Offsets are computed AFTER this on the final string, so entity spans always
    stop before any trailing '?' punctuation.

    no_entity queries are handled separately (they carry their own punctuation),
    so we skip variation for them to keep them clean/controlled.
    """
    if not _SURFACE_VARIATION or _VARY_RNG is None or category == "no_entity":
        return query
    rng = _VARY_RNG
    # Question form: append '?' to a share of queries (only if not already punctuated).
    if not query.endswith(("?", ".")) and rng.random() < QUESTION_FRACTION:
        query = query + "?"
    # Natural capitalization of the first letter for a share of queries.
    if query and rng.random() < CAPITALIZE_FRACTION:
        query = query[0].upper() + query[1:]
    return query


def build_record(query: str, concept_labels: list[tuple[str, str]],
                 category: str, difficulty: str) -> dict | None:
    """concept_labels: list of (concept, label). Returns a record or None if a span is missing."""
    # Apply surface variation (question marks / casing) BEFORE computing offsets,
    # so spans align to the final text and exclude trailing punctuation.
    query = surface_variation(query, category)
    entities = []
    for concept, label in concept_labels:
        ent = make_entity(query, concept, label)
        if ent is None:
            return None  # skip malformed
        entities.append(ent)
    # sort by start offset
    entities.sort(key=lambda e: e["start"])
    return {
        "query": query,
        "entities": entities,
        "category": category,
        "difficulty": difficulty,
        "source_concepts": [c for c, _ in concept_labels],
    }


def gen_single(rng, concepts, label, templates, category, difficulty, n) -> list[dict]:
    """Single-entity queries with EVEN concept coverage (round-robin sampler),
    so no concept dominates and none is starved."""
    out = []
    sampler = EvenSampler(concepts, rng)
    attempts = 0
    while len(out) < n and attempts < n * 40:
        attempts += 1
        concept = sampler.next()
        if label == "CONDITION":
            template = rng.choice(condition_templates_for(concept))
            query = template.format(Cphrase=condition_phrase(concept))
        else:
            template = rng.choice(templates)
            query = template.format(X=concept)
        rec = build_record(query, [(concept, label)], category, difficulty)
        if rec:
            out.append(rec)
    return out


def gen_pair(rng, concepts_a, label_a, concepts_b, label_b, templates,
             key_a, key_b, category, difficulty, n) -> list[dict]:
    """Generate two-entity queries. If an entity is CONDITION, its template slot
    is {Cphrase} and the value is rendered via condition_phrase(); the entity
    span still covers only the raw concept."""
    out = []
    attempts = 0
    while len(out) < n and attempts < n * 30:
        attempts += 1
        a = rng.choice(concepts_a)
        b = rng.choice(concepts_b)
        fmt = {}
        fmt[key_a] = condition_phrase(a) if label_a == "CONDITION" else a
        fmt[key_b] = condition_phrase(b) if label_b == "CONDITION" else b
        template = rng.choice(templates)
        query = template.format(**fmt)
        rec = build_record(query, [(a, label_a), (b, label_b)], category, difficulty)
        if rec:
            out.append(rec)
    return out


def gen_entity_condition(rng, main_concepts, main_label, conditions, ns_templates, pd_templates,
                         main_key, category, difficulty, n) -> list[dict]:
    """Two-entity queries pairing a DISEASE or SYMPTOM with a CONDITION, choosing
    noun-state vs patient-descriptor templates per condition concept."""
    out = []
    attempts = 0
    while len(out) < n and attempts < n * 30:
        attempts += 1
        m = rng.choice(main_concepts)
        c = rng.choice(conditions)
        templates = pd_templates if is_descriptor(c) else ns_templates
        template = rng.choice(templates)
        query = template.format(**{main_key: m, "Cphrase": condition_phrase(c)})
        rec = build_record(query, [(m, main_label), (c, "CONDITION")], category, difficulty)
        if rec:
            out.append(rec)
    return out


def gen_triple(rng, diseases, symptoms, conditions, templates, category, difficulty, n) -> list[dict]:
    out = []
    attempts = 0
    while len(out) < n and attempts < n * 20:
        attempts += 1
        d = rng.choice(diseases)
        s = rng.choice(symptoms)
        c = rng.choice(conditions)
        tmpl_list = DISEASE_SYMPTOM_CONDITION_PD if is_descriptor(c) else DISEASE_SYMPTOM_CONDITION_NS
        template = rng.choice(tmpl_list)
        query = template.format(D=d, S=s, Cphrase=condition_phrase(c))
        rec = build_record(query, [(d, "DISEASE"), (s, "SYMPTOM"), (c, "CONDITION")],
                           category, difficulty)
        if rec:
            out.append(rec)
    return out


def gen_same_type(rng, concepts, label, templates, category, difficulty, n) -> list[dict]:
    out = []
    attempts = 0
    while len(out) < n and attempts < n * 20:
        attempts += 1
        if len(concepts) < 2:
            break
        a, b = rng.sample(concepts, 2)
        template = rng.choice(templates)
        if label == "CONDITION":
            query = template.format(Aphrase=condition_phrase(a), Bphrase=condition_phrase(b))
        else:
            query = template.format(A=a, B=b)
        rec = build_record(query, [(a, label), (b, label)], category, difficulty)
        if rec:
            out.append(rec)
    return out


def gen_no_entity(rng, n) -> list[dict]:
    """Emit up to n UNIQUE no-entity queries (never duplicates), with a mix of
    plain, question-form ('?'), and sentence-form ('.') endings + casing, so the
    model learns that such phrasings carry NO entities (prevents hallucination)."""
    pool = list(NO_ENTITY_QUERIES)
    rng.shuffle(pool)
    chosen = pool[:min(n, len(pool))]
    out = []
    for base in chosen:
        q = base
        if _SURFACE_VARIATION:
            roll = rng.random()
            if roll < 0.4:
                q = q + "?"
            elif roll < 0.6:
                q = q + "."
            if rng.random() < 0.5:
                q = q[0].upper() + q[1:]
        out.append({
            "query": q,
            "entities": [],
            "category": "no_entity",
            "difficulty": "easy",
            "source_concepts": [],
        })
    return out


def gen_difficult_boundary(rng, bank, n) -> list[dict]:
    """
    Boundary cases stressing DISEASE-vs-CONDITION. Pairs a DISEASE with a
    CONDITION in the same query so the model must separate them by label,
    not by surface form. Preserves exact labels.
    """
    out = []
    diseases = bank["DISEASE"]
    conditions = bank["CONDITION"]
    ns_templates = [
        "treatment for {D} in {Cphrase}",
        "managing {D} during {Cphrase}",
        "drugs for {D} in {Cphrase}",
        "is treatment for {D} safe in {Cphrase}",
    ]
    pd_templates = [
        "treatment for {D} in {Cphrase}",
        "managing {D} in {Cphrase}",
        "drugs for {D} in {Cphrase}",
        "is treatment for {D} safe in {Cphrase}",
    ]
    attempts = 0
    while len(out) < n and attempts < n * 30:
        attempts += 1
        d = rng.choice(diseases)
        c = rng.choice(conditions)
        template = rng.choice(pd_templates if is_descriptor(c) else ns_templates)
        query = template.format(D=d, Cphrase=condition_phrase(c))
        rec = build_record(query, [(d, "DISEASE"), (c, "CONDITION")],
                           "difficult_boundary_cases", "hard")
        if rec:
            out.append(rec)
    return out


def generate_train(rng, bank) -> list[dict]:
    d, s, c = bank["DISEASE"], bank["SYMPTOM"], bank["CONDITION"]
    recs: list[dict] = []
    # Single-entity (larger share)
    recs += gen_single(rng, d, "DISEASE", DISEASE_TEMPLATES, "single_disease", "easy", 170)
    recs += gen_single(rng, s, "SYMPTOM", SYMPTOM_TEMPLATES, "single_symptom", "easy", 155)
    recs += gen_single(rng, c, "CONDITION", None, "single_condition", "easy", 80)
    # Multi-entity (fewer)
    recs += gen_pair(rng, d, "DISEASE", s, "SYMPTOM", DISEASE_SYMPTOM_TEMPLATES,
                     "D", "S", "disease_symptom", "medium", 90)
    recs += gen_entity_condition(rng, d, "DISEASE", c, DISEASE_CONDITION_NS, DISEASE_CONDITION_PD,
                                 "D", "disease_condition", "medium", 90)
    recs += gen_entity_condition(rng, s, "SYMPTOM", c, SYMPTOM_CONDITION_NS, SYMPTOM_CONDITION_PD,
                                 "S", "symptom_condition", "medium", 70)
    recs += gen_triple(rng, d, s, c, None,
                       "disease_symptom_condition", "hard", 40)
    # Multiple same-type
    recs += gen_same_type(rng, d, "DISEASE", MULTI_SAME_DISEASE, "multiple_same_type", "medium", 25)
    recs += gen_same_type(rng, s, "SYMPTOM", MULTI_SAME_SYMPTOM, "multiple_same_type", "medium", 20)
    recs += gen_same_type(rng, c, "CONDITION", MULTI_SAME_CONDITION, "multiple_same_type", "medium", 15)
    # No entity (pool is limited; dedupe will cap it)
    recs += gen_no_entity(rng, 30)
    # Difficult boundary
    recs += gen_difficult_boundary(rng, bank, 45)
    return recs


def generate_test_seen(rng, bank, n) -> list[dict]:
    """Seen concepts, unseen phrasing: use held-out templates not used in train-heavy mix."""
    d, s, c = bank["DISEASE"], bank["SYMPTOM"], bank["CONDITION"]
    # Held-out phrasings NOT used in training, to test language generalization
    # on already-seen concepts. {P} is a phrase slot (concept or condition-phrase).
    held_out = [
        "could you suggest something for {P}",
        "i need a medicine for {P}",
        "what would you recommend for {P}",
        "any options to manage {P}",
        "help with {P} please",
        "im looking for treatment for {P}",
        "please suggest a drug for {P}",
        "what should be given for {P}",
        "advise a treatment for {P}",
        "kindly recommend medicine for {P}",
    ]
    recs = []
    labels = [("DISEASE", d), ("SYMPTOM", s), ("CONDITION", c)]
    attempts = 0
    while len(recs) < n and attempts < n * 30:
        attempts += 1
        label, pool = rng.choice(labels)
        concept = rng.choice(pool)
        phrase = condition_phrase(concept) if label == "CONDITION" else concept
        template = rng.choice(held_out)
        query = template.format(P=phrase)
        rec = build_record(query, [(concept, label)], "test_seen_concept_new_phrasing", "medium")
        if rec:
            recs.append(rec)
    return recs


def generate_test_unseen(rng, unseen, n) -> list[dict]:
    """Unseen concepts: standard phrasing, concepts NOT in the training bank."""
    d, s, c = unseen["DISEASE"], unseen["SYMPTOM"], unseen["CONDITION"]
    recs = []
    labels = [
        ("DISEASE", d, DISEASE_TEMPLATES),
        ("SYMPTOM", s, SYMPTOM_TEMPLATES),
        ("CONDITION", c, None),
    ]
    attempts = 0
    while len(recs) < n and attempts < n * 30:
        attempts += 1
        label, pool, templates = rng.choice(labels)
        if not pool:
            continue
        concept = rng.choice(pool)
        if label == "CONDITION":
            template = rng.choice(condition_templates_for(concept, unseen=True))
            query = template.format(Cphrase=unseen_condition_phrase(concept))
        else:
            template = rng.choice(templates)
            query = template.format(X=concept)
        rec = build_record(query, [(concept, label)], "test_unseen_concept", "hard")
        if rec:
            recs.append(rec)
    return recs


def unseen_condition_phrase(concept: str) -> str:
    """Phrasing for unseen test conditions. Descriptors render as a grammatical
    patient-group phrase; the entity span still covers only the concept word.

      immunocompromised -> "immunocompromised patients"
      adolescents       -> "adolescents"  (used with "in adolescents"; NOT "adolescents patients")
      geriatric patients-> "geriatric patients" (already a group)
      obesity           -> "obesity" (noun state)
    """
    low = concept.lower()
    if low == "immunocompromised":
        return f"{concept} patients"
    # "adolescents", "geriatric patients", "obesity" read naturally as-is with
    # the templates chosen for them; do not append "patients".
    return concept


def coverage_matrix(records: list[dict]) -> dict:
    by_category: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    by_label: dict[str, int] = {}
    entity_count_hist: dict[int, int] = {}
    for r in records:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1
        by_difficulty[r["difficulty"]] = by_difficulty.get(r["difficulty"], 0) + 1
        n = len(r["entities"])
        entity_count_hist[n] = entity_count_hist.get(n, 0) + 1
        for e in r["entities"]:
            by_label[e["label"]] = by_label.get(e["label"], 0) + 1
    return {
        "total": len(records),
        "by_category": dict(sorted(by_category.items())),
        "by_difficulty": dict(sorted(by_difficulty.items())),
        "entities_by_label": dict(sorted(by_label.items())),
        "queries_by_entity_count": {str(k): v for k, v in sorted(entity_count_hist.items())},
    }


def _write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate coverage-based NER queries (JSON).")
    parser.add_argument("--bank", type=Path, default=Path("data/terminology/terminology_bank.json"))
    parser.add_argument("--unseen", type=Path, default=Path("data/terminology/unseen_eval_concepts.json"))
    parser.add_argument("--outdir", type=Path, default=Path("data/training"))
    parser.add_argument("--train", type=int, default=800)
    parser.add_argument("--test-seen", type=int, default=75)
    parser.add_argument("--test-unseen", type=int, default=75)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--surface-variation", choices=["on", "off"], default="on",
                        help="on = iteration-2 style (?/casing/dialysis-extra); "
                             "off = true V1 baseline (none of these).")
    args = parser.parse_args()

    global _SURFACE_VARIATION
    _SURFACE_VARIATION = (args.surface_variation == "on")

    bank = load_bank(args.bank)
    unseen = load_unseen(args.unseen)

    # Enforce source-of-truth separation.
    assert_no_overlap(bank, unseen)

    rng = random.Random(args.seed)
    # Separate seeded RNG for surface-form variation (deterministic).
    global _VARY_RNG
    _VARY_RNG = random.Random(args.seed + 1)

    # TRAIN
    train = generate_train(rng, bank)
    # De-duplicate identical queries within train.
    train = _dedupe(train)

    # TEST
    test_seen = _dedupe(generate_test_seen(rng, bank, args.test_seen))
    test_unseen = _dedupe(generate_test_unseen(rng, unseen, args.test_unseen))
    test = test_seen + test_unseen

    # Safety: ensure no unseen concept leaked into train.
    _assert_train_has_no_unseen(train, unseen)

    args.outdir.mkdir(parents=True, exist_ok=True)
    _write_json(args.outdir / "train.json", train)
    _write_json(args.outdir / "test.json", test)
    _write_json(args.outdir / "all_generated.json", train + test)

    matrix = {
        "seed": args.seed,
        "train": coverage_matrix(train),
        "test_seen_concept_new_phrasing": coverage_matrix(test_seen),
        "test_unseen_concept": coverage_matrix(test_unseen),
        "test_total": coverage_matrix(test),
    }
    _write_json(args.outdir / "coverage_matrix.json", matrix)

    print(f"Query generation complete (JSON) [surface-variation={args.surface_variation}]:")
    print(f"  TRAIN: {len(train)}  (target {args.train})")
    print(f"  TEST : {len(test)}  = seen {len(test_seen)} + unseen {len(test_unseen)}")
    print(f"\n  train.json / test.json / all_generated.json / coverage_matrix.json -> {args.outdir}")
    print("\n  TRAIN categories:")
    for cat, cnt in matrix["train"]["by_category"].items():
        print(f"    {cat:<32} {cnt}")


def _dedupe(records: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in records:
        if r["query"] in seen:
            continue
        seen.add(r["query"])
        out.append(r)
    return out


def _assert_train_has_no_unseen(train: list[dict], unseen: dict[str, list[str]]) -> None:
    unseen_all = {c.lower() for label in unseen for c in unseen[label]}
    for r in train:
        for concept in r["source_concepts"]:
            if concept.lower() in unseen_all:
                raise SystemExit(
                    f"ABORT: unseen concept '{concept}' leaked into TRAIN query: {r['query']!r}"
                )


if __name__ == "__main__":
    main()
