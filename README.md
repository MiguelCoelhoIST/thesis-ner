# thesis-ner

MSc thesis repository for Portuguese legal anonymization, Named Entity Recognition
(NER), and legal role classification.

The current work extends a legal anonymization pipeline by assigning legal roles to
person entities detected by a NER model.

```text
Text -> NER model -> PER entities -> legal role classifier
```

The role classifier is intended to refine `PER` entities with legal context while
keeping `UNKNOWN` as an internal class for people without an explicit legal role.

`UNKNOWN` is used as an internal fallback class for person entities
without sufficient contextual evidence for legal role attribution.

## Legal Role Labels

Current target labels:

```text
ARGUIDO
TESTEMUNHA
RELATOR
REU
UNKNOWN
```

## Current Experiments

The project currently evaluates several approaches for legal role classification:

- `LogisticRegression` + `CountVectorizer` lexical baseline
- rule-based and entity-aware rule-based classifiers
- transformer fine-tuning with BERTimbau
- sentence embedding encoder + `LogisticRegression`
- multi-encoder comparison using selected multilingual embedding models

The current best embedding encoder is:

```text
sentence-transformers/paraphrase-multilingual-mpnet-base-v2
```

On the current realistic evaluation set, this encoder outperformed the other
tested embedding models in the multi-encoder comparison.

## Current Best Results

| Approach | Macro F1 | Notes |
|---|---|---|
| Rule-based entity-aware classifier | ~0.94-1.00 | Strong lexical patterns, limited semantic generalization |
| BERTimbau fine-tuning | ~0.46 | Contextual transformer baseline |
| Embedding encoder + LogisticRegression | ~0.54 | Current best learned model |

## Project Structure

```text
thesis-ner/
  data/
    raw/                  # raw or sensitive data; ignored by Git
    processed/            # generated training datasets
    eval/                 # evaluation datasets

  docs/                   # thesis notes, objectives, labels, project guidance

  models/                 # trained models and checkpoints; ignored by Git

  notebooks/              # exploratory notebooks

  results/                # lightweight experiment summaries
    old_models/           # inherited model notes/results

  src/
    data/                 # dataset generation scripts and old model inspectors
    data_generation/      # role dataset generation and merge scripts
    evaluation/           # evaluation scripts and role pipeline scripts
    training/             # model training and encoder comparison scripts
    utils/                # conversion, inspection, and helper scripts

  README.md
  requirements.txt
  requirements_LEGACY.txt
```

No files have been moved yet; the structure above reflects the current repository
layout.

## Installation

### Local Environment

Windows PowerShell:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Linux/macOS:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### INESC GPU Environment

On the INESC GPU machines, first update the repository and activate the
environment:

```bash
git pull
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Before running GPU experiments, inspect GPU usage:

```bash
nvidia-smi
```

Choose an available GPU:

```bash
export CUDA_VISIBLE_DEVICES=5
```

Then run the desired training or evaluation script.

## Running Experiments

Run commands from the repository root.

### Transformer Fine-Tuning

Fine-tune BERTimbau for legal role classification:

```bash
python src/training/train_transformer_role_classifier.py
```

This uses:

```text
train: data/processed/roles_v4.jsonl
eval:  data/eval/roles_eval_realistic.jsonl
```

Trained models are written under `models/`, which is ignored by Git.

### Embedding Classifier

Train and evaluate an embedding encoder with a logistic regression classifier:

```bash
python src/training/train_embedding_role_classifier.py
```

Current main encoder:

```text
sentence-transformers/paraphrase-multilingual-mpnet-base-v2
```

### Multi-Encoder Comparison

Compare multiple multilingual embedding encoders:

```bash
python src/training/compare_embedding_models.py
```

The comparison currently includes:

```text
sentence-transformers/paraphrase-multilingual-mpnet-base-v2
intfloat/multilingual-e5-base
BAAI/bge-m3
```

### Evaluation Scripts

Evaluate the lexical role classifier:

```bash
python src/evaluation/evaluate_role_classifier.py
```

Evaluate threshold behavior:

```bash
python src/evaluation/evaluate_thresholds.py
```

Evaluate the entity-aware role classifier:

```bash
python src/evaluation/evaluate_entity_aware_roles.py
```

Evaluate rule-based baselines:

```bash
python src/evaluation/evaluate_rule_based_roles.py
python src/evaluation/evaluate_rule_based_roles_v2.py
```

Evaluate transformer predictions:

```bash
python src/evaluation/evaluate_transformer_predictions.py
```

## Data

The project uses generated role-classification datasets and evaluation files:

```text
data/processed/
data/eval/
```

Raw legal data and inherited sensitive datasets should remain under:

```text
data/raw/
```

Raw data must not be committed unless it is explicitly verified as safe to share.

## Dataset Generation

The project uses synthetic and semi-synthetic legal-role examples generated
through templates and entity-aware contextual patterns.

Additional experiments explore LLM-generated examples and realistic
multi-entity legal contexts.

## Dependency Management

All Python dependencies used by scripts should be listed in:

```text
requirements.txt
```

The legacy dependency file is kept only for inherited model compatibility:

```text
requirements_LEGACY.txt
```

The Git ignore rules exclude virtual environments, trained models, checkpoints,
logs, caches, and raw data directories. Lightweight documentation and experiment
summaries under `results/` should be committed.

## Experiment Tracking

Each experiment should have a corresponding result file:

```text
results/experiment_NN_short_name.txt
```

Each result file should briefly document:

- goal
- model or method
- dataset
- training/evaluation setup
- metrics
- qualitative observations
- conclusion
- next step

This keeps the thesis work reproducible and makes it easier to connect code,
results, and written analysis.

## Future Work

Planned directions:

- build larger and more realistic evaluation datasets
- generate legal-role examples with LLMs
- explore LLM-as-judge qualitative evaluation
- compare more multilingual encoders from the MTEB leaderboard
- improve robustness on indirect and multi-entity legal role mentions
