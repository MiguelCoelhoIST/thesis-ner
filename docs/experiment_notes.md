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