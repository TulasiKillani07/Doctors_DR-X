"""
preprocess.py — runtime query normalization for the QuerySearch NER pipeline.

Rationale: the NER model is trained on clean, lowercase, punctuation-free query
text (the V1 baseline). Rather than teach the model every surface variation
(casing, '?', extra spaces), we normalize the raw query at RUNTIME before NER.
This keeps the training data clean and the model stable, and solves surface-form
issues (Hypertension? / HYPERTENSION / extra spaces) deterministically.

Preprocessing solves SURFACE-FORM problems only. It does NOT fix semantic
classification errors (e.g. a concept the model learned with the wrong label);
those require NER-level work, not normalization.

Offset preservation: we keep a character-level map from every position in the
NORMALIZED text back to its position in the ORIGINAL text, so entities detected
on normalized text can be reported against the original query string.

Normalization steps:
  1. lowercase
  2. replace punctuation with spaces (keeps intra-word hyphens, e.g. breast-feeding)
  3. collapse runs of whitespace to a single space
  4. strip leading/trailing whitespace

Usage (as a library):
    from src.preprocess import normalize_query
    result = normalize_query("What treatment for HYPERTENSION?")
    result.normalized   -> "what treatment for hypertension"
    result.to_original(start, end) -> (orig_start, orig_end)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Characters kept as-is (letters, digits, whitespace, and intra-word hyphen).
# Everything else becomes a space during normalization.
# Includes Greek alphabet (e.g. α in acid α-glucosidase deficiency).
_KEEP = re.compile(r"[0-9a-z\u0370-\u03ff\s\-]")


@dataclass
class PreprocessResult:
    original: str
    normalized: str
    # index_map[i] = index in `original` of the char at normalized[i]
    index_map: list[int]

    def to_original(self, start: int, end: int) -> tuple[int, int]:
        """Map a [start, end) span on the normalized text back to the original."""
        if start >= len(self.index_map):
            return len(self.original), len(self.original)
        orig_start = self.index_map[start]
        # end is exclusive; map the last included char then +1
        last = min(end, len(self.index_map)) - 1
        orig_end = self.index_map[last] + 1 if last >= start else orig_start
        return orig_start, orig_end


def normalize_query(text: str) -> PreprocessResult:
    """Normalize a raw query, preserving a normalized->original offset map."""
    # Step 1: build a lowercased, char-filtered stream with source indices.
    chars: list[str] = []
    src_idx: list[int] = []
    for i, ch in enumerate(text):
        low = ch.lower()
        if _KEEP.match(low):
            chars.append(low)
        else:
            # Replace disallowed punctuation with a space (records original idx).
            low = " "
            chars.append(low)
        src_idx.append(i)

    # Step 2: collapse whitespace runs to a single space, tracking source idx.
    norm_chars: list[str] = []
    norm_map: list[int] = []
    prev_space = False
    for ch, oi in zip(chars, src_idx):
        if ch.isspace():
            if prev_space:
                continue  # skip repeated whitespace
            norm_chars.append(" ")
            norm_map.append(oi)
            prev_space = True
        else:
            norm_chars.append(ch)
            norm_map.append(oi)
            prev_space = False

    # Step 3: strip leading/trailing whitespace (and their map entries).
    lo, hi = 0, len(norm_chars)
    while lo < hi and norm_chars[lo] == " ":
        lo += 1
    while hi > lo and norm_chars[hi - 1] == " ":
        hi -= 1

    normalized = "".join(norm_chars[lo:hi])
    index_map = norm_map[lo:hi]

    return PreprocessResult(original=text, normalized=normalized, index_map=index_map)


if __name__ == "__main__":
    # Quick manual check.
    for q in [
        "What treatment for HYPERTENSION?",
        "What can help with  Sore Throat? ",
        "breast-feeding safety",
        "Show me the available medicines.",
    ]:
        r = normalize_query(q)
        print(f"{q!r}\n  -> {r.normalized!r}")
