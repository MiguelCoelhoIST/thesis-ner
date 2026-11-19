"""Offline import of manually saved responses; no browser, API or inference.

Read UTF-8 bytes unchanged, reuse the historical strict parser, and leave all
semantic review pending. Never infer that permission to import authorizes upload.
"""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import annotate_stj_silver_19c_target_first as prompt
from src.annotation import prepare_second_llm_pilot_19c as package
from src.annotation.annotate_role_candidates_qwen import unique_keys, write_new_json
from src.annotation.prepare_role_annotation_batch import private_new_output
from src.annotation.role_reference_provenance import fingerprint

VERSION='19c-claude-manual-import-v1'


def read_json(path):
    def invalid_constant(_):raise ValueError('non_finite_json')
    return json.loads(path.read_bytes().decode('utf-8'),object_pairs_hook=unique_keys,parse_constant=invalid_constant)


def validate_session(path):
    session=read_json(path)
    required={'provider','model_display_name','model_version_or_identifier','platform','execution_mode',
              'message_delivery','fresh_chat_per_mention','generation_controls',
              'platform_instructions_or_tools','session_date','response_capture_method'}
    if not isinstance(session,dict) or not required<=session.keys():raise ValueError('session_metadata_required')
    for key in required-{'fresh_chat_per_mention'}:
        if (not isinstance(session[key],str) or not session[key].strip()
                or session[key]=='PENDING_CONFIRMATION'):
            raise ValueError('session_metadata_pending')
    if (session['provider']!='Anthropic' or session['execution_mode']!='manual_chat'
            or session['message_delivery'] not in ('single_user_message','separate_system_user')
            or session['fresh_chat_per_mention'] is not True):
        raise ValueError('manual_session_protocol_mismatch')
    return session


def validated_package(folder):
    manifest=read_json(folder/'manifest_PRIVATE.json')
    if manifest['version']!=package.VERSION or manifest['records']!=30:raise ValueError('wrong_package_version')
    paths={k:Path(v) for k,v in manifest['source_paths'].items()}
    if any(core.file_hash(path)!=manifest['source_hashes'][key] for key,path in paths.items()):
        raise ValueError('package_source_changed')
    if (paths['prompt'].resolve()!=prompt.PROMPT_PATH.resolve()
            or paths['taxonomy'].resolve()!=core.TAXONOMY.resolve()
            or paths['parser_and_pilot_validator'].resolve()!=Path(core.__file__).resolve()
            or manifest['source_hashes']['prompt']!=prompt.PROMPT_SHA256):
        raise ValueError('package_code_or_prompt_mismatch')
    rows=core.load_pilot(paths['input'],paths['selection'])
    messages_path=folder/'model_messages_PRIVATE.jsonl'
    if core.file_hash(messages_path)!=manifest['model_messages_sha256']:raise ValueError('messages_changed')
    requests=[json.loads(line,object_pairs_hook=unique_keys) for line in messages_path.read_text(encoding='utf-8').splitlines()]
    mapping=manifest['mapping']
    if (len(mapping)!=30 or len(requests)!=30
            or [m['ordinal'] for m in mapping]!=list(range(1,31))
            or [m['id'] for m in mapping]!=[r['id'] for r in rows]):
        raise ValueError('package_mapping_mismatch')
    for ordinal,(record,request,item) in enumerate(zip(rows,requests,mapping),1):
        messages=prompt.build_messages(record)
        if (request!={'messages':messages} or fingerprint(messages)!=item['messages_sha256']
                or fingerprint(record)!=item['record_sha256']
                or any(item[key]!=record[key] for key in ('document_id','source_text_sha256','entity_start','entity_end',
                       'entity_document_start','entity_document_end','context_document_start','context_document_end'))
                or record['pilot_selection'].get('training_eligibility')!='NOT_ESTABLISHED'):
            raise ValueError('package_record_or_messages_changed')
        for key,expected in (('manual_text_file',f'requests/{ordinal:03}.txt'),
                             ('structured_file',f'requests/{ordinal:03}.messages.json')):
            if item[key]!=expected:raise ValueError('package_request_path_mismatch')
        flat=folder/item['manual_text_file'];structured=folder/item['structured_file']
        if (core.file_hash(flat)!=item['manual_text_sha256'] or core.file_hash(structured)!=item['structured_sha256']
                or flat.read_bytes()!='\n\n'.join(m['content'] for m in messages).encode('utf-8')
                or read_json(structured)!={'messages':messages}):
            raise ValueError('manual_request_changed')
    return rows,manifest


def import_responses(folder,session_path,output_dir):
    output=private_new_output(output_dir)
    before={'manifest':core.file_hash(folder/'manifest_PRIVATE.json'),'session':core.file_hash(session_path)}
    session=validate_session(session_path);rows,manifest=validated_package(folder)
    response_dir=folder/'raw_responses'
    expected={f'{n:03}.txt' for n in range(1,31)}
    if {p.name for p in response_dir.iterdir() if p.is_file()}!=expected:
        raise ValueError('expected_exactly_30_raw_responses')
    results=[];raw_files=[]
    for ordinal,record in enumerate(rows,1):
        path=response_dir/f'{ordinal:03}.txt';raw_bytes=path.read_bytes()
        raw_sha=hashlib.sha256(raw_bytes).hexdigest()
        raw=raw_bytes.decode('utf-8')  # No stripping, newline conversion or fence repair.
        response,errors=core.parse_response(raw,record['text'])
        row=copy.deepcopy(record);valid=not errors
        row.update(annotation_tier='SILVER',annotation_source=session['model_display_name'],
                   annotation_provider=session['provider'],human_validated=False,requires_review=True,
                   llm_raw_output=raw,llm_response=response,llm_output_valid=valid,parsing_errors=errors,
                   proposed_labels=[label for label in core.LABELS if valid and any(
                       i['label']==label for i in response['assignments'])],
                   proposed_other_roles=response['other_roles'] if valid else [],
                   execution_metadata=copy.deepcopy(session),
                   manual_import={'ordinal':ordinal,'source_record_sha256':fingerprint(record),
                                  'raw_file':path.name,'raw_sha256':raw_sha,
                                  'request_sha256':manifest['mapping'][ordinal-1][
                                      'manual_text_sha256' if session['message_delivery']=='single_user_message' else 'structured_sha256']},
                   semantic_review={'target_association':None,'proceeding_scope':None,
                                    'additional_roles_and_abstention':None})
        results.append(row);raw_files.append((path,raw_bytes,row['manual_import']['raw_sha256']))
    validated_package(folder)
    if (before['manifest']!=core.file_hash(folder/'manifest_PRIVATE.json')
            or before['session']!=core.file_hash(session_path)
            or any(core.file_hash(path)!=sha for path,_,sha in raw_files)):
        raise ValueError('manual_import_source_changed')
    output.mkdir(parents=True,mode=0o700);(output/'raw_responses').mkdir(mode=0o700)
    for path,data,_ in raw_files:
        with (output/'raw_responses'/path.name).open('xb') as handle:handle.write(data)
    package.write_jsonl(output/'silver_predictions.jsonl',results)
    summary=core.aggregate(results)
    report={'version':VERSION,'status':'imported_with_invalid_outputs' if summary['invalid_outputs'] else 'imported',
            'summary':summary,'session':session,'source_hashes':before,
            'source_paths':{'package':str(folder.resolve()),'session':str(session_path.resolve())},
            'parser_sha256':core.file_hash(Path(core.__file__)),'importer_sha256':core.file_hash(Path(__file__)),
            'predictions_sha256':core.file_hash(output/'silver_predictions.jsonl'),
            'manual_responses_imported':len(results),'origin_execution_mode':'manual_chat',
            'LLM_calls':0,'human_validated':False,'requires_review':True,'training_eligibility':'NOT_ESTABLISHED'}
    write_new_json(output/'run.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('package-dir','session','output-dir'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:report=import_responses(args.package_dir,args.session,args.output_dir)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        safe={'session_metadata_required','session_metadata_pending','manual_session_protocol_mismatch',
              'expected_exactly_30_raw_responses','manual_import_source_changed'}
        parser.exit(1,json.dumps({'error_code':str(exc) if str(exc) in safe else 'manual_import_binding_failure'})+'\n')
    print(json.dumps({k:report[k] for k in ('status','summary','LLM_calls')}))


if __name__=='__main__':main()
