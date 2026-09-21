# QuerySearch — NER (Phase 1)

A custom **Named Entity Recognition (NER)** model that reads doctor-style medical
search queries and extracts the open-ended medical concepts from them.

This is **Phase 1** of the larger **QuerySearch** understanding pipeline. Right now
we build and prove the NER model in isolation. Later phases (dictionary, entity
resolution, intent detection, entity→DB field mapping, search object, ranking,
Groq) are added on top, and only after that do we connect to the real MRX/DRX
database. None of those later layers are built yet.

Built with **spaCy**, fine-tuning the pretrained **`en_core_web_md`** model on our
own annotated query dataset.

## Entities (finalized for the NER phase)

The NER model recognizes exactly three labels:

| Label       | Meaning | Examples |
|-------------|---------|----------|
| `DISEASE`   | A diagnosed illness / pathology being treated | breast cancer, asthma, hypertension, diabetes |
| `SYMPTOM`   | A symptom / complaint the patient experiences | abdominal pain, headache, cough, fever |
| `CONDITION` | A physiological state / context that affects drug choice | pregnancy, renal impairment, lactation, elderly |

Drug names, brands, manufacturers, dosage forms, and routes are **not** handled by
NER — those belong to the dictionary layer in a later phase.

Labels live in one place: [`config/labels.py`](config/labels.py).

### Example behavior

| Query | Expected entities |
|-------|-------------------|
| "Suggest drugs for breast cancer during pregnancy" | breast cancer → DISEASE, pregnancy → CONDITION |
| "Drugs for abdominal pain" | abdominal pain → SYMPTOM |
| "Which drugs are contraindicated during pregnancy?" | pregnancy → CONDITION |
| "Safe medication in renal impairment" | renal impairment → CONDITION |

The trickiest boundary is **DISEASE vs CONDITION** — see the annotation guidelines.

## Training data

**Training data is provided by the project owner** — this repo ships no starter
queries or annotations. Place your data as described below.

## Project structure

```
QuerySearch_NER/
├── README.md
├── requirements.txt
├── config/
│   ├── labels.py          # single source of truth for entity labels
│   └── config.cfg         # spaCy training config (you generate this)
├── data/
│   ├── raw/               # raw, unannotated queries (you provide)
│   ├── annotations/       # annotated JSONL + ANNOTATION_GUIDELINES.md
│   ├── splits/            # train/dev/test JSONL (generated)
│   └── processed/         # .spacy binaries (generated)
├── src/
│   ├── data_prep.py       # 1. clean/normalize raw queries
│   ├── split_data.py      # 3. split annotations into train/dev/test
│   ├── convert.py         # 4. JSONL -> .spacy
│   ├── train.py           # 5. train on top of en_core_web_md
│   ├── evaluate.py        # 6. Precision / Recall / F1
│   └── predict.py         # 7. run model on new queries
├── models/                # trained models saved here
├── notebooks/
└── tests/
    └── sample_queries.txt # unseen queries for quick manual testing (you provide)
```

## Setup

```bash
# from the QuerySearch_NER/ directory
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` installs spaCy and the `en_core_web_md` base model.

## Workflow

### 1. Prepare raw queries
Put your raw queries (one per line) in `data/raw/queries.txt`, then:
```bash
python -m src.data_prep --input data/raw/queries.txt --output data/raw/queries_clean.txt
```

### 2. Annotate
Follow [`data/annotations/ANNOTATION_GUIDELINES.md`](data/annotations/ANNOTATION_GUIDELINES.md)
and store annotations as JSONL in `data/annotations/queries.jsonl`. Each line:
```json
{"text": "Suggest drugs for breast cancer during pregnancy", "entities": [[18, 31, "DISEASE"], [39, 48, "CONDITION"]]}
```
Target roughly **500–1000 annotated queries**, iterating with difficult real
queries (especially DISEASE vs CONDITION cases).

### 3. Split into train / dev / test
```bash
python -m src.split_data --input data/annotations/queries.jsonl --outdir data/splits --train 0.7 --dev 0.15 --test 0.15
```

### 4. Convert to spaCy format
```bash
python -m src.convert --input data/splits/train.jsonl --output data/processed/train.spacy
python -m src.convert --input data/splits/dev.jsonl   --output data/processed/dev.spacy
python -m src.convert --input data/splits/test.jsonl  --output data/processed/test.spacy
```

### 5. Create the training config (once)
```bash
python -m spacy init config config/config.cfg --lang en --pipeline ner --optimize efficiency
```
In `config/config.cfg`, set the base vectors so we fine-tune on top of
`en_core_web_md`:
```ini
[paths]
vectors = "en_core_web_md"

[initialize]
vectors = ${paths.vectors}
```

### 6. Train
```bash
python -m spacy train config/config.cfg --output models \
    --paths.train data/processed/train.spacy \
    --paths.dev data/processed/dev.spacy
```
(or `python -m src.train`). Best model is saved to `models/model-best`.

### 7. Evaluate (Precision / Recall / F1)
```bash
python -m src.evaluate --model models/model-best --test data/processed/test.spacy
```
Look at per-label scores, especially DISEASE vs CONDITION.

### 8. Test on unseen queries
```bash
python -m src.predict --model models/model-best --file tests/sample_queries.txt
python -m src.predict --model models/model-best --text "Safe medication in renal impairment"
```

### 9. Error analysis + iterate
Review mistakes (focus on DISEASE vs CONDITION confusion), add/fix annotations,
then repeat steps 3–8. More and better-annotated data is usually the highest-
leverage improvement. Freeze a reliable model before moving to Phase 2.

## Notes
- `.spacy` binaries and trained models are gitignored — regenerate them from the
  annotations + config.
- Keep the label schema in `config/labels.py` as the single source of truth.
- Later QuerySearch layers (dictionary, resolution, intent, mapping, ranking,
  Groq) are intentionally not built yet.
```
