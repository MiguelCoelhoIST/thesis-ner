"""Offline audit of private review proposals against immutable original records.

No repairs, inference, semantic certification, or modification of source files.
Only aggregate counts/error codes are printed; the full audit stays in data/raw.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation.import_claude_manual_19c import read_json
from src.annotation.prepare_role_annotation_batch import private_new_output


def compact_fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def literal_spans(text, quote):
    if not isinstance(quote, str) or not quote:
        return []
    spans, start = [], 0
    while (start := text.find(quote, start)) != -1:
        spans.append({'start': start, 'end': start + len(quote)})
        start += 1
    return spans


def verify(review, originals, inputs):
    """Validate bindings, historical parser flags and every proposed quote offset."""
    if len({r['id'] for r in originals}) != len(originals) or len({r['id'] for r in inputs}) != len(inputs):
        raise ValueError('duplicate_original_id')
    if [r['id'] for r in originals] != [r['id'] for r in inputs]:
        raise ValueError('input_prediction_id_order_mismatch')
    for original, source in zip(originals, inputs):
        core.check_unannotated(source)
        core.build_messages(source)
        if (any(original.get(k) != v for k, v in source.items() if k != 'annotation_tier')
                or original.get('annotation_tier') != 'SILVER'
                or original.get('human_validated') is not False or original.get('requires_review') is not True):
            raise ValueError('original_input_metadata_mismatch')
        parsed, errors = core.parse_response(original['llm_raw_output'], original['text'])
        if (parsed != original['llm_response'] or errors != original['parsing_errors']
                or original['llm_output_valid'] != (not errors)):
            raise ValueError('historical_parser_flags_mismatch')
    reviews = review['reviews']
    if len({r['id'] for r in reviews}) != len(reviews):
        raise ValueError('duplicate_review_id')
    by_id = {r['id']: (i, r, inputs[i-1]) for i, r in enumerate(originals, 1)}
    results = []
    for item in reviews:
        errors = []
        if item['id'] not in by_id:
            results.append({'id': item['id'], 'errors': ['unknown_review_id']})
            continue
        ordinal, original, source = by_id[item['id']]
        text = original['text']
        if item['ordinal'] != ordinal:
            errors.append('ordinal_mismatch')
        if compact_fingerprint(original) != item['source_record_sha256']:
            errors.append('source_record_fingerprint_mismatch')
        if hashlib.sha256(text.encode('utf-8')).hexdigest() != item['source_context_sha256']:
            errors.append('context_fingerprint_mismatch')
        a, b = original['entity_start'], original['entity_end']
        if (type(a) is not int or type(b) is not int or not 0 <= a < b <= len(text)
                or text[a:b] != original['entity']
                or item['source_entity_span'] != {'start': a, 'end': b}):
            errors.append('entity_span_mismatch')
        parsed, old_errors = core.parse_response(original['llm_raw_output'], text)
        if (parsed != original['llm_response'] or old_errors != original['parsing_errors']
                or original['llm_output_valid'] != (not old_errors)
                or item['original_llm_raw_output'] != original['llm_raw_output']
                or item['original_response'] != parsed or item['original_parsing_errors'] != old_errors):
            errors.append('historical_output_mismatch')
        proposed = item['proposed_response']
        _, proposed_errors = core.parse_response(json.dumps(proposed, ensure_ascii=False), text)
        if proposed_errors or item['proposed_parser_errors'] != proposed_errors:
            errors.append('proposed_response_invalid')
        if type(item['changed']) is not bool or item['changed'] != (proposed != parsed):
            errors.append('changed_flag_mismatch')
        expected = [
            {'field': field, 'designation': assignment[key], 'quote': assignment['quote'],
             'context_matches': literal_spans(text, assignment['quote'])}
            for field, key in [('assignments', 'label'), ('other_roles', 'role')]
            for assignment in proposed.get(field, []) if assignment.get('quote')
        ]
        if item['evidence_source_spans'] != expected:
            errors.append('proposed_evidence_offsets_mismatch')
        if (item.get('human_validated') is not False or item.get('requires_review') is not True
                or item.get('training_eligibility') != 'NOT_ESTABLISHED'):
            errors.append('review_status_unsafe')
        results.append({'id': item['id'], 'ordinal': ordinal, 'errors': errors,
                        'source_record_sha256': compact_fingerprint(original),
                        'proposed_response': proposed, 'evidence_source_spans': expected,
                        'human_validated': False, 'requires_review': True,
                        'training_eligibility': 'NOT_ESTABLISHED'})
    summary = {'reviewed': len(reviews), 'verified': sum(not r['errors'] for r in results),
               'changed': sum(r['changed'] is True for r in reviews),
               'error_counts': dict(Counter(e for r in results for e in r['errors'])),
               'semantic_validation': 'PENDING_HUMAN_REVIEW', 'LLM_calls': 0}
    return results, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('review', 'predictions', 'run', 'input', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        output = private_new_output(args.output_dir)
        bindings = {k: core.file_hash(getattr(args, k)) for k in ('review', 'predictions', 'run', 'input')}
        review, run = read_json(args.review), read_json(args.run)
        if (bindings['predictions'] != review['source_predictions_sha256']
                or bindings['run'] != review['source_run_sha256']
                or run['predictions_sha256'] != bindings['predictions']
                or core.file_hash(Path(core.__file__)) != review['parser_script_sha256']):
            raise ValueError('review_source_binding_mismatch')
        if (review.get('human_validated') is not False or review.get('LLM_calls') != 0
                or review.get('changes_original_results') is not False
                or review.get('training_eligibility') != 'NOT_ESTABLISHED'):
            raise ValueError('review_status_unsafe')
        originals = [json.loads(line) for line in args.predictions.read_text(encoding='utf-8').splitlines()]
        inputs = [json.loads(line) for line in args.input.read_text(encoding='utf-8').splitlines()]
        results, summary = verify(review, originals, inputs)
        if core.aggregate(originals) != run['summary']:
            raise ValueError('historical_summary_mismatch')
        if (review['original_summary'] != {k: run['summary'][k] for k in
                ('records', 'valid_outputs', 'invalid_outputs')}
                or review['review_summary']['reviewed_cases'] != summary['reviewed']
                or review['review_summary']['changed_proposals'] != summary['changed']
                or review['review_summary']['confirmed_proposals'] != summary['reviewed'] - summary['changed']):
            raise ValueError('declared_review_summary_mismatch')
        summary['historical_records_reparsed'] = len(originals)
        if any(core.file_hash(getattr(args, k)) != sha for k, sha in bindings.items()):
            raise ValueError('inputs_changed_during_verification')
        output.mkdir(parents=True)
        (output/'verification_PRIVATE.json').write_text(json.dumps(
            {'bindings': bindings, 'summary': summary, 'reviews': results},
            ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(summary))
        return 0 if summary['verified'] == summary['reviewed'] else 1
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(1, 'review_verification_failed; inspect private inputs; no private content printed.\n')


if __name__ == '__main__':
    sys.exit(main())
