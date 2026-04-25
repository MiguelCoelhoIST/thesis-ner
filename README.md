# thesis-ner

Repository for my MSc thesis work on Named Entity Recognition (NER) for Portuguese legal documents, continuing the work developed in the IRIS anonymizer project.

## Current focus

The current work is based on:

* an inherited NER pipeline using spaCy + transformers
* a silver annotated dataset in `.spacy` format
* a baseline model and an extended model trained previously

The goal is to:

* understand and reproduce the current system
* analyze the existing dataset and models
* explore improvements to the NER/classifier
* investigate synthetic data generation
* potentially test other transformer-based approaches

## Project structure

```text
thesis-ner/
  data/
    raw/
    processed/
    eval/
  docs/
    thesis_objectives.md
    model_notes.md
  models/
    baseline_model/
    eduardo_extended_model/
    experiments/
  notebooks/
  results/
  src/
    data/
    evaluation/
    training/
    utils/
  README.md
  requirements.txt
```

## Setup

Create and activate a virtual environment:

**Windows PowerShell**

```bash
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Current data

The main dataset currently being explored is:

```
data/raw/silver.spacy
```

# Dataset description

The `silver.spacy` dataset is:
- automatically annotated (silver standard)
- generated using previous NER models / heuristics / LLM-assisted annotation
- stored using spaCy's `DocBin` format

Note: This dataset may contain noise and is not manually verified.

This dataset contains annotated legal examples with the following labels identified so far:

* PER
* ORG
* LOC
* DAT
* IDP
* ADDR / MOR (depending on dataset/model naming)

# Labels

- PER: Person names
- ORG: Organizations / companies
- LOC: Locations / addresses
- DAT: Dates (non-legal)
- IDP: Identification numbers (e.g. NIF, IBAN)
- ADDR / MOR: Addresses / residence

## Current models

The project currently includes:

* `models/baseline_model/`
  Baseline model previously used

* `models/eduardo_extended_model/`
  Extended model trained with additional improvements

## Current scripts

**Inspect dataset examples**

```bash
python .\src\data\inspect_spacy_dataset.py
```

**Count labels in dataset**

```bash
python .\src\data\count_entity_labels.py
```

**Compare saved models on sample text**

```bash
python .\src\data\test_saved_models.py
```

## Notes

The inherited models were trained with older versions of spaCy / transformers, so compatibility warnings may appear when loading them. If needed, a legacy-compatible environment may be created later.

## Thesis direction

Possible next steps include:

* deeper comparison of baseline vs extended model
* creation of a proper evaluation setup
* generation of synthetic data for new entities
* extension to more specific legal-role labels such as:

  * Arguido
  * Réu
  * Testemunha
  * Relator
* testing alternative transformer models or training workflows
