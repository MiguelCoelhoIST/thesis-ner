"""Local human review of role candidates; no model inference or API calls.

Restart with the identical arguments and --resume. Saved skips are retained as
review outcomes; they are not automatically presented again. Gold exports must
select only review_status=accepted and human_validated=true.
"""

import argparse
import copy
import hashlib
import json
import os
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.extract_role_candidates_v2 import candidate_process_key
from src.data.map_role_taxonomy import load_jsonl, load_taxonomy
from src.evaluation.validate_role_candidates_v2 import validate_candidate_record


LABELS, _ = load_taxonomy()
RAW_DATA_DIR = PROJECT_ROOT / "data/raw"
SEED = 42
PRESERVED_FIELDS = (
    "id", "source_file", "process_number", "text", "entity",
    "entity_start", "entity_end", "suggested_label",
)


def load_candidates(path):
    records = load_jsonl(path)
    seen = set()
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("Candidate IDs must be non-empty strings")
        if record_id in seen:
            raise ValueError(f"Duplicate candidate ID: {record_id}")
        seen.add(record_id)
        missing = [field for field in PRESERVED_FIELDS if field not in record]
        if missing:
            raise ValueError(f"Candidate {record_id}: missing fields: {', '.join(missing)}")
        if record["suggested_label"] not in LABELS:
            raise ValueError(f"Candidate {record_id}: invalid suggested-label field")
    return records


def select_pilot(records, size=20, seed=SEED):
    """Prioritize distinct root processes, balancing discovery roles on ties."""
    remaining = sorted(records, key=lambda record: record["id"])
    random.Random(seed).shuffle(remaining)
    tie_order = {record["id"]: index for index, record in enumerate(remaining)}
    process_counts = Counter()
    role_counts = Counter()
    selected = []
    while remaining and len(selected) < size:
        chosen = min(remaining, key=lambda record: (
            process_counts[candidate_process_key(record)],
            role_counts[record["suggested_label"]],
            tie_order[record["id"]],
        ))
        selected.append(chosen)
        remaining.remove(chosen)
        process_counts[candidate_process_key(chosen)] += 1
        role_counts[chosen["suggested_label"]] += 1
    return selected


def span_issue(record):
    text, entity = record.get("text"), record.get("entity")
    start, end = record.get("entity_start"), record.get("entity_end")
    if not isinstance(text, str) or not text.strip():
        return "Missing or unusable text."
    if not isinstance(entity, str) or not entity.strip():
        return "Missing or unusable target entity."
    if type(start) is not int or type(end) is not int:
        return "Exact integer entity offsets are missing."
    if not 0 <= start < end <= len(text):
        return "Entity offsets are outside text bounds."
    if text[start:end] != entity:
        return "Entity offsets do not select the specified entity."
    return None


def display_candidate(record, position, total):
    print(f"\n{'=' * 72}\nCandidate {position}/{total} | ID: {record['id']}")
    print(f"Process: {record['process_number'] or '(not available)'}")
    print(f"Target entity: {record['entity']}")
    issue = span_issue(record)
    if issue:
        print(f"REVIEW ISSUE: {issue} Choose REJECT or skip; roles cannot be accepted.")
        print(record["text"] if isinstance(record["text"], str) else "(unusable text)")
    else:
        text, start, end = record["text"], record["entity_start"], record["entity_end"]
        print(text[:start] + "<<< TARGET: " + text[start:end] + " >>>" + text[end:])
    print("\nUNKNOWN = valid person with no supported target role.")
    print("REJECT = wrong entity, invalid span, or irrelevant/unusable example.")
    print(" | ".join(f"{index}={label}" for index, label in enumerate(LABELS, start=1)))
    print("Choose one or more labels (comma separated), r=REJECT, s=skip, q=quit.")


def parse_labels(value):
    chosen = []
    for token in value.replace(",", " ").upper().split():
        if token.isdigit() and 1 <= int(token) <= len(LABELS):
            token = LABELS[int(token) - 1]
        if token not in LABELS:
            raise ValueError("Choose label numbers or names from the displayed list.")
        if token not in chosen:
            chosen.append(token)
    if not chosen:
        raise ValueError("Choose at least one label.")
    if "UNKNOWN" in chosen and len(chosen) > 1:
        raise ValueError("UNKNOWN cannot be combined with a supported target role.")
    return [label for label in LABELS if label in chosen]


def build_review(
    candidate, status, labels=None, evidence=None, difficulty=None,
    distractor=None, note="", confirmed=False,
):
    if status in ("accepted", "uncertain"):
        issue = span_issue(candidate)
        if issue:
            raise ValueError(issue)
    row = copy.deepcopy(candidate)
    row.pop("label", None)
    row.update({
        "labels": list(labels or []),
        "annotation_evidence": evidence,
        "evidence_type": {"explicit": "explicit", "implicit": "contextual"}.get(evidence),
        "difficulty": difficulty,
        "contains_distractor_role": distractor,
        "review_status": status,
        "review_note": note,
        "human_confirmed": confirmed,
        "human_validated": status == "accepted" and confirmed and evidence != "uncertain",
    })
    if status in ("rejected", "skipped"):
        row.update({
            "labels": [], "annotation_evidence": None, "evidence_type": None,
            "difficulty": None, "contains_distractor_role": None,
            "human_confirmed": False, "human_validated": False,
        })
    errors = validate_candidate_record(row, LABELS)
    if errors:
        raise ValueError("Inconsistent review: " + "; ".join(errors))
    return row


class ReviewStore:
    """Atomic, resumable saves, with an exclusive session lock against duplicates."""

    def __init__(self, path, candidates, config, pilot_ids, resume=False):
        self.path = Path(path)
        self.by_id = {row["id"]: row for row in candidates}
        self.config = config
        self.pilot_ids = set(pilot_ids)
        self.rows = []
        self.ids = set()
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and not resume:
            raise ValueError("Output exists. Use --resume with the same input, pilot size and seed.")
        if resume and not self.path.exists():
            raise ValueError("Resume output does not exist.")
        self.lock_fd = None
        try:
            self.lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(self.lock_fd, str(os.getpid()).encode("ascii"))
            if self.path.exists():
                self.rows = load_jsonl(self.path)
                for row in self.rows:
                    self.check_row(row)
                    if row["id"] in self.ids:
                        raise ValueError(f"Duplicate review ID: {row['id']}")
                    self.ids.add(row["id"])
            else:
                with self.path.open("x", encoding="utf-8"):
                    pass
            self.saved_bytes = self.path.read_bytes()
        except FileExistsError as exc:
            self.close()
            raise ValueError(
                "A review session lock exists. Close the other session; after a crash, "
                "verify it stopped before removing the .lock file."
            ) from exc
        except BaseException:
            self.close()
            raise

    def check_row(self, row):
        record_id = row.get("id")
        if record_id not in self.by_id or record_id not in self.pilot_ids:
            raise ValueError("Review ID is not part of this source pool/pilot.")
        if row.get("review_config") != self.config:
            raise ValueError("Resume requires the unchanged source pool, seed and pilot size.")
        for field in PRESERVED_FIELDS:
            if row.get(field) != self.by_id[record_id].get(field):
                raise ValueError(f"Review {record_id}: original field changed: {field}")
        errors = validate_candidate_record(row, LABELS)
        if errors:
            raise ValueError(f"Review {record_id}: " + "; ".join(errors))

    def save(self, row):
        row = copy.deepcopy(row)
        row["review_config"] = dict(self.config)
        self.check_row(row)
        if row["id"] in self.ids:
            raise ValueError(f"Duplicate review ID: {row['id']}")
        if self.path.read_bytes() != self.saved_bytes:
            raise ValueError("Review output changed externally; restart before saving.")
        rows = self.rows + [row]
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=self.path.name + ".", suffix=".tmp", delete=False,
            ) as output:
                temporary_path = Path(output.name)
                for reviewed in rows:
                    output.write(json.dumps(reviewed, ensure_ascii=False) + "\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        self.rows = rows
        self.ids.add(row["id"])
        self.saved_bytes = self.path.read_bytes()

    def close(self):
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None
            self.lock_path.unlink()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def choose(prompt, options):
    while True:
        value = input(prompt).strip().lower()
        if value in options:
            return options[value]
        if value in ("q", "quit"):
            raise EOFError
        print("Choose one of the displayed options, or q to quit.")


def review_candidate(candidate, position, total):
    while True:
        display_candidate(candidate, position, total)
        decision = input("Decision: ").strip()
        if decision.lower() in ("q", "quit"):
            return None
        if decision.lower() in ("r", "reject", "s", "skip"):
            status = "rejected" if decision.lower() in ("r", "reject") else "skipped"
            note = input("Review note (optional): ").strip()
            return build_review(candidate, status, note=note)
        try:
            labels = parse_labels(decision)
        except ValueError as exc:
            print(exc)
            continue
        if span_issue(candidate):
            print("This span requires REJECT or skip; offsets are preserved.")
            continue
        evidence = choose("Evidence: e=explicit, i=implicit, u=uncertain: ", {
            "e": "explicit", "explicit": "explicit",
            "i": "implicit", "implicit": "implicit",
            "u": "uncertain", "uncertain": "uncertain",
        })
        difficulty = choose("Difficulty: e=easy, m=medium, h=hard: ", {
            "e": "easy", "easy": "easy", "m": "medium", "medium": "medium",
            "h": "hard", "hard": "hard",
        })
        distractor = choose("Distracting role mentions: y=yes, n=no: ", {
            "y": True, "yes": True, "n": False, "no": False,
        })
        note = input("Review note (optional): ").strip()
        print(f"\nYour labels: {', '.join(labels)} | evidence={evidence} | "
              f"difficulty={difficulty} | distractors={distractor}")
        print("Uncertain evidence remains unvalidated.")
        confirmation = choose(
            "Type yes to confirm/save; u=save uncertain, e=edit, s=skip, q=quit: ",
            {"yes": "confirm", "u": "uncertain", "e": "edit", "s": "skip"},
        )
        if confirmation == "edit":
            continue
        if confirmation == "skip":
            return build_review(candidate, "skipped", note=note)
        confirmed = confirmation == "confirm"
        status = "accepted" if confirmed and evidence != "uncertain" else "uncertain"
        return build_review(
            candidate, status, labels, evidence, difficulty, distractor, note, confirmed
        )


def review_summary(rows):
    statuses = Counter(row["review_status"] for row in rows)
    accepted = [row for row in rows if row["review_status"] == "accepted"]
    return {
        "reviewed": len(rows),
        "accepted": statuses["accepted"], "rejected": statuses["rejected"],
        "skipped": statuses["skipped"], "uncertain": statuses["uncertain"],
        "class_distribution": dict(Counter(label for row in accepted for label in row["labels"])),
        "multi_label_count": sum(len(row["labels"]) > 1 for row in accepted),
    }


def print_summary(rows):
    summary = review_summary(rows)
    print("\nReview summary (cumulative for this output):")
    for key in ("reviewed", "accepted", "rejected", "skipped", "uncertain"):
        print(f"  {key}: {summary[key]}")
    print("Class distribution (accepted annotations only):")
    for label in LABELS:
        print(f"  {label}: {summary['class_distribution'].get(label, 0)}")
    print(f"Multi-label accepted examples: {summary['multi_label_count']}")
    print("Gold annotations require review_status=accepted and human_validated=true.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Unmodified candidate pool JSONL")
    parser.add_argument("--output", type=Path, required=True, help="New/resumed review JSONL under data/raw/")
    parser.add_argument("--pilot-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error("Input candidate pool does not exist.")
    if args.pilot_size < 1:
        parser.error("--pilot-size must be positive")
    if not args.output.resolve().is_relative_to(RAW_DATA_DIR.resolve()):
        parser.error("--output must be under the ignored data/raw/ directory")
    if args.output.resolve() == args.input.resolve() or (
        args.output.exists() and os.path.samefile(args.input, args.output)
    ):
        parser.error("The source pool and review output must be different files.")

    try:
        source_hash = hashlib.sha256(args.input.read_bytes()).hexdigest()
        candidates = load_candidates(args.input)
        if not candidates:
            raise ValueError("The candidate pool is empty.")
        pilot = select_pilot(candidates, args.pilot_size, args.seed)
        config = {"pool_sha256": source_hash, "seed": args.seed, "pilot_size": args.pilot_size}
        with ReviewStore(args.output, candidates, config, [row["id"] for row in pilot], args.resume) as store:
            print(f"Pilot: {len(pilot)} candidates. Previously saved: {len(store.rows)}.")
            print("Each decision is saved immediately. Use the same arguments plus --resume to continue.")
            try:
                for position, candidate in enumerate(pilot, start=1):
                    if candidate["id"] in store.ids:
                        continue
                    review = review_candidate(candidate, position, len(pilot))
                    if review is None:
                        break
                    store.save(review)
                    print(f"Saved: {review['review_status']}")
            except (EOFError, KeyboardInterrupt):
                print("\nStopping; completed decisions are saved. Current unfinished decision was not saved.")
            finally:
                print_summary(store.rows)
        if hashlib.sha256(args.input.read_bytes()).hexdigest() != source_hash:
            raise ValueError("The source pool changed externally during this review.")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Review stopped: {exc}\n")


if __name__ == "__main__":
    main()
