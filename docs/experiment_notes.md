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

### Confidence threshold result

After applying a confidence threshold of 0.50, the previous false positive was corrected.

Evaluation result:
- Accuracy: 1.00
- No errors in the current 25-example evaluation set

This does not mean the classifier is perfect. The evaluation set is still small and partially similar to the synthetic data generation patterns. However, the result shows that confidence thresholding can reduce false positives and make the pipeline safer.

## Experiment 5 — Hard role evaluation

A harder evaluation set was created using sentence structures different from the original templates.

The goal was to test whether the classifier generalizes beyond simple patterns such as:
- "O arguido {name}..."
- "A testemunha {name}..."

This evaluation is important to measure robustness and identify whether the template-generated data is too narrow.

### Result

The hard evaluation achieved 96% accuracy.

Only one error was observed:
- "Luís Fernandes foi designado relator do processo."
  - GOLD: RELATOR
  - PRED: UNKNOWN

The raw classifier assigned the highest probability to RELATOR (0.4479), but this was below the confidence threshold of 0.50. This shows a trade-off: the threshold reduces false positives, but may introduce false negatives for less direct sentence structures.

## Experiment 6 — Confidence threshold comparison

Different confidence thresholds were compared to understand the trade-off between false positives and false negatives.

Thresholds tested:
- 0.00
- 0.40
- 0.45
- 0.50
- 0.60

The goal is to find whether the threshold improves robustness or becomes too aggressive by converting valid role predictions into UNKNOWN.

### Threshold comparison result

Several confidence thresholds were compared on both the normal and hard evaluation sets.

Results:
- On the normal evaluation set, threshold 0.50 achieved the best result.
- On the hard evaluation set, threshold 0.40 achieved the best result.
- Threshold 0.50 was too strict for some indirect role mentions, converting valid role predictions into UNKNOWN.

For now, threshold 0.40 will be used as the default because it provides better robustness on harder examples.

## Experiment 7 — Realistic paragraph evaluation

The pipeline was tested on longer, more realistic legal-style paragraphs containing multiple person entities.

### Observation

The first version classified each PER entity using the full sentence/paragraph as input. This caused all person entities in the same text to receive the same role, even when they had different legal roles.

Example:
- "A testemunha Carla Mendes declarou que viu o arguido Rui Lopes..."
  - Carla Mendes -> TESTEMUNHA
  - Rui Lopes -> TESTEMUNHA

### Next improvement

Use a local context window around each PER entity instead of the full text. This should allow the classifier to assign different roles to different persons in the same sentence.

## Experiment 8 — Entity-aware classification

To improve role classification in sentences with multiple person entities, an entity marking strategy was introduced.

Instead of classifying based on the full sentence, the input now highlights the target entity:

Example:
"A testemunha [ENTITY] Sofia Almeida [/ENTITY] e o arguido Paulo Rocha..."

This allows the classifier to focus on the correct entity when multiple roles are present in the same context.

### Observation

Adding entity markers only at inference time did not significantly improve the classifier, because the model had not seen these markers during training.

### Next improvement

Generate a new training dataset (`roles_v3.jsonl`) where the target entity is explicitly marked with `[ENTITY] ... [/ENTITY]`.

## Experiment 9 — Entity-aware training dataset

A new template-generated dataset was created where the target entity is explicitly marked in the training examples.

Dataset:
- `data/processed/roles_v3.jsonl`

Example:
"O arguido [ENTITY] João Martins [/ENTITY] foi ouvido em tribunal."

The goal is to align the training format with the inference format used in the pipeline.

### Result

Entity-aware training improved the pipeline in realistic paragraphs, especially in cases with multiple PER entities and different roles.

Remaining issue:
The classifier still struggles when the role appears after the entity, such as:
"João Ribeiro como arguido"

Next improvement:
Add templates where legal roles appear after the entity, not only before it.

### Observation

Entity-aware training improved several multi-entity cases, but the classifier still struggles when multiple legal roles appear in the same local context.

Example:
"O tribunal ouviu Inês Costa como testemunha e João Ribeiro como arguido."

The classifier predicted TESTEMUNHA for both entities because the context contains both role indicators.

### Next improvement

Add multi-entity training examples where the same sentence appears with different target entities marked. This teaches the classifier to associate the role with the marked entity rather than with the sentence globally.

### Multi-entity training examples

After adding multi-entity training examples where different target entities are marked in the same sentence, the classifier correctly handled cases with multiple legal roles.

Example:
"O tribunal ouviu Inês Costa como testemunha e João Ribeiro como arguido."

Result:
- Inês Costa -> TESTEMUNHA
- João Ribeiro -> ARGUIDO

This confirms that entity-aware training examples are important for role classification when multiple persons and roles appear in the same context.