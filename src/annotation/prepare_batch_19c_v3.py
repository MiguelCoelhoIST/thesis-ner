"""Source-bound deterministic selection and private v3 capsule; no API calls."""

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import audit_next100_19c as capacity
from src.annotation import prepare_stj_pilot_19c as pilot
from src.annotation import prompt_19c_v3 as prompt
from src.annotation.import_claude_manual_19c import read_json
from src.annotation.plan_inventory_batches import load_bound_inventory, validate_document_sources
from src.annotation.portable_iaedu_pilot_19c import CODE_FILES as OLD_CODE_FILES, lf_hash, write_json_new
from src.annotation.prepare_role_annotation_batch import content_related, normalized, private_new_output
from src.annotation.role_reference_provenance import fingerprint
from src.data.map_role_taxonomy import load_jsonl

VERSION = '19c-v3-variable-batch-v1'
COHORT = 'EXPLORATORY_SILVER_V3_BATCH_NOT_GOLD'
AUTH_SCOPE = 'STJ_19C_V3_BATCH_IAEDU_API'
CODE_FILES = OLD_CODE_FILES + (
    'src/annotation/audit_next100_19c.py', 'src/annotation/prompt_19c_v3.py',
    'src/annotation/prepare_batch_19c_v3.py', 'src/annotation/run_iaedu_batch_19c_v3.py',
    'config/prompts/role_annotation_19c_v3_legal_roles.txt')


def check_bindings(binding):
    if not binding or any(core.file_hash(Path(v['path'])) != v['sha256'] for v in binding.values()):
        raise ValueError('source_binding_changed')


def load_audit(folder):
    """Rebind the completed audit, sources, protected references and every entry.

    Reuse the frozen content-similarity reservations instead of repeating the
    expensive whole-corpus similarity pass. This is consistency verification of
    a trusted local audit, not authentication of an arbitrarily forged bundle.
    """
    path = folder/'audit_PRIVATE.json'
    entry_path = folder/'mention_capacity_PRIVATE.jsonl'
    before = {str(p.resolve()): core.file_hash(p) for p in (path, entry_path)}
    audit = read_json(path); summary = audit['summary']; binding = audit['validated_bundle']
    required = {'input', 'inventory_manifest', 'documents', 'ner_predictions', 'gold',
                'pilot_sources', 'development_input', 'development_selection'}
    if (not required <= binding.keys() or summary['version'] != capacity.VERSION
            or summary['protection_recheck_complete'] is not True
            or summary['unresolved_reference_count'] != 0 or audit['unresolved_references']
            or summary['selected'] != 0 or summary['selection_performed'] is not False
            or audit['script_sha256'] != core.file_hash(Path(capacity.__file__))):
        raise ValueError('completed_source_audit_required')
    check_bindings(binding)
    p = lambda key: Path(binding[key]['path'])
    rows, docs, inventory, rebound = load_bound_inventory(p('input'), p('inventory_manifest'))
    if inventory.get('inventory_complete') is not True or inventory.get('NER_executed') is not True:
        raise ValueError('complete_inventory_required')
    if any(binding[k]['sha256'] != v['sha256'] for k, v in rebound.items()):
        raise ValueError('audit_inventory_binding_mismatch')
    if core.file_hash(p('gold')) != pilot.GOLD_SHA or core.file_hash(p('pilot_sources')) != pilot.PILOT_SOURCES_SHA:
        raise ValueError('frozen_protected_source_changed')
    development = core.load_pilot(p('development_input'), p('development_selection'))
    selection = read_json(p('development_selection'))
    if any(selection['validated_bundle'][k]['sha256'] != binding[k]['sha256'] for k in ('input', 'inventory_manifest')):
        raise ValueError('development_inventory_mismatch')
    texts, _ = validate_document_sources(docs, read_json(p('inventory_manifest')))
    protected = {'gold': load_jsonl(p('gold')), 'human_pilot': load_jsonl(p('pilot_sources')),
                 'development_30': development}
    decisions = read_json(p('protection_decisions')) if 'protection_decisions' in binding else {}
    groups, blocked, unresolved, references = pilot.assess_protection(rows, docs, texts, protected, decisions)
    reserved = set(audit['blocked_groups']); identity = set(audit['identity_review_groups'])
    expected_identity = {groups[d['document_id']][0] for d in docs
        if (d.get('requires_identity_review') is not False or len(d.get('potential_process_group_ids', [])) != 1
            or 'identity_unresolved_or_conflicting' in groups[d['document_id']][1])}
    if (unresolved or references != audit['protected_reference_checks'] or not blocked <= reserved
            or identity != expected_identity or not reserved <= {g for g, _ in groups.values()}):
        raise ValueError('audit_protection_mismatch')
    entries = load_jsonl(entry_path)
    if len(entries) != len(rows) or len({e['id'] for e in entries}) != len(rows):
        raise ValueError('audit_entry_ids_mismatch')
    by_id = {e['id']: e for e in entries}; available = []
    for row in rows:
        entry = by_id.get(row['id']); group, flags = groups[row['document_id']]
        reasons = []
        if group in blocked: reasons.append('protected_related_group')
        if group in reserved - blocked: reasons.append('protected_context_similarity_group')
        if group in identity: reasons.append('identity_unresolved_or_conflicting_group')
        expected = {'id': row['id'], 'document_id': row['document_id'],
                    'source_text_sha256': row['source_text_sha256'], 'planning_group_id': group,
                    'entity_document_start': row['entity_document_start'], 'entity_document_end': row['entity_document_end'],
                    'context_sha256': pilot.digest(normalized(row['text'])),
                    'status': 'REVIEW_OR_EXCLUDED' if reasons else 'CAPACITY_ONLY_EXPLORATORY',
                    'reasons': reasons, 'original_review_reasons': sorted(flags),
                    'training_eligibility': 'NOT_ESTABLISHED'}
        if entry != expected: raise ValueError('audit_entry_mismatch')
        if not reasons: available.append(row)
    if (len(available) != summary['available_mentions_capacity_only']
            or len({groups[r['document_id']][0] for r in available}) != summary['available_related_groups']
            or len(rows) != summary['mentions'] or len(docs) != summary['documents']):
        raise ValueError('audit_capacity_mismatch')
    check_bindings(binding)
    if any(core.file_hash(Path(name)) != sha for name, sha in before.items()):
        raise ValueError('audit_changed_during_validation')
    return available, groups, audit, {**binding,
        'capacity_audit': {'path': str(path.resolve()), 'sha256': before[str(path.resolve())]},
        'capacity_entries': {'path': str(entry_path.resolve()), 'sha256': before[str(entry_path.resolve())]}}


def select_rows(rows, groups, maximum=64, seed=42):
    if type(maximum) is not int or not 1 <= maximum <= 64 or type(seed) is not int:
        raise ValueError('invalid_selection_parameters')
    if len({r['id'] for r in rows}) != len(rows): raise ValueError('duplicate_mention_id')
    buckets = defaultdict(list)
    for row in rows:
        prompt.build_messages(row)
        buckets[groups[row['document_id']][0]].append(row)
    rank = lambda kind, key: (pilot.digest(f'{seed}:{kind}:{key}'), key)
    chosen, dispositions = [], []
    for group in sorted(buckets, key=lambda g: rank('group', g)):
        found = False
        for row in sorted(buckets[group], key=lambda r: rank('mention', r['id'])):
            conflict = None
            if len(chosen) >= maximum and not found:
                reason = 'requested_group_limit'
            elif found:
                reason = 'group_already_represented'
            elif (conflict := next((peer['id'] for peer in chosen if
                    normalized(row['text']) == normalized(peer['text']) or content_related(row, peer)), None)) is not None:
                reason = 'selected_context_similarity'
            else:
                item = copy.deepcopy(row)
                item['cohort'] = COHORT
                item['batch_selection'] = {'version': VERSION, 'seed': seed, 'planning_group_id': group,
                    'eligibility': 'source_audit_rechecked_exploratory_only', 'training_eligibility': 'NOT_ESTABLISHED'}
                chosen.append(item); found = True; reason = 'selected'
            dispositions.append({'id': row['id'], 'planning_group_id': group, 'reason': reason,
                                 'first_conflicting_selected_id': conflict})
    represented = {r['batch_selection']['planning_group_id'] for r in chosen}
    report = {'seed': seed, 'maximum_requested': maximum, 'available_mentions': len(rows),
              'available_groups': len(buckets), 'selected': len(chosen), 'selected_groups': len(represented),
              'unrepresented_groups': sorted(set(buckets)-represented),
              'disposition_counts': dict(Counter(d['reason'] for d in dispositions)),
              'method': 'SHA256 seed/group/id rank; first nonsimilar context per group; no lexical labels',
              'not_a_maximum_matching_or_independence_proof': True, 'LLM_calls': 0}
    return chosen, report, dispositions


def export_capsule(rows, folder, selection_sha, audit_sha):
    folder = private_new_output(folder)
    folder.mkdir(mode=0o700); (folder/'requests').mkdir(mode=0o700)
    data = ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows).encode('utf-8')
    (folder/'batch_input.jsonl').write_bytes(data)
    files = {'batch_input.jsonl': hashlib.sha256(data).hexdigest()}; mapping = []
    for n, row in enumerate(rows, 1):
        request = '\n\n'.join(m['content'] for m in prompt.build_messages(row)).encode('utf-8')
        name = f'requests/{n:03}.txt'; (folder/name).write_bytes(request)
        files[name] = hashlib.sha256(request).hexdigest()
        mapping.append({'ordinal': n, 'id': row['id'], 'record_sha256': fingerprint(row),
                        'request_file': name, 'request_sha256': files[name]})
    manifest = {'version': VERSION, 'records': len(rows), 'mapping': mapping, 'files': files,
                'prompt_configuration': prompt.configuration(), 'prompt_version': prompt.VERSION,
                'code_lf_sha256': {name: lf_hash(ROOT/name) for name in CODE_FILES},
                'source_selection_sha256': selection_sha, 'source_audit_sha256': audit_sha,
                'source_protection_attestation': {'validation_site': 'SOURCE_FULL_BUNDLE',
                    'unresolved_references': 0, 'one_per_related_group': True,
                    'selected_context_similarity_checked': True,
                    'windows_scope': 'capsule_integrity_NOT_independent_corpus_recheck'},
                'full_corpus_included': False, 'contains_private_contexts': True,
                'external_transmission_authorized': False, 'human_validated': False,
                'requires_review': True, 'training_eligibility': 'NOT_ESTABLISHED'}
    write_json_new(folder/'portable_manifest_PRIVATE.json', manifest)
    digest = core.file_hash(folder/'portable_manifest_PRIVATE.json')
    write_json_new(folder/'authorization_TEMPLATE_PRIVATE.json', {
        'version': VERSION, 'scope': AUTH_SCOPE, 'records': len(rows), 'prompt_version': prompt.VERSION,
        'capsule_manifest_sha256': digest, 'external_transmission_authorized': False,
        'privacy_review_completed': False, 'approved_by': None, 'approved_at': None, 'endpoint': None, 'channel_id': None})
    validate_capsule(folder, digest)
    return digest


def validate_capsule(folder, expected_digest):
    if core.file_hash(folder/'portable_manifest_PRIVATE.json') != expected_digest:
        raise ValueError('trusted_capsule_digest_mismatch')
    manifest = read_json(folder/'portable_manifest_PRIVATE.json'); count = manifest['records']
    if (type(count) is not int or not 1 <= count <= 64 or manifest['version'] != VERSION
            or manifest['prompt_version'] != prompt.VERSION
            or set(manifest['code_lf_sha256']) != set(CODE_FILES)
            or manifest['external_transmission_authorized'] is not False
            or manifest.get('human_validated') is not False or manifest.get('requires_review') is not True
            or manifest.get('training_eligibility') != 'NOT_ESTABLISHED'
            or manifest.get('full_corpus_included') is not False
            or manifest['source_protection_attestation'].get('validation_site') != 'SOURCE_FULL_BUNDLE'
            or manifest['source_protection_attestation']['unresolved_references'] != 0
            or manifest['source_protection_attestation']['one_per_related_group'] is not True
            or manifest['source_protection_attestation']['selected_context_similarity_checked'] is not True):
        raise ValueError('batch_protocol_mismatch')
    if any(lf_hash(ROOT/name) != sha for name, sha in manifest['code_lf_sha256'].items()):
        raise ValueError('portable_code_mismatch')
    expected_files = {'batch_input.jsonl'} | {f'requests/{n:03}.txt' for n in range(1, count+1)}
    if set(manifest['files']) != expected_files or any(core.file_hash(folder/name) != sha for name, sha in manifest['files'].items()):
        raise ValueError('portable_file_changed')
    rows = load_jsonl(folder/'batch_input.jsonl'); mapping = manifest['mapping']
    if (len(rows) != count or len(mapping) != count or len({r['id'] for r in rows}) != count
            or [m['ordinal'] for m in mapping] != list(range(1, count+1))
            or [m['id'] for m in mapping] != [r['id'] for r in rows]):
        raise ValueError('portable_ids_mismatch')
    groups = set(); checked = []
    for row, item in zip(rows, mapping):
        name = f"requests/{item['ordinal']:03}.txt"
        expected = '\n\n'.join(m['content'] for m in prompt.build_messages(row)).encode('utf-8')
        group = row['batch_selection']['planning_group_id']
        if (row.get('cohort') != COHORT or group in groups or fingerprint(row) != item['record_sha256']
                or row['batch_selection']['training_eligibility'] != 'NOT_ESTABLISHED'
                or row['batch_selection']['version'] != VERSION
                or row['batch_selection'].get('eligibility') != 'source_audit_rechecked_exploratory_only'
                or item['request_file'] != name or item['request_sha256'] != manifest['files'][name]
                or (folder/name).read_bytes() != expected):
            raise ValueError('portable_record_or_request_mismatch')
        if any(normalized(row['text']) == normalized(peer['text']) or content_related(row, peer) for peer in checked):
            raise ValueError('selected_context_overlap')
        groups.add(group); checked.append(row)
    return rows, manifest


def prepare(folder, output_dir, maximum=64, seed=42):
    output = private_new_output(output_dir)
    rows, groups, source, binding = load_audit(folder)
    chosen, summary, dispositions = select_rows(rows, groups, maximum, seed)
    if not chosen: raise ValueError('no_nonsimilar_groups_available')
    check_bindings(binding)
    output.mkdir(parents=True, mode=0o700)
    selection = {'version': VERSION, 'summary': summary, 'selected_ids': [r['id'] for r in chosen],
                 'dispositions': dispositions, 'source_audit_summary': source['summary'],
                 'source_exclusion_counts_NON_DISJOINT': source['summary']['exclusion_reason_counts_NON_DISJOINT'],
                 'validated_bundle': binding, 'prompt_configuration': prompt.configuration(),
                 'human_validated': False, 'requires_review': True, 'training_eligibility': 'NOT_ESTABLISHED'}
    write_json_new(output/'selection_manifest_PRIVATE.json', selection)
    digest = export_capsule(chosen, output/'capsule', core.file_hash(output/'selection_manifest_PRIVATE.json'),
                            binding['capacity_audit']['sha256'])
    check_bindings(binding)
    return {**summary, 'capsule_manifest_sha256': digest, 'external_transmission_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--max-mentions', type=int, default=64)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args(); os.umask(0o077)
    try:
        report = prepare(args.audit_dir, args.output_dir, args.max_mentions, args.seed)
        # Group IDs/dispositions remain private, even when they are hashes.
        print(json.dumps({k: v for k, v in report.items() if k != 'unrepresented_groups'}))
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(1, 'batch_preparation_failed; inspect private audit/source bindings.\n')


if __name__ == '__main__':
    main()
