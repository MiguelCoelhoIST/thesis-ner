# Experiment 19a: mention-level annotation protocol

This protocol applies to the new nine-role benchmark. The previous five-role guidelines and frozen 50-example set remain unchanged. Fine labels are the source of truth; aggregated targets are derived from `config/role_taxonomy.json`.

## Annotation unit and role definitions

Review one exact PER occurrence in a continuous extracted-text context. Preserve the source ID, text, target expression, and offsets. Verify `text[entity_start:entity_end] == entity`. Read the passage before considering any discovery suggestion; the terminal reviewer hides that suggestion.

| Label | Supported role of the marked person |
| --- | --- |
| ARGUIDO | Criminal accused/defendant. |
| REU | Civil defendant. A criminal accused is ARGUIDO, not REU. |
| AUTOR | Civil claimant/plaintiff. The author of an offense or publication is not thereby an AUTOR. |
| REQUERENTE | Person bringing the request/petition described in the passage. |
| RECORRENTE | Person bringing the appeal described in the passage. |
| RECORRIDO | Person against whom that appeal is directed. |
| TESTEMUNHA | Person identified as giving evidence as a witness. |
| RELATOR | Reporting judge responsible for the decision referenced in the passage. |
| UNKNOWN | Valid single-person mention with none of the eight target roles supported by the context. |

Role words discover candidates; they do not establish a target's identity or role. In particular, `autor do crime` does not automatically establish a civil claimant or ARGUIDO. Classify using the passage's supported procedural role. Out-of-scope roles can yield UNKNOWN; unresolved in-scope role ambiguity requires an uncertain review, not UNKNOWN.

## Decisions and multiple labels

- Accept one or more labels only when the context supports each one for the same target occurrence. A person may, for example, be ARGUIDO and RECORRENTE. Do not combine roles belonging to different people.
- Keep labels as a deduplicated list in taxonomy order. UNKNOWN is exclusive of every other label.
- REJECT is a review status, not a taxonomy label. Reject an organization, code, road abbreviation, merged people, invalid target span, irrelevant passage or unusable example. Preserve its source evidence; do not repair a span by guessing.
- Skip postpones a decision. Uncertain records retain tentative labels without validation. Only an explicitly confirmed, accepted annotation receives `human_validated=true`.
- Review notes should explain nontrivial decisions, ambiguous vocabulary, references to other cases, and identity discrepancies. Existing v4 annotations are retained without automatic correction or migration.

## Mention-level roles and cited proceedings

A role clearly assigned to the marked person in a cited proceeding is eligible for mention-level annotation. It must be flagged as belonging to that proceeding; it is not evidence that the person holds that role in the source judgment's current case.

Record `annotation_task="mention_level"` and a `role_scope_by_label` entry for every label: `current_proceeding`, `cited_proceeding`, `current_and_cited`, or `unclear`. UNKNOWN uses `not_applicable`. The reviewer derives `has_cited_proceeding_roles` from these entries. Roles can be assigned when the role itself is clear but proceeding scope remains unclear; retain `unclear` and explain the issue in the note.

For multi-label examples, assess proceeding scope separately for each label. Do not carry one label's scope over to another. If a single role is supported in both the current and a cited proceeding, use `current_and_cited`.

Any later current-case experiment must explicitly filter/adjudicate scopes. Do not silently reuse the mention-level set as current-case ground truth or convert citation-only roles to UNKNOWN. Legacy reviews lacking scope require a separate provenance review before that use.

## Evidence, difficulty and distractors

`annotation_evidence` describes the role assignment:

- `explicit`: a role phrase directly identifies this target, including a clearly supported cited-case role.
- `implicit`: syntax, coreference or procedural context supports the role without a direct target-role phrase.
- `not_applicable`: accepted UNKNOWN; there is no supported in-scope role assignment to grade as explicit or implicit.
- `uncertain`: evidence does not settle the decision; leave the record unvalidated.

For a multi-label record containing both explicit and implicit assignments, use `implicit` as the conservative record-level value and identify individual links in the review note. Existing `evidence_type` compatibility is retained: explicit -> explicit; implicit -> contextual; not_applicable/uncertain -> null. Historical UNKNOWN annotations with explicit/contextual evidence are not rewritten; flag them if re-reviewed under this protocol.

Difficulty is `easy` for direct resolution, `medium` for nearby contextual inference, and `hard` for competing people/roles, long-distance reference or complex attribution. Difficulty measures effort, not annotation uncertainty.

Set `contains_distractor_role=true` when a role cue belongs to another person. This can coexist with any label/evidence value, including UNKNOWN. A role of the target in a cited case is not by itself a distracting role of another person.

## Source identity and future splitting

Keep exact decision identifiers, including `.S1`/`.S2` and incident suffixes. `process_group_id` normalizes the base process and conservatively groups its related decisions/incidents for later split isolation.

New extraction records preserve `decision_id`, `decision_id_candidates`, `process_group_id`, and detailed `process_provenance` (header, filename and reference evidence). Conflicting header/filename IDs leave `decision_id=null`; same-root conflicts may still have a usable group ID. Different-root conflicts leave the group unresolved. `process_number` remains legacy evidence and must not be treated as a verified exact decision ID.

Resolve identity conflicts explicitly against source metadata. Store any adjudication separately; do not overwrite original evidence, candidates or reviews. A body reference is not automatically the source decision ID, nor does it automatically establish the marked person's proceeding scope.

Before creating splits, keep every example sharing `process_group_id` together, adjudicate missing/conflicting groups, and inspect duplicates/cited passages for additional leakage. Filename variants and repeated conversions must not create independent split identities.
