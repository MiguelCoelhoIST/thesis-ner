"""Fabricated DGSI-shaped documents/URLs only; never real judgment contents."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch
import test_stj_pilot_19c as fixtures

from src.data.role_provenance import extract_process_provenance, normalize_decision_id
from src.annotation import dgsi_source_evidence as dgsi
from src.annotation import prepare_dgsi_adjudication_19c as wizard
from src.annotation import role_reference_provenance as protection
from src.annotation import prepare_stj_pilot_19c as preparation

URL='https://www.dgsi.pt/jstj.nsf/'+('a'*32)+'/'+('b'*32)+'?OpenDocument'
URL2='https://www.dgsi.pt/jstj.nsf/'+('a'*32)+'/'+('c'*32)+'?OpenDocument'
PASSAGE='AA descreveu factos inteiramente fictícios neste exemplo artificial criado apenas para testes.'


def html_capture(identifier,body=PASSAGE,url=URL):
    return '<html><head><meta property="og:url" content="'+url+'"></head><body><b>Processo:</b><p>'+identifier+'</p><b>Texto Integral:</b><p>'+body+'</p></body></html>'


class HeaderTests(unittest.TestCase):
    def test_next_line_nbsp_and_bom_preserve_exact_span_and_suffix(self):
        for label in ('Processo:','Proc. n.º:','Nº do Processo:'):
            text='\ufeff'+label+'\r\n\u00a0901/23.5T8XYZ.P1.S2\nTexto Integral:\nConteúdo artificial.'
            result=extract_process_provenance(text,'copy.txt')
            self.assertEqual(result['decision_id'],'901/23.5T8XYZ.P1.S2')
            for item in result['process_provenance']['header_evidence']:
                self.assertEqual(text[item['start']:item['end']],item['raw'])
        self.assertEqual(extract_process_provenance('Proc.901/23.5T8XYZ.S1','copy.txt')['decision_id'],
                         '901/23.5T8XYZ.S1')

    def test_confusable_letters_are_not_replaced_or_assigned_identity_roots(self):
        for value,code in [('901/23.ST8XYZ.P1.S1','NON_NUMERIC_SEGMENT_START'),
                           ('902/2S.0T8ABC.S1','NON_CANONICAL_YEAR')]:
            self.assertIsNone(normalize_decision_id(value))
            result=extract_process_provenance('Processo:\n'+value+'\n','copy.txt')
            self.assertEqual(result['process_provenance']['status'],'unresolved')
            self.assertFalse(result['process_provenance']['header_evidence'])
            self.assertEqual(result['process_group_id_candidates'],[])
            evidence=result['process_provenance']['unparsed_header_evidence'][0]
            self.assertEqual(evidence['raw'],value);self.assertIn(code,evidence['cause_codes'])

    def test_body_process_fields_do_not_become_header_evidence(self):
        for boundary in ('Sumário:','Texto Integral:'):
            result=extract_process_provenance(boundary+'\nProcesso:\n901/23.5T8XYZ.S1\n','copy.txt')
            self.assertEqual(result['process_provenance']['status'],'unresolved')


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'copy.txt';self.capture=self.root/'capture.html'
        self.text='Processo:\n901/23.ST8XYZ.P1.S1\nTexto Integral:\n'+PASSAGE
        self.source.write_text(self.text,encoding='utf-8')
        self.capture.write_text(html_capture('901/23.5T8XYZ.P1.S1'),encoding='utf-8')
        self.ref={'id':'synthetic-ref','text':PASSAGE,'entity':'AA','entity_start':0,'entity_end':2,'source_url':URL}

    def receipt(self):return dgsi.make_receipt(self.source,self.text,self.capture,URL,'synthetic-reviewer','Verified synthetic capture.',[self.ref],self.source.name)

    def verify(self,receipt=None):
        return dgsi.verify_receipt(receipt or self.receipt(),self.source,self.text,self.ref,
                    {(self.capture,'official_capture',preparation.file_hash(self.capture))})

    def test_verified_capture_supplies_identity_without_rewriting_copied_text(self):
        before=self.source.read_bytes();receipt=self.receipt();result=self.verify(receipt)
        self.assertEqual(result['decision_id'],'901/23.5T8XYZ.P1.S1')
        self.assertEqual(receipt['copied_unparsed_header_evidence'][0]['raw'],'901/23.ST8XYZ.P1.S1')
        self.assertEqual(self.source.read_bytes(),before)

    def test_capture_with_same_ambiguity_cannot_confirm_a_numeric_correction(self):
        self.capture.write_text(html_capture('901/23.ST8XYZ.P1.S1'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'capture_identity_not_verified'):self.receipt()

    def test_changed_snapshot_reference_url_and_unconfirmed_discrepancy_fail(self):
        receipt=self.receipt();receipt['identity_discrepancy_reviewed']=False
        with self.assertRaises(ValueError):self.verify(receipt)
        receipt=self.receipt();self.capture.write_text(html_capture('901/23.5T8XYZ.P1.S1',body=PASSAGE+' changed'),encoding='utf-8')
        with self.assertRaises(ValueError):self.verify(receipt)
        self.ref['source_url']=URL2;receipt=self.receipt()
        with self.assertRaisesRegex(ValueError,'official_url_conflict'):self.verify(receipt)

    def test_url_validation_rejects_unofficial_hosts_credentials_and_search_pages(self):
        for url in ('https://dgsi.pt.evil/jstj.nsf/'+('b'*32)+'?OpenDocument',
                    'https://synthetic-user:synthetic-password'+'@'+'www.dgsi.pt/jstj.nsf/'+('b'*32)+'?OpenDocument',
                    'https://www.dgsi.pt/jstj.nsf?SearchView'):
            with self.assertRaises(ValueError):dgsi.official_document_key(url)

    def test_plain_copy_without_origin_needs_matching_frozen_reference_url(self):
        self.capture=self.root/'capture.txt'
        self.capture.write_text('Processo:\n901/23.5T8XYZ.P1.S1\nTexto Integral:\n'+PASSAGE,encoding='utf-8')
        self.assertEqual(self.verify()['decision_id'],'901/23.5T8XYZ.P1.S1')
        del self.ref['source_url']
        with self.assertRaisesRegex(ValueError,'capture_origin_not_bound'):self.verify()

    def test_mhtml_origin_and_visible_text_exclude_script_identity(self):
        message=EmailMessage();message['Content-Location']=URL
        message.set_content(html_capture('901/23.5T8XYZ.P1.S1')+'<script>Processo: 99/99.0T8ZZZ.S1</script>',subtype='html',charset='utf-8')
        path=self.root/'capture.mhtml';path.write_bytes(message.as_bytes())
        text,origins=dgsi.read_capture(path)
        self.assertNotIn('99/99',text);self.assertIn(URL,origins)
        self.assertEqual(dgsi.capture_identity(text,path)['decision_id'],'901/23.5T8XYZ.P1.S1')

    def test_inline_markup_does_not_split_process_id_and_view_zero_is_same_document(self):
        source=html_capture('<b>901/23.</b><span>5T8XYZ.P1.S1</span>')
        self.capture.write_text(source,encoding='utf-8')
        self.assertEqual(self.verify()['decision_id'],'901/23.5T8XYZ.P1.S1')
        alternate='http://www.dgsi.pt/jstj.nsf/0/'+('b'*32)+'?OpenDocument'
        self.assertEqual(dgsi.official_document_key(alternate),dgsi.official_document_key(URL))

    def test_conflicting_valid_copy_header_and_missing_capture_context_fail(self):
        self.text='Processo: 903/23.5T8XYZ.P1.S2\nTexto Integral:\n'+PASSAGE
        self.source.write_text(self.text,encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'copied_identity_conflict'):self.verify()
        self.text='Processo: 901/23.ST8XYZ.P1.S1\nTexto Integral:\n'+PASSAGE
        self.source.write_text(self.text,encoding='utf-8')
        self.capture.write_text(html_capture('901/23.5T8XYZ.P1.S1',body='Other invented material.'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'context_not_in_both'):self.verify()

    def test_validate_decision_still_checks_corpus_family_overlap(self):
        rows,docs,texts=fixtures.corpus(2)
        receipt=self.receipt();receipt_path=self.root/'receipt.json';receipt_path.write_text(json.dumps(receipt),encoding='utf-8')
        decision={'human_confirmed':True,'reviewer':'synthetic-reviewer','reason':'Synthetic verified external evidence.',
                  'reference_sha256':protection.fingerprint(self.ref),'inventory_fingerprint':protection.fingerprint(docs),
                  'excluded_from_corpus':True,'evidence':[
                      {'kind':kind,'path':str(path),'sha256':preparation.file_hash(path)}for kind,path in
                      [('external_source',self.source),('official_capture',self.capture),('dgsi_identity_receipt',receipt_path)]]}
        proof=protection.match_reference(self.ref,protection.reference_index(docs,texts))
        with patch.object(protection,'RAW_ROOT',self.root):
            reserved,_=protection.validate_decision(decision,self.ref,docs,texts,proof)
            self.assertEqual(reserved,set())
            docs[0]['potential_process_group_ids']=['901/23.5T8XYZ']
            decision['inventory_fingerprint']=protection.fingerprint(docs)
            with self.assertRaisesRegex(ValueError,'not_disjoint'):
                protection.validate_decision(decision,self.ref,docs,texts,proof)
            # A known family must be reserved, including aliases. It cannot be
            # discharged as external, nor can a reservation omit a known peer.
            docs[1]['aliases']=[{'decision_id':'901/23.5T8XYZ.P1.S2'}]
            decision.update(excluded_from_corpus=False,document_ids=[docs[0]['document_id']],
                            inventory_fingerprint=protection.fingerprint(docs))
            with self.assertRaisesRegex(ValueError,'not_fully_reserved'):
                protection.validate_decision(decision,self.ref,docs,texts,proof)
            targets=[d['document_id']for d in docs];decision['document_ids']=targets
            packet=self.root/'packet.json'
            packet.write_text(json.dumps({'reference_sha256':protection.fingerprint(self.ref),'document_ids':targets,
                                          'document_source_hashes':{d['document_id']:d['source_text_sha256']for d in docs}}),encoding='utf-8')
            decision['evidence'].append({'kind':'reservation_packet','path':str(packet),'sha256':preparation.file_hash(packet)})
            reserved,_=protection.validate_decision(decision,self.ref,docs,texts,proof)
            self.assertEqual(reserved,set(targets))


class WizardTests(unittest.TestCase):
    def test_three_references_two_sources_wizard_then_protected_selection_30(self):
        fixture=fixtures.PilotBundleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        passages=[PASSAGE, 'BB confirmou acontecimentos absolutamente artificiais desta segunda passagem escrita apenas para testes.',
                  'CC identificou circunstâncias inteiramente artificiais de outro exemplo preparado só para testes.']
        copied=[fixture.root/'copy1.txt',fixture.root/'copy2.txt'];captures=[fixture.root/'capture1.html',fixture.root/'capture2.html']
        bodies=[passages[0]+'\n'+passages[1],passages[2]]
        for i in range(2):
            copied[i].write_text('Processo:\n'+('901/23.ST8XYZ.P1.S1' if i==0 else '902/2S.0T8ABC.S1')+'\nTexto Integral:\n'+bodies[i],encoding='utf-8')
            captures[i].write_text(html_capture('901/23.5T8XYZ.P1.S1' if i==0 else '902/25.0T8ABC.S1',bodies[i],URL if i==0 else URL2),encoding='utf-8')
        refs=[{'id':f'synthetic-gold-{i}','text':p,'entity':p[:2],'entity_start':0,'entity_end':2,'source_url':URL if i<2 else URL2}for i,p in enumerate(passages)]
        gold=fixture.root/'gold.jsonl';gold.write_text(''.join(json.dumps(r)+'\n'for r in refs),encoding='utf-8')
        binding=fixture.audit['validated_bundle'];binding['gold']={'path':str(gold),'sha256':preparation.file_hash(gold)}
        docs=load_lines(fixture.root/'inventory_documents.jsonl')
        decisions={}
        for i,ref in enumerate(refs):
            source=copied[0 if i<2 else 1]
            decisions['gold:'+ref['id']]={'human_confirmed':True,'reviewer':'synthetic','reason':'Original synthetic review.',
                   'reference_sha256':protection.fingerprint(ref),'inventory_fingerprint':protection.fingerprint(docs),
                   'excluded_from_corpus':True,'evidence':[{'kind':'external_source','path':str(source),'sha256':preparation.file_hash(source)}]}
        decision_path=fixture.root/'old_decisions.json';decision_path.write_text(json.dumps(decisions),encoding='utf-8')
        fixture.audit['unresolved_references']=list(decisions);fixture.audit['selection_complete']=False;fixture.write_manifest()
        before={p:p.read_bytes()for p in fixture.root.iterdir()if p.is_file()}
        output=fixture.root/'new_evidence';stdout=io.StringIO()
        replies=['synthetic reviewer','Identity checked against synthetic official captures.',str(captures[0]),URL,'CONFIRMO',str(captures[1]),URL2,'CONFIRMO']
        with (patch('sys.argv',['wizard','--selection-manifest',str(fixture.selection),'--decisions',str(decision_path),'--output-dir',str(output)]),
              patch.object(wizard,'private_file',side_effect=lambda p:Path(p).resolve()),
              patch.object(wizard,'private_new_output',side_effect=lambda p:p),patch.object(protection,'RAW_ROOT',fixture.root),
              patch.object(wizard,'GOLD_SHA',binding['gold']['sha256']),patch.object(wizard,'PILOT_SOURCES_SHA',binding['human_pilot']['sha256']),
              patch('builtins.input',side_effect=replies),redirect_stdout(stdout),redirect_stderr(io.StringIO())):
            wizard.main()
            updated=json.loads((output/'protection_decisions_PRIVATE.json').read_text())
            original=json.loads((fixture.root/'inventory_manifest.json').read_text())
            texts,_=preparation.validate_document_sources(docs,original)
            selected,audit=preparation.select_pilot(load_lines(fixture.root/'inventory_mentions.jsonl'),docs,texts,
                              {'gold':refs,'human_pilot':load_lines(fixture.root/'human_pilot.jsonl')},decisions=updated)
        self.assertEqual(json.loads(stdout.getvalue())['unresolved_reference_count'],0)
        self.assertEqual(json.loads(stdout.getvalue())['external_sources'],2)
        self.assertEqual(len(selected),30);self.assertTrue(audit['selection_complete'])
        self.assertTrue(all(p.read_bytes()==content for p,content in before.items()))
        self.assertNotIn(PASSAGE,stdout.getvalue());self.assertNotIn('901/',stdout.getvalue())


def load_lines(path):return [json.loads(line)for line in path.read_text(encoding='utf-8').splitlines()if line.strip()]


if __name__=='__main__':unittest.main()
