"""Synthetic sources and injected HTTP only; no real court text or API calls."""

import copy
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_stj_pilot_19c as fixtures
from test_iaedu_agent_api_19c import ENV, Response
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import audit_next100_19c as capacity
from src.annotation import prepare_batch_19c_v3 as batch
from src.annotation import run_iaedu_batch_19c_v3 as runner


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.rows, docs, _ = fixtures.corpus(7)
        self.groups = batch.pilot.group_index(self.rows, docs)

    def test_deterministic_order_independent_no_quota_forcing_or_source_mutation(self):
        before = copy.deepcopy(self.rows)
        selected, summary, dispositions = batch.select_rows(self.rows, self.groups)
        again, summary2, dispositions2 = batch.select_rows(self.rows[::-1], self.groups)
        self.assertEqual((selected, summary, dispositions), (again, summary2, dispositions2))
        self.assertEqual(self.rows, before); self.assertEqual(summary['selected'], 7)
        self.assertEqual(summary['seed'], 42)
        self.assertEqual(len({r['batch_selection']['planning_group_id'] for r in selected}), 7)
        self.assertTrue(all(r['human_validated'] is False and r['label'] is None for r in selected))
        self.assertTrue(all('suggested_label' not in r for r in selected))

    def test_same_context_across_groups_reduces_actual_count(self):
        for row in self.rows:
            row['text'] = self.rows[0]['text']
        selected, summary, dispositions = batch.select_rows(self.rows, self.groups)
        self.assertEqual(len(selected), 1)
        self.assertEqual(summary['disposition_counts']['selected_context_similarity'], 6)
        self.assertEqual(len(summary['unrepresented_groups']), 6)
        self.assertTrue(all(d['first_conflicting_selected_id'] == selected[0]['id']
                            for d in dispositions if d['reason'] == 'selected_context_similarity'))

    def test_next_candidate_in_group_can_avoid_context_conflict(self):
        rows = self.rows[:3]
        # Visit the single-candidate group first, so the next group must choose
        # its distinct alternative. The policy is greedy, not global matching.
        labels = sorted(('invented-group-a', 'invented-group-b'), key=lambda g: (batch.pilot.digest(f'42:group:{g}'), g))
        self.groups[rows[0]['document_id']] = (labels[0], set())
        self.groups[rows[1]['document_id']] = (labels[1], set())
        self.groups[rows[2]['document_id']] = (labels[1], set())
        rows[1]['text'] = rows[0]['text']
        selected, _, _ = batch.select_rows(rows, self.groups)
        self.assertEqual(len(selected), 2)

    def test_group_cap_invalid_spans_duplicates_and_labels(self):
        chosen, summary, _ = batch.select_rows(self.rows, self.groups, maximum=2)
        self.assertEqual(len(chosen), 2); self.assertEqual(summary['disposition_counts']['requested_group_limit'], 5)
        for maximum in (0, 65, True):
            with self.assertRaises(ValueError): batch.select_rows(self.rows, self.groups, maximum)
        for changes in ('duplicate', 'span', 'label'):
            rows = copy.deepcopy(self.rows)
            if changes == 'duplicate': rows.append(rows[0])
            elif changes == 'span': rows[0]['entity_end'] = 3
            else: rows[0]['suggested_label'] = 'ARGUIDO'
            with self.assertRaises(ValueError): batch.select_rows(rows, self.groups)

    def test_sixty_four_groups_are_supported_without_forcing_larger_quota(self):
        rows, docs, _ = fixtures.corpus(70)
        groups = batch.pilot.group_index(rows, docs)
        chosen, summary, _ = batch.select_rows(rows, groups)
        self.assertEqual(len(chosen), 64)
        self.assertEqual(summary['disposition_counts']['requested_group_limit'], 6)


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.PilotBundleTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.fixture = fixture; self.root = fixture.root; self.folder = self.root/'capacity'
        for module in (capacity, batch):
            self.enterContext(patch.object(module, 'private_new_output', side_effect=lambda p: p))
        self.enterContext(patch.object(batch.pilot, 'GOLD_SHA', core.file_hash(self.root/'gold.jsonl')))
        self.enterContext(patch.object(batch.pilot, 'PILOT_SOURCES_SHA', core.file_hash(self.root/'human_pilot.jsonl')))
        argv = ['audit', '--input', str(self.root/'inventory_mentions.jsonl'),
                '--inventory-manifest', str(self.root/'inventory_manifest.json'),
                '--gold', str(self.root/'gold.jsonl'), '--pilot-sources', str(self.root/'human_pilot.jsonl'),
                '--development-input', str(fixture.input), '--development-selection', str(fixture.selection),
                '--output-dir', str(self.folder)]
        with patch('sys.argv', argv), redirect_stdout(io.StringIO()):
            self.assertEqual(capacity.main(), 0)

    def test_preparation_rebinds_full_audit_exports_effective_count_and_no_gold(self):
        paths = list(self.root.rglob('*')); before = {p: p.read_bytes() for p in paths if p.is_file()}
        report = batch.prepare(self.folder, self.root/'new-batch')
        self.assertEqual(report['selected'], 5)
        rows, manifest = batch.validate_capsule(self.root/'new-batch/capsule', report['capsule_manifest_sha256'])
        self.assertEqual(len(rows), 5); self.assertEqual(manifest['records'], 5)
        self.assertEqual(len(manifest['files']), 6)
        self.assertFalse(manifest['external_transmission_authorized'])
        old_ids = {r['id'] for r in self.fixture.rows}
        self.assertFalse(old_ids & {r['id'] for r in rows})
        for item in manifest['mapping']:
            request = (self.root/'new-batch/capsule'/item['request_file']).read_text(encoding='utf-8')
            self.assertIn('19c-v3-legal-roles', request)
            self.assertNotIn('suggested_label', request)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_changed_entry_including_fake_eligibility_or_missing_record_blocks(self):
        path = self.folder/'mention_capacity_PRIVATE.jsonl'
        original = path.read_bytes()
        rows = [json.loads(line) for line in original.decode().splitlines()]
        for modified in (rows[:-1], [dict(rows[0], reasons=[])]+rows[1:]):
            path.write_text(''.join(json.dumps(r)+'\n' for r in modified), encoding='utf-8')
            with self.assertRaises(ValueError): batch.load_audit(self.folder)
        path.write_bytes(original)

    def test_pending_reference_or_changed_source_blocks_before_output(self):
        path = self.folder/'audit_PRIVATE.json'; audit = json.loads(path.read_text())
        audit['unresolved_references'] = ['invented-unresolved']
        path.write_text(json.dumps(audit), encoding='utf-8')
        with self.assertRaises(ValueError): batch.prepare(self.folder, self.root/'blocked')
        self.assertFalse((self.root/'blocked').exists())

    def test_changed_source_hash_blocks_without_reauditing_or_overwriting(self):
        path = self.root/'inventory_mentions.jsonl'
        path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError, 'source_binding_changed'):
            batch.prepare(self.folder, self.root/'blocked')
        self.assertFalse((self.root/'blocked').exists())


class RunnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        for module in (batch, runner, runner.api):
            self.enterContext(patch.object(module, 'private_new_output', side_effect=lambda p: p))
        self.enterContext(patch.dict(os.environ, ENV, clear=True))
        rows, docs, _ = fixtures.corpus(3)
        groups = batch.pilot.group_index(rows, docs)
        self.rows, _, _ = batch.select_rows(rows, groups)
        self.capsule = self.root/'capsule'
        self.digest = batch.export_capsule(self.rows, self.capsule, 'a'*64, 'b'*64)
        self.auth = self.root/'auth.json'
        self.auth_value = json.loads((self.capsule/'authorization_TEMPLATE_PRIVATE.json').read_text())
        self.auth_value.update(external_transmission_authorized=True, privacy_review_completed=True,
                               approved_by='invented-local-tester', approved_at='2026-11-19T12:00:00+00:00',
                               endpoint=ENV['IAEDU_ENDPOINT'], channel_id=ENV['IAEDU_CHANNEL_ID'])
        self.auth.write_text(json.dumps(self.auth_value))
        unknown = fixtures.response('UNKNOWN')
        unknown['assignments'][0].update(evidence='not_applicable', quote='', scope='not_applicable')
        self.raw = json.dumps(unknown); self.body = (json.dumps({'type': 'token', 'content': self.raw})+'\n').encode()
        self.session = Mock(); self.session.post.return_value = Response(self.body)
        self.run = self.root/'run'

    def execute(self, resume=False):
        with redirect_stdout(io.StringIO()), patch.object(core, 'load_pilot', side_effect=AssertionError('No corpus on Windows')):
            return runner.execute(self.capsule, self.digest, self.run, self.auth, resume=resume, session=self.session)

    def test_effective_count_new_threads_raw_offsets_and_resume_without_replay(self):
        report = self.execute()
        self.assertEqual(report['expected_records'], 3)
        self.assertEqual(report['summary']['records'], 3)
        self.assertEqual(report['summary']['cohort'], batch.COHORT)
        self.assertEqual(self.session.post.call_count, 3)
        self.assertEqual(len({c.kwargs['files']['thread_id'][1] for c in self.session.post.call_args_list}), 3)
        results = [json.loads(line) for line in (self.run/'silver_predictions.jsonl').read_text().splitlines()]
        for n, (source, row) in enumerate(zip(self.rows, results), 1):
            for field in ('id', 'text', 'entity', 'entity_start', 'entity_end'):
                self.assertEqual(source[field], row[field])
            self.assertEqual((self.run/f'mentions/{n:03}/transport/response_body.bin').read_bytes(), self.body)
            self.assertEqual(row['llm_raw_output'], self.raw)
            self.assertFalse(row['human_validated']); self.assertTrue(row['requires_review'])
            self.assertEqual(row['model_metadata_returned'], [])
        self.session.post.reset_mock(); self.execute(resume=True)
        self.session.post.assert_not_called()

    def test_old_scope_wrong_count_or_false_authorization_never_dispatch(self):
        for changes in ({'scope': 'STJ_19C_30_IAEDU_API'}, {'records': 30}, {'external_transmission_authorized': False}):
            self.auth.write_text(json.dumps({**self.auth_value, **changes}))
            with self.assertRaisesRegex(ValueError, 'explicit_batch_authorization'): self.execute()
            self.assertFalse(self.run.exists()); self.session.post.assert_not_called()

    def test_invalid_json_preserved_without_repair(self):
        self.session.post.return_value = Response((json.dumps({'type': 'token', 'content': '```json\n{}\n```'})+'\n').encode())
        report = self.execute(); self.assertEqual(report['summary']['invalid_outputs'], 3)
        row = json.loads((self.run/'mentions/001/prediction.json').read_text())
        self.assertEqual(row['parsing_errors'], ['invalid_json'])
        self.assertEqual(row['llm_raw_output'], '```json\n{}\n```')

    def test_crash_after_capture_recovered_offline_no_duplicate_call(self):
        with patch.object(runner.historical, 'recover_result', side_effect=RuntimeError('invented-crash')):
            with self.assertRaises(RuntimeError): self.execute()
        self.assertEqual(self.session.post.call_count, 1)
        self.session.post.reset_mock(); report = self.execute(resume=True)
        self.assertEqual(report['summary']['records'], 3); self.assertEqual(self.session.post.call_count, 2)

    def test_unknown_dispatch_blocks_resume_and_checkpoint_tampering_blocks(self):
        with patch.object(runner.api, 'stream_one', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.execute()
        with self.assertRaisesRegex(ValueError, 'dispatch_outcome_unknown'): self.execute(resume=True)
        self.session.post.assert_not_called()

    def test_capsule_tampering_and_digest_mismatch_fail(self):
        with self.assertRaisesRegex(ValueError, 'trusted_capsule_digest'): batch.validate_capsule(self.capsule, '0'*64)
        path = self.capsule/'requests/001.txt'; path.write_bytes(path.read_bytes()+b' changed')
        with self.assertRaisesRegex(ValueError, 'portable_file_changed'): self.execute()
        self.session.post.assert_not_called()

    def test_check_only_without_env_credentials_or_dispatch(self):
        argv = ['check', '--capsule-dir', str(self.capsule), '--expected-manifest-sha256', self.digest, '--check-only']
        with patch('sys.argv', argv), patch.dict(os.environ, {}, clear=True), redirect_stdout(io.StringIO()):
            runner.main()
        self.session.post.assert_not_called(); self.assertFalse(self.run.exists())

    def test_capsule_and_orchestration_support_more_than_thirty_records(self):
        rows, docs, _ = fixtures.corpus(64)
        groups = batch.pilot.group_index(rows, docs)
        selected, _, _ = batch.select_rows(rows, groups)
        capsule = self.root/'capsule64'
        digest = batch.export_capsule(selected, capsule, 'c'*64, 'd'*64)
        verified, manifest = batch.validate_capsule(capsule, digest)
        self.assertEqual(len(verified), 64)
        auth = dict(self.auth_value, records=64, capsule_manifest_sha256=digest)
        self.auth.write_text(json.dumps(auth))
        # Transport and recovery already have end-to-end injected HTTP tests.
        # Isolate orchestration cardinality here to avoid 64 redundant captures.
        with patch.object(batch, 'validate_capsule', return_value=(verified, manifest)), \
                patch.object(runner.api, 'stream_one') as stream, \
                patch.object(runner.historical, 'recover_result', side_effect=lambda slot, record, binding: core.proposal(record, self.raw, {})), \
                redirect_stdout(io.StringIO()) as stdout:
            report = runner.execute(capsule, digest, self.run, self.auth, session=self.session)
        self.assertEqual(stream.call_count, 64)
        self.assertEqual(report['expected_records'], 64)
        self.assertIn('64/64', stdout.getvalue())
        self.assertTrue((self.run/'mentions/064/attempt.json').exists())


if __name__ == '__main__':
    unittest.main()
