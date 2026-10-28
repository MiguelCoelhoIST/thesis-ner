import argparse
import hashlib
import html
import json
import random
import re
import sys
import warnings
import zipfile
import threading
import time
from bisect import bisect_left, bisect_right
from collections import Counter, OrderedDict, defaultdict
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.role_provenance import extract_process_provenance


SEED = 42
SUPPORTED_SUFFIXES = {
    ".txt", ".text", ".md", ".html", ".htm", ".json", ".jsonl", ".docx", ".rtf"
}
RAW_DATA_DIR = Path(__file__).resolve().parents[2] / "data/raw"
DEFAULT_NER_MODEL = Path(__file__).resolve().parents[2] / "models/eduardo_extended_model"
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


class ProgressReporter:
    """Flush a heartbeat even while one long transformer batch is running."""

    def __init__(self, interval=10):
        self.interval = interval
        self.started = time.perf_counter()
        self.last_print = self.started
        self.state = {"stage": "starting", "documents": 0, "total": "?", "windows": 0,
                      "candidates": 0, "files": 0, "document_characters": 0, "planned_windows": 0}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)

    def __call__(self, **updates):
        with self.lock:
            previous_stage = self.state["stage"]
            self.state.update(updates)
            if self.state["stage"] != previous_stage or time.perf_counter() - self.last_print >= self.interval:
                self._print()

    def _print(self):
        self.last_print = time.perf_counter()
        value = self.state
        print(
            f"[progress] stage={value['stage']} documents={value['documents']}/{value['total']} "
            f"files_parsed={value['files']} "
            f"elapsed={time.perf_counter() - self.started:.1f}s "
            f"NER_windows_processed={value['windows']} candidates={value['candidates']}",
            f"current_chars={value['document_characters']} current_windows={value['planned_windows']}",
            flush=True,
        )

    def _heartbeat(self):
        while not self.stop.wait(self.interval):
            with self.lock:
                self._print()

    def __enter__(self):
        self.thread.start()
        with self.lock:
            self._print()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()


class WindowPredictionCache:
    """Bounded in-memory reuse of identical inputs to the same loaded model."""

    def __init__(self, capacity=128):
        self.capacity = capacity
        self.entries = OrderedDict()

    def get(self, nlp, text):
        key = (id(nlp), text)
        if key not in self.entries:
            return None
        self.entries.move_to_end(key)
        return self.entries[key]

    def put(self, nlp, text, predictions):
        if self.capacity == 0:
            return
        key = (id(nlp), text)
        self.entries[key] = predictions
        self.entries.move_to_end(key)
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)


def find_role_anchors(text):
    return {
        role: [(match.start(), match.end()) for match in pattern.finditer(text)]
        for role, pattern in ANCHOR_PATTERNS.items()
    }


def load_person_ner(model_path=DEFAULT_NER_MODEL, cpu_threads=4):
    """Load the existing pretrained PER recognizer; never fall back to regex."""
    model_path = Path(model_path)
    setup = (
        "Install requirements.txt in the project venv and restore Eduardo's "
        "iris-lfs-storage/model-extended model to models/eduardo_extended_model "
        "(config.cfg, meta.json, tokenizer, ner/, transformer/ and vocab/). "
        "Alternatively pass --ner-model with the local model directory."
    )
    if not model_path.is_dir() or not (model_path / "config.cfg").is_file():
        raise ValueError(f"Pretrained Eduardo NER model unavailable at {model_path}. {setup}")
    try:
        import spacy
        import torch
        if cpu_threads:
            torch.set_num_threads(cpu_threads)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            nlp = spacy.load(model_path)
        if "ner" not in nlp.pipe_names or "PER" not in nlp.get_pipe("ner").labels:
            raise ValueError("The model must have an enabled ner component with a PER label.")
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        raise ValueError(f"Cannot load pretrained PER model ({type(exc).__name__}). {setup}") from exc
    nlp.meta["candidate_extraction_audit"] = {
        "path": str(model_path.resolve()), "spacy_version": spacy.__version__,
        "model_spacy_version": nlp.meta.get("spacy_version"),
        "pipeline": list(nlp.pipe_names), "ner_labels": list(nlp.get_pipe("ner").labels),
        "config_sha256": hashlib.sha256((model_path / "config.cfg").read_bytes()).hexdigest(),
        "compatibility_warnings": list(dict.fromkeys(str(item.message) for item in caught)),
        "torch_cpu_threads": torch.get_num_threads(),
        "torch_interop_threads": torch.get_num_interop_threads(),
    }
    return nlp


def ner_windows(text, context_chars=240, max_chars=6000, anchors=None):
    """Bounded overlapping windows cover every anchor's entity search area."""
    margin = max(context_chars, ENTITY_SEARCH_CHARS) + 120
    windows = []
    anchors = find_role_anchors(text) if anchors is None else anchors
    for start, end in sorted(span for spans in anchors.values() for span in spans):
        bounded_margin = min(margin, (max_chars - (end - start)) // 2)
        left, right = max(0, start - bounded_margin), min(len(text), end + bounded_margin)
        if windows and left <= windows[-1][1] and right - windows[-1][0] <= max_chars:
            windows[-1] = (windows[-1][0], max(right, windows[-1][1]))
        else:
            windows.append((left, right))
    return windows


def rejected_per_reason(entity):
    """Conservative rejection only: these rules never create a person span."""
    if re.search(r"\b(?:tribunal|tribunais|código|procuradoria|ministério|estrada)\b", entity, re.IGNORECASE):
        return "organization_or_legal_code"
    if re.fullmatch(r"(?:EN|EM|ER|IP|IC|A)(?:[ .-]?\d+)?", entity):
        return "road_abbreviation"
    if re.search(r"\b(?:e|ou)\b|[;,]", entity, re.IGNORECASE):
        return "merged_or_ambiguous_coordination"
    if entity.casefold() in ANCHOR_WORDS or not any(character.isalpha() for character in entity):
        return "not_a_person_target"
    return None


def detect_person_spans(
    text, nlp, context_chars=240, batch_size=4, stats=None,
    anchors=None, prediction_cache=None, progress=None, timings=None,
    windows=None,
):
    stats = stats if stats is not None else Counter()
    timings = timings if timings is not None else Counter()
    started = time.perf_counter()
    windows = ner_windows(text, context_chars, anchors=anchors) if windows is None else windows
    timings["anchor_discovery_seconds"] += time.perf_counter() - started
    prediction_cache = prediction_cache if prediction_cache is not None else WindowPredictionCache()
    stats["ner_windows"] += len(windows)
    stats["document_characters"] += len(text)
    stats["ner_input_characters"] += sum(end - start for start, end in windows)
    covered_end = -1
    for start, end in windows:
        stats["ner_overlap_characters"] += max(0, min(covered_end, end) - start)
        covered_end = max(covered_end, end)
    proposed = set()
    for offset in range(0, len(windows), batch_size):
        batch = windows[offset:offset + batch_size]
        predictions = {}
        missing = []
        for start, end in batch:
            window_text = text[start:end]
            if window_text in predictions:
                stats["ner_window_cache_hits"] += 1
                continue
            cached = prediction_cache.get(nlp, window_text)
            predictions[window_text] = cached
            if cached is None:
                missing.append(window_text)
            else:
                stats["ner_window_cache_hits"] += 1
        # Identical text is inferred once, then projected back onto every source
        # window's original offset. Different overlapping inputs are retained.
        started = time.perf_counter()
        documents = nlp.pipe(missing, batch_size=batch_size, n_process=1) if missing else ()
        for window_text, doc in zip(missing, documents):
            predicted = tuple(
                (entity.start_char, entity.end_char, entity.text, entity.label_)
                for entity in doc.ents
            )
            predictions[window_text] = predicted
            prediction_cache.put(nlp, window_text, predicted)
            stats["ner_windows_processed"] += 1
            stats["ner_characters_inferred"] += len(window_text)
        timings["ner_inference_seconds"] += time.perf_counter() - started
        for window_start, window_end in batch:
            for local_start, local_end, entity_text, label in predictions[text[window_start:window_end]]:
                if label != "PER":
                    stats["non_per_predictions"] += 1
                    continue
                proposed.add((window_start + local_start, window_start + local_end,
                              entity_text, window_start, window_end))
        if progress:
            progress(windows=stats["ner_windows_processed"])
    if progress:
        progress(stage="person_span_filtering")
    started = time.perf_counter()
    accepted = set()
    stats["ner_per_spans_considered"] += len({(start, end) for start, end, *_ in proposed})
    # Unique spans are counted once, even when overlapping windows rediscover them.
    rejected = set()
    for start, end, entity, window_start, window_end in sorted(proposed):
        key = (start, end)
        reason = None
        if not 0 <= start < end <= len(text) or text[start:end] != entity or entity != entity.strip():
            reason = "invalid_ner_offsets"
        elif (start == window_start and start > 0) or (end == window_end and end < len(text)):
            # A window may cut a name. Do not accept that truncated prediction.
            reason = "window_boundary"
        else:
            reason = rejected_per_reason(entity)
        if reason is None:
            accepted.add((start, end, entity))
        else:
            rejected.add((key, reason))
    accepted_keys = {(start, end) for start, end, _ in accepted}
    rejected = {(key, reason) for key, reason in rejected if key not in accepted_keys}
    for _, reason in rejected:
        stats[f"dropped_{reason}"] += 1
    overlapping = set()
    component = []
    component_end = -1
    for span in sorted(accepted):
        if span[0] >= component_end:
            if len(component) > 1:
                overlapping.update(component)
            component = []
        component.append(span)
        component_end = max(span[1], component_end) if len(component) > 1 else span[1]
    if len(component) > 1:
        overlapping.update(component)
    stats["dropped_conflicting_spans"] += len(overlapping)
    accepted -= overlapping
    stats["accepted_per_spans"] += len(accepted)
    stats["merged_spans"] += sum(reason == "merged_or_ambiguous_coordination" for _, reason in rejected)
    stats["dropped_false_entities"] += len(overlapping) + sum(reason != "merged_or_ambiguous_coordination" for _, reason in rejected)
    timings["person_span_filtering_seconds"] += time.perf_counter() - started
    return sorted(accepted)


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
    if "process_provenance" in candidate:
        # Conflicting identity roots require manual resolution before splitting.
        return candidate.get("process_group_id") or (
            "unresolved:" + str(Path(candidate["source_file"]).with_suffix("")).casefold()
        )
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


def person_span_index(person_spans):
    by_start = sorted(person_spans)
    by_end = sorted(person_spans, key=lambda span: span[1])
    return by_start, [span[0] for span in by_start], by_end, [span[1] for span in by_end]


def nearby_entities(text, anchor_start, anchor_end, person_spans, index=None):
    candidates = []
    by_start, starts, by_end, ends = index if index is not None else person_span_index(person_spans)
    nearby = (
        by_end[bisect_left(ends, anchor_start - ENTITY_SEARCH_CHARS):bisect_right(ends, anchor_start)]
        + by_start[bisect_left(starts, anchor_end):bisect_right(starts, anchor_end + ENTITY_SEARCH_CHARS)]
    )
    for start, end, entity in nearby:
        if start < anchor_end and end > anchor_start:
            continue
        distance = distance_to_anchor(start, end, anchor_start, anchor_end)
        if distance > ENTITY_SEARCH_CHARS:
            continue
        gap = text[end:anchor_start] if end <= anchor_start else text[anchor_end:start]
        boundary_penalty = 1 if re.search(r"[.!?;\n]", gap) else 0
        candidates.append((boundary_penalty, distance, start, end, entity))
    return [(entity, start, end) for _, _, start, end, entity in sorted(candidates)]


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
    person_spans=None,
    nlp=None,
    batch_size=4,
    stats=None,
    anchors=None,
    provenance=None,
    role_link_counts=None,
):
    document_key = document_key or source_file
    anchors = find_role_anchors(text) if anchors is None else anchors
    if person_spans is None:
        nlp = nlp if nlp is not None else load_person_ner()
        person_spans = detect_person_spans(text, nlp, context_chars, batch_size, stats, anchors=anchors)
    index = person_span_index(person_spans)
    by_start, starts, _, _ = index
    discovered = []

    for suggested_label in ROLE_ANCHORS:
        role_candidates = []
        for anchor_start, anchor_end in anchors[suggested_label]:
            linked_entities = nearby_entities(
                text, anchor_start, anchor_end, person_spans, index=index
            )
            if linked_entities and role_link_counts is not None:
                role_link_counts[suggested_label] += 1
            for entity, entity_absolute_start, entity_absolute_end in linked_entities:
                span_start = min(anchor_start, entity_absolute_start)
                span_end = max(anchor_end, entity_absolute_end)
                context_start = max(0, span_start - context_chars)
                context_end = min(len(text), span_end + context_chars)
                context = text[context_start:context_end]
                entity_start = entity_absolute_start - context_start
                entity_end = entity_absolute_end - context_start

                role_candidates.append({
                    "id": candidate_id(
                        source_file,
                        document_key,
                        suggested_label,
                        anchor_start,
                        entity_absolute_start,
                    ),
                    "source_file": source_file,
                    "source_document_id": document_key,
                    "process_number": process_number,
                    **(provenance or {}),
                    "text": context,
                    "entity": entity,
                    "entity_start": entity_start,
                    "entity_end": entity_end,
                    "entity_document_start": entity_absolute_start,
                    "entity_document_end": entity_absolute_end,
                    "entity_detection": "spacy:PER",
                    "context_per_count": sum(
                        end <= context_end
                        for start, end, _ in by_start[
                            bisect_left(starts, context_start):bisect_right(starts, context_end)
                        ]
                    ),
                    "suggested_label": suggested_label,
                    "label": None,
                    "evidence_type": None,
                    "difficulty": None,
                    "contains_distractor_role": None,
                    "human_validated": False,
                })
        # Multiple anchors may rediscover exactly the same target/context.
        role_candidates = list({
            (row["entity_document_start"], row["entity_document_end"], row["text"]): row
            for row in role_candidates
        }.values())
        role_candidates.sort(key=lambda item: (evidence_rank(item), item["id"]))
        discovered.extend(role_candidates[:MAX_PER_ROLE_PER_DOCUMENT])

    discovered.sort(key=lambda item: (evidence_rank(item), item["id"]))
    return discovered[:MAX_PER_DOCUMENT]


def is_hard_context(candidate):
    text = candidate["text"]
    roles = sum(bool(pattern.search(text)) for pattern in ANCHOR_PATTERNS.values())
    return candidate.get("context_per_count", 1) > 1 or roles > 1


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
            matcher.real_quick_ratio() >= 0.92 and matcher.quick_ratio() >= 0.92
            and matcher.ratio() >= 0.92
            for existing_text in comparison_groups[group_key]
            for matcher in [SequenceMatcher(None, existing_text, normalized_text)]
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
    state = {}
    process_keys = {item["id"]: candidate_process_key(item) for item in candidates}
    hard_contexts = {item["id"]: is_hard_context(item) for item in candidates}
    evidence_ranks = {item["id"]: evidence_rank(item) for item in candidates}
    for role in ROLE_ANCHORS:
        role_candidates = sorted(grouped[role], key=lambda item: item["id"])
        rng.shuffle(role_candidates)
        tie_order = {item["id"]: index for index, item in enumerate(role_candidates)}
        available_per_process = Counter(candidate_process_key(item) for item in role_candidates)
        attainable_count = min(max_per_role, sum(
            min(count, max_per_process_role) for count in available_per_process.values()
        ))
        state[role] = {
            "remaining": role_candidates, "tie_order": tie_order,
            "process_counts": Counter(), "selected": 0, "hard_count": 0,
            "target_hard": int(attainable_count * hard_share + 0.5),
        }
    # Round-robin avoids consuming process budgets before later roles are visited.
    while True:
        made_progress = False
        for role in ROLE_ANCHORS:
            current = state[role]
            if current["selected"] >= max_per_role:
                continue
            eligible = [
                item for item in current["remaining"]
                if current["process_counts"][process_keys[item["id"]]] < max_per_process_role
                and process_totals[process_keys[item["id"]]] < MAX_PER_DOCUMENT
            ]
            if not eligible:
                continue
            # First exhaust distinct processes; then aim at the context quota.
            prefer_hard = current["hard_count"] < current["target_hard"]
            chosen = min(
                eligible,
                key=lambda item: (
                    current["process_counts"][process_keys[item["id"]]],
                    process_totals[process_keys[item["id"]]],
                    hard_contexts[item["id"]] != prefer_hard,
                    evidence_ranks[item["id"]],
                    current["tie_order"][item["id"]],
                ),
            )
            current["remaining"].remove(chosen)
            sampled.append(chosen)
            current["selected"] += 1
            current["hard_count"] += is_hard_context(chosen)
            current["process_counts"][candidate_process_key(chosen)] += 1
            process_totals[candidate_process_key(chosen)] += 1
            made_progress = True
        if not made_progress:
            break
    return sampled


def audit_corpus(
    input_dir, context_chars=240, nlp=None, batch_size=4,
    max_documents=None, progress=None, window_cache_size=128,
):
    """Read every input file, accounting for failures without storing its text."""
    nlp = nlp if nlp is not None else load_person_ner()
    ner_stats = Counter()
    timings = Counter({key: 0.0 for key in (
        "file_parsing_seconds", "anchor_discovery_seconds", "ner_inference_seconds",
        "person_span_filtering_seconds", "candidate_selection_seconds", "provenance_extraction_seconds",
    )})
    paths = sorted(path for path in input_dir.rglob("*") if path.is_file())
    audit = {
        "detected_files": len(paths),
        "files_by_extension": dict(sorted(Counter(
            path.suffix.lower() or "<no extension>" for path in paths
        ).items())),
        "supported_files": 0,
        "files_parsed": 0,
        "successfully_extracted_files": 0,
        "successfully_extracted_documents": 0,
        "failed_files": [],
        "skipped_files": [],
        "documents_contributing_candidates": 0,
        "documents_without_process_id": [],
        "documents_without_process_group_id": [],
        "ner_model": getattr(nlp, "meta", {}).get("candidate_extraction_audit", {}),
        "role_anchor_occurrences": {role: 0 for role in ROLE_ANCHORS},
        "role_anchors_with_nearby_per": Counter({role: 0 for role in ROLE_ANCHORS}),
        "max_documents": max_documents,
        "files_deferred_by_limit": [], "documents_deferred_within_parsed_files": 0,
        "document_profiles": [], "phase_timings_seconds": timings,
        "window_cache_size": window_cache_size,
        "document_provenance": [],
    }
    jobs = []
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
        if max_documents is not None and len(jobs) >= max_documents:
            audit["files_deferred_by_limit"].append(source_file)
            continue
        started = time.perf_counter()
        audit["files_parsed"] += 1
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
        finally:
            timings["file_parsing_seconds"] += time.perf_counter() - started
            if progress:
                progress(stage="file_parsing", files=audit["files_parsed"])
        documents = [document for document in documents if document[1].strip()]
        if not documents:
            audit["failed_files"].append({
                "source_file": source_file, "reason": "no extractable document text"
            })
            continue
        audit["successfully_extracted_files"] += 1
        remaining = len(documents) if max_documents is None else max_documents - len(jobs)
        audit["documents_deferred_within_parsed_files"] += max(0, len(documents) - remaining)
        documents = documents[:remaining]
        audit["successfully_extracted_documents"] += len(documents)
        for document_key, text, process_number in documents:
            process_number = process_number or process_number_from_filename(path)
            started = time.perf_counter()
            provenance = extract_process_provenance(text, source_file, process_number)
            timings["provenance_extraction_seconds"] += time.perf_counter() - started
            audit["document_provenance"].append({
                "source_file": source_file, "source_document_id": document_key, **provenance,
            })
            if not process_number:
                audit["documents_without_process_id"].append({
                    "source_file": source_file, "document_key": document_key
                })
            if not provenance["process_group_id"]:
                audit["documents_without_process_group_id"].append({
                    "source_file": source_file, "source_document_id": document_key,
                })
            jobs.append((source_file, document_key, text, process_number, provenance))
    candidates = []
    prediction_cache = WindowPredictionCache(window_cache_size)
    if progress:
        progress(stage="documents_planned", total=len(jobs), files=audit["files_parsed"])
    for job_index in range(len(jobs)):
        source_file, document_key, text, process_number, provenance = jobs[job_index]
        started_document = time.perf_counter()
        previous_stats = ner_stats.copy()
        previous_timings = timings.copy()
        if progress:
            progress(stage="anchor_discovery", documents=job_index)
        started = time.perf_counter()
        anchors = find_role_anchors(text)
        windows = ner_windows(text, context_chars, anchors=anchors)
        timings["anchor_discovery_seconds"] += time.perf_counter() - started
        for role, spans in anchors.items():
            audit["role_anchor_occurrences"][role] += len(spans)
        if progress:
            progress(stage="NER_inference", document_characters=len(text), planned_windows=len(windows))
        try:
            person_spans = detect_person_spans(
                text, nlp, context_chars, batch_size, ner_stats,
                anchors=anchors, prediction_cache=prediction_cache,
                progress=progress, timings=timings, windows=windows,
            )
        except (ValueError, RuntimeError) as exc:
            raise ValueError(
                f"Pretrained NER failed for {source_file}. Check model compatibility "
                "and try --ner-batch-size 1; no regex fallback is used."
            ) from exc
        if progress:
            progress(stage="candidate_selection")
        started = time.perf_counter()
        found = discover_candidates(
            text, source_file, process_number, context_chars, document_key,
            person_spans=person_spans, anchors=anchors, provenance=provenance,
            role_link_counts=audit["role_anchors_with_nearby_per"],
        )
        timings["candidate_selection_seconds"] += time.perf_counter() - started
        audit["documents_contributing_candidates"] += bool(found)
        candidates.extend(found)
        audit["document_profiles"].append({
            "source_file": source_file, "source_document_id": document_key,
            "process_number": process_number, "characters": len(text),
            "decision_id": provenance["decision_id"],
            "process_group_id": provenance["process_group_id"],
            "process_provenance_status": provenance["process_provenance"]["status"],
            "anchor_occurrences": sum(map(len, anchors.values())),
            "ner_window_ranges": windows,
            "NER_windows_processed": ner_stats["ner_windows_processed"] - previous_stats["ner_windows_processed"],
            "cache_hits": ner_stats["ner_window_cache_hits"] - previous_stats["ner_window_cache_hits"],
            "candidates": len(found),
            "elapsed_seconds": time.perf_counter() - started_document,
            "phase_timings_seconds": {key: timings[key] - previous_timings[key] for key in timings},
        })
        jobs[job_index] = None  # Release each source text once processed.
        if progress:
            progress(stage="document_complete", documents=job_index + 1, candidates=len(candidates))
    audit["failed_count"] = len(audit["failed_files"])
    audit["skipped_count"] = len(audit["skipped_files"])
    audit["processed_documents"] = len(jobs)
    audit["max_document_characters"] = max(
        (profile["characters"] for profile in audit["document_profiles"]), default=0
    )
    for key in ("accepted_per_spans", "dropped_false_entities", "merged_spans", "non_per_predictions", "ner_windows"):
        ner_stats.setdefault(key, 0)
    audit["ner_span_counts"] = dict(sorted(ner_stats.items()))
    audit["discovered_candidates_by_role"] = {
        role: sum(item["suggested_label"] == role for item in candidates)
        for role in ROLE_ANCHORS
    }
    audit["distinct_process_numbers_discovered"] = sorted({
        item["process_group_id"] for item in candidates if item.get("process_group_id")
    })
    audit["provenance_status_counts"] = dict(Counter(
        item["process_provenance"]["status"] for item in audit["document_provenance"]
    ))
    audit["documents_with_provenance_discrepancies"] = sum(
        item["process_provenance"]["status"] == "conflict" for item in audit["document_provenance"]
    )
    audit["role_anchors_without_nearby_per"] = {
        role: audit["role_anchor_occurrences"][role] - audit["role_anchors_with_nearby_per"][role]
        for role in ROLE_ANCHORS
    }
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
    print(f"Documents with missing legacy process_number: {len(audit['documents_without_process_id'])}")
    print(f"Documents with unresolved process group IDs: {len(audit['documents_without_process_group_id'])}")
    print(f"Distinct discovered process IDs: {len(audit['distinct_process_numbers_discovered'])}")
    print("Pretrained NER span/window counts (automatic filters, not human judgments):")
    for key, count in audit["ner_span_counts"].items():
        print(f"  {key}: {count}")
    for warning in audit["ner_model"].get("compatibility_warnings", []):
        print(f"NER compatibility warning: {warning}")
    print("Coverage by suggested role (anchors / anchors with PER / discovered / selected):")
    for role in ROLE_ANCHORS:
        print(f"  {role}: {audit['role_anchor_occurrences'][role]} / "
              f"{audit['role_anchors_with_nearby_per'][role]} / "
              f"{audit['discovered_candidates_by_role'][role]} / "
              f"{audit['selected_candidates_by_role'][role]}")
    print("UNKNOWN: no automatic candidates are generated.")
    print(f"Distinct selected process IDs: {len(audit['distinct_process_numbers_selected'])}")
    print(f"Selected candidates with missing process IDs: {audit['selected_missing_process_ids']}")
    print(f"Selected hard-context heuristic count: {audit['selected_hard_contexts']}")
    print(f"Process provenance status: {audit['provenance_status_counts']}")
    print(f"Documents with conflicting identity evidence: {audit['documents_with_provenance_discrepancies']}")
    print(f"Documents deferred by limit (within parsed files): {audit['documents_deferred_within_parsed_files']}")
    print(f"Files deferred by document limit: {len(audit['files_deferred_by_limit'])}")
    print(f"Largest processed document: {audit['max_document_characters']} characters")
    print("Approximate phase timings (seconds):")
    for phase, seconds in audit["phase_timings_seconds"].items():
        print(f"  {phase}: {seconds:.3f}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract non-gold legal-role candidates from STJ judgments."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-per-role", type=int, default=100)
    parser.add_argument("--context-chars", type=int, default=240)
    parser.add_argument("--ner-model", type=Path, default=DEFAULT_NER_MODEL, help="Local pretrained spaCy pipeline with an enabled PER recognizer")
    parser.add_argument("--ner-batch-size", type=int, default=4, help="NER windows per nlp.pipe batch (default: 4; one worker)")
    parser.add_argument("--max-documents", type=int, help="Process only the first N readable documents in sorted source order")
    parser.add_argument("--progress-seconds", type=float, default=10, help="Heartbeat interval, including during a long NER batch (default: 10)")
    parser.add_argument("--window-cache-size", type=int, default=128, help="In-memory exact NER-window cache entries; 0 disables reuse")
    parser.add_argument("--cpu-threads", type=int, default=4, help="PyTorch CPU threads (default: 4; 0 retains the environment default)")
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
    if args.ner_batch_size < 1:
        parser.error("--ner-batch-size must be at least 1")
    if args.max_documents is not None and args.max_documents < 1:
        parser.error("--max-documents must be at least 1")
    if args.progress_seconds <= 0:
        parser.error("--progress-seconds must be positive")
    if args.window_cache_size < 0 or args.cpu_threads < 0:
        parser.error("--window-cache-size and --cpu-threads must be non-negative")
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

    run_started = time.perf_counter()
    try:
        with ProgressReporter(args.progress_seconds) as progress:
            progress(stage="model_loading")
            started = time.perf_counter()
            nlp = load_person_ner(args.ner_model, cpu_threads=args.cpu_threads)
            model_loading_seconds = time.perf_counter() - started
            all_candidates, audit = audit_corpus(
                args.input_dir, args.context_chars, nlp=nlp, batch_size=args.ner_batch_size,
                max_documents=args.max_documents, progress=progress,
                window_cache_size=args.window_cache_size,
            )
            progress(stage="candidate_deduplication_and_sampling")
            started = time.perf_counter()
            unique_candidates = deduplicate_candidates(all_candidates)
            sampled_candidates = deterministic_sample(
                unique_candidates, args.max_per_role, hard_share=args.hard_share,
                max_per_process_role=args.max_per_process_role,
            )
            audit["phase_timings_seconds"]["candidate_selection_seconds"] += time.perf_counter() - started
            audit["phase_timings_seconds"]["model_loading_seconds"] = model_loading_seconds
            audit["phase_timings_seconds"]["total_elapsed_seconds"] = time.perf_counter() - run_started
            progress(stage="complete", candidates=len(sampled_candidates))
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"NER extraction stopped: {exc}\n")

    audit.update({
        "seed": SEED, "hard_share_target": args.hard_share,
        "max_per_role": args.max_per_role, "context_chars": args.context_chars,
        "max_per_process_role": args.max_per_process_role,
        "ner_batch_size": args.ner_batch_size,
        "candidates_before_deduplication": len(all_candidates),
        "candidates_after_deduplication": len(unique_candidates),
        "selected_candidates": len(sampled_candidates),
        "selected_candidates_by_role": {
            role: sum(item["suggested_label"] == role for item in sampled_candidates)
            for role in ROLE_ANCHORS
        },
        "distinct_process_numbers_selected": sorted({
            item["process_group_id"] for item in sampled_candidates if item.get("process_group_id")
        }),
        "selected_missing_process_ids": sum(not item["process_number"] for item in sampled_candidates),
        "selected_unresolved_process_group_ids": sum(not item.get("process_group_id") for item in sampled_candidates),
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
