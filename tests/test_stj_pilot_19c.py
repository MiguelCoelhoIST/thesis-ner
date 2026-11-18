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
from src.annotation import revalidate_stj_silver_19c as revalidation
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


class EvidenceRecoveryTests(unittest.TestCase):
    def test_recovers_literal_source_and_audits_context_offsets(self):
        text = 'A testemunha\nAA prestou declarações.'
        obj = response()
        obj['assignments'][0]['quote'] = 'testemunha [ENTITY] AA [/ENTITY]'
        raw = json.dumps(obj)
        derived, repairs = revalidation.recover_evidence(raw, text)
        self.assertEqual(json.loads(raw), obj)
        self.assertEqual(json.loads(derived)['assignments'][0]['quote'], 'testemunha\nAA')
        self.assertEqual(annotation.parse_response(derived, text)[1], [])
        self.assertEqual(len(repairs), 1)
        repair = repairs[0]
        self.assertEqual(text[repair['context_start']:repair['context_end']], repair['source_quote'])
        self.assertEqual(repair['original_quote'], obj['assignments'][0]['quote'])

    def test_adjacent_markers_unicode_whitespace_and_multiple_roles_preserve_offsets(self):
        text = 'AA\u00a0testemunha e recorrente\r\nBB.'
        obj = response()
        obj['assignments'][0]['quote'] = '[ENTITY]AA[/ENTITY] testemunha'
        obj['assignments'].append({'label':'RECORRENTE', 'evidence':'inferred',
                                   'quote':'recorrente [ENTITY]BB[/ENTITY]', 'scope':'cited_proceeding'})
        derived, repairs = revalidation.recover_evidence(json.dumps(obj), text)
        self.assertEqual(annotation.parse_response(derived, text)[1], [])
        self.assertEqual(len(repairs), 2)
        for repair in repairs:
            self.assertEqual(text[repair['context_start']:repair['context_end']], repair['source_quote'])
        self.assertEqual(json.loads(derived)['assignments'][1]['scope'], 'cited_proceeding')

    def test_existing_exact_evidence_is_unchanged_even_with_repeated_occurrences(self):
        raw = json.dumps(response())
        self.assertEqual(revalidation.recover_evidence(raw, 'testemunha e testemunha'), (raw, []))

    def test_repeated_and_overlapping_normalized_matches_are_rejected(self):
        for quote, text in (('[ENTITY] AA [/ENTITY] a', 'AA\na AA a'),
                            ('[ENTITY] aa [/ENTITY]', 'aaa')):
            obj = response()
            obj['assignments'][0]['quote'] = quote
            raw = json.dumps(obj)
            self.assertEqual(revalidation.recover_evidence(raw, text), (raw, []))

    def test_paraphrase_punctuation_case_accents_and_overlong_source_are_rejected(self):
        for quote, text in (('a testemunha', 'A testemunha'),
                            ('testemunha AA', 'testemunha, AA'),
                            ('Joao testemunha', 'João testemunha'),
                            ('testemunha AA', 'testemunha' + ' ' * 241 + 'AA'),
                            ('ouviu a testemunha', 'escutou a testemunha'),
                            ('[ENTITY] [/ENTITY]', 'testemunha AA')):
            obj = response()
            obj['assignments'][0]['quote'] = quote
            raw = json.dumps(obj)
            self.assertEqual(revalidation.recover_evidence(raw, text), (raw, []))

    def test_duplicates_scope_and_invalid_role_still_fail_after_evidence_recovery(self):
        obj = response('FAKE')
        obj['assignments'][0].update(quote='testemunha [ENTITY] AA [/ENTITY]', scope='not_applicable')
        obj['assignments'] *= 2
        derived, repairs = revalidation.recover_evidence(json.dumps(obj), 'testemunha\nAA')
        errors = annotation.parse_response(derived, 'testemunha\nAA')[1]
        self.assertEqual(len(repairs), 2)
        self.assertEqual(set(errors), {'invalid_role', 'duplicate_role', 'scope_category_mismatch'})

    def test_invalid_json_schema_and_unknown_are_preserved(self):
        unknown = response('UNKNOWN')
        unknown['assignments'][0].update(evidence='not_applicable', scope='not_applicable', quote='')
        for raw in ('not JSON', '{"status":1,"status":2}', '{}', json.dumps(unknown)):
            self.assertEqual(revalidation.recover_evidence(raw, 'AA'), (raw, []))

    def test_other_roles_are_recovered_without_changing_the_role_designation(self):
        obj = response('UNKNOWN')
        obj['assignments'][0].update(evidence='not_applicable', scope='not_applicable', quote='')
        obj['other_roles'] = [{'role':'advogado', 'evidence':'explicit',
                              'quote':'advogado [ENTITY] AA [/ENTITY]', 'scope':'current_proceeding'}]
        derived, repairs = revalidation.recover_evidence(json.dumps(obj), 'O advogado\nAA respondeu.')
        self.assertEqual(annotation.parse_response(derived, 'O advogado\nAA respondeu.')[1], [])
        self.assertEqual(repairs[0]['field'], 'other_roles')
        self.assertEqual(json.loads(derived)['other_roles'][0]['role'], 'advogado')

    def test_token_limit_failure_is_preserved_and_raw_output_is_never_replaced(self):
        record = corpus(1)[0][0]
        obj = response()
        obj['assignments'][0]['quote'] = '[ENTITY] AA [/ENTITY]'
        raw = json.dumps(obj)
        prediction = annotation.proposal(record, raw, {}, 'generation_token_limit_reached')
        result = revalidation.revalidate_prediction(record, prediction, {})
        self.assertEqual(result['parsing_errors'], ['generation_token_limit_reached'])
        self.assertEqual(result['evidence_revalidation']['repairs'], [])
        self.assertEqual(result['llm_raw_output'], raw)
        self.assertFalse(result['human_validated'])
        self.assertTrue(result['requires_review'])


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

    def write_saved_pilot(self):
        configuration = {
            'input_sha256':annotation.file_hash(self.input),
            'selection_sha256':annotation.file_hash(self.selection),
            'prompt_sha256':annotation.file_hash(annotation.PROMPT_PATH),
            'taxonomy_sha256':annotation.file_hash(annotation.TAXONOMY),
            'script_sha256':annotation.file_hash(Path(annotation.__file__)),
            'loader_sha256':annotation.file_hash(annotation.ROOT/'src/annotation/annotate_role_candidates_qwen.py'),
        }
        unknown = response('UNKNOWN')
        unknown['assignments'][0].update(evidence='not_applicable', quote='', scope='not_applicable')
        rows = [annotation.proposal(row, json.dumps(unknown), configuration) for row in self.rows]
        marked = response()
        marked['assignments'][0]['quote'] = '[ENTITY] AA [/ENTITY]'
        rows[0] = annotation.proposal(self.rows[0], json.dumps(marked), configuration)
        rows[0]['historical_extra_metadata'] = {'generated_tokens':35}
        source = self.root/'saved_pilot'
        source.mkdir()
        predictions = source/'silver_predictions.jsonl'
        predictions.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
        run = {'configuration':configuration, 'status':'completed_with_invalid_outputs',
               'predictions_sha256':annotation.file_hash(predictions), 'input_unchanged':True,
               'selection_unchanged':True, 'summary':annotation.aggregate(rows),
               'Slurm_job_id':'invented-job', 'elapsed_seconds':1.25,
               'environment':{'device':'invented-device'}, 'input_token_counts':[100]*30}
        (source/'run.json').write_text(json.dumps(run), encoding='utf-8')
        return source, rows

    def test_offline_revalidation_preserves_sources_raw_offsets_and_training_status(self):
        source, rows = self.write_saved_pilot()
        output = self.root/'revalidated'
        tracked = [self.input, self.selection, source/'run.json', source/'silver_predictions.jsonl']
        saved = {path:path.read_bytes() for path in tracked}
        with (patch.object(revalidation, 'private_new_output', side_effect=lambda path:path),
              patch.object(annotation, 'load_local_qwen', side_effect=AssertionError('Model must stay unloaded'))):
            report = revalidation.revalidate_run(self.input, self.selection, source, output)
        self.assertEqual(report['original_summary']['valid_outputs'], 29)
        self.assertEqual(report['summary']['valid_outputs'], 30)
        self.assertEqual(report['repaired_evidence_count'], 1)
        self.assertEqual(report['LLM_calls'], 0)
        self.assertEqual(report['original_run'], json.loads((source/'run.json').read_text()))
        self.assertEqual(report['training_eligibility'], 'NOT_ESTABLISHED')
        results = [json.loads(line) for line in (output/'silver_predictions.jsonl').read_text().splitlines()]
        for original, prediction, result in zip(self.rows, rows, results):
            self.assertTrue(all(result[key] == value for key, value in original.items()
                                if key != 'annotation_tier'))
            self.assertEqual(result['llm_raw_output'], prediction['llm_raw_output'])
            self.assertEqual(result['llm_config'], prediction['llm_config'])
            self.assertFalse(result['human_validated'])
            self.assertTrue(result['requires_review'])
            self.assertEqual(result['pilot_selection']['training_eligibility'], 'NOT_ESTABLISHED')
        self.assertEqual(saved, {path:path.read_bytes() for path in tracked})
        self.assertEqual(report['predictions_sha256'], annotation.file_hash(output/'silver_predictions.jsonl'))
        self.assertEqual(results[0]['historical_extra_metadata'], rows[0]['historical_extra_metadata'])
        for result, prediction in zip(results, rows):
            audit = result['evidence_revalidation']
            self.assertEqual(audit['source_prediction_sha256'], revalidation.fingerprint(prediction))
            self.assertEqual(annotation.parse_response(audit['validation_input'], result['text'])[0], result['llm_response'])

    def test_revalidation_checks_loader_status_missing_metadata_and_json_types(self):
        source, rows = self.write_saved_pilot()
        run_path = source/'run.json';predictions_path = source/'silver_predictions.jsonl'
        saved_run = json.loads(run_path.read_text())
        for mutation in ('loader', 'status', 'missing_null', 'boolean_as_integer', 'duplicate_id'):
            with self.subTest(mutation=mutation):
                run = copy.deepcopy(saved_run);changed = copy.deepcopy(rows)
                if mutation == 'loader':
                    run['configuration']['loader_sha256'] = '0'*64
                    for row in changed:row['llm_config'] = run['configuration']
                if mutation == 'status':run['status'] = 'completed'
                if mutation == 'missing_null':del changed[0]['label']
                if mutation == 'boolean_as_integer':changed[0]['human_validated'] = 0
                if mutation == 'duplicate_id':changed[1]['id'] = changed[0]['id']
                predictions_path.write_text(''.join(json.dumps(row)+'\n' for row in changed), encoding='utf-8')
                run['predictions_sha256'] = annotation.file_hash(predictions_path)
                run_path.write_text(json.dumps(run), encoding='utf-8')
                output = self.root/('revalidate_'+mutation)
                with patch.object(revalidation,'private_new_output',side_effect=lambda path:path),self.assertRaises(ValueError):
                    revalidation.revalidate_run(self.input,self.selection,source,output)
                self.assertFalse(output.exists())

    def test_revalidation_rejects_duplicate_json_keys_and_nonfinite_metadata(self):
        source, rows = self.write_saved_pilot()
        run_path = source/'run.json';predictions_path = source/'silver_predictions.jsonl'
        saved_run = json.loads(run_path.read_text())
        original_predictions = predictions_path.read_text()
        for mutation in ('run_duplicate_key', 'prediction_duplicate_key', 'nonfinite_metadata'):
            with self.subTest(mutation=mutation):
                run = copy.deepcopy(saved_run);content = original_predictions
                if mutation == 'prediction_duplicate_key':
                    content = content.replace('{', '{"id":'+json.dumps(rows[0]['id'])+',',1)
                if mutation == 'nonfinite_metadata':run['elapsed_seconds'] = float('nan')
                predictions_path.write_text(content, encoding='utf-8')
                run['predictions_sha256'] = annotation.file_hash(predictions_path)
                serialized = json.dumps(run)
                if mutation == 'run_duplicate_key':serialized = '{"configuration":{},'+serialized[1:]
                run_path.write_text(serialized, encoding='utf-8')
                output = self.root/('revalidate_'+mutation)
                with patch.object(revalidation,'private_new_output',side_effect=lambda path:path),self.assertRaises(ValueError):
                    revalidation.revalidate_run(self.input,self.selection,source,output)
                self.assertFalse(output.exists())

    def test_revalidation_does_not_establish_training_eligibility(self):
        self.rows[0]['pilot_selection']['training_eligibility'] = 'ELIGIBLE'
        self.input.write_text(''.join(json.dumps(row)+'\n' for row in self.rows), encoding='utf-8')
        self.audit['pilot_input_sha256'] = annotation.file_hash(self.input);self.write_manifest()
        source,_ = self.write_saved_pilot();output = self.root/'training_revalidation'
        with (patch.object(revalidation,'private_new_output',side_effect=lambda path:path),
              self.assertRaisesRegex(ValueError,'pilot_review_status_mismatch')):
            revalidation.revalidate_run(self.input,self.selection,source,output)
        self.assertFalse(output.exists())

    def test_revalidation_detects_source_changes_during_processing_before_writing(self):
        source,_ = self.write_saved_pilot();output = self.root/'changed_during_revalidation'
        original = revalidation.recover_evidence
        def recover_and_change(raw,text):
            path = source/'run.json'
            path.write_text(path.read_text()+' ',encoding='utf-8')
            return original(raw,text)
        with (patch.object(revalidation,'private_new_output',side_effect=lambda path:path),
              patch.object(revalidation,'recover_evidence',side_effect=recover_and_change),
              self.assertRaisesRegex(ValueError,'revalidation_source_changed')):
            revalidation.revalidate_run(self.input,self.selection,source,output)
        self.assertFalse(output.exists())

    def test_revalidation_cli_errors_do_not_expose_private_values(self):
        source,_ = self.write_saved_pilot();output = self.root/'failed_private_cli'
        path = source/'run.json'
        run = json.loads(path.read_text());run['status'] = 'invented-private-status'
        path.write_text(json.dumps(run),encoding='utf-8')
        argv = ['revalidate','--input',str(self.input),'--selection-manifest',str(self.selection),
                '--source-run-dir',str(source),'--output-dir',str(output)]
        stderr = io.StringIO()
        with (patch('sys.argv',argv),redirect_stderr(stderr),
              patch.object(revalidation,'private_new_output',side_effect=lambda path:path),
              self.assertRaises(SystemExit)):
            previous_umask = os.umask(0o077)
            try:revalidation.main()
            finally:os.umask(previous_umask)
        error = json.loads(stderr.getvalue())
        self.assertEqual(error['error_code'],'completed_pilot_required')
        self.assertNotIn('invented-private-status',stderr.getvalue())
        self.assertNotIn(str(source),stderr.getvalue())
        self.assertFalse(output.exists())

    def test_revalidation_rejects_changed_bindings_ids_and_validation_metadata(self):
        source, rows = self.write_saved_pilot()
        run_path = source/'run.json'
        predictions_path = source/'silver_predictions.jsonl'
        saved_run = json.loads(run_path.read_text())
        for mutation in ('hash', 'id', 'context', 'human_validation', 'configuration', 'summary', 'raw', 'protection'):
            with self.subTest(mutation=mutation):
                run = copy.deepcopy(saved_run)
                changed = copy.deepcopy(rows)
                if mutation == 'id':changed[0]['id'] = 'invented-wrong-id'
                if mutation == 'context':changed[0]['text'] += ' changed'
                if mutation == 'human_validation':changed[0]['human_validated'] = True
                if mutation == 'configuration':changed[0]['llm_config'] = {}
                if mutation == 'summary':run['summary']['valid_outputs'] = 30
                if mutation == 'raw':changed[0]['llm_raw_output'] = '{}'
                if mutation == 'protection':
                    self.audit['unresolved_references'] = ['invented-pending']
                    self.write_manifest()
                    run['configuration']['selection_sha256'] = annotation.file_hash(self.selection)
                    for row in changed:row['llm_config'] = run['configuration']
                predictions_path.write_text(''.join(json.dumps(row)+'\n' for row in changed), encoding='utf-8')
                run['predictions_sha256'] = annotation.file_hash(predictions_path)
                if mutation == 'hash':run['predictions_sha256'] = '0'*64
                run_path.write_text(json.dumps(run), encoding='utf-8')
                output = self.root/('revalidated_'+mutation)
                with patch.object(revalidation, 'private_new_output', side_effect=lambda path:path):
                    with self.assertRaises(ValueError):
                        revalidation.revalidate_run(self.input, self.selection, source, output)
                self.assertFalse(output.exists())

    def test_revalidation_cli_prints_only_aggregates_and_refuses_existing_outputs(self):
        source, _ = self.write_saved_pilot()
        output = self.root/'cli_revalidation'
        argv = ['revalidate', '--input', str(self.input), '--selection-manifest', str(self.selection),
                '--source-run-dir', str(source), '--output-dir', str(output)]
        stdout = io.StringIO()
        from contextlib import redirect_stdout
        with (patch('sys.argv', argv), patch.object(revalidation, 'private_new_output', side_effect=lambda path:path),
              redirect_stdout(stdout), patch.dict(os.environ, {}, clear=True)):
            previous_umask = os.umask(0o077)
            try:
                revalidation.main()
            finally:
                os.umask(previous_umask)
        printed = json.loads(stdout.getvalue())
        self.assertEqual(printed['summary']['records'], 30)
        self.assertNotIn('AA', stdout.getvalue())
        self.assertNotIn('original_quote', stdout.getvalue())
        with (patch('src.annotation.prepare_role_annotation_batch.RAW', self.root),
              self.assertRaisesRegex(ValueError, 'NEW files')):
            revalidation.revalidate_run(self.input, self.selection, source, output)

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
