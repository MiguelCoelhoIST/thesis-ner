"""Build a PRIVATE blind 30-mention package; never call or select a model.

Only messages go to the annotator. IDs, provenance and empty comparison forms
stay in separate private files. No Qwen predictions/review are used as input.
"""

import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import annotate_stj_silver_19c_target_first as prompt
from src.annotation.annotate_role_candidates_qwen import unique_keys, write_new_json
from src.annotation.prepare_role_annotation_batch import private_new_output
from src.annotation.role_reference_provenance import fingerprint

VERSION='19c-second-llm-claude-manual-package-v2'


def write_jsonl(path,rows):
    with path.open('x',encoding='utf-8') as handle:
        for row in rows:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
        handle.flush();os.fsync(handle.fileno())


def prepare_package(input_path,selection_path,reference_run,output_dir):
    output=private_new_output(output_dir)
    paths={'input':input_path,'selection':selection_path,'reference_run':reference_run,
           'prompt':prompt.PROMPT_PATH,'taxonomy':core.TAXONOMY,
           'parser_and_pilot_validator':Path(core.__file__),'message_builder':Path(prompt.__file__),
           'packager':Path(__file__)}
    hashes={key:core.file_hash(path) for key,path in paths.items()}
    reference=json.loads(reference_run.read_text(encoding='utf-8'),object_pairs_hook=unique_keys)
    if (not isinstance(reference,dict) or not isinstance(reference.get('configuration'),dict)
            or not isinstance(reference.get('summary'),dict) or reference['summary'].get('records')!=30
            or reference.get('status') not in ('completed','completed_with_invalid_outputs')
            or reference.get('input_unchanged') is not True or reference.get('selection_unchanged') is not True
            or reference['configuration'].get('input_sha256')!=hashes['input']
            or reference['configuration'].get('selection_sha256')!=hashes['selection']
            or reference['configuration'].get('script_sha256')!=hashes['parser_and_pilot_validator']
            or reference['configuration'].get('taxonomy_sha256')!=hashes['taxonomy']):
        raise ValueError('reference_pilot_binding_mismatch')
    records=core.load_pilot(input_path,selection_path)
    if any(r['pilot_selection'].get('training_eligibility')!='NOT_ESTABLISHED' for r in records):
        raise ValueError('training_eligibility_not_established_required')
    if prompt.PROMPT_SHA256!=hashes['prompt']:
        raise ValueError('prompt_changed_after_import')
    requests=[];mapping=[];review=[];manual=[]
    for ordinal,record in enumerate(records,1):
        messages=prompt.build_messages(record)
        text='\n\n'.join(message['content'] for message in messages)
        manual.append((ordinal,text,messages))
        requests.append({'messages':messages})
        mapping.append({'ordinal':ordinal,'id':record['id'],'record_sha256':fingerprint(record),
                        'document_id':record['document_id'],'source_text_sha256':record['source_text_sha256'],
                        'entity_start':record['entity_start'],'entity_end':record['entity_end'],
                        'entity_document_start':record['entity_document_start'],
                        'entity_document_end':record['entity_document_end'],
                        'context_document_start':record['context_document_start'],
                        'context_document_end':record['context_document_end'],
                        'messages_sha256':fingerprint(messages)})
        review.append({'ordinal':ordinal,'id':record['id'],
                       'format_and_quotes':None,'target_association':None,'proceeding_scope':None,
                       'additional_roles_and_abstention':None,'role_claim_assessments':[],
                       'human_validated':False,'requires_review':True,'training_eligibility':'NOT_ESTABLISHED'})
    # Recheck source spans/protection before publishing; no NER/model inference.
    core.load_pilot(input_path,selection_path)
    if any(core.file_hash(path)!=hashes[key] for key,path in paths.items()):
        raise ValueError('package_source_changed')
    output.mkdir(parents=True,mode=0o700)
    (output/'requests').mkdir(mode=0o700)
    (output/'raw_responses').mkdir(mode=0o700)
    for ordinal,text,messages in manual:
        flat=output/'requests'/f'{ordinal:03}.txt'
        structured=output/'requests'/f'{ordinal:03}.messages.json'
        flat.write_bytes(text.encode('utf-8'))
        write_new_json(structured,{'messages':messages})
        mapping[ordinal-1].update(manual_text_file=f'requests/{flat.name}',manual_text_sha256=core.file_hash(flat),
                                  structured_file=f'requests/{structured.name}',structured_sha256=core.file_hash(structured))
    write_jsonl(output/'model_messages_PRIVATE.jsonl',requests)
    write_jsonl(output/'comparison_template_PRIVATE.jsonl',review)
    manifest={'version':VERSION,'records':len(records),'prompt_version':prompt.VERSION,
              'source_paths':{k:str(p.resolve()) for k,p in paths.items()},'source_hashes':hashes,
              'mapping':mapping,'model_messages_sha256':core.file_hash(output/'model_messages_PRIVATE.jsonl'),
              'comparison_template_sha256':core.file_hash(output/'comparison_template_PRIVATE.jsonl'),
              'model_selection':'CLAUDE_VERSION_PENDING','execution_mode':'manual_chat',
              'external_transmission_authorized':False,
              'intended_use':'CLAUDE_MANUAL_PRIVATE_INSPECTION_ONLY','preferred_platform':'IAedu',
              'privacy_review_status':'PENDING',
              'role_support_review_states':['supported','not_demonstrated','contradicted','unresolved'],
              'privacy_status':'PRIVATE_UNREDACTED_NOT_CLEARED_FOR_EXTERNAL_SHARING',
              'LLM_calls':0,'human_validated':False,'requires_review':True,
              'training_eligibility':'NOT_ESTABLISHED'}
    write_new_json(output/'manifest_PRIVATE.json',manifest)
    write_new_json(output/'session_TEMPLATE_PRIVATE.json',{
        'provider':'Anthropic','model_display_name':'PENDING_CONFIRMATION',
        'model_version_or_identifier':'PENDING_CONFIRMATION','platform':'PENDING_CONFIRMATION',
        'execution_mode':'manual_chat','message_delivery':'single_user_message',
        'response_capture_method':'PENDING_CONFIRMATION',
        'fresh_chat_per_mention':None,'generation_controls':'PENDING_CONFIRMATION',
        'platform_instructions_or_tools':'PENDING_CONFIRMATION','session_date':'PENDING_CONFIRMATION'})
    (output/'MANUAL_README_PRIVATE.md').write_bytes((
        '# Private preparation only\n\n'
        'Do not upload or paste these unredacted texts before privacy review and authorization.\n'
        'One request per mention: requests/001.txt through requests/030.txt.\n'
        'Separate-role equivalent: requests/001.messages.json through requests/030.messages.json.\n'
        'After authorization, use a fresh chat for every mention; do not show Qwen/review outputs.\n'
        'Save the entire first response as UTF-8 without BOM in raw_responses/001.txt, etc.\n'
        'Do not remove code fences, rewrite quotes, repair JSON, or replace a response with a retry.\n'
        'Copy session_TEMPLATE_PRIVATE.json to session_PRIVATE.json and record the observed\n'
        'Claude model/version, platform, delivery mode and actually exposed controls.\n'
        'Use not_disclosed or not_exposed where appropriate; never invent a checkpoint or temperature.\n'
        'Never send manifest/session/comparison files to the model.\n'
        'Full procedure: docs/experiment_19c_claude_manual.md in the repository.\n').encode('utf-8'))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('input','selection-manifest','reference-run','output-dir'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:manifest=prepare_package(args.input,args.selection_manifest,args.reference_run,args.output_dir)
    except (ValueError,KeyError,TypeError,OSError):
        parser.exit(1,json.dumps({'error_code':'blind_package_input_or_protection_failure'})+'\n')
    print(json.dumps({k:manifest[k] for k in
                      ('records','prompt_version','LLM_calls','model_selection','intended_use','privacy_status')}))


if __name__=='__main__':main()
