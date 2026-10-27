import argparse
import hashlib
import html
import json
import random
import re
import sys
import zipfile
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree


SEED = 42
SUPPORTED_SUFFIXES = {
    ".txt", ".text", ".md", ".html", ".htm", ".json", ".jsonl", ".docx", ".rtf"
}
RAW_DATA_DIR = Path(__file__).resolve().parents[2] / "data/raw"
MAX_PER_ROLE_PER_DOCUMENT = 3
MAX_PER_DOCUMENT = 12
ENTITY_SEARCH_CHARS = 120

ROLE_ANCHORS = {
    "ARGUIDO": ("arguido", "arguida", "arguidos", "arguidas"),
    "REU": ("réu", "ré", "réus", "rés"),
    "AUTOR": ("autor", "autora", "autores", "autoras"),
    "REQUERENTE": ("requerente", "requerentes"),
    "RECORRENTE": ("recorrente", "recorrentes"),
    "RECORRIDO": ("recorrido", "recorrida", "recorridos", "recorridas"),
    "TESTEMUNHA": ("testemunha", "testemunhas"),
    "RELATOR": ("relator", "relatora"),
}

PROCESS_NUMBER_RE = re.compile(
    r"\b\d{1,7}/\d{2,4}(?:\.[A-Z0-9-]+)+\b", re.IGNORECASE
)
PLACEHOLDER_RE = re.compile(r"\b[A-Z]{2}(?:\d+)?\b")
CAPITALIZED_WORD = (
    r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]"
    r"[a-záàâãéêíóôõúüç]+"
    r"(?:[-'][A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]?[a-záàâãéêíóôõúüç]+)*"
)
PERSON_NAME_RE = re.compile(
    rf"\b{CAPITALIZED_WORD}(?:\s+(?:da|das|de|do|dos|e)\s+|\s+){CAPITALIZED_WORD}"
    rf"(?:\s+(?:da|das|de|do|dos|e)\s+{CAPITALIZED_WORD}|\s+{CAPITALIZED_WORD}){{0,3}}\b"
)

ANCHOR_PATTERNS = {
    label: re.compile(
        r"\b(?:" + "|".join(re.escape(anchor) for anchor in anchors) + r")\b",
        re.IGNORECASE,
    )
    for label, anchors in ROLE_ANCHORS.items()
}
ANCHOR_WORDS = {
    anchor.casefold() for anchors in ROLE_ANCHORS.values() for anchor in anchors
}


class DocumentReadError(ValueError):
    """An input cannot be reliably read; the reason is safe for the audit."""


def read_docx(path):
    """Read OOXML body paragraphs and table cells in document order."""
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as document:
            root = ElementTree.fromstring(document.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise DocumentReadError("invalid or unsupported DOCX package") from exc
    body = root.find(f"{namespace}body")
    if body is None:
        raise DocumentReadError("DOCX has no document body")
    paragraphs = []
    for paragraph in body.iter(f"{namespace}p"):
        parts = []
        for element in paragraph.iter():
            if element.tag == f"{namespace}t":
                parts.append(element.text or "")
            elif element.tag == f"{namespace}tab":
                parts.append("\t")
            elif element.tag in {f"{namespace}br", f"{namespace}cr"}:
                parts.append("\n")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


def read_rtf(path):
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError as exc:
        raise DocumentReadError("RTF requires striprtf; install requirements.txt") from exc
    raw = path.read_bytes()
    if not raw.lstrip().startswith(b"{\\rtf"):
        raise DocumentReadError("file is not an RTF document")
    # RTF control words and escaped byte sequences are ASCII; use the declared
    # ANSI code page for literal bytes and let striprtf interpret RTF escapes.
    codepage = re.search(rb"\\ansicpg(\d+)", raw[:4096])
    encoding = f"cp{codepage.group(1).decode('ascii')}" if codepage else "cp1252"
    try:
        return rtf_to_text(raw.decode(encoding), encoding=encoding, errors="strict")
    except (LookupError, UnicodeError, ValueError, IndexError) as exc:
        raise DocumentReadError("RTF decoding failed; convert with LibreOffice") from exc


def stable_process_id(process_number):
    if not process_number:
        return None
    compact = re.sub(r"\s+", "", process_number).upper()
    # Group appellate versions and incident suffixes under their root process.
    match = re.match(r"(\d+/\d{2,4}\.\d[A-Z0-9]+)", compact)
    return match.group(1) if match else compact


def process_number_from_filename(path):
    stem = re.sub(r"(\d+)_(\d{2,4})_(\d[A-Za-z0-9]+)", r"\1/\2.\3", path.stem)
    return process_number_from_text(stem)


def candidate_process_key(candidate):
    return stable_process_id(candidate["process_number"]) or (
        "missing:" + str(Path(candidate["source_file"]).with_suffix("")).casefold()
    )


class TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data)

    def text(self):
        return "\n".join(self.parts)


def html_to_text(value):
    parser = TextHTMLParser()
    parser.feed(value)
    return html.unescape(parser.text())


def process_number_from_text(text):
    match = PROCESS_NUMBER_RE.search(text[:5000])
    return match.group(0) if match else None


def extract_json_documents(value, source_key):
    if isinstance(value, list):
        documents = []
        for index, item in enumerate(value):
            documents.extend(extract_json_documents(item, f"{source_key}#{index + 1}"))
        return documents
    if not isinstance(value, dict):
        return []

    text = next(
        (
            value[field]
            for field in ("text", "content", "body", "judgment", "document_text")
            if isinstance(value.get(field), str) and value[field].strip()
        ),
        None,
    )
    if text is None:
        return []
    process_number = value.get("process_number")
    if not isinstance(process_number, str) or not process_number.strip():
        process_number = process_number_from_text(text)
    return [(source_key, text, process_number)]


def read_documents(path):
    suffix = path.suffix.lower()
    if suffix == ".doc":
        raise DocumentReadError("legacy DOC requires pre-conversion to DOCX with LibreOffice")
    if suffix == ".docx":
        text = read_docx(path)
        return [(path.name, text, process_number_from_text(text))]
    if suffix == ".rtf":
        text = read_rtf(path)
        return [(path.name, text, process_number_from_text(text))]
    raw = path.read_text(encoding="utf-8-sig")

    if suffix in {".txt", ".text", ".md"}:
        return [(path.name, raw, process_number_from_text(raw))]
    if suffix in {".html", ".htm"}:
        text = html_to_text(raw)
        return [(path.name, text, process_number_from_text(text))]
    if suffix == ".json":
        return extract_json_documents(json.loads(raw), path.name)
    if suffix == ".jsonl":
        documents = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            documents.extend(
                extract_json_documents(value, f"{path.name}#{line_number}")
            )
        return documents
    return []


def distance_to_anchor(start, end, anchor_start, anchor_end):
    if end <= anchor_start:
        return anchor_start - end
    if start >= anchor_end:
        return start - anchor_end
    return 0


def nearby_entity(text, anchor_start, anchor_end):
    window_start = max(0, anchor_start - ENTITY_SEARCH_CHARS)
    window_end = min(len(text), anchor_end + ENTITY_SEARCH_CHARS)
    window = text[window_start:window_end]
    candidates = []

    for priority, pattern in ((0, PLACEHOLDER_RE), (1, PERSON_NAME_RE)):
        for match in pattern.finditer(window):
            start = window_start + match.start()
            end = window_start + match.end()
            entity = match.group(0)
            if start < anchor_end and end > anchor_start:
                continue
            if entity.casefold() in ANCHOR_WORDS:
                continue
            distance = distance_to_anchor(start, end, anchor_start, anchor_end)
            after_penalty = 0 if start >= anchor_end else 1
            gap = text[end:anchor_start] if end <= anchor_start else text[anchor_end:start]
            # A nearby mention across a sentence boundary is weak evidence.
            boundary_penalty = 1 if re.search(r"[.!?;\n]", gap) else 0
            candidates.append(
                (boundary_penalty, distance, after_penalty, priority, start, end, entity)
            )

    if not candidates:
        return None
    _, _, _, _, start, end, entity = min(candidates)
    return entity, start, end


def candidate_id(source_file, document_key, label, anchor_start, entity_start):
    identity = f"{source_file}|{document_key}|{label}|{anchor_start}|{entity_start}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"stj-role-candidate-{digest}"


def discover_candidates(
    text,
    source_file="synthetic.txt",
    process_number=None,
    context_chars=240,
    document_key=None,
):
    document_key = document_key or source_file
    discovered = []

    for suggested_label, pattern in ANCHOR_PATTERNS.items():
        role_candidates = []
        for anchor_match in pattern.finditer(text):
            entity_match = nearby_entity(
                text, anchor_match.start(), anchor_match.end()
            )
            if entity_match is None:
                continue

            entity, entity_absolute_start, entity_absolute_end = entity_match
            span_start = min(anchor_match.start(), entity_absolute_start)
            span_end = max(anchor_match.end(), entity_absolute_end)
            context_start = max(0, span_start - context_chars)
            context_end = min(len(text), span_end + context_chars)
            context = text[context_start:context_end]
            entity_start = entity_absolute_start - context_start
            entity_end = entity_absolute_end - context_start

            role_candidates.append(
                {
                    "id": candidate_id(
                        source_file,
                        document_key,
                        suggested_label,
                        anchor_match.start(),
                        entity_absolute_start,
                    ),
                    "source_file": source_file,
                    "process_number": process_number,
                    "text": context,
                    "entity": entity,
                    "entity_start": entity_start,
                    "entity_end": entity_end,
                    "suggested_label": suggested_label,
                    "label": None,
                    "evidence_type": None,
                    "difficulty": None,
                    "contains_distractor_role": None,
                    "human_validated": False,
                }
            )
        role_candidates.sort(key=lambda item: (evidence_rank(item), item["id"]))
        discovered.extend(role_candidates[:MAX_PER_ROLE_PER_DOCUMENT])

    discovered.sort(key=lambda item: (evidence_rank(item), item["id"]))
    return discovered[:MAX_PER_DOCUMENT]


def is_hard_context(candidate):
    text = candidate["text"]
    mentions = {
        (match.start(), match.end())
        for pattern in (PLACEHOLDER_RE, PERSON_NAME_RE)
        for match in pattern.finditer(text)
    }
    roles = sum(bool(pattern.search(text)) for pattern in ANCHOR_PATTERNS.values())
    return len(mentions) > 1 or roles > 1


def evidence_rank(candidate):
    """Prefer adjacent anchor/target links; this is a heuristic, never a label."""
    start, end = candidate["entity_start"], candidate["entity_end"]
    text = candidate["text"]
    links = []
    for anchor in ANCHOR_PATTERNS[candidate["suggested_label"]].finditer(text):
        if anchor.end() <= start:
            gap = text[anchor.end():start]
        elif end <= anchor.start():
            gap = text[end:anchor.start()]
        else:
            continue
        direct = bool(re.fullmatch(r"[\s,:()\-]*", gap))
        links.append((0 if direct else 1, len(gap)))
    return min(links, default=(2, len(text)))


def normalized_candidate_text(text):
    return " ".join(text.casefold().split())


def deduplicate_candidates(candidates):
    unique = []
    exact_keys = set()
    comparison_groups = defaultdict(list)

    for candidate in sorted(candidates, key=lambda item: item["id"]):
        normalized_text = normalized_candidate_text(candidate["text"])
        key = (
            candidate_process_key(candidate),
            candidate["suggested_label"],
            candidate["entity"].casefold(),
            normalized_text,
        )
        if key in exact_keys:
            continue

        group_key = key[:3]
        near_duplicate = any(
            SequenceMatcher(None, existing_text, normalized_text).ratio() >= 0.92
            for existing_text in comparison_groups[group_key]
        )
        if near_duplicate:
            continue

        exact_keys.add(key)
        comparison_groups[group_key].append(normalized_text)
        unique.append(candidate)
    return unique


def deterministic_sample(
    candidates, max_per_role, seed=SEED, hard_share=0.25, max_per_process_role=2
):
    grouped = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["suggested_label"]].append(candidate)

    rng = random.Random(seed)
    sampled = []
    process_totals = Counter()
    for role in ROLE_ANCHORS:
        role_candidates = sorted(grouped[role], key=lambda item: item["id"])
        rng.shuffle(role_candidates)
        tie_order = {item["id"]: index for index, item in enumerate(role_candidates)}
        process_counts = Counter()
        selected = []
        hard_count = 0
        available_per_process = Counter(candidate_process_key(item) for item in role_candidates)
        attainable_count = min(max_per_role, sum(
            min(count, max_per_process_role) for count in available_per_process.values()
        ))
        target_hard = int(attainable_count * hard_share + 0.5)
        while role_candidates and len(selected) < max_per_role:
            eligible = [
                item for item in role_candidates
                if process_counts[candidate_process_key(item)] < max_per_process_role
                and process_totals[candidate_process_key(item)] < MAX_PER_DOCUMENT
            ]
            if not eligible:
                break
            # First exhaust distinct processes; then aim at the context quota.
            prefer_hard = hard_count < target_hard
            chosen = min(
                eligible,
                key=lambda item: (
                    process_counts[candidate_process_key(item)],
                    is_hard_context(item) != prefer_hard,
                    evidence_rank(item),
                    tie_order[item["id"]],
                ),
            )
            role_candidates.remove(chosen)
            selected.append(chosen)
            hard_count += is_hard_context(chosen)
            process_counts[candidate_process_key(chosen)] += 1
            process_totals[candidate_process_key(chosen)] += 1
        sampled.extend(selected)
    return sampled


def audit_corpus(input_dir, context_chars=240):
    """Read every input file, accounting for failures without storing its text."""
    paths = sorted(path for path in input_dir.rglob("*") if path.is_file())
    audit = {
        "detected_files": len(paths),
        "files_by_extension": dict(sorted(Counter(
            path.suffix.lower() or "<no extension>" for path in paths
        ).items())),
        "supported_files": 0,
        "successfully_extracted_files": 0,
        "successfully_extracted_documents": 0,
        "failed_files": [],
        "skipped_files": [],
        "documents_contributing_candidates": 0,
        "documents_without_process_id": [],
    }
    candidates = []
    for path in paths:
        source_file = path.relative_to(input_dir).as_posix()
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            reason = (
                "legacy DOC requires pre-conversion to DOCX with LibreOffice"
                if suffix == ".doc" else "unsupported file extension"
            )
            audit["skipped_files"].append({"source_file": source_file, "reason": reason})
            continue
        audit["supported_files"] += 1
        try:
            documents = read_documents(path)
        except DocumentReadError as exc:
            audit["failed_files"].append({"source_file": source_file, "reason": str(exc)})
            continue
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            audit["failed_files"].append({
                "source_file": source_file,
                "reason": f"document extraction failed ({type(exc).__name__})",
            })
            continue
        documents = [document for document in documents if document[1].strip()]
        if not documents:
            audit["failed_files"].append({
                "source_file": source_file, "reason": "no extractable document text"
            })
            continue
        audit["successfully_extracted_files"] += 1
        audit["successfully_extracted_documents"] += len(documents)
        for document_key, text, process_number in documents:
            process_number = process_number or process_number_from_filename(path)
            if not process_number:
                audit["documents_without_process_id"].append({
                    "source_file": source_file, "document_key": document_key
                })
            found = discover_candidates(
                text, source_file, process_number, context_chars, document_key
            )
            audit["documents_contributing_candidates"] += bool(found)
            candidates.extend(found)
    audit["failed_count"] = len(audit["failed_files"])
    audit["skipped_count"] = len(audit["skipped_files"])
    audit["discovered_candidates_by_role"] = {
        role: sum(item["suggested_label"] == role for item in candidates)
        for role in ROLE_ANCHORS
    }
    audit["distinct_process_numbers_discovered"] = sorted({
        stable_process_id(item["process_number"])
        for item in candidates if item["process_number"]
    })
    return candidates, audit


def require_extracted_candidates(audit, candidates):
    if not audit["successfully_extracted_documents"]:
        raise ValueError("No supported documents were successfully extracted; see audit reasons.")
    if not candidates:
        raise ValueError("No role candidates were extracted; see audit counts and input formats.")


def print_audit(audit):
    print("Detected files by extension:")
    for extension, count in audit["files_by_extension"].items():
        print(f"  {extension}: {count}")
    for field in (
        "detected_files", "successfully_extracted_files",
        "successfully_extracted_documents", "failed_count", "skipped_count",
        "documents_contributing_candidates",
    ):
        print(f"{field}: {audit[field]}")
    for field in ("failed_files", "skipped_files"):
        for item in audit[field]:
            print(f"{field}: {item['source_file']}: {item['reason']}")
    print(f"Documents with missing process IDs: {len(audit['documents_without_process_id'])}")
    print(f"Distinct discovered process IDs: {len(audit['distinct_process_numbers_discovered'])}")
    print("Candidate counts by suggested role (discovered / selected):")
    for role in ROLE_ANCHORS:
        print(f"  {role}: {audit['discovered_candidates_by_role'][role]} / "
              f"{audit['selected_candidates_by_role'][role]}")
    print(f"Distinct selected process IDs: {len(audit['distinct_process_numbers_selected'])}")
    print(f"Selected candidates with missing process IDs: {audit['selected_missing_process_ids']}")
    print(f"Selected hard-context heuristic count: {audit['selected_hard_contexts']}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract non-gold legal-role candidates from STJ judgments."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-per-role", type=int, default=100)
    parser.add_argument("--context-chars", type=int, default=240)
    parser.add_argument("--audit-only", action="store_true", help="Inspect inputs and candidates without writing a pool")
    parser.add_argument("--audit-json", type=Path, help="New audit JSON path under ignored data/raw/")
    parser.add_argument("--hard-share", type=float, default=0.25, help="Target share of multi-person/multi-role contexts (default: 0.25)")
    parser.add_argument("--max-per-process-role", type=int, default=2, help="Maximum candidates per root process per role (default: 2)")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        parser.error(f"input directory does not exist: {args.input_dir}")
    if not args.audit_only and args.output is None:
        parser.error("--output is required unless --audit-only is selected")
    if args.output is not None and args.output.exists():
        parser.error(f"output already exists: {args.output}")
    if args.max_per_role < 1:
        parser.error("--max-per-role must be at least 1")
    if args.context_chars < 1:
        parser.error("--context-chars must be at least 1")
    if not 0 <= args.hard_share <= 1:
        parser.error("--hard-share must be between 0 and 1")
    if args.max_per_process_role < 1:
        parser.error("--max-per-process-role must be at least 1")
    if args.audit_json is not None:
        if not args.audit_json.resolve().is_relative_to(RAW_DATA_DIR.resolve()):
            parser.error("--audit-json must be under the ignored data/raw/ directory")
        if args.audit_json.exists():
            parser.error(f"audit output already exists: {args.audit_json}")
        if args.output is not None and args.output.resolve() == args.audit_json.resolve():
            parser.error("candidate and audit outputs must be different")

    all_candidates, audit = audit_corpus(args.input_dir, args.context_chars)

    unique_candidates = deduplicate_candidates(all_candidates)
    sampled_candidates = deterministic_sample(
        unique_candidates, args.max_per_role, hard_share=args.hard_share,
        max_per_process_role=args.max_per_process_role,
    )
    audit.update({
        "seed": SEED, "hard_share_target": args.hard_share,
        "max_per_role": args.max_per_role, "context_chars": args.context_chars,
        "max_per_process_role": args.max_per_process_role,
        "candidates_before_deduplication": len(all_candidates),
        "candidates_after_deduplication": len(unique_candidates),
        "selected_candidates": len(sampled_candidates),
        "selected_candidates_by_role": {
            role: sum(item["suggested_label"] == role for item in sampled_candidates)
            for role in ROLE_ANCHORS
        },
        "distinct_process_numbers_selected": sorted({
            stable_process_id(item["process_number"])
            for item in sampled_candidates if item["process_number"]
        }),
        "selected_missing_process_ids": sum(not item["process_number"] for item in sampled_candidates),
        "selected_hard_contexts": sum(is_hard_context(item) for item in sampled_candidates),
    })
    try:
        require_extracted_candidates(audit, sampled_candidates)
    except ValueError as exc:
        audit["error"] = str(exc)
    print_audit(audit)
    if args.audit_json is not None:
        args.audit_json.parent.mkdir(parents=True, exist_ok=True)
        with args.audit_json.open("x", encoding="utf-8") as audit_file:
            json.dump(audit, audit_file, ensure_ascii=False, indent=2)
            audit_file.write("\n")
    if "error" in audit:
        print(audit["error"], file=sys.stderr)
        return 1

    if not args.audit_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output_file:
            for candidate in sampled_candidates:
                output_file.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        print(f"Candidates written: {len(sampled_candidates)}")
    print("Suggested labels are lexical discovery hints, not gold labels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
