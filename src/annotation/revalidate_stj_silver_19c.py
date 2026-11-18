"""Recover source-exact evidence in a new private copy of a completed 19c pilot.

Reuses saved generations and the strict validator. Only entity markers and
whitespace may differ during matching. Structural validity is not human review.
"""

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.annotation import annotate_stj_silver_19c as annotation
from src.annotation.annotate_role_candidates_qwen import unique_keys, write_new_json
from src.annotation.plan_inventory_batches import file_hash
from src.annotation.prepare_role_annotation_batch import private_new_output
from src.annotation.role_reference_provenance import fingerprint

VERSION = "19c-evidence-recovery-v1"
ERROR_CODES = {
    "prediction_configuration_mismatch", "missing_raw_output", "historical_validation_mismatch",
    "completed_pilot_required", "historical_binding_mismatch", "historical_integrity_mismatch",
    "prediction_selection_mismatch", "historical_summary_mismatch", "revalidation_source_changed",
    "historical_status_mismatch", "historical_json_invalid", "pilot_review_status_mismatch",
}


def strict_json(raw):
    def invalid_constant(_):raise ValueError("historical_json_invalid")
    return json.loads(raw, object_pairs_hook=unique_keys, parse_constant=invalid_constant)


def saved_predictions(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = strict_json(line)
        if not isinstance(row, dict):raise ValueError("historical_json_invalid")
        rows.append(row)
    return rows


def recover_evidence(raw, text):
    """Return derived JSON and an audit trail, without changing the saved raw JSON."""
    response, errors = annotation.parse_response(raw, text)
    if "evidence_not_exact_short_substring" not in errors:
        return raw, []
    derived = copy.deepcopy(response)
    repairs = []
    for field in ("assignments", "other_roles"):
        for index, item in enumerate(derived[field]):
            if not isinstance(item, dict):
                continue
            quote = item.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                continue
            if len(quote) <= 240 and quote in text:
                continue
            # Preserve letters, accents, punctuation and case exactly. A lookahead
            # also detects overlapping matches, which must remain ambiguous.
            unmarked = quote.replace("[ENTITY]", "").replace("[/ENTITY]", "")
            tokens = unmarked.split()
            if not tokens:
                continue
            pattern = r"\s+".join(re.escape(token) for token in tokens)
            matches = list(re.finditer("(?=(" + pattern + "))", text))
            if len(matches) != 1:
                continue
            start, end = matches[0].span(1)
            literal = text[start:end]
            if len(literal) > 240:
                continue
            item["quote"] = literal
            repairs.append({"field": field, "index": index,
                            "original_quote": quote, "source_quote": literal,
                            "context_start": start, "context_end": end})
    if not repairs:
        return raw, []
    return json.dumps(derived, ensure_ascii=False), repairs


def revalidate_prediction(record, prediction, configuration):
    """Check the historical proposal before deriving a separately audited copy."""
    if prediction.get("llm_config") != configuration:
        raise ValueError("prediction_configuration_mismatch")
    raw = prediction.get("llm_raw_output")
    if not isinstance(raw, str):
        raise ValueError("missing_raw_output")
    generation_error = ("generation_token_limit_reached"
                        if "generation_token_limit_reached" in prediction.get("parsing_errors", [])
                        else None)
    expected = annotation.proposal(record, raw, configuration, generation_error)
    if (not expected.keys() <= prediction.keys() or
            fingerprint({k: prediction[k] for k in expected}) != fingerprint(expected)):
        raise ValueError("historical_validation_mismatch")
    derived_raw, repairs = (raw, []) if generation_error else recover_evidence(raw, record["text"])
    # Keep any historical per-record metadata as well as the generated fields.
    result = copy.deepcopy(prediction)
    result.update(annotation.proposal(record, derived_raw, configuration, generation_error))
    result["llm_raw_output"] = raw
    result["evidence_revalidation"] = {
        "version": VERSION,
        "original_llm_output_valid": prediction["llm_output_valid"],
        "original_parsing_errors": prediction["parsing_errors"],
        "source_prediction_sha256": fingerprint(prediction),
        "validation_input": derived_raw,
        "repairs": repairs,
    }
    return result


def revalidate_run(input_path, selection_path, source_dir, output_dir):
    output = private_new_output(output_dir)
    run_path = source_dir / "run.json"
    predictions_path = source_dir / "silver_predictions.jsonl"
    paths = {"input": input_path, "selection": selection_path,
             "source_run": run_path, "source_predictions": predictions_path,
             "prompt": annotation.PROMPT_PATH, "taxonomy": annotation.TAXONOMY,
             "generator": Path(annotation.__file__),
             "loader": annotation.ROOT / "src/annotation/annotate_role_candidates_qwen.py",
             "revalidator": Path(__file__)}
    hashes = {key: file_hash(path) for key, path in paths.items()}
    source_run = strict_json(run_path.read_text(encoding="utf-8"))
    if not isinstance(source_run, dict) or source_run.get("status") not in ("completed", "completed_with_invalid_outputs"):
        raise ValueError("completed_pilot_required")
    configuration = source_run["configuration"]
    if not isinstance(configuration, dict):raise ValueError("historical_json_invalid")
    for field, key in (("input_sha256", "input"), ("selection_sha256", "selection"),
                       ("prompt_sha256", "prompt"), ("taxonomy_sha256", "taxonomy"),
                       ("script_sha256", "generator"), ("loader_sha256", "loader")):
        if configuration.get(field) != hashes[key]:
            raise ValueError("historical_binding_mismatch")
    if (source_run.get("predictions_sha256") != hashes["source_predictions"]
            or source_run.get("input_unchanged") is not True
            or source_run.get("selection_unchanged") is not True):
        raise ValueError("historical_integrity_mismatch")
    records = annotation.load_pilot(input_path, selection_path)
    if any(row["pilot_selection"].get("training_eligibility") != "NOT_ESTABLISHED" for row in records):
        raise ValueError("pilot_review_status_mismatch")
    predictions = saved_predictions(predictions_path)
    if [row.get("id") for row in predictions] != [row["id"] for row in records]:
        raise ValueError("prediction_selection_mismatch")
    results = [revalidate_prediction(record, prediction, configuration)
               for record, prediction in zip(records, predictions)]
    original_summary = annotation.aggregate(predictions)
    if source_run.get("summary") != original_summary:
        raise ValueError("historical_summary_mismatch")
    if source_run["status"] != ("completed_with_invalid_outputs" if original_summary["invalid_outputs"] else "completed"):
        raise ValueError("historical_status_mismatch")
    # Recheck the full protected bundle before publishing derived proposals.
    annotation.load_pilot(input_path, selection_path)
    if any(file_hash(path) != hashes[key] for key, path in paths.items()):
        raise ValueError("revalidation_source_changed")
    summary = annotation.aggregate(results)
    report = {
        "version": VERSION,
        "status": "revalidated" if not summary["invalid_outputs"] else "revalidated_with_invalid_outputs",
        "source_hashes": hashes,
        "source_paths": {key: str(path.resolve()) for key, path in paths.items()},
        "generation_configuration": configuration,
        "original_run": copy.deepcopy(source_run),
        "original_summary": original_summary,
        "summary": summary,
        "repaired_evidence_count": sum(len(row["evidence_revalidation"]["repairs"]) for row in results),
        "repaired_record_count": sum(bool(row["evidence_revalidation"]["repairs"]) for row in results),
        "LLM_calls": 0,
        "human_validated": False,
        "requires_review": True,
        "training_eligibility": "NOT_ESTABLISHED",
    }
    output.mkdir(parents=True, mode=0o700)
    with (output / "silver_predictions.jsonl").open("x", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    report["predictions_sha256"] = file_hash(output / "silver_predictions.jsonl")
    write_new_json(output / "run.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--selection-manifest", type=Path, required=True)
    parser.add_argument("--source-run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        report = revalidate_run(args.input, args.selection_manifest,
                                args.source_run_dir, args.output_dir)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        code = str(exc) if str(exc) in ERROR_CODES else "input_or_protection_binding_failure"
        parser.exit(1, json.dumps({"status": "failed", "error_type": type(exc).__name__,
                                   "error_code": code}) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("status", "original_summary", "summary", "repaired_evidence_count",
                       "repaired_record_count", "LLM_calls")}))


if __name__ == "__main__":
    main()
