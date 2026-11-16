"""Plan ALL private mention IDs, never train/eval splits or shareable texts.

Bind inputs to the same-prefix document/prediction bundle before writing.
Unknown protection checks propagate across related sources and stay under review.
No NER, annotation, external transmission or changes to inventory files.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.annotation.prepare_role_annotation_batch import Components, identity_roots, private_new_output
from src.data.map_role_taxonomy import load_jsonl
from src.data.extract_role_candidates_v2 import read_documents
from src.data.role_provenance import normalize_process_group_id
from src.utils.entity_marking import mark_entity

VERSION = 'private-inventory-batches-v2'
FLAGS = ('gold_known_process_overlap', 'gold_context_containment_flag', 'pilot_related_block')


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_document_sources(documents, manifest):
    """Bind document text hashes to the manifest's original file fingerprints.

    Read only: uses the existing reader, never loads a model. Missing/moved or
    changed sources require explicit local reconciliation, never count-only trust.
    """
    directory = Path(manifest['source_inventory']['directory']).resolve()
    sources = {}
    for name, value in manifest['input_files'].items():
        if name.startswith('source_'):
            if value['sha256'] != manifest['inputs_sha256'][name]:
                raise ValueError('manifest_source_fingerprint_mismatch')
            sources[Path(value['path']).resolve()] = value['sha256']
    texts, checked, cache = {}, {}, {}
    for doc in documents:
        source = doc['canonical_source']
        path = (directory / source['source_file']).resolve()
        if not path.is_relative_to(directory) or path not in sources:
            raise ValueError('document_source_not_in_manifest')
        if path not in cache:
            if file_hash(path) != sources[path]:
                raise ValueError('original_source_changed')
            cache[path] = {key: text for key, text, _ in read_documents(path)}
            checked['source_' + str(len(checked))] = {'path': str(path), 'sha256': sources[path]}
        text = cache[path][source['source_document_id']]
        if digest(text) != doc['source_text_sha256'] or len(text) != doc['characters']:
            raise ValueError('document_text_hash_mismatch')
        texts[doc['document_id']] = text
    return texts, checked


def check_unannotated(row):
    if ('suggested_label' in row or row.get('human_validated') is not False
            or row.get('label') is not None or row.get('labels') not in (None, [])
            or row.get('annotation_tier', 'UNANNOTATED') != 'UNANNOTATED'
            or row.get('proposed_labels') or row.get('experimental_categories')
            or row.get('other_roles') or row.get('annotation_source') is not None):
        raise ValueError('expected_unannotated_hint_free_inventory')


def review_reasons(row):
    reasons = set()
    checks = row.get('reference_checks') or {}
    if row.get('gold_known_process_overlap') is True or row.get('gold_context_containment_flag') is True:
        reasons.add('gold_related')
    if row.get('pilot_related_block') is True:
        reasons.add('pilot_related')
    if (checks.get('gold') != 'checked' or checks.get('pilot') != 'checked'
            or any(type(row.get(field)) is not bool for field in FLAGS)):
        reasons.add('protected_reference_checks_incomplete')
    if row.get('requires_identity_review') is not False:
        reasons.add('identity_unresolved_or_conflicting')
    return reasons


def plan_batches(rows, batch_size=100, documents=None):
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError('invalid_batch_size')
    graph = Components()
    reasons = defaultdict(set)
    metadata = list(documents or []) + list(rows)
    for row in metadata:
        node = ('document', row['document_id'])
        graph.find(node)
        for field in ('source_text_sha256', 'split_block_id'):
            if row.get(field):
                graph.join(node, (field, row[field]))
        roots = identity_roots(row)
        roots.update(normalize_process_group_id(v) for v in row.get('potential_process_group_ids', []))
        for alias in row.get('aliases', []):
            roots.update(identity_roots(alias))
        for root in roots - {None}:
            graph.join(node, ('process', root))
    members = defaultdict(set)
    for row in metadata:
        component = graph.find(('document', row['document_id']))
        members[component].add(row['document_id'])
        reasons[component].update(review_reasons(row))
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        if row['id'] in seen:
            raise ValueError('duplicate_mention_id')
        seen.add(row['id'])
        mark_entity(row['text'], row['entity_start'], row['entity_end'])
        if row['text'][row['entity_start']:row['entity_end']] != row['entity']:
            raise ValueError('entity_mismatch')
        check_unannotated(row)
        component = graph.find(('document', row['document_id']))
        flags = reasons[component]
        cohort = ('reserved_gold_related' if 'gold_related' in flags else
                  'reserved_pilot_related' if 'pilot_related' in flags else
                  'reference_review_required' if 'protected_reference_checks_incomplete' in flags else
                  'identity_review_required' if flags else 'unassigned_development_NOT_a_train_split')
        group = 'group_' + digest(json.dumps(sorted(members[component])))
        groups[cohort].append((row, group, flags))
    result = []
    for cohort, items in sorted(groups.items()):
        items.sort(key=lambda item: (item[1], item[0]['document_id'], item[0]['entity_document_start'], item[0]['id']))
        for start in range(0, len(items), batch_size):
            chunk = items[start:start + batch_size]
            result.append({
                'batch_id': f'batch_{len(result) + 1:04}', 'cohort': cohort,
                'mention_ids': [row['id'] for row, _, _ in chunk],
                'document_ids': sorted({row['document_id'] for row, _, _ in chunk}),
                'split_block_ids': sorted({row['split_block_id'] for row, _, _ in chunk}),
                'planning_group_ids': sorted({group for _, group, _ in chunk}),
                'review_reasons': sorted(set().union(*(flags for _, _, flags in chunk))),
                'split_assignment': None, 'training_eligibility': 'NOT_ESTABLISHED',
                'privacy_release_status': 'NOT_APPROVED_NO_EXTERNAL_TEXT_EXPORT'})
    assert sum(len(batch['mention_ids']) for batch in result) == len(rows)
    return result


def load_bound_inventory(input_path, manifest_path):
    """Check producer IDs, document hashes, metadata and accepted predictions.

    Existing NER manifests lack output digests. Cross-check companion artifacts,
    then hash the validated bundle in the NEW plan. This checks consistency, not
    authenticity of an entirely replaced/forged bundle.
    """
    if not manifest_path.name.endswith('_manifest.json'):
        raise ValueError('expected_inventory_manifest_suffix')
    prefix = manifest_path.name[:-len('manifest.json')]
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    summary = manifest['summary']
    is_ner = summary.get('NER_executed') is True
    suffix = 'mentions.jsonl' if is_ner else 'known_mentions_PARTIAL.jsonl'
    if input_path.resolve() != (manifest_path.parent / (prefix + suffix)).resolve():
        raise ValueError('input_not_inventory_companion')
    paths = {'input': input_path, 'inventory_manifest': manifest_path,
             'documents': manifest_path.parent / (prefix + 'documents.jsonl')}
    if is_ner:
        paths['ner_predictions'] = manifest_path.parent / (prefix + 'ner_predictions.jsonl')
    before = {key: file_hash(path) for key, path in paths.items()}
    rows = load_jsonl(input_path)
    documents = load_jsonl(paths['documents'])
    index = {}
    for doc in documents:
        sha = doc['source_text_sha256']
        if (len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha)
                or doc['document_id'] != 'doc_' + sha or doc['document_id'] in index):
            raise ValueError('invalid_or_duplicate_document_identity')
        index[doc['document_id']] = doc
    expected = (summary.get('total_PER_mentions_complete') if summary.get('inventory_complete') is True else
                summary.get('accepted_mentions_this_run') if is_ner else summary.get('recovered_known_occurrences_lower_bound'))
    if type(expected) is not int or len(rows) != expected or len(documents) != summary.get('unique_texts'):
        raise ValueError('inventory_count_mismatch')
    source_texts, source_binding = validate_document_sources(documents, manifest)
    keys = set()
    for row in rows:
        doc = index.get(row['document_id'])
        if doc is None or row['source_text_sha256'] != doc['source_text_sha256']:
            raise ValueError('mention_document_mismatch')
        a, b = row['entity_document_start'], row['entity_document_end']
        left, right = row['context_document_start'], row['context_document_end']
        if (any(type(n) is not int for n in (a, b, left, right))
                or not 0 <= left <= a < b <= right <= doc['characters']
                or len(row['text']) != right-left
                or row['entity_start'] != a-left or row['entity_end'] != b-left
                or row['id'] != 'per_' + digest(f"{doc['source_text_sha256']}:{a}:{b}")
                or row['context_id'] != 'ctx_' + digest(f"{row['id']}:{left}:{right}")):
            raise ValueError('mention_hash_or_document_offsets_mismatch')
        if source_texts[row['document_id']][left:right] != row['text']:
            raise ValueError('context_not_original_source_slice')
        key = (row['document_id'], a, b)
        if key in keys:
            raise ValueError('duplicate_occurrence')
        keys.add(key)
        for field in ('split_block_id', 'requires_identity_review', *FLAGS):
            if row.get(field) != doc.get(field):
                raise ValueError('mention_document_metadata_mismatch')
        if row.get('reference_checks', {}) != doc.get('reference_checks', {}):
            raise ValueError('mention_reference_checks_mismatch')
        if row['process_group_id_candidates'] != doc['potential_process_group_ids']:
            raise ValueError('mention_process_roots_mismatch')
        if any(row[field] != doc['canonical_source'][field] for field in ('source_file', 'source_document_id')):
            raise ValueError('mention_source_mismatch')
    if is_ner:
        predictions = {}
        for prediction in load_jsonl(paths['ner_predictions']):
            if prediction.get('accepted_PER') is not True:
                continue
            key = (prediction['document_id'], prediction['start'], prediction['end'])
            if (key in predictions or prediction.get('ner_label') != 'PER'
                    or prediction.get('offsets_valid') is not True):
                raise ValueError('invalid_accepted_prediction')
            predictions[key] = prediction
        if keys != predictions.keys():
            raise ValueError('accepted_prediction_ids_mismatch')
        for row in rows:
            prediction = predictions[(row['document_id'], row['entity_document_start'], row['entity_document_end'])]
            if prediction['mention_id'] != row['id'] or any(prediction[field] != row[field] for field in (
                    'entity', 'text', 'entity_start', 'entity_end', 'context_document_start', 'context_document_end', 'context_id')):
                raise ValueError('prediction_context_mismatch')
    if before != {key: file_hash(path) for key, path in paths.items()}:
        raise ValueError('inventory_changed_during_validation')
    binding = {key: {'path': str(paths[key].resolve()), 'sha256': value} for key, value in before.items()}
    binding.update(source_binding)
    return rows, documents, summary, binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--inventory-manifest', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    try:
        output = private_new_output(args.output_dir)
        rows, documents, summary, binding = load_bound_inventory(args.input, args.inventory_manifest)
        complete = summary.get('inventory_complete') is True
        if not complete and not args.allow_partial:
            raise ValueError('partial_inventory_requires_allow_partial')
        batches = plan_batches(rows, args.batch_size, documents)
        if any(file_hash(Path(item['path'])) != item['sha256'] for item in binding.values()):
            raise ValueError('inventory_changed_during_planning')
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(1, 'Planning failed: check private bundle paths, IDs, hashes, offsets, annotation state and completeness. No output created.\n')
    counts = {'mentions': len(rows), 'batches': len(batches), 'inventory_complete': complete,
              'cohort_mentions': dict(Counter({c: sum(len(b['mention_ids']) for b in batches if b['cohort'] == c)
                                              for c in sorted({b['cohort'] for b in batches})})),
              'external_transmission_authorized': False, 'LLM_calls': 0}
    output.mkdir(parents=True)
    for batch in batches:
        with (output / (batch['batch_id'] + '.json')).open('x', encoding='utf-8') as handle:
            json.dump(batch, handle, indent=2)
    manifest = {'version': VERSION, 'validated_bundle': binding,
                'input_sha256': binding['input']['sha256'],
                'inventory_manifest_sha256': binding['inventory_manifest']['sha256'],
                'script_sha256': file_hash(Path(__file__)), 'batch_size': args.batch_size, 'summary': counts,
                'warning': 'Batches are NOT splits or training eligibility. Keep planning_group_id together in every future split. No shareable text created.'}
    with (output / 'manifest.json').open('x', encoding='utf-8') as handle:
        json.dump(manifest, handle, indent=2)
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
