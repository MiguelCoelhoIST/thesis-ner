import tempfile
import unittest
from pathlib import Path

from src.data.role_provenance import (
    audit_metadata,
    extract_process_provenance,
    filename_identifier_evidence,
    normalize_decision_id,
    normalize_process_group_id,
)
from src.data.extract_role_candidates_v2 import candidate_process_key


class RoleProvenanceTests(unittest.TestCase):
    def test_exact_decision_suffix_is_preserved_but_groups_match(self):
        for value in ("00042/24.0T8ABC.S1", "42/24.0T8ABC.S2", "42/24.0T8ABC-A.P1.S1"):
            self.assertEqual(normalize_process_group_id(value), "42/24.0T8ABC")
        self.assertEqual(normalize_decision_id("42/24.0T8abc.S2"), "42/24.0T8ABC.S2")

    def test_filename_hyphens_underscores_and_conversion_suffixes(self):
        for filename in ("Ac 42-24.0T8ABC.S2.docx.txt", "42_24_0T8ABC_S2.txt"):
            evidence = filename_identifier_evidence(filename)
            self.assertEqual([row["decision_id"] for row in evidence], ["42/24.0T8ABC.S2"])

    def test_header_filename_mismatch_is_preserved_and_not_resolved(self):
        # Fabricated identifiers and text, not excerpts from the real source.
        text = "Cabeçalho sintético\nProc. 42/24.0T8ABC.S1\nReferência de teste: 90/20.1T8XYZ.S1."
        result = extract_process_provenance(text, "Ac 42-24.0T8ABC.S2.docx.txt", "42/24.0T8ABC.S1")
        self.assertIsNone(result["decision_id"])
        self.assertEqual(result["decision_id_candidates"], ["42/24.0T8ABC.S1", "42/24.0T8ABC.S2"])
        self.assertEqual(result["process_group_id"], "42/24.0T8ABC")
        evidence = result["process_provenance"]
        self.assertEqual(evidence["status"], "conflict")
        self.assertTrue(evidence["requires_review"])
        self.assertEqual(evidence["legacy_process_number"], "42/24.0T8ABC.S1")
        for reference in evidence["detected_references"]:
            self.assertEqual(text[reference["start"]:reference["end"]], reference["raw"])

    def test_body_reference_does_not_override_source_identity(self):
        text = "Referência fictícia a 90/20.1T8XYZ.S1.\nProc. 42/24.0T8ABC.S2\n"
        result = extract_process_provenance(text, "42-24.0T8ABC.S2.txt", "90/20.1T8XYZ.S1")
        self.assertEqual(result["decision_id"], "42/24.0T8ABC.S2")
        self.assertEqual(result["process_group_id"], "42/24.0T8ABC")
        self.assertEqual(result["process_provenance"]["status"], "header_filename_agree")
        self.assertFalse(result["process_provenance"]["requires_review"])

    def test_unmarked_reference_alone_is_unresolved(self):
        result = extract_process_provenance("No teste cita-se 90/20.1T8XYZ.S1.", "synthetic.txt", "90/20.1T8XYZ.S1")
        self.assertIsNone(result["decision_id"])
        self.assertIsNone(result["process_group_id"])
        self.assertEqual(result["process_provenance"]["status"], "unresolved")

    def test_conflicting_roots_require_manual_group_adjudication(self):
        result = extract_process_provenance("Proc. 42/24.0T8ABC.S1\n", "90-20.1T8XYZ.S2.txt")
        self.assertIsNone(result["process_group_id"])
        candidate = {"source_file": "synthetic.txt", "process_number": "42/24.0T8ABC.S1", **result}
        self.assertTrue(candidate_process_key(candidate).startswith("unresolved:"))

    def test_truncated_numeric_reference_is_not_a_complete_identifier(self):
        self.assertIsNone(normalize_decision_id("42/24.0"))
        result = extract_process_provenance("Referência truncada: 42/24.0.", "synthetic.txt")
        self.assertEqual(result["process_provenance"]["detected_references"], [])

    def test_metadata_audit_is_local_read_only_and_contains_no_passage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "42-24.0T8ABC.S2.txt"
            text = "Proc. 42/24.0T8ABC.S2\nConteúdo de teste sem pessoas reais."
            path.write_text(text, encoding="utf-8")
            original = path.read_bytes()
            report = audit_metadata(Path(directory))
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(len(report["documents"]), 1)
        self.assertNotIn("text", report["documents"][0])
        self.assertEqual(report["status_counts"], {"header_filename_agree": 1})


if __name__ == "__main__":
    unittest.main()
