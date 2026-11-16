"""Synthetic full-corpus preparation tests; never loads a model or real text."""

import copy
import json
import tempfile
import hashlib
import unittest
from pathlib import Path
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

from src.data import prepare_stj_corpus_inventory as inventory

from src.data.prepare_stj_corpus_inventory import (
    build_documents, digest, full_windows, known_mentions, make_mention, union_length,
    recover_saved_context_ner,
)
from src.data.extract_role_candidates_v2 import detect_person_spans


def fixture():
    text = 'AA chegou. AA saiu.'
    aliases = []
    for filename, group in [('invented-a.txt', '101/26.1T8XYZ'), ('invented-b.txt', '102/26.1T8XYZ')]:
        aliases.append({'source_file':filename,'source_document_id':filename,
                        'source_text_sha256':digest(text),'decision_id':group+'.S1',
                        'decision_id_candidates':[group+'.S1'],'process_group_id':group,
                        'process_group_id_candidates':[group],
                        'process_provenance':{'status':'header_only'}})
    profiles = [{'source_file':r['source_file'],'source_document_id':r['source_document_id'],
                 'characters':len(text),'ner_window_ranges':[[0,5]],'process_number':r['process_group_id']} for r in aliases]
    audit={'document_provenance':aliases,'document_profiles':profiles}
    texts={(r['source_file'],r['source_document_id']):text for r in aliases}
    return text,audit,texts


class CorpusInventoryTests(unittest.TestCase):
    def exercise_clean_source_cli(self, smoke):
        """Real source-reader path: no audit, candidates, pilot or gold exists."""
        class FakeNLP:
            def pipe(self,items,batch_size,n_process):
                for text in items:
                    yield SimpleNamespace(ents=[SimpleNamespace(start_char=a,end_char=a+2,text='AA',label_='PER')for a in(0,11)])
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);source=root/'source';source.mkdir();(root/'results').mkdir()
            (root/'src/data').mkdir(parents=True)
            (root/'src/data/extract_role_candidates_v2.py').write_text('# Synthetic source fixture.\n',encoding='utf-8')
            for i in range(191):
                text=f'AA chegou. AA saiu. Documento inventado {i}.'
                for suffix in('a','b'):
                    (source/f'invented-{i:03}-{suffix}.txt').write_text(text,encoding='utf-8')
                if i<6:(source/f'invented-{i:03}-c.txt').write_text(text,encoding='utf-8')
            (source/'non-document.json').write_text('{}',encoding='utf-8')
            (source/'editor.swp').write_text('not a judgment',encoding='utf-8')
            prefix=root/'execution'
            argv=['inventory','--input-dir',str(source),'--prefix',str(prefix),
                  '--report',str(root/'results/run.md'),'--run-ner','--expected-unique-documents','191']
            if smoke:argv+=['--max-documents','3']
            with patch.object(inventory,'ROOT',root),patch.object(inventory,'private_new_output',side_effect=lambda p:p),patch.object(inventory,'load_person_ner',return_value=FakeNLP())as loader,patch.object(inventory,'refine_transformer_windows',wraps=inventory.refine_transformer_windows)as preflight,patch('sys.argv',argv),patch('builtins.print'):
                inventory.main()
            self.assertEqual(loader.call_count,1)
            # Even smoke inference of three documents checks every source text,
            # including difficult inputs outside the selected smoke subset.
            self.assertEqual(preflight.call_count,191)
            self.assertEqual(len({call.args[0]for call in preflight.call_args_list}),191)
            manifest=json.loads(Path(str(prefix)+'_manifest.json').read_text(encoding='utf-8'))
            summary=manifest['summary']
            self.assertEqual(summary['audited_documents'],388)
            self.assertEqual(summary['unique_texts'],191)
            self.assertEqual(summary['NER_documents_processed'],3 if smoke else 191)
            self.assertEqual(summary['accepted_mentions_this_run'],6 if smoke else 382)
            self.assertEqual(summary['inventory_complete'],not smoke)
            self.assertEqual(summary['source_mode'],'original_documents')
            self.assertEqual(summary['source_files_skipped_by_reason'],{'no_extractable_document_text':1,'unsupported_extension':1})
            self.assertEqual(summary['reference_checks'],{'pilot':'not_requested','gold':'not_requested'})
            self.assertIsNone(summary['gold_known_process_overlap_documents'])
            self.assertFalse({'audit','candidates','pilot','gold'} & manifest['input_files'].keys())
            self.assertEqual(len(manifest['input_files']),390) # taxonomy + 388 texts + explicit non-document JSON
            docs=[json.loads(l)for l in Path(str(prefix)+'_documents.jsonl').read_text().splitlines()]
            self.assertEqual(sum(len(d['aliases'])for d in docs),388)
            self.assertTrue(all(d['pilot_related_block']is None and d['gold_known_process_overlap']is None for d in docs))
            self.assertFalse(Path(str(prefix)+'_known_mentions_PARTIAL.jsonl').exists())
            for line in Path(str(prefix)+'_mentions.jsonl').read_text().splitlines():
                row=json.loads(line)
                self.assertEqual(row['text'][row['entity_start']:row['entity_end']],row['entity'])
                self.assertNotIn('suggested_label',row)
                self.assertFalse(row['human_validated'])
            self.assertFalse((root/'data/raw/experiment_19a_candidates_v4_smoke10.jsonl').exists())

    def test_clean_checkout_smoke_needs_only_original_sources_and_config(self):
        self.exercise_clean_source_cli(True)

    def test_clean_checkout_full_needs_only_original_sources_and_config(self):
        self.exercise_clean_source_cli(False)

    def test_explicit_missing_optional_references_are_errors_not_ignored(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);(root/'results').mkdir();source=root/'source';source.mkdir()
            (source/'invented.txt').write_text('AA chegou.',encoding='utf-8')
            for option in('--audit','--candidates','--pilot','--gold','--reuse-privacy-map','--taxonomy-config'):
                with self.subTest(option=option):
                    argv=['inventory','--input-dir',str(source),'--prefix',str(root/'outputs'),
                          '--report',str(root/'results/run.md'),'--run-ner',option,str(root/'missing.json')]
                    with patch.object(inventory,'ROOT',root),patch.object(inventory,'private_new_output',side_effect=lambda p:p),patch.object(inventory,'load_person_ner')as loader,patch('sys.argv',argv):
                        with self.assertRaises(FileNotFoundError):inventory.main()
                        loader.assert_not_called()
            with self.assertRaises(FileNotFoundError):inventory.load_source_corpus(root/'missing-corpus')

    def test_unreadable_or_empty_source_documents_fail_instead_of_being_skipped(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);path=root/'invented.txt';path.write_bytes(b'\xff\xfe')
            with self.assertRaises(UnicodeError):inventory.load_source_corpus(root)
            path.write_text('',encoding='utf-8')
            with self.assertRaises(ValueError):inventory.load_source_corpus(root)

    def test_reuses_saved_ner_without_anchors_or_duplicate_occurrences(self):
        text,audit,texts=fixture();docs=build_documents(audit,texts);doc=docs[0];sha=digest(text)
        known=[make_mention(doc,text,0,2,'AA')]
        source={**known[0],'entity_start':0,'text':text}
        cache={'records':[{'export_id':'EXEMPLO_001','original_record':source,'ner_spans':[
            {'start':0,'end':2,'label':'PER'},{'start':11,'end':13,'label':'PER'},
            {'start':3,'end':9,'label':'ORG'}]}]}
        recovered,log,stats=recover_saved_context_ner(known,docs,{sha:text},cache)
        self.assertEqual(len(recovered),2)
        self.assertEqual(stats['new_cached_occurrences'],1)
        again,_,stats=recover_saved_context_ner(recovered,docs,{sha:text},cache)
        self.assertEqual(len(again),2)
        self.assertEqual(stats['new_cached_occurrences'],0)
        self.assertTrue(all('suggested_label'not in row for row in again))

    def test_saved_overlap_is_reviewed_not_recounted(self):
        text,audit,texts=fixture();docs=build_documents(audit,texts);sha=digest(text)
        row=make_mention(docs[0],text,0,2,'AA');source={**row,'text':text}
        cache={'records':[{'export_id':'EXEMPLO_001','original_record':source,
                           'ner_spans':[{'start':0,'end':5,'label':'PER'}]}]}
        recovered,log,_=recover_saved_context_ner([row],docs,{sha:text},cache)
        self.assertEqual(len(recovered),1)
        self.assertEqual(log[0]['recovery_status'],'overlapping_variant_needs_review')

    def test_changed_cached_context_fails_closed(self):
        text,audit,texts=fixture();docs=build_documents(audit,texts);sha=digest(text)
        source={**make_mention(docs[0],text,0,2,'AA'),'text':'Changed synthetic context'}
        with self.assertRaises(ValueError):recover_saved_context_ner([],docs,{sha:text},{'records':[{'original_record':source}]})

    def exercise_cli(self, run_ner):
        text,audit,_=fixture()
        audit['ner_span_counts']={'accepted_per_spans':4}
        class FakeNLP:
            def pipe(self,items,batch_size,n_process):
                for value in items:
                    yield SimpleNamespace(ents=[SimpleNamespace(start_char=a,end_char=a+2,text='AA',label_='PER') for a in (0,11)]+
                                          [SimpleNamespace(start_char=0,end_char=2,text='BB',label_='PER')])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir();(root/'results').mkdir()
            (root/'src/data').mkdir(parents=True)
            (root/'src/data/extract_role_candidates_v2.py').write_text('# Synthetic fingerprint fixture only.\n',encoding='utf-8')
            for alias in audit['document_provenance']:(source/alias['source_file']).write_text(text,encoding='utf-8')
            for name,value in [('audit',audit),('candidates',[]),('pilot',[]),('gold',[])]:
                path=root/(name+'.json')
                path.write_text(json.dumps(value) if name=='audit' else '',encoding='utf-8')
            prefix=root/'plan'
            argv=['inventory','--input-dir',str(source),'--prefix',str(prefix),'--report',str(root/'results/report.md')]
            for name in ('audit','candidates','pilot','gold'):argv+=['--'+name,str(root/(name+'.json'))]
            if run_ner:argv+=['--run-ner']
            with patch.object(inventory,'ROOT',root),patch.object(inventory,'private_new_output',side_effect=lambda p:p),patch.object(inventory,'load_person_ner',return_value=FakeNLP()) as loader,patch('sys.argv',argv),patch('builtins.print'):
                inventory.main()
            manifest=json.loads(Path(str(prefix)+'_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(loader.call_count,int(run_ner))
            self.assertEqual(manifest['summary']['unique_texts'],1)
            self.assertTrue(Path(str(prefix)+'_task.json').is_file())
            if run_ner:
                self.assertTrue(manifest['summary']['inventory_complete'])
                self.assertEqual(manifest['summary']['total_PER_mentions_complete'],2)
                self.assertEqual(len(Path(str(prefix)+'_mentions.jsonl').read_text().splitlines()),2)
                self.assertFalse(Path(str(prefix)+'_known_mentions_PARTIAL.jsonl').exists())
                self.assertEqual(manifest['summary']['NER_documents_processed'],1)
                raw=[json.loads(l)for l in Path(str(prefix)+'_ner_predictions.jsonl').read_text().splitlines()]
                self.assertEqual(len(raw),3)
                self.assertEqual(manifest['summary']['raw_valid_PER_predictions_this_run'],2)
                self.assertTrue(all(not r['accepted_PER']for r in raw if not r['offsets_valid']))
                self.assertTrue(all(r['text'][r['entity_start']:r['entity_end']]==r['entity']for r in raw if r['offsets_valid']))
                task=json.loads(Path(str(prefix)+'_task.json').read_text(encoding='utf-8'))
                self.assertIn('REFERENCE',task['allowed_labels'])
                self.assertIn('other_roles',task['response_schema']['properties'])
            else:
                self.assertFalse(manifest['summary']['inventory_complete'])
                self.assertIsNone(manifest['summary']['total_PER_mentions_complete'])

    def test_plan_cli_writes_all_artifacts_without_loading_ner(self):
        self.exercise_cli(False)

    def test_full_ner_cli_persists_predictions_and_mentions_with_fake_model(self):
        self.exercise_cli(True)

    def test_v2_specific_labels_and_open_other_roles_preserve_historical_config(self):
        task=inventory.annotation_task()
        self.assertEqual(task['allowed_labels'],['ARGUIDO','REU','AUTOR','REQUERENTE','RECORRENTE','RECORRIDO','TESTEMUNHA','RELATOR','REFERENCE','UNKNOWN'])
        self.assertTrue(task['response_schema']['properties']['labels']['uniqueItems'])
        self.assertIn('other_roles',task['response_schema']['properties'])
        fine,mapping=inventory.load_taxonomy(inventory.TAXONOMY_V2)
        self.assertEqual(mapping['ARGUIDO'],mapping['REU'])
        self.assertEqual(mapping['REFERENCE'],'REFERENCE')
        old,_=inventory.load_taxonomy()
        self.assertNotIn('REFERENCE',old)

    def test_full_run_gate_checks_smoke_and_current_input_hashes(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);source=root/'synthetic.txt';source.write_text('invented',encoding='utf-8')
            manifest={'summary':{'unique_texts':191,'NER_documents_processed':3,'NER_executed':True,'accepted_mentions_this_run':2,
                                'transformer_length_validation':{'validated':True,'documents':191,'effective_limit':512,'maximum_safe_wordpieces':512}},
                      'script_sha256':hashlib.sha256(Path(inventory.__file__).read_bytes()).hexdigest(),
                      'length_guard_sha256':hashlib.sha256(Path(inventory.length_guard_module.__file__).read_bytes()).hexdigest(),
                      'extractor_sha256':hashlib.sha256((inventory.ROOT/'src/data/extract_role_candidates_v2.py').read_bytes()).hexdigest(),
                      'input_files':{'source':{'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}}}
            path=root/'smoke.json';path.write_text(json.dumps(manifest),encoding='utf-8')
            inventory.validate_smoke_manifest(path)
            for field,value in [('validated',False),('documents',3),('maximum_safe_wordpieces',513)]:
                invalid=copy.deepcopy(manifest)
                invalid['summary']['transformer_length_validation'][field]=value
                path.write_text(json.dumps(invalid),encoding='utf-8')
                with self.subTest(field=field),self.assertRaises(ValueError):
                    inventory.validate_smoke_manifest(path)
            missing=copy.deepcopy(manifest)
            del missing['summary']['transformer_length_validation']
            path.write_text(json.dumps(missing),encoding='utf-8')
            with self.assertRaises(ValueError):inventory.validate_smoke_manifest(path)
            path.write_text(json.dumps(manifest),encoding='utf-8')
            source.write_text('changed synthetic input',encoding='utf-8')
            with self.assertRaises(ValueError):inventory.validate_smoke_manifest(path)

    def test_hash_dedup_keeps_conflicting_aliases_and_process_block(self):
        text,audit,texts=fixture()
        saved=copy.deepcopy(audit)
        docs=build_documents(audit,texts)
        self.assertEqual(len(docs),1)
        self.assertEqual(len(docs[0]['aliases']),2)
        self.assertEqual(len(docs[0]['potential_process_group_ids']),2)
        self.assertTrue(docs[0]['requires_identity_review'])
        self.assertEqual(audit,saved)

    def test_source_change_fails_hash_check(self):
        _,audit,texts=fixture()
        texts[next(iter(texts))]+=' changed'
        with self.assertRaises(ValueError):build_documents(audit,texts)

    def test_whole_text_windows_independent_of_role_words(self):
        text='x'*20001
        windows=full_windows(text,6000,600)
        self.assertEqual(union_length(windows),len(text))
        self.assertTrue(all(b-a<=6000 for a,b in windows))
        self.assertEqual(full_windows(''),[])

    def test_same_person_different_offsets_or_contexts_remain_distinct(self):
        text,audit,texts=fixture();doc=build_documents(audit,texts)[0]
        a=make_mention(doc,text,0,2,'AA',3)
        b=make_mention(doc,text,11,13,'AA',3)
        wider=make_mention(doc,text,0,2,'AA',20)
        self.assertNotEqual(a['id'],b['id'])
        self.assertEqual(a['id'],wider['id'])
        self.assertNotEqual(a['context_id'],wider['context_id'])
        self.assertEqual(b['text'][b['entity_start']:b['entity_end']],'AA')
        self.assertFalse(b['human_validated'])
        self.assertIsNone(b['label'])

    def test_recovered_subset_dedups_only_same_source_occurrence(self):
        text,audit,texts=fixture();docs=build_documents(audit,texts);sha=digest(text)
        rows=[{'id':str(i),'source_text_sha256':sha,'entity':'AA','entity_document_start':a,
               'entity_document_end':a+2,'entity_start':a,'text':text,'suggested_label':'ARGUIDO'}
              for i,a in enumerate([0,0,11])]
        mentions=known_mentions(docs,{sha:text},rows)
        self.assertEqual(len(mentions),2)
        self.assertNotIn('suggested_label',mentions[0])
        self.assertEqual(sum(len(r['legacy_candidate_ids'])for r in mentions),3)

    def test_full_coverage_and_optional_prediction_sink_reuse_detector(self):
        text='AA chegou.'
        class FakeNLP:
            def pipe(self,items,batch_size,n_process):
                for value in items:
                    yield SimpleNamespace(ents=[SimpleNamespace(start_char=0,end_char=2,text='AA',label_='PER'),
                                                SimpleNamespace(start_char=3,end_char=9,text='chegou',label_='ORG')])
        nlp=FakeNLP();raw=[];stats=Counter()
        self.assertEqual(detect_person_spans(text,nlp),[])  # old anchor discovery
        found=detect_person_spans(text,nlp,windows=full_windows(text),prediction_sink=raw.append,stats=stats)
        self.assertEqual(found,[(0,2,'AA')])
        self.assertEqual({r['label']for r in raw},{'PER','ORG'})
        self.assertEqual(raw[0]['window_start'],0)


if __name__=='__main__':unittest.main()
