import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
import threading
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.data import extract_role_candidates_v2 as extractor
from src.evaluation.validate_role_candidates_v2 import validate_candidate_record


class CountingNER:
    meta = {}

    def __init__(self):
        self.inputs = []

    def pipe(self, texts, **kwargs):
        for text in texts:
            self.inputs.append(text)
            yield SimpleNamespace(ents=[
                SimpleNamespace(start_char=match.start(), end_char=match.end(),
                                text=match.group(), label_="PER")
                for match in re.finditer(r"\bAA\b", text)
            ])


class CandidatePerformanceTests(unittest.TestCase):
    def test_document_limit_is_deterministic_and_does_not_parse_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in reversed(range(12)):
                (root / f"{index:02d}.txt").write_text("O arguido AA respondeu.", encoding="utf-8")
            with patch.object(extractor, "read_documents", wraps=extractor.read_documents) as reader:
                _, audit = extractor.audit_corpus(root, nlp=CountingNER(), max_documents=5)
            self.assertEqual(reader.call_count, 5)
            self.assertEqual(audit["processed_documents"], 5)
            self.assertEqual(len(audit["files_deferred_by_limit"]), 7)
            self.assertEqual([row["source_file"] for row in audit["document_profiles"]],
                             [f"{index:02d}.txt" for index in range(5)])

    def test_json_container_limit_counts_documents_rather_than_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "synthetic.json").write_text(json.dumps([
                {"text": "O arguido AA respondeu."} for _ in range(8)
            ]), encoding="utf-8")
            _, audit = extractor.audit_corpus(root, nlp=CountingNER(), max_documents=3)
            self.assertEqual(audit["processed_documents"], 3)
            self.assertEqual(audit["successfully_extracted_files"], 1)
            self.assertEqual(audit["documents_deferred_within_parsed_files"], 5)

    def test_identical_windows_are_inferred_once_with_original_offsets(self):
        unit = "O arguido AA respondeu. "
        text = unit * 2
        windows = [(0, len(unit)), (len(unit), len(text))]
        nlp = CountingNER()
        stats = Counter()
        spans = extractor.detect_person_spans(text, nlp, windows=windows, stats=stats)
        self.assertEqual(len(nlp.inputs), 1)
        self.assertEqual(stats["ner_windows_processed"], 1)
        self.assertEqual(stats["ner_window_cache_hits"], 1)
        self.assertEqual(spans, [(10, 12, "AA"), (len(unit) + 10, len(unit) + 12, "AA")])
        uncached = extractor.detect_person_spans(
            text, CountingNER(), windows=windows, batch_size=1,
            prediction_cache=extractor.WindowPredictionCache(0),
        )
        self.assertEqual(spans, uncached)

    def test_cross_document_cache_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ("first.txt", "second.txt"):
                (root / filename).write_text("O arguido AA respondeu.", encoding="utf-8")
            nlp = CountingNER()
            rows, audit = extractor.audit_corpus(root, nlp=nlp)
        self.assertEqual(len(nlp.inputs), 1)
        self.assertEqual({row["source_file"] for row in rows}, {"first.txt", "second.txt"})
        self.assertEqual(len({row["id"] for row in rows}), 2)
        for row in rows:
            self.assertEqual(row["text"][row["entity_start"]:row["entity_end"]], "AA")
            self.assertEqual((row["entity_document_start"], row["entity_document_end"]), (10, 12))
        self.assertEqual(audit["ner_span_counts"]["ner_window_cache_hits"], 1)

    def test_anchor_scan_is_reused_and_phase_timings_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "synthetic.txt").write_text("O arguido AA respondeu.", encoding="utf-8")
            with patch.object(extractor, "find_role_anchors", wraps=extractor.find_role_anchors) as finder:
                _, audit = extractor.audit_corpus(root, nlp=CountingNER())
            self.assertEqual(finder.call_count, 1)
        for phase in ("file_parsing_seconds", "anchor_discovery_seconds", "ner_inference_seconds", "candidate_selection_seconds"):
            self.assertGreaterEqual(audit["phase_timings_seconds"][phase], 0)
        self.assertEqual(audit["max_document_characters"], len("O arguido AA respondeu."))
        self.assertTrue(audit["document_profiles"][0]["ner_window_ranges"])

    def test_heartbeat_remains_visible_without_document_completion(self):
        seen = threading.Event()

        class HeartbeatStream(io.StringIO):
            count = 0

            def write(self, text):
                if "stage=NER_inference" in text:
                    self.count += 1
                    if self.count >= 2:
                        seen.set()
                return super().write(text)

        stream = HeartbeatStream()
        with contextlib.redirect_stdout(stream):
            with extractor.ProgressReporter(0.01) as progress:
                progress(stage="NER_inference", total=10)
                self.assertTrue(seen.wait(1))
        self.assertIn("documents=0/10", stream.getvalue())
        self.assertIn("NER_windows_processed=0", stream.getvalue())

    def test_one_cli_run_saves_pool_and_audit_with_one_ner_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input"
            source.mkdir()
            input_path = source / "synthetic.txt"
            input_path.write_text("O arguido AA respondeu.", encoding="utf-8")
            original_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
            output = root / "raw" / "new_v4.jsonl"
            audit_path = root / "raw" / "audit_v4.json"
            argv = ["extractor", "--input-dir", str(source), "--output", str(output),
                    "--audit-json", str(audit_path), "--max-documents", "10"]
            nlp = CountingNER()
            with (
                patch.object(extractor, "load_person_ner", return_value=nlp),
                patch.object(extractor, "RAW_DATA_DIR", root / "raw"),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(extractor.main(), 0)
            self.assertEqual(len(nlp.inputs), 1)
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), audit["selected_candidates"])
            self.assertEqual(audit["max_documents"], 10)
            self.assertIn("total_elapsed_seconds", audit["phase_timings_seconds"])
            for row in rows:
                self.assertEqual(validate_candidate_record(row, list(extractor.ROLE_ANCHORS) + ["UNKNOWN"]), [])
            self.assertEqual(hashlib.sha256(input_path.read_bytes()).hexdigest(), original_hash)

    def test_sampling_computes_evidence_scores_once_per_candidate(self):
        rows = extractor.discover_candidates("O arguido AA respondeu.", nlp=CountingNER())
        with patch.object(extractor, "evidence_rank", wraps=extractor.evidence_rank) as scorer:
            extractor.deterministic_sample(rows, 30)
        self.assertEqual(scorer.call_count, len(rows))

    def test_indexed_nearby_spans_match_exhaustive_reference(self):
        text = "Texto sintético. " * 30
        spans = [(start, start + 2, text[start:start + 2]) for start in range(0, 400, 10)]
        anchor_start, anchor_end = 180, 187
        expected = []
        for start, end, entity in spans:
            if start < anchor_end and end > anchor_start:
                continue
            distance = extractor.distance_to_anchor(start, end, anchor_start, anchor_end)
            if distance <= extractor.ENTITY_SEARCH_CHARS:
                gap = text[end:anchor_start] if end <= anchor_start else text[anchor_end:start]
                boundary = int(bool(re.search(r"[.!?;\n]", gap)))
                expected.append((boundary, distance, start, end, entity))
        expected = [(entity, start, end) for _, _, start, end, entity in sorted(expected)]
        self.assertEqual(extractor.nearby_entities(text, anchor_start, anchor_end, spans), expected)

    def test_overlap_sweep_drops_conflicts_and_keeps_independent_spans(self):
        text = "O arguido Rui Domingues falou com Tiago Ferreira."

        class OverlapNER:
            def pipe(self, texts, **kwargs):
                for value in texts:
                    yield SimpleNamespace(ents=[
                        SimpleNamespace(start_char=value.index(name), end_char=value.index(name) + len(name), text=name, label_="PER")
                        for name in ("Rui Domingues", "Domingues", "Tiago Ferreira")
                    ])

        stats = Counter()
        spans = extractor.detect_person_spans(text, OverlapNER(), stats=stats)
        self.assertEqual([entity for _, _, entity in spans], ["Tiago Ferreira"])
        self.assertEqual(stats["dropped_conflicting_spans"], 2)


if __name__ == "__main__":
    unittest.main()
