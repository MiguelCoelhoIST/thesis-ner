# Project instructions

This project is part of a MSc thesis on Portuguese legal anonymization / NER and legal role classification.

## Current pipeline

```text
Text -> NER model -> PER entities -> legal role classifier
```

Current legal role labels:

* ARGUIDO
* TESTEMUNHA
* RELATOR
* REU
* UNKNOWN

## Important development rules

* Keep all source code under `src/`.
* Keep experiment notes/results as `.txt` files under `results/`.
* Do not commit trained models, checkpoints, virtual environments, or raw sensitive data.
* Do commit scripts, dataset generation code, evaluation code, configs, and lightweight experiment summaries.
* Every experiment should have a corresponding result file.
* When adding a new Python dependency, update `requirements.txt`.
* Any change tested on the INESC machines must also be committed locally and pushed to GitHub.
* Prefer editing code locally, then `git push` locally and `git pull` on the INESC machine.
* Avoid editing source files directly on the remote machine unless absolutely necessary.

## Remote machine workflow

Use INESC GPU machines carefully. Before running any training:

```bash
nvidia-smi
```

Choose a GPU with low memory usage and low utilization.

Example:

```bash
export CUDA_VISIBLE_DEVICES=5
```

Then run training/evaluation.

## Dependency management

Install dependencies with:

```bash
pip install -r requirements.txt
```

If a package is used in an experiment, it must be added to `requirements.txt`.

Currently required for transformer and embedding experiments:

```text
spacy==3.8.13
spacy-transformers>=1.3.0
transformers
torch
datasets
jupyter
scikit-learn
accelerate
evaluate
sentence-transformers
```

## Experiment tracking

Each experiment should document:

* goal
* model
* dataset
* training/evaluation setup
* metrics
* qualitative observations
* conclusion
* next step

## Current experimental direction

Completed/ongoing directions:

* LogisticRegression + CountVectorizer lexical baseline
* rule-based entity-aware classifier
* BERTimbau fine-tuning
* hard multi-entity data augmentation
* GPU training on INESC g07
* sentence embedding encoder + classifier

Next directions:

* compare multiple encoders from the MTEB leaderboard
* generate more realistic examples from legal texts
* use LLMs for data generation / annotation
* explore LLM as a judge for qualitative evaluation
