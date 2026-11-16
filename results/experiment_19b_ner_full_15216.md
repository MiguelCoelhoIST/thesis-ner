# Experiência 19b — Extração NER integral (job 15216)

Extração NER de cobertura integral por documento; sem LLM, transmissão, treino ou quotas por papel. A completude declarada refere-se ao processamento, não ao recall humano.

```json
{
  "audited_documents": 388,
  "unique_texts": 191,
  "duplicate_text_versions": 197,
  "unique_text_characters": 15102124,
  "unique_text_words_whitespace": 2411871,
  "largest_document_characters": 1024075,
  "split_blocks_conservative": 187,
  "documents_requiring_identity_review": 47,
  "documents_in_multi_root_blocks": 11,
  "documents_without_component_root": 4,
  "old_covered_unique_characters": null,
  "old_accepted_PER_across_duplicate_versions_NOT_unique": null,
  "recovered_known_occurrences_lower_bound": 0,
  "recovered_from_19a_only": 0,
  "reused_privacy_cache_summary": [],
  "legacy_duplicate_occurrence_records": null,
  "known_occurrences_with_multiple_contexts": 0,
  "total_PER_mentions_complete": 24467,
  "planned_full_coverage_windows_6000_overlap_600": 2874,
  "planned_NER_input_characters_including_overlap": 16711924,
  "pilot_related_unique_documents": null,
  "gold_known_process_overlap_documents": null,
  "gold_context_containment_documents": null,
  "gold_process_ids_not_normalized": null,
  "reference_checks": {
    "pilot": "not_requested",
    "gold": "not_requested"
  },
  "source_mode": "original_documents",
  "source_files_skipped_by_reason": {
    "unsupported_extension": 3,
    "no_extractable_document_text": 1
  },
  "NER_executed": true,
  "LLM_calls": 0,
  "inventory_complete": true,
  "transformer_length_validation": {
    "validated": true,
    "documents": 191,
    "effective_limit": 512,
    "maximum_original_wordpieces": 703,
    "maximum_safe_wordpieces": 486,
    "outer_window_subdivisions": 1,
    "safe_outer_windows": 2875,
    "includes_special_tokens": true,
    "truncation": false
  },
  "NER_documents_processed": 191,
  "accepted_mentions_this_run": 24467,
  "ner_statistics": {
    "ner_windows": 2875,
    "document_characters": 15102124,
    "ner_input_characters": 16712524,
    "ner_overlap_characters": 1610400,
    "ner_windows_processed": 2875,
    "ner_characters_inferred": 16712524,
    "non_per_predictions": 39407,
    "ner_per_spans_considered": 24977,
    "dropped_invalid_ner_offsets": 252,
    "dropped_conflicting_spans": 82,
    "accepted_per_spans": 24467,
    "merged_spans": 114,
    "dropped_false_entities": 396,
    "dropped_merged_or_ambiguous_coordination": 114,
    "dropped_window_boundary": 51,
    "dropped_not_a_person_target": 6,
    "dropped_organization_or_legal_code": 5
  },
  "raw_PER_predictions_this_run": 24977,
  "raw_valid_PER_predictions_this_run": 24977,
  "NER_elapsed_seconds_including_load": 299.7902398649603,
  "dimension_scenarios_NOT_estimates": {
    "10000": {
      "annotation_rows_per_LLM": 10000,
      "batches_at_100_per_batch": 100,
      "maximum_context_characters_approx": 16300000
    },
    "20000": {
      "annotation_rows_per_LLM": 20000,
      "batches_at_100_per_batch": 200,
      "maximum_context_characters_approx": 32600000
    },
    "40000": {
      "annotation_rows_per_LLM": 40000,
      "batches_at_100_per_batch": 400,
      "maximum_context_characters_approx": 65200000
    }
  }
}
```
