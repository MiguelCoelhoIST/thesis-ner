"""Invented corpus/outputs only. No weights, court text or external calls."""

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import nullcontext, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import Mock

from src.annotation import annotate_stj_silver_19c as annotation
from src.annotation import prepare_stj_pilot_19c as preparation
from src.annotation.annotate_role_candidates_qwen import load_local_qwen
from src.data.prepare_stj_corpus_inventory import make_mention, digest


def corpus(count=35):
    rows=[];documents=[];texts={}
    for i in range(count):
        cue=['testemunha','recorrente','arguido','relator','obra','requerente','exemplo'][i%7]
        text='AA '+cue+' '+' '.join('termo'+digest(f'{i}:{n}')[:10] for n in range(12))+'.'
        sha=digest(text)
        doc={'document_id':'doc_'+sha,'source_text_sha256':sha,'characters':len(text),
             'canonical_source':{'source_file':f'invented-{i}.txt','source_document_id':f'invented-{i}.txt'},
             'aliases':[],'split_block_id':f'invented-block-{i}',
             'potential_process_group_ids':[f'{1000+i}/26.1T8XYZ'],
             'requires_identity_review':False,'pilot_related_block':None,
             'gold_known_process_overlap':None,'gold_context_containment_flag':None,
             'reference_checks':{'gold':'not_requested','pilot':'not_requested'}}
        documents.append(doc);texts[doc['document_id']]=text
        rows.append(make_mention(doc,text,0,2,'AA'))
    return rows,documents,texts


def protected():
    return {'gold':[{'id':'invented-gold','text':'ZZ passagem reservada inventada sem outra correspondencia.',
                     'entity':'ZZ','entity_start':0,'entity_end':2,
                     'process_number':'99001/26.1T8ZZZ'}],
            'human_pilot':[{'id':'invented-pilot','text':'YY outra passagem reservada criada apenas para testes.',
                           'entity':'YY','entity_start':0,'entity_end':2,
                           'process_number':'99002/26.1T8ZZZ'}]}


def response(label='TESTEMUNHA'):
    return {'status':'supported','assignments':[{'label':label,'evidence':'explicit',
             'quote':'testemunha','scope':'current_proceeding'}],
            'other_roles':[],'uncertain':False,'uncertainty_reason':''}


class SelectionTests(unittest.TestCase):
    def test_30_reproducible_distinct_groups_preserve_originals_and_hide_cues(self):
        rows,docs,texts=corpus();saved=copy.deepcopy(rows)
        chosen,audit=preparation.select_pilot(rows,docs,texts,protected())
        again,_=preparation.select_pilot(list(reversed(rows)),list(reversed(docs)),texts,protected())
        self.assertEqual(chosen,again);self.assertEqual(rows,saved)
        self.assertEqual(len(chosen),30);self.assertTrue(audit['selection_complete'])
        self.assertEqual(len({r['pilot_selection']['planning_group_id'] for r in chosen}),30)
        self.assertTrue(all(not r['human_validated'] and r['label'] is None for r in chosen))
        for row in chosen:
            original=next(r for r in saved if r['id']==row['id'])
            self.assertTrue(all(row[k]==v for k,v in original.items()))
            self.assertNotIn('suggested_label',row)
            self.assertNotIn('selected_features',row)

    def test_protected_groups_and_related_aliases_cannot_enter(self):
        rows,docs,texts=corpus(5)
        refs=protected();refs['gold'][0]['process_number']=docs[0]['potential_process_group_ids'][0]
        docs[1]['aliases']=[{'decision_id':docs[0]['potential_process_group_ids'][0]+'.S2'}]
        chosen,audit=preparation.select_pilot(rows,docs,texts,refs,count=3)
        self.assertTrue(audit['selection_complete'])
        self.assertFalse({r['document_id']for r in chosen}&{docs[0]['document_id'],docs[1]['document_id']})

    def test_unresolved_references_block_all_not_automatically_clear(self):
        rows,docs,texts=corpus();refs=protected();del refs['gold'][0]['process_number']
        chosen,audit=preparation.select_pilot(rows,docs,texts,refs)
        self.assertEqual(chosen,[]);self.assertEqual(audit['unresolved_references'],['gold:invented-gold'])
        decision={'gold:invented-gold':{'excluded_from_corpus':True,'human_confirmed':True,'reason':'Invented independent source verification.'}}
        # A checkbox/reason alone is no longer sufficient provenance evidence.
        with self.assertRaises(ValueError):
            preparation.select_pilot(rows,docs,texts,refs,decisions=decision)

    def test_manual_resolution_cannot_erase_detected_overlap(self):
        rows,docs,texts=corpus(2);refs=protected();refs['gold'][0]['text']=rows[0]['text']
        decision={'gold:invented-gold':{'excluded_from_corpus':True,'human_confirmed':True,'reason':'Invented conflicting declaration.'}}
        with self.assertRaises(ValueError):preparation.select_pilot(rows,docs,texts,refs,count=1,decisions=decision)

    def test_unknown_identity_and_insufficient_diversity_do_not_force_quotas(self):
        rows,docs,texts=corpus(3);docs[0]['requires_identity_review']=True
        selected,audit=preparation.select_pilot(rows,docs,texts,protected(),count=3)
        self.assertEqual(selected,[]);self.assertFalse(audit['selection_complete'])
        self.assertEqual(audit['exclusion_counts']['identity_unresolved_or_conflicting'],1)

    def test_duplicate_ids_and_preexisting_labels_fail(self):
        rows,docs,texts=corpus(2)
        with self.assertRaises(ValueError):preparation.select_pilot(rows+[rows[0]],docs,texts,protected(),count=1)
        rows[0]['labels']=['ARGUIDO']
        with self.assertRaises(ValueError):preparation.select_pilot(rows,docs,texts,protected(),count=1)


class LoaderTests(unittest.TestCase):
    def test_offline_fp16_loader_reuses_exp17_classes_without_gpu_or_download(self):
        import src.evaluation as package
        torch=SimpleNamespace(cuda=SimpleNamespace(is_available=Mock(return_value=True),manual_seed_all=Mock()),
                              manual_seed=Mock(),backends=SimpleNamespace(cudnn=SimpleNamespace(benchmark=True)),
                              float16='SYNTHETIC_FP16',__version__='synthetic')
        tokenizer=SimpleNamespace(pad_token_id=None,eos_token_id=1,init_kwargs={'_commit_hash':'f'*40},chat_template='synthetic')
        model=SimpleNamespace(config=SimpleNamespace(_commit_hash='f'*40),eval=Mock())
        fake=SimpleNamespace(torch=torch,transformers=SimpleNamespace(__version__='synthetic'),
                             AutoTokenizer=SimpleNamespace(from_pretrained=Mock(return_value=tokenizer)),
                             AutoModelForCausalLM=SimpleNamespace(from_pretrained=Mock(return_value=model)),
                             device_information=Mock(return_value={}))
        with (patch.object(package,'evaluate_qwen3_8b_real_stj',fake,create=True),
              patch.dict('sys.modules',{'src.evaluation.evaluate_qwen3_8b_real_stj':fake}),patch.dict(os.environ,{})):
            _,_,_,environment=load_local_qwen('f'*40,inference_dtype='float16')
            self.assertEqual(os.environ['HF_HUB_OFFLINE'],'1')
            self.assertEqual(os.environ['TRANSFORMERS_OFFLINE'],'1')
        self.assertTrue(fake.AutoTokenizer.from_pretrained.call_args.kwargs['local_files_only'])
        self.assertTrue(fake.AutoModelForCausalLM.from_pretrained.call_args.kwargs['local_files_only'])
        self.assertEqual(fake.AutoModelForCausalLM.from_pretrained.call_args.kwargs['torch_dtype'],'SYNTHETIC_FP16')
        self.assertEqual(environment['resolved_model_revision'],'f'*40)
        model.eval.assert_called_once()


class ProtocolTests(unittest.TestCase):
    text='A testemunha AA, também recorrente, ouviu o advogado BB citar uma obra.'

    def test_prompt_target_only_and_exact_offsets(self):
        row=corpus(1)[0][0]
        messages=annotation.build_messages(row)
        self.assertEqual(messages[1]['content'], '[ENTITY] AA [/ENTITY]'+row['text'][2:])
        self.assertNotIn(row['document_id'],str(messages))
        for update in ({'entity_start':True},{'entity_end':999},{'entity':'BB'},{'suggested_label':'REU'}):
            with self.assertRaises((ValueError,TypeError)):annotation.build_messages({**row,**update})

    def test_multiple_roles_and_reference_are_main_labels(self):
        obj=response();obj['assignments'].append({'label':'RECORRENTE','evidence':'inferred',
                                                 'quote':'recorrente','scope':'cited_proceeding'})
        self.assertEqual(annotation.parse_response(json.dumps(obj),self.text)[1],[])
        obj=response('REFERENCE');obj['assignments'][0].update(quote='obra',scope='not_applicable')
        self.assertEqual(annotation.parse_response(json.dumps(obj),self.text)[1],[])

    def test_unknown_and_literal_out_of_scope_role_preserved(self):
        obj=response('UNKNOWN');obj['assignments'][0].update(evidence='not_applicable',quote='',scope='not_applicable')
        obj['other_roles']=[{'role':'advogado','evidence':'explicit','quote':'advogado BB','scope':'current_proceeding'}]
        self.assertEqual(annotation.parse_response(json.dumps(obj),self.text)[1],[])
        obj['uncertain']=True;obj['uncertainty_reason']='Invented uncertainty.'
        self.assertIn('unknown_is_not_uncertainty',annotation.parse_response(json.dumps(obj),self.text)[1])

    def test_invalid_labels_quotes_incomplete_and_duplicate_json_fail(self):
        for raw in ('{"status":"supported"}', '```json\n{}\n```','{"status":0,"status":1}', 'NaN'):
            self.assertTrue(annotation.parse_response(raw,self.text)[1])
        for update in ({'label':'FAKE'},{'quote':'Evidence not present.'},{'scope':'invented'},{'evidence':'invented'}):
            obj=response();obj['assignments'][0].update(update)
            self.assertTrue(annotation.parse_response(json.dumps(obj),self.text)[1])
        obj=response();obj['assignments']*=2
        self.assertIn('duplicate_role',annotation.parse_response(json.dumps(obj),self.text)[1])

    def test_abstention_and_token_limit_do_not_become_unknown_or_gold(self):
        row=corpus(1)[0][0];obj=response()
        obj.update(status='insufficient',assignments=[],uncertain=True,uncertainty_reason='Not enough context.')
        result=annotation.proposal(row,json.dumps(obj),{})
        self.assertEqual(result['proposed_labels'],[]);self.assertFalse(result['human_validated'])
        self.assertEqual(result['annotation_tier'],'SILVER');self.assertIsNone(result['label'])
        result=annotation.proposal(row,json.dumps(response()),{},'generation_token_limit_reached')
        self.assertFalse(result['llm_output_valid']);self.assertEqual(result['proposed_labels'],[])

    def test_scope_uncertainty_and_invented_other_role_fail(self):
        obj=response();obj['assignments'][0]['scope']='uncertain'
        self.assertIn('uncertain_scope_not_flagged',annotation.parse_response(json.dumps(obj),self.text)[1])
        obj=response();obj['other_roles']=[{'role':'invented_role','evidence':'explicit','quote':'testemunha','scope':'current_proceeding'}]
        self.assertIn('invalid_role',annotation.parse_response(json.dumps(obj),self.text)[1])


class PilotBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.input=self.root/'pilot_input.jsonl';self.selection=self.root/'selection_manifest.json'
        rows,docs,texts=corpus();self.rows,audit=preparation.select_pilot(rows,docs,texts,protected())
        inventory={'summary':{'inventory_complete':True,'NER_executed':True,'unique_texts':len(docs),
                              'total_PER_mentions_complete':len(rows)},
                   'source_inventory':{'directory':str(self.root)},'input_files':{},'inputs_sha256':{}}
        for i,doc in enumerate(docs):
            source=self.root/doc['canonical_source']['source_file']
            source.write_text(texts[doc['document_id']],encoding='utf-8')
            sha=preparation.file_hash(source)
            inventory['input_files'][f'source_{i}']={'path':str(source),'sha256':sha}
            inventory['inputs_sha256'][f'source_{i}']=sha
        predictions=[{'document_id':r['document_id'],'start':r['entity_document_start'],'end':r['entity_document_end'],
                      'ner_label':'PER','accepted_PER':True,'offsets_valid':True,'mention_id':r['id'],
                      **{k:r[k]for k in ('entity','text','entity_start','entity_end','context_document_start','context_document_end','context_id')}}for r in rows]
        for suffix,values in [('mentions',rows),('documents',docs),('ner_predictions',predictions)]:
            (self.root/f'inventory_{suffix}.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in values),encoding='utf-8')
        inventory_path=self.root/'inventory_manifest.json'
        inventory_path.write_text(json.dumps(inventory),encoding='utf-8')
        _,_,_,binding=preparation.load_bound_inventory(self.root/'inventory_mentions.jsonl',inventory_path)
        for key,values in protected().items():
            source=self.root/f'{key}.jsonl';source.write_text(''.join(json.dumps(r)+'\n'for r in values),encoding='utf-8')
            binding[key]={'path':str(source),'sha256':preparation.file_hash(source)}
        self.input.write_text(''.join(json.dumps(r)+'\n'for r in self.rows),encoding='utf-8')
        self.audit={**audit,'cohort':preparation.COHORT,'validated_bundle':binding,'pilot_input_sha256':preparation.file_hash(self.input)}
        self.write_manifest()

    def write_manifest(self):self.selection.write_text(json.dumps(self.audit),encoding='utf-8')

    def test_input_hash_id_list_and_distinct_groups_are_required(self):
        self.assertEqual(len(annotation.load_pilot(self.input,self.selection)),30)
        self.audit['selected_ids'][0]='wrong';self.write_manifest()
        with self.assertRaises(ValueError):annotation.load_pilot(self.input,self.selection)
        self.audit['selected_ids']=[r['id']for r in self.rows]
        self.audit['unresolved_references']=['invented-unresolved'];self.write_manifest()
        with self.assertRaises(ValueError):annotation.load_pilot(self.input,self.selection)

    def test_no_inference_outside_slurm(self):
        with (patch.dict(os.environ,{},clear=True),patch('sys.argv',['annotate','--input',str(self.input),
             '--selection-manifest',str(self.selection),'--run-dir',str(self.root/'out'),'--revision','f'*40]),
             patch.object(annotation,'load_local_qwen')as loader,redirect_stderr(io.StringIO())):
            with self.assertRaises(SystemExit):annotation.main()
            loader.assert_not_called()

    def test_mocked_gpu_preflight_then_30_predictions_without_real_model(self):
        class Tensor:
            def __init__(self,n):self.shape=(1,n)
            def __getitem__(self,key):return Tensor(self.shape[1]-(key[1].start or 0))
        class Inputs(dict):
            def to(self,_):return self
        obj=response('UNKNOWN');obj['assignments'][0].update(evidence='not_applicable',quote='',scope='not_applicable')
        class Tokenizer:
            pad_token_id=0;eos_token_id=1
            def __call__(self,*args,**kwargs):
                assert kwargs['truncation'] is False
                return Inputs(input_ids=Tensor(100))
            def batch_decode(self,*args,**kwargs):return [json.dumps(obj)]
        model=SimpleNamespace(config=SimpleNamespace(max_position_embeddings=8192),generate=Mock(return_value=Tensor(107)))
        exp17=SimpleNamespace(render_prompt=lambda tokenizer,messages:'synthetic prompt',model_input_device=lambda model:'cuda:0',
                              torch=SimpleNamespace(inference_mode=nullcontext))
        env={'resolved_model_revision':'f'*40,'torch':'synthetic','transformers':'synthetic',
             'tokenizer_commit':'f'*40,'chat_template_sha256':'synthetic'}
        base=['annotate','--input',str(self.input),'--selection-manifest',str(self.selection),'--revision','f'*40]
        with (patch.dict(os.environ,{'SLURM_JOB_ID':'synthetic','CUDA_VISIBLE_DEVICES':'0'}),
              patch.object(annotation,'private_new_output',side_effect=lambda p:p),
              patch.object(annotation,'load_local_qwen',return_value=(model,Tokenizer(),exp17,env))as loader,
              patch('builtins.print')):
            preflight=self.root/'preflight'
            with patch('sys.argv',base+['--run-dir',str(preflight),'--preflight-only']):annotation.main()
            self.assertEqual(json.loads((preflight/'run.json').read_text())['status'],'preflight_passed')
            model.generate.assert_not_called()
            output=self.root/'pilot'
            with patch('sys.argv',base+['--run-dir',str(output),'--preflight-run',str(preflight/'run.json')]):annotation.main()
            self.assertEqual(model.generate.call_count,30)
            self.assertEqual(json.loads((output/'run.json').read_text())['status'],'completed')
            results=[json.loads(line)for line in (output/'silver_predictions.jsonl').read_text().splitlines()]
            self.assertEqual([r['id']for r in results],[r['id']for r in self.rows])
            self.assertTrue(all(r['llm_output_valid']and not r['human_validated']for r in results))
            self.assertEqual(loader.call_args.kwargs['inference_dtype'],'float16')

    def test_missing_binding_is_rejected(self):
        self.audit['validated_bundle']={};self.write_manifest()
        with self.assertRaisesRegex(ValueError,'incomplete_pilot_source_binding'):
            annotation.load_pilot(self.input,self.selection)

    def test_failed_preflight_cannot_start_model(self):
        failed=self.root/'failed.json';failed.write_text(json.dumps({'status':'failed','configuration':{}}))
        argv=['annotate','--input',str(self.input),'--selection-manifest',str(self.selection),
              '--run-dir',str(self.root/'out'),'--revision','f'*40,'--preflight-run',str(failed)]
        with (patch.dict(os.environ,{'SLURM_JOB_ID':'synthetic','CUDA_VISIBLE_DEVICES':'0'}),
              patch('sys.argv',argv),patch.object(annotation,'private_new_output',side_effect=lambda p:p),
              patch.object(annotation,'load_local_qwen')as loader,redirect_stderr(io.StringIO())):
            with self.assertRaises(SystemExit):annotation.main()
            loader.assert_not_called()


if __name__=='__main__':unittest.main()
