"""Entirely synthetic protected data; public diagnostics must not leak it."""

import io
import json
import tempfile
import unittest
import unicodedata
import test_stj_pilot_19c as pilot_fixtures
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.annotation import diagnose_pilot_protection_19c as diagnostic
from src.annotation import role_reference_provenance as provenance
from src.annotation import prepare_stj_pilot_19c as preparation
from test_stj_pilot_19c import corpus, protected


def legacy_selection(refs, documents, texts):
    index=provenance.reference_index(documents,texts);records=[]
    for origin,values in refs.items():
        for ref in values:
            proof=provenance.match_reference(ref,index)
            records.append({'reference':origin+':'+ref['id'],'resolved':bool(proof['roots']or proof['legacy_matches'])})
    return {'protected_reference_checks':records,'unresolved_references':[r['reference']for r in records if not r['resolved']],
            'blocked_groups':[]}


class ReconciliationTests(unittest.TestCase):
    def test_formatting_match_reserves_source_and_allows_30_without_dropping_reference(self):
        rows,docs,texts=corpus();refs=protected();ref=refs['gold'][0]
        ref.update(text=rows[0]['text'].replace('testemunha','testemu-\nnha'),entity='AA',entity_start=0,entity_end=2)
        del ref['process_number']
        old=legacy_selection(refs,docs,texts)
        self.assertEqual(old['unresolved_references'],['gold:invented-gold'])
        chosen,audit=preparation.select_pilot(rows,docs,texts,refs)
        self.assertEqual(len(chosen),30);self.assertTrue(audit['selection_complete'])
        self.assertEqual(len(audit['protected_reference_checks']),2)
        self.assertNotIn(docs[0]['document_id'],{r['document_id']for r in chosen})
        self.assertIn('FORMATTING_NORMALIZED_CONTEXT',audit['protected_reference_checks'][0]['matching_evidence']['methods'][docs[0]['document_id']])

    def test_unicode_and_soft_hyphen_are_verified_positive_matches_only(self):
        text='A testemunha AA confirmou a decisão inteiramente fictícia neste exemplo inventado.'
        ref={'id':'invented','text':text,'entity':'AA','entity_start':13,'entity_end':15}
        rows,docs,_=corpus(1)
        variant=unicodedata.normalize('NFD',text).replace('testemunha','testemu\u00adnha')
        index=provenance.reference_index(docs,{docs[0]['document_id']:variant})
        proof=provenance.match_reference(ref,index)
        self.assertFalse(proof['legacy_matches']);self.assertIn(docs[0]['document_id'],proof['methods'])
        ref['text']='A testemunha AA descreveu factos diferentes de todos os anteriores neste exemplo inventado.'
        self.assertFalse(provenance.match_reference(ref,index)['methods'])

    def test_process_format_variant_requires_positive_inventory_root(self):
        _,docs,texts=corpus(1);ref=protected()['gold'][0]
        ref['process_number']='1000-26.1T8XYZ.S2.docx.txt'
        proof=provenance.match_reference(ref,provenance.reference_index(docs,texts))
        self.assertFalse(proof['roots'])
        self.assertIn('PROCESS_FORMAT_WITH_INVENTORY_ROOT',proof['methods'][docs[0]['document_id']])
        ref['process_number']='99000-26.1T8XYZ.S2.docx.txt'
        self.assertFalse(provenance.match_reference(ref,provenance.reference_index(docs,texts))['methods'])

    def test_multiple_matching_documents_are_all_reserved(self):
        _,docs,_=corpus(2);ref=protected()['gold'][0]
        del ref['process_number']
        texts={d['document_id']:provenance.formatting_text(ref['text']) for d in docs}
        proof=provenance.match_reference(ref,provenance.reference_index(docs,texts))
        self.assertEqual(set(proof['methods']),{d['document_id']for d in docs})


class PublicDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.rows,self.docs,self.texts=corpus(3);self.refs=protected()
        self.refs['gold'][0]['id']='PRIVATE_REFERENCE_SENTINEL'
        self.refs['gold'][0]['process_number']='PRIVATE_UNPARSEABLE_SENTINEL'
        self.selection=legacy_selection(self.refs,self.docs,self.texts)

    def test_origin_causes_and_keyed_tokens_without_private_values(self):
        public,private,template=diagnostic.diagnose(self.selection,self.rows,self.docs,self.texts,self.refs,b'k'*32)
        serialized=json.dumps(public)
        for value in ('PRIVATE_REFERENCE_SENTINEL','PRIVATE_UNPARSEABLE_SENTINEL',self.refs['gold'][0]['text'],
                      self.docs[0]['document_id'],self.docs[0]['source_text_sha256']):
            self.assertNotIn(value,serialized)
        row=public['references'][0]
        self.assertEqual(row['origin_code'],'GOLD');self.assertEqual(len(row['reference_token']),64)
        self.assertIn('IDENTITY_METADATA_UNPARSEABLE',row['cause_codes'])
        self.assertIn('MANUAL_PROVENANCE_REQUIRED',row['cause_codes'])
        key='gold:PRIVATE_REFERENCE_SENTINEL'
        self.assertEqual(private[0]['reference'],key)
        self.assertFalse(template[key]['human_confirmed'])
        other=diagnostic.diagnose(self.selection,self.rows,self.docs,self.texts,self.refs,b'z'*32)[0]
        self.assertNotEqual(other['references'][0]['reference_token'],row['reference_token'])
        self.assertEqual(diagnostic.diagnose(self.selection,self.rows,self.docs,self.texts,self.refs,b'k'*32)[0],public)

    def test_weak_candidates_do_not_resolve_reference(self):
        ref=self.refs['gold'][0]
        ref.update(text=self.rows[0]['text']+' mais palavras diferentes inventadas',entity='AA',entity_start=0,entity_end=2)
        self.selection=legacy_selection(self.refs,self.docs,self.texts)
        public,_,template=diagnostic.diagnose(self.selection,self.rows,self.docs,self.texts,self.refs,b'k'*32)
        self.assertIn('WEAK_CONTENT_CANDIDATES_NOT_PROOF',public['references'][0]['cause_codes'])
        self.assertEqual(public['counts']['verifiable_reconciliations'],0)
        self.assertTrue(template)

    def test_bad_key_or_changed_reference_manifest_is_rejected(self):
        with self.assertRaises(ValueError):diagnostic.diagnose(self.selection,self.rows,self.docs,self.texts,self.refs,b'bad')
        self.selection['protected_reference_checks'].append(self.selection['protected_reference_checks'][0])
        with self.assertRaises(ValueError):diagnostic.diagnose(self.selection,self.rows,self.docs,self.texts,self.refs,b'k'*32)

    def test_cli_error_never_prints_private_path_or_exception_value(self):
        with tempfile.TemporaryDirectory()as directory:
            argv=['diagnose','--selection-manifest',str(Path(directory)/'PRIVATE_SENTINEL.json'),
                  '--output-dir',str(Path(directory)/'out')]
            stderr=io.StringIO();stdout=io.StringIO()
            with (patch('sys.argv',argv),patch.object(diagnostic,'private_new_output',side_effect=lambda p:p),
                  redirect_stderr(stderr),redirect_stdout(stdout)):
                with self.assertRaises(SystemExit):diagnostic.main()
            self.assertNotIn('PRIVATE_SENTINEL',stderr.getvalue()+stdout.getvalue())
            self.assertEqual(json.loads(stderr.getvalue())['error_code'],'DIAGNOSTIC_INPUT_VALIDATION_FAILED')

    def test_successful_cli_writes_only_safe_public_json_and_preserves_inputs(self):
        fixture=pilot_fixtures.PilotBundleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        refs=protected();del refs['gold'][0]['process_number'];del refs['human_pilot'][0]['process_number']
        refs['gold'].append({**refs['gold'][0],'id':'SECOND_PRIVATE_SENTINEL'})
        for name,values in refs.items():
            path=fixture.root/f'{name}.jsonl';path.write_text(''.join(json.dumps(r)+'\n'for r in values),encoding='utf-8')
            fixture.audit['validated_bundle'][name]={'path':str(path),'sha256':preparation.file_hash(path)}
        docs=[json.loads(line)for line in (fixture.root/'inventory_documents.jsonl').read_text().splitlines()]
        texts={d['document_id']:(fixture.root/d['canonical_source']['source_file']).read_text()for d in docs}
        fixture.audit.update(legacy_selection(refs,docs,texts));fixture.audit['selection_complete']=False
        fixture.write_manifest();before={p:p.read_bytes()for p in fixture.root.iterdir()if p.is_file()}
        output=fixture.root/'diagnostic'
        argv=['diagnose','--selection-manifest',str(fixture.selection),'--output-dir',str(output)]
        stdout=io.StringIO()
        with (patch('sys.argv',argv),patch.object(diagnostic,'private_new_output',side_effect=lambda p:p),
              patch.object(diagnostic,'GOLD_SHA',fixture.audit['validated_bundle']['gold']['sha256']),
              patch.object(diagnostic,'PILOT_SOURCES_SHA',fixture.audit['validated_bundle']['human_pilot']['sha256']),
              redirect_stdout(stdout)):
            diagnostic.main()
        public=json.loads(stdout.getvalue())
        self.assertEqual(public['counts']['original_unresolved'],3)
        self.assertNotIn('SECOND_PRIVATE_SENTINEL',stdout.getvalue())
        self.assertEqual(json.loads((output/'shareable_diagnostic.json').read_text()),public)
        self.assertEqual(len((output/'token_key_PRIVATE.bin').read_bytes()),32)
        template=json.loads((output/'adjudication_template_PRIVATE.json').read_text())
        self.assertTrue(all(d['human_confirmed']is False for d in template.values()))
        self.assertTrue(all(path.read_bytes()==contents for path,contents in before.items()))

    def test_verified_reconciliation_is_counted_without_issuing_manual_clearance(self):
        ref=self.refs['gold'][0]
        ref.update(text=self.rows[0]['text'].replace('testemunha','testemu-\nnha'),entity='AA',entity_start=0,entity_end=2)
        self.selection=legacy_selection(self.refs,self.docs,self.texts)
        public,_,template=diagnostic.diagnose(self.selection,self.rows,self.docs,self.texts,self.refs,b'k'*32)
        self.assertEqual(public['counts']['verifiable_reconciliations'],1)
        self.assertFalse(template)


class AdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.rows,self.docs,self.texts=corpus(2);self.ref=protected()['gold'][0];del self.ref['process_number']
        self.ref['text'] += ' Contexto adicional exclusivamente artificial.'
        self.proof=provenance.match_reference(self.ref,provenance.reference_index(self.docs,self.texts))
        self.decision={'human_confirmed':True,'reviewer':'invented-reviewer','reason':'Invented documented provenance review.',
                       'reference_sha256':provenance.fingerprint(self.ref),'inventory_fingerprint':provenance.fingerprint(self.docs)}
        self.raw_patch=patch.object(provenance,'RAW_ROOT',self.root);self.raw_patch.start();self.addCleanup(self.raw_patch.stop)

    def evidence(self,kind,content,suffix='.json'):
        path=self.root/('evidence'+suffix);path.write_text(content,encoding='utf-8')
        return {'kind':kind,'path':str(path),'sha256':preparation.file_hash(path)}

    def validate(self,decision):return provenance.validate_decision(decision,self.ref,self.docs,self.texts,self.proof)

    def test_bound_human_reservation_blocks_documents_not_declares_training_safe(self):
        targets=[self.docs[0]['document_id']]
        packet={'reference_sha256':provenance.fingerprint(self.ref),'document_ids':targets,
                'document_source_hashes':{d['document_id']:d['source_text_sha256']for d in self.docs[:1]}}
        decision={**self.decision,'document_ids':targets,'evidence':[self.evidence('reservation_packet',json.dumps(packet))]}
        reserved,evidence=self.validate(decision)
        self.assertEqual(reserved,set(targets));self.assertEqual(evidence['kind'],'human_document_reservation')

    def test_bare_checkbox_stale_fingerprint_wrong_hash_and_wrong_packet_fail(self):
        for change in ({},{'reference_sha256':'wrong'},{'inventory_fingerprint':'wrong'},{'human_confirmed':False}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate({**self.decision,**change})
        item=self.evidence('reservation_packet','{}')
        with self.assertRaises(ValueError):self.validate({**self.decision,'document_ids':[self.docs[0]['document_id']], 'evidence':[item]})
        item['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash_mismatch'):self.validate({**self.decision,'evidence':[item]})

    def test_external_exclusion_requires_matching_source_and_disjoint_verified_header(self):
        text='Processo: 99001/26.1T8ZZZ\n'+self.ref['text']
        item=self.evidence('external_source',text,'.txt')
        decision={**self.decision,'excluded_from_corpus':True,'evidence':[item]}
        reserved,evidence=self.validate(decision)
        self.assertEqual(reserved,set());self.assertEqual(evidence['kind'],'verified_external_source')
        text='Processo: '+self.docs[0]['potential_process_group_ids'][0]+'\n'+self.ref['text']
        decision['evidence']=[self.evidence('external_source',text,'.txt')]
        with self.assertRaises(ValueError):self.validate(decision)

    def test_external_missing_context_missing_header_and_detected_overlap_fail(self):
        for text in ('Processo: 99001/26.1T8ZZZ\nEntirely different invented material.',self.ref['text']):
            with self.subTest(text=text),self.assertRaises(ValueError):
                self.validate({**self.decision,'excluded_from_corpus':True,'evidence':[self.evidence('external_source',text,'.txt')]})
        item=self.evidence('external_source','Processo: 99001/26.1T8ZZZ\n'+self.ref['text'],'.txt')
        self.proof['methods']={self.docs[0]['document_id']:['VERBATIM_CONTEXT']}
        with self.assertRaises(ValueError):self.validate({**self.decision,'excluded_from_corpus':True,'evidence':[item]})

    def test_evidence_outside_private_storage_is_rejected(self):
        item=self.evidence('reservation_packet','{}')
        with patch.object(provenance,'RAW_ROOT',self.root/'different-private-root'):
            with self.assertRaisesRegex(ValueError,'private_local_file'):
                self.validate({**self.decision,'evidence':[item]})

    def test_bound_adjudication_propagates_to_related_group_in_selection(self):
        rows,docs,texts=corpus(4);refs=protected();del refs['gold'][0]['process_number']
        docs[1]['aliases']=[{'decision_id':docs[0]['potential_process_group_ids'][0]+'.S2'}]
        targets=[docs[0]['document_id']]
        packet={'reference_sha256':provenance.fingerprint(refs['gold'][0]),'document_ids':targets,
                'document_source_hashes':{targets[0]:docs[0]['source_text_sha256']}}
        item=self.evidence('reservation_packet',json.dumps(packet))
        decision={**self.decision,'reference_sha256':packet['reference_sha256'],
                  'inventory_fingerprint':provenance.fingerprint(docs),'document_ids':targets,'evidence':[item]}
        selected,audit=preparation.select_pilot(rows,docs,texts,refs,count=2,decisions={'gold:invented-gold':decision})
        self.assertTrue(audit['selection_complete'])
        self.assertEqual({r['document_id']for r in selected},{d['document_id']for d in docs[2:]})


if __name__=='__main__':unittest.main()
