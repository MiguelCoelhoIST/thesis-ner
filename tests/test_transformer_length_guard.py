"""Synthetic regressions for BERT positional limits, not GPU accuracy tests.

Confirmed local Eduardo configuration: BERTimbau 512 positions; fast tokenizer
declares a huge sentinel; strided_spans.v1 uses 128 spaCy tokens/stride 96.
WordPiece expansion may therefore exceed 512 despite a short linguistic span.
The opt-in integration test uses local weights only, never court documents.
"""

import os
import re
import unittest
from collections import Counter
from types import SimpleNamespace

from src.utils.transformer_length_guard import install_length_guard, get_length_guard, refine_transformer_windows
from src.data.extract_role_candidates_v2 import detect_person_spans
from src.data.prepare_stj_corpus_inventory import full_windows, union_length


class Tokenizer:
    model_max_length = 10**30

    def num_special_tokens_to_add(self, pair=False):
        return 2

    def __call__(self, texts, **kwargs):
        assert kwargs['truncation'] is False
        assert kwargs['add_special_tokens'] is True
        return {'input_ids': [[0]*(sum(5 if c in '/§' else 1 for c in text)+2) for text in texts]}


class FakeNLP:
    pipe_names = ['transformer', 'ner']

    def __init__(self, limit=24):
        self.model=SimpleNamespace(attrs={'get_spans':lambda docs:[[doc]for doc in docs]},
            tokenizer=Tokenizer(), transformer=SimpleNamespace(config=SimpleNamespace(max_position_embeddings=limit),
            embeddings=SimpleNamespace(position_embeddings=SimpleNamespace(num_embeddings=limit))))
        self.seen=[]
        install_length_guard(self)

    def get_pipe(self, name):
        return SimpleNamespace(model=self.model)

    def make_doc(self, text):
        return SimpleNamespace(text=text)

    def pipe(self, texts, batch_size=4, n_process=1):
        for text in texts:
            doc=self.make_doc(text)
            self.model.attrs['get_spans']([doc])  # final guard before simulated BERT
            self.seen.append(text)
            doc.ents=[SimpleNamespace(start_char=m.start(),end_char=m.end(),text=m.group(),label_='PER')for m in re.finditer('AA BB',text)]
            for value in ('AA','BB'):
                if text.startswith(value) and not text.startswith('AA BB'):
                    doc.ents.append(SimpleNamespace(start_char=0,end_char=len(value),text=value,label_='PER'))
            yield doc


class TransformerLengthTests(unittest.TestCase):
    def test_model_limit_wins_over_tokenizer_sentinel_without_changing_it(self):
        nlp=FakeNLP(12);guard=get_length_guard(nlp)
        self.assertEqual(guard.limit,12)
        self.assertEqual(nlp.model.tokenizer.model_max_length,10**30)
        guard([nlp.make_doc('x'*10)])  # 10 + CLS/SEP = 12
        with self.assertRaisesRegex(ValueError,'13 WordPieces'):
            guard([nlp.make_doc('x'*11)])

    def test_dense_legal_citation_unicode_and_single_giant_token_cover_every_character(self):
        nlp=FakeNLP()
        for text in ('processo '+('/§'*200), 'x'*703, 'ção/§' *100):
            windows,report=refine_transformer_windows(text,nlp,[(0,len(text))])
            self.assertGreater(report['subdivisions'],0)
            self.assertGreater(report['maximum_original_wordpieces'],24)
            self.assertLessEqual(report['maximum_safe_wordpieces'],24)
            self.assertEqual(union_length(windows),len(text))
            self.assertTrue(all(a< b and 0<=a<b<=len(text)for a,b in windows))
            for a,b in windows:get_length_guard(nlp)([nlp.make_doc(text[a:b])])

    def test_overlap_keeps_exact_entity_offsets_and_deduplicates(self):
        text='q'*17+' AA BB '+'z'*80;nlp=FakeNLP();raw=[]
        windows=full_windows(text,60,20)
        found=detect_person_spans(text,nlp,windows=windows,prediction_sink=raw.append)
        a=text.index('AA BB')
        self.assertEqual(found,[(a,a+5,'AA BB')])
        self.assertGreater(sum(p['start']==a and p['end']==a+5 for p in raw),1)
        self.assertTrue(all(text[p['start']:p['end']]==p['text']for p in raw))

    def test_final_guard_refuses_unsafe_prevalidated_input(self):
        nlp=FakeNLP()
        with self.assertRaises(ValueError):
            detect_person_spans('x'*100,nlp,windows=[(0,100)],windows_prevalidated=True)
        self.assertEqual(nlp.seen,[])

    def test_partial_name_at_window_boundary_is_not_a_second_person(self):
        text='xxxx AA BB yyyy';nlp=FakeNLP();raw=[];stats=Counter()
        cut=text.index('BB')
        found=detect_person_spans(text,nlp,windows=[(0,len(text)),(cut,len(text))],
                                  prediction_sink=raw.append,stats=stats)
        self.assertEqual(found,[(5,10,'AA BB')])
        self.assertTrue(any(p['text']=='BB'and p['start']==cut for p in raw))
        self.assertEqual(stats['dropped_window_boundary'],1)

    def test_already_safe_windows_unchanged_and_real_short_limit_respected(self):
        nlp=FakeNLP(12)
        text='short text'
        windows,report=refine_transformer_windows(text,nlp,[(0,len(text))])
        self.assertEqual(windows,[(0,len(text))])
        self.assertEqual(report['maximum_safe_wordpieces'],12)
        self.assertEqual(report['subdivisions'],0)
        nlp.model.tokenizer.model_max_length=8
        nlp.model.attrs['get_spans']=get_length_guard(nlp).original
        self.assertEqual(install_length_guard(nlp)['effective_limit'],8)


@unittest.skipUnless(os.environ.get('THESIS_NER_INTEGRATION')=='1',
                     'Opt in with THESIS_NER_INTEGRATION=1 and local Eduardo weights')
class RealEduardoIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
        from src.data.extract_role_candidates_v2 import load_person_ner
        cls.nlp=load_person_ner(cpu_threads=4)

    def test_real_wordpiece_overflow_is_subdivided_and_bert_completes(self):
        # Artificial legal prose + difficult morphology; no real names or cases.
        text='A testemunha AA respondeu. '+('hiperconstitucionalizadíssimo '*150)+' A testemunha BB terminou.'
        guard=get_length_guard(self.nlp)
        _,before=guard.maximum_wordpieces([self.nlp.make_doc(text)])
        self.assertGreater(before,guard.limit)
        windows,report=refine_transformer_windows(text,self.nlp,full_windows(text))
        self.assertEqual(union_length(windows),len(text))
        self.assertLessEqual(report['maximum_safe_wordpieces'],guard.limit)
        raw=[];stats=Counter()
        accepted=detect_person_spans(text,self.nlp,windows=windows,windows_prevalidated=True,prediction_sink=raw.append,stats=stats)
        # NER accuracy on invented placeholders is not part of a length test.
        self.assertEqual(stats['ner_windows_processed'],len(windows))
        self.assertGreater(guard.maximum_checked,0)
        self.assertTrue(all(text[a:b]==entity for a,b,entity in accepted))
        self.assertLessEqual(guard.maximum_checked,guard.limit)
        # Prove the same physical BERT rejects the unchecked over-limit input.
        import torch
        inputs=self.nlp.get_pipe('transformer').model.tokenizer(['x '*guard.limit],return_tensors='pt',truncation=False)
        with torch.inference_mode(),self.assertRaises(RuntimeError):
            self.nlp.get_pipe('transformer').model.transformer(**inputs)


if __name__=='__main__':unittest.main()
