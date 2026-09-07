# Annotation guidelines for legal-role classification

## Purpose

This dataset evaluates the legal-role classifier on real candidate examples from Portuguese legal decisions. Each JSONL record represents one person entity in a text passage. Annotate the role of the person named in `entity`, using the passage in `text` as evidence.

Annotate only the target entity. Other people and role words in the passage are context or distractors and must not determine the target label.

## Labels

Use exactly one of these labels:

- `ARGUIDO`: the target is identified as an arguido or arguida in criminal proceedings.
- `TESTEMUNHA`: the target gives, gave, or is identified as giving evidence as a witness.
- `RELATOR`: the target is the judge responsible for reporting or authoring the decision, including feminine forms such as relatora.
- `REU`: the target is identified as a defendant or respondent in civil proceedings. A criminal defendant must be annotated as `ARGUIDO`, not `REU`.
- `UNKNOWN`: none of the four target roles (`ARGUIDO`, `TESTEMUNHA`, `RELATOR`, `REU`) is supported by the passage for the target entity.

Do not infer a role from a person's name, profession, title, or proximity to a role belonging to somebody else. Use `UNKNOWN` when the target is merely mentioned or when the passage supports a legal role outside this label set.

Do not use `UNKNOWN` to resolve genuine ambiguity between two or more in-scope labels, or when multiple in-scope roles apply to the same target. Exclude such cases from the primary gold evaluation set and flag them for later qualitative analysis.

## Annotation procedure

1. Locate the exact target named by `entity` in `text`.
2. Read the complete passage, including references, pronouns, and grammatical links to the target.
3. Identify whether the passage supports one of the four legal roles.
4. Check that any role expression applies to the target rather than another person.
5. Assign `UNKNOWN` if no supported in-scope role remains.
6. Exclude and flag the case for later qualitative analysis if two or more in-scope labels remain genuinely ambiguous or multiple in-scope roles apply.
7. Otherwise, record the evidence type, difficulty, distractor status, provenance, and validation status described below.

Do not guess when a passage appears to support more than one in-scope role for the same target and the intended role cannot be resolved from context. This is an exclusion case, not an `UNKNOWN` example.

## Required record fields

Each line must be one JSON object containing all of these fields:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier unique within the dataset. |
| `process_number` | Process or case number from the source decision. |
| `decision_date` | Date of the decision. Preserve one consistent dataset-wide date format. |
| `source_url` | URL of the source decision. |
| `text` | Self-contained passage used to classify the target. It must not be empty. |
| `entity` | Target person expression as it appears in the passage. It must not be empty. |
| `label` | One of the five labels defined above. |
| `evidence_type` | `explicit` or `contextual`, as defined below. |
| `difficulty` | `easy`, `medium`, or `hard`, as defined below. |
| `contains_distractor_role` | Boolean indicating whether the passage includes a role cue for a person other than the target. |
| `original_anonymized` | Boolean indicating whether the source itself anonymized the target expression. |
| `human_validated` | Boolean indicating whether a human annotator has reviewed the complete record. |

Additional metadata may be retained, but it must not replace any required field.

## Evidence type

- `explicit`: the target is directly linked to its role by a title, apposition, or unambiguous role phrase.
- `contextual`: the role is supported through syntax, coreference, or surrounding context rather than a direct target-role phrase.

Evidence type describes how the gold label is determined; it is not itself a role label.

## Difficulty

- `easy`: the target-role link, or the absence of a role, is direct and unambiguous.
- `medium`: resolving the label requires nearby context, a pronoun, or a straightforward distinction between people.
- `hard`: the passage contains competing role cues that can be resolved, long-distance references, complex syntax, or anonymization that requires close reading. Genuinely unresolved label ambiguity is excluded from the primary gold set.

## Distractors and anonymization

Set `contains_distractor_role` to `true` whenever an in-scope role cue in the passage refers to someone other than the target. Otherwise set it to `false`. Distractors are represented exclusively by this boolean and are not an evidence type. `contains_distractor_role: true` may coexist with any label and with either `explicit` or `contextual` evidence.

Set `original_anonymized` to `true` only when the source decision already replaced or obscured the target's identity. Do not set it merely because the dataset curator later removed identifying information.

Set `human_validated` to `true` only after a person has checked the source metadata, target span, label, evidence type, difficulty, and boolean flags.

## Quality checks

Before accepting a record, confirm that:

- the `id` is unique;
- `text` and `entity` are non-empty and the target can be identified in the passage;
- the role evidence applies to the target entity;
- the label, evidence type, and difficulty use the permitted values;
- all three flags contain JSON booleans (`true` or `false`), not strings or integers;
- source metadata is sufficient to trace the passage back to its decision;
- sensitive information is handled according to the source and project data policy.

Example record structure:

```json
{"id":"candidate-0001","process_number":"123/24.0TEST","decision_date":"2026-01-15","source_url":"https://example.invalid/decision/123","text":"Foi ouvida como testemunha a pessoa AA.","entity":"AA","label":"TESTEMUNHA","evidence_type":"explicit","difficulty":"easy","contains_distractor_role":false,"original_anonymized":true,"human_validated":true}
```
