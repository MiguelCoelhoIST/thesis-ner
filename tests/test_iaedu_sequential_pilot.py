"""Invented corpus, local files and injected HTTP only; never call IAedu."""

from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import test_stj_pilot_19c as fixtures
from test_iaedu_agent_api_19c import ENV, Response
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import prepare_second_llm_pilot_19c as package
from src.annotation import portable_iaedu_pilot_19c as portable
from src.annotation import run_iaedu_pilot_19c as runner
from src.annotation import iaedu_agent_api_19c as api


class SequentialTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.PilotBundleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture;self.root=fixture.root
        for module in (package,portable,runner,api):
            self.enterContext(patch.object(module,'private_new_output',side_effect=lambda p:p))
        self.enterContext(patch.dict(os.environ,ENV,clear=True))
        source,_=fixture.write_saved_pilot();self.folder=self.root/'source_package'
        package.prepare_package(fixture.input,fixture.selection,source/'run.json',self.folder)
        self.capsule=self.root/'capsule'
        exported=portable.export_capsule(self.folder,self.capsule);self.digest=exported['portable_manifest_sha256']
        self.auth=self.root/'authorization.json'
        auth=copy.deepcopy(json.loads((self.capsule/'authorization_TEMPLATE_PRIVATE.json').read_text()))
        auth.update(external_transmission_authorized=True,privacy_review_completed=True,approved_by='invented-test-user',
                    approved_at='2026-11-19T12:00:00+00:00',endpoint=ENV['IAEDU_ENDPOINT'],channel_id=ENV['IAEDU_CHANNEL_ID'])
        portable.write_json_new(self.auth,auth)
        obj=fixtures.response('UNKNOWN');obj['assignments'][0].update(evidence='not_applicable',quote='',scope='not_applicable')
        self.raw=json.dumps(obj)
        self.body=(json.dumps({'type':'token','content':self.raw})+'\n').encode()
        self.session=Mock();self.session.post.return_value=Response(self.body)
        self.run=self.root/'run'

    def execute(self,resume=False):
        # Portable execution may not fall back to the source corpus validator.
        with patch.object(core,'load_pilot',side_effect=AssertionError('Corpus must remain on source')),redirect_stdout(io.StringIO()):
            return runner.execute(self.capsule,self.digest,self.run,self.auth,resume=resume,session=self.session)

    def test_capsule_is_minimal_and_validates_without_corpus_but_requires_trusted_digest(self):
        with patch.object(core,'load_pilot',side_effect=AssertionError('No corpus on Windows')):
            rows,manifest=portable.validate_capsule(self.capsule,self.digest)
        self.assertEqual(len(rows),30);self.assertFalse(manifest['full_corpus_included'])
        self.assertTrue(manifest['contains_private_contexts'])
        self.assertFalse(manifest['gold_examples_included'])
        self.assertEqual(len(manifest['files']),31)
        self.assertFalse(json.loads((self.capsule/'authorization_TEMPLATE_PRIVATE.json').read_text())['external_transmission_authorized'])
        self.assertEqual((self.capsule/'pilot_input.jsonl').read_bytes(),self.fixture.input.read_bytes())
        with self.assertRaisesRegex(ValueError,'trusted_capsule_digest'):portable.validate_capsule(self.capsule,'0'*64)
        request=self.capsule/'requests/001.txt';request.write_bytes(request.read_bytes()+b' changed')
        with self.assertRaisesRegex(ValueError,'portable_file_changed'):portable.validate_capsule(self.capsule,self.digest)

    def test_false_authorization_never_dispatches_or_modifies_run(self):
        auth=json.loads(self.auth.read_text());auth['external_transmission_authorized']=False
        self.auth.write_text(json.dumps(auth))
        with self.assertRaisesRegex(ValueError,'explicit_scoped_authorization_required'):self.execute()
        self.session.post.assert_not_called();self.assertFalse(self.run.exists())

    def test_all_30_new_threads_preserve_requests_raw_offsets_and_skip_completed_on_resume(self):
        report=self.execute();self.assertEqual(report['state'],'completed')
        self.assertEqual(self.session.post.call_count,30)
        threads={call.kwargs['files']['thread_id'][1] for call in self.session.post.call_args_list}
        self.assertEqual(len(threads),30)
        results=[json.loads(line) for line in (self.run/'silver_predictions.jsonl').read_text().splitlines()]
        for ordinal,(record,result,call) in enumerate(zip(self.fixture.rows,results,self.session.post.call_args_list),1):
            slot=self.run/'mentions'/f'{ordinal:03}'
            self.assertEqual(call.kwargs['files']['message'][1],(self.capsule/'requests'/f'{ordinal:03}.txt').read_bytes().decode())
            self.assertEqual((slot/'transport/response_body.bin').read_bytes(),self.body)
            self.assertTrue((slot/'complete.json').is_file())
            for key in ('id','text','entity','entity_start','entity_end','source_text_sha256'):
                self.assertEqual(record[key],result[key])
            self.assertFalse(result['human_validated']);self.assertTrue(result['requires_review'])
            self.assertEqual(result['model_metadata_returned'],[])
            self.assertEqual(result['backend_model_identity_status'],'not_found_in_parsed_metadata')
            self.assertEqual(result['agent_label_reported_by_user'],'OpenAI GPT-5.5')
        before=(self.run/'mentions/001/prediction.json').read_bytes()
        self.session.post.reset_mock();self.execute(resume=True)
        self.session.post.assert_not_called()
        self.assertEqual(before,(self.run/'mentions/001/prediction.json').read_bytes())

    def test_crash_after_http_before_prediction_recovers_without_repeating_completed_http(self):
        with patch.object(runner,'recover_result',side_effect=RuntimeError('invented process crash')):
            with self.assertRaises(RuntimeError):self.execute()
        self.assertEqual(self.session.post.call_count,1)
        self.assertFalse((self.run/'mentions/001/complete.json').exists())
        self.session.post.reset_mock();report=self.execute(resume=True)
        self.assertEqual(report['summary']['records'],30);self.assertEqual(self.session.post.call_count,29)

    def test_unknown_dispatch_is_never_blindly_replayed(self):
        with patch.object(api,'stream_one',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.execute()
        self.session.post.assert_not_called()
        with self.assertRaisesRegex(ValueError,'dispatch_outcome_unknown'):self.execute(resume=True)
        self.session.post.assert_not_called()
        self.assertEqual(json.loads((self.run/'run.json').read_text())['state'],'blocked_review_required')

    def test_partial_stream_stops_and_is_not_retried_on_resume(self):
        self.session.post.return_value=Response(self.body,fail=True)
        with self.assertRaisesRegex(ValueError,'transport_failure_review_required'):self.execute()
        self.assertEqual(self.session.post.call_count,1);self.session.post.reset_mock()
        with self.assertRaisesRegex(ValueError,'transport_failure_review_required'):self.execute(resume=True)
        self.session.post.assert_not_called()

    def test_invalid_model_json_is_preserved_and_completed_not_repaired_or_retried(self):
        invalid='```json\n'+self.raw+'\n```'
        self.session.post.return_value=Response((json.dumps({'type':'token','content':invalid})+'\n').encode())
        report=self.execute();self.assertEqual(report['summary']['invalid_outputs'],30)
        result=json.loads((self.run/'mentions/001/prediction.json').read_text())
        self.assertEqual(result['llm_raw_output'],invalid);self.assertEqual(result['parsing_errors'],['invalid_json'])
        self.assertEqual(result['proposed_labels'],[])
        self.session.post.reset_mock();self.execute(resume=True);self.session.post.assert_not_called()

    def test_tampered_completed_result_blocks_and_lock_prevents_concurrent_runner(self):
        self.execute();self.session.post.reset_mock()
        with runner.run_lock(self.run),self.assertRaisesRegex(ValueError,'another_runner'):
            self.execute(resume=True)
        self.session.post.assert_not_called()
        raw=self.run/'mentions/001/transport/response_body.bin';raw.write_bytes(raw.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'captured_body_changed'):self.execute(resume=True)
        self.session.post.assert_not_called()

    def test_check_only_needs_no_key_or_api_configuration(self):
        argv=['runner','--capsule-dir',str(self.capsule),'--expected-manifest-sha256',self.digest,'--check-only']
        stdout=io.StringIO()
        with (patch('sys.argv',argv),patch.object(api,'configuration',side_effect=AssertionError('No API configuration')),
              patch.object(runner,'execute',side_effect=AssertionError('No execution')),redirect_stdout(stdout)):
            runner.main()
        result=json.loads(stdout.getvalue());self.assertEqual(result['network_calls'],0)
        self.assertFalse(result['external_transmission_authorized'])

    def test_line_endings_only_are_allowed_for_code_and_secret_never_saved_as_request(self):
        a=self.root/'lf.py';b=self.root/'crlf.py'
        a.write_bytes(b'print("invented")\n');b.write_bytes(b'print("invented")\r\n')
        self.assertEqual(portable.lf_hash(a),portable.lf_hash(b))
        b.write_bytes(b'print("changed")\r\n');self.assertNotEqual(portable.lf_hash(a),portable.lf_hash(b))
        with patch.dict(os.environ,{'IAEDU_API_KEY':'AA'}),self.assertRaisesRegex(ValueError,'credential_in_request'):
            self.execute()
        self.session.post.assert_not_called();self.assertFalse(self.run.exists())

    def test_changed_endpoint_mid_run_stops_before_another_http_request(self):
        def post(*args,**kwargs):
            os.environ['IAEDU_CHANNEL_ID']='changed-after-first-request'
            return Response(self.body)
        self.session.post.side_effect=post
        with self.assertRaisesRegex(ValueError,'iaedu_configuration_changed'):self.execute()
        self.assertEqual(self.session.post.call_count,1)
        self.assertTrue((self.run/'mentions/001/complete.json').is_file())

    def test_api_model_metadata_is_distinct_from_ui_label_not_inferred_as_verified(self):
        body=(json.dumps({'type':'metadata','model':'invented-returned-backend'})+'\n').encode()+self.body
        self.session.post.return_value=Response(body);self.execute()
        row=json.loads((self.run/'mentions/001/prediction.json').read_text())
        self.assertEqual(row['agent_label_reported_by_user'],'OpenAI GPT-5.5')
        self.assertEqual(row['model_metadata_returned'][0]['value'],'invented-returned-backend')
        self.assertEqual(row['backend_model_identity_status'],'metadata_returned_not_independently_verified')


if __name__=='__main__':unittest.main()
