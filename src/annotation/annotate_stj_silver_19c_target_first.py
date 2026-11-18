"""Experimental target-first prompt adapter; retain the historical 19c runner.

No new inference loop or parser. A private sidecar binds this adapter, the
unchanged core, reference run and effective configuration for both Slurm jobs.
"""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation.annotate_role_candidates_qwen import unique_keys, write_new_json
from src.annotation.prepare_role_annotation_batch import private_new_output

VERSION = '19c-v2-target-first'
PROMPT_PATH = ROOT/'config/prompts/role_annotation_19c_v2_target_first.txt'
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding='utf-8')
PROMPT_SHA256 = core.file_hash(PROMPT_PATH)
BASE_MESSAGES = core.build_messages


def build_messages(record):
    original = BASE_MESSAGES(record)  # Preserve all original span/input checks.
    return [{'role':'system','content':SYSTEM_PROMPT},
            {'role':'user','content':'Target mention (verbatim JSON string): '
             +json.dumps(record['entity'],ensure_ascii=False)+'\nMarked context:\n'+original[1]['content']}]


@contextmanager
def target_first_profile(argv):
    names = ('PROMPT_VERSION','PROMPT_PATH','SYSTEM_PROMPT','build_messages')
    saved = {name:getattr(core,name) for name in names};saved_argv=sys.argv
    try:
        core.PROMPT_VERSION=VERSION;core.PROMPT_PATH=PROMPT_PATH
        core.SYSTEM_PROMPT=SYSTEM_PROMPT;core.build_messages=build_messages
        sys.argv=argv
        yield
    finally:
        for name,value in saved.items():setattr(core,name,value)
        sys.argv=saved_argv


def reference_binding(args):
    reference=json.loads(args.reference_run.read_text(encoding='utf-8'),object_pairs_hook=unique_keys)
    if (not isinstance(reference,dict) or not isinstance(reference.get('configuration'),dict)
            or not isinstance(reference.get('summary'),dict) or core.file_hash(PROMPT_PATH)!=PROMPT_SHA256):
        raise ValueError('reference_run_binding_mismatch')
    config=reference['configuration']
    checks={'input_sha256':core.file_hash(args.input),'selection_sha256':core.file_hash(args.selection_manifest),
            'script_sha256':core.file_hash(Path(core.__file__)),
            'loader_sha256':core.file_hash(ROOT/'src/annotation/annotate_role_candidates_qwen.py'),
            'taxonomy_sha256':core.file_hash(core.TAXONOMY),
            'prompt_version':'19c-v1','prompt_sha256':core.file_hash(core.PROMPT_PATH),'revision':args.revision}
    if (reference.get('status') not in ('completed','completed_with_invalid_outputs')
            or reference.get('summary',{}).get('records')!=30
            or reference.get('input_unchanged') is not True or reference.get('selection_unchanged') is not True
            or any(config.get(k)!=v for k,v in checks.items())):
        raise ValueError('reference_run_binding_mismatch')
    # Bind the historical prediction file too; no labels/quotes are read as input.
    if core.file_hash(args.reference_run.parent/'silver_predictions.jsonl')!=reference.get('predictions_sha256'):
        raise ValueError('reference_predictions_changed')
    expected=dict(config,prompt_version=VERSION,prompt_sha256=core.file_hash(PROMPT_PATH))
    binding={'prompt_version':VERSION,'adapter_sha256':core.file_hash(Path(__file__)),
             'reference_run_sha256':core.file_hash(args.reference_run),'expected_configuration':expected}
    return binding


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('input','selection-manifest','run-dir','reference-run'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--preflight-only',action='store_true')
    parser.add_argument('--preflight-run',type=Path)
    args=parser.parse_args();os.umask(0o077)
    try:
        output=private_new_output(args.run_dir)
        binding=reference_binding(args)
        if not args.preflight_only:
            if args.preflight_run is None:raise ValueError('variant_preflight_required')
            previous=json.loads((args.preflight_run.parent/'variant.json').read_text(encoding='utf-8'),object_pairs_hook=unique_keys)
            if (previous.get('binding')!=binding or previous.get('run_sha256')!=core.file_hash(args.preflight_run)
                    or previous.get('run_status')!='preflight_passed'):
                raise ValueError('variant_preflight_binding_mismatch')
        argv=['19c-target-first','--input',str(args.input),'--selection-manifest',str(args.selection_manifest),
              '--run-dir',str(output),'--revision',args.revision]
        argv+=['--preflight-only'] if args.preflight_only else ['--preflight-run',str(args.preflight_run)]
        exit_code=0
        with target_first_profile(argv):
            try:core.main()
            except SystemExit as exc:exit_code=exc.code
        run_path=output/'run.json'
        if not run_path.is_file():raise ValueError('variant_run_not_created')
        run=json.loads(run_path.read_text(encoding='utf-8'),object_pairs_hook=unique_keys)
        if run['configuration']!=binding['expected_configuration'] or reference_binding(args)!=binding:
            raise ValueError('variant_configuration_or_source_changed')
        write_new_json(output/'variant.json',{'binding':binding,'run_sha256':core.file_hash(run_path),
                                            'run_status':run['status']})
        if exit_code:raise SystemExit(exit_code)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        codes={'reference_run_binding_mismatch','reference_predictions_changed','variant_preflight_required',
               'variant_preflight_binding_mismatch','variant_run_not_created','variant_configuration_or_source_changed'}
        parser.exit(1,json.dumps({'error_code':str(exc) if str(exc) in codes else 'variant_input_or_binding_failure'})+'\n')


if __name__=='__main__':main()
