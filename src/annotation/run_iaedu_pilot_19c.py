"""Sequential IAedu runner: explicit authorization, durable results, no blind replay.

An uncertain dispatch is blocked. Exactly-once server execution cannot be
guaranteed without an API idempotency contract; never auto-retry an unknown call.
"""

import argparse
from contextlib import contextmanager
import copy
import hashlib
from datetime import datetime
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import iaedu_agent_api_19c as api
from src.annotation.import_claude_manual_19c import read_json
from src.annotation import portable_iaedu_pilot_19c as portable
from src.annotation.prepare_role_annotation_batch import private_new_output

VERSION='19c-iaedu-sequential-v1'


def atomic_json(path,value):
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w',encoding='utf-8',newline='\n') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2);handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,path)


@contextmanager
def run_lock(folder):
    with (folder/'runner.lock').open('a+b') as handle:
        handle.seek(0,2)
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise ValueError('another_runner_is_active') from None
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle,fcntl.LOCK_UN)


def authorization(path,digest,endpoint,channel):
    data=path.read_bytes()
    def invalid_constant(_):raise ValueError('invalid_authorization_json')
    value=json.loads(data.decode('utf-8'),object_pairs_hook=core.unique_keys,parse_constant=invalid_constant)
    if (not isinstance(value,dict) or value.get('version')!='iaedu-pilot-authorization-v1' or value.get('scope')!='STJ_19C_30_IAEDU_API'
            or value.get('capsule_manifest_sha256')!=digest
            or value.get('external_transmission_authorized') is not True
            or value.get('privacy_review_completed') is not True
            or value.get('endpoint')!=endpoint or value.get('channel_id')!=channel
            or not isinstance(value.get('approved_by'),str) or not value['approved_by'].strip()
            or not isinstance(value.get('approved_at'),str)):
        raise ValueError('explicit_scoped_authorization_required')
    if datetime.fromisoformat(value['approved_at'].replace('Z','+00:00')).tzinfo is None:
        raise ValueError('authorization_timestamp_requires_timezone')
    return hashlib.sha256(data).hexdigest()


def recover_result(slot,record,binding):
    """Rebuild only from a durable successful transport; never resend."""
    if not (slot/'attempt.json').is_file():raise ValueError('dispatch_outcome_unknown_review_required')
    intent=read_json(slot/'attempt.json')
    if intent['id']!=record['id'] or core.file_hash(slot/'request.txt')!=intent['request_sha256']:
        raise ValueError('attempt_request_changed')
    capture=slot/'transport';run_path=capture/'run.json'
    if not run_path.is_file():raise ValueError('dispatch_outcome_unknown_review_required')
    report=read_json(run_path)
    if report.get('status')!='captured':raise ValueError('transport_failure_review_required')
    raw_path=capture/'response_body.bin'
    if core.file_hash(raw_path)!=report['body_sha256']:raise ValueError('captured_body_changed')
    decoded=api.decode_json_lines(raw_path.read_bytes())
    if decoded['errors'] or read_json(capture/'stream_frames_PRIVATE.json')!=decoded:
        raise ValueError('captured_frames_changed')
    raw=decoded['assistant_output']
    if raw is None or (capture/'assistant_output.txt').read_bytes()!=raw.encode('utf-8'):
        raise ValueError('assistant_output_changed')
    dispatch=read_json(capture/'dispatch_intent.json')
    if (report['request']['message_sha256']!=intent['request_sha256']
            or dispatch['message_sha256']!=intent['request_sha256']
            or dispatch['thread_id']!=report['request']['thread_id']
            or report['request']['endpoint']!=binding['endpoint']
            or report['request']['channel_id']!=binding['channel_id']):
        raise ValueError('transport_request_binding_changed')
    response,errors=core.parse_response(raw,record['text']);valid=not errors
    metadata=api.returned_model_metadata(decoded['events'],report['response_headers'])
    row=copy.deepcopy(record)
    row.update(annotation_tier='SILVER',annotation_source='IAedu agent API',human_validated=False,requires_review=True,
               llm_raw_output=raw,llm_response=response,llm_output_valid=valid,parsing_errors=errors,
               proposed_labels=[label for label in core.LABELS if valid and any(i['label']==label for i in response['assignments'])],
               proposed_other_roles=response['other_roles'] if valid else [],
               agent_label_reported_by_user=binding['agent_label_reported_by_user'],
               model_metadata_returned=metadata,
               backend_model_identity_status='metadata_returned_not_independently_verified' if metadata else 'not_found_in_parsed_metadata',
               api_thread_id=report['request']['thread_id'],capsule_manifest_sha256=binding['capsule_manifest_sha256'],
               execution_mode='iaedu_agent_api',semantic_review={'target_association':None,'proceeding_scope':None,
                                                             'additional_roles_and_abstention':None})
    prediction=slot/'prediction.json'
    if prediction.exists():
        if read_json(prediction)!=row:raise ValueError('saved_prediction_changed')
    else:atomic_json(prediction,row)
    hashes={str(path.relative_to(slot)):core.file_hash(path) for path in
            [slot/'attempt.json',slot/'request.txt',prediction,*sorted(capture.iterdir())] if path.is_file()}
    marker={'id':record['id'],'state':'completed','files':hashes}
    complete=slot/'complete.json'
    if complete.exists():
        if read_json(complete)!=marker:raise ValueError('completion_checkpoint_changed')
    else:atomic_json(complete,marker)
    return row


def update_summary(root,completed,state):
    temporary=root/'silver_predictions.jsonl.tmp'
    with temporary.open('w',encoding='utf-8',newline='\n') as handle:
        for row in completed:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
        handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,root/'silver_predictions.jsonl')
    report={'version':VERSION,'state':state,'summary':core.aggregate(completed),
            'predictions_sha256':core.file_hash(root/'silver_predictions.jsonl'),
            'human_validated':False,'requires_review':True,'training_eligibility':'NOT_ESTABLISHED'}
    atomic_json(root/'run.json',report)
    return report


def execute(folder,digest,run_dir,auth_path,*,resume=False,session=None,agent_label='OpenAI GPT-5.5'):
    rows,manifest=portable.validate_capsule(folder,digest)
    endpoint,channel=api.configuration();auth_sha=authorization(auth_path,digest,endpoint,channel)
    key=os.environ.get('IAEDU_API_KEY','')
    if not key or key.strip()!=key:raise ValueError('iaedu_api_key_env_required')
    if key in agent_label or key in endpoint or key in channel:raise ValueError('credential_in_configuration')
    auth_bytes=auth_path.read_bytes();manifest_bytes=(folder/'portable_manifest_PRIVATE.json').read_bytes()
    if hashlib.sha256(auth_bytes).hexdigest()!=auth_sha:raise ValueError('authorization_changed')
    if hashlib.sha256(manifest_bytes).hexdigest()!=digest:raise ValueError('trusted_capsule_digest_mismatch')
    if key.encode('utf-8') in auth_bytes:raise ValueError('credential_in_authorization')
    payloads=[(folder/item['request_file']).read_bytes() for item in manifest['mapping']]
    for item,data in zip(manifest['mapping'],payloads):
        if hashlib.sha256(data).hexdigest()!=item['request_sha256']:raise ValueError('portable_file_changed')
        if key in data.decode('utf-8'):
            raise ValueError('credential_in_request')
    binding={'version':VERSION,'capsule_manifest_sha256':digest,'endpoint':endpoint,'channel_id':channel,
             'authorization_sha256':auth_sha,'agent_label_reported_by_user':agent_label,
             'code_lf_sha256':manifest['code_lf_sha256']}
    root=run_dir.resolve()
    if resume:
        # Validate before creating a lock in any pre-existing directory.
        private_new_output(root/'__new_private_path_check__')
        if read_json(root/'binding.json')!=binding:raise ValueError('resume_binding_mismatch')
        if (core.file_hash(root/'authorization_snapshot.json')!=auth_sha
                or core.file_hash(root/'capsule_manifest_snapshot.json')!=digest):
            raise ValueError('resume_snapshot_changed')
    else:
        root=private_new_output(root);root.mkdir(parents=True,mode=0o700)
        for data,name,sha in ((auth_bytes,'authorization_snapshot.json',auth_sha),
                              (manifest_bytes,'capsule_manifest_snapshot.json',digest)):
            with (root/name).open('xb') as handle:
                handle.write(data);handle.flush();os.fsync(handle.fileno())
            if core.file_hash(root/name)!=sha:raise ValueError('run_snapshot_source_changed')
        atomic_json(root/'binding.json',binding);(root/'mentions').mkdir(mode=0o700)
    completed=[]
    with run_lock(root):
        (root/'mentions').mkdir(mode=0o700,exist_ok=True)
        if any(path.name not in {f'{n:03}' for n in range(1,31)} for path in (root/'mentions').iterdir()):
            raise ValueError('unexpected_mention_checkpoint')
        try:
            for ordinal,(record,item) in enumerate(zip(rows,manifest['mapping']),1):
                portable.validate_capsule(folder,digest)
                if core.file_hash(auth_path)!=auth_sha:raise ValueError('authorization_changed')
                if api.configuration()!=(endpoint,channel):raise ValueError('iaedu_configuration_changed')
                slot=root/'mentions'/f'{ordinal:03}'
                recovered=slot.exists()
                if not recovered:
                    slot.mkdir(mode=0o700)
                    data=payloads[ordinal-1]
                    with (slot/'request.txt').open('xb') as handle:
                        handle.write(data);handle.flush();os.fsync(handle.fileno())
                    atomic_json(slot/'attempt.json',{'id':record['id'],'ordinal':ordinal,
                                'request_sha256':item['request_sha256'],'state':'dispatch_intent_never_auto_replay'})
                    api.stream_one(data.decode('utf-8'),slot/'transport',network_authorized=True,
                                   session=session,agent_label=agent_label)
                if core.file_hash(slot/'request.txt')!=item['request_sha256']:
                    raise ValueError('attempt_request_changed')
                row=recover_result(slot,record,binding);completed.append(row)
                update_summary(root,completed,'running')
                print(f'IAedu progress {ordinal}/30; parser_valid={row["llm_output_valid"]}; recovered={recovered}',flush=True)
        except (ValueError,KeyError,TypeError,OSError,KeyboardInterrupt):
            update_summary(root,completed,'blocked_review_required')
            raise
        return update_summary(root,completed,'completed')


def main():
    class SafeParser(argparse.ArgumentParser):
        def error(self,_):self.exit(2,'{"error_code":"invalid_arguments"}\n')
    parser=SafeParser(description=__doc__)
    parser.add_argument('--capsule-dir',type=Path,required=True)
    parser.add_argument('--expected-manifest-sha256',required=True)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check-only',action='store_true');modes.add_argument('--execute',action='store_true')
    parser.add_argument('--run-dir',type=Path);parser.add_argument('--authorization',type=Path)
    parser.add_argument('--resume',action='store_true');parser.add_argument('--agent-label',default='OpenAI GPT-5.5')
    args=parser.parse_args();os.umask(0o077)
    try:
        if args.check_only:
            rows,_=portable.validate_capsule(args.capsule_dir,args.expected_manifest_sha256)
            print(json.dumps({'records':len(rows),'integrity':'PASS','network_calls':0,
                              'source_corpus_rechecked_on_windows':False,'external_transmission_authorized':False}));return
        if args.run_dir is None or args.authorization is None:raise ValueError('explicit_scoped_authorization_required')
        report=execute(args.capsule_dir,args.expected_manifest_sha256,args.run_dir,args.authorization,
                       resume=args.resume,agent_label=args.agent_label)
        print(json.dumps({'state':report['state'],'summary':report['summary']}))
    except (ValueError,KeyError,TypeError,OSError,KeyboardInterrupt) as exc:
        safe={'explicit_scoped_authorization_required','dispatch_outcome_unknown_review_required',
              'transport_failure_review_required','another_runner_is_active','resume_binding_mismatch',
              'trusted_capsule_digest_mismatch','portable_code_mismatch'}
        parser.exit(1,json.dumps({'error_code':str(exc) if str(exc) in safe else 'iaedu_batch_integrity_or_state_failure'})+'\n')


if __name__=='__main__':main()
