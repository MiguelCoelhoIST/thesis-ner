"""Select existing candidates locally; never infer entities or annotate labels.

Private outputs must be new files under ignored data/raw/. The manifest records
all decisions; stdout contains aggregates only. No spaCy model is loaded.
"""

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.annotation.review_role_candidates import load_candidates
from src.data.extract_role_candidates_v2 import ANCHOR_PATTERNS
from src.data.map_role_taxonomy import load_jsonl, load_taxonomy
from src.data.role_provenance import ID_RE, normalize_process_group_id
from src.evaluation.validate_role_candidates_v2 import validate_candidate_file

ROLES = [role for role in load_taxonomy()[0] if role != "UNKNOWN"]
RAW = ROOT / "data/raw"
VERSION = "19a-batch-v1"


def normalized(value):
    return " ".join(value.casefold().split())


def document_key(row):
    source = row.get("source_file") or row.get("source_url")
    if source is None:
        return ("record_without_document", row["id"])
    return (source, row.get("source_document_id") or source)


def identity_roots(row):
    """Potential identity edges, not adjudicated identities. Excludes citations."""
    values = [row.get("process_group_id"), row.get("decision_id")]
    values += row.get("process_group_id_candidates", [])
    values += row.get("decision_id_candidates", [])
    provenance = row.get("process_provenance", {})
    for field in ("header_evidence", "filename_evidence"):
        values += [item.get("decision_id") for item in provenance.get(field, [])]
    # Legacy IDs are unverified: only conservative blocking edges, not truth.
    values.append(row.get("process_number"))
    return {group for value in values if (group := normalize_process_group_id(value))}


def marked(row, mask=False):
    start, end = row["entity_start"], row["entity_end"]
    return normalized(row["text"][:start] + " <target> " +
                      ("person" if mask else row["entity"]) +
                      " </target> " + row["text"][end:])


def shingles(row):
    words = re.findall(r"\w+", marked(row, mask=True))
    return {tuple(words[i:i + 5]) for i in range(len(words) - 4)}


def content_related(left, right):
    """Conservative overlap guard, not a claim of person/case identity."""
    a, b = normalized(left["text"]), normalized(right["text"])
    if min(len(a.split()), len(b.split())) >= 5 and (a in b or b in a):
        return True
    a, b = marked(left), marked(right)
    if normalized(left["entity"]) == normalized(right["entity"]):
        matcher = SequenceMatcher(None, a, b)
        if (matcher.real_quick_ratio() >= .92 and matcher.quick_ratio() >= .92
                and matcher.ratio() >= .92):
            return True
    a, b = shingles(left), shingles(right)
    if a and b and min(len(a), len(b)) / max(len(a), len(b)) >= .80:
        intersection = len(a & b)
        return intersection / (len(a) + len(b) - intersection) >= .80
    return False


def features(row):
    roles = [role for role, pattern in ANCHOR_PATTERNS.items()
             if pattern.search(row["text"])]
    other = {normalize_process_group_id(match.group()) for match in ID_RE.finditer(row["text"])}
    other.discard(None)
    other -= identity_roots(row)
    multiple = row.get("context_per_count", 1) > 1
    # This is a sentence proxy, not re-detection of PER or a human assertion.
    sentences = [s for s in re.split(r"[.!?](?:\s+|$)", row["text"]) if s.strip()]
    return {"multi_per_context": multiple, "multi_role_context": len(roles) > 1,
            "other_process_reference": bool(other),
            "multi_per_single_sentence_proxy": multiple and len(sentences) == 1}


class Components:
    def __init__(self):
        self.parent = {}

    def find(self, key):
        self.parent.setdefault(key, key)
        if self.parent[key] != key:
            self.parent[key] = self.find(self.parent[key])
        return self.parent[key]

    def join(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.parent[b] = a


def prepare(records, documents, protected, per_role=5, seed=42):
    """Pure selection: returns original records and a private decision manifest."""
    graph = Components()
    evidence_edges = Counter()
    for row in documents + records + protected:
        node = ("document", *document_key(row))
        graph.find(node)
        digest = row.get("source_text_sha256")
        if digest:
            graph.join(node, ("hash", digest))
        for group in sorted(identity_roots(row)):
            graph.join(node, ("group", group))
    # Compare all pool records, including those that will fail the quality gate.
    # This propagates overlaps instead of allowing an unsafe alias to disappear.
    for index, row in enumerate(records):
        for peer in records[:index]:
            if content_related(row, peer):
                graph.join(("document", *document_key(row)), ("document", *document_key(peer)))
                evidence_edges["pool_content_pairs"] += 1
        for peer in protected:
            if content_related(row, peer):
                graph.join(("document", *document_key(row)), ("document", *document_key(peer)))
                evidence_edges["protected_content_pairs"] += 1

    protected_components = {graph.find(("document", *document_key(row))) for row in protected}
    protected_ids = {row["id"] for row in protected}
    roots = defaultdict(set)
    statuses = defaultdict(set)
    for row in documents + records + protected:
        component = graph.find(("document", *document_key(row)))
        roots[component].update(identity_roots(row))
        statuses[component].add(row.get("process_provenance", {}).get("status"))

    decisions = {}
    eligible = []
    for row in records:
        component = graph.find(("document", *document_key(row)))
        reasons = []
        status = row.get("process_provenance", {}).get("status")
        if component in protected_components or row["id"] in protected_ids:
            reasons.append("protected_document_group_or_content")
        if len(roots[component]) != 1:
            reasons.append("missing_or_multiple_component_identity_roots")
        if not row.get("decision_id") or not row.get("process_group_id"):
            reasons.append("missing_resolved_identity")
        if status != "header_filename_agree" and not (
                row["suggested_label"] == "REU" and status == "header_only"):
            reasons.append("insufficient_own_provenance")
        if row.get("human_validated") is not False or row.get("label") is not None or row.get("labels"):
            reasons.append("already_annotated")
        decisions[row["id"]] = {"excluded_reasons": reasons,
                                 "component_roots": sorted(roots[component]),
                                 "alias_statuses": sorted(s for s in statuses[component] if s),
                                 "features": features(row)}
        if not reasons:
            eligible.append(row)

    # Maximum bipartite matching: quota slots -> conservative components.
    # One component per batch, even when differently named groups are linked.
    available = defaultdict(lambda: defaultdict(list))
    for row in eligible:
        component = graph.find(("document", *document_key(row)))
        available[row["suggested_label"]][component].append(row)
    role_order = sorted(ROLES, key=lambda role: (len(available[role]), ROLES.index(role)))
    preferences = (None, "multi_per_context", "multi_role_context", "other_process_reference",
                   "multi_per_single_sentence_proxy")

    def rank(row, slot):
        flags = decisions[row["id"]]["features"]
        preference = preferences[slot % len(preferences)]
        desired = (not any(flags.values())) if preference is None else flags[preference]
        tie = hashlib.sha256(f"{seed}:{slot}:{row['id']}".encode()).hexdigest()
        return (not desired, row["process_provenance"]["status"] != "header_filename_agree", tie)

    choices = {}
    for slot in range(per_role):
        for role in role_order:
            choices[(role, slot)] = sorted(
                (min(items, key=lambda row: rank(row, slot)) for items in available[role].values()),
                key=lambda row: rank(row, slot))
    matched = {}

    def augment(slot, visited):
        for row in choices[slot]:
            component = graph.find(("document", *document_key(row)))
            if component in visited:
                continue
            visited.add(component)
            if component not in matched or augment(matched[component][0], visited):
                matched[component] = (slot, row)
                return True
        return False

    for slot in range(per_role):
        for role in role_order:
            augment((role, slot), set())
    selected = sorted((row for slot, row in matched.values()), key=lambda row: row["id"])
    random.Random(seed).shuffle(selected)
    ids = {row["id"] for row in selected}
    for row in eligible:
        decisions[row["id"]]["selection"] = "selected" if row["id"] in ids else "quota_or_shared_component"
    manifest = {
        "algorithm": VERSION, "seed": seed, "requested_per_role": per_role,
        "selected_ids_in_file_order": [row["id"] for row in selected],
        "decisions": decisions,
        "summary": {
            "input_records": len(records), "eligible_records": len(eligible),
            "selected_records": len(selected),
            "selected_roles": dict(Counter(row["suggested_label"] for row in selected)),
            "eligible_roles": dict(Counter(row["suggested_label"] for row in eligible)),
            "selected_provenance": dict(Counter(row["process_provenance"]["status"] for row in selected)),
            "selected_feature_counts": {name: sum(features(row)[name] for row in selected)
                                        for name in preferences[1:]},
            "excluded_reasons_nonexclusive": dict(Counter(reason for entry in decisions.values()
                                                          for reason in entry["excluded_reasons"])),
            "content_guard_edges": dict(evidence_edges),
            "selected_distinct_hashes": len({row["source_text_sha256"] for row in selected}),
            "selected_distinct_groups": len({row["process_group_id"] for row in selected}),
            "selected_alias_conflict_warnings": sum("conflict" in decisions[row["id"]]["alias_statuses"]
                                                    for row in selected),
        },
    }
    return selected, manifest


def private_new_output(path):
    path = path.resolve()
    if not path.is_relative_to(RAW.resolve()) or path.exists():
        raise ValueError("Outputs must be NEW files under data/raw/.")
    result = subprocess.run(["git", "check-ignore", "-q", "--", str(path)], cwd=ROOT)
    if result.returncode != 0:
        raise ValueError("Private output is not ignored by Git.")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pool", "audit", "pilot", "reviews", "gold", "output", "manifest"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--per-role", type=int, default=5)
    args = parser.parse_args()
    try:
        if args.per_role < 1:
            raise ValueError("--per-role must be positive")
        output, metadata = private_new_output(args.output), private_new_output(args.manifest)
        if output == metadata:
            raise ValueError("Output and manifest must differ")
        inputs = {key: getattr(args, key) for key in ("pool", "audit", "pilot", "reviews", "gold")}
        before = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in inputs.items()}
        fine, _ = load_taxonomy()
        count, _, errors = validate_candidate_file(args.pool, fine)
        if errors:
            raise ValueError(f"Input validation failed ({len(errors)} errors); no outputs written")
        records = load_candidates(args.pool)
        audit = json.loads(args.audit.read_text(encoding="utf-8"))
        documents = audit["document_provenance"]
        by_document = {document_key(row): row for row in documents}
        for row in records:
            source = by_document[document_key(row)]
            if any(row[field] != source[field] for field in (
                    "source_text_sha256", "decision_id", "process_group_id", "process_provenance")):
                raise ValueError("Pool/audit provenance mismatch; no outputs written")
        protected = []
        for name in ("pilot", "reviews", "gold"):
            for original in load_jsonl(inputs[name]):
                # Enrich only blocking evidence in memory, never the source records.
                row = {**by_document.get(document_key(original), {}), **original}
                protected.append(row)
        selected, manifest = prepare(records, documents, protected, args.per_role, args.seed)
        if not selected:
            raise ValueError("No safely eligible candidates; no outputs written")
        assert all(before[key] == hashlib.sha256(path.read_bytes()).hexdigest()
                   for key, path in inputs.items())
        manifest.update({"inputs": {key: {"path": str(path), "sha256": before[key]}
                                    for key, path in inputs.items()},
                         "selector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         "gold_unparsed_process_ids": sum(normalize_process_group_id(row.get("process_number")) is None
                                                          for row in load_jsonl(args.gold))})
        lines = {json.loads(line)["id"]: line for line in args.pool.read_text(encoding="utf-8").splitlines()}
        payload = "\n".join(lines[row["id"]] for row in selected) + "\n"
        manifest["output_sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        for path in (output, metadata):
            path.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        with metadata.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Batch preparation failed ({type(exc).__name__}); no private details printed.\n")


if __name__ == "__main__":
    main()
