"""Private offline wizard: bind existing decisions to official DGSI captures.

Never edits source texts, guesses a process number or bypasses validate_decision.
Prompts contain no private identifiers. Only aggregate counts/codes go to stdout.
"""

import argparse
import copy
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.annotation.dgsi_source_evidence import make_receipt, verify_receipt
from src.annotation.plan_inventory_batches import file_hash, load_bound_inventory, validate_document_sources
from src.annotation.prepare_role_annotation_batch import private_new_output
from src.annotation.prepare_stj_pilot_19c import GOLD_SHA, PILOT_SOURCES_SHA, assess_protection
from src.annotation.role_reference_provenance import fingerprint, reference_index, match_reference
from src.annotation.prepare_role_annotation_batch import identity_roots
from src.data.extract_role_candidates_v2 import read_documents
from src.data.map_role_taxonomy import load_jsonl


def ask(prompt):
    print(prompt,file=sys.stderr)
    return input().strip()


def unique_keys(pairs):
    obj={}
    for key,value in pairs:
        if key in obj:raise ValueError('dgsi_duplicate_private_json_key')
        obj[key]=value
    return obj


def private_file(value):
    path=Path(value).expanduser().resolve(strict=True)
    if not path.is_relative_to((ROOT/'data/raw').resolve()) or not path.is_file():
        raise ValueError('dgsi_evidence_must_stay_private')
    return path


def write_private(path,value):
    with path.open('x',encoding='utf-8') as handle:json.dump(value,handle,ensure_ascii=False,indent=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection-manifest',type=Path,required=True)
    parser.add_argument('--decisions',type=Path,help='Existing private decisions; prompted if omitted')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:
        output=private_new_output(args.output_dir)
        selection_path=private_file(args.selection_manifest)
        selection=json.loads(selection_path.read_text(encoding='utf-8'),object_pairs_hook=unique_keys)
        bindings=dict(selection['validated_bundle'])
        bindings['selection']={'path':str(selection_path),'sha256':file_hash(selection_path)}
        if bindings['gold']['sha256']!=GOLD_SHA or bindings['human_pilot']['sha256']!=PILOT_SOURCES_SHA:
            raise ValueError('dgsi_protected_reference_version_mismatch')
        if any(file_hash(Path(i['path']))!=i['sha256'] for i in bindings.values()):
            raise ValueError('dgsi_selection_inputs_changed')
        rows,docs,summary,_=load_bound_inventory(Path(bindings['input']['path']),Path(bindings['inventory_manifest']['path']))
        if summary.get('inventory_complete') is not True:raise ValueError('dgsi_complete_inventory_required')
        original=json.loads(Path(bindings['inventory_manifest']['path']).read_text(encoding='utf-8'))
        texts,_=validate_document_sources(docs,original)
        protected={'gold':load_jsonl(Path(bindings['gold']['path'])),
                   'human_pilot':load_jsonl(Path(bindings['human_pilot']['path']))}
        refs={name+':'+r['id']:r for name,items in protected.items() for r in items}
        decision_path=private_file(args.decisions or ask('Caminho do JSON privado das decisões já criadas:'))
        decisions=json.loads(decision_path.read_text(encoding='utf-8'),object_pairs_hook=unique_keys)
        bindings['original_decisions']={'path':str(decision_path),'sha256':file_hash(decision_path)}
        if (not decisions or set(decisions)!=set(selection['unresolved_references']) or
                not set(decisions)<=refs.keys()):raise ValueError('dgsi_decisions_do_not_cover_pending_references')
        sources=defaultdict(list)
        for key,decision in decisions.items():
            if (decision.get('reference_sha256')!=fingerprint(refs[key]) or
                    decision.get('inventory_fingerprint')!=fingerprint(docs)):
                raise ValueError('dgsi_original_adjudication_is_stale')
            if decision.get('excluded_from_corpus') is not True or decision.get('document_ids'):
                raise ValueError('dgsi_wizard_requires_external_source_decisions')
            external=[i for i in decision['evidence'] if i.get('kind')=='external_source']
            if not external:raise ValueError('dgsi_copied_source_required')
            for item in external:
                path=private_file(item['path'])
                if file_hash(path)!=item['sha256']:raise ValueError('dgsi_copied_source_hash_mismatch')
                bindings['copied_source_'+str(len(bindings))]={'path':str(path),'sha256':item['sha256']}
                sources[(path,item.get('source_document_id'))].append(key)
        reviewer=ask('Revisor da conferência de proveniência (guardado só no ficheiro privado):')
        reason=ask('Fundamento da conferência na fonte oficial (privado):')
        if not reviewer or not reason:raise ValueError('dgsi_human_confirmation_required')
        additions=defaultdict(list);receipts=[];positive_targets=defaultdict(set)
        index=reference_index(docs,texts)
        for number,((source,source_id),keys) in enumerate(sources.items(),1):
            extracted=read_documents(source)
            entries=[entry for entry in extracted if entry[0]==source_id]
            if not entries and source_id is None and len(extracted)==1:entries=extracted
            if len(entries)!=1:raise ValueError('dgsi_copied_document_ambiguous')
            actual_id,text,_=entries[0]
            print(json.dumps({'stage_code':'DGSI_SOURCE_REVIEW','source_count':len(sources),'source_ordinal':number}),file=sys.stderr)
            capture=private_file(ask('Caminho da captura oficial local HTML/MHTML/TXT, sem editar o original:'))
            url=ask('URL oficial OpenDocument da decisão no DGSI:')
            if ask('Após conferir a fonte oficial, o ID nela e a discrepância da cópia, escreva CONFIRMO:')!='CONFIRMO':
                raise ValueError('dgsi_human_confirmation_required')
            receipt=make_receipt(source,text,capture,url,reviewer,reason,[refs[k] for k in keys],actual_id)
            artifact={'kind':'official_capture','path':str(capture),'sha256':file_hash(capture)}
            bindings[f'capture_{number}']={'path':str(capture),'sha256':artifact['sha256']}
            for key in keys:
                identity=verify_receipt(receipt,source,text,refs[key],{(capture,'official_capture',artifact['sha256'])})
                positive_targets[key].update(match_reference(refs[key],index)['methods'])
                for root in identity_roots(identity):positive_targets[key].update(index['roots'].get(root,set()))
            receipts.append((number,receipt))
            for key in keys:additions[key].append((number,artifact))
        if any(file_hash(Path(i['path']))!=i['sha256'] for i in bindings.values()):
            raise ValueError('dgsi_inputs_changed_during_review')
        output.mkdir(parents=True)
        receipt_items={}
        for number,receipt in receipts:
            path=output/f'identity_{number:02}_PRIVATE.json';write_private(path,receipt)
            receipt_items[number]={'kind':'dgsi_identity_receipt','path':str(path.resolve()),'sha256':file_hash(path)}
        updated=copy.deepcopy(decisions)
        doc_index={doc['document_id']:doc for doc in docs}
        for key,items in additions.items():
            updated[key].update(human_confirmed=True,reviewer=reviewer,reason=reason)
            # Preserve the actual copied sources; regenerate only this new receipt
            # set. Old decisions and all their artifacts remain untouched.
            updated[key]['evidence']=[i for i in updated[key]['evidence'] if i['kind'] not in ('dgsi_identity_receipt','official_capture')]
            for number,capture in items:updated[key]['evidence'] += [capture,receipt_items[number]]
            if positive_targets[key]:
                targets=sorted(positive_targets[key])
                packet=output/f'reservation_{list(updated).index(key)+1:02}_PRIVATE.json'
                write_private(packet,{'reference_sha256':updated[key]['reference_sha256'],'document_ids':targets,
                                     'document_source_hashes':{d:doc_index[d]['source_text_sha256'] for d in targets}})
                updated[key].update(excluded_from_corpus=False,document_ids=targets)
                updated[key]['evidence'].append({'kind':'reservation_packet','path':str(packet.resolve()),'sha256':file_hash(packet)})
        _,blocked,pending,log=assess_protection(rows,docs,texts,protected,updated)
        write_private(output/'protection_decisions_PRIVATE.json',updated)
        write_private(output/'validation_PRIVATE.json',{'validated_inputs':bindings,'protected_reference_checks':log,
                      'unresolved_references':pending,'blocked_groups':sorted(blocked)})
        print(json.dumps({'validated_references':len(updated),'external_sources':len(sources),
                          'reserved_references':sum(bool(d.get('document_ids')) for d in updated.values()),
                          'unresolved_reference_count':len(pending),'blocked_groups':len(blocked),'LLM_calls':0}))
        if pending:raise SystemExit(1)
    except (ValueError,KeyError,TypeError,OSError,EOFError) as exc:
        code=str(exc) if str(exc).startswith('dgsi_') and str(exc).replace('_','').isalnum() else 'DGSI_EVIDENCE_VALIDATION_FAILED'
        parser.exit(1,json.dumps({'error_code':code})+'\n')


if __name__=='__main__':main()
