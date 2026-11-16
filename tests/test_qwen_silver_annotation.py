"""Historical suspended Qwen prototype contract, NOT the Experiment 19c schema.

Synthetic tests only: no model inference or authorization to run the prototype.
"""

import copy
import json
import unittest

from src.annotation.annotate_role_candidates_qwen import (
    aggregate, build_messages, parse_response, proposal,
)


def candidate():
    text = "A testemunha AA respondeu."
    return {"id": "synthetic", "text": text, "entity": "AA",
            "entity_start": text.index("AA"), "entity_end": text.index("AA") + 2,
            "suggested_label": "RELATOR", "label": None, "human_validated": False}


def response(label="TESTEMUNHA", **updates):
    row = {"status": "supported", "assignments": [
        {"label": label, "evidence": "explicit", "quote": "testemunha AA", "scope": "current_proceeding"}],
           "ambiguity_reason": ""}
    row.update(updates)
    return row


class SilverAnnotationTests(unittest.TestCase):
    def test_prompt_hides_suggestion_and_metadata(self):
        row = candidate()
        messages = build_messages(row)
        other = {**row, "suggested_label": "REU", "process_number": "PRIVATE_METADATA"}
        self.assertEqual(messages, build_messages(other))
        self.assertIn("[ENTITY] AA [/ENTITY]", messages[1]["content"])
        self.assertNotIn("PRIVATE_METADATA", str(messages))

    def test_offsets_exact_and_boolean_rejected(self):
        row = candidate()
        for change in ({"entity_start": 0}, {"entity_end": 999}, {"entity_start": True}, {"entity": "BB"}):
            with self.assertRaises((ValueError, TypeError)):
                build_messages({**row, **change})

    def test_exact_quote_and_supported_response(self):
        parsed, errors = parse_response(json.dumps(response()), candidate()["text"])
        self.assertEqual(errors, [])
        self.assertEqual(parsed["assignments"][0]["label"], "TESTEMUNHA")
        bad = response()
        bad["assignments"][0]["quote"] = "invented evidence not present"
        self.assertIn("quote_not_exact_short_substring", parse_response(json.dumps(bad), candidate()["text"])[1])

    def test_multilabel_cited_scope_and_no_gold(self):
        obj = response()
        obj["assignments"].append({"label": "RECORRENTE", "evidence": "inferred",
                                   "quote": "AA respondeu", "scope": "cited_proceeding"})
        original = candidate()
        saved = copy.deepcopy(original)
        row = proposal(original, json.dumps(obj), {"model": "synthetic-test"})
        self.assertTrue(row["llm_output_valid"])
        self.assertEqual(set(row["proposed_labels"]), {"TESTEMUNHA", "RECORRENTE"})
        self.assertIsNone(row["label"])
        self.assertFalse(row["human_validated"])
        self.assertEqual(original, saved)

    def test_reference_separate_and_unknown_exclusive(self):
        ref = response("REFERENCE")
        ref["assignments"][0]["scope"] = "not_applicable"
        row = proposal(candidate(), json.dumps(ref), {})
        self.assertEqual(row["proposed_labels"], [])
        self.assertEqual(row["experimental_categories"], ["REFERENCE"])
        unknown = {"label": "UNKNOWN", "evidence": "not_applicable", "scope": "not_applicable", "quote": ""}
        ref["assignments"].append(unknown)
        self.assertIn("unknown_not_exclusive", parse_response(json.dumps(ref), candidate()["text"])[1])
        self.assertEqual(parse_response(json.dumps(response(assignments=[unknown])), candidate()["text"])[1], [])

    def test_insufficient_is_not_unknown(self):
        obj = response(status="insufficient", assignments=[], ambiguity_reason="Not enough context.")
        row = proposal(candidate(), json.dumps(obj), {})
        self.assertTrue(row["llm_output_valid"])
        self.assertEqual(row["proposed_labels"], [])
        self.assertFalse(row["human_validated"])

    def test_ambiguous_requires_reason(self):
        self.assertIn("missing_ambiguity_reason", parse_response(json.dumps(response(status="ambiguous")), candidate()["text"])[1])
        self.assertEqual(parse_response(json.dumps(response(status="ambiguous", ambiguity_reason="Two roles uncertain.")), candidate()["text"])[1], [])

    def test_strict_invalid_json_labels_keys_and_duplicates(self):
        for raw in ("```json\n{}\n```", "UNKNOWN", '{"status":1,"status":2}'):
            self.assertTrue(parse_response(raw, candidate()["text"])[1])
        for obj in (response("FAKE"), response(assignments=response()["assignments"] * 2),
                    {**response(), "human_validated": True}, response(status="insufficient")):
            self.assertTrue(parse_response(json.dumps(obj), candidate()["text"])[1])

    def test_summary_is_lexical_comparison_not_accuracy(self):
        good = proposal(candidate(), json.dumps(response()), {})
        invalid = proposal({**candidate(), "id": "second"}, "garbage", {})
        summary = aggregate([good, invalid])
        self.assertEqual(summary["valid_outputs"], 1)
        self.assertEqual(summary["invalid_outputs"], 1)
        self.assertEqual(summary["lexical_comparison_not_accuracy"]["suggestion_absent"], 1)
        self.assertNotIn("accuracy", summary)
        self.assertNotIn("f1", summary)
        self.assertNotIn("raw_output", json.dumps(summary))


if __name__ == "__main__":
    unittest.main()
