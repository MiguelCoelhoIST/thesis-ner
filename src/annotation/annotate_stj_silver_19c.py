"""Local Qwen3 pilot of exactly 30 source-bound PER occurrences, never gold."""

import argparse
import copy
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0, str(ROOT))
from src.annotation.annotate_role_candidates_qwen import load_local_qwen, unique_keys, write_new_json
from src.annotation.plan_inventory_batches import check_unannotated, file_hash, load_bound_inventory
from src.annotation.prepare_role_annotation_batch import private_new_output
from src.annotation.prepare_stj_pilot_19c import COHORT
from src.data.map_role_taxonomy import load_jsonl, load_taxonomy
from src.utils.entity_marking import mark_entity

PROMPT_VERSION = '19c-v1'
PROMPT_PATH = ROOT/'config/prompts/role_annotation_19c_v1.txt'
TAXONOMY = ROOT/'config/role_taxonomy_v2.json'
LABELS, _ = load_taxonomy(TAXONOMY)
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding='utf-8')
SCOPES = ('current_proceeding', 'cited_proceeding', 'both', 'uncertain', 'not_applicable')


def build_messages(record):
    check_unannotated(record)
    text = record['text'];a, b = record['entity_start'], record['entity_end']
    marked = mark_entity(text, a, b)
    if text[a:b] != record['entity'] or '[ENTITY]' in text or '[/ENTITY]' in text:
        raise ValueError('invalid_target_or_existing_markers')
    return [{'role':'system', 'content':SYSTEM_PROMPT}, {'role':'user', 'content':marked}]


def parse_response(raw, text):
    def invalid_constant(_):raise ValueError('non_json_constant')
    try:
        obj = json.loads(raw, object_pairs_hook=unique_keys, parse_constant=invalid_constant)
    except (ValueError, TypeError):return None, ['invalid_json']
    required = {'status', 'assignments', 'other_roles', 'uncertain', 'uncertainty_reason'}
    if not isinstance(obj, dict) or set(obj) != required:return obj, ['invalid_schema']
    errors = []
    status = obj['status'];uncertain = obj['uncertain'];reason = obj['uncertainty_reason']
    if status not in ('supported', 'ambiguous', 'insufficient', 'invalid_entity'):errors.append('invalid_status')
    if type(uncertain) is not bool:errors.append('uncertain_not_boolean')
    if (not isinstance(reason, str) or len(reason) > 300 or
            (uncertain is True and not reason.strip()) or (uncertain is False and reason != '')):
        errors.append('invalid_uncertainty_reason')
    if status != 'supported' and uncertain is not True:errors.append('abstention_requires_uncertainty')
    if not isinstance(obj['assignments'], list) or not isinstance(obj['other_roles'], list):
        return obj, errors + ['assignments_and_other_roles_must_be_lists']
    if status == 'supported' and not obj['assignments']:errors.append('supported_without_assignment')
    if status in ('insufficient', 'invalid_entity') and (obj['assignments'] or obj['other_roles']):
        errors.append('abstention_with_assignments')
    seen = set()
    for field, role_key in [('assignments', 'label'), ('other_roles', 'role')]:
        for item in obj[field]:
            if not isinstance(item, dict) or set(item) != {role_key, 'evidence', 'quote', 'scope'}:
                errors.append('invalid_assignment_schema');continue
            label = item[role_key];quote = item['quote'];scope = item['scope'];mode = item['evidence']
            if not isinstance(label, str):errors.append('invalid_role');continue
            if (field == 'assignments' and label not in LABELS) or (field == 'other_roles' and
                    (not label.strip() or len(label) > 80 or label.upper() in LABELS or label not in text)):
                errors.append('invalid_role')
            key = (field, label.casefold())
            if key in seen:errors.append('duplicate_role')
            seen.add(key)
            if scope not in SCOPES:errors.append('invalid_scope')
            if scope == 'uncertain' and uncertain is not True:errors.append('uncertain_scope_not_flagged')
            if field == 'assignments' and label == 'UNKNOWN':
                if (mode, quote, scope) != ('not_applicable', '', 'not_applicable'):
                    errors.append('invalid_unknown_evidence')
                if uncertain is not False or status != 'supported':errors.append('unknown_is_not_uncertainty')
            else:
                if mode not in ('explicit', 'inferred'):errors.append('invalid_evidence')
                if not isinstance(quote, str) or not quote.strip() or len(quote) > 240 or quote not in text:
                    errors.append('evidence_not_exact_short_substring')
                if field == 'assignments' and ((label == 'REFERENCE') != (scope == 'not_applicable')):
                    errors.append('scope_category_mismatch')
    if ('assignments', 'unknown') in seen and len(obj['assignments']) != 1:errors.append('unknown_not_exclusive')
    return obj, sorted(set(errors))


def proposal(record, raw, config, error=None):
    response, errors = (None, [error]) if error else parse_response(raw, record['text'])
    row = copy.deepcopy(record)
    valid = not errors
    row.update(annotation_tier='SILVER', annotation_source='Qwen/Qwen3-8B', human_validated=False,
               proposed_labels=[label for label in LABELS if valid and any(i['label'] == label for i in response['assignments'])],
               proposed_other_roles=response['other_roles'] if valid else [], llm_response=response,
               llm_raw_output=raw, llm_output_valid=valid, parsing_errors=errors,
               llm_config=copy.deepcopy(config), requires_review=True)
    return row


def load_pilot(input_path, selection_path):
    manifest = json.loads(selection_path.read_text(encoding='utf-8'))
    if manifest.get('selection_complete') is not True or file_hash(input_path) != manifest.get('pilot_input_sha256'):
        raise ValueError('pilot_input_manifest_mismatch')
    if not {'input', 'inventory_manifest', 'documents', 'ner_predictions', 'gold', 'human_pilot'} <= manifest['validated_bundle'].keys():
        raise ValueError('incomplete_pilot_source_binding')
    for item in manifest['validated_bundle'].values():
        if file_hash(Path(item['path'])) != item['sha256']:raise ValueError('pilot_source_changed')
    original_rows, _, _, _ = load_bound_inventory(Path(manifest['validated_bundle']['input']['path']),
                                                 Path(manifest['validated_bundle']['inventory_manifest']['path']))
    originals = {r['id']:r for r in original_rows}
    rows = load_jsonl(input_path)
    if len(rows) != 30 or [r['id'] for r in rows] != manifest['selected_ids'] or len({r['id'] for r in rows}) != 30:
        raise ValueError('expected_30_distinct_selected_ids')
    groups = set()
    for row in rows:
        build_messages(row)
        if row['id'] not in originals or any(row.get(k) != v for k, v in originals[row['id']].items()):
            raise ValueError('pilot_original_metadata_or_context_mismatch')
        selection = row['pilot_selection']
        if (row.get('cohort') != COHORT or manifest.get('cohort') != COHORT or
                selection['eligibility'] != 'explicit_protection_recheck_passed_exploratory_only' or
                selection['planning_group_id'] in groups or manifest.get('unresolved_references')):
            raise ValueError('pilot_cohort_or_protection_mismatch')
        groups.add(selection['planning_group_id'])
    return rows


def aggregate(rows):
    valid = [r for r in rows if r['llm_output_valid']]
    return {'records':len(rows), 'valid_outputs':len(valid), 'invalid_outputs':len(rows)-len(valid),
            'status_counts':dict(Counter(r['llm_response']['status'] for r in valid)),
            'proposed_label_counts_NOT_gold':dict(Counter(label for r in valid for label in r['proposed_labels'])),
            'multilabel':sum(len(r['proposed_labels']) > 1 for r in valid),
            'uncertain':sum(r['llm_response']['uncertain'] for r in valid),
            'other_role_assignments':sum(len(r['proposed_other_roles']) for r in valid),
            'parsing_error_counts':dict(Counter(e for r in rows for e in r['parsing_errors'])),
            'human_validated':False, 'cohort':COHORT}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--selection-manifest', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--revision', required=True, help='Immutable locally cached 40-hex model commit')
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--preflight-run', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('CUDA_VISIBLE_DEVICES'):
        parser.error('Qwen inference/model preflight requires an authorized Slurm GPU allocation.')
    if not re.fullmatch('[0-9a-f]{40}', args.revision):parser.error('Use an immutable cached model revision.')
    try:
        output = private_new_output(args.run_dir)
        rows = load_pilot(args.input, args.selection_manifest)
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(1, 'Pilot inputs/protection binding invalid; no private values printed.\n')
    config = {'experiment':'19c', 'model':'Qwen/Qwen3-8B', 'revision':args.revision, 'seed':42,
              'prompt_version':PROMPT_VERSION, 'prompt_sha256':file_hash(PROMPT_PATH),
              'taxonomy_sha256':file_hash(TAXONOMY), 'script_sha256':file_hash(Path(__file__)),
              'loader_sha256':file_hash(ROOT/'src/annotation/annotate_role_candidates_qwen.py'),
              'input_sha256':file_hash(args.input), 'selection_sha256':file_hash(args.selection_manifest),
              'do_sample':False, 'temperature':0.0, 'enable_thinking':False,
              'max_new_tokens':1024, 'max_input_tokens':4096, 'batch_size':1, 'local_files_only':True,
              'torch_dtype':'float16'}
    if not args.preflight_only:
        if args.preflight_run is None:parser.error('Run and inspect a GPU preflight first.')
        previous = json.loads(args.preflight_run.read_text(encoding='utf-8'))
        if previous.get('status') != 'preflight_passed' or previous.get('configuration') != config:
            parser.error('Preflight configuration/data/code mismatch.')
    output.mkdir(parents=True)
    run = {'configuration':config, 'status':'initializing', 'Slurm_job_id':os.environ['SLURM_JOB_ID']}
    generated = [];started = time.perf_counter()
    try:
        model, tokenizer, exp17, environment = load_local_qwen(args.revision, seed=42, inference_dtype='float16')
        run['environment'] = environment
        if environment['resolved_model_revision'] != args.revision:
            raise ValueError('resolved_checkpoint_mismatch')
        if not args.preflight_only and any(previous['environment'].get(k) != environment.get(k) for k in
                ('torch', 'transformers', 'resolved_model_revision', 'tokenizer_commit', 'chat_template_sha256')):
            raise ValueError('preflight_runtime_mismatch')
        encoded = []
        for row in rows:
            prompt = exp17.render_prompt(tokenizer, build_messages(row))
            inputs = tokenizer([prompt], return_tensors='pt', padding=True, truncation=False)
            tokens = inputs['input_ids'].shape[1]
            if tokens > config['max_input_tokens'] or tokens+config['max_new_tokens'] > model.config.max_position_embeddings:
                raise ValueError('context_limit_exceeded_no_truncation')
            encoded.append(inputs)
        run['input_token_counts'] = [i['input_ids'].shape[1] for i in encoded]
        if args.preflight_only:
            run['status'] = 'preflight_passed'
        else:
            with (output/'silver_predictions.jsonl').open('x', encoding='utf-8') as handle:
                for index, (row, inputs) in enumerate(zip(rows, encoded), 1):
                    inputs = inputs.to(exp17.model_input_device(model))
                    with exp17.torch.inference_mode():
                        result = model.generate(**inputs, max_new_tokens=config['max_new_tokens'],
                            do_sample=False, temperature=0.0, pad_token_id=tokenizer.pad_token_id,
                            eos_token_id=tokenizer.eos_token_id)
                    new_tokens = result[:, inputs['input_ids'].shape[1]:]
                    raw = tokenizer.batch_decode(new_tokens, skip_special_tokens=True)[0]
                    error = 'generation_token_limit_reached' if new_tokens.shape[1] >= config['max_new_tokens'] else None
                    prediction = proposal(row, raw, config, error)
                    generated.append(prediction)
                    handle.write(json.dumps(prediction, ensure_ascii=False)+'\n');handle.flush();os.fsync(handle.fileno())
                    print(f'Pilot progress {index}/30; valid {sum(r["llm_output_valid"] for r in generated)}', flush=True)
            run['status'] = ('completed' if all(r['llm_output_valid'] for r in generated)
                             else 'completed_with_invalid_outputs') if len(generated) == 30 else 'incomplete'
    except Exception as exc:
        code = str(exc) if str(exc) in ('resolved_checkpoint_mismatch', 'preflight_runtime_mismatch',
                                       'context_limit_exceeded_no_truncation', 'cuda_unavailable') else 'local_preflight_or_inference_failure'
        run.update(status='failed', error_type=type(exc).__name__, error_code=code)
    finally:
        run['elapsed_seconds'] = time.perf_counter()-started
        run['summary'] = aggregate(generated)
        run['input_unchanged'] = file_hash(args.input) == config['input_sha256']
        run['selection_unchanged'] = file_hash(args.selection_manifest) == config['selection_sha256']
        if (output/'silver_predictions.jsonl').exists():
            run['predictions_sha256'] = file_hash(output/'silver_predictions.jsonl')
        write_new_json(output/'run.json', run)
        write_new_json(output/'aggregate.json', {'status':run['status'], 'summary':run['summary'],
                                              'elapsed_seconds':run['elapsed_seconds']})
        print(json.dumps({'status':run['status'], 'summary':run['summary']}))
    if run['status'] not in ('preflight_passed', 'completed') or not run['input_unchanged'] or not run['selection_unchanged']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
