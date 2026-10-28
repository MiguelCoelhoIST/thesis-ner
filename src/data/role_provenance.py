"""Local identifier evidence for STJ candidates; no judgment text in reports."""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


RAW_DATA_DIR = Path(__file__).resolve().parents[2] / "data/raw"
ID_PATTERN = (
    r"\d{1,7}/\d{2,4}\.\d[A-Z][A-Z0-9]*"
    r"(?:-[A-Z0-9]+)?(?:\.(?:[A-Z]\d+[A-Z0-9-]*|[A-Z]))*"
)
ID_RE = re.compile(r"(?<![\w/])" + ID_PATTERN + r"(?!\w)", re.IGNORECASE)
HEADER_RE = re.compile(
    r"^[ \t]*(?:processo|proc\.?)[ \t]*(?:n[.º°o]*[ \t]*)?[:=-]?[ \t]*"
    r"(?P<identifier>" + ID_PATTERN + r")(?!\w)",
    re.IGNORECASE | re.MULTILINE,
)


def normalize_decision_id(value):
    """Canonical spelling, retaining decision/incident suffixes such as .S2."""
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", "", value).upper()
    return value if re.fullmatch(ID_PATTERN, value) else None


def normalize_process_group_id(value):
    decision = normalize_decision_id(value)
    if decision is None:
        return None
    match = re.match(r"(\d+)/(\d{2,4})\.(\d[A-Z][A-Z0-9]*)", decision)
    return f"{int(match[1])}/{match[2]}.{match[3]}"


def filename_identifier_evidence(source_file):
    name = Path(source_file).name
    # Remove conversion suffixes without swallowing .S1/.S2 decision suffixes.
    name = re.sub(r"(?:\.(?:docx?|rtf|txt|text|html?|jsonl?|md))+$", "", name, flags=re.I)
    pattern = re.compile(
        r"(?<!\d)(?P<number>\d{1,7})[/_-](?P<year>\d{2,4})[._]"
        r"(?P<tail>\d[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)?"
        r"(?:[._](?:[A-Z]\d+[A-Z0-9-]*|[A-Z]))*)(?!\w)", re.I,
    )
    evidence = []
    for match in pattern.finditer(name):
        identifier = f"{match['number']}/{match['year']}.{match['tail'].replace('_', '.')}".upper()
        evidence.append({"raw": match.group(), "decision_id": identifier,
                         "start": match.start(), "end": match.end()})
    return evidence


def extract_process_provenance(text, source_file, legacy_process_number=None):
    """Never promote an arbitrary body reference to the source decision ID."""
    header_end = min(len(text), 3000)
    lines = text.splitlines(keepends=True)
    header_end = min(header_end, sum(map(len, lines[:40])))
    headers = []
    for match in HEADER_RE.finditer(text[:header_end]):
        start, end = match.span("identifier")
        headers.append({
            "raw": text[start:end], "decision_id": normalize_decision_id(text[start:end]),
            "start": start, "end": end, "line": text.count("\n", 0, start) + 1,
        })
    filenames = filename_identifier_evidence(source_file)
    header_offsets = {item["start"] for item in headers}
    references = [
        {"raw": match.group(), "decision_id": normalize_decision_id(match.group()),
         "start": match.start(), "end": match.end(),
         "location": "header" if match.start() in header_offsets else "body_reference"}
        for match in ID_RE.finditer(text)
    ]
    header_ids = sorted({item["decision_id"] for item in headers})
    filename_ids = sorted({item["decision_id"] for item in filenames})
    identity_ids = sorted(set(header_ids + filename_ids))
    groups = sorted({normalize_process_group_id(value) for value in identity_ids})
    if len(identity_ids) > 1:
        status = "conflict"
    elif header_ids and filename_ids:
        status = "header_filename_agree"
    elif header_ids:
        status = "header_only"
    elif filename_ids:
        status = "filename_only"
    else:
        status = "unresolved"
    return {
        "source_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "decision_id": identity_ids[0] if len(identity_ids) == 1 else None,
        "decision_id_candidates": identity_ids,
        "process_group_id": groups[0] if len(groups) == 1 else None,
        "process_group_id_candidates": groups,
        "process_provenance": {
            "status": status, "requires_review": status != "header_filename_agree",
            "header_evidence": headers, "filename_evidence": filenames,
            "detected_references": references,
            "legacy_process_number": legacy_process_number,
            "legacy_value_is_verified_decision_id": False,
        },
    }


def audit_metadata(input_dir, max_documents=None):
    # Import lazily: the extractor imports provenance during normal extraction.
    from src.data.extract_role_candidates_v2 import SUPPORTED_SUFFIXES, read_documents

    documents = []
    failures = []
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if max_documents is not None and len(documents) >= max_documents:
            break
        relative = path.relative_to(input_dir).as_posix()
        try:
            extracted = read_documents(path)
        except (ValueError, OSError, UnicodeError) as exc:
            failures.append({"source_file": relative, "reason": type(exc).__name__})
            continue
        for document_key, text, legacy in extracted:
            if max_documents is not None and len(documents) >= max_documents:
                break
            documents.append({
                "source_file": relative, "source_document_id": document_key,
                "source_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                **extract_process_provenance(text, relative, legacy),
            })
    return {
        "documents": documents, "failures": failures,
        "status_counts": dict(Counter(row["process_provenance"]["status"] for row in documents)),
        "requires_review": sum(row["process_provenance"]["requires_review"] for row in documents),
    }


def main():
    parser = argparse.ArgumentParser(description="Audit STJ identifier provenance locally without NER.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-documents", type=int)
    args = parser.parse_args()
    if not args.input_dir.is_dir():
        parser.error("input directory does not exist")
    if not args.output.resolve().is_relative_to(RAW_DATA_DIR.resolve()):
        parser.error("output must be under ignored data/raw/")
    if args.output.exists():
        parser.error("output already exists")
    if args.max_documents is not None and args.max_documents < 1:
        parser.error("max-documents must be positive")
    report = audit_metadata(args.input_dir, args.max_documents)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(f"Metadata documents: {len(report['documents'])}; failures: {len(report['failures'])}")
    print(f"Status counts: {report['status_counts']}; require review: {report['requires_review']}")
    return 1 if report["failures"] or not report["documents"] else 0


if __name__ == "__main__":
    # Support direct execution while keeping all operational work local.
    import sys
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    raise SystemExit(main())
