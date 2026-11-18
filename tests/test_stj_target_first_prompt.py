"""Synthetic contexts and mocked GPUs only; private review is never a fixture."""

import copy
from contextlib import nullcontext, redirect_stderr
import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_stj_pilot_19c as fixtures
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import annotate_stj_silver_19c_target_first as variant


class PromptTests(unittest.TestCase):
    def test_target_before_identical_marked_context_without_suggestions_or_mutation(self):
        record=fixtures.corpus(1)[0][0];before=copy.deepcopy(record)
        baseline=core.build_messages(record);messages=variant.build_messages(record)
        prefix,marked=messages[1]['content'].split('\nMarked context:\n',1)
        self.assertEqual(marked,baseline[1]['content'])
        self.assertIn(json.dumps(record['entity']),prefix)
        self.assertEqual(record,before)
        self.assertNotIn('suggested_label',json.dumps(messages))
        self.assertLess(len(variant.SYSTEM_PROMPT),len(core.SYSTEM_PROMPT))
        self.assertLess(len(variant.SYSTEM_PROMPT.split()),len(core.SYSTEM_PROMPT.split()))

    def test_multi_person_citation_and_invalid_spans_keep_the_original_protocol(self):
        text='AA ouviu BB, testemunha; citou a obra de CC. Tribunal Ficticio decidiu.'
        row=fixtures.corpus(1)[0][0]
        for entity in ('AA','BB','CC','Tribunal Ficticio'):
            start=text.index(entity)
            record={**row,'text':text,'entity':entity,'entity_start':start,'entity_end':start+len(entity)}
            content=variant.build_messages(record)[1]['content']
            self.assertEqual(content.count('[ENTITY]'),1)
            self.assertIn('[ENTITY] '+entity+' [/ENTITY]',content)
        with self.assertRaises(ValueError):variant.build_messages({**record,'entity':'wrong'})
        with self.assertRaises((ValueError,TypeError)):variant.build_messages({**record,'entity_end':len(text)+1})
        for term in ('REFERENCE','UNKNOWN','invalid_entity','other_roles','cited_proceeding'):
            self.assertIn(term,variant.SYSTEM_PROMPT)
        for label in core.LABELS:self.assertIn(label,variant.SYSTEM_PROMPT)
        self.assertIs(variant.core.parse_response,core.parse_response)

    def test_profile_restores_v1_even_on_failure(self):
        original=(core.PROMPT_VERSION,core.PROMPT_PATH,core.SYSTEM_PROMPT,core.build_messages)
        with self.assertRaises(RuntimeError):
            with variant.target_first_profile(['invented']):
                self.assertEqual(core.PROMPT_VERSION,variant.VERSION)
                raise RuntimeError('invented')
        self.assertEqual((core.PROMPT_VERSION,core.PROMPT_PATH,core.SYSTEM_PROMPT,core.build_messages),original)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.PilotBundleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture;self.root=fixture.root
        class Tensor:
            def __init__(self,n):self.shape=(1,n)
            def __getitem__(self,key):return Tensor(self.shape[1]-(key[1].start or 0))
        class Inputs(dict):
            def to(self,_):return self
        unknown=fixtures.response('UNKNOWN')
        unknown['assignments'][0].update(evidence='not_applicable',quote='',scope='not_applicable')
        class Tokenizer:
            pad_token_id=0;eos_token_id=1
            def __call__(self,*args,**kwargs):
                assert kwargs['truncation'] is False
                return Inputs(input_ids=Tensor(100))
            def batch_decode(self,*args,**kwargs):return [json.dumps(unknown)]
        self.model=SimpleNamespace(config=SimpleNamespace(max_position_embeddings=8192),generate=Mock(return_value=Tensor(107)))
        exp17=SimpleNamespace(render_prompt=lambda tokenizer,messages:'invented prompt',model_input_device=lambda model:'cuda:0',
                              torch=SimpleNamespace(inference_mode=nullcontext))
        env={'resolved_model_revision':'f'*40,'torch':'invented','transformers':'invented',
             'tokenizer_commit':'f'*40,'chat_template_sha256':'invented'}
        for context in (patch.dict(os.environ,{'SLURM_JOB_ID':'invented','CUDA_VISIBLE_DEVICES':'0'}),
                        patch.object(core,'private_new_output',side_effect=lambda p:p),
                        patch.object(variant,'private_new_output',side_effect=lambda p:p),
                        patch.object(core,'load_local_qwen',return_value=(self.model,Tokenizer(),exp17,env)),
                        patch('builtins.print')):
            self.enterContext(context)
        self.base=['runner','--input',str(fixture.input),'--selection-manifest',str(fixture.selection),'--revision','f'*40]
        preflight=self.root/'baseline_preflight';self.reference=self.root/'baseline'
        with patch('sys.argv',self.base+['--run-dir',str(preflight),'--preflight-only']):core.main()
        with patch('sys.argv',self.base+['--run-dir',str(self.reference),'--preflight-run',str(preflight/'run.json')]):core.main()
        self.base+=['--reference-run',str(self.reference/'run.json')]
        self.model.generate.reset_mock();self.baseline_bytes={p:p.read_bytes() for p in self.reference.iterdir()}

    def run_variant(self,output,preflight=None):
        argv=self.base+['--run-dir',str(output)]
        argv+=['--preflight-run',str(preflight/'run.json')] if preflight else ['--preflight-only']
        with patch('sys.argv',argv):
            mask=os.umask(0o077)
            try:variant.main()
            finally:os.umask(mask)

    def test_preflight_then_identical_30_occurrences_and_all_nonprompt_settings(self):
        preflight=self.root/'new_preflight';output=self.root/'new_pilot'
        self.run_variant(preflight);self.model.generate.assert_not_called()
        self.run_variant(output,preflight);self.assertEqual(self.model.generate.call_count,30)
        before=json.loads((self.reference/'run.json').read_text())['configuration']
        after=json.loads((output/'run.json').read_text())['configuration']
        self.assertEqual({k:v for k,v in before.items() if not k.startswith('prompt_')},
                         {k:v for k,v in after.items() if not k.startswith('prompt_')})
        self.assertEqual(after['prompt_version'],variant.VERSION)
        self.assertNotEqual(before['prompt_sha256'],after['prompt_sha256'])
        binding=json.loads((output/'variant.json').read_text())
        self.assertEqual(binding['run_sha256'],core.file_hash(output/'run.json'))
        predictions=[json.loads(line) for line in (output/'silver_predictions.jsonl').read_text().splitlines()]
        for original,result in zip(self.fixture.rows,predictions):
            for key in ('id','text','entity','entity_start','entity_end','source_text_sha256','pilot_selection'):
                self.assertEqual(original[key],result[key])
            self.assertFalse(result['human_validated']);self.assertTrue(result['requires_review'])
        self.assertEqual(self.baseline_bytes,{p:p.read_bytes() for p in self.reference.iterdir()})
        self.assertEqual(core.PROMPT_VERSION,'19c-v1')

    def test_wrong_preflight_or_changed_reference_cannot_load_model(self):
        preflight=self.root/'new_preflight';self.run_variant(preflight)
        path=preflight/'variant.json';saved=path.read_text();data=json.loads(saved)
        data['binding']['adapter_sha256']='changed';path.write_text(json.dumps(data))
        with patch.object(core,'load_local_qwen') as loader,redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.run_variant(self.root/'bad_pilot',preflight)
        loader.assert_not_called();path.write_text(saved)
        reference_path=self.reference/'run.json';data=json.loads(reference_path.read_text())
        data['configuration']['input_sha256']='changed';reference_path.write_text(json.dumps(data))
        with patch.object(core,'load_local_qwen') as loader,redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.run_variant(self.root/'bad_input')
        loader.assert_not_called()

    def test_changed_protected_bundle_blocks_before_model_loading(self):
        self.fixture.audit['unresolved_references']=['invented-pending']
        self.fixture.write_manifest()
        with patch.object(core,'load_local_qwen') as loader,redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.run_variant(self.root/'protected_failure')
        loader.assert_not_called()

    def test_missing_or_v1_preflight_cannot_start_variant(self):
        for preflight in (self.root/'baseline_preflight',self.root/'missing_preflight'):
            with self.subTest(path=preflight.name):
                with patch.object(core,'load_local_qwen') as loader,redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                    self.run_variant(self.root/('blocked_'+preflight.name),preflight)
                loader.assert_not_called()


if __name__=='__main__':unittest.main()
