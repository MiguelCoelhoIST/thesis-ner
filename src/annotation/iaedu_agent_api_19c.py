"""IAedu adapter: offline plans or ONE fixed, invented connection probe.

Based on the supplied form example and IAedu's official Python example. No
OpenAI SDK/model name is assumed. Never log request headers or exception text.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
import uuid

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import annotate_stj_silver_19c_target_first as prompt
from src.annotation.import_claude_manual_19c import validated_package
from src.annotation.annotate_role_candidates_qwen import unique_keys, write_new_json
from src.annotation.prepare_role_annotation_batch import private_new_output

VERSION='19c-iaedu-agent-api-v3-checkpoints'
OFFICIAL_EXAMPLE='https://docs.iaedu.pt/books/funcionalidade-api/page/exemplo-python'
SYNTHETIC_TEXT='AA, pessoa fictícia, foi ouvida como testemunha num processo inteiramente inventado.'


def configuration():
    endpoint=os.environ.get('IAEDU_ENDPOINT','');channel=os.environ.get('IAEDU_CHANNEL_ID','')
    parsed=urlsplit(endpoint)
    if (parsed.scheme!='https' or parsed.hostname!='api.iaedu.pt' or parsed.port is not None
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not re.fullmatch(r'/agent-chat/{1,2}api/v1/agent/[A-Za-z0-9_-]+/stream',parsed.path)
            or not re.fullmatch(r'[A-Za-z0-9_-]+',channel)):
        raise ValueError('iaedu_endpoint_and_channel_required')
    return endpoint,channel


def form_fields(message,channel):
    # A new UUID at EVERY call: never a module-level/session/example thread ID.
    return {'channel_id':channel,'thread_id':str(uuid.uuid4()),'user_info':'{}','message':message}


def prepare_plan(folder,output_dir,agent_label='OpenAI GPT-5.5'):
    """Private preview, no API key required/read and no transmission possible."""
    output=private_new_output(output_dir);endpoint,channel=configuration()
    manifest_path=folder/'manifest_PRIVATE.json';before=core.file_hash(manifest_path)
    rows,manifest=validated_package(folder);previews=[]
    for item,record in zip(manifest['mapping'],rows):
        message=(folder/item['manual_text_file']).read_bytes().decode('utf-8')
        fields=form_fields(message,channel)
        previews.append({'ordinal':item['ordinal'],'id':record['id'],
                         'message_sha256':item['manual_text_sha256'],'fields':fields})
    if len({p['fields']['thread_id'] for p in previews})!=30:raise ValueError('iaedu_duplicate_threads')
    validated_package(folder)
    if before!=core.file_hash(manifest_path):raise ValueError('iaedu_package_changed')
    output.mkdir(parents=True,mode=0o700)
    report={'version':VERSION,'mode':'OFFLINE_PREVIEW_ONLY','endpoint':endpoint,
            'agent_label_reported_by_user':agent_label,'backend_model_identity':'NOT_VERIFIED',
            'package_path':str(folder.resolve()),'package_manifest_sha256':before,
            'adapter_sha256':core.file_hash(Path(__file__)),'official_example':OFFICIAL_EXAMPLE,
            'requests':previews,'thread_policy':'new_uuid4_per_request; preview_UUIDs_not_for_live_reuse',
            'auth_env_name':'IAEDU_API_KEY','generation_controls_requested':{},
            'external_transmission_authorized':False,'LLM_calls':0,'human_validated':False,'requires_review':True}
    write_new_json(output/'api_plan_PRIVATE.json',report)
    return report


def decode_json_lines(body):
    """Official framing: JSON lines, type=token/content. Keep ALL frames/raw."""
    events=[];errors=[];tokens=[]
    try:lines=body.decode('utf-8').splitlines()
    except UnicodeDecodeError:return {'events':[],'errors':['invalid_utf8'],'assistant_output':None}
    def invalid_constant(_):raise ValueError('non_json_constant')
    for ordinal,line in enumerate(lines,1):
        if not line.strip():continue
        try:event=json.loads(line,object_pairs_hook=unique_keys,parse_constant=invalid_constant)
        except (ValueError,TypeError):
            errors.append({'line':ordinal,'code':'unexpected_stream_frame'});continue
        events.append(event)  # Includes unknown metadata, usage, errors, model IDs.
        if not isinstance(event,dict):
            errors.append({'line':ordinal,'code':'unexpected_stream_object'});continue
        if event.get('type')=='token':
            if isinstance(event.get('content'),str):tokens.append(event['content'])
            else:errors.append({'line':ordinal,'code':'invalid_token_content'})
        if event.get('type') in ('error','failed') or event.get('error') is not None:
            errors.append({'line':ordinal,'code':'api_error_frame'})
    if not tokens:errors.append('no_assistant_tokens')
    return {'events':events,'errors':errors,'assistant_output':''.join(tokens) if tokens else None}


def stream_one(message,output_dir,*,network_authorized=False,session=None,agent_label='OpenAI GPT-5.5'):
    """Transport primitive; the CLI only invokes it for the fixed invented probe.

    No retry/redirect or shared thread. Preserve even failed/partial HTTP bodies.
    A boolean here is a caller contract, not a substitute for data authorization.
    """
    if network_authorized is not True:raise ValueError('iaedu_network_not_authorized')
    endpoint,channel=configuration();key=os.environ.get('IAEDU_API_KEY','')
    if not key or key.strip()!=key:raise ValueError('iaedu_api_key_env_required')
    if key in message or key in endpoint or key in channel or key in agent_label:
        raise ValueError('iaedu_credential_in_input')
    output=private_new_output(output_dir);fields=form_fields(message,channel)
    output.mkdir(parents=True,mode=0o700)
    write_new_json(output/'dispatch_intent.json',{
        'status':'intent_persisted_before_http','thread_id':fields['thread_id'],
        'endpoint':endpoint,'channel_id':channel,
        'message_sha256':hashlib.sha256(message.encode('utf-8')).hexdigest()})
    with (output/'dispatch_intent.json').open('r+b') as handle:os.fsync(handle.fileno())
    body=bytearray();status=None;headers={};transport_error=None;owned=False;response=None
    started=time.perf_counter()
    try:
        if session is None:
            import requests
            session=requests.Session();session.trust_env=False;owned=True
        # requests builds the multipart boundary. Do NOT set Content-Type alone.
        response=session.post(endpoint,headers={'x-api-key':key},
                              files={name:(None,value) for name,value in fields.items()},
                              stream=True,timeout=(10,120),allow_redirects=False)
        status=response.status_code;headers=dict(response.headers)
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:body.extend(chunk)
    except KeyboardInterrupt:
        transport_error='interrupted'
    except Exception:
        transport_error='transport_failure'  # Exception text can contain secrets.
    finally:
        if response is not None:
            try:response.close()
            except Exception:transport_error='transport_close_failure'
        if owned:
            try:session.close()
            except Exception:transport_error='transport_close_failure'
    raw=bytes(body);decoded=decode_json_lines(raw)
    # Refuse persistence if a server echoes the credential, even JSON-escaped.
    serialized=json.dumps({'headers':headers,'decoded':decoded},ensure_ascii=True).encode('utf-8')
    if key.encode('utf-8') in raw or key.encode('utf-8') in serialized:
        safe={'version':VERSION,'status':'failed','error_code':'credential_echo_detected',
              'http_status':status,'LLM_calls_attempted':1}
        write_new_json(output/'run.json',safe)
        return safe
    (output/'response_body.bin').write_bytes(raw)
    write_new_json(output/'stream_frames_PRIVATE.json',decoded)
    complete=transport_error is None and isinstance(status,int) and 200<=status<300 and not decoded['errors']
    if decoded['assistant_output'] is not None:
        (output/'assistant_output.txt').write_bytes(decoded['assistant_output'].encode('utf-8'))
    report={'version':VERSION,'status':'captured' if complete else 'captured_with_errors',
            'adapter_sha256':core.file_hash(Path(__file__)),
            'http_status':status,'response_headers':headers,'transport_error':transport_error,
            'request':{'endpoint':endpoint,'channel_id':channel,'thread_id':fields['thread_id'],'user_info':'{}',
                       'message_sha256':hashlib.sha256(message.encode('utf-8')).hexdigest()},
            'agent_label_reported_by_user':agent_label,'model_identity':'SEE_UNMODIFIED_API_EVENTS',
            'requested_generation_controls':{},'stream_errors':decoded['errors'],
            'body_sha256':hashlib.sha256(raw).hexdigest(),'body_representation':'requests_decoded_http_entity_bytes',
            'completion_evidence':'HTTP_EOF_ONLY_NO_DOCUMENTED_FINISH_EVENT',
            'elapsed_seconds':time.perf_counter()-started,
            'LLM_calls_attempted':1,'human_validated':False,'requires_review':True}
    write_new_json(output/'run.json',report)
    for path in output.iterdir():
        if path.is_file():
            with path.open('r+b') as handle:os.fsync(handle.fileno())
    return report


def returned_model_metadata(events,headers):
    """Select actual structured API fields, never infer model from assistant text."""
    keys={'model','modelid','modelname','modelversion','modelprovider','provider',
          'deployment','deploymentid','systemfingerprint'}
    found=[]
    def walk(value,path):
        if isinstance(value,dict):
            for key,item in value.items():
                if key.casefold() in {'content','text','message','messages'}:continue
                normalized=key.casefold().replace('_','').replace('-','')
                if normalized in keys and not isinstance(item,(dict,list)):
                    found.append({'source':path+'.'+key,'value':item})
                elif isinstance(item,(dict,list)):walk(item,path+'.'+key)
        elif isinstance(value,list):
            for index,item in enumerate(value):walk(item,f'{path}[{index}]')
    walk(events,'events')
    header_keys={'x-model','x-model-id','x-model-name','x-model-version','x-model-provider',
                 'openai-model','model','model-version','x-system-fingerprint'}
    for key,value in headers.items():
        if key.casefold() in header_keys:found.append({'source':'headers.'+key,'value':value})
    return found


def synthetic_connection_test(output_dir,*,session=None,agent_label='OpenAI GPT-5.5'):
    """One invented message, no file/message/package argument or pilot access."""
    record={'text':SYNTHETIC_TEXT,'entity':'AA','entity_start':0,'entity_end':2,
            'human_validated':False,'label':None}
    messages=prompt.build_messages(record)
    message='\n\n'.join(item['content'] for item in messages)
    report=stream_one(message,output_dir,network_authorized=True,session=session,agent_label=agent_label)
    folder=Path(output_dir)
    frames_path=folder/'stream_frames_PRIVATE.json'
    frames=json.loads(frames_path.read_text(encoding='utf-8')) if frames_path.is_file() else {}
    extracted=frames.get('assistant_output')
    metadata=returned_model_metadata(frames.get('events',[]),report.get('response_headers',{}))
    summary={'test':'FIXED_INVENTED_EXAMPLE_ONLY','status':report['status'],
             'http_status':report.get('http_status'),'error_code':report.get('error_code'),
             'assistant_message_extracted':isinstance(extracted,str) and bool(extracted.strip()),
             'stream_errors':report.get('stream_errors',[]),'transport_error':report.get('transport_error'),
             'model_metadata_returned':metadata,
             'model_metadata_status':'fields_found' if metadata else 'not_found_in_parsed_metadata',
             'real_pilot_read':False,'real_contexts_transmitted':False,
             'real_dataset_external_transmission_authorized':False,
             'output_dir':str(folder.resolve())}
    write_new_json(folder/'connection_test.json',summary)
    return summary


def main():
    class SafeParser(argparse.ArgumentParser):
        def error(self,_):self.exit(2,json.dumps({'error_code':'invalid_arguments'})+'\n')
    parser=SafeParser(description='Offline plan or a single FIXED INVENTED connection test; no real-pilot sending.')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--package-dir',type=Path)
    mode.add_argument('--synthetic-connection-test',action='store_true')
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--agent-label',default='OpenAI GPT-5.5')
    args=parser.parse_args();os.umask(0o077)
    try:
        if args.synthetic_connection_test:
            summary=synthetic_connection_test(args.output_dir,agent_label=args.agent_label)
            print(json.dumps(summary,ensure_ascii=True))
            if summary['status']!='captured' or not summary['assistant_message_extracted']:raise SystemExit(1)
            return
        report=prepare_plan(args.package_dir,args.output_dir,args.agent_label)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        safe={'iaedu_endpoint_and_channel_required','iaedu_api_key_env_required','iaedu_credential_in_input'}
        parser.exit(1,json.dumps({'error_code':str(exc) if str(exc) in safe else 'iaedu_configuration_or_binding_failure'})+'\n')
    print(json.dumps({'mode':report['mode'],'records':len(report['requests']),
                      'external_transmission_authorized':False,'LLM_calls':0}))


if __name__=='__main__':main()
