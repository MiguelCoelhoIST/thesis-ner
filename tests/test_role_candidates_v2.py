import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src.data import extract_role_candidates_v2 as extractor

from src.data.extract_role_candidates_v2 import (
    DocumentReadError,
    audit_corpus,
    deterministic_sample,
    deduplicate_candidates,
    discover_candidates,
    is_hard_context,
    read_documents,
    require_extracted_candidates,
    stable_process_id,
)
from src.data.map_role_taxonomy import load_taxonomy
from src.evaluation.validate_role_candidates_v2 import (
    validate_candidate_file,
    validate_candidate_record,
)


class RoleCandidateExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fine_labels, _ = load_taxonomy()

    def test_lexical_candidate_discovery(self):
        text = "O arguido AA respondeu. A testemunha BB foi ouvida."
        candidates = discover_candidates(text, context_chars=40)
        pairs = {
            (candidate["suggested_label"], candidate["entity"])
            for candidate in candidates
        }
        self.assertIn(("ARGUIDO", "AA"), pairs)
        self.assertIn(("TESTEMUNHA", "BB"), pairs)

    def test_anonymized_placeholders_and_offsets(self):
        text = "A autora AA apresentou prova contra o réu BB."
        candidates = discover_candidates(text, context_chars=30)
        entities = {candidate["entity"] for candidate in candidates}
        self.assertTrue({"AA", "BB"}.issubset(entities))
        for candidate in candidates:
            start = candidate["entity_start"]
            end = candidate["entity_end"]
            self.assertEqual(candidate["text"][start:end], candidate["entity"])

    def test_deduplication(self):
        text = "O arguido AA respondeu."
        candidate = discover_candidates(text)[0]
        duplicate = dict(candidate)
        duplicate["id"] = "duplicate-id"
        duplicate["text"] = "  " + duplicate["text"] + "  "
        self.assertEqual(
            len(deduplicate_candidates([candidate, duplicate])), 1
        )

    def test_validator_detects_duplicate_ids(self):
        candidate = discover_candidates("O requerido AA respondeu.")
        self.assertEqual(candidate, [])

        valid = discover_candidates("O requerente AA respondeu.")[0]
        self.assertEqual(
            validate_candidate_record(valid, self.fine_labels), []
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "candidates.jsonl"
            path.write_text(
                json.dumps(valid, ensure_ascii=False)
                + "\n"
                + json.dumps(valid, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            count, _, errors = validate_candidate_file(
                path, self.fine_labels
            )
        self.assertEqual(count, 2)
        self.assertTrue(any("duplicate id" in error for error in errors))

    def test_candidates_are_never_automatically_validated(self):
        candidates = discover_candidates(
            "A recorrente AA respondeu ao recorrido BB."
        )
        self.assertTrue(candidates)
        self.assertTrue(
            all(candidate["human_validated"] is False for candidate in candidates)
        )
        self.assertTrue(all(candidate["label"] is None for candidate in candidates))

    def test_docx_body_runs_tables_and_offsets(self):
        xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>O argu</w:t></w:r>'
            '<w:r><w:t>ido AA respondeu.</w:t></w:r></w:p>'
            '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>A testemunha BB.</w:t>'
            '</w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)
            _, text, _ = read_documents(path)[0]
        self.assertEqual(text, "O arguido AA respondeu.\nA testemunha BB.")
        for candidate in discover_candidates(text):
            self.assertEqual(validate_candidate_record(candidate, self.fine_labels), [])

    def test_rtf_codepage_unicode_and_offsets(self):
        try:
            import striprtf.striprtf  # noqa: F401
        except ImportError:
            self.skipTest("Install requirements.txt for RTF extraction tests")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.rtf"
            path.write_bytes(
                br"{\rtf1\ansi\ansicpg1252 O r\'e9u AA.\par A testemunha BB.}"
            )
            _, text, _ = read_documents(path)[0]
        self.assertIn("r\u00e9u AA", text)
        candidates = discover_candidates(text)
        self.assertTrue(any(row["suggested_label"] == "REU" for row in candidates))
        for candidate in candidates:
            self.assertEqual(validate_candidate_record(candidate, self.fine_labels), [])

    def test_audit_accounts_for_skipped_failed_and_missing_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "synthetic.txt").write_text("O arguido AA respondeu.", encoding="utf-8")
            (root / "legacy.doc").write_bytes(b"synthetic legacy file")
            (root / "image.pdf").write_bytes(b"synthetic unsupported file")
            (root / "broken.docx").write_bytes(b"invalid zip")
            candidates, audit = audit_corpus(root)
        self.assertTrue(candidates)
        self.assertEqual(audit["detected_files"], 4)
        self.assertEqual(audit["successfully_extracted_files"], 1)
        self.assertEqual(audit["failed_count"], 1)
        self.assertEqual(audit["skipped_count"], 2)
        self.assertEqual(audit["documents_contributing_candidates"], 1)
        self.assertEqual(len(audit["documents_without_process_id"]), 1)
        self.assertTrue(any("pre-conversion" in row["reason"] for row in audit["skipped_files"]))

    def test_no_candidates_and_no_supported_documents_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "synthetic.txt").write_text("Texto de teste sem candidatos.", encoding="utf-8")
            candidates, audit = audit_corpus(root)
            with self.assertRaisesRegex(ValueError, "No role candidates"):
                require_extracted_candidates(audit, candidates)
            output = root / "pool.jsonl"
            result = subprocess.run(
                [sys.executable, "src/data/extract_role_candidates_v2.py",
                 "--input-dir", str(root), "--output", str(output)],
                capture_output=True, text=True,
                cwd=Path(__file__).resolve().parents[1],
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
        with tempfile.TemporaryDirectory() as directory:
            candidates, audit = audit_corpus(Path(directory))
            with self.assertRaisesRegex(ValueError, "No supported documents"):
                require_extracted_candidates(audit, candidates)

    def test_process_sampling_prioritizes_diversity_and_caps_versions(self):
        candidates = []
        for number, versions in ((123, 8), (456, 1), (789, 1)):
            for version in range(versions):
                rows = discover_candidates(
                    "O arguido AA respondeu.",
                    source_file=f"version-{number}-{version}.txt",
                    process_number=f"{number}/22.1T8ABC.P1.S1",
                )
                candidates.extend(rows)
        sampled = deterministic_sample(candidates, 3)
        self.assertEqual(len({stable_process_id(row["process_number"]) for row in sampled}), 3)
        self.assertEqual(sampled, deterministic_sample(list(reversed(candidates)), 3))
        larger = deterministic_sample(candidates, 20)
        self.assertEqual(sum(row["process_number"].startswith("123/") for row in larger), 2)
        self.assertEqual(stable_process_id("123/22.1T8ABC-A.P1.S1"), "123/22.1T8ABC")

    def test_hard_share_and_direct_evidence(self):
        candidates = []
        for index in range(4):
            text = "O arguido AA respondeu."
            if index == 0:
                text += " BB estava presente."
            candidates.extend(discover_candidates(text, process_number=f"{index + 1}/22.1T8ABC"))
        sampled = deterministic_sample(candidates, 4, hard_share=0.25)
        self.assertEqual(sum(is_hard_context(row) for row in sampled), 1)
        rows = discover_candidates("O arguido AA respondeu. " + "A testemunha BB foi ouvida. " * 4)
        self.assertTrue(any(row["entity"] == "AA" for row in rows))

    def test_legacy_doc_is_explicitly_rejected(self):
        with self.assertRaisesRegex(DocumentReadError, "pre-conversion"):
            read_documents(Path("synthetic.doc"))

    def test_duplicate_process_versions_are_deduplicated(self):
        candidates = []
        for filename, process in (
            ("first.txt", "123/22.1T8ABC"),
            ("appeal.docx", "123/22.1T8ABC.P1.S1"),
        ):
            candidates.extend(discover_candidates(
                "O arguido AA respondeu.", filename, process
            ))
        self.assertEqual(len(deduplicate_candidates(candidates)), 1)

    def test_audit_only_writes_metadata_and_failure_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "corpus"
            source.mkdir()
            document = source / "123_22_1T8ABC.txt"
            document.write_text("O arguido AA respondeu.", encoding="utf-8")
            audit_path = root / "raw" / "audit.json"
            command = [
                "extractor", "--input-dir", str(source), "--audit-only",
                "--audit-json", str(audit_path),
            ]
            with (
                patch.object(extractor, "RAW_DATA_DIR", root / "raw"),
                patch.object(sys, "argv", command),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(extractor.main(), 0)
            summary_text = audit_path.read_text(encoding="utf-8")
            summary = json.loads(summary_text)
            self.assertEqual(summary["distinct_process_numbers_selected"], ["123/22.1T8ABC"])
            self.assertNotIn("O arguido AA respondeu.", summary_text)
            document.write_text("Texto sem candidatos.", encoding="utf-8")
            failed_path = root / "raw" / "failure.json"
            command[-1] = str(failed_path)
            with (
                patch.object(extractor, "RAW_DATA_DIR", root / "raw"),
                patch.object(sys, "argv", command),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(extractor.main(), 1)
            self.assertIn("No role candidates", json.loads(failed_path.read_text())["error"])


if __name__ == "__main__":
    unittest.main()
