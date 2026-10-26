import argparse
import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config/role_taxonomy.json"


def load_taxonomy(path=DEFAULT_CONFIG_PATH):
    with path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    fine_labels = config.get("fine_labels")
    aggregated_mapping = config.get("aggregated_mapping")
    if not isinstance(fine_labels, list) or not all(
        isinstance(label, str) for label in fine_labels
    ):
        raise ValueError("fine_labels must be a list of strings")
    if not isinstance(aggregated_mapping, dict):
        raise ValueError("aggregated_mapping must be an object")
    if set(aggregated_mapping) != set(fine_labels):
        raise ValueError("aggregated_mapping must define every fine label exactly once")

    return fine_labels, aggregated_mapping


def map_label(label, taxonomy, fine_labels, aggregated_mapping):
    if label not in fine_labels:
        raise ValueError(f"unknown fine label: {label!r}")
    if taxonomy == "fine":
        return label
    if taxonomy == "aggregated":
        return aggregated_mapping[label]
    raise ValueError(f"unknown taxonomy: {taxonomy!r}")


def map_labels(labels, taxonomy, fine_labels, aggregated_mapping):
    if not isinstance(labels, list):
        raise ValueError("labels must be a list")

    mapped_labels = []
    seen = set()
    for label in labels:
        mapped = map_label(label, taxonomy, fine_labels, aggregated_mapping)
        if mapped not in seen:
            seen.add(mapped)
            mapped_labels.append(mapped)
    return mapped_labels


def map_record(record, taxonomy, fine_labels, aggregated_mapping):
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")
    if "label" not in record and "labels" not in record:
        raise ValueError("record must contain label or labels")

    mapped_record = dict(record)
    if "label" in record:
        mapped_record["label"] = map_label(
            record["label"], taxonomy, fine_labels, aggregated_mapping
        )
    if "labels" in record:
        mapped_record["labels"] = map_labels(
            record["labels"], taxonomy, fine_labels, aggregated_mapping
        )
    return mapped_record


def record_labels(record):
    if "labels" in record:
        return record["labels"]
    if "label" in record:
        return [record["label"]]
    return []


def print_distribution(title, records, preferred_order):
    counts = Counter(
        label for record in records for label in record_labels(record)
    )
    ordered_labels = [label for label in preferred_order if label in counts]
    ordered_labels.extend(sorted(set(counts) - set(ordered_labels)))

    print(title)
    for label in ordered_labels:
        print(f"  {label}: {counts[label]}")


def load_jsonl(path):
    records = []
    with path.open("r", encoding="utf-8") as dataset:
        for line_number, line in enumerate(dataset, start=1):
            if not line.strip():
                raise ValueError(f"{path}:{line_number}: empty line")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(record, dict):
                raise ValueError(
                    f"{path}:{line_number}: record must be a JSON object"
                )
            records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser(
        description="Map a fine-grained role JSONL dataset to a selected taxonomy."
    )
    parser.add_argument("input", type=Path, help="Source JSONL dataset")
    parser.add_argument("output", type=Path, help="New mapped JSONL dataset")
    parser.add_argument(
        "--taxonomy",
        choices=("fine", "aggregated"),
        required=True,
        help="Output taxonomy",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Taxonomy configuration (default: {DEFAULT_CONFIG_PATH})",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")
    if args.input.resolve() == args.output.resolve():
        parser.error("output must be different from the source dataset")
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")

    fine_labels, aggregated_mapping = load_taxonomy(args.config)
    source_records = load_jsonl(args.input)

    mapped_records = []
    for line_number, record in enumerate(source_records, start=1):
        try:
            mapped_records.append(
                map_record(
                    record,
                    args.taxonomy,
                    fine_labels,
                    aggregated_mapping,
                )
            )
        except ValueError as exc:
            raise ValueError(f"{args.input}:{line_number}: {exc}") from exc

    aggregated_order = list(dict.fromkeys(aggregated_mapping.values()))
    print_distribution("Class distribution before mapping:", source_records, fine_labels)
    print_distribution(
        "Class distribution after mapping:",
        mapped_records,
        fine_labels if args.taxonomy == "fine" else aggregated_order,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output_file:
        for record in mapped_records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(mapped_records)} records to: {args.output}")


if __name__ == "__main__":
    main()
