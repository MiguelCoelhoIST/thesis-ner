"""Invented data only; no model, GPU, corpus or API is required."""

import copy
import hashlib
import random
import unittest

from src.annotation.prepare_role_annotation_batch import ROLES, prepare
from src.annotation.review_role_candidates import select_pilot, span_issue
from src.evaluation.validate_role_candidates_v2 import validate_candidate_record


def candidate(index, role="ARGUIDO", status="header_filename_agree"):
    rng = random.Random(index)
    words = ["".join(rng.choices("abcdefghijklmno", k=12)) for _ in range(20)]
    text = "AA " + " ".join(words) + "."
    group = f"{index}/26.1T8XYZ"
    return {
        "id": f"invented-{index}", "source_file": f"invented-{index}.txt",
        "source_document_id": f"document-{index}", "process_number": group,
        "decision_id": group + ".S1", "decision_id_candidates": [group + ".S1"],
        "process_group_id": group, "process_group_id_candidates": [group],
        "source_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "process_provenance": {"status": status, "requires_review": status != "header_filename_agree"},
        "text": text, "entity": "AA", "entity_start": 0, "entity_end": 2,
        "entity_document_start": 0, "entity_document_end": 2,
        "suggested_label": role, "label": None, "evidence_type": None,
        "difficulty": None, "contains_distractor_role": None,
        "human_validated": False, "context_per_count": 1,
    }


class BatchPreparationTests(unittest.TestCase):
    def test_balanced_deterministic_unchanged_and_reviewable(self):
        rows = [candidate(10 + i, role) for i, role in enumerate(ROLES)]
        original = copy.deepcopy(rows)
        selected, manifest = prepare(rows, rows, [], per_role=1)
        repeated, repeated_manifest = prepare(list(reversed(rows)), rows, [], per_role=1)
        self.assertEqual(len(selected), 8)
        self.assertEqual({r["id"] for r in selected}, {r["id"] for r in repeated})
        self.assertEqual(manifest["selected_ids_in_file_order"], repeated_manifest["selected_ids_in_file_order"])
        self.assertEqual(rows, original)
        self.assertEqual({r["id"] for r in select_pilot(selected, 8, 42)}, {r["id"] for r in selected})
        for row in selected:
            self.assertIsNone(row["label"])
            self.assertFalse(row["human_validated"])
            self.assertIsNone(span_issue(row))
            self.assertEqual(validate_candidate_record(row, ROLES + ["UNKNOWN"]), [])

    def test_cross_root_conflict_alias_excludes_otherwise_safe_record(self):
        safe = candidate(101)
        alias = candidate(102, status="conflict")
        alias["source_text_sha256"] = safe["source_text_sha256"]
        selected, manifest = prepare([safe], [safe, alias], [], per_role=1)
        self.assertEqual(selected, [])
        self.assertIn("missing_or_multiple_component_identity_roots",
                      manifest["decisions"][safe["id"]]["excluded_reasons"])

    def test_protected_hash_and_alias_group_propagate(self):
        safe = candidate(111)
        protected = copy.deepcopy(safe)
        protected.update(id="pilot", source_file="other.txt", source_document_id="pilot-doc")
        selected, manifest = prepare([safe], [safe], [protected], per_role=1)
        self.assertEqual(selected, [])
        self.assertIn("protected_document_group_or_content",
                      manifest["decisions"][safe["id"]]["excluded_reasons"])

    def test_no_forced_quota_and_header_only_exception_is_reu_only(self):
        rows = [candidate(120, "REU", "header_only"), candidate(121, "AUTOR", "header_only")]
        selected, _ = prepare(rows, rows, [], per_role=5)
        self.assertEqual([r["id"] for r in selected], [rows[0]["id"]])

    def test_different_ids_same_context_cannot_enter_twice(self):
        one = candidate(130)
        two = copy.deepcopy(one)
        two.update(id="copy", source_file="copy.txt", source_document_id="copy-doc")
        selected, _ = prepare([one, two], [one, two], [], per_role=5)
        self.assertEqual(len(selected), 1)

    def test_gold_without_metadata_is_excluded_by_context(self):
        row = candidate(140)
        gold = {key: row[key] for key in ("text", "entity", "entity_start", "entity_end")}
        gold["id"] = "gold-synthetic"
        selected, _ = prepare([row], [row], [gold], per_role=1)
        self.assertEqual(selected, [])


if __name__ == "__main__":
    unittest.main()
