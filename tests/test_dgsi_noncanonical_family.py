"""Invented offline sources only: document identity is not family identity."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import test_stj_pilot_19c as fixtures
from src.annotation import dgsi_source_evidence as dgsi
from src.annotation import role_reference_provenance as protection
from src.annotation import prepare_dgsi_adjudication_19c as wizard
from src.annotation import prepare_stj_pilot_19c as preparation
from src.data.prepare_stj_corpus_inventory import make_mention, digest

URL='https://www.dgsi.pt/jstj.nsf/0/'+('d'*32)+'?OpenDocument'
PASSAGE='ZZ descreveu uma situacao inteiramente inventada para verificar protecoes neste teste sintetico.'


class FamilyTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.source=self.root/'synthetic_copy.txt';self.capture=self.root/'synthetic_capture.html'
        self.text='Processo:\n701/2S.0T8XYZ.S1\nTexto Integral:\n'+PASSAGE
        self.source.write_text(self.text,encoding='utf-8')
        self.capture.write_text('<meta property="og:url" content="'+URL+'"><p>Processo:</p>'
                                '<p>701/2S.0T8XYZ.S1</p><p>Texto Integral:</p><p>'+PASSAGE+'</p>',encoding='utf-8')
        self.ref={'id':'invented-ref','text':PASSAGE,'entity':'ZZ','entity_start':0,'entity_end':2,'source_url':URL}
        self.rows,self.docs,self.texts=fixtures.corpus(35)
        # A trustworthy inventory identity must be corroborated by the actual
        # frozen source header, rather than metadata alone.
        for doc in self.docs:
            old=doc['document_id'];body=self.texts.pop(old)
            text='Processo: '+doc['potential_process_group_ids'][0]+'.S1\nTexto Integral:\n'+body
            doc.update(document_id='doc_'+digest(text),source_text_sha256=digest(text),characters=len(text))
            self.texts[doc['document_id']]=text
        self.refresh_rows()

    def refresh_rows(self):
        self.rows=[]
        for doc in self.docs:
            text=self.texts[doc['document_id']];start=text.index('AA ')
            self.rows.append(make_mention(doc,text,start,start+2,'AA'))

    def identity(self):
        self.receipt=dgsi.make_receipt(self.source,self.text,self.capture,URL,'invented reviewer',
                                     'Offline synthetic source checked.',[self.ref])
        return dgsi.verify_receipt(self.receipt,self.source,self.text,self.ref,
                                  {(self.capture,'official_capture',preparation.file_hash(self.capture))})

    def decision(self):
        identity=self.identity();guard=dgsi.family_guard(identity,self.docs,self.texts,self.ref,self.text,self.source)
        targets=guard['required_document_ids']
        packet={'reference_sha256':protection.fingerprint(self.ref),'inventory_fingerprint':protection.fingerprint(self.docs),
                'guard_fingerprints':[protection.fingerprint(guard)],'document_ids':targets,
                'document_source_hashes':{d['document_id']:d['source_text_sha256'] for d in self.docs if d['document_id'] in targets}}
        self.packet_path=self.root/'packet.json';self.packet_path.write_text(json.dumps(packet),encoding='utf-8')
        receipt_path=self.root/'receipt.json';receipt_path.write_text(json.dumps(self.receipt),encoding='utf-8')
        return {'human_confirmed':True,'reviewer':'invented','reason':'Synthetic protected exclusion review.',
                'reference_sha256':protection.fingerprint(self.ref),'inventory_fingerprint':protection.fingerprint(self.docs),
                'excluded_from_corpus':False,'document_ids':targets,'evidence':[
                    {'kind':kind,'path':str(path),'sha256':preparation.file_hash(path)} for kind,path in
                    [('external_source',self.source),('official_capture',self.capture),
                     ('dgsi_identity_receipt',receipt_path),('dgsi_family_reservation_packet',self.packet_path)]]}

    def validate(self,decision):
        with patch.object(protection,'RAW_ROOT',self.root):
            return protection.validate_decision(decision,self.ref,self.docs,self.texts,
                       protection.match_reference(self.ref,protection.reference_index(self.docs,self.texts)))

    def replace_source(self,i,text,root):
        doc=self.docs[i];self.texts.pop(doc['document_id'])
        doc.update(document_id='doc_'+digest(text),source_text_sha256=digest(text),characters=len(text),
                   potential_process_group_ids=[root])
        self.texts[doc['document_id']]=text

    def test_same_serial_all_years_courts_unknowns_and_unid_are_reserved(self):
        text='Processo: 701/99.7T8ABC.S2\nTexto Integral:\nAA exemplo artificial.'
        self.replace_source(0,text,'701/99.7T8ABC')
        self.docs[1]['requires_identity_review']=True
        doc=self.docs[2];text=self.texts[doc['document_id']]+' '+('d'*32)
        self.replace_source(2,text,doc['potential_process_group_ids'][0])
        self.docs[3]['aliases']=[{'decision_id':'701/88.2T8ZZZ.S1','process_provenance':{'status':'conflict'}}]
        doc=self.docs[4];text=self.texts[doc['document_id']]+' Citacao: 701/2S.0T8XYZ.S2.'
        self.replace_source(4,text,doc['potential_process_group_ids'][0])
        decision=self.decision();targets,proof=self.validate(decision)
        self.assertEqual(targets,{d['document_id'] for d in self.docs[:5]})
        self.assertEqual(proof['family_identity_status'],'unconfirmed')
        self.assertFalse(proof['external_absence_claimed'])
        self.assertEqual(proof['family_guards'][0]['training_eligibility'],'NOT_ESTABLISHED')
        omitted=copy.deepcopy(decision);omitted['document_ids']=sorted(targets)[1:]
        with self.assertRaisesRegex(ValueError,'envelope_not_fully_reserved'):self.validate(omitted)

    def test_verified_document_cannot_be_declared_external(self):
        decision=self.decision();decision['excluded_from_corpus']=True
        with self.assertRaisesRegex(ValueError,'does_not_prove_external_family'):self.validate(decision)

    def test_packet_and_inventory_and_source_are_bound(self):
        decision=self.decision()
        bad=copy.deepcopy(decision);bad['evidence']=bad['evidence'][:-1]
        with self.assertRaisesRegex(ValueError,'bound_family_reservation_packet_required'):self.validate(bad)
        packet=json.loads(self.packet_path.read_text());packet['guard_fingerprints']=['changed']
        self.packet_path.write_text(json.dumps(packet),encoding='utf-8')
        decision['evidence'][-1]['sha256']=preparation.file_hash(self.packet_path)
        with self.assertRaisesRegex(ValueError,'packet_not_bound'):self.validate(decision)
        decision=self.decision();self.texts[self.docs[0]['document_id']]+=' changed'
        with self.assertRaisesRegex(ValueError,'source_fingerprint_mismatch'):self.validate(decision)

    def test_empty_reservation_is_coverage_not_family_absence_and_allows_synthetic_selection(self):
        decision=self.decision();self.assertEqual(decision['document_ids'],[])
        refs=fixtures.protected();refs['gold']=[self.ref]
        before=copy.deepcopy((self.rows,self.docs,self.ref))
        with patch.object(protection,'RAW_ROOT',self.root):
            selected,audit=preparation.select_pilot(self.rows,self.docs,self.texts,refs,
                                                   decisions={'gold:'+self.ref['id']:decision})
        self.assertEqual(len(selected),30);self.assertTrue(audit['selection_complete'])
        check=next(r for r in audit['protected_reference_checks'] if r['reference'].startswith('gold:'))
        self.assertEqual(check['adjudication']['family_identity_status'],'unconfirmed')
        self.assertEqual(check['resolution_scope'],'protection_only_family_unconfirmed')
        self.assertEqual((self.rows,self.docs,self.ref),before)

    def test_unverified_headers_are_reserved_even_when_metadata_claims_unrelated(self):
        self.rows,self.docs,self.texts=fixtures.corpus(35)
        decision=self.decision();targets,_=self.validate(decision)
        self.assertEqual(len(targets),35)
        refs=fixtures.protected();refs['gold']=[self.ref]
        with patch.object(protection,'RAW_ROOT',self.root):
            selected,audit=preparation.select_pilot(self.rows,self.docs,self.texts,refs,
                                                   decisions={'gold:'+self.ref['id']:decision})
        self.assertEqual(selected,[]);self.assertFalse(audit['selection_complete'])

    def test_reservation_propagates_to_known_related_blocks_with_other_identifiers(self):
        self.replace_source(0,'Processo: 701/99.7T8ABC.S2\nTexto Integral:\nAA exemplo artificial.','701/99.7T8ABC')
        self.docs[1]['split_block_id']=self.docs[0]['split_block_id']
        self.refresh_rows();decision=self.decision()
        refs=fixtures.protected();refs['gold']=[self.ref]
        with patch.object(protection,'RAW_ROOT',self.root):
            selected,audit=preparation.select_pilot(self.rows,self.docs,self.texts,refs,
                                                   decisions={'gold:'+self.ref['id']:decision})
        self.assertTrue(audit['selection_complete'])
        self.assertFalse({r['document_id'] for r in selected}&{d['document_id'] for d in self.docs[:2]})


class PrivateSourceTests(unittest.TestCase):
    def test_local_source_identification_never_puts_filename_in_redirected_output(self):
        stream=io.StringIO();source=Path('invented_private_source.txt')
        with redirect_stderr(stream):wizard.identify_source_locally(source,1,2)
        self.assertNotIn(source.name,stream.getvalue())
        self.assertEqual(json.loads(stream.getvalue())['source_ordinal'],1)
        stream=io.StringIO()
        with patch.object(stream,'isatty',return_value=True),redirect_stderr(stream):
            wizard.identify_source_locally(source,1,2)
        self.assertIn(source.name,stream.getvalue())


if __name__=='__main__':unittest.main()
