"""
train.py — train the custom NER model on top of en_core_web_md.

Stage 5. Thin wrapper around spaCy's training loop. It expects:
  - a spaCy config file (config/config.cfg)
  - processed training data (data/processed/train.spacy)
  - processed dev data     (data/processed/dev.spacy)

The recommended way to train with spaCy 3.x is the CLI:

    python -m spacy train config/config.cfg \
        --output models \
        --paths.train data/processed/train.spacy \
        --paths.dev data/processed/dev.spacy

This module offers the same thing as a Python entry point for convenience, and
prints the exact CLI command so you can run it manually too.

To generate a starting config (fine-tuning en_core_web_md for NER):

    python -m spacy init config config/config.cfg \
        --lang en --pipeline ner --optimize efficiency

Then edit config/config.cfg so that:
    [components.ner.source] or [initialize] uses "en_core_web_md" as the base,
    i.e. set [paths] vectors = "en_core_web_md" and
    [initialize.vectors] = "en_core_web_md".
See README.md for the exact settings.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from spacy.cli.train import train as spacy_train


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the custom NER model.")
    parser.add_argument("--config", type=Path, default=Path("config/config.cfg"))
    parser.add_argument("--output", type=Path, default=Path("models"))
    parser.add_argument("--train", type=Path, default=Path("data/processed/train.spacy"))
    parser.add_argument("--dev", type=Path, default=Path("data/processed/dev.spacy"))
    args = parser.parse_args()

    overrides = {
        "paths.train": str(args.train),
        "paths.dev": str(args.dev),
    }

    print("Equivalent CLI:")
    print(
        f"  python -m spacy train {args.config} --output {args.output} "
        f"--paths.train {args.train} --paths.dev {args.dev}\n"
    )

    spacy_train(args.config, output_path=args.output, overrides=overrides)


if __name__ == "__main__":
    main()
