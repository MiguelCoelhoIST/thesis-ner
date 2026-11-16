"""Prepare a NEW private exploratory 30-mention cohort; no model or annotation."""

import argparse
import copy
import json
import os
import re
import sys
from collections import Counter, defaultdict, deque
from bisect import bisect_left
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.annotation.plan_inventory_batches import (
    check_unannotated, digest, file_hash, load_bound_inventory, review_reasons, validate_document_sources,
)
from src.annotation.prepare_role_annotation_batch import Components, content_related, identity_roots, private_new_output
from src.data.map_role_taxonomy import load_jsonl
from src.utils.entity_marking import mark_entity

VERSION = '19c-exploratory-pilot-v1'
COHORT = 'EXPLORATORY_SILVER_PILOT_NOT_GOLD'
GOLD_SHA = 'f687174287e7aeb50283a42e510897eb4bd9daa663749b3f3a4507c77a3bd6c8'
PILOT_SOURCES_SHA = 'b64857723d32375f8f461fc26fd7c1d3ffd675676980ba0663a2a20dc2200a6e'
CUES = {
    'appeal_context': r'\brecorrent[es]*\b', 'criminal_context': r'\barguid[oa]s?\b',
    'witness_context': r'\btestemunhas?\b', 'reporter_context': r'\brelator[ae]?\b',
    'bibliographic_context': r'\b(?:doutrina|obra|edição|editora|pág|revista|livro)\b',
    'civil_context': r'\b(?:réu|ré|réus|rés|autor|autora|autores|autoras)\b',
    'request_context': r'\brequerentes?\b', 'appellee_context': r'\brecorrid[oa]s?\b',
}


def canonical_hash(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False))


def group_index(rows, documents):
    for row in rows:
        check_unannotated(row)
        mark_entity(row['text'], row['entity_start'], row['entity_end'])
        if row['text'][row['entity_start']:row['entity_end']] != row['entity']:
            raise ValueError('entity_mismatch')
    if len({row['id'] for row in rows}) != len(rows):
        raise ValueError('duplicate_mention_id')
    graph = Components();members = defaultdict(set);flags = defaultdict(set)
    metadata = list(documents) + list(rows)
    for row in metadata:
        node = ('document', row['document_id']);graph.find(node)
        for field in ('source_text_sha256', 'split_block_id'):
            if row.get(field):graph.join(node, (field, row[field]))
        roots = identity_roots(row) | set(row.get('potential_process_group_ids', []))
        for alias in row.get('aliases', []):roots.update(identity_roots(alias))
        for root in roots:graph.join(node, ('process', root))
    for row in metadata:
        component = graph.find(('document', row['document_id']))
        members[component].add(row['document_id']);flags[component].update(review_reasons(row))
    return {doc['document_id']: ('group_' + digest(json.dumps(sorted(members[graph.find(('document', doc['document_id']))]))),
                               flags[graph.find(('document', doc['document_id']))]) for doc in documents}


def assess_protection(rows, documents, texts, protected_sets, decisions=None):
    groups = group_index(rows, documents)
    members = defaultdict(set)
    for doc_id, (group, _) in groups.items():
        members[group].add(doc_id)
    doc_index = {doc['document_id']: doc for doc in documents}
    roots = defaultdict(set)
    for doc in documents:
        for root in doc['potential_process_group_ids']:
            roots[root].add(doc['document_id'])
        for alias in doc.get('aliases', []):
            for root in identity_roots(alias):
                roots[root].add(doc['document_id'])
    blocked, unresolved, reference_log = set(), [], []
    normalized = {key: ' '.join(text.casefold().split()) for key, text in texts.items()}
    decisions = decisions or {}
    used = set()
    for source_set, references in protected_sets.items():
        if not references or len({r['id'] for r in references}) != len(references):
            raise ValueError('missing_or_duplicate_protected_references')
        for ref in references:
            mark_entity(ref['text'], ref['entity_start'], ref['entity_end'])
            if ref['text'][ref['entity_start']:ref['entity_end']] != ref['entity']:
                raise ValueError('invalid_protected_reference_target')
            key = source_set + ':' + ref['id']
            ref_roots = identity_roots(ref)
            matches = set()
            for root in ref_roots:
                matches.update(roots.get(root, set()))
            passage = ' '.join(ref['text'].casefold().split())
            for doc in documents:
                aliases = doc.get('aliases', [])
                same_source = any(
                    ref.get('source_file') == a.get('source_file') and
                    ref.get('source_document_id') == a.get('source_document_id')
                    for a in aliases if ref.get('source_file') and ref.get('source_document_id'))
                if (doc['source_text_sha256'] == ref.get('source_text_sha256') or same_source
                        or (len(passage.split()) >= 5 and passage in normalized[doc['document_id']])):
                    matches.add(doc['document_id'])
            resolved = bool(ref_roots or matches)
            if key in decisions:
                decision = decisions[key];used.add(key)
                if (decision.get('human_confirmed') is not True or not isinstance(decision.get('reason'), str)
                        or not decision['reason'].strip()):
                    raise ValueError('protection_decision_needs_explicit_human_evidence')
                if decision.get('excluded_from_corpus') is True:
                    if matches:
                        raise ValueError('manual_exclusion_conflicts_with_detected_overlap')
                    resolved = True
                else:
                    targets = decision.get('document_ids', [])
                    if not targets or any(d not in doc_index for d in targets):
                        raise ValueError('invalid_protection_resolution_document')
                    matches.update(targets);resolved = True
            if not resolved:
                unresolved.append(key)
            blocked.update(groups[d][0] for d in matches if d in groups)
            reference_log.append({'reference': key, 'resolved': resolved, 'matched_documents': sorted(matches)})
    if used != set(decisions):
        raise ValueError('unknown_protection_resolution_id')
    # Keep established reservations even if the newly supplied checks find none.
    for doc_id, (group, flags) in groups.items():
        if {'gold_related', 'pilot_related'} & flags:
            blocked.add(group)
    return groups, blocked, unresolved, reference_log


def select_pilot(rows, documents, texts, protected_sets, seed=42, count=30, decisions=None):
    groups, blocked, unresolved, references = assess_protection(rows, documents, texts, protected_sets, decisions)
    audit = {'version': VERSION, 'seed': seed, 'requested': count, 'unresolved_references': unresolved,
             'protected_reference_checks': references, 'blocked_groups': sorted(blocked),
             'selection_complete': False, 'method': 'cyclic discovery features; hash-ranked; one per related-document group',
             'features_are_NOT_gold_labels': True, 'exclusion_counts': {}, 'selected_features': {}}
    if unresolved:
        return [], audit
    docs = {doc['document_id']: doc for doc in documents}
    by_doc = defaultdict(list)
    for row in rows:
        by_doc[row['document_id']].append(row)
    starts = {key: sorted(r['entity_document_start'] for r in values) for key, values in by_doc.items()}
    candidates, excluded, features = [], Counter(), {}
    protected = [row for references in protected_sets.values() for row in references]
    for row in rows:
        group, _ = groups[row['document_id']]
        doc = docs[row['document_id']]
        if group in blocked:
            excluded['protected_related_group'] += 1;continue
        if (doc.get('requires_identity_review') is not False or len(doc['potential_process_group_ids']) != 1
                or 'identity_unresolved_or_conflicting' in groups[row['document_id']][1]):
            excluded['identity_unresolved_or_conflicting'] += 1;continue
        flags = {name for name, pattern in CUES.items() if re.search(pattern, row['text'], re.I)}
        if not flags:
            flags.add('no_target_cue_NOT_unknown_gold')
        if re.fullmatch(r'[A-Z]{2,3}(?:\s+[A-Z]{2,3})*', row['entity']):
            flags.add('placeholder')
        positions = starts[row['document_id']]
        if bisect_left(positions, row['context_document_end'])-bisect_left(positions, row['context_document_start']) > 1:
            flags.add('multi_person_context')
        features[row['id']] = sorted(flags)
        candidates.append(row)
    buckets = {name: deque(sorted((r for r in candidates if name in features[r['id']]),
                           key=lambda r: digest(f"{seed}:{name}:{r['id']}")))
               for name in (*CUES, 'placeholder', 'multi_person_context', 'no_target_cue_NOT_unknown_gold')}
    selected, used_groups, used_contexts = [], set(), set()
    while len(selected) < count:
        added = False
        for name, bucket in buckets.items():
            while bucket:
                row = bucket.popleft();group = groups[row['document_id']][0]
                context = digest(' '.join(row['text'].casefold().split()))
                if group in used_groups or group in blocked or context in used_contexts:
                    continue
                if any(content_related(row, peer) for peer in protected):
                    blocked.add(group);excluded['protected_context_similarity'] += 1;continue
                if any(content_related(row, peer) for peer in selected):
                    excluded['selected_context_similarity'] += 1;continue
                item = copy.deepcopy(row)
                item['cohort'] = COHORT
                item['pilot_selection'] = {'version': VERSION, 'planning_group_id': group,
                                           'eligibility': 'explicit_protection_recheck_passed_exploratory_only',
                                           'training_eligibility': 'NOT_ESTABLISHED'}
                selected.append(item);used_groups.add(group);used_contexts.add(context)
                audit['selected_features'][row['id']] = features[row['id']]
                added = True;break
            if len(selected) == count:
                break
        if not added:
            break
    audit.update(selection_complete=len(selected) == count, selected_ids=[r['id'] for r in selected],
                 blocked_groups=sorted(blocked), exclusion_counts=dict(excluded),
                 eligible_before_context_similarity=len(candidates), selected=len(selected))
    return selected if audit['selection_complete'] else [], audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--inventory-manifest', type=Path, required=True)
    parser.add_argument('--gold', type=Path, default=ROOT/'data/eval/roles_eval_real_candidates_v1.jsonl')
    parser.add_argument('--pilot-sources', type=Path, required=True,
                        help='Private source records of the protected human pilot, not demonstrations')
    parser.add_argument('--protection-decisions', type=Path, help='Private explicit human resolutions for unidentifiable references')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        output = private_new_output(args.output_dir)
        rows, docs, summary, binding = load_bound_inventory(args.input, args.inventory_manifest)
        if summary.get('inventory_complete') is not True or summary.get('NER_executed') is not True:
            raise ValueError('complete_ner_inventory_required')
        if file_hash(args.gold) != GOLD_SHA or file_hash(args.pilot_sources) != PILOT_SOURCES_SHA:
            raise ValueError('frozen_gold_or_pilot_source_hash_mismatch')
        source_manifest = json.loads(args.inventory_manifest.read_text(encoding='utf-8'))
        texts, _ = validate_document_sources(docs, source_manifest)
        protected = {'gold': load_jsonl(args.gold), 'human_pilot': load_jsonl(args.pilot_sources)}
        for name, path in [('gold', args.gold), ('human_pilot', args.pilot_sources)]:
            binding[name] = {'path': str(path.resolve()), 'sha256': file_hash(path)}
        decisions = json.loads(args.protection_decisions.read_text(encoding='utf-8')) if args.protection_decisions else {}
        if args.protection_decisions:
            binding['protection_decisions'] = {'path': str(args.protection_decisions.resolve()), 'sha256': file_hash(args.protection_decisions)}
        selected, audit = select_pilot(rows, docs, texts, protected, args.seed, decisions=decisions)
        if any(file_hash(Path(item['path'])) != item['sha256'] for item in binding.values()):
            raise ValueError('inputs_changed_during_selection')
        output.mkdir(parents=True)
        audit.update(validated_bundle=binding, script_sha256=file_hash(Path(__file__)), cohort=COHORT,
                     observed_record_fields=sorted(set().union(*(r.keys() for r in rows))),
                     inventory_records=len(rows), inventory_documents=len(docs))
        if selected:
            target = output/'pilot_input.jsonl'
            with target.open('x', encoding='utf-8') as handle:
                for row in selected:
                    handle.write(json.dumps(row, ensure_ascii=False)+'\n')
            audit['pilot_input_sha256'] = file_hash(target)
        with (output/'selection_manifest.json').open('x', encoding='utf-8') as handle:
            json.dump(audit, handle, ensure_ascii=False, indent=2)
        print(json.dumps({'selection_complete': bool(selected), 'selected': len(selected),
                          'unresolved_reference_count': len(audit['unresolved_references']),
                          'exclusion_counts': audit['exclusion_counts'], 'LLM_calls': 0}))
        if not selected:
            raise SystemExit(1)
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(1, 'Pilot preparation failed; inspect private setup/bundle. No private text printed.\n')


if __name__ == '__main__':
    main()
