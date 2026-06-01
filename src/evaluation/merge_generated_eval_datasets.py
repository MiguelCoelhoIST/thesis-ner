import json
from collections import Counter
from pathlib import Path


INPUT_DIR = Path("data/eval/generated")
OUTPUT_PATH = Path("data/eval/roles_eval_realistic_v2.jsonl")

EXPECTED_KEYS = {"text", "label"}
VALID_LABELS = {"ARGUIDO", "TESTEMUNHA", "RELATOR", "REU", "UNKNOWN"}


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


def load_valid_records(path):
    records = []

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                raise ValueError(f"{path}:{line_number}: empty line")

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc

            errors = validate_record(record, path, line_number)
            if errors:
                raise ValueError(f"{path}:{line_number}: {'; '.join(errors)}")

            records.append(record)

    return records


def main():
    files = sorted(INPUT_DIR.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No JSONL files found under: {INPUT_DIR}")

    total_records_read = 0
    duplicate_records_removed = 0
    merged_records = []
    seen_texts = set()

    for path in files:
        records = load_valid_records(path)
        total_records_read += len(records)

        for record in records:
            text = record["text"]
            if text in seen_texts:
                duplicate_records_removed += 1
                continue

            seen_texts.add(text)
            merged_records.append(record)

    label_counts = Counter(record["label"] for record in merged_records)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for record in merged_records:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")

    print(f"Input files: {len(files)}")
    print(f"Total records read: {total_records_read}")
    print(f"Duplicate records removed: {duplicate_records_removed}")
    print(f"Final record count: {len(merged_records)}")
    print("Final label distribution:")

    for label in sorted(VALID_LABELS):
        print(f"  {label}: {label_counts[label]}")

    print(f"Saved output to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
