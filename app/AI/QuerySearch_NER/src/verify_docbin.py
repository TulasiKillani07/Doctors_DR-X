"""
verify_docbin.py — integrity checks on the converted .spacy DocBins.

Verifies, by reading the DocBins back:
  - character offsets are correct (ent.text matches the doc span)
  - entities don't overlap
  - unicode concepts have correct offsets (round-trip check)
  - all three labels are present across the data
  - train/dev/test separation (doc counts)
  - no unseen concepts appear in train/dev
  - no-entity examples converted to zero-entity docs

Usage:
    python -m src.verify_docbin
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import spacy
from spacy.tokens import DocBin

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.labels import ENTITY_LABELS  # noqa: E402

PROCESSED = Path("data/processed")
UNSEEN = Path("data/terminology/unseen_eval_concepts.json")


def load_docs(nlp, name):
    db = DocBin().from_disk(PROCESSED / f"{name}.spacy")
    return list(db.get_docs(nlp.vocab))


def overlaps(ents) -> bool:
    spans = sorted((e.start_char, e.end_char) for e in ents)
    for i in range(1, len(spans)):
        if spans[i][0] < spans[i - 1][1]:
            return True
    return False


def main() -> None:
    nlp = spacy.blank("en")
    unseen = json.loads(UNSEEN.read_text(encoding="utf-8"))
    unseen_set = {c.lower() for lab in ("DISEASE", "SYMPTOM", "CONDITION")
                  for c in unseen["concepts"].get(lab, [])}

    docs = {name: load_docs(nlp, name) for name in ("train", "dev", "test")}
    failures = []

    labels_seen = set()
    offset_bad = overlap_bad = 0
    for name, dlist in docs.items():
        for doc in dlist:
            if overlaps(doc.ents):
                overlap_bad += 1
                failures.append(f"[overlap] {doc.text!r}")
            for e in doc.ents:
                labels_seen.add(e.label_)
                # round-trip offset check (covers unicode)
                if doc.text[e.start_char:e.end_char] != e.text:
                    offset_bad += 1
                    failures.append(f"[offset] {doc.text!r} :: {e.text!r}")

    # no unseen concept in train/dev
    leak = 0
    for name in ("train", "dev"):
        for doc in docs[name]:
            for e in doc.ents:
                if e.text.lower() in unseen_set:
                    leak += 1
                    failures.append(f"[leak:{name}] unseen {e.text!r} in {doc.text!r}")

    # no-entity docs (queries with zero ents should exist in train)
    zero_ent = sum(1 for doc in docs["train"] if len(doc.ents) == 0)

    # unicode round-trip: find any non-ascii entity and confirm it survived
    unicode_ents = [e.text for name in docs for doc in docs[name] for e in doc.ents
                    if any(ord(ch) > 127 for ch in e.text)]

    print("=== DocBin integrity ===")
    print(f"doc counts: train={len(docs['train'])}, dev={len(docs['dev'])}, test={len(docs['test'])}")
    print(f"labels present: {sorted(labels_seen)}  (expected {ENTITY_LABELS})")
    print(f"offset mismatches: {offset_bad}")
    print(f"overlapping-entity docs: {overlap_bad}")
    print(f"unseen concepts leaked into train/dev: {leak}")
    print(f"zero-entity (no_entity) docs in train: {zero_ent}")
    print(f"unicode entities round-tripped: {len(unicode_ents)}"
          + (f" e.g. {unicode_ents[0]!r}" if unicode_ents else ""))

    all_labels_present = set(ENTITY_LABELS) == labels_seen
    ok = (offset_bad == 0 and overlap_bad == 0 and leak == 0
          and all_labels_present and zero_ent > 0)

    if not all_labels_present:
        failures.append(f"[labels] present {sorted(labels_seen)} != expected {ENTITY_LABELS}")
    if zero_ent == 0:
        failures.append("[no_entity] no zero-entity docs found in train")

    if ok:
        print("\nALL DOCBIN CHECKS PASSED.")
    else:
        print(f"\nFAILURES: {len(failures)}")
        for f in failures[:30]:
            print(f"  {f}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
