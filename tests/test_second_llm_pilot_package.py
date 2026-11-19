"""Invented contexts only. Blind preparation never invokes a model or API."""

import copy
import io
import json
import os
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch

import test_stj_pilot_19c as fixtures
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import annotate_stj_silver_19c_target_first as prompt
from src.annotation import prepare_second_llm_pilot_19c as package


class PackageTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.PilotBundleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture;self.root=fixture.root
        self.source,_=fixture.write_saved_pilot();self.reference=self.source/'run.json'

    def prepare(self,output):
        with patch.object(package,'private_new_output',side_effect=lambda p:p):
            return package.prepare_package(self.fixture.input,self.fixture.selection,self.reference,output)

    def test_only_messages_sent_and_exact_30_preserved_with_private_mapping(self):
        saved={p:p.read_bytes() for p in (self.fixture.input,self.fixture.selection,self.reference,
                                         self.source/'silver_predictions.jsonl')}
        output=self.root/'blind'
        with patch.object(core,'load_local_qwen',side_effect=AssertionError('No inference')):
            manifest=self.prepare(output)
        requests=[json.loads(l) for l in (output/'model_messages_PRIVATE.jsonl').read_text().splitlines()]
        forms=[json.loads(l) for l in (output/'comparison_template_PRIVATE.jsonl').read_text().splitlines()]
        self.assertEqual(len(requests),30);self.assertEqual(manifest['LLM_calls'],0)
        self.assertFalse(manifest['external_transmission_authorized'])
        self.assertEqual(manifest['intended_use'],'CLAUDE_MANUAL_PRIVATE_INSPECTION_ONLY')
        self.assertEqual(manifest['privacy_review_status'],'PENDING')
        for record,request,mapping,form in zip(self.fixture.rows,requests,manifest['mapping'],forms):
            self.assertEqual(set(request),{'messages'})
            self.assertEqual(request['messages'],prompt.build_messages(record))
            self.assertEqual((output/mapping['manual_text_file']).read_bytes(),
                             '\n\n'.join(m['content'] for m in request['messages']).encode('utf-8'))
            for key in ('id','entity_start','entity_end','source_text_sha256'):
                self.assertEqual(mapping[key],record[key])
            self.assertEqual(mapping['messages_sha256'],package.fingerprint(request['messages']))
            for key in ('format_and_quotes','target_association','proceeding_scope','additional_roles_and_abstention'):
                self.assertIsNone(form[key])
            self.assertFalse(form['human_validated']);self.assertTrue(form['requires_review'])
        self.assertEqual(saved,{p:p.read_bytes() for p in saved})

    def test_proposals_and_reviews_cannot_enter_messages_from_extra_metadata(self):
        record=copy.deepcopy(self.fixture.rows[0])
        record['private_review']={'comment':'SENTINEL_PRIVATE_OPINION','proposed_response':{'label':'REU'}}
        request={'messages':prompt.build_messages(record)}
        self.assertNotIn('SENTINEL_PRIVATE_OPINION',json.dumps(request))
        record['suggested_label']='REU'
        with self.assertRaises(ValueError):prompt.build_messages(record)

    def test_wrong_reference_or_unresolved_protection_never_writes(self):
        original=self.reference.read_text()
        reference=json.loads(original);reference['configuration']['input_sha256']='changed'
        self.reference.write_text(json.dumps(reference))
        output=self.root/'bad_reference'
        with self.assertRaises(ValueError):self.prepare(output)
        self.assertFalse(output.exists());self.reference.write_text(original)
        self.fixture.audit['unresolved_references']=['invented-pending'];self.fixture.write_manifest()
        # Even a refreshed run binding cannot hide the unresolved protection.
        reference=json.loads(original)
        reference['configuration']['selection_sha256']=core.file_hash(self.fixture.selection)
        self.reference.write_text(json.dumps(reference))
        output=self.root/'bad_protection'
        with self.assertRaises(ValueError):self.prepare(output)
        self.assertFalse(output.exists())

    def test_cli_outputs_only_aggregates(self):
        output=self.root/'cli';stdout=io.StringIO()
        argv=['prepare','--input',str(self.fixture.input),'--selection-manifest',str(self.fixture.selection),
              '--reference-run',str(self.reference),'--output-dir',str(output)]
        with patch('sys.argv',argv),patch.object(package,'private_new_output',side_effect=lambda p:p),redirect_stdout(stdout):
            mask=os.umask(0o077)
            try:package.main()
            finally:os.umask(mask)
        printed=json.loads(stdout.getvalue())
        self.assertEqual(printed['records'],30);self.assertEqual(printed['LLM_calls'],0)
        self.assertNotIn(self.fixture.rows[0]['entity'],stdout.getvalue())

    def test_new_private_output_required_without_touching_existing_files(self):
        output=self.root/'existing';output.mkdir();path=output/'keep.txt';path.write_text('invented')
        with patch('src.annotation.prepare_role_annotation_batch.RAW',self.root),self.assertRaises(ValueError):
            package.prepare_package(self.fixture.input,self.fixture.selection,self.reference,output)
        self.assertEqual(path.read_text(),'invented');self.assertEqual(list(output.iterdir()),[path])


if __name__=='__main__':unittest.main()
