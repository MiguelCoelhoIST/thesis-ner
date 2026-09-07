import argparse
import json
import re
from datetime import date
from pathlib import Path


DEFAULT_DATASET = Path("data/eval/roles_eval_real_candidates_v1.jsonl")
REQUIRED_FIELDS = {
    "id",
    "process_number",
    "decision_date",
    "source_url",
    "text",
    "entity",
    "label",
    "evidence_type",
    "difficulty",
    "contains_distractor_role",
    "original_anonymized",
    "human_validated",
}
ALLOWED_LABELS = {"ARGUIDO", "TESTEMUNHA", "RELATOR", "REU", "UNKNOWN"}
ALLOWED_EVIDENCE_TYPES = {"explicit", "contextual"}
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
NON_EMPTY_STRING_FIELDS = {"id", "process_number", "decision_date", "source_url"}
BOOLEAN_FIELDS = {
    "contains_distractor_role",
    "original_anonymized",
    "human_validated",
}


def validate_record(record):
    if not isinstance(record, dict):
        return ["record is not a JSON object"]

    errors = []
    missing = sorted(REQUIRED_FIELDS - record.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")

    for field in sorted(NON_EMPTY_STRING_FIELDS):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        errors.append("text must be a non-empty string")

    entity = record.get("entity")
    if not isinstance(entity, str) or not entity.strip():
        errors.append("entity must be a non-empty string")
    elif isinstance(text, str) and entity not in text:
        errors.append("entity must occur exactly in text")

    decision_date = record.get("decision_date")
    if isinstance(decision_date, str) and decision_date.strip():
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", decision_date):
            errors.append("decision_date must use YYYY-MM-DD")
        else:
            try:
                date.fromisoformat(decision_date)
            except ValueError:
                errors.append("decision_date must be a valid date")

    source_url = record.get("source_url")
    if (
        isinstance(source_url, str)
        and source_url.strip()
        and not source_url.startswith(("http://", "https://"))
    ):
        errors.append("source_url must begin with http:// or https://")

    label = record.get("label")
    if label not in ALLOWED_LABELS:
        errors.append(f"invalid label: {label!r}")

    evidence_type = record.get("evidence_type")
    if evidence_type not in ALLOWED_EVIDENCE_TYPES:
        errors.append(f"invalid evidence_type: {evidence_type!r}")

    difficulty = record.get("difficulty")
    if difficulty not in ALLOWED_DIFFICULTIES:
        errors.append(f"invalid difficulty: {difficulty!r}")

    for field in sorted(BOOLEAN_FIELDS):
        if field in record and not isinstance(record[field], bool):
            errors.append(f"{field} must be a boolean")

    return errors


def validate_file(path):
    errors = []
    seen_ids = {}
    record_count = 0

    with path.open("r", encoding="utf-8") as dataset:
        for line_number, line in enumerate(dataset, start=1):
            if not line.strip():
                errors.append(f"{path}:{line_number}: empty line")
                continue

            record_count += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_number}: invalid JSON: {exc.msg}")
                continue

            record_errors = validate_record(record)
            errors.extend(
                f"{path}:{line_number}: {message}" for message in record_errors
            )

            if isinstance(record, dict) and "id" in record:
                id_key = json.dumps(record["id"], sort_keys=True, ensure_ascii=False)
                if id_key in seen_ids:
                    errors.append(
                        f"{path}:{line_number}: duplicate id {record['id']!r} "
                        f"(first seen on line {seen_ids[id_key]})"
                    )
                else:
                    seen_ids[id_key] = line_number

    return record_count, errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate the real-candidate legal-role evaluation dataset."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"JSONL dataset to validate (default: {DEFAULT_DATASET})",
    )
    args = parser.parse_args()

    if not args.path.is_file():
        parser.error(f"dataset file does not exist: {args.path}")

    record_count, errors = validate_file(args.path)
    for error in errors:
        print(error)

    if errors:
        print(f"Validation failed: {len(errors)} error(s) in {record_count} record(s).")
        raise SystemExit(1)

    print(f"Validation passed: {record_count} record(s).")


if __name__ == "__main__":
    main()
