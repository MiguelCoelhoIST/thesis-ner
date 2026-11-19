"""Variable-size v3 runner; reuse the historical transport/parser/checkpoints.

Check-only never reads credentials or transmits. Real execution requires a NEW
explicit authorization bound to this capsule, prompt and actual record count.
"""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import iaedu_agent_api_19c as api
from src.annotation import prepare_batch_19c_v3 as batch
from src.annotation import run_iaedu_pilot_19c as historical
from src.annotation.import_claude_manual_19c import read_json
from src.annotation.prepare_role_annotation_batch import private_new_output

VERSION = '19c-iaedu-v3-variable-sequential-v1'


def authorization(path, digest, count, endpoint, channel):
    data = path.read_bytes()
    def invalid_constant(_): raise ValueError('invalid_authorization_json')
    value = json.loads(data.decode('utf-8'), object_pairs_hook=core.unique_keys, parse_constant=invalid_constant)
    if (not isinstance(value, dict) or value.get('version') != batch.VERSION
            or value.get('scope') != batch.AUTH_SCOPE or type(value.get('records')) is not int
            or value['records'] != count or value.get('prompt_version') != batch.prompt.VERSION
            or value.get('capsule_manifest_sha256') != digest
            or value.get('external_transmission_authorized') is not True
            or value.get('privacy_review_completed') is not True
            or value.get('endpoint') != endpoint or value.get('channel_id') != channel
            or not isinstance(value.get('approved_by'), str) or not value['approved_by'].strip()
            or not isinstance(value.get('approved_at'), str)):
        raise ValueError('explicit_batch_authorization_required')
    if datetime.fromisoformat(value['approved_at'].replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('authorization_timestamp_requires_timezone')
    return hashlib.sha256(data).hexdigest()


def update_summary(root, completed, state, binding):
    temporary = root/'silver_predictions.jsonl.tmp'
    with temporary.open('w', encoding='utf-8', newline='\n') as handle:
        for row in completed:
            handle.write(json.dumps(row, ensure_ascii=False)+'\n')
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, root/'silver_predictions.jsonl')
    summary = core.aggregate(completed); summary['cohort'] = batch.COHORT
    report = {'version': VERSION, 'expected_records': binding['records'],
              'prompt_version': batch.prompt.VERSION, 'state': state, 'summary': summary,
              'predictions_sha256': core.file_hash(root/'silver_predictions.jsonl'),
              'human_validated': False, 'requires_review': True, 'training_eligibility': 'NOT_ESTABLISHED'}
    historical.atomic_json(root/'run.json', report)
    return report


def execute(folder, digest, run_dir, auth_path, *, resume=False, session=None, agent_label='OpenAI GPT-5.5'):
    rows, manifest = batch.validate_capsule(folder, digest); count = len(rows)
    endpoint, channel = api.configuration()
    auth_sha = authorization(auth_path, digest, count, endpoint, channel)
    key = os.environ.get('IAEDU_API_KEY', '')
    if not key or key.strip() != key: raise ValueError('iaedu_api_key_env_required')
    if any(key in v for v in (agent_label, endpoint, channel)): raise ValueError('credential_in_configuration')
    auth_bytes = auth_path.read_bytes(); manifest_bytes = (folder/'portable_manifest_PRIVATE.json').read_bytes()
    if hashlib.sha256(auth_bytes).hexdigest() != auth_sha: raise ValueError('authorization_changed')
    if hashlib.sha256(manifest_bytes).hexdigest() != digest: raise ValueError('trusted_capsule_digest_mismatch')
    if key.encode() in auth_bytes: raise ValueError('credential_in_authorization')
    payloads = [(folder/m['request_file']).read_bytes() for m in manifest['mapping']]
    for data, item in zip(payloads, manifest['mapping']):
        if hashlib.sha256(data).hexdigest() != item['request_sha256']: raise ValueError('portable_file_changed')
        if key in data.decode('utf-8'): raise ValueError('credential_in_request')
    binding = {'version': VERSION, 'records': count, 'prompt_version': batch.prompt.VERSION,
               'prompt_configuration': manifest['prompt_configuration'],
               'capsule_manifest_sha256': digest, 'source_audit_sha256': manifest['source_audit_sha256'],
               'endpoint': endpoint, 'channel_id': channel, 'authorization_sha256': auth_sha,
               'agent_label_reported_by_user': agent_label, 'code_lf_sha256': manifest['code_lf_sha256']}
    root = run_dir.resolve()
    if resume:
        private_new_output(root/'__new_private_path_check__')
        if read_json(root/'binding.json') != binding: raise ValueError('resume_binding_mismatch')
        if (core.file_hash(root/'authorization_snapshot.json') != auth_sha
                or core.file_hash(root/'capsule_manifest_snapshot.json') != digest):
            raise ValueError('resume_snapshot_changed')
    else:
        root = private_new_output(root); root.mkdir(parents=True, mode=0o700)
        for data, name, sha in ((auth_bytes, 'authorization_snapshot.json', auth_sha),
                               (manifest_bytes, 'capsule_manifest_snapshot.json', digest)):
            with (root/name).open('xb') as handle:
                handle.write(data); handle.flush(); os.fsync(handle.fileno())
            if core.file_hash(root/name) != sha: raise ValueError('run_snapshot_source_changed')
        historical.atomic_json(root/'binding.json', binding)
        (root/'mentions').mkdir(mode=0o700)
    completed = []
    with historical.run_lock(root):
        if any(p.name not in {f'{n:03}' for n in range(1, count+1)} for p in (root/'mentions').iterdir()):
            raise ValueError('unexpected_mention_checkpoint')
        try:
            for ordinal, (record, item) in enumerate(zip(rows, manifest['mapping']), 1):
                batch.validate_capsule(folder, digest)
                if core.file_hash(auth_path) != auth_sha: raise ValueError('authorization_changed')
                if api.configuration() != (endpoint, channel): raise ValueError('iaedu_configuration_changed')
                slot = root/'mentions'/f'{ordinal:03}'; recovered = slot.exists()
                if not recovered:
                    slot.mkdir(mode=0o700)
                    data = payloads[ordinal-1]
                    with (slot/'request.txt').open('xb') as handle:
                        handle.write(data); handle.flush(); os.fsync(handle.fileno())
                    historical.atomic_json(slot/'attempt.json', {'id': record['id'], 'ordinal': ordinal,
                        'request_sha256': item['request_sha256'], 'state': 'dispatch_intent_never_auto_replay'})
                    api.stream_one(data.decode('utf-8'), slot/'transport', network_authorized=True,
                                   session=session, agent_label=agent_label)
                if core.file_hash(slot/'request.txt') != item['request_sha256']: raise ValueError('attempt_request_changed')
                result = historical.recover_result(slot, record, binding); completed.append(result)
                update_summary(root, completed, 'running', binding)
                print(f'IAedu v3 progress {ordinal}/{count}; parser_valid={result["llm_output_valid"]}; recovered={recovered}', flush=True)
        except (ValueError, KeyError, TypeError, OSError, KeyboardInterrupt):
            update_summary(root, completed, 'blocked_review_required', binding)
            raise
        return update_summary(root, completed, 'completed', binding)


def main():
    class SafeParser(argparse.ArgumentParser):
        def error(self, _): self.exit(2, '{"error_code":"invalid_arguments"}\n')
    parser = SafeParser(description=__doc__)
    parser.add_argument('--capsule-dir', type=Path, required=True)
    parser.add_argument('--expected-manifest-sha256', required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check-only', action='store_true'); modes.add_argument('--execute', action='store_true')
    parser.add_argument('--run-dir', type=Path); parser.add_argument('--authorization', type=Path)
    parser.add_argument('--resume', action='store_true'); parser.add_argument('--agent-label', default='OpenAI GPT-5.5')
    args = parser.parse_args(); os.umask(0o077)
    try:
        if args.check_only:
            rows, _ = batch.validate_capsule(args.capsule_dir, args.expected_manifest_sha256)
            print(json.dumps({'records': len(rows), 'integrity': 'PASS', 'network_calls': 0,
                'external_transmission_authorized': False, 'source_corpus_rechecked_on_windows': False}))
            return
        if args.run_dir is None or args.authorization is None: raise ValueError('explicit_batch_authorization_required')
        report = execute(args.capsule_dir, args.expected_manifest_sha256, args.run_dir, args.authorization,
                         resume=args.resume, agent_label=args.agent_label)
        print(json.dumps({'state': report['state'], 'expected_records': report['expected_records'], 'summary': report['summary']}))
    except (ValueError, KeyError, TypeError, OSError, KeyboardInterrupt) as exc:
        safe = {'explicit_batch_authorization_required', 'dispatch_outcome_unknown_review_required',
                'transport_failure_review_required', 'another_runner_is_active', 'resume_binding_mismatch',
                'trusted_capsule_digest_mismatch', 'portable_code_mismatch'}
        parser.exit(1, json.dumps({'error_code': str(exc) if str(exc) in safe else 'iaedu_v3_batch_integrity_or_state_failure'})+'\n')


if __name__ == '__main__':
    main()
