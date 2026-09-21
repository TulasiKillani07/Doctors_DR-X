"""
Single source of truth for the NER entity labels used across the project.

This NER model is the first layer of the larger QuerySearch understanding
pipeline. Its ONLY job is to recognize open-ended medical concepts in
doctor-style search queries. Closed/controlled values (brand, manufacturer,
dosage form, route, etc.) are handled later by the dictionary layer, NOT here.

The three labels below are the finalized schema for the NER phase:

    DISEASE    - a diagnosed illness / pathology being treated
                 e.g. breast cancer, asthma, hypertension, diabetes
    SYMPTOM    - a symptom or complaint the patient experiences
                 e.g. abdominal pain, headache, cough, fever
    CONDITION  - a physiological state / context that affects drug choice
                 but is not itself the illness being treated
                 e.g. pregnancy, renal impairment, lactation, elderly

Keep this list as the one place that defines the labels so annotation checks,
training, and evaluation all stay consistent. Every other module imports from
here rather than hardcoding label strings.
"""

ENTITY_LABELS = [
    "DISEASE",     # diagnosed illness / pathology, e.g. breast cancer, asthma
    "SYMPTOM",     # patient complaint, e.g. abdominal pain, headache, fever
    "CONDITION",   # physiological state / context, e.g. pregnancy, renal impairment
]


def is_valid_label(label: str) -> bool:
    """Return True if the given label is part of the current schema."""
    return label in ENTITY_LABELS
