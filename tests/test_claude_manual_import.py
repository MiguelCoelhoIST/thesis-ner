"""Synthetic responses only; no browser, external service or model is invoked."""

import json
import unittest
from unittest.mock import patch

import test_stj_pilot_19c as fixtures
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import prepare_second_llm_pilot_19c as package
from src.annotation import import_claude_manual_19c as importer


class ManualImportTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.PilotBundleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture;self.root=fixture.root
        source,_=fixture.write_saved_pilot();self.folder=self.root/'manual_package'
        with patch.object(package,'private_new_output',side_effect=lambda p:p):
            package.prepare_package(fixture.input,fixture.selection,source/'run.json',self.folder)
        self.session=self.folder/'session_PRIVATE.json'
        metadata=importer.read_json(self.folder/'session_TEMPLATE_PRIVATE.json')
        metadata.update(model_display_name='Claude Invented Test Model',model_version_or_identifier='invented-test-version',
                        platform='invented-platform',fresh_chat_per_mention=True,generation_controls='not_exposed',
                        platform_instructions_or_tools='not_disclosed',session_date='2026-11-19',
                        response_capture_method='invented_full_message_copy')
        self.session.write_text(json.dumps(metadata),encoding='utf-8')
        obj=fixtures.response('UNKNOWN');obj['assignments'][0].update(evidence='not_applicable',quote='',scope='not_applicable')
        self.raw=(json.dumps(obj)+'\r\n').encode('utf-8')
        for i in range(1,31):(self.folder/'raw_responses'/f'{i:03}.txt').write_bytes(self.raw)

    def run_import(self,output):
        with patch.object(importer,'private_new_output',side_effect=lambda p:p):
            return importer.import_responses(self.folder,self.session,output)

    def test_preserves_raw_bytes_and_records_model_without_semantic_validation(self):
        bad=self.folder/'raw_responses/002.txt';bad.write_bytes(b'```json\r\n'+self.raw+b'```\r\n')
        saved={p:p.read_bytes() for p in (self.session,self.fixture.input,self.fixture.selection,bad)}
        output=self.root/'imported'
        with patch.object(core,'load_local_qwen',side_effect=AssertionError('No model')):
            report=self.run_import(output)
        self.assertEqual(report['summary']['valid_outputs'],29);self.assertEqual(report['LLM_calls'],0)
        self.assertEqual(report['manual_responses_imported'],30)
        rows=[json.loads(l) for l in (output/'silver_predictions.jsonl').read_text().splitlines()]
        self.assertEqual(rows[0]['llm_raw_output'].encode('utf-8'),self.raw)
        self.assertEqual((output/'raw_responses/002.txt').read_bytes(),bad.read_bytes())
        self.assertEqual(rows[1]['manual_import']['raw_sha256'],core.file_hash(output/'raw_responses/002.txt'))
        self.assertEqual(rows[1]['parsing_errors'],['invalid_json'])
        self.assertEqual(rows[1]['proposed_labels'],[])
        for original,row in zip(self.fixture.rows,rows):
            for key in ('id','text','entity','entity_start','entity_end','pilot_selection'):
                self.assertEqual(row[key],original[key])
            self.assertEqual(row['annotation_provider'],'Anthropic')
            self.assertEqual(row['annotation_source'],'Claude Invented Test Model')
            self.assertFalse(row['human_validated']);self.assertTrue(row['requires_review'])
            self.assertTrue(all(v is None for v in row['semantic_review'].values()))
        self.assertEqual(saved,{p:p.read_bytes() for p in saved})

    def test_missing_extra_responses_pending_model_and_mixed_context_are_rejected(self):
        output=self.root/'bad'
        missing=self.folder/'raw_responses/030.txt';missing.unlink()
        with self.assertRaisesRegex(ValueError,'exactly_30'):self.run_import(output)
        self.assertFalse(output.exists());missing.write_bytes(self.raw)
        extra=self.folder/'raw_responses/retry.txt';extra.write_bytes(self.raw)
        with self.assertRaisesRegex(ValueError,'exactly_30'):self.run_import(output)
        extra.unlink()
        metadata=importer.read_json(self.session);metadata['model_version_or_identifier']='PENDING_CONFIRMATION'
        self.session.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError,'metadata_pending'):self.run_import(output)
        metadata['model_version_or_identifier']='not_disclosed';metadata['fresh_chat_per_mention']=False
        self.session.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError,'protocol_mismatch'):self.run_import(output)
        self.assertFalse(output.exists())

    def test_changed_request_or_mapping_never_silently_reassigns_a_response(self):
        output=self.root/'changed';request=self.folder/'requests/001.txt'
        before=request.read_bytes();request.write_bytes(before+b' invented extra instruction')
        with self.assertRaises(ValueError):self.run_import(output)
        self.assertFalse(output.exists());request.write_bytes(before)
        manifest_path=self.folder/'manifest_PRIVATE.json';manifest=importer.read_json(manifest_path)
        manifest['mapping'][0]['entity_start']+=1
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):self.run_import(output)
        self.assertFalse(output.exists())

    def test_separate_system_user_modality_is_recorded_and_schema_stays_strict(self):
        metadata=importer.read_json(self.session);metadata['message_delivery']='separate_system_user'
        self.session.write_text(json.dumps(metadata))
        report=self.run_import(self.root/'separate_roles')
        self.assertEqual(report['session']['message_delivery'],'separate_system_user')
        self.assertEqual(report['summary']['valid_outputs'],30)


if __name__=='__main__':unittest.main()
