# Experiência 19b — propostas SILVER, não gold

> Enquadramento de 16-11-2026 — Tentativa histórica de smoke Qwen local BLOQUEADA antes da inferência: zero respostas. Não é o smoke NER Slurm nem prova de anotação concluída. Protótipo suspenso; ver [estado atual](../docs/THESIS_STATE.md).

Zero-shot Qwen/Qwen3-8B; suggested_label não é enviado ao modelo.

Concordância lexical não é accuracy. Sem gold independente, não se calcula F1.

REFERENCE é experimental e separada da taxonomia fina; nenhuma saída é human-validated.

```json
{
  "status": "blocked",
  "elapsed_seconds": 12.442239099997096,
  "summary": {
    "generated_records": 0,
    "valid_outputs": 0,
    "invalid_outputs": 0,
    "status_counts": {},
    "proposed_fine_labels_valid_outputs": {},
    "supported_fine_labels": {},
    "experimental_categories": {},
    "fine_multilabel_records": 0,
    "scope_counts": {},
    "evidence_counts": {},
    "lexical_comparison_not_accuracy": {
      "denominator_valid_with_fine_proposals": 0,
      "suggestion_in_proposals": 0,
      "suggestion_absent": 0,
      "singleton_exact_match": 0,
      "valid_without_fine_proposal": 0
    },
    "parse_error_counts": {}
  },
  "input_unchanged": true,
  "expected_records": 5,
  "error_code": "cuda_unavailable"
}
```
