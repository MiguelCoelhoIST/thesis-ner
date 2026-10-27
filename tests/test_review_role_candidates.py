import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.annotation import review_role_candidates as reviewer
from src.data.map_role_taxonomy import map_record, load_taxonomy
from src.evaluation.validate_role_candidates_v2 import validate_candidate_record


def synthetic_candidate(record_id="synthetic-1", role="ARGUIDO", process="123/22.1T8ABC"):
    return {
        "id": record_id, "source_file": "synthetic.txt", "process_number": process,
        "text": "O arguido AA respondeu.", "entity": "AA",
        "entity_start": 10, "entity_end": 12, "suggested_label": role,
        "label": None, "evidence_type": None, "difficulty": None,
        "contains_distractor_role": None, "human_validated": False,
    }


def accepted(candidate, labels=None):
    return reviewer.build_review(
        candidate, "accepted", labels or ["ARGUIDO"], "explicit", "easy",
        False, "Synthetic review.", confirmed=True,
    )


class HumanRoleReviewTests(unittest.TestCase):
    def test_unknown_is_accepted_and_distinct_from_reject(self):
        candidate = synthetic_candidate()
        unknown = accepted(candidate, ["UNKNOWN"])
        rejected = reviewer.build_review(candidate, "rejected", note="Wrong synthetic entity.")
        self.assertEqual(unknown["labels"], ["UNKNOWN"])
        self.assertTrue(unknown["human_validated"])
        self.assertEqual(rejected["labels"], [])
        self.assertFalse(rejected["human_validated"])
        self.assertEqual(rejected["review_status"], "rejected")

    def test_multi_label_output_is_compatible_with_taxonomy_mapping(self):
        candidate = synthetic_candidate()
        row = accepted(candidate, ["ARGUIDO", "RECORRENTE"])
        self.assertNotIn("label", row)
        self.assertEqual(row["labels"], ["ARGUIDO", "RECORRENTE"])
        fine, mapping = load_taxonomy()
        self.assertEqual(map_record(row, "aggregated", fine, mapping)["labels"], ["PASSIVE_PARTY", "APPELLANT"])
        self.assertEqual(validate_candidate_record(row, fine), [])
        for field in reviewer.PRESERVED_FIELDS:
            self.assertEqual(row[field], candidate[field])
        self.assertIsNone(candidate["label"])
        self.assertFalse(candidate["human_validated"])

    def test_uncertain_and_unconfirmed_reviews_are_unvalidated(self):
        for evidence, confirmation in (("uncertain", True), ("implicit", False)):
            row = reviewer.build_review(
                synthetic_candidate(), "uncertain", ["ARGUIDO"], evidence,
                "hard", True, confirmed=confirmation,
            )
            self.assertFalse(row["human_validated"])
            self.assertEqual(validate_candidate_record(row, reviewer.LABELS), [])
        with self.assertRaises(ValueError):
            reviewer.build_review(
                synthetic_candidate(), "accepted", ["ARGUIDO"], "explicit",
                "easy", False, confirmed=False,
            )
        with self.assertRaises(ValueError):
            reviewer.build_review(
                synthetic_candidate(), "accepted", ["ARGUIDO"], "uncertain",
                "easy", False, confirmed=True,
            )

    def test_invalid_offsets_can_be_rejected_but_not_accepted(self):
        candidate = synthetic_candidate()
        candidate["entity_start"] = 0
        row = reviewer.build_review(candidate, "rejected")
        self.assertEqual(row["entity_start"], 0)
        self.assertEqual(validate_candidate_record(row, reviewer.LABELS), [])
        with self.assertRaises(ValueError):
            accepted(candidate)

    def test_annotation_consistency_is_enforced(self):
        for status in ("rejected", "skipped", "uncertain"):
            if status == "uncertain":
                row = reviewer.build_review(
                    synthetic_candidate(), status, ["ARGUIDO"], "uncertain",
                    "medium", False,
                )
            else:
                row = reviewer.build_review(synthetic_candidate(), status)
            row["human_validated"] = True
            self.assertTrue(validate_candidate_record(row, reviewer.LABELS))
        row = accepted(synthetic_candidate())
        row["evidence_type"] = "contextual"
        self.assertTrue(validate_candidate_record(row, reviewer.LABELS))
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            reviewer.parse_labels("9,1")
        self.assertEqual(reviewer.parse_labels("5,1,1"), ["ARGUIDO", "RECORRENTE"])

    def test_save_resume_and_duplicate_protection(self):
        candidates = [synthetic_candidate("one"), synthetic_candidate("two")]
        config = {"pool_sha256": "synthetic", "seed": 42, "pilot_size": 2}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.jsonl"
            with reviewer.ReviewStore(path, candidates, config, ["one", "two"]) as store:
                store.save(accepted(candidates[0]))
                saved = path.read_bytes()
                with self.assertRaisesRegex(ValueError, "Duplicate review ID"):
                    store.save(accepted(candidates[0]))
                self.assertEqual(path.read_bytes(), saved)
            with reviewer.ReviewStore(path, candidates, config, ["one", "two"], resume=True) as store:
                self.assertEqual(store.ids, {"one"})
                store.save(reviewer.build_review(candidates[1], "skipped", note="Review later."))
            rows = reviewer.load_jsonl(path)
            self.assertEqual([row["id"] for row in rows], ["one", "two"])
            self.assertEqual(rows[0]["review_note"], "Synthetic review.")
            self.assertFalse(path.with_name(path.name + ".lock").exists())
            with self.assertRaisesRegex(ValueError, "source pool, seed and pilot size"):
                with reviewer.ReviewStore(path, candidates, {**config, "seed": 7}, ["one", "two"], resume=True):
                    pass

    def test_second_session_and_external_changes_are_blocked(self):
        candidate = synthetic_candidate()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.jsonl"
            with reviewer.ReviewStore(path, [candidate], {}, [candidate["id"]]) as store:
                with self.assertRaisesRegex(ValueError, "session lock"):
                    reviewer.ReviewStore(path, [candidate], {}, [candidate["id"]], resume=True)
                path.write_text("\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "changed externally"):
                    store.save(accepted(candidate))

    def test_pilot_balances_roles_and_distinct_processes_deterministically(self):
        candidates = [
            synthetic_candidate(f"{role}-{index}", role, f"{role}-{index}")
            for role in reviewer.LABELS for index in range(4)
        ]
        pilot = reviewer.select_pilot(candidates, 20)
        self.assertEqual(pilot, reviewer.select_pilot(list(reversed(candidates)), 20))
        self.assertEqual(len({row["process_number"] for row in pilot}), 20)
        counts = [sum(row["suggested_label"] == role for row in pilot) for role in reviewer.LABELS]
        self.assertLessEqual(max(counts) - min(counts), 1)
        shared = [synthetic_candidate(f"v-{index}") for index in range(10)]
        distinct = [synthetic_candidate("other", process="456/22.1T8ABC.P1.S1")]
        first = reviewer.select_pilot(shared + distinct, 2)
        self.assertEqual(len({row["process_number"] for row in first}), 2)

    def test_display_highlights_span_and_hides_suggestion(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            reviewer.display_candidate(synthetic_candidate(), 1, 20)
        text = output.getvalue()
        self.assertIn("<<< TARGET: AA >>>", text)
        self.assertIn("123/22.1T8ABC", text)
        self.assertNotIn("suggested", text.lower())

    def test_summary_counts_only_accepted_labels(self):
        rows = [
            accepted(synthetic_candidate("one"), ["ARGUIDO", "RECORRENTE"]),
            reviewer.build_review(synthetic_candidate("two"), "skipped"),
            reviewer.build_review(synthetic_candidate("three"), "rejected"),
            reviewer.build_review(synthetic_candidate("four"), "uncertain", ["REU"], "uncertain", "hard", True),
        ]
        summary = reviewer.review_summary(rows)
        self.assertEqual(summary["reviewed"], 4)
        self.assertEqual(summary["accepted"], 1)
        self.assertEqual(summary["rejected"], 1)
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(summary["uncertain"], 1)
        self.assertEqual(summary["class_distribution"], {"ARGUIDO": 1, "RECORRENTE": 1})
        self.assertEqual(summary["multi_label_count"], 1)

    def test_terminal_quit_and_resume_preserve_input_and_completed_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "pool.jsonl"
            source.write_text("\n".join(json.dumps(synthetic_candidate(f"c-{index}")) for index in range(3)) + "\n", encoding="utf-8")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            output = root / "raw" / "reviews.jsonl"
            argv = ["reviewer", "--input", str(source), "--output", str(output), "--pilot-size", "3"]
            with (
                patch.object(reviewer, "RAW_DATA_DIR", root / "raw"),
                patch("sys.argv", argv),
                patch("builtins.input", side_effect=["9", "e", "e", "n", "Synthetic note", "yes", "q"]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                reviewer.main()
            saved = reviewer.load_jsonl(output)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["labels"], ["UNKNOWN"])
            with (
                patch.object(reviewer, "RAW_DATA_DIR", root / "raw"),
                patch("sys.argv", argv + ["--resume"]),
                patch("builtins.input", side_effect=["r", "Wrong synthetic entity", "s", "Later"]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                reviewer.main()
            rows = reviewer.load_jsonl(output)
            self.assertEqual(len(rows), 3)
            self.assertEqual(len({row["id"] for row in rows}), 3)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)


if __name__ == "__main__":
    unittest.main()
