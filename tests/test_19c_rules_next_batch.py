"""Invented people/texts only; no model, corpus, API or private review fixtures."""

import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from src.annotation import annotate_stj_silver_19c as core
from src.annotation import annotate_stj_silver_19c_target_first as v2
from src.annotation import prompt_19c_v3 as v3
from src.annotation import verify_assisted_review_19c as review_tool
from src.annotation import audit_next100_19c as inventory
import test_stj_pilot_19c as fixtures


def invented_review():
    source = {'id': 'invented-review-1', 'text': 'AA, testemunha, confirmou o facto.',
              'entity': 'AA', 'entity_start': 0, 'entity_end': 2,
              'annotation_tier': 'UNANNOTATED', 'human_validated': False, 'label': None}
    response = fixtures.response()
    original = core.proposal(source, json.dumps(response), {})
    item = {'id': source['id'], 'ordinal': 1,
            'source_record_sha256': review_tool.compact_fingerprint(original),
            'source_context_sha256': hashlib.sha256(source['text'].encode()).hexdigest(),
            'source_entity_span': {'start': 0, 'end': 2},
            'original_llm_raw_output': original['llm_raw_output'],
            'original_response': response, 'original_parsing_errors': [],
            'proposed_response': response, 'changed': False,
            'evidence_source_spans': [{'field': 'assignments', 'designation': 'TESTEMUNHA',
                'quote': 'testemunha', 'context_matches': [{'start': 4, 'end': 14}]}],
            'proposed_parser_errors': [], 'human_validated': False, 'requires_review': True,
            'training_eligibility': 'NOT_ESTABLISHED'}
    return {'reviews': [item]}, [original], [source]


class ReviewTests(unittest.TestCase):
    def test_cli_binds_sources_writes_new_audit_without_mutation_or_private_stdout(self):
        review, originals, inputs = invented_review()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            files = {'predictions': originals, 'input': inputs}
            for name, records in files.items():
                (folder/name).write_text(''.join(json.dumps(r)+'\n' for r in records), encoding='utf-8')
            aggregate = core.aggregate(originals)
            run = {'predictions_sha256': core.file_hash(folder/'predictions'), 'summary': aggregate}
            (folder/'run').write_text(json.dumps(run), encoding='utf-8')
            review.update(source_predictions_sha256=core.file_hash(folder/'predictions'),
                          source_run_sha256=core.file_hash(folder/'run'),
                          parser_script_sha256=core.file_hash(Path(core.__file__)),
                          human_validated=False, LLM_calls=0, changes_original_results=False,
                          training_eligibility='NOT_ESTABLISHED',
                          original_summary={k: aggregate[k] for k in ('records', 'valid_outputs', 'invalid_outputs')},
                          review_summary={'reviewed_cases': 1, 'changed_proposals': 0, 'confirmed_proposals': 1})
            (folder/'review').write_text(json.dumps(review), encoding='utf-8')
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            argv = ['verify']
            for name in ('review', 'predictions', 'run', 'input'):
                argv += ['--'+name, str(folder/name)]
            argv += ['--output-dir', str(folder/'output')]
            stdout = io.StringIO()
            with patch('sys.argv', argv), patch.object(review_tool, 'private_new_output', side_effect=lambda p: p), redirect_stdout(stdout):
                self.assertEqual(review_tool.main(), 0)
            self.assertNotIn(originals[0]['text'], stdout.getvalue())
            self.assertTrue((folder/'output/verification_PRIVATE.json').exists())
            self.assertEqual(before, {name: (folder/name).read_bytes() for name in before})
            (folder/'run').write_text('{}', encoding='utf-8')
            with patch('sys.argv', argv), patch.object(review_tool, 'private_new_output', side_effect=lambda p: folder/'second'), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): review_tool.main()
            self.assertFalse((folder/'second').exists())

    def test_verified_proposal_is_still_not_human_gold(self):
        args = invented_review(); saved = copy.deepcopy(args)
        rows, summary = review_tool.verify(*args)
        self.assertEqual(summary['verified'], 1)
        self.assertFalse(rows[0]['human_validated'])
        self.assertEqual(args, saved)

    def test_fingerprint_raw_and_quote_tampering_fail(self):
        for field, value, expected in [
            ('source_record_sha256', '0'*64, 'source_record_fingerprint_mismatch'),
            ('original_llm_raw_output', '{}', 'historical_output_mismatch'),
            ('evidence_source_spans', [], 'proposed_evidence_offsets_mismatch'),
            ('human_validated', True, 'review_status_unsafe')]:
            with self.subTest(field=field):
                args = invented_review(); args[0]['reviews'][0][field] = value
                results, _ = review_tool.verify(*args)
                self.assertIn(expected, results[0]['errors'])

    def test_duplicate_or_unknown_review_ids(self):
        args = invented_review(); args[0]['reviews'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicate_review_id'):
            review_tool.verify(*args)
        args = invented_review(); args[0]['reviews'][0]['id'] = 'invented-missing'
        rows, _ = review_tool.verify(*args)
        self.assertEqual(rows[0]['errors'], ['unknown_review_id'])

    def test_original_metadata_and_id_order_cannot_be_rebound(self):
        args = invented_review(); args[2][0]['text'] += ' Alterado.'
        with self.assertRaisesRegex(ValueError, 'original_input_metadata_mismatch'):
            review_tool.verify(*args)
        args = invented_review(); args[2][0]['id'] = 'another-invented-id'
        with self.assertRaisesRegex(ValueError, 'input_prediction_id_order_mismatch'):
            review_tool.verify(*args)

    def test_invented_nonliteral_evidence_is_not_repaired(self):
        args = invented_review()
        args[0]['reviews'][0]['proposed_response'] = copy.deepcopy(args[0]['reviews'][0]['proposed_response'])
        args[0]['reviews'][0]['proposed_response']['assignments'][0]['quote'] = 'AA era testemunha'
        rows, _ = review_tool.verify(*args)
        self.assertIn('proposed_response_invalid', rows[0]['errors'])

    def test_all_overlapping_literal_matches_are_recorded(self):
        self.assertEqual(review_tool.literal_spans('aaaa', 'aa'), [
            {'start': 0, 'end': 2}, {'start': 1, 'end': 3}, {'start': 2, 'end': 4}])


class PromptTests(unittest.TestCase):
    def test_target_first_same_context_no_mutation_or_review_leak(self):
        row = invented_review()[2][0]; saved = copy.deepcopy(row)
        before = (core.SYSTEM_PROMPT, v2.SYSTEM_PROMPT)
        messages = v3.build_messages(row)
        self.assertEqual(messages[1], v2.build_messages(row)[1])
        self.assertEqual((core.SYSTEM_PROMPT, v2.SYSTEM_PROMPT), before)
        self.assertEqual(row, saved)
        self.assertNotEqual(messages[0]['content'], v2.SYSTEM_PROMPT)
        self.assertFalse(v3.configuration()['external_transmission_authorized'])
        self.assertEqual(len(core.LABELS), 10)

    def test_biased_or_invalid_input_is_rejected(self):
        for change in ({'suggested_label': 'ARGUIDO'}, {'entity_end': 3}, {'human_validated': True}):
            row = invented_review()[2][0]; row.update(change)
            with self.assertRaises(ValueError):
                v3.build_messages(row)

    def test_policy_has_decisive_distinctions_and_exact_schema(self):
        for phrase in ('labour claimant', 'family/affective', 'decisive gap',
                       'earlier stage', 'doctrinal position', 'redundant hierarchy',
                       'other_roles', 'uncertainty_reason', '240 characters'):
            self.assertIn(phrase, v3.SYSTEM_PROMPT)

    def test_multilabel_unknown_legal_role_and_abstention_reuse_parser(self):
        text = 'AA, arguido e recorrente, apresentou o pedido como comprador.'
        response = fixtures.response('ARGUIDO')
        response['assignments'][0]['quote'] = 'AA, arguido e recorrente'
        response['assignments'].append(dict(response['assignments'][0], label='RECORRENTE'))
        self.assertEqual(core.parse_response(json.dumps(response), text)[1], [])
        response['assignments'] = [{'label': 'UNKNOWN', 'evidence': 'not_applicable',
                                    'quote': '', 'scope': 'not_applicable'}]
        response['other_roles'] = [{'role': 'comprador', 'evidence': 'explicit',
                                   'quote': 'como comprador', 'scope': 'current_proceeding'}]
        self.assertEqual(core.parse_response(json.dumps(response), text)[1], [])
        response.update(status='insufficient', assignments=[], other_roles=[], uncertain=True,
                        uncertainty_reason='Falta o antecedente do alvo.')
        self.assertEqual(core.parse_response(json.dumps(response), text)[1], [])


class CapacityTests(unittest.TestCase):
    def test_source_bound_cli_audits_clean_synthetic_bundle_and_preserves_inputs(self):
        bundle = fixtures.PilotBundleTests(); bundle.setUp(); self.addCleanup(bundle.doCleanups)
        root = bundle.root
        argv = ['audit', '--input', str(root/'inventory_mentions.jsonl'),
                '--inventory-manifest', str(root/'inventory_manifest.json'),
                '--gold', str(root/'gold.jsonl'), '--pilot-sources', str(root/'human_pilot.jsonl'),
                '--development-input', str(bundle.input), '--development-selection', str(bundle.selection),
                '--output-dir', str(root/'capacity')]
        before = {p: p.read_bytes() for p in root.iterdir() if p.is_file()}
        stdout = io.StringIO()
        with patch('sys.argv', argv), patch.object(inventory, 'private_new_output', side_effect=lambda p: p), \
                patch.object(inventory.pilot, 'GOLD_SHA', core.file_hash(root/'gold.jsonl')), \
                patch.object(inventory.pilot, 'PILOT_SOURCES_SHA', core.file_hash(root/'human_pilot.jsonl')), \
                redirect_stdout(stdout):
            self.assertEqual(inventory.main(), 0)
        audit = json.loads((root/'capacity/audit_PRIVATE.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['summary']['available_related_groups'], 5)
        self.assertEqual(audit['summary']['selected'], 0)
        self.assertEqual(len((root/'capacity/mention_capacity_PRIVATE.jsonl').read_text().splitlines()), 35)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertNotIn(bundle.rows[0]['text'], stdout.getvalue())

    def corpus_and_refs(self, count=7):
        rows, docs, texts = fixtures.corpus(count)
        refs = fixtures.protected()
        refs['development_30'] = [copy.deepcopy(rows[0])]
        return rows, docs, texts, refs

    def test_protected_development_and_alias_families_excluded_without_selection(self):
        rows, docs, texts, refs = self.corpus_and_refs()
        saved = copy.deepcopy(rows)
        docs[1]['aliases'] = [{'decision_id': docs[0]['potential_process_group_ids'][0] + '.S2'}]
        entries, audit = inventory.audit_capacity(rows, docs, texts, refs)
        by_id = {r['id']: r for r in entries}
        self.assertTrue(by_id[rows[0]['id']]['reasons'])
        self.assertTrue(by_id[rows[1]['id']]['reasons'])
        self.assertEqual(audit['summary']['available_related_groups'], 5)
        self.assertEqual(audit['summary']['selected'], 0)
        self.assertFalse(audit['summary']['selection_performed'])
        self.assertEqual(rows, saved)

    def test_unresolved_protection_globally_blocks_capacity(self):
        args = self.corpus_and_refs(); del args[3]['gold'][0]['process_number']
        entries, audit = inventory.audit_capacity(*args)
        self.assertEqual(audit['summary']['available_mentions_capacity_only'], 0)
        self.assertTrue(all('protected_reference_unresolved_global_gate' in r['reasons'] for r in entries))

    def test_identity_unknown_propagates_across_related_documents(self):
        rows, docs, texts, refs = self.corpus_and_refs()
        docs[2]['requires_identity_review'] = True
        docs[3]['aliases'] = [{'decision_id': docs[2]['potential_process_group_ids'][0] + '.S1'}]
        entries, _ = inventory.audit_capacity(rows, docs, texts, refs)
        for row in entries[2:4]:
            self.assertIn('identity_unresolved_or_conflicting_group', row['reasons'])

    def test_content_match_reserves_entire_group_even_if_found_late(self):
        rows, docs, texts, refs = self.corpus_and_refs()
        docs[2]['aliases'] = [{'decision_id': docs[3]['potential_process_group_ids'][0] + '.S1'}]
        # Shortened protected context matches an inventory occurrence, with no
        # process identity of its own. Exact document match then reserves family.
        refs['gold'][0] = copy.deepcopy(rows[3])
        entries, audit = inventory.audit_capacity(rows, docs, texts, refs)
        self.assertTrue(entries[2]['reasons']); self.assertTrue(entries[3]['reasons'])
        self.assertEqual(audit['summary']['LLM_calls'], 0)

    def test_similarity_only_match_propagates_to_previously_seen_family(self):
        rows, docs, texts, refs = self.corpus_and_refs()
        docs[2]['aliases'] = [{'decision_id': docs[3]['potential_process_group_ids'][0] + '.S1'}]
        with patch.object(inventory, 'content_related', side_effect=lambda a, b: a['id'] == rows[3]['id']):
            entries, audit = inventory.audit_capacity(rows, docs, texts, refs)
        for row in entries[2:4]:
            self.assertIn('protected_context_similarity_group', row['reasons'])
        self.assertEqual(audit['summary']['protected_similarity_groups'], 1)

    def test_missing_protected_set_prefilled_labels_or_duplicate_ids_fail(self):
        args = self.corpus_and_refs(); del args[3]['development_30']
        with self.assertRaises(ValueError): inventory.audit_capacity(*args)
        for change in ('duplicate', 'label'):
            args = self.corpus_and_refs()
            if change == 'duplicate': args[0].append(args[0][0])
            else: args[0][1]['label'] = 'TESTEMUNHA'
            with self.assertRaises(ValueError): inventory.audit_capacity(*args)


if __name__ == '__main__':
    unittest.main()
