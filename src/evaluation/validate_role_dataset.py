import argparse
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.map_role_taxonomy import DEFAULT_CONFIG_PATH, load_taxonomy


def validate_record(record):
    if not isinstance(record, dict):
        return ["record must be a JSON object"]

    errors = []
    for field in ("text", "entity"):
        if field not in record:
            errors.append(f"missing required field: {field}")
        elif not isinstance(record[field], str):
            errors.append(f"{field} must be a string")

    if "label" not in record and "labels" not in record:
        errors.append("record must contain label or labels")

    if "label" in record and not isinstance(record["label"], str):
        errors.append("label must be a string")
    if "labels" in record:
        if not isinstance(record["labels"], list):
            errors.append("labels must be a list")
        elif not all(isinstance(label, str) for label in record["labels"]):
            errors.append("every value in labels must be a string")

    has_start = "entity_start" in record
    has_end = "entity_end" in record
    if has_start != has_end:
        errors.append("entity_start and entity_end must appear together")
    elif has_start and has_end:
        start = record["entity_start"]
        end = record["entity_end"]
        text = record.get("text")
        entity = record.get("entity")
        if type(start) is not int or type(end) is not int:
            errors.append("entity_start and entity_end must be integers")
        elif isinstance(text, str) and not 0 <= start < end <= len(text):
            errors.append("entity offsets are outside text bounds")
        elif (
            isinstance(text, str)
            and isinstance(entity, str)
            and text[start:end] != entity
        ):
            errors.append(
                "text[entity_start:entity_end] does not equal entity"
            )

    return errors


def validate_file(path, fine_labels):
    errors = []
    distribution = Counter()
    multi_label_count = 0
    record_count = 0

    with path.open("r", encoding="utf-8") as dataset:
        for line_number, line in enumerate(dataset, start=1):
            if not line.strip():
                errors.append(f"{path}:{line_number}: empty line")
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(
                    f"{path}:{line_number}: invalid JSON: {exc.msg}"
                )
                continue

            record_count += 1
            for error in validate_record(record):
                errors.append(f"{path}:{line_number}: {error}")

            if not isinstance(record, dict):
                continue

            labels = []
            if "labels" in record and isinstance(record["labels"], list):
                labels = [
                    label for label in record["labels"] if isinstance(label, str)
                ]
                if len(record["labels"]) > 1:
                    multi_label_count += 1
            elif "label" in record and isinstance(record["label"], str):
                labels = [record["label"]]

            labels_to_validate = list(labels)
            if (
                "labels" in record
                and "label" in record
                and isinstance(record["label"], str)
            ):
                labels_to_validate.append(record["label"])

            for label in dict.fromkeys(labels_to_validate):
                if label not in fine_labels:
                    errors.append(
                        f"{path}:{line_number}: unknown fine label: {label!r}"
                    )

            distribution.update(label for label in labels if label in fine_labels)

    return record_count, distribution, multi_label_count, errors


def main():
    parser = argparse.ArgumentParser(description="Validate a fine role JSONL dataset.")
    parser.add_argument("path", type=Path, help="JSONL dataset to validate")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Taxonomy configuration (default: {DEFAULT_CONFIG_PATH})",
    )
    args = parser.parse_args()

    if not args.path.is_file():
        parser.error(f"dataset file does not exist: {args.path}")

    fine_labels, _ = load_taxonomy(args.config)
    record_count, distribution, multi_label_count, errors = validate_file(
        args.path, fine_labels
    )

    print("Class distribution:")
    for label in fine_labels:
        print(f"  {label}: {distribution[label]}")
    print(f"Records: {record_count}")
    print(f"Multi-label examples: {multi_label_count}")

    if errors:
        for error in errors:
            print(error)
        print(f"Validation failed: {len(errors)} error(s).")
        raise SystemExit(1)

    print("Validation passed.")


if __name__ == "__main__":
    main()
