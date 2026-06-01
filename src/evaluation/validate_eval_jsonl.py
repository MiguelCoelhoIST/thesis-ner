import argparse
import json
from collections import Counter
from pathlib import Path


EXPECTED_KEYS = {"text", "label"}
VALID_LABELS = {"ARGUIDO", "TESTEMUNHA", "RELATOR", "REU", "UNKNOWN"}
DEFAULT_EVAL_DIR = Path("data/eval/generated")


def validate_record(record, path, line_number):
    errors = []

    if not isinstance(record, dict):
        return ["record is not a JSON object"]

    keys = set(record.keys())
    if keys != EXPECTED_KEYS:
        missing = sorted(EXPECTED_KEYS - keys)
        extra = sorted(keys - EXPECTED_KEYS)
        if missing:
            errors.append(f"missing keys: {', '.join(missing)}")
        if extra:
            errors.append(f"extra keys: {', '.join(extra)}")

    text = record.get("text")
    if not isinstance(text, str):
        errors.append("text is not a string")
    else:
        start_count = text.count("[ENTITY]")
        end_count = text.count("[/ENTITY]")

        if start_count != 1:
            errors.append(f"text contains {start_count} [ENTITY] markers")
        if end_count != 1:
            errors.append(f"text contains {end_count} [/ENTITY] markers")

    label = record.get("label")
    if label not in VALID_LABELS:
        errors.append(f"invalid label: {label!r}")

    return errors


def validate_file(path):
    label_counts = Counter()
    invalid_count = 0
    total_count = 0

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                invalid_count += 1
                print(f"{path}:{line_number}: empty line")
                continue

            total_count += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                invalid_count += 1
                print(f"{path}:{line_number}: invalid JSON: {exc.msg}")
                continue

            errors = validate_record(record, path, line_number)
            if errors:
                invalid_count += 1
                print(f"{path}:{line_number}: {'; '.join(errors)}")
                continue

            label_counts[record["label"]] += 1

    return total_count, invalid_count, label_counts


def print_label_distribution(path, label_counts):
    print(f"\n{path}")
    print("Label distribution:")

    for label in sorted(VALID_LABELS):
        print(f"  {label}: {label_counts[label]}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate generated legal-role evaluation JSONL files."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_EVAL_DIR,
        help=f"Directory containing JSONL files, default: {DEFAULT_EVAL_DIR}",
    )
    args = parser.parse_args()

    if not args.path.exists():
        raise FileNotFoundError(f"Path does not exist: {args.path}")

    files = sorted(args.path.glob("*.jsonl"))
    if not files:
        print(f"No JSONL files found under: {args.path}")
        return

    total_files = 0
    total_records = 0
    total_invalid = 0

    for path in files:
        total_files += 1
        file_total, file_invalid, label_counts = validate_file(path)

        total_records += file_total
        total_invalid += file_invalid

        print_label_distribution(path, label_counts)
        print(f"Records: {file_total}")
        print(f"Invalid lines: {file_invalid}")

    print("\nSummary")
    print(f"Files checked: {total_files}")
    print(f"Records checked: {total_records}")
    print(f"Invalid lines: {total_invalid}")


if __name__ == "__main__":
    main()
