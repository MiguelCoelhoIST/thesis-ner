"""Diagnose a blocked private selection; stdout is counts/codes/keyed tokens only.

No NER, annotation, APIs or negative inference from unsuccessful searches.
The public JSON contains no private IDs, paths, excerpts, people or raw hashes.
The random HMAC key, mapping, evidence and adjudication template stay private.
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.annotation.plan_inventory_batches import file_hash, load_bound_inventory, validate_document_sources
from src.annotation.prepare_role_annotation_batch import private_new_output
from src.annotation.prepare_stj_pilot_19c import GOLD_SHA, PILOT_SOURCES_SHA
from src.annotation.role_reference_provenance import (
    fingerprint, formatting_text, match_reference, reference_index, NORMALIZATION_VERSION,
)
from src.data.map_role_taxonomy import load_jsonl


def token(secret, namespace, value):
    return hmac.new(secret, (namespace+'\0'+value).encode('utf-8'), hashlib.sha256).hexdigest()


def word_set(text, entity):
    value = formatting_text(text)
    value = re.sub(r'(?<!\w)'+re.escape(formatting_text(entity))+r'(?!\w)', ' target ', value)
    return set(re.findall(r'\w+', value))


def content_candidates(ref, rows, maximum=5):
    query = word_set(ref['text'], ref['entity'])
    if len(query) < 8:return []
    ranked = {}
    for row in rows:
        words = word_set(row['text'], row['entity'])
        common = len(query & words)
        score = common/len(query | words) if words else 0
        if common >= 6 and score >= .30:
            previous = ranked.get(row['document_id'])
            candidate = {'document_id':row['document_id'], 'mention_id':row['id'],
                         'context_id':row['context_id'], 'score_NOT_identity_proof':score}
            if previous is None or score > previous['score_NOT_identity_proof']:
                ranked[row['document_id']] = candidate
    return sorted(ranked.values(), key=lambda r:(-r['score_NOT_identity_proof'],r['document_id']))[:maximum]


def diagnose(selection, rows, documents, texts, protected, secret):
    if len(secret) != 32:raise ValueError('expected_private_256_bit_hmac_key')
    lookup = {name+':'+ref['id']:(name,ref) for name,refs in protected.items() for ref in refs}
    if len(lookup) != sum(len(refs) for refs in protected.values()):raise ValueError('duplicate_reference_ids')
    recorded = selection['protected_reference_checks']
    unresolved = selection['unresolved_references']
    if (len(set(unresolved)) != len(unresolved) or len(recorded) != len(lookup)
            or any(type(r.get('resolved')) is not bool for r in recorded)
            or set(lookup) != {r['reference'] for r in recorded}
            or set(unresolved) != {r['reference'] for r in recorded if r['resolved'] is False}):
        raise ValueError('selection_reference_inventory_mismatch')
    index = reference_index(documents, texts)
    public_rows, private_rows, template = [], [], {}
    causes = Counter();origins = Counter();reconciled = 0
    for key in unresolved:
        origin,ref = lookup[key];proof = match_reference(ref,index)
        if proof['roots'] or proof['legacy_matches']:
            raise ValueError('recorded_unresolved_status_not_reproducible')
        codes = ['NO_NORMALIZABLE_IDENTITY_ROOT', 'NO_LEGACY_SOURCE_ASSOCIATION', 'NO_LEGACY_VERBATIM_CONTEXT_MATCH']
        metadata = any(ref.get(field) for field in ('process_number','decision_id','process_group_id',
                                                    'decision_id_candidates','process_group_id_candidates'))
        codes.append('IDENTITY_METADATA_UNPARSEABLE' if metadata else 'IDENTITY_METADATA_ABSENT')
        codes.append('SOURCE_HASH_PRESENT_NO_MATCH' if ref.get('source_text_sha256') else 'SOURCE_HASH_ABSENT')
        codes.append('SOURCE_PAIR_PRESENT_NO_MATCH' if ref.get('source_file') and ref.get('source_document_id') else 'SOURCE_PAIR_INCOMPLETE')
        codes.append('DOCUMENT_ID_PRESENT_NO_LEGACY_LINK' if ref.get('document_id') else 'DOCUMENT_ID_ABSENT')
        if len(ref['text'].split()) < 5:codes.append('CONTEXT_TOO_SHORT_FOR_LEGACY_MATCH')
        matches = sorted(proof['methods'])
        candidates = [] if matches else content_candidates(ref,rows)
        if matches:
            codes.append('VERIFIABLE_CONSERVATIVE_RESERVATION');reconciled += 1
        else:
            codes.append('MANUAL_PROVENANCE_REQUIRED')
            if candidates:codes.append('WEAK_CONTENT_CANDIDATES_NOT_PROOF')
            template[key] = {'human_confirmed':False, 'reviewer':'', 'reason':'',
                             'reference_sha256':fingerprint(ref), 'inventory_fingerprint':fingerprint(documents),
                             'excluded_from_corpus':False, 'document_ids':[],
                             'evidence':[{'kind':'reservation_packet_OR_external_source', 'path':'', 'sha256':''}]}
        ref_token = token(secret,'reference',key)
        origin_code = 'GOLD' if origin == 'gold' else 'HUMAN_PILOT'
        origins[origin_code] += 1;causes.update(codes)
        public_rows.append({'reference_token':ref_token,'origin_code':origin_code,'cause_codes':codes,
                            'verified_match_count':len(matches), 'candidate_document_count':len(candidates),
                            'document_tokens':sorted(token(secret,'document',d) for d in matches),
                            'candidate_document_tokens':sorted(token(secret,'document',c['document_id']) for c in candidates)})
        private_rows.append({'reference_token':ref_token,'reference':key,'original_record':ref,
                             'matching_evidence':proof,'review_candidates_NOT_proof':candidates})
    public_rows.sort(key=lambda row:row['reference_token'])
    public = {'version':'19c-protection-diagnostic-v1','normalization_version':NORMALIZATION_VERSION,
              'counts':{'protected_references':len(lookup),'original_unresolved':len(unresolved),
                        'original_blocked_groups':len(selection['blocked_groups']),
                        'verifiable_reconciliations':reconciled,'manual_provenance_required':len(template),
                        'LLM_calls':0},
              'origin_counts':dict(origins),'cause_counts':dict(causes),'references':public_rows}
    return public, private_rows, template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection-manifest',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--hmac-key',type=Path,help='Optional existing PRIVATE 32-byte key, never share it')
    args = parser.parse_args();os.umask(0o077)
    try:
        output = private_new_output(args.output_dir)
        selection = json.loads(args.selection_manifest.read_text(encoding='utf-8'))
        binding = dict(selection['validated_bundle'])
        binding['blocked_selection'] = {'path':str(args.selection_manifest.resolve()),'sha256':file_hash(args.selection_manifest)}
        if binding['gold']['sha256'] != GOLD_SHA or binding['human_pilot']['sha256'] != PILOT_SOURCES_SHA:
            raise ValueError('protected_reference_fingerprint_mismatch')
        if any(file_hash(Path(item['path'])) != item['sha256'] for item in binding.values()):
            raise ValueError('diagnostic_inputs_changed')
        rows,documents,summary,_ = load_bound_inventory(Path(binding['input']['path']),Path(binding['inventory_manifest']['path']))
        if summary.get('inventory_complete') is not True:raise ValueError('complete_inventory_required')
        source_manifest = json.loads(Path(binding['inventory_manifest']['path']).read_text(encoding='utf-8'))
        texts,_ = validate_document_sources(documents,source_manifest)
        protected = {'gold':load_jsonl(Path(binding['gold']['path'])),
                     'human_pilot':load_jsonl(Path(binding['human_pilot']['path']))}
        if args.hmac_key:
            key_path = args.hmac_key.resolve(strict=True)
            if not key_path.is_relative_to((ROOT/'data/raw').resolve()):raise ValueError('hmac_key_must_stay_private')
            secret = key_path.read_bytes()
            binding['hmac_key'] = {'path':str(key_path),'sha256':file_hash(key_path)}
        else:secret = secrets.token_bytes(32)
        public, private, template = diagnose(selection,rows,documents,texts,protected,secret)
        if any(file_hash(Path(item['path'])) != item['sha256'] for item in binding.values()):
            raise ValueError('diagnostic_inputs_changed')
        output.mkdir(parents=True)
        if not args.hmac_key:
            with (output/'token_key_PRIVATE.bin').open('xb') as handle:handle.write(secret)
        for name,value in [('shareable_diagnostic.json',public),
                           ('reference_evidence_PRIVATE.json',{'validated_bundle':binding,'references':private}),
                           ('adjudication_template_PRIVATE.json',template)]:
            with (output/name).open('x',encoding='utf-8') as handle:json.dump(value,handle,ensure_ascii=False,indent=2)
        print(json.dumps(public,ensure_ascii=False))
    except (ValueError,KeyError,TypeError,OSError):
        parser.exit(1,'{"error_code":"DIAGNOSTIC_INPUT_VALIDATION_FAILED"}\n')


if __name__=='__main__':main()
