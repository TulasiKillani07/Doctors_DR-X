"""
generate_queries_v2.py — V2 Coverage-based NER Query Generator (Combinations-First & Clean Search Grammar).

Generates ~3,500 completely NEW, authentic, natural doctor-style search queries
grounded strictly in data/terminology/terminology_bank.json (93 concepts: 41 DISEASE,
44 SYMPTOM, 8 CONDITION).

Guarantees & Clinical Ontology Rules:
  1. Authentic Doctor Search Phrasing (Zero Recommendation / Case-Note Jargon):
     - Stripped: 'what should i prescribe', 'what is recommended', 'which agents should be avoided',
       'what can i give', 'doctor evaluating', 'patient diagnosed with ... what should i prescribe'.
     - NER models need clean entity search syntax ('treatment for X', 'medicines for X in Y').
  2. Strict CONDITION_GRAMMAR_RULES:
     - pregnancy: 'during pregnancy', 'in pregnancy'
     - lactation: 'during lactation'
     - breastfeeding: 'while breastfeeding', 'during breastfeeding'
     - renal impairment: 'in renal impairment', 'in patients with renal impairment'
     - hepatic impairment: 'in hepatic impairment', 'in patients with hepatic impairment'
     - dialysis: 'in patients undergoing dialysis', 'in patients on dialysis', 'during dialysis'
     - elderly: 'in elderly patients', 'for elderly patients'
     - paediatric: 'in paediatric patients', 'for paediatric patients'
     - STRICTLY BANS: 'during elderly', 'during paediatric', 'given to pregnancy', etc.
  3. Synonymous Context Co-occurrence Ban:
     - 'breastfeeding' and 'lactation' are never generated together in the same query.
  4. Combinations-First Balance (~74% Multi-Entity):
     - Heavy multi-entity emphasis: DISEASE+CONDITION (~700), DISEASE+SYMPTOM (~500),
       DISEASE+SYMPTOM+CONDITION (~400), SYMPTOM+CONDITION (~350), Boundary cases (~250).
     - Single-entity reduced to ~22% baseline.
  5. Seizure Cluster (Option A):
     - 'seizures' -> SYMPTOM.
     - 'complex partial seizures' -> DISEASE.
     - 'simple and complex absence seizures' -> DISEASE.
  6. DISEASE vs CONDITION Boundaries:
     - 'acute renal failure' is DISEASE, 'renal impairment' is CONDITION (standalone and co-occurring).
     - 'autoimmune hepatitis' is DISEASE, 'hepatic impairment' is CONDITION.
     - 'cardiac insufficiency' is DISEASE, 'elderly' is CONDITION.
  7. Frame ceiling enforced: (concept, frame_id) <= 2.
  8. Clean catalog/formulation no-entity queries with exactly 0 entity spans.
  9. Stratified 90/10 train/dev split preserving concept, label, and style coverage (100% concept coverage in both splits).
  10. Strict runtime normalization via src.preprocess.normalize_query with exact character offsets.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocess import normalize_query

# --------------------------------------------------------------------------
# Template definitions with explicit frame_id
# --------------------------------------------------------------------------

@dataclass
class Template:
    frame_id: str
    template: str
    style: str
    difficulty: str


# 1. Single DISEASE Templates (Direct search phrasing, NO recommendation jargon)
DISEASE_TEMPLATES: list[Template] = [
    Template("d_meds_for", "Medicines for {D}", "search_style", "easy"),
    Template("d_treatment_for", "Treatment for {D}", "search_style", "easy"),
    Template("d_drugs_for", "Drugs for {D}", "search_style", "easy"),
    Template("d_rx_options", "Prescription options for {D}", "search_style", "easy"),
    Template("d_treatment_options", "Treatment options for {D}", "search_style", "easy"),
    Template("d_clinical_management", "Clinical management of {D}", "search_style", "medium"),
    Template("d_therapies_indicated", "Therapies indicated for {D}", "search_style", "medium"),
    Template("d_pharmacotherapy", "Pharmacotherapy for {D}", "search_style", "medium"),

    Template("dq_which_medicine_used", "Which medicine is used for {D}?", "direct_question", "easy"),
    Template("dq_what_treatment_available", "What treatment is available for {D}?", "direct_question", "easy"),
    Template("dq_what_drugs_prescribed", "What drugs are indicated for {D}?", "direct_question", "easy"),
    Template("dq_how_is_d_treated", "How is {D} treated?", "direct_question", "easy"),
    Template("dq_what_can_be_prescribed", "What options exist for {D}?", "direct_question", "medium"),
    Template("dq_which_medications_indicated", "Which medications are indicated for {D}?", "direct_question", "medium"),
    Template("dq_is_there_medical_treatment", "Is there an approved medical treatment for {D}?", "direct_question", "medium"),
    Template("dq_what_options_exist", "What therapeutic options exist for {D}?", "direct_question", "medium"),

    Template("act_show_meds", "Show medicines for {D}.", "action_oriented", "easy"),
    Template("act_list_treatments", "List treatments for {D}.", "action_oriented", "easy"),
    Template("act_find_drugs", "Find approved drugs for {D}.", "action_oriented", "easy"),
    Template("act_display_options", "Display therapy options for {D}.", "action_oriented", "medium"),
    Template("act_identify_therapies", "Identify medicines used to treat {D}.", "action_oriented", "medium"),

    Template("help_what_helps_with", "What helps with {D}?", "can_help_relief", "easy"),
    Template("help_which_drug_helps", "Which drug helps treat {D}?", "can_help_relief", "easy"),
    Template("help_medicines_that_help", "Are there medicines that help with {D}?", "can_help_relief", "easy"),

    Template("inf_anything_for", "Anything for {D}?", "informal_brief", "easy"),
    Template("inf_need_something_for", "Need something for {D}.", "informal_brief", "easy"),
    Template("inf_medicine_for", "Medicine needed for {D}.", "informal_brief", "easy"),
    Template("inf_what_works_for", "What works for {D}?", "informal_brief", "easy"),
]

# 2. Single SYMPTOM Templates (Symptom-relief search phrasing)
SYMPTOM_TEMPLATES: list[Template] = [
    Template("s_relief_meds", "{S} relief medications", "search_style", "easy"),
    Template("s_drugs_for", "Drugs for {S}", "search_style", "easy"),
    Template("s_medicines_for", "Medicines for {S}", "search_style", "easy"),
    Template("s_management_meds", "Medication to manage {S}", "search_style", "easy"),
    Template("s_remedies", "Medical remedies for {S}", "search_style", "medium"),

    Template("dq_which_medicine_relieves", "Which medicine relieves {S}?", "direct_question", "easy"),
    Template("dq_what_treatment_available_s", "What treatment is available for {S}?", "direct_question", "easy"),
    Template("dq_how_to_manage_s", "How to manage {S}?", "direct_question", "medium"),
    Template("dq_what_drugs_prescribed_s", "What drugs are used to relieve {S}?", "direct_question", "medium"),
    Template("dq_which_agent_eases", "Which pharmaceutical eases {S}?", "direct_question", "medium"),
    Template("dq_what_helps_reduce", "What helps reduce {S}?", "direct_question", "easy"),

    Template("act_show_meds_s", "Show medicines used to treat {S}.", "action_oriented", "easy"),
    Template("act_list_drugs_s", "List drugs indicated for relieving {S}.", "action_oriented", "easy"),
    Template("act_find_treatments_s", "Find treatments for {S}.", "action_oriented", "easy"),
    Template("act_display_options_s", "Display pharmaceutical options for {S}.", "action_oriented", "medium"),

    Template("help_what_can_help_with_s", "What can help with {S}?", "can_help_relief", "easy"),
    Template("help_which_medicine_helps_s", "Which medicine helps with {S}?", "can_help_relief", "easy"),
    Template("help_what_helps_relieve_s", "What helps relieve {S}?", "can_help_relief", "easy"),
    Template("help_anything_to_ease_s", "Is there anything to help ease {S}?", "can_help_relief", "easy"),

    Template("inf_something_for_s", "Something for {S}.", "informal_brief", "easy"),
    Template("inf_anything_for_s", "Anything for {S}?", "informal_brief", "easy"),
    Template("inf_need_medicine_for_s", "Need medicine for {S}.", "informal_brief", "easy"),
    Template("inf_what_stops_s", "What stops {S}?", "informal_brief", "easy"),
]

# 3. Single CONDITION Templates (Prepositional context modifying therapy)
CONDITION_TEMPLATES: list[Template] = [
    Template("c_meds_suitable", "Medicines suitable {C}", "search_style", "easy"),
    Template("c_treatment_options", "Treatment options {C}", "search_style", "easy"),
    Template("c_drug_choices", "Drug choices {C}", "search_style", "easy"),
    Template("c_prescribing_guidelines", "Prescribing guidelines {C}", "search_style", "medium"),

    Template("dq_which_meds_suitable_c", "Which medicines are suitable {C}?", "direct_question", "easy"),
    Template("dq_what_treatment_appropriate_c", "What treatment is appropriate {C}?", "direct_question", "easy"),
    Template("dq_what_drugs_permitted_c", "What drugs are permitted {C}?", "direct_question", "easy"),
    Template("dq_which_medications_permitted_c", "Which medications are permitted {C}?", "direct_question", "medium"),
    Template("dq_what_therapeutic_options_c", "What therapeutic options exist {C}?", "direct_question", "medium"),

    Template("act_show_drugs_c", "Show drugs permitted {C}.", "action_oriented", "easy"),
    Template("act_list_treatments_c", "List medical therapies {C}.", "action_oriented", "easy"),
    Template("act_find_suitable_c", "Find suitable medications {C}.", "action_oriented", "easy"),

    Template("inf_medication_c", "Medication options {C}.", "informal_brief", "easy"),
    Template("inf_treatments_c", "Treatments {C}.", "informal_brief", "easy"),
]

# 4. Multi-Entity Templates

# DISEASE + CONDITION (The key boundary pair: pathology + context)
DISEASE_CONDITION_TEMPLATES: list[Template] = [
    Template("dc_treatment_for_d_c", "Treatment for {D} {C}", "search_style", "easy"),
    Template("dc_medicines_for_d_c", "Medicines for {D} {C}", "search_style", "easy"),
    Template("dc_drugs_for_d_c", "Drugs for {D} {C}", "search_style", "easy"),
    Template("dc_drug_options_d_c", "Drug options for {D} {C}", "search_style", "easy"),
    Template("dc_managing_d_c", "Managing {D} {C}", "search_style", "medium"),
    Template("dc_clinical_management_d_c", "Clinical management of {D} {C}", "search_style", "medium"),
    Template("dc_therapies_for_d_c", "Therapies indicated for {D} {C}", "search_style", "medium"),
    Template("dc_pharmacotherapy_d_c", "Pharmacotherapy for {D} {C}", "search_style", "medium"),
    Template("dc_rx_options_d_c", "Prescription options for {D} {C}", "search_style", "easy"),
    Template("dc_treatment_options_d_c", "Treatment options for {D} {C}", "search_style", "easy"),
    Template("dc_prescribing_for_d_c", "Prescribing for {D} {C}", "search_style", "medium"),
    Template("dc_medical_therapies_d_c", "Medical therapies for {D} {C}", "search_style", "medium"),
    Template("dc_therapy_choices_d_c", "Therapy choices for {D} {C}", "search_style", "medium"),
    Template("dc_approved_treatments_d_c", "Approved treatments for {D} {C}", "search_style", "medium"),
    Template("dc_drug_therapies_d_c", "Drug therapies for {D} {C}", "search_style", "medium"),
    Template("dc_medication_choices_d_c", "Medication choices for {D} {C}", "search_style", "medium"),

    Template("dc_dq_what_suitable_d_c", "What medicine is suitable for {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_which_treatment_d_c", "Which treatment is appropriate for {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_which_drugs_treat_d_c", "Which drugs treat {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_how_to_treat_d_c", "How to treat {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_options_for_d_c", "What options exist for {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_what_drugs_used_d_c", "What drugs are used for {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_which_medicine_used_d_c", "Which medicine is used for {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_how_is_d_managed_c", "How is {D} managed {C}?", "direct_question", "medium"),
    Template("dc_dq_what_therapies_indicated_d_c", "What therapies are indicated for {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_what_treatments_available_d_c", "What treatments are available for {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_is_there_treatment_d_c", "Is there an approved treatment for {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_which_pharmaceutical_d_c", "Which pharmaceutical is used for {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_what_can_treat_d_c", "What can treat {D} {C}?", "direct_question", "medium"),
    Template("dc_dq_which_regimen_d_c", "Which medicine is indicated for {D} {C}?", "direct_question", "medium"),

    Template("act_show_options_d_c", "Show available options for {D} {C}.", "action_oriented", "easy"),
    Template("act_list_meds_d_c", "List medications for {D} {C}.", "action_oriented", "easy"),
    Template("act_find_therapies_d_c", "Find therapies for {D} {C}.", "action_oriented", "medium"),
    Template("act_display_drugs_d_c", "Display approved drugs for {D} {C}.", "action_oriented", "medium"),
    Template("act_identify_medicines_d_c", "Identify medicines for {D} {C}.", "action_oriented", "medium"),
    Template("act_show_therapies_d_c", "Show therapies indicated for {D} {C}.", "action_oriented", "medium"),
    Template("act_list_treatments_d_c", "List treatments for {D} {C}.", "action_oriented", "easy"),
    Template("act_find_medicines_d_c", "Find medicines for {D} {C}.", "action_oriented", "easy"),
    Template("act_display_options_d_c", "Display therapeutic options for {D} {C}.", "action_oriented", "medium"),
    Template("act_locate_therapies_d_c", "Locate therapies for {D} {C}.", "action_oriented", "medium"),

    Template("help_what_can_treat_d_c", "What helps treat {D} {C}?", "can_help_relief", "medium"),
    Template("help_which_drug_helps_d_c", "Which drug helps treat {D} {C}?", "can_help_relief", "medium"),
    Template("help_medicines_that_help_d_c", "Medicines that help treat {D} {C}.", "can_help_relief", "medium"),

    Template("inf_meds_d_c", "Medicines for {D} {C}.", "informal_brief", "easy"),
    Template("inf_options_d_c", "Options for {D} {C}.", "informal_brief", "easy"),
    Template("inf_treatment_d_c", "Treatment for {D} {C}.", "informal_brief", "easy"),
    Template("inf_therapies_d_c", "Therapies for {D} {C}.", "informal_brief", "easy"),
    Template("inf_drugs_d_c", "Drugs for {D} {C}.", "informal_brief", "easy"),
    Template("inf_need_medicine_d_c", "Need medicine for {D} {C}.", "informal_brief", "easy"),
]

# DISEASE + SYMPTOM (Pathology + presenting complaint)
DISEASE_SYMPTOM_TEMPLATES: list[Template] = [
    Template("ds_treatment_d_with_s", "Treatment for {D} with {S}", "search_style", "easy"),
    Template("ds_meds_d_and_s", "Medicines for {D} and {S}", "search_style", "easy"),
    Template("ds_managing_d_with_s", "Managing {D} accompanied by {S}", "search_style", "medium"),
    Template("ds_therapies_d_s", "Therapies for {D} with concurrent {S}", "search_style", "medium"),

    Template("ds_dq_what_suitable_d_s", "What medicine is suitable for {D} and {S}?", "direct_question", "medium"),
    Template("ds_dq_how_to_treat_d_s", "How to treat {D} accompanied by {S}?", "direct_question", "medium"),
    Template("ds_dq_which_drug_d_s", "Which drug treats {D} and relieves {S}?", "direct_question", "medium"),
    Template("ds_dq_what_given_d_s", "What treats {D} accompanied by {S}?", "direct_question", "medium"),

    Template("ds_act_show_meds_d_s", "Show medications for {D} with {S}.", "action_oriented", "easy"),
    Template("ds_act_find_therapy_d_s", "Find therapy for {D} accompanied by {S}.", "action_oriented", "medium"),

    Template("ds_help_what_helps_d_s", "What helps treat {D} while relieving {S}?", "can_help_relief", "medium"),
    Template("ds_inf_treatment_d_s", "Treatment for {D} with {S}.", "informal_brief", "easy"),
]

# SYMPTOM + CONDITION (Complaint modified by context)
SYMPTOM_CONDITION_TEMPLATES: list[Template] = [
    Template("sc_relief_s_c", "{S} relief {C}", "search_style", "easy"),
    Template("sc_meds_s_c", "Medicines for {S} {C}", "search_style", "easy"),
    Template("sc_drugs_s_c", "Drugs for {S} {C}", "search_style", "easy"),
    Template("sc_management_s_c", "Management of {S} {C}", "search_style", "medium"),
    Template("sc_treatment_s_c", "Treatment options for {S} {C}", "search_style", "easy"),
    Template("sc_remedies_s_c", "Medical remedies for {S} {C}", "search_style", "medium"),

    Template("sc_dq_what_relieves_s_c", "What medicine relieves {S} {C}?", "direct_question", "medium"),
    Template("sc_dq_which_drug_s_c", "Which drug for {S} is suitable {C}?", "direct_question", "medium"),
    Template("sc_dq_how_manage_s_c", "How to manage {S} {C}?", "direct_question", "medium"),
    Template("sc_dq_what_treatments_s_c", "What treatments exist for {S} {C}?", "direct_question", "medium"),
    Template("sc_dq_which_agent_eases_s_c", "Which agent eases {S} {C}?", "direct_question", "medium"),
    Template("sc_dq_what_helps_reduce_s_c", "What helps reduce {S} {C}?", "direct_question", "medium"),

    Template("sc_act_show_remedies_s_c", "Show remedies for {S} {C}.", "action_oriented", "easy"),
    Template("sc_act_find_meds_s_c", "Find medicines for {S} {C}.", "action_oriented", "easy"),
    Template("sc_act_list_options_s_c", "List options for {S} {C}.", "action_oriented", "easy"),
    Template("sc_act_display_treatments_s_c", "Display treatments for {S} {C}.", "action_oriented", "medium"),

    Template("sc_help_what_helps_s_c", "What helps with {S} {C}?", "can_help_relief", "medium"),
    Template("sc_help_which_relieves_s_c", "Which medicine helps relieve {S} {C}?", "can_help_relief", "medium"),

    Template("sc_inf_treatment_s_c", "Treatment for {S} {C}.", "informal_brief", "easy"),
    Template("sc_inf_need_something_s_c", "Need something for {S} {C}.", "informal_brief", "easy"),
]

# SYMPTOM + SYMPTOM
SYMPTOM_SYMPTOM_TEMPLATES: list[Template] = [
    Template("ss_meds_s1_s2", "Medicines for {S1} and {S2}", "search_style", "easy"),
    Template("ss_relief_s1_s2", "Relief for {S1} and {S2}", "search_style", "easy"),
    Template("ss_dq_what_helps_s1_s2", "What medicine helps with {S1} and {S2}?", "direct_question", "medium"),
    Template("ss_dq_which_treatment_s1_s2", "Which treatment addresses {S1} and {S2}?", "direct_question", "medium"),
    Template("ss_act_show_meds_s1_s2", "Show medications indicated for {S1} and {S2}.", "action_oriented", "medium"),
    Template("ss_help_what_relieves_s1_s2", "What relieves {S1} and {S2}?", "can_help_relief", "easy"),
    Template("ss_inf_medicine_s1_s2", "Medicine for {S1} and {S2}.", "informal_brief", "easy"),
]

# DISEASE + SYMPTOM + CONDITION (Syntactically coordinated, clean search framing)
DISEASE_SYMPTOM_CONDITION_TEMPLATES: list[Template] = [
    Template("dsc_treatment_d_s_c", "Treatment for {D} accompanied by {S} {C}", "search_style", "medium"),
    Template("dsc_meds_d_s_c", "Medicines for {D} and {S} {C}", "search_style", "medium"),
    Template("dsc_managing_d_s_c", "Managing {D} accompanied by {S} {C}", "search_style", "hard"),
    Template("dsc_clinical_mgmt_d_s_c", "Clinical management of {D} and {S} {C}", "search_style", "hard"),
    Template("dsc_therapies_d_s_c", "Therapies for {D} with concurrent {S} {C}", "search_style", "hard"),
    Template("dsc_options_d_s_c", "Treatment options for {D} and {S} {C}", "search_style", "medium"),
    Template("dsc_drug_choices_d_s_c", "Drug choices for {D} with {S} {C}", "search_style", "medium"),
    Template("dsc_pharmacotherapy_d_s_c", "Pharmacotherapy for {D} accompanied by {S} {C}", "search_style", "hard"),

    Template("dsc_dq_what_appropriate_d_s_c", "What treatment is appropriate for {D} accompanied by {S} {C}?", "direct_question", "hard"),
    Template("dsc_dq_which_med_d_s_c", "Which medicine treats {D} accompanied by {S} {C}?", "direct_question", "hard"),
    Template("dsc_dq_options_d_s_c", "What options exist for {D} accompanied by {S} {C}?", "direct_question", "hard"),
    Template("dsc_dq_how_to_treat_d_s_c", "How to treat {D} and relieve {S} {C}?", "direct_question", "hard"),
    Template("dsc_dq_what_drugs_treat_d_s_c", "What drugs treat {D} presenting with {S} {C}?", "direct_question", "hard"),
    Template("dsc_dq_which_therapy_d_s_c", "Which therapy addresses {D} and {S} {C}?", "direct_question", "hard"),
    Template("dsc_dq_what_is_indicated_d_s_c", "What is indicated for {D} accompanied by {S} {C}?", "direct_question", "hard"),

    Template("dsc_act_find_therapies_d_s_c", "Find therapies for {D} accompanied by {S} {C}.", "action_oriented", "hard"),
    Template("dsc_act_show_meds_d_s_c", "Show medicines for {D} and {S} {C}.", "action_oriented", "hard"),
    Template("dsc_act_list_options_d_s_c", "List options for {D} accompanied by {S} {C}.", "action_oriented", "hard"),
    Template("dsc_act_display_drugs_d_s_c", "Display drugs for {D} with concurrent {S} {C}.", "action_oriented", "hard"),

    Template("dsc_help_what_can_help_d_s_c", "What helps treat {D} and relieve {S} {C}?", "can_help_relief", "hard"),
    Template("dsc_help_which_medicine_helps_d_s_c", "Which medicine helps with {D} and {S} {C}?", "can_help_relief", "hard"),

    Template("dsc_inf_meds_d_s_c", "Medicines for {D} with {S} {C}.", "informal_brief", "medium"),
    Template("dsc_inf_treatment_d_s_c", "Treatment for {D} and {S} {C}.", "informal_brief", "medium"),
    Template("dsc_inf_options_d_s_c", "Options for {D} and {S} {C}.", "informal_brief", "medium"),
]

# DISEASE + SYMPTOM + SYMPTOM
DISEASE_SYMPTOM_SYMPTOM_TEMPLATES: list[Template] = [
    Template("dss_meds_d_s1_s2", "Medicines for {D} with {S1} and {S2}", "search_style", "medium"),
    Template("dss_dq_what_suitable_d_s1_s2", "What is suitable for {D} with {S1} and {S2}?", "direct_question", "hard"),
    Template("dss_act_show_meds_d_s1_s2", "Show drugs for {D} accompanied by {S1} and {S2}.", "action_oriented", "hard"),
    Template("dss_treatment_d_s1_s2", "Treatment for {D} presenting with {S1} and {S2}.", "search_style", "medium"),
]

# SYMPTOM + SYMPTOM + CONDITION
SYMPTOM_SYMPTOM_CONDITION_TEMPLATES: list[Template] = [
    Template("ssc_relief_s1_s2_c", "Relief for {S1} and {S2} {C}", "search_style", "medium"),
    Template("ssc_dq_what_relieves_s1_s2_c", "What relieves {S1} and {S2} {C}?", "direct_question", "hard"),
    Template("ssc_act_show_options_s1_s2_c", "Show treatment options for {S1} and {S2} {C}.", "action_oriented", "hard"),
    Template("ssc_meds_s1_s2_c", "Medicines for {S1} and {S2} {C}.", "search_style", "medium"),
]

# 5. Dedicated Boundary Templates
BOUNDARY_PAIR_TEMPLATES: list[Template] = [
    Template("bound_treatment_d_c", "Treatment for {D} {C}", "search_style", "medium"),
    Template("bound_meds_d_c", "Medicines for {D} {C}", "search_style", "medium"),
    Template("bound_options_d_c", "Options for {D} {C}", "search_style", "medium"),
    Template("bound_show_options_d_c", "Show therapeutic options for {D} {C}.", "action_oriented", "hard"),
    Template("bound_dq_which_treats_d_c", "Which medicine treats {D} {C}?", "direct_question", "hard"),
]

# 6. Realistic No-Entity Queries (Clean catalog, packaging, price list searches)
NO_ENTITY_QUERIES: list[tuple[str, str, str]] = [
    ("Show me available medicines.", "ne_available_medicines", "action_oriented"),
    ("Which pharmaceutical products are currently in stock?", "ne_in_stock", "direct_question"),
    ("Show available products in catalog.", "ne_catalog_products", "action_oriented"),
    ("List all approved medicines.", "ne_approved_medicines", "action_oriented"),
    ("What treatments do you have in the inventory?", "ne_inventory_treatments", "direct_question"),
    ("Show available oral tablets.", "ne_oral_tablets", "action_oriented"),
    ("Which injectable solutions are available?", "ne_injectable_solutions", "direct_question"),
    ("Are there capsules available in the inventory?", "ne_capsules_inventory", "direct_question"),
    ("Show blister pack configurations.", "ne_blister_packs", "action_oriented"),
    ("What is the packaging format for vials?", "ne_vial_packaging", "direct_question"),
    ("Display maximum retail prices for catalog medicines.", "ne_display_mrp", "action_oriented"),
    ("Show list of prescription drugs.", "ne_rx_drugs_list", "action_oriented"),
    ("What medicines are available for hospital orders?", "ne_hospital_orders", "direct_question"),
    ("List products manufactured by Sanofi.", "ne_sanofi_products", "action_oriented"),
    ("Display all marketed pharmaceutical brands.", "ne_marketed_brands", "action_oriented"),
    ("What dosage forms are supported in the database?", "ne_dosage_forms", "direct_question"),
    ("Show storage temperature requirements for stored products.", "ne_storage_temp", "action_oriented"),
    ("Which medications require cold chain storage below 25 degrees?", "ne_cold_chain", "direct_question"),
    ("Show package inserts for Sanofi products.", "ne_package_inserts", "action_oriented"),
    ("Are brochures available for download?", "ne_brochures_download", "direct_question"),
    ("Find generic alternatives in the formulary.", "ne_generic_alternatives", "action_oriented"),
    ("Show prescription type classification for listed drugs.", "ne_prescription_type", "action_oriented"),
    ("Which oral formulations come in thirty tablet packs?", "ne_thirty_tablets", "direct_question"),
    ("Display all active pharmaceutical substances in stock.", "ne_active_substances", "action_oriented"),
    ("Show clinical literature references for available brands.", "ne_clinical_literature", "action_oriented"),
    ("Display drug strengths for tablet lines.", "ne_drug_strengths", "action_oriented"),
    ("Show cardiovascular therapeutic category products.", "ne_cardio_category", "action_oriented"),
    ("Which antidiabetic agents are listed in the catalog?", "ne_antidiabetic_catalog", "direct_question"),
    ("Show pharmaceutical suspension products.", "ne_suspension_products", "action_oriented"),
    ("List medicines with intravenous infusion route.", "ne_iv_route", "action_oriented"),
    ("What extended release formulations are available?", "ne_extended_release", "direct_question"),
    ("Show film-coated tablet options.", "ne_film_coated", "action_oriented"),
    ("Find medicines with once-daily dosing.", "ne_once_daily", "action_oriented"),
    ("What products are supplied in prefilled syringes?", "ne_prefilled_syringes", "direct_question"),
    ("Display marketing authorization holder details.", "ne_marketing_auth", "action_oriented"),
    ("How many tablets are in each strip?", "ne_tablets_per_strip", "direct_question"),
    ("Show pricing for blister pack cartons.", "ne_blister_cartons_price", "action_oriented"),
    ("List available medicinal products with oral route.", "ne_oral_route_list", "action_oriented"),
    ("What vial sizes are supplied for hospital distribution?", "ne_vial_sizes_hospital", "direct_question"),
    ("Show shelf life and storage conditions for stock items.", "ne_shelf_life_storage", "action_oriented"),
]


# --------------------------------------------------------------------------
# Condition Phrasing Helper (Strictly follows user CONDITION grammar rules)
# --------------------------------------------------------------------------

def get_condition_phrasings(concept: str) -> list[tuple[str, str]]:
    """
    Returns list of (clean_prepositional_context, exact_concept).
    Strictly conforms to user's condition grammar rules:
      - pregnancy: 'during pregnancy', 'in pregnancy'
      - lactation: 'during lactation'
      - breastfeeding: 'while breastfeeding', 'during breastfeeding'
      - renal impairment: 'in renal impairment', 'in patients with renal impairment'
      - hepatic impairment: 'in hepatic impairment', 'in patients with hepatic impairment'
      - dialysis: 'in patients undergoing dialysis', 'in patients on dialysis', 'during dialysis'
      - elderly: 'in elderly patients', 'for elderly patients'
      - paediatric: 'in paediatric patients', 'for paediatric patients'
    """
    c = concept.lower()
    if c == "pregnancy":
        return [
            ("during pregnancy", "pregnancy"),
            ("in pregnancy", "pregnancy"),
        ]
    elif c == "lactation":
        return [
            ("during lactation", "lactation"),
        ]
    elif c == "breastfeeding":
        return [
            ("while breastfeeding", "breastfeeding"),
            ("during breastfeeding", "breastfeeding"),
        ]
    elif c == "renal impairment":
        return [
            ("in renal impairment", "renal impairment"),
            ("in patients with renal impairment", "renal impairment"),
        ]
    elif c == "hepatic impairment":
        return [
            ("in hepatic impairment", "hepatic impairment"),
            ("in patients with hepatic impairment", "hepatic impairment"),
        ]
    elif c == "dialysis":
        return [
            ("in patients undergoing dialysis", "dialysis"),
            ("in patients on dialysis", "dialysis"),
            ("during dialysis", "dialysis"),
        ]
    elif c == "elderly":
        return [
            ("in elderly patients", "elderly"),
            ("for elderly patients", "elderly"),
        ]
    elif c == "paediatric":
        return [
            ("in paediatric patients", "paediatric"),
            ("for paediatric patients", "paediatric"),
        ]
    else:
        return [(f"in {c}", c)]


def extract_spans(query: str, concepts_with_labels: list[tuple[str, str]]) -> list[dict] | None:
    """
    Locates exact concept spans in normalized query.
    Enforces word boundaries, strict substring match, and no overlaps.
    """
    spans = []
    sorted_cwl = sorted(concepts_with_labels, key=lambda x: len(x[0]), reverse=True)
    occupied = [False] * len(query)

    for concept_text, label in sorted_cwl:
        escaped = re.escape(concept_text)
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        match = re.search(pattern, query)
        if not match:
            return None
        start, end = match.start(), match.end()
        if any(occupied[i] for i in range(start, end)):
            return None
        for i in range(start, end):
            occupied[i] = True
        spans.append({
            "text": query[start:end],
            "label": label,
            "start": start,
            "end": end,
        })

    spans.sort(key=lambda s: s["start"])
    return spans


# --------------------------------------------------------------------------
# Generator Class
# --------------------------------------------------------------------------

class V2DatasetGenerator:
    def __init__(self, bank_path: Path, unseen_path: Path, seed: int = 42):
        self.rng = random.Random(seed)
        self.bank_path = bank_path
        self.unseen_path = unseen_path

        with bank_path.open("r", encoding="utf-8") as f:
            bank = json.load(f)
        with unseen_path.open("r", encoding="utf-8") as f:
            unseen = json.load(f)

        self.diseases = [c["concept"] for c in bank["concepts"]["DISEASE"]]
        self.symptoms = [c["concept"] for c in bank["concepts"]["SYMPTOM"]]
        self.conditions = [c["concept"] for c in bank["concepts"]["CONDITION"]]
        self.all_concepts = set(self.diseases + self.symptoms + self.conditions)

        # Assertion: Zero unseen concept leakage
        unseen_set = set()
        for lab in ("DISEASE", "SYMPTOM", "CONDITION"):
            for c in unseen["concepts"].get(lab, []):
                unseen_set.add(c.lower())
        overlap = self.all_concepts & unseen_set
        if overlap:
            raise ValueError(f"FATAL: bank and unseen overlap: {overlap}")

        self.difficult_diseases = [d for d in self.diseases if len(d.split()) >= 2]
        self.difficult_symptoms = [s for s in self.symptoms if len(s.split()) >= 2]
        self.difficult_conditions = [c for c in self.conditions if len(c.split()) >= 2]

        self.frame_concept_usage: dict[tuple[str, str], int] = defaultdict(int)
        self.seen_normalized_queries: set[str] = set()
        self.records: list[dict] = []

    def can_use_frame(self, concept: str, frame_id: str) -> bool:
        return self.frame_concept_usage[(concept.lower(), frame_id)] < 2

    def record_frame_usage(self, concept: str, frame_id: str):
        self.frame_concept_usage[(concept.lower(), frame_id)] += 1

    def add_query(self, raw_text: str, concepts_with_labels: list[tuple[str, str]],
                  category: str, style: str, difficulty: str, frame_id: str) -> bool:
        # Rule: Never pair synonymous conditions breastfeeding and lactation together
        concepts_lower = [c.lower() for c, _ in concepts_with_labels]
        if "breastfeeding" in concepts_lower and "lactation" in concepts_lower:
            return False

        pre = normalize_query(raw_text)
        norm_text = pre.normalized
        if not norm_text:
            return False
        if norm_text in self.seen_normalized_queries:
            return False

        if concepts_with_labels:
            spans = extract_spans(norm_text, concepts_with_labels)
            if spans is None or len(spans) != len(concepts_with_labels):
                return False
            for s in spans:
                if norm_text[s["start"]:s["end"]] != s["text"]:
                    return False
        else:
            spans = []

        # Check frame usage ceiling (max 2 per concept)
        for concept, _ in concepts_with_labels:
            if not self.can_use_frame(concept, frame_id):
                return False

        for concept, _ in concepts_with_labels:
            self.record_frame_usage(concept, frame_id)

        self.seen_normalized_queries.add(norm_text)
        self.records.append({
            "query": norm_text,
            "entities": spans,
            "category": category,
            "style": style,
            "difficulty": difficulty,
            "source_concepts": [c for c, _ in concepts_with_labels],
            "frame_id": frame_id,
        })
        return True

    def generate_single_disease(self, target: int = 350):
        added = 0
        concepts = list(self.diseases)
        self.rng.shuffle(concepts)
        templates = list(DISEASE_TEMPLATES)

        while added < target:
            made_progress = False
            for d in concepts:
                if added >= target:
                    break
                self.rng.shuffle(templates)
                for t in templates:
                    if self.can_use_frame(d, t.frame_id):
                        raw = t.template.format(D=d)
                        if self.add_query(raw, [(d, "DISEASE")], "single_disease", t.style, t.difficulty, t.frame_id):
                            added += 1
                            made_progress = True
                            break
            if not made_progress:
                break
        print(f"Generated {added} single_disease queries.")

    def generate_single_symptom(self, target: int = 300):
        added = 0
        concepts = list(self.symptoms)
        self.rng.shuffle(concepts)
        templates = list(SYMPTOM_TEMPLATES)

        while added < target:
            made_progress = False
            for s in concepts:
                if added >= target:
                    break
                self.rng.shuffle(templates)
                for t in templates:
                    if self.can_use_frame(s, t.frame_id):
                        raw = t.template.format(S=s)
                        if self.add_query(raw, [(s, "SYMPTOM")], "single_symptom", t.style, t.difficulty, t.frame_id):
                            added += 1
                            made_progress = True
                            break
            if not made_progress:
                break
        print(f"Generated {added} single_symptom queries.")

    def generate_single_condition(self, target: int = 100):
        added = 0
        concepts = list(self.conditions)
        templates = list(CONDITION_TEMPLATES)

        while added < target:
            made_progress = False
            for c in concepts:
                if added >= target:
                    break
                phrasings = get_condition_phrasings(c)
                self.rng.shuffle(phrasings)
                self.rng.shuffle(templates)
                for full_c_phrase, concept_exact in phrasings:
                    for t in templates:
                        if self.can_use_frame(concept_exact, t.frame_id):
                            raw = t.template.format(C=full_c_phrase)
                            if self.add_query(raw, [(concept_exact, "CONDITION")], "single_condition", t.style, t.difficulty, t.frame_id):
                                added += 1
                                made_progress = True
                                break
                    if made_progress:
                        break
            if not made_progress:
                break
        print(f"Generated {added} single_condition queries.")

    def generate_bare_concepts(self, target: int = 20):
        added = 0
        sample_d = self.rng.sample(self.diseases, 9)
        sample_s = self.rng.sample(self.symptoms, 8)
        sample_c = self.rng.sample(self.conditions, 3)

        for d in sample_d:
            if self.add_query(d, [(d, "DISEASE")], "bare_concept", "bare_concept", "easy", "bare_d"):
                added += 1
        for s in sample_s:
            if self.add_query(s, [(s, "SYMPTOM")], "bare_concept", "bare_concept", "easy", "bare_s"):
                added += 1
        for c in sample_c:
            if self.add_query(c, [(c, "CONDITION")], "bare_concept", "bare_concept", "easy", "bare_c"):
                added += 1
        print(f"Generated {added} bare concept queries.")

    def generate_disease_condition(self, target: int = 700):
        """Cornerstone category: directly teaches DISEASE vs CONDITION boundary and extensive co-occurrence."""
        added = 0
        templates = list(DISEASE_CONDITION_TEMPLATES)
        attempts = 0

        while added < target and attempts < target * 25:
            attempts += 1
            d = self.rng.choice(self.diseases)
            c = self.rng.choice(self.conditions)
            phrasing, c_exact = self.rng.choice(get_condition_phrasings(c))
            t = self.rng.choice(templates)
            if self.can_use_frame(d, t.frame_id) and self.can_use_frame(c_exact, t.frame_id):
                raw = t.template.format(D=d, C=phrasing)
                if self.add_query(raw, [(d, "DISEASE"), (c_exact, "CONDITION")], "disease_condition", t.style, t.difficulty, t.frame_id):
                    added += 1
        print(f"Generated {added} disease_condition queries.")

    def generate_disease_symptom(self, target: int = 500):
        added = 0
        templates = list(DISEASE_SYMPTOM_TEMPLATES)
        attempts = 0

        while added < target and attempts < target * 25:
            attempts += 1
            d = self.rng.choice(self.diseases)
            s = self.rng.choice(self.symptoms)
            t = self.rng.choice(templates)
            if self.can_use_frame(d, t.frame_id) and self.can_use_frame(s, t.frame_id):
                raw = t.template.format(D=d, S=s)
                if self.add_query(raw, [(d, "DISEASE"), (s, "SYMPTOM")], "disease_symptom", t.style, t.difficulty, t.frame_id):
                    added += 1
        print(f"Generated {added} disease_symptom queries.")

    def generate_disease_symptom_condition(self, target: int = 400):
        added = 0
        templates = list(DISEASE_SYMPTOM_CONDITION_TEMPLATES)
        attempts = 0

        while added < target and attempts < target * 30:
            attempts += 1
            d = self.rng.choice(self.diseases)
            s = self.rng.choice(self.symptoms)
            c = self.rng.choice(self.conditions)
            phrasing, c_exact = self.rng.choice(get_condition_phrasings(c))
            t = self.rng.choice(templates)
            if self.can_use_frame(d, t.frame_id) and self.can_use_frame(s, t.frame_id) and self.can_use_frame(c_exact, t.frame_id):
                raw = t.template.format(D=d, S=s, C=phrasing)
                if self.add_query(raw, [(d, "DISEASE"), (s, "SYMPTOM"), (c_exact, "CONDITION")], "disease_symptom_condition", t.style, t.difficulty, t.frame_id):
                    added += 1
        print(f"Generated {added} disease_symptom_condition queries.")

    def generate_symptom_condition(self, target: int = 350):
        added = 0
        templates = list(SYMPTOM_CONDITION_TEMPLATES)
        attempts = 0

        while added < target and attempts < target * 25:
            attempts += 1
            s = self.rng.choice(self.symptoms)
            c = self.rng.choice(self.conditions)
            phrasing, c_exact = self.rng.choice(get_condition_phrasings(c))
            t = self.rng.choice(templates)
            if self.can_use_frame(s, t.frame_id) and self.can_use_frame(c_exact, t.frame_id):
                raw = t.template.format(S=s, C=phrasing)
                if self.add_query(raw, [(s, "SYMPTOM"), (c_exact, "CONDITION")], "symptom_condition", t.style, t.difficulty, t.frame_id):
                    added += 1
        print(f"Generated {added} symptom_condition queries.")

    def generate_symptom_symptom(self, target: int = 150):
        added = 0
        templates = list(SYMPTOM_SYMPTOM_TEMPLATES)
        attempts = 0

        while added < target and attempts < target * 20:
            attempts += 1
            s1, s2 = self.rng.sample(self.symptoms, 2)
            if s1.split()[0].lower() == s2.split()[0].lower():
                continue
            t = self.rng.choice(templates)
            if self.can_use_frame(s1, t.frame_id) and self.can_use_frame(s2, t.frame_id):
                raw = t.template.format(S1=s1, S2=s2)
                if self.add_query(raw, [(s1, "SYMPTOM"), (s2, "SYMPTOM")], "multiple_same_type", t.style, t.difficulty, t.frame_id):
                    added += 1
        print(f"Generated {added} symptom_symptom queries.")

    def generate_other_three_entity(self, target: int = 250):
        added = 0
        dss_templates = list(DISEASE_SYMPTOM_SYMPTOM_TEMPLATES)
        ssc_templates = list(SYMPTOM_SYMPTOM_CONDITION_TEMPLATES)

        attempts = 0
        while added < target and attempts < target * 25:
            attempts += 1
            roll = self.rng.random()
            if roll < 0.60:
                # D + S1 + S2
                d = self.rng.choice(self.diseases)
                s1, s2 = self.rng.sample(self.symptoms, 2)
                if s1.split()[0].lower() == s2.split()[0].lower():
                    continue
                t = self.rng.choice(dss_templates)
                if self.can_use_frame(d, t.frame_id) and self.can_use_frame(s1, t.frame_id) and self.can_use_frame(s2, t.frame_id):
                    raw = t.template.format(D=d, S1=s1, S2=s2)
                    if self.add_query(raw, [(d, "DISEASE"), (s1, "SYMPTOM"), (s2, "SYMPTOM")], "three_entity_dss", t.style, t.difficulty, t.frame_id):
                        added += 1
            else:
                # S1 + S2 + C
                s1, s2 = self.rng.sample(self.symptoms, 2)
                if s1.split()[0].lower() == s2.split()[0].lower():
                    continue
                c = self.rng.choice(self.conditions)
                phrasing, c_exact = self.rng.choice(get_condition_phrasings(c))
                t = self.rng.choice(ssc_templates)
                if self.can_use_frame(s1, t.frame_id) and self.can_use_frame(s2, t.frame_id) and self.can_use_frame(c_exact, t.frame_id):
                    raw = t.template.format(S1=s1, S2=s2, C=phrasing)
                    if self.add_query(raw, [(s1, "SYMPTOM"), (s2, "SYMPTOM"), (c_exact, "CONDITION")], "three_entity_ssc", t.style, t.difficulty, t.frame_id):
                        added += 1
        print(f"Generated {added} other_three_entity queries.")

    def generate_boundary_pairs(self, target: int = 250):
        """
        Explicit boundary queries:
          1. acute renal failure (DISEASE) vs renal impairment (CONDITION)
          2. autoimmune hepatitis (DISEASE) vs hepatic impairment (CONDITION)
          3. cardiac insufficiency (DISEASE) vs elderly / renal impairment (CONDITION)
          4. Seizure cluster:
             - seizures (SYMPTOM)
             - complex partial seizures (DISEASE)
             - simple and complex absence seizures (DISEASE)
          5. Multi-word disease boundary queries paired with conditions.
        """
        added = 0
        templates = list(BOUNDARY_PAIR_TEMPLATES)

        # 1. Acute renal failure vs Renal impairment (contrast & co-occurrence)
        arf_queries = [
            ("Management of acute renal failure in patients with renal impairment",
             [("acute renal failure", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_arf_ri_1"),
            ("Treatment options for acute renal failure in patients with renal impairment",
             [("acute renal failure", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_arf_ri_2"),
            ("Medicines for acute renal failure in patients with renal impairment",
             [("acute renal failure", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_arf_ri_3"),
            ("Drug choices for acute renal failure in patients with renal impairment",
             [("acute renal failure", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_arf_ri_4"),
            ("Which medicine treats acute renal failure in renal impairment?",
             [("acute renal failure", "DISEASE"), ("renal impairment", "CONDITION")], "direct_question", "b_arf_ri_5"),
            ("Therapies indicated for acute renal failure in renal impairment",
             [("acute renal failure", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_arf_ri_6"),
            ("Treatment for acute renal failure in elderly patients",
             [("acute renal failure", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_arf_eld_1"),
            ("Medicines for acute renal failure in elderly patients",
             [("acute renal failure", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_arf_eld_2"),
            ("Therapies indicated for acute renal failure in paediatric patients",
             [("acute renal failure", "DISEASE"), ("paediatric", "CONDITION")], "search_style", "b_arf_paed_1"),
            ("Treatment for acute renal failure during pregnancy",
             [("acute renal failure", "DISEASE"), ("pregnancy", "CONDITION")], "search_style", "b_arf_preg_1"),
            ("Managing acute renal failure in patients on dialysis",
             [("acute renal failure", "DISEASE"), ("dialysis", "CONDITION")], "search_style", "b_arf_dial_1"),
            # Diseases with renal impairment context
            ("Medication for conjunctivitis in patients with renal impairment",
             [("conjunctivitis", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_conj_ri_1"),
            ("Treatment for cardiac insufficiency in patients with renal impairment",
             [("cardiac insufficiency", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_ci_ri_1"),
            ("Medicines for sinusitis in patients with renal impairment",
             [("sinusitis", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_sin_ri_1"),
            ("Prescription options for angina in patients with renal impairment",
             [("angina", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_ang_ri_1"),
            ("Therapies for hyperglycemia in patients with renal impairment",
             [("hyperglycemia", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_hg_ri_1"),
            ("Treatment for stroke in patients with renal impairment",
             [("stroke", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_str_ri_1"),
            # Conditions standalone
            ("Dose adjustment in renal impairment",
             [("renal impairment", "CONDITION")], "search_style", "b_ri_alone_1"),
            ("Medicines suitable in patients with renal impairment",
             [("renal impairment", "CONDITION")], "search_style", "b_ri_alone_2"),
            ("Which drugs are permitted in renal impairment?",
             [("renal impairment", "CONDITION")], "direct_question", "b_ri_alone_3"),
            ("Treatment in renal impairment",
             [("renal impairment", "CONDITION")], "search_style", "b_ri_alone_4"),
        ]
        for q, spans, st, fid in arf_queries:
            if self.add_query(q, spans, "difficult_boundary_cases", st, "hard", fid):
                added += 1

        # 2. Autoimmune hepatitis vs Hepatic impairment
        hep_queries = [
            ("Treatment for autoimmune hepatitis in patients with hepatic impairment",
             [("autoimmune hepatitis", "DISEASE"), ("hepatic impairment", "CONDITION")], "search_style", "b_hep_hi_1"),
            ("Which medicines treat autoimmune hepatitis in hepatic impairment?",
             [("autoimmune hepatitis", "DISEASE"), ("hepatic impairment", "CONDITION")], "direct_question", "b_hep_hi_2"),
            ("Treatment for autoimmune hepatitis while breastfeeding",
             [("autoimmune hepatitis", "DISEASE"), ("breastfeeding", "CONDITION")], "search_style", "b_hep_bf_1"),
            ("Medicines for autoimmune hepatitis during pregnancy",
             [("autoimmune hepatitis", "DISEASE"), ("pregnancy", "CONDITION")], "search_style", "b_hep_preg_1"),
            ("Managing autoimmune hepatitis in elderly patients",
             [("autoimmune hepatitis", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_hep_eld_1"),
            ("Treatment in hepatic impairment",
             [("hepatic impairment", "CONDITION")], "search_style", "b_hi_alone_1"),
            ("Dose adjustment in hepatic impairment",
             [("hepatic impairment", "CONDITION")], "search_style", "b_hi_alone_2"),
            ("Which medicines are suitable in hepatic impairment?",
             [("hepatic impairment", "CONDITION")], "direct_question", "b_hi_alone_3"),
        ]
        for q, spans, st, fid in hep_queries:
            if self.add_query(q, spans, "difficult_boundary_cases", st, "hard", fid):
                added += 1

        # 3. Cardiac / Elderly / Dialysis Boundaries
        cardio_queries = [
            ("Treatment for cardiac insufficiency in elderly patients",
             [("cardiac insufficiency", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_ci_eld_1"),
            ("Medication options for cardiac insufficiency in elderly patients",
             [("cardiac insufficiency", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_ci_eld_2"),
            ("Therapies for cardiac insufficiency in elderly patients",
             [("cardiac insufficiency", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_ci_eld_3"),
            ("Treatment for cardiomegaly in elderly patients",
             [("cardiomegaly", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_cm_eld_1"),
            ("Managing cardiomegaly in elderly patients",
             [("cardiomegaly", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_cm_eld_2"),
            ("Therapies for anaemia in patients on dialysis",
             [("anaemia", "DISEASE"), ("dialysis", "CONDITION")], "search_style", "b_ana_dial_1"),
            ("Treatment for stroke in elderly patients",
             [("stroke", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_str_eld_1"),
            ("Medicines for hyperglycemia during pregnancy",
             [("hyperglycemia", "DISEASE"), ("pregnancy", "CONDITION")], "search_style", "b_hg_preg_1"),
        ]
        for q, spans, st, fid in cardio_queries:
            if self.add_query(q, spans, "difficult_boundary_cases", st, "hard", fid):
                added += 1

        # 4. Seizure cluster: Option A
        seizure_queries = [
            # seizures -> SYMPTOM
            ("Treatment for seizures", [("seizures", "SYMPTOM")], "search_style", "b_sz_1"),
            ("Medicines for seizures", [("seizures", "SYMPTOM")], "search_style", "b_sz_2"),
            ("What medicine relieves acute seizures?", [("seizures", "SYMPTOM")], "direct_question", "b_sz_3"),
            ("Medication needed to stop seizures", [("seizures", "SYMPTOM")], "search_style", "b_sz_4"),
            ("What helps reduce seizures?", [("seizures", "SYMPTOM")], "direct_question", "b_sz_5"),
            ("Which drug relieves acute seizures?", [("seizures", "SYMPTOM")], "direct_question", "b_sz_6"),
            ("Treatment for seizures during pregnancy", [("seizures", "SYMPTOM"), ("pregnancy", "CONDITION")], "search_style", "b_sz_preg_1"),
            ("Management of seizures in elderly patients", [("seizures", "SYMPTOM"), ("elderly", "CONDITION")], "search_style", "b_sz_eld_1"),
            ("Therapies for seizures in paediatric patients", [("seizures", "SYMPTOM"), ("paediatric", "CONDITION")], "search_style", "b_sz_paed_1"),
            ("Relief for seizures while breastfeeding", [("seizures", "SYMPTOM"), ("breastfeeding", "CONDITION")], "search_style", "b_sz_bf_1"),
            ("Medication to relieve seizures in patients on dialysis", [("seizures", "SYMPTOM"), ("dialysis", "CONDITION")], "search_style", "b_sz_dial_1"),

            # complex partial seizures -> DISEASE
            ("Treatment for complex partial seizures", [("complex partial seizures", "DISEASE")], "search_style", "b_cps_1"),
            ("Which medicines are used for complex partial seizures?", [("complex partial seizures", "DISEASE")], "direct_question", "b_cps_2"),
            ("What drugs are indicated for complex partial seizures?", [("complex partial seizures", "DISEASE")], "direct_question", "b_cps_3"),
            ("Prescription options for complex partial seizures", [("complex partial seizures", "DISEASE")], "search_style", "b_cps_4"),
            ("How is complex partial seizures treated?", [("complex partial seizures", "DISEASE")], "direct_question", "b_cps_5"),
            ("Find approved drugs for complex partial seizures", [("complex partial seizures", "DISEASE")], "action_oriented", "b_cps_6"),
            ("Treatment for complex partial seizures in paediatric patients", [("complex partial seizures", "DISEASE"), ("paediatric", "CONDITION")], "search_style", "b_cps_paed_1"),
            ("Therapy options for complex partial seizures in elderly patients", [("complex partial seizures", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_cps_eld_1"),
            ("Managing complex partial seizures during pregnancy", [("complex partial seizures", "DISEASE"), ("pregnancy", "CONDITION")], "search_style", "b_cps_preg_1"),
            ("Therapies for complex partial seizures in patients with renal impairment", [("complex partial seizures", "DISEASE"), ("renal impairment", "CONDITION")], "search_style", "b_cps_ri_1"),

            # simple and complex absence seizures -> DISEASE
            ("Medication for simple and complex absence seizures", [("simple and complex absence seizures", "DISEASE")], "search_style", "b_cas_1"),
            ("Treatment for simple and complex absence seizures", [("simple and complex absence seizures", "DISEASE")], "search_style", "b_cas_2"),
            ("Which medications are indicated for simple and complex absence seizures?", [("simple and complex absence seizures", "DISEASE")], "direct_question", "b_cas_4"),
            ("Therapies indicated for simple and complex absence seizures", [("simple and complex absence seizures", "DISEASE")], "search_style", "b_cas_5"),
            ("Treatment options for simple and complex absence seizures", [("simple and complex absence seizures", "DISEASE")], "search_style", "b_cas_6"),
            ("Treatment for simple and complex absence seizures in paediatric patients", [("simple and complex absence seizures", "DISEASE"), ("paediatric", "CONDITION")], "search_style", "b_cas_paed_1"),
            ("Management of simple and complex absence seizures in elderly patients", [("simple and complex absence seizures", "DISEASE"), ("elderly", "CONDITION")], "search_style", "b_cas_eld_1"),
        ]
        for q, spans, st, fid in seizure_queries:
            if self.add_query(q, spans, "difficult_boundary_cases", st, "hard", fid):
                added += 1

        # 5. Multi-word diseases with conditions
        for d in self.difficult_diseases[:35]:
            c = self.rng.choice(self.conditions)
            phrasing, c_exact = self.rng.choice(get_condition_phrasings(c))
            t = self.rng.choice(templates)
            raw = t.template.format(D=d, C=phrasing)
            if self.add_query(raw, [(d, "DISEASE"), (c_exact, "CONDITION")], "difficult_boundary_cases", t.style, "hard", f"diff_d_c_{t.frame_id}"):
                added += 1

        print(f"Generated {added} explicit boundary pair queries.")

    def generate_no_entity(self, target: int = 130):
        """Clean catalog, formulation, packaging queries with zero medical entities."""
        added = 0
        pool = list(NO_ENTITY_QUERIES)
        self.rng.shuffle(pool)

        for q, fid, style in pool:
            if added >= target:
                break
            if self.add_query(q, [], "no_entity", style, "easy", fid):
                added += 1

        prefixes = ["", "Please ", "Where can I ", "I need to ", "Kindly "]
        suffixes = ["", " in stock", " from distributor", " in current inventory", " available for order", " listed in database"]

        attempts = 0
        while added < target and attempts < target * 10:
            attempts += 1
            base_q, base_fid, style = self.rng.choice(pool)
            p = self.rng.choice(prefixes)
            s = self.rng.choice(suffixes)
            if "available" in base_q.lower() and "available" in s.lower():
                continue
            if "stock" in base_q.lower() and "stock" in s.lower():
                continue
            if "inventory" in base_q.lower() and "inventory" in s.lower():
                continue
            text = f"{p}{base_q.rstrip('.?')}{s}."
            fid = f"{base_fid}_v"
            if self.add_query(text, [], "no_entity", style, "easy", fid):
                added += 1

        print(f"Generated {added} no_entity queries.")

    def fill_remaining_to_target(self, target_total: int = 3500):
        current = len(self.records)
        shortfall = target_total - current
        if shortfall <= 0:
            return
        print(f"Generating {shortfall} balanced combination queries to reach exact target of {target_total}...")

        attempts = 0
        while len(self.records) < target_total and attempts < shortfall * 30:
            attempts += 1
            roll = self.rng.random()
            if roll < 0.40:
                # Disease + Condition (reinforce key boundary)
                d = self.rng.choice(self.diseases)
                c = self.rng.choice(self.conditions)
                phrasing, c_exact = self.rng.choice(get_condition_phrasings(c))
                t = self.rng.choice(DISEASE_CONDITION_TEMPLATES)
                if self.can_use_frame(d, t.frame_id) and self.can_use_frame(c_exact, t.frame_id):
                    raw = t.template.format(D=d, C=phrasing)
                    self.add_query(raw, [(d, "DISEASE"), (c_exact, "CONDITION")], "disease_condition", t.style, t.difficulty, t.frame_id)
            elif roll < 0.65:
                # Disease + Symptom
                d = self.rng.choice(self.diseases)
                s = self.rng.choice(self.symptoms)
                t = self.rng.choice(DISEASE_SYMPTOM_TEMPLATES)
                if self.can_use_frame(d, t.frame_id) and self.can_use_frame(s, t.frame_id):
                    raw = t.template.format(D=d, S=s)
                    self.add_query(raw, [(d, "DISEASE"), (s, "SYMPTOM")], "disease_symptom", t.style, t.difficulty, t.frame_id)
            elif roll < 0.85:
                # Disease + Symptom + Condition
                d = self.rng.choice(self.diseases)
                s = self.rng.choice(self.symptoms)
                c = self.rng.choice(self.conditions)
                phrasing, c_exact = self.rng.choice(get_condition_phrasings(c))
                t = self.rng.choice(DISEASE_SYMPTOM_CONDITION_TEMPLATES)
                if self.can_use_frame(d, t.frame_id) and self.can_use_frame(s, t.frame_id) and self.can_use_frame(c_exact, t.frame_id):
                    raw = t.template.format(D=d, S=s, C=phrasing)
                    self.add_query(raw, [(d, "DISEASE"), (s, "SYMPTOM"), (c_exact, "CONDITION")], "disease_symptom_condition", t.style, t.difficulty, t.frame_id)
            elif roll < 0.95:
                # Symptom + Condition
                s = self.rng.choice(self.symptoms)
                c = self.rng.choice(self.conditions)
                phrasing, c_exact = self.rng.choice(get_condition_phrasings(c))
                t = self.rng.choice(SYMPTOM_CONDITION_TEMPLATES)
                if self.can_use_frame(s, t.frame_id) and self.can_use_frame(c_exact, t.frame_id):
                    raw = t.template.format(S=s, C=phrasing)
                    self.add_query(raw, [(s, "SYMPTOM"), (c_exact, "CONDITION")], "symptom_condition", t.style, t.difficulty, t.frame_id)
            else:
                # Single disease or symptom to balance concept coverage
                if self.rng.random() < 0.5:
                    d = self.rng.choice(self.diseases)
                    t = self.rng.choice(DISEASE_TEMPLATES)
                    if self.can_use_frame(d, t.frame_id):
                        raw = t.template.format(D=d)
                        self.add_query(raw, [(d, "DISEASE")], "single_disease", t.style, t.difficulty, t.frame_id)
                else:
                    s = self.rng.choice(self.symptoms)
                    t = self.rng.choice(SYMPTOM_TEMPLATES)
                    if self.can_use_frame(s, t.frame_id):
                        raw = t.template.format(S=s)
                        self.add_query(raw, [(s, "SYMPTOM")], "single_symptom", t.style, t.difficulty, t.frame_id)

    def generate_all(self, target_total: int = 3500) -> list[dict]:
        self.generate_single_disease(350)
        self.generate_single_symptom(300)
        self.generate_single_condition(100)
        self.generate_bare_concepts(20)
        self.generate_disease_condition(700)
        self.generate_disease_symptom(500)
        self.generate_disease_symptom_condition(400)
        self.generate_symptom_condition(350)
        self.generate_symptom_symptom(150)
        self.generate_other_three_entity(250)
        self.generate_boundary_pairs(250)
        self.generate_no_entity(130)

        self.fill_remaining_to_target(target_total)
        print(f"Total unique queries generated: {len(self.records)}")
        return self.records


# --------------------------------------------------------------------------
# Stratified 90/10 Splitter
# --------------------------------------------------------------------------

def stratified_split(records: list[dict], train_ratio: float = 0.90, seed: int = 42) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    total = len(records)
    target_dev = int(total * (1.0 - train_ratio))

    buckets = defaultdict(list)
    for r in records:
        key = (r["category"], len(r["entities"]), r["style"])
        buckets[key].append(r)

    train: list[dict] = []
    dev: list[dict] = []

    concept_in_dev = Counter()
    concept_in_train = Counter()

    for key, bucket in buckets.items():
        rng.shuffle(bucket)
        n_dev = int(len(bucket) * (1.0 - train_ratio))
        if n_dev == 0 and len(bucket) >= 4 and len(dev) < target_dev:
            n_dev = 1

        dev_slice = bucket[:n_dev]
        train_slice = bucket[n_dev:]

        dev.extend(dev_slice)
        train.extend(train_slice)

        for r in dev_slice:
            for c in r["source_concepts"]:
                concept_in_dev[c] += 1
        for r in train_slice:
            for c in r["source_concepts"]:
                concept_in_train[c] += 1

    # Guarantee that 100% of concepts present in the dataset have at least 1 representation in dev
    all_dataset_concepts = {c for r in records for c in r["source_concepts"]}
    for c in sorted(all_dataset_concepts):
        if concept_in_dev[c] == 0:
            train_candidates = [r for r in train if c in r["source_concepts"]]
            if train_candidates:
                picked = train_candidates[0]
                train.remove(picked)
                dev.append(picked)
                for sc in picked["source_concepts"]:
                    concept_in_train[sc] -= 1
                    concept_in_dev[sc] += 1
                donor_candidates = [
                    r for r in dev
                    if all(concept_in_dev[sc] >= 2 for sc in r["source_concepts"])
                ]
                if donor_candidates:
                    donor = donor_candidates[0]
                    dev.remove(donor)
                    train.append(donor)
                    for sc in donor["source_concepts"]:
                        concept_in_dev[sc] -= 1
                        concept_in_train[sc] += 1

    rng.shuffle(train)
    rng.shuffle(dev)

    print(f"Stratified split complete: {len(train)} train ({(len(train)/total)*100:.1f}%), {len(dev)} dev ({(len(dev)/total)*100:.1f}%)")
    return train, dev


def compute_coverage_matrix(train: list[dict], dev: list[dict], seed: int) -> dict:
    def stats(records: list[dict]) -> dict:
        total = len(records)
        by_cat = Counter(r["category"] for r in records)
        by_diff = Counter(r["difficulty"] for r in records)
        by_style = Counter(r["style"] for r in records)
        by_n_ents = Counter(len(r["entities"]) for r in records)
        ents_by_label = Counter(e["label"] for r in records for e in r["entities"])
        concept_counts = Counter(c for r in records for c in r["source_concepts"])

        return {
            "total_queries": total,
            "queries_by_category": dict(sorted(by_cat.items())),
            "queries_by_style": dict(sorted(by_style.items())),
            "queries_by_difficulty": dict(sorted(by_diff.items())),
            "queries_by_entity_count": {str(k): v for k, v in sorted(by_n_ents.items())},
            "entities_by_label": dict(sorted(ents_by_label.items())),
            "distinct_concepts_covered": len(concept_counts),
        }

    return {
        "seed": seed,
        "train": stats(train),
        "dev": stats(dev),
        "total": stats(train + dev),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate refined V2 NER query dataset (~3,500 queries).")
    parser.add_argument("--bank", type=Path, default=PROJECT_ROOT / "data/terminology/terminology_bank.json")
    parser.add_argument("--unseen", type=Path, default=PROJECT_ROOT / "data/terminology/unseen_eval_concepts.json")
    parser.add_argument("--outdir", type=Path, default=PROJECT_ROOT / "data/training_v2")
    parser.add_argument("--target", type=int, default=3500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    generator = V2DatasetGenerator(args.bank, args.unseen, seed=args.seed)
    all_records = generator.generate_all(target_total=args.target)

    train, dev = stratified_split(all_records, train_ratio=0.90, seed=args.seed)
    coverage = compute_coverage_matrix(train, dev, seed=args.seed)

    train_path = args.outdir / "train.json"
    dev_path = args.outdir / "dev.json"
    all_path = args.outdir / "all_generated.json"
    cov_path = args.outdir / "coverage_matrix.json"

    with train_path.open("w", encoding="utf-8") as f:
        json.dump(train, f, ensure_ascii=False, indent=2)
    with dev_path.open("w", encoding="utf-8") as f:
        json.dump(dev, f, ensure_ascii=False, indent=2)
    with all_path.open("w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    with cov_path.open("w", encoding="utf-8") as f:
        json.dump(coverage, f, ensure_ascii=False, indent=2)

    print(f"\nFiles written to {args.outdir}:")
    print(f"  train.json:         {len(train)} queries")
    print(f"  dev.json:           {len(dev)} queries")
    print(f"  all_generated.json: {len(all_records)} queries")
    print(f"  coverage_matrix.json")


if __name__ == "__main__":
    main()
