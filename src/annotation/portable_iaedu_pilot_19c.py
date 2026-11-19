"""Export a source-validated 30-mention capsule, not the corpus or gold data.

Windows verifies a separately supplied source manifest digest, capsule files,
spans/messages and code. It does not claim to re-read the INESC corpus.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import annotate_stj_silver_19c_target_first as prompt
from src.annotation.import_claude_manual_19c import read_json, validated_package
from src.annotation.prepare_role_annotation_batch import private_new_output
from src.annotation.role_reference_provenance import fingerprint

VERSION='19c-iaedu-portable-v1'
CODE_FILES=('src/annotation/annotate_stj_silver_19c.py','src/annotation/annotate_stj_silver_19c_target_first.py',
            'src/annotation/annotate_role_candidates_qwen.py',
            'src/annotation/iaedu_agent_api_19c.py','src/annotation/portable_iaedu_pilot_19c.py',
            'src/annotation/run_iaedu_pilot_19c.py','src/annotation/plan_inventory_batches.py',
            'src/annotation/prepare_role_annotation_batch.py','src/annotation/prepare_stj_pilot_19c.py',
            'src/annotation/role_reference_provenance.py','src/data/map_role_taxonomy.py','src/utils/entity_marking.py',
            'config/prompts/role_annotation_19c_v2_target_first.txt','config/role_taxonomy_v2.json')


def lf_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def export_capsule(folder,output_dir):
    output=private_new_output(output_dir)
    source_manifest=folder/'manifest_PRIVATE.json';before=core.file_hash(source_manifest)
    rows,source=validated_package(folder)
    selection=read_json(Path(source['source_paths']['selection']))
    if selection.get('unresolved_references') or selection.get('selection_complete') is not True:
        raise ValueError('source_protection_not_complete')
    data={'pilot_input.jsonl':Path(source['source_paths']['input']).read_bytes()}
    mapping=[]
    for record,item in zip(rows,source['mapping']):
        name=f"requests/{item['ordinal']:03}.txt"
        data[name]=(folder/item['manual_text_file']).read_bytes()
        mapping.append({'ordinal':item['ordinal'],'id':record['id'],'record_sha256':fingerprint(record),
                        'request_file':name,'request_sha256':hashlib.sha256(data[name]).hexdigest()})
    code={name:lf_hash(ROOT/name) for name in CODE_FILES}
    validated_package(folder)
    if before!=core.file_hash(source_manifest):raise ValueError('source_package_changed')
    manifest={'version':VERSION,'records':30,'prompt_version':prompt.VERSION,'mapping':mapping,
              'files':{name:hashlib.sha256(value).hexdigest() for name,value in data.items()},
              'code_lf_sha256':code,'source_package_manifest_sha256':before,
              'source_input_sha256':source['source_hashes']['input'],
              'source_selection_sha256':source['source_hashes']['selection'],
              'source_reference_run_sha256':source['source_hashes']['reference_run'],
              'source_protection_attestation':{'method':'validated_package/load_pilot',
                  'selection_complete':True,'unresolved_references':0,'validation_site':'SOURCE_FULL_BUNDLE',
                  'windows_scope':'capsule_integrity_and_source_attestation_NOT_independent_corpus_recheck'},
              'full_corpus_included':False,'contains_private_contexts':True,
              'gold_examples_included':False,'source_corpus_stays_on_inesc':True,
              'external_transmission_authorized':False,'human_validated':False,'requires_review':True,
              'training_eligibility':'NOT_ESTABLISHED'}
    output.mkdir(parents=True,mode=0o700);(output/'requests').mkdir(mode=0o700)
    for name,value in data.items():(output/name).write_bytes(value)
    write_json_new(output/'portable_manifest_PRIVATE.json',manifest)
    digest=core.file_hash(output/'portable_manifest_PRIVATE.json')
    write_json_new(output/'authorization_TEMPLATE_PRIVATE.json',{
        'version':'iaedu-pilot-authorization-v1','scope':'STJ_19C_30_IAEDU_API',
        'capsule_manifest_sha256':digest,'external_transmission_authorized':False,
        'privacy_review_completed':False,'approved_by':None,'approved_at':None,'endpoint':None,'channel_id':None})
    validate_capsule(output,digest)
    files=[p for p in output.rglob('*') if p.is_file()]
    return {'records':30,'portable_manifest_sha256':digest,'full_corpus_included':False,'contains_private_contexts':True,
            'files':len(files),'bytes':sum(p.stat().st_size for p in files),'LLM_calls':0}


def write_json_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2);handle.flush();os.fsync(handle.fileno())


def validate_capsule(folder,expected_sha256):
    path=folder/'portable_manifest_PRIVATE.json'
    if (not isinstance(expected_sha256,str) or len(expected_sha256)!=64
            or core.file_hash(path)!=expected_sha256):raise ValueError('trusted_capsule_digest_mismatch')
    manifest=read_json(path)
    expected_files={'pilot_input.jsonl'}|{f'requests/{n:03}.txt' for n in range(1,31)}
    if (manifest['version']!=VERSION or manifest['records']!=30 or manifest['prompt_version']!=prompt.VERSION
            or set(manifest['files'])!=expected_files or set(manifest['code_lf_sha256'])!=set(CODE_FILES)
            or manifest['source_protection_attestation']['selection_complete'] is not True
            or manifest['source_protection_attestation']['unresolved_references']!=0
            or manifest.get('external_transmission_authorized') is not False):
        raise ValueError('portable_protocol_mismatch')
    if any(lf_hash(ROOT/name)!=sha for name,sha in manifest['code_lf_sha256'].items()):
        raise ValueError('portable_code_mismatch')
    if any(core.file_hash(folder/name)!=sha for name,sha in manifest['files'].items()):
        raise ValueError('portable_file_changed')
    if manifest['files']['pilot_input.jsonl']!=manifest['source_input_sha256']:
        raise ValueError('portable_original_input_mismatch')
    rows=[json.loads(line,object_pairs_hook=core.unique_keys) for line in
          (folder/'pilot_input.jsonl').read_bytes().decode('utf-8').splitlines()]
    mapping=manifest['mapping']
    if (len(rows)!=30 or len(mapping)!=30 or len({r['id'] for r in rows})!=30
            or [m['ordinal'] for m in mapping]!=list(range(1,31))
            or [m['id'] for m in mapping]!=[r['id'] for r in rows]):raise ValueError('portable_ids_mismatch')
    groups=set()
    for record,item in zip(rows,mapping):
        messages=prompt.build_messages(record)
        expected='\n\n'.join(m['content'] for m in messages).encode('utf-8')
        name=f"requests/{item['ordinal']:03}.txt"
        group=record['pilot_selection']['planning_group_id']
        if (fingerprint(record)!=item['record_sha256'] or item['request_file']!=name
                or item['request_sha256']!=manifest['files'][name] or (folder/name).read_bytes()!=expected
                or record['pilot_selection']['training_eligibility']!='NOT_ESTABLISHED' or group in groups):
            raise ValueError('portable_record_or_request_mismatch')
        groups.add(group)
    return rows,manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:report=export_capsule(args.package_dir,args.output_dir)
    except (ValueError,KeyError,TypeError,OSError):parser.exit(1,'{"error_code":"portable_export_failed"}\n')
    print(json.dumps(report))


if __name__=='__main__':main()
