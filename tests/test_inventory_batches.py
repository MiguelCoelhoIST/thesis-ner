"""Private batch planning only, with invented mentions."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.annotation import plan_inventory_batches as planner
from src.annotation.plan_inventory_batches import plan_batches
from src.data.prepare_stj_corpus_inventory import make_mention, digest

def mention(number,**updates):
    return {'id':f'invented-{number}','text':'AA respondeu.','entity':'AA','entity_start':0,'entity_end':2,
            'entity_document_start':number*20,'document_id':'invented-doc','split_block_id':'invented-block',
            'label':None,'human_validated':False,'requires_identity_review':False,
            'gold_known_process_overlap':False,'gold_context_containment_flag':False,'pilot_related_block':False,
            'reference_checks':{'gold':'checked','pilot':'checked'},**updates}

class BatchTests(unittest.TestCase):
    def test_all_257_mentions_are_planned_not_sampled(self):
        rows=[mention(n)for n in range(257)];batches=plan_batches(rows,100)
        self.assertEqual([len(b['mention_ids'])for b in batches],[100,100,57])
        self.assertEqual(set(r['id']for r in rows),{i for b in batches for i in b['mention_ids']})
        self.assertTrue(all('text'not in b for b in batches))
        self.assertEqual(len({block for b in batches for block in b['split_block_ids']}),1)

    def test_reserved_cohorts_are_separate_without_dropping_mentions(self):
        rows=[mention(1,document_id='a',split_block_id='a'),mention(2,document_id='b',split_block_id='b',pilot_related_block=True),mention(3,document_id='c',split_block_id='c',gold_known_process_overlap=True),mention(4,document_id='d',split_block_id='d',requires_identity_review=True)]
        batches=plan_batches(rows)
        self.assertEqual(len(batches),4)
        self.assertEqual(sum(len(b['mention_ids'])for b in batches),4)

    def test_duplicate_offsets_and_hints_are_rejected(self):
        for rows in ([mention(1),mention(1)],[mention(1,entity_start=1)], [mention(1,suggested_label='REU')]):
            with self.assertRaises(ValueError):plan_batches(rows)

    def test_null_missing_and_indeterminate_checks_are_never_cleared(self):
        for updates in ({'gold_known_process_overlap':None}, {'pilot_related_block':'not_requested'},
                        {'reference_checks':{}}, {'reference_checks':{'gold':'checked','pilot':'not_requested'}},
                        {'gold_context_containment_flag':0}, {'reference_checks':None}):
            with self.subTest(updates=updates):
                batch=plan_batches([mention(1,**updates)])[0]
                self.assertEqual(batch['cohort'],'reference_review_required')
                self.assertIn('protected_reference_checks_incomplete',batch['review_reasons'])
                self.assertIsNone(batch['split_assignment'])
                self.assertEqual(batch['training_eligibility'],'NOT_ESTABLISHED')

    def test_existing_scalar_multi_and_silver_annotations_rejected(self):
        for update in ({'label':'ARGUIDO'}, {'labels':['ARGUIDO']}, {'labels':'ARGUIDO'},
                       {'annotation_tier':'SILVER'}, {'human_validated':True},
                       {'proposed_labels':['ARGUIDO']}, {'other_roles':[{'role':'invented'}]}):
            with self.subTest(update=update),self.assertRaises(ValueError):
                plan_batches([mention(1,**update)])

    def test_protection_propagates_across_hash_block_process_and_aliases(self):
        for link in ('hash','block','process','alias'):
            left=mention(1,document_id='doc-a',split_block_id='a',gold_known_process_overlap=True)
            right=mention(2,document_id='doc-b',split_block_id='b')
            if link=='hash':left['source_text_sha256']=right['source_text_sha256']='invented-hash'
            if link=='block':right['split_block_id']='a'
            if link=='process':
                left['process_group_id_candidates']=['101/26.1T8XYZ.S1']
                right['process_group_id_candidates']=['101/26.1T8XYZ.S2']
            if link=='alias':
                left['aliases']=[{'decision_id':'101/26.1T8XYZ.S1'}]
                right['aliases']=[{'decision_id':'101/26.1T8XYZ.S2'}]
            with self.subTest(link=link):
                batches=plan_batches([left,right],1)
                self.assertEqual({b['cohort']for b in batches},{'reserved_gold_related'})
                self.assertEqual(batches[0]['planning_group_ids'],batches[1]['planning_group_ids'])
                self.assertEqual(plan_batches([right,left],1),batches)

    def test_unselected_document_can_reserve_related_mentions(self):
        row=mention(1)
        related={**row,'document_id':'other','pilot_related_block':True}
        batches=plan_batches([row],documents=[related])
        self.assertEqual(batches[0]['cohort'],'reserved_pilot_related')
        self.assertEqual(batches[0]['mention_ids'],[row['id']])

    def test_unknown_check_propagates_without_losing_known_protection(self):
        batches=plan_batches([mention(1,pilot_related_block=True),mention(2,reference_checks={})])
        self.assertEqual(batches[0]['cohort'],'reserved_pilot_related')
        self.assertIn('protected_reference_checks_incomplete',batches[0]['review_reasons'])
        self.assertEqual(len(batches[0]['mention_ids']),2)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.prefix=self.root/'invented_run_'
        text='AA respondeu.';sha=digest(text)
        self.doc={'document_id':'doc_'+sha,'source_text_sha256':sha,'characters':len(text),
                  'canonical_source':{'source_file':'invented.txt','source_document_id':'invented.txt'},
                  'aliases':[],'split_block_id':'invented-block','potential_process_group_ids':['101/26.1T8XYZ'],
                  'requires_identity_review':False,'pilot_related_block':False,'gold_known_process_overlap':False,
                  'gold_context_containment_flag':False,'reference_checks':{'gold':'checked','pilot':'checked'}}
        self.row=make_mention(self.doc,text,0,2,'AA')
        self.pred={'document_id':self.row['document_id'],'start':0,'end':2,'entity':'AA','ner_label':'PER',
                   'accepted_PER':True,'offsets_valid':True,'mention_id':self.row['id'],
                   **{f:self.row[f]for f in ('text','entity_start','entity_end','context_document_start','context_document_end','context_id')}}
        source=self.root/'invented.txt';source.write_text(text,encoding='utf-8')
        source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
        self.manifest={'summary':{'inventory_complete':True,'NER_executed':True,'unique_texts':1,'total_PER_mentions_complete':1},
                       'source_inventory':{'directory':str(self.root)},
                       'inputs_sha256':{'source_0':source_sha},
                       'input_files':{'source_0':{'path':str(source),'sha256':source_sha}}}
        self.write('documents.jsonl',[self.doc]);self.write('mentions.jsonl',[self.row])
        self.write('ner_predictions.jsonl',[self.pred]);self.write('manifest.json',self.manifest)

    def path(self,suffix):return Path(str(self.prefix)+suffix)

    def write(self,suffix,value):
        text=''.join(json.dumps(r)+'\n'for r in value)if suffix.endswith('.jsonl')else json.dumps(value)
        self.path(suffix).write_text(text,encoding='utf-8')

    def load(self):return planner.load_bound_inventory(self.path('mentions.jsonl'),self.path('manifest.json'))

    def test_binding_hashes_and_source_ids_match(self):
        rows,docs,summary,binding=self.load()
        self.assertEqual(rows,[self.row]);self.assertEqual(docs,[self.doc])
        self.assertTrue(summary['inventory_complete']);self.assertEqual(len(binding),5)
        for item in binding.values():
            self.assertEqual(item['sha256'],hashlib.sha256(Path(item['path']).read_bytes()).hexdigest())

    def test_same_count_wrong_ids_hashes_context_and_metadata_fail(self):
        for change in ({'id':'wrong'}, {'document_id':'wrong'}, {'source_text_sha256':'0'*64},
                       {'context_id':'wrong'}, {'split_block_id':'wrong'},
                       {'process_group_id_candidates':[]}, {'source_file':'wrong'},
                       {'reference_checks':{}}, {'text':'AA inventado.'}, {'labels':['ARGUIDO']}):
            row={**self.row,**change};self.write('mentions.jsonl',[row])
            with self.subTest(change=change),self.assertRaises(ValueError):
                rows,docs,_,_=self.load();plan_batches(rows,documents=docs)

    def test_raw_context_tamper_and_missing_accepted_prediction_fail(self):
        for prediction in ({**self.pred,'text':'AA inventado.'},{**self.pred,'mention_id':'wrong'},
                           {**self.pred,'accepted_PER':False},{**self.pred,'offsets_valid':False}):
            self.write('ner_predictions.jsonl',[prediction])
            with self.subTest(prediction=prediction),self.assertRaises(ValueError):self.load()

    def test_missing_companion_and_different_bundle_are_explicit_errors(self):
        wrong=self.root/'wrong_mentions.jsonl';wrong.write_text(self.path('mentions.jsonl').read_text())
        with self.assertRaises(ValueError):planner.load_bound_inventory(wrong,self.path('manifest.json'))
        self.path('ner_predictions.jsonl').unlink()
        with self.assertRaises(FileNotFoundError):self.load()

    def test_same_count_manifest_from_different_sources_is_rejected(self):
        self.manifest['input_files']['source_0']['sha256']='0'*64
        self.manifest['inputs_sha256']['source_0']='0'*64
        self.write('manifest.json',self.manifest)
        with self.assertRaisesRegex(ValueError,'original_source_changed'):self.load()

    def test_changed_source_and_forged_context_in_both_outputs_are_rejected(self):
        # Even a consistent alteration of mentions AND raw predictions cannot
        # bypass the document hash tied to the source fingerprint in the manifest.
        row={**self.row,'text':'AA inventado.'};pred={**self.pred,'text':row['text']}
        self.write('mentions.jsonl',[row]);self.write('ner_predictions.jsonl',[pred])
        with self.assertRaises(ValueError):self.load()
        (self.root/'invented.txt').write_text('BB respondeu.',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'original_source_changed'):self.load()

    def test_cli_writes_new_private_plan_and_refuses_overwrite(self):
        output=self.root/'new-plan'
        argv=['plan','--input',str(self.path('mentions.jsonl')),'--inventory-manifest',str(self.path('manifest.json')),'--output-dir',str(output)]
        before={p.name:p.read_bytes()for p in self.root.iterdir()}
        with patch('sys.argv',argv),patch.object(planner,'private_new_output',side_effect=lambda p:p),patch('builtins.print'):
            planner.main()
            with self.assertRaises(FileExistsError):planner.main()
        self.assertEqual(before,{p.name:p.read_bytes()for p in self.root.iterdir()if p.is_file()})
        manifest=json.loads((output/'manifest.json').read_text())
        self.assertEqual(manifest['validated_bundle']['input']['sha256'],planner.file_hash(self.path('mentions.jsonl')))
        batch=json.loads((output/'batch_0001.json').read_text())
        self.assertNotIn('text',batch);self.assertIsNone(batch['split_assignment'])

    def test_cli_failure_creates_nothing_and_hides_private_values(self):
        output=self.root/'new-plan';self.write('mentions.jsonl',[{**self.row,'id':'PRIVATE_FAILURE_SENTINEL'}])
        argv=['plan','--input',str(self.path('mentions.jsonl')),'--inventory-manifest',str(self.path('manifest.json')),'--output-dir',str(output)]
        import io
        from contextlib import redirect_stderr
        stream=io.StringIO()
        with patch('sys.argv',argv),patch.object(planner,'private_new_output',side_effect=lambda p:p),redirect_stderr(stream):
            with self.assertRaises(SystemExit)as result:planner.main()
        self.assertEqual(result.exception.code,1);self.assertFalse(output.exists())
        self.assertNotIn('PRIVATE_FAILURE_SENTINEL',stream.getvalue())

    def test_partial_requires_explicit_acknowledgment(self):
        self.manifest['summary'].update(inventory_complete=False,accepted_mentions_this_run=1)
        self.write('manifest.json',self.manifest)
        output=self.root/'partial-plan'
        argv=['plan','--input',str(self.path('mentions.jsonl')),'--inventory-manifest',str(self.path('manifest.json')),'--output-dir',str(output)]
        with patch.object(planner,'private_new_output',side_effect=lambda p:p),patch('sys.stderr'),patch('builtins.print'):
            with patch('sys.argv',argv),self.assertRaises(SystemExit):planner.main()
            self.assertFalse(output.exists())
            with patch('sys.argv',argv+['--allow-partial']):planner.main()
        self.assertFalse(json.loads((output/'manifest.json').read_text())['summary']['inventory_complete'])

    def test_recovered_partial_is_source_bound_without_requiring_ner_outputs(self):
        self.manifest['summary'].update(inventory_complete=False,NER_executed=False,recovered_known_occurrences_lower_bound=1)
        self.write('manifest.json',self.manifest)
        self.write('known_mentions_PARTIAL.jsonl',[self.row])
        self.path('ner_predictions.jsonl').unlink()
        rows,documents,summary,binding=planner.load_bound_inventory(self.path('known_mentions_PARTIAL.jsonl'),self.path('manifest.json'))
        self.assertEqual(rows,[self.row]);self.assertEqual(documents,[self.doc])
        self.assertFalse(summary['inventory_complete']);self.assertNotIn('ner_predictions',binding)

if __name__=='__main__':unittest.main()
