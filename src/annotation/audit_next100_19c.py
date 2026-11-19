"""Read-only source-bound capacity audit BEFORE selecting the next 100 mentions.

Reuses the historical protection protocol. No selection, prompts, model or API.
All individual IDs, exclusions and family relations are written privately only.
"""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.annotation import annotate_stj_silver_19c as core
from src.annotation import prepare_stj_pilot_19c as pilot
from src.annotation.import_claude_manual_19c import read_json
from src.annotation.plan_inventory_batches import load_bound_inventory, validate_document_sources
from src.annotation.prepare_role_annotation_batch import content_related, normalized, private_new_output
from src.data.map_role_taxonomy import load_jsonl

VERSION = '19c-next100-capacity-audit-v1'


def audit_capacity(rows, documents, texts, protected_sets, decisions=None, progress=None):
    if set(protected_sets) != {'gold', 'human_pilot', 'development_30'}:
        raise ValueError('all_three_protected_sets_required')
    groups, blocked, unresolved, references = pilot.assess_protection(
        rows, documents, texts, protected_sets, decisions)
    protected = [r for source in protected_sets.values() for r in source]
    similarity_blocks = set()
    # Group-level propagation is deliberate: a later match also excludes earlier
    # occurrences in that family. No greedy selection or per-role quotas here.
    for n, row in enumerate(rows, 1):
        group = groups[row['document_id']][0]
        if group not in blocked and group not in similarity_blocks:
            if any(content_related(row, peer) for peer in protected):
                similarity_blocks.add(group)
        if progress and (n % 100 == 0 or n == len(rows)):
            progress(n, len(rows))
    identity_groups = {
        groups[d['document_id']][0] for d in documents
        if (d.get('requires_identity_review') is not False
            or len(d.get('potential_process_group_ids', [])) != 1
            or 'identity_unresolved_or_conflicting' in groups[d['document_id']][1])
    }
    entries = []
    for row in rows:
        group = groups[row['document_id']][0]
        reasons = []
        if group in blocked:
            reasons.append('protected_related_group')
        if group in similarity_blocks:
            reasons.append('protected_context_similarity_group')
        if group in identity_groups:
            reasons.append('identity_unresolved_or_conflicting_group')
        if unresolved:
            reasons.append('protected_reference_unresolved_global_gate')
        entries.append({'id': row['id'], 'document_id': row['document_id'],
                        'source_text_sha256': row['source_text_sha256'],
                        'planning_group_id': group,
                        'entity_document_start': row['entity_document_start'],
                        'entity_document_end': row['entity_document_end'],
                        'context_sha256': pilot.digest(normalized(row['text'])),
                        'status': 'REVIEW_OR_EXCLUDED' if reasons else 'CAPACITY_ONLY_EXPLORATORY',
                        'reasons': reasons,
                        'original_review_reasons': sorted(groups[row['document_id']][1]),
                        'training_eligibility': 'NOT_ESTABLISHED'})
    available = [r for r in entries if not r['reasons']]
    context_counts = Counter(r['context_sha256'] for r in available)
    summary = {
        'version': VERSION, 'mentions': len(rows), 'documents': len(documents),
        'related_groups': len({g for g, _ in groups.values()}),
        'unresolved_reference_count': len(unresolved), 'protection_recheck_complete': not unresolved,
        'protected_related_groups': len(blocked), 'protected_similarity_groups': len(similarity_blocks),
        'identity_review_groups': len(identity_groups),
        'exclusion_reason_counts_NON_DISJOINT': dict(Counter(e for r in entries for e in r['reasons'])),
        'available_mentions_capacity_only': len(available),
        'available_documents': len({r['document_id'] for r in available}),
        'available_related_groups': len({r['planning_group_id'] for r in available}),
        'available_distinct_contexts': len(context_counts),
        'repeated_context_occurrences': sum(n-1 for n in context_counts.values()),
        'requested_future_mentions': 100, 'selected': 0, 'selection_performed': False,
        'one_per_group_upper_bound': min(len(context_counts), len({r['planning_group_id'] for r in available})),
        'capacity_is_NOT_selection_or_train_eligibility': True,
        'training_eligibility': 'NOT_ESTABLISHED', 'external_transmission_authorized': False, 'LLM_calls': 0,
    }
    return entries, {'summary': summary, 'protected_reference_checks': references,
                     'unresolved_references': unresolved,
                     'blocked_groups': sorted(blocked | similarity_blocks),
                     'identity_review_groups': sorted(identity_groups)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('input', 'inventory-manifest', 'pilot-sources', 'development-input',
                 'development-selection', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--gold', type=Path, default=ROOT/'data/eval/roles_eval_real_candidates_v1.jsonl')
    parser.add_argument('--protection-decisions', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        output = private_new_output(args.output_dir)
        rows, documents, summary, binding = load_bound_inventory(args.input, args.inventory_manifest)
        if summary.get('inventory_complete') is not True or summary.get('NER_executed') is not True:
            raise ValueError('complete_inventory_required')
        if core.file_hash(args.gold) != pilot.GOLD_SHA or core.file_hash(args.pilot_sources) != pilot.PILOT_SOURCES_SHA:
            raise ValueError('frozen_protected_source_changed')
        development = core.load_pilot(args.development_input, args.development_selection)
        selection = read_json(args.development_selection)
        for key in ('input', 'inventory_manifest'):
            if binding[key]['sha256'] != selection['validated_bundle'][key]['sha256']:
                raise ValueError('development_inventory_binding_mismatch')
        texts, _ = validate_document_sources(documents, read_json(args.inventory_manifest))
        for key in ('gold', 'pilot_sources', 'development_input', 'development_selection'):
            path = getattr(args, key)
            binding[key] = {'path': str(path.resolve()), 'sha256': core.file_hash(path)}
        decisions = read_json(args.protection_decisions) if args.protection_decisions else {}
        if args.protection_decisions:
            binding['protection_decisions'] = {'path': str(args.protection_decisions.resolve()),
                                               'sha256': core.file_hash(args.protection_decisions)}
        # Keep the evidence used for the original cohort and current resolutions
        # in the before/after binding; validate_decision still verifies each proof.
        for key, value in selection['validated_bundle'].items():
            binding['development_bundle_' + key] = value
        for i, item in enumerate(e for d in decisions.values() for e in d.get('evidence', [])):
            binding['current_evidence_' + str(i)] = {'path': item['path'], 'sha256': item['sha256']}
        sets = {'gold': load_jsonl(args.gold), 'human_pilot': load_jsonl(args.pilot_sources),
                'development_30': development}
        entries, audit = audit_capacity(rows, documents, texts, sets, decisions,
            progress=lambda n, total: print(f'Protection content audit: {n}/{total}', flush=True))
        if any(core.file_hash(Path(v['path'])) != v['sha256'] for v in binding.values()):
            raise ValueError('inputs_changed_during_audit')
        audit.update(validated_bundle=binding, script_sha256=core.file_hash(Path(__file__)))
        output.mkdir(parents=True)
        with (output/'mention_capacity_PRIVATE.jsonl').open('x', encoding='utf-8') as handle:
            for entry in entries:
                handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
        (output/'audit_PRIVATE.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(audit['summary']))
        return 0 if not audit['unresolved_references'] else 1
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(1, 'next100_audit_failed; inspect private source bindings; no private content printed.\n')


if __name__ == '__main__':
    sys.exit(main())
