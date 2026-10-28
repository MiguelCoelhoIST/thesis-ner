import argparse
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.map_role_taxonomy import DEFAULT_CONFIG_PATH, load_taxonomy


REQUIRED_FIELDS = {
    "id",
    "source_file",
    "process_number",
    "text",
    "entity",
    "entity_start",
    "entity_end",
    "suggested_label",
    "label",
    "evidence_type",
    "difficulty",
    "contains_distractor_role",
    "human_validated",
}


def validate_candidate_record(record, fine_labels):
    if not isinstance(record, dict):
        return ["record must be a JSON object"]

    errors = []
    required = REQUIRED_FIELDS - {"label"} if "labels" in record else REQUIRED_FIELDS
    missing = sorted(required - record.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")

    for field in ("id", "source_file", "text", "entity"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    process_number = record.get("process_number")
    if process_number is not None and not isinstance(process_number, str):
        errors.append("process_number must be a string or null")

    suggested_label = record.get("suggested_label")
    if suggested_label not in fine_labels:
        errors.append(f"invalid suggested_label: {suggested_label!r}")

    label = record.get("label")
    if label is not None:
        if isinstance(label, str):
            labels = [label]
        elif isinstance(label, list) and all(
            isinstance(item, str) for item in label
        ):
            labels = label
        else:
            labels = []
            errors.append("label must be null, a string, or a list of strings")
        for item in labels:
            if item not in fine_labels:
                errors.append(f"invalid fine label: {item!r}")

    if "labels" in record:
        labels = record["labels"]
        if not isinstance(labels, list) or not all(isinstance(item, str) for item in labels):
            errors.append("labels must be a list of strings")
        else:
            for item in labels:
                if item not in fine_labels:
                    errors.append(f"invalid fine label: {item!r}")
            if len(set(labels)) != len(labels):
                errors.append("labels must not contain duplicates")
            if "UNKNOWN" in labels and len(labels) > 1:
                errors.append("UNKNOWN cannot coexist with a supported target role")
            if label is not None:
                scalar_labels = [label] if isinstance(label, str) else label
                if scalar_labels != labels:
                    errors.append("label and labels disagree")

    evidence_type = record.get("evidence_type")
    if evidence_type not in (None, "explicit", "contextual"):
        errors.append(
            "evidence_type must be null, 'explicit', or 'contextual'"
        )

    difficulty = record.get("difficulty")
    if difficulty not in (None, "easy", "medium", "hard"):
        errors.append("difficulty must be null, 'easy', 'medium', or 'hard'")

    distractor = record.get("contains_distractor_role")
    if distractor is not None and not isinstance(distractor, bool):
        errors.append("contains_distractor_role must be a boolean or null")

    start = record.get("entity_start")
    end = record.get("entity_end")
    text = record.get("text")
    entity = record.get("entity")
    # Rejected/skipped review records retain the original unusable span for
    # provenance. They are explicitly excluded from validated annotations.
    retain_unusable_span = (
        record.get("review_status") in ("rejected", "skipped")
        and record.get("human_validated") is False
    )
    if retain_unusable_span:
        pass
    elif start is None and end is None:
        if (
            isinstance(text, str)
            and isinstance(entity, str)
            and entity not in text
        ):
            errors.append("entity does not occur in text")
    elif type(start) is not int or type(end) is not int:
        errors.append("entity_start and entity_end must both be integers or null")
    elif isinstance(text, str) and not 0 <= start < end <= len(text):
        errors.append("entity offsets are outside text bounds")
    elif (
        isinstance(text, str)
        and isinstance(entity, str)
        and text[start:end] != entity
    ):
        errors.append("text[entity_start:entity_end] does not equal entity")

    if not isinstance(record.get("human_validated"), bool):
        errors.append("human_validated must be a boolean")

    if "review_status" in record:
        errors.extend(validate_review_fields(record))

    return errors


def validate_review_fields(record):
    """Consistency rules for new human-review records only."""
    errors = []
    status = record.get("review_status")
    if status not in ("accepted", "uncertain", "rejected", "skipped"):
        errors.append("invalid review_status")
    labels = record.get("labels")
    if not isinstance(labels, list):
        errors.append("review records require a labels list")
    if not isinstance(record.get("review_note"), str):
        errors.append("review_note must be a string")
    if not isinstance(record.get("human_confirmed"), bool):
        errors.append("human_confirmed must be a boolean")
    evidence = record.get("annotation_evidence")
    if evidence not in (None, "explicit", "implicit", "uncertain", "not_applicable"):
        errors.append("invalid annotation_evidence")

    if status in ("accepted", "uncertain"):
        if not labels:
            errors.append("accepted/uncertain reviews require at least one label")
        if record.get("difficulty") not in ("easy", "medium", "hard"):
            errors.append("accepted/uncertain reviews require difficulty")
        if not isinstance(record.get("contains_distractor_role"), bool):
            errors.append("accepted/uncertain reviews require a distractor boolean")
        if evidence is None:
            errors.append("accepted/uncertain reviews require annotation_evidence")
        expected_type = {"explicit": "explicit", "implicit": "contextual"}.get(
            evidence if isinstance(evidence, str) else ""
        )
        if record.get("evidence_type") != expected_type:
            errors.append("evidence_type does not match annotation_evidence")

    if status == "accepted":
        if record.get("human_validated") is not True or record.get("human_confirmed") is not True:
            errors.append("accepted reviews require explicit human confirmation and validation")
        if evidence not in ("explicit", "implicit", "not_applicable"):
            errors.append("uncertain evidence cannot be accepted")
        start, end, text = record.get("entity_start"), record.get("entity_end"), record.get("text")
        if type(start) is not int or type(end) is not int or not isinstance(text, str):
            errors.append("accepted reviews require exact entity offsets")
    elif record.get("human_validated") is not False:
        errors.append("only accepted reviews may be human_validated")

    if status in ("rejected", "skipped"):
        if labels != []:
            errors.append("rejected/skipped reviews must have an empty labels list")
        if record.get("human_confirmed") is not False:
            errors.append("rejected/skipped reviews cannot confirm a role annotation")
        if any(record.get(field) is not None for field in (
            "annotation_evidence", "evidence_type", "difficulty", "contains_distractor_role"
        )):
            errors.append("rejected/skipped reviews must leave annotation metadata unset")
    if evidence == "not_applicable" and labels != ["UNKNOWN"]:
        errors.append("not_applicable evidence requires UNKNOWN only")
    if record.get("review_schema_version") == 2 and status == "accepted" and labels == ["UNKNOWN"] and evidence != "not_applicable":
        errors.append("schema-v2 accepted UNKNOWN requires not_applicable evidence")
    if "role_scope_by_label" in record:
        scopes = record["role_scope_by_label"]
        if (not isinstance(scopes, dict) or not isinstance(labels, list)
                or not all(isinstance(label, str) for label in labels) or set(scopes) != set(labels)):
            errors.append("role_scope_by_label must match the selected labels")
        else:
            for label, scope in scopes.items():
                if scope not in ("current_proceeding", "cited_proceeding", "current_and_cited", "unclear", "not_applicable"):
                    errors.append("invalid role proceeding scope")
                if (label == "UNKNOWN") != (scope == "not_applicable"):
                    errors.append("not_applicable proceeding scope is reserved for UNKNOWN")
            cited = any(scope in ("cited_proceeding", "current_and_cited") for scope in scopes.values())
            if record.get("has_cited_proceeding_roles") is not cited:
                errors.append("has_cited_proceeding_roles disagrees with role scope")
        if record.get("annotation_task") != "mention_level":
            errors.append("scoped reviews must declare annotation_task=mention_level")
    return errors


def validate_candidate_file(path, fine_labels):
    errors = []
    seen_ids = {}
    suggested_distribution = Counter()
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
            for error in validate_candidate_record(record, fine_labels):
                errors.append(f"{path}:{line_number}: {error}")

            if not isinstance(record, dict):
                continue
            record_id = record.get("id")
            if isinstance(record_id, str):
                if record_id in seen_ids:
                    errors.append(
                        f"{path}:{line_number}: duplicate id {record_id!r} "
                        f"(first seen on line {seen_ids[record_id]})"
                    )
                else:
                    seen_ids[record_id] = line_number
            if record.get("suggested_label") in fine_labels:
                suggested_distribution[record["suggested_label"]] += 1

    return record_count, suggested_distribution, errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate an Experiment 19a role-candidate JSONL pool."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH
    )
    args = parser.parse_args()

    if not args.path.is_file():
        parser.error(f"candidate file does not exist: {args.path}")

    fine_labels, _ = load_taxonomy(args.config)
    record_count, distribution, errors = validate_candidate_file(
        args.path, fine_labels
    )

    print("Suggested-label distribution:")
    for label in fine_labels:
        print(f"  {label}: {distribution[label]}")
    print(f"Records: {record_count}")

    if errors:
        for error in errors:
            print(error)
        print(f"Validation failed: {len(errors)} error(s).")
        raise SystemExit(1)
    print("Validation passed.")


if __name__ == "__main__":
    main()
