"""
predict.py — run the trained NER model on new / unseen queries.

Loads a trained model from models/ and prints the entities it finds in each
query. By default it PREPROCESSES the query first (lowercase, strip punctuation,
collapse whitespace) and maps detected spans back to the original text — this is
the production flow (preprocess -> NER). Use --raw to skip preprocessing and run
the model directly on the input.

Usage:
    # single query (preprocessed by default)
    python -m src.predict --text "What treatment for HYPERTENSION?"

    # a file of queries (one per line)
    python -m src.predict --file tests/sample_queries.txt

    # interactive
    python -m src.predict -i

    # run the model on the raw text without normalization
    python -m src.predict --text "HYPERTENSION?" --raw
"""

from __future__ import annotations

import argparse
from pathlib import Path

import spacy

from src.preprocess import normalize_query


def predict_one(nlp, text: str, preprocess: bool = True) -> None:
    print(f"\nQuery: {text}")
    if preprocess:
        pre = normalize_query(text)
        doc = nlp(pre.normalized)
        if pre.normalized != text:
            print(f"  (normalized: {pre.normalized!r})")
        if not doc.ents:
            print("  (no entities found)")
            return
        for ent in doc.ents:
            # Map the entity span on normalized text back to the original text.
            os, oe = pre.to_original(ent.start_char, ent.end_char)
            orig_text = text[os:oe]
            print(f"  {orig_text!r:30} -> {ent.label_}")
    else:
        doc = nlp(text)
        if not doc.ents:
            print("  (no entities found)")
            return
        for ent in doc.ents:
            print(f"  {ent.text!r:30} -> {ent.label_}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict entities on queries (preprocess -> NER).")
    parser.add_argument("--model", type=Path, default=Path("models/model-best"),
                        help="Path to trained model dir.")
    parser.add_argument("--text", type=str, help="A single query to analyze.")
    parser.add_argument("--file", type=Path, help="File of queries, one per line.")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Type queries one at a time; blank line or 'quit' to exit.")
    parser.add_argument("--raw", action="store_true",
                        help="Skip preprocessing; run the model on the raw input text.")
    args = parser.parse_args()

    preprocess = not args.raw
    nlp = spacy.load(args.model)

    if args.text:
        predict_one(nlp, args.text, preprocess)

    if args.file:
        for line in args.file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                predict_one(nlp, line, preprocess)

    # Interactive mode (default if nothing else was given).
    if args.interactive or (not args.text and not args.file):
        mode = "raw" if args.raw else "preprocess -> NER"
        print(f"\nInteractive NER [{mode}] — type a query and press Enter.")
        print("Type 'quit' or 'exit' (or an empty line) to stop.\n")
        while True:
            try:
                text = input("query> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text or text.lower() in {"quit", "exit"}:
                break
            predict_one(nlp, text, preprocess)


if __name__ == "__main__":
    main()
