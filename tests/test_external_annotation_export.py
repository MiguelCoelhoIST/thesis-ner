"""Synthetic local export tests; no private text or external service."""

import copy
import json
import unittest
from types import SimpleNamespace

from src.annotation.export_external_annotation import export_records, reintegrate_responses, response_schema, select_records, residual_risks


def sample(text="A testemunha AA ouviu o arguido BB e AA.", identity="one"):
    start = text.index("AA")
    row = {"id": identity, "text": text, "entity": "AA", "entity_start": start,
           "entity_end": start + 2, "suggested_label": "REU",
           "source_file": "PRIVATE_SOURCE", "source_text_sha256": identity,
           "process_number": "PRIVATE_PROCESS", "human_validated": False}
    entities = []
    for value in ("AA", "BB"):
        offset = 0
        while (offset := text.find(value, offset)) >= 0:
            entities.append(SimpleNamespace(start_char=offset, end_char=offset+len(value), label_="PER"))
            offset += len(value)
    return row, SimpleNamespace(ents=entities)


class ExternalExportTests(unittest.TestCase):
    def test_full_batch_contains_40_records_and_reintegrates_all_ids(self):
        pairs = [sample(identity=f"invented-{i}") for i in range(40)]
        rows = [r for r, _ in pairs]
        output, mapping, summary = export_records(select_records(rows), [d for _, d in pairs])
        self.assertEqual(len(output), 40)
        self.assertEqual([r["original_id"] for r in mapping["records"]], [r["id"] for r in rows])
        self.assertEqual(summary["offset_checks_passed"], 40)
        self.assertEqual(summary["reversible_text_checks_passed"], 40)
        joined = reintegrate_responses([{"id": r["id"], "labels": []} for r in output], mapping)
        self.assertEqual([r["id"] for r in joined], [r["id"] for r in rows])
        with self.assertRaises(ValueError):
            select_records(rows[:5])

    def test_residual_check_ignores_pseudonyms_but_flags_identifiers(self):
        self.assertEqual(sum(residual_risks({"text": "PESSOA_12 ORGANIZACAO_1"})["direct_identifier_matches"].values()), 0)
        self.assertGreater(residual_risks({"text": "PESSOA_12 user@example.invalid"})["direct_identifier_matches"]["EMAIL"], 0)

    def test_consistent_person_tokens_and_exact_target_offsets(self):
        row, doc = sample()
        saved = copy.deepcopy(row)
        output, mapping, summary = export_records([row], [doc])
        item = output[0]
        self.assertEqual(item["entity"], "PESSOA_1")
        self.assertEqual(item["text"].count("PESSOA_1"), 2)
        self.assertIn("PESSOA_2", item["text"])
        self.assertEqual(item["text"][item["entity_start"]:item["entity_end"]], item["entity"])
        self.assertIn("[ENTITY] PESSOA_1 [/ENTITY]", item["marked_text"])
        self.assertEqual(mapping["records"][0]["original_record"], saved)
        self.assertEqual(row, saved)
        self.assertFalse(summary["anonymization_certified"])

    def test_export_whitelist_excludes_provenance_hints_and_original_ids(self):
        row, doc = sample(identity="PRIVATE_ID")
        output, _, _ = export_records([row], [doc])
        payload = json.dumps(output)
        for forbidden in ("suggested_label", "PRIVATE_ID", "PRIVATE_PROCESS", "PRIVATE_SOURCE"):
            self.assertNotIn(forbidden, payload)

    def test_contacts_ids_and_dates_not_just_people(self):
        text = "A testemunha AA indicou person@example.invalid, +351 912 345 678, 17/26.1T8XYZ.S1 e 2026-01-02."
        row, doc = sample(text)
        output, _, summary = export_records([row], [doc])
        for value in ("person@example.invalid", "912 345 678", "17/26.1T8XYZ.S1", "2026-01-02"):
            self.assertNotIn(value, output[0]["text"])
        self.assertGreater(sum(summary["redactions_by_kind"].values()), 3)

    def test_address_and_unrecognized_capitalized_surface_are_redacted(self):
        row, doc = sample("A testemunha AA reside em Rua Inventada 123; falou com FICTICIO.")
        a = row["text"].index("Rua")
        b = row["text"].index(";")
        doc.ents.append(SimpleNamespace(start_char=a, end_char=b, label_="MOR"))
        output, _, _ = export_records([row], [doc])
        self.assertNotIn("Rua Inventada", output[0]["text"])
        self.assertNotIn("FICTICIO", output[0]["text"])

    def test_same_spelling_in_different_documents_does_not_claim_identity(self):
        a, ad = sample(identity="first")
        b, bd = sample(identity="second")
        output, _, _ = export_records([a, b], [ad, bd])
        self.assertNotEqual(output[0]["entity"], output[1]["entity"])

    def test_ambiguous_target_overlap_fails_closed(self):
        row, doc = sample()
        doc.ents.append(SimpleNamespace(start_char=0, end_char=row["entity_end"], label_="ORG"))
        with self.assertRaises(ValueError):
            export_records([row], [doc])

        row, doc = sample("Sr. AA é relator; Sr. AA respondeu.")
        other = row["text"].index("Sr.", 4)
        doc.ents = [SimpleNamespace(start_char=0, end_char=row["entity_end"], label_="PER"),
                    SimpleNamespace(start_char=other, end_char=other+6, label_="PER")]
        output, _, _ = export_records([row], [doc])
        self.assertEqual(output[0]["text"].count("Sr. PESSOA_1"), 2)

    def test_courtesy_title_only_adjustment_preserves_target_and_evidence(self):
        row, doc = sample("Dr. AA é relator.")
        doc.ents = [SimpleNamespace(start_char=0, end_char=row["entity_end"], label_="PER")]
        output, mapping, summary = export_records([row], [doc])
        self.assertTrue(output[0]["text"].startswith("Dr. PESSOA_1"))
        self.assertEqual(summary["courtesy_title_boundary_adjustments"], 1)
        self.assertEqual(mapping["records"][0]["ner_spans"][0]["start"], 0)
        self.assertEqual(mapping["records"][0]["original_record"]["entity"], "AA")
        row, doc = sample("ZZZ AA é relator.")
        doc.ents = [SimpleNamespace(start_char=0, end_char=row["entity_end"], label_="PER")]
        with self.assertRaises(ValueError):
            export_records([row], [doc])

    def test_statutory_article_retained_and_roundtrip_reintegration(self):
        row, doc = sample("A testemunha AA referiu o artigo 127.")
        output, mapping, summary = export_records([row], [doc])
        self.assertIn("artigo 127", output[0]["text"])
        restored = output[0]["text"]
        for edit in reversed(mapping["records"][0]["edits"]):
            restored = restored[:edit["export_start"]] + edit["original"] + restored[edit["export_end"]:]
        self.assertEqual(restored, row["text"])
        answer = {"id": output[0]["id"], "labels": ["TESTEMUNHA"], "uncertain": False}
        joined = reintegrate_responses([answer], mapping)
        self.assertEqual(joined[0]["id"], row["id"])
        self.assertFalse(joined[0]["human_validated"])
        with self.assertRaises(ValueError):
            reintegrate_responses([answer, answer], mapping)
        with self.assertRaises(ValueError):
            reintegrate_responses([{**answer, "id": "NOT_KNOWN"}], mapping)

    def test_schema_includes_requested_fields_and_reference(self):
        schema = response_schema()
        self.assertTrue({"labels", "evidence", "scope", "uncertain"}.issubset(schema["required"]))
        self.assertIn("REFERENCE", schema["properties"]["labels"]["items"]["enum"])


if __name__ == "__main__":
    unittest.main()
