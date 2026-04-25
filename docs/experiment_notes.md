## Experiment 1 — Role classification

A simple classifier was trained to identify legal roles (ARGUIDO, TESTEMUNHA, RELATOR, REU) from sentences.

The classifier was combined with the existing NER model, allowing PER entities to be further classified into legal roles.

Initial results show that this approach is feasible and can extend the current system without retraining the full NER model.

### Observation
The first version of the role classifier always predicts one of the known legal roles. This causes false positives when a PER entity has no explicit legal role in the sentence.

### Next improvement
Add an UNKNOWN class for person entities without a legal role.


### UNKNOWN class

The role classifier includes an `UNKNOWN` class for PER entities that do not have an explicit legal role in the sentence.

This prevents the classifier from forcing every person entity into one of the legal-role labels.

In the final pipeline, `UNKNOWN` should not be exposed as a final label. It is used internally to decide when no role should be assigned.


## Experiment 2 — Template-generated role dataset

A second dataset was generated automatically using templates and a list of names.

The goal was to scale the initial role classification experiment without manually writing every example.

Dataset:
- `data/processed/roles_v2.jsonl`

Labels:
- ARGUIDO
- TESTEMUNHA
- RELATOR
- REU
- UNKNOWN

This dataset is useful for testing whether template-based synthetic data improves the stability of the role classifier.

### Observation after template-generated dataset

The first template-generated dataset improved stability, but introduced a bias: sentences containing words like "reside" or "mora" were strongly associated with UNKNOWN.

This caused examples such as "O arguido Paulo Rocha reside..." to be classified as UNKNOWN.

### Next improvement

Add mixed templates where legal-role entities also appear with addresses, identifiers and dates, so the classifier learns that these contextual features do not necessarily imply UNKNOWN.


## Experiment 3 — Improved template dataset

After observing bias in the initial template dataset, new mixed templates were introduced combining legal roles with other contextual elements such as addresses and actions (e.g. "reside").

This improved the classifier's robustness and reduced incorrect UNKNOWN predictions.

This highlights an important limitation of synthetic data:
simple templates can introduce unintended biases.

## Experiment 4 — Role classifier evaluation

An independent evaluation set was created with examples for:
- ARGUIDO
- TESTEMUNHA
- RELATOR
- REU
- UNKNOWN

The classifier was trained on the template-generated dataset (`roles_v2.jsonl`) and evaluated on `roles_eval.jsonl`.

Metrics used:
- accuracy
- precision
- recall
- F1-score

This evaluation is important because the previous evaluation dataset from Eduardo was lost, so a new evaluation setup needs to be created for this thesis.

### Result

The first independent evaluation achieved 96% accuracy.

Only one error was observed:
- "João Ribeiro vive na Avenida da Liberdade."
  - GOLD: UNKNOWN
  - PRED: TESTEMUNHA

This suggests that the UNKNOWN class needs more lexical and contextual diversity. Some words in the evaluation sentence were not present in the training vocabulary, so the classifier may have relied on weak remaining features or class-level biases.

Because the current classifier is based on CountVectorizer, unseen words such as "vive" are ignored during prediction. This highlights a limitation of the current simple bag-of-words approach.

### Confidence threshold

The misclassified UNKNOWN example was predicted as TESTEMUNHA with low confidence (0.4638).

A confidence threshold can be used to reduce false positives:
if the highest predicted probability is below 0.50, the role is assigned as UNKNOWN.

This is useful because the role classifier should only assign a legal role when there is enough contextual evidence.