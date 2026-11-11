"""Plan the entire audited STJ corpus without NER; explicit --run-ner inventories it.

All row-level outputs are private, new, Git-ignored files. No LLM/API calls.
No role sampling, no name-based deduplication, no gold annotations or training.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.annotation.prepare_role_annotation_batch import Components, document_key, identity_roots, private_new_output
from src.annotation.export_external_annotation import TASK_INSTRUCTIONS, response_schema
from src.data.extract_role_candidates_v2 import detect_person_spans, load_person_ner, read_documents, rejected_per_reason, ProgressReporter, SUPPORTED_SUFFIXES, process_number_from_filename
from src.data.map_role_taxonomy import load_jsonl, load_taxonomy
from src.data.role_provenance import normalize_process_group_id, extract_process_provenance

VERSION = "19b-corpus-inventory-v2-source-inputs"
TAXONOMY_V2 = ROOT/'config/role_taxonomy_v2.json'


def annotation_task(config_path=TAXONOMY_V2):
    labels,_=load_taxonomy(config_path)
    schema=response_schema()
    schema['properties']['id']={'type':'string','minLength':1}
    schema['properties']['labels']['items']['enum']=labels
    schema['properties']['evidence']['items']['properties']['label']['enum']=labels
    schema['properties']['scope']['propertyNames']['enum']=labels
    schema['properties']['other_roles']={
        'type':'array','items':{'type':'object','additionalProperties':False,
        'required':['role','quote','scope'],'properties':{
            'role':{'type':'string','minLength':1,'maxLength':120},
            'quote':{'type':'string','maxLength':240},
            'scope':{'enum':['current_proceeding','cited_proceeding','both','unclear','not_applicable']}}}}
    instructions=TASK_INSTRUCTIONS.replace('REFERENCE é experimental:', 'REFERENCE:').replace(
        'sem nenhum dos oito papéis suportado.', 'sem nenhum dos nove papéis específicos suportado.')
    instructions+='\nPreserve labels específicas e múltiplas quando sustentadas. Registe outros papéis explícitos fora da lista em other_roles (role, quote, scope), sem inventar labels principais. UNKNOWN pode coexistir com other_roles quando nenhum dos nove papéis específicos é suportado; incerteza não é UNKNOWN. REFERENCE pertence à taxonomia principal desta versão; não implica excluir identidades da anonimização. Nunca reduza as labels específicas às agrupadas na anotação.'
    return {'instructions':instructions,'response_schema':schema,'allowed_labels':labels,
            'taxonomy_config':str(config_path),'taxonomy_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),
            'annotation_tier':'SILVER','human_validated':False,'external_transmission_authorized':False,
            'privacy_gate':'Must create a separately pseudonymized, inspected export; NEVER upload this private inventory.'}


def validate_smoke_manifest(path, expected_unique=191):
    manifest=json.loads(path.read_text(encoding='utf-8'));summary=manifest['summary']
    if (summary.get('unique_texts')!=expected_unique or summary.get('NER_documents_processed')!=3
            or not summary.get('NER_executed') or summary.get('accepted_mentions_this_run',0)<1):
        raise ValueError('smoke_not_successful_three_documents')
    if manifest['script_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('script_changed_since_smoke')
    if manifest['extractor_sha256']!=hashlib.sha256((ROOT/'src/data/extract_role_candidates_v2.py').read_bytes()).hexdigest():
        raise ValueError('extractor_changed_since_smoke')
    for source in manifest.get('input_files',{}).values():
        if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('input_changed_since_smoke')
    if not manifest.get('input_files'):raise ValueError('smoke_missing_input_fingerprints')
    inventory=manifest.get('source_inventory')
    if inventory is not None:
        current=sorted(p.relative_to(Path(inventory['directory'])).as_posix()
                       for p in Path(inventory['directory']).rglob('*')if p.is_file())
        if current!=inventory['files']:raise ValueError('source_directory_changed_since_smoke')
    return summary


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def union_length(ranges):
    result, right = 0, 0
    for a, b in sorted(ranges):
        result += max(0, b - max(a, right))
        right = max(right, b)
    return result


def full_windows(text, width=6000, overlap=600):
    if width < 2 or not 0 < overlap < width:
        raise ValueError("invalid_window_parameters")
    windows, start = [], 0
    while start < len(text):
        end = min(len(text), start + width)
        windows.append((start, end))
        if end == len(text):
            break
        start = end - overlap
    return windows


def load_source_corpus(input_dir, legacy_audit=None):
    """Build the existing metadata shape from original documents by default.

    An explicit old audit is an optional hash-checked reference, never a required
    corpus index. Unreadable documents fail; non-document/unsupported files are
    accounted for explicitly rather than silently swallowed.
    """
    input_dir=input_dir.resolve()
    if not input_dir.is_dir():raise FileNotFoundError('input_directory_missing')
    files=sorted(p for p in input_dir.rglob('*')if p.is_file())
    inventory={'directory':str(input_dir),'files':[p.relative_to(input_dir).as_posix()for p in files]}
    texts,source_paths={},{}
    if legacy_audit is not None:
        audit=json.loads(legacy_audit.read_text(encoding='utf-8'));loaded={}
        for row in audit['document_provenance']:
            source=row['source_file'];path=(input_dir/source).resolve()
            if not path.is_relative_to(input_dir):raise ValueError('source_outside_input_directory')
            source_paths[source]=path
            if source not in loaded:loaded[source]={key:text for key,text,_ in read_documents(path)}
            texts[document_key(row)]=loaded[source][row['source_document_id']]
        return audit,texts,source_paths,inventory
    audit={'document_provenance':[],'document_profiles':[],'source_mode':'original_documents',
           'skipped_files':[],'ner_span_counts':{}}
    for original in files:
        path=original.resolve();relative=original.relative_to(input_dir).as_posix()
        if not path.is_relative_to(input_dir):raise ValueError('source_outside_input_directory')
        if path.suffix.lower()=='.doc':raise ValueError('legacy_DOC_requires_preconversion')
        if path.suffix.lower()not in SUPPORTED_SUFFIXES:
            audit['skipped_files'].append({'source_file':relative,'reason':'unsupported_extension'})
            continue
        # Missing, unreadable, malformed and empty text sources are NOT ignored.
        source_paths[relative]=path
        extracted=read_documents(path)
        if not extracted:
            audit['skipped_files'].append({'source_file':relative,'reason':'no_extractable_document_text'})
        for key,text,legacy in extracted:
            if not text.strip():raise ValueError('empty_source_document')
            doc_key=(relative,key)
            if doc_key in texts:raise ValueError('duplicate_source_document_key')
            texts[doc_key]=text
            legacy=legacy or process_number_from_filename(path)
            provenance=extract_process_provenance(text,relative,legacy)
            audit['document_provenance'].append({'source_file':relative,'source_document_id':key,**provenance})
            audit['document_profiles'].append({'source_file':relative,'source_document_id':key,
                'process_number':legacy,'characters':len(text),'ner_window_ranges':[]})
    if not texts:raise ValueError('no_source_documents')
    return audit,texts,source_paths,inventory


def build_documents(audit, texts, pilot=None, gold=None):
    profiles = {document_key(row): row for row in audit["document_profiles"]}
    grouped = defaultdict(list)
    graph = Components()
    for original in audit["document_provenance"]:
        key = document_key(original)
        row = {**original, "process_number": profiles[key].get("process_number")}
        sha = row["source_text_sha256"]
        if digest(texts[key]) != sha or len(texts[key]) != profiles[key]["characters"]:
            raise ValueError("source_hash_or_length_mismatch")
        grouped[sha].append(row)
        graph.find(("text", sha))
        for root in sorted(identity_roots(row)):
            graph.join(("text", sha), ("group", root))
    members, roots = defaultdict(list), defaultdict(set)
    for sha, aliases in grouped.items():
        component = graph.find(("text", sha))
        members[component].append(sha)
        for row in aliases:
            roots[component].update(identity_roots(row))
    pilot_keys = {document_key(row) for row in (pilot or [])}
    pilot_hashes = {sha for sha, aliases in grouped.items() if any(document_key(row) in pilot_keys for row in aliases)}
    pilot_blocks = {graph.find(("text", sha)) for sha in pilot_hashes}
    gold_groups = {normalize_process_group_id(row.get("process_number")) for row in (gold or [])} - {None}
    gold_passages = [" ".join(row["text"].casefold().split()) for row in (gold or []) if len(row["text"].split()) >= 5]
    documents = []
    for sha, aliases in sorted(grouped.items()):
        aliases.sort(key=document_key)
        canonical = aliases[0]
        text = texts[document_key(canonical)]
        component = graph.find(("text", sha))
        old_ranges = [r for row in aliases for r in profiles[document_key(row)]["ner_window_ranges"]]
        block = digest(json.dumps(sorted(members[component])))
        root_values = sorted(roots[component])
        normalized = " ".join(text.casefold().split())
        documents.append({
            "document_id": "doc_" + sha, "source_text_sha256": sha,
            "canonical_source": {k: canonical[k] for k in ("source_file", "source_document_id")},
            "aliases": aliases, "characters": len(text), "words_whitespace": len(text.split()),
            "split_block_id": "block_" + block, "potential_process_group_ids": root_values,
            "requires_identity_review": len(root_values) != 1 or any(row["process_provenance"]["status"] == "conflict" for row in aliases),
            "old_window_covered_characters": union_length(old_ranges) if audit.get('source_mode')!='original_documents' else None,
            "pilot_related_block": component in pilot_blocks if pilot is not None else None,
            "gold_known_process_overlap": bool(set(root_values) & gold_groups) if gold is not None else None,
            "gold_context_containment_flag": any(passage in normalized for passage in gold_passages) if gold is not None else None,
            "reference_checks": {'pilot':'checked'if pilot is not None else 'not_requested',
                                 'gold':'checked'if gold is not None else 'not_requested'},
        })
    return documents


def make_mention(document, text, start, end, entity, context_chars=800):
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text) or text[start:end] != entity:
        raise ValueError("invalid_mention_offsets")
    a, b = max(0, start-context_chars), min(len(text), end+context_chars)
    mention_id = "per_" + digest(f"{document['source_text_sha256']}:{start}:{end}")
    return {"id": mention_id, "document_id": document["document_id"],
            "source_text_sha256": document["source_text_sha256"], "split_block_id": document["split_block_id"],
            "source_file": document["canonical_source"]["source_file"],
            "source_document_id": document["canonical_source"]["source_document_id"],
            "process_group_id_candidates": document["potential_process_group_ids"],
            "requires_identity_review": document["requires_identity_review"],
            "pilot_related_block": document["pilot_related_block"],
            "gold_known_process_overlap": document["gold_known_process_overlap"],
            "gold_context_containment_flag": document["gold_context_containment_flag"],
            "reference_checks": document.get('reference_checks',{}),
            "entity": entity, "entity_document_start": start, "entity_document_end": end,
            "context_document_start": a, "context_document_end": b,
            "context_id": "ctx_" + digest(f"{mention_id}:{a}:{b}"),
            "text": text[a:b], "entity_start": start-a, "entity_end": end-a,
            "context_policy": "verbatim_800_chars_each_side_default_not_guaranteed_sufficient",
            "context_chars_each_side": context_chars,
            "label": None, "human_validated": False, "annotation_tier": "UNANNOTATED"}


def known_mentions(documents, text_by_hash, candidates, context_chars=800):
    index = {row["source_text_sha256"]: row for row in documents}
    grouped = defaultdict(list)
    for row in candidates:
        grouped[(row["source_text_sha256"], row["entity_document_start"], row["entity_document_end"])].append(row)
    mentions = []
    for (sha, start, end), variants in sorted(grouped.items()):
        if any(row["entity"] != variants[0]["entity"] for row in variants):
            raise ValueError("same_occurrence_entity_disagreement")
        mention = make_mention(index[sha], text_by_hash[sha], start, end, variants[0]["entity"], context_chars)
        mention["inventory_origin"] = "PARTIAL_recovered_from_sampled_19a_not_complete_NER"
        mention["legacy_candidate_ids"] = [row["id"] for row in variants]
        # Keep differing old contexts privately; do not turn different lexical
        # suggestions into gold multi-label or leak those hints to an annotator.
        contexts = {(row["entity_document_start"]-row["entity_start"], row["text"]) for row in variants}
        mention["legacy_context_variants"] = [{"start": a, "text": t} for a, t in sorted(contexts)]
        mentions.append(mention)
    return mentions


def recover_saved_context_ner(mentions, documents, text_by_hash, saved_map, context_chars=800):
    """Reuse exact saved PER offsets; retain conflicts without guessing spans."""
    index = {row['source_text_sha256']:row for row in documents}
    existing = {(row['source_text_sha256'],row['entity_document_start'],row['entity_document_end']):row for row in mentions}
    proposals, log = defaultdict(list), []
    for record in saved_map['records']:
        source = record['original_record']; sha = source['source_text_sha256']
        text = text_by_hash[sha]
        base = source['entity_document_start']-source['entity_start']
        if not 0 <= base <= len(text) or text[base:base+len(source['text'])] != source['text']:
            raise ValueError('saved_context_source_mismatch')
        for span in record.get('ner_spans',[]):
            if span['label'] != 'PER':continue
            a,b = span['start'],span['end']
            if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(source['text']):
                raise ValueError('invalid_saved_span_offsets')
            entity=source['text'][a:b]; start,end=base+a,base+b
            if text[start:end] != entity:raise ValueError('saved_span_source_mismatch')
            key=(sha,start,end)
            entry={'document_id':index[sha]['document_id'],'entity_document_start':start,
                   'entity_document_end':end,'entity':entity,'source_export_id':record['export_id']}
            if key in existing:entry['recovery_status']='exact_existing_occurrence'
            elif (a==0 and base>0) or (b==len(source['text']) and base+b<len(text)):
                entry['recovery_status']='context_boundary_needs_review'
            elif rejected_per_reason(entity):entry['recovery_status']='automatic_filter_needs_review'
            else:
                proposals[key].append(entry)
                continue
            log.append(entry)
    accepted=[]
    for key,entries in sorted(proposals.items()):
        sha,a,b=key
        conflicting = any(other_sha==sha and a<other_end and other_start<b and (other_start,other_end)!=(a,b)
                          for other_sha,other_start,other_end in list(existing)+list(proposals))
        status='overlapping_variant_needs_review' if conflicting else 'new_cached_PER_occurrence'
        for entry in entries:entry['recovery_status']=status
        log.extend(entries)
        if not conflicting:
            row=make_mention(index[sha],text_by_hash[sha],a,b,entries[0]['entity'],context_chars)
            row['inventory_origin']='PARTIAL_recovered_saved_context_NER_not_complete_corpus'
            row['cached_export_ids']=sorted({entry['source_export_id']for entry in entries})
            accepted.append(row)
    result=sorted(mentions+accepted,key=lambda row:(row['source_text_sha256'],row['entity_document_start'],row['entity_document_end']))
    return result,log,{'saved_PER_predictions':len(log),'new_cached_occurrences':len(accepted),
                      'recovery_status_counts':dict(Counter(row['recovery_status']for row in log))}


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--audit", type=Path, help="Optional explicit legacy audit for source-hash comparison")
    parser.add_argument("--candidates", type=Path, help="Optional explicit old candidates for mention recovery only")
    parser.add_argument("--pilot", type=Path, help="Optional explicit pilot for overlap checks, not required by NER")
    parser.add_argument("--gold", type=Path, help="Optional explicit gold for overlap checks, not required by NER")
    parser.add_argument("--prefix", type=Path, default=ROOT/'data/raw/experiment_19b_corpus_plan02')
    parser.add_argument("--report", type=Path, default=ROOT/'results/experiment_19b_corpus_plan02.md')
    parser.add_argument("--context-chars", type=int, default=800)
    parser.add_argument("--run-ner", action="store_true", help="EXPLICIT full-coverage local NER; no LLM calls")
    parser.add_argument("--ner-model", type=Path, default=ROOT/'models/eduardo_extended_model')
    parser.add_argument("--gpu-id", type=int)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--progress-seconds", type=float, default=10)
    parser.add_argument("--expected-unique-documents", type=int)
    parser.add_argument("--taxonomy-config", type=Path, default=TAXONOMY_V2)
    parser.add_argument("--max-documents", type=int, help="Explicit NER smoke limit only; no limit by default")
    parser.add_argument("--reuse-privacy-map", type=Path, action='append', default=[],
                        help="Recover saved NER spans from a PRIVATE export map, without model inference")
    args = parser.parse_args()
    if args.context_chars < 1 or args.batch_size < 1 or args.progress_seconds<=0 or (args.max_documents is not None and args.max_documents < 1):
        parser.error("Positive context, batch size and optional document limit required")
    suffixes = ['documents.jsonl', 'manifest.json', 'task.json']
    if not args.run_ner:suffixes+=['known_mentions_PARTIAL.jsonl']
    if args.reuse_privacy_map:suffixes += ['cached_span_review_PRIVATE.jsonl']
    if args.run_ner:
        suffixes += ['mentions.jsonl', 'ner_predictions.jsonl']
    paths = {name: private_new_output(Path(str(args.prefix)+'_'+name)) for name in suffixes}
    if args.report.exists() or not args.report.resolve().is_relative_to((ROOT/'results').resolve()):
        parser.error("Report must be a NEW file under results/")
    for path in list(paths.values()) + [args.report]:
        path.parent.mkdir(parents=True, exist_ok=True)
    inputs = {name: path for name, path in [('audit', args.audit), ('candidates', args.candidates), ('pilot', args.pilot), ('gold', args.gold)] if path is not None}
    inputs['taxonomy']=args.taxonomy_config
    inputs.update({f'privacy_map_{i}':path for i,path in enumerate(args.reuse_privacy_map)})
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()}
    audit,texts,source_paths,source_inventory=load_source_corpus(args.input_dir,args.audit)
    for i,(source,path)in enumerate(sorted(source_paths.items())):
        name=f'source_{i}';inputs[name]=path;hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    pilot=load_jsonl(args.pilot) if args.pilot is not None else None
    gold=load_jsonl(args.gold) if args.gold is not None else None
    candidates=load_jsonl(args.candidates) if args.candidates is not None else []
    documents = build_documents(audit, texts, pilot, gold)
    if args.expected_unique_documents is not None and len(documents)!=args.expected_unique_documents:
        raise ValueError('unexpected_unique_document_count_before_NER')
    by_hash = {row['source_text_sha256']: texts[document_key(row['canonical_source'])] for row in documents}
    recovered = known_mentions(documents, by_hash, candidates, args.context_chars)
    legacy_recovered_count=len(recovered)
    cache_log,cache_summaries=[],[]
    for path in args.reuse_privacy_map:
        recovered,review,cache_summary=recover_saved_context_ner(recovered,documents,by_hash,json.loads(path.read_text(encoding='utf-8')),args.context_chars)
        cache_log.extend(review);cache_summaries.append(cache_summary)
    proposed_windows = sum(len(full_windows(by_hash[row['source_text_sha256']])) for row in documents)
    full_input_chars = sum(sum(b-a for a,b in full_windows(by_hash[row['source_text_sha256']])) for row in documents)
    summary = {
        'audited_documents': len(texts), 'unique_texts': len(documents), 'duplicate_text_versions': len(texts)-len(documents),
        'unique_text_characters': sum(row['characters'] for row in documents),
        'unique_text_words_whitespace': sum(row['words_whitespace'] for row in documents),
        'largest_document_characters': max(row['characters'] for row in documents),
        'split_blocks_conservative': len({row['split_block_id'] for row in documents}),
        'documents_requiring_identity_review': sum(row['requires_identity_review'] for row in documents),
        'documents_in_multi_root_blocks': sum(len(row['potential_process_group_ids'])>1 for row in documents),
        'documents_without_component_root': sum(not row['potential_process_group_ids'] for row in documents),
        'old_covered_unique_characters': sum(row['old_window_covered_characters']or 0 for row in documents) if args.audit is not None else None,
        'old_accepted_PER_across_duplicate_versions_NOT_unique': audit.get('ner_span_counts',{}).get('accepted_per_spans'),
        'recovered_known_occurrences_lower_bound': len(recovered),
        'recovered_from_19a_only': legacy_recovered_count,
        'reused_privacy_cache_summary':cache_summaries,
        'legacy_duplicate_occurrence_records': len(candidates)-legacy_recovered_count if args.candidates is not None else None,
        'known_occurrences_with_multiple_contexts': sum(len(row.get('legacy_context_variants',[]))>1 for row in recovered),
        'total_PER_mentions_complete': None,
        'planned_full_coverage_windows_6000_overlap_600': proposed_windows,
        'planned_NER_input_characters_including_overlap': full_input_chars,
        'pilot_related_unique_documents': sum(row['pilot_related_block'] for row in documents) if pilot is not None else None,
        'gold_known_process_overlap_documents': sum(row['gold_known_process_overlap'] for row in documents) if gold is not None else None,
        'gold_context_containment_documents': sum(row['gold_context_containment_flag'] for row in documents) if gold is not None else None,
        'gold_process_ids_not_normalized': sum(normalize_process_group_id(row.get('process_number')) is None for row in gold) if gold is not None else None,
        'reference_checks':{'pilot':'checked'if pilot is not None else 'not_requested',
                            'gold':'checked'if gold is not None else 'not_requested'},
        'source_mode':'explicit_legacy_audit'if args.audit is not None else 'original_documents',
        'source_files_skipped_by_reason':dict(Counter(row['reason']for row in audit.get('skipped_files',[]))),
        'NER_executed': args.run_ner, 'LLM_calls': 0, 'inventory_complete': False,
    }
    ner_metadata=None
    if args.run_ner:
        os.environ['HF_HUB_OFFLINE']='1'; os.environ['TRANSFORMERS_OFFLINE']='1'
        os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
        ner_started=time.perf_counter()
        nlp = load_person_ner(args.ner_model, gpu_id=args.gpu_id)
        ner_metadata=getattr(nlp,'meta',{}).get('candidate_extraction_audit',{})
        selected_docs = documents[:args.max_documents] if args.max_documents else documents
        stats = Counter(); count = 0; raw_per_count = 0; valid_per_count = 0
        with ProgressReporter(args.progress_seconds) as progress, paths['mentions.jsonl'].open('x', encoding='utf-8') as mentions_file, paths['ner_predictions.jsonl'].open('x', encoding='utf-8') as predictions_file:
            progress(stage='full_coverage_NER',total=len(selected_docs),files=len(source_paths))
            for ordinal, doc in enumerate(selected_docs, 1):
                text = by_hash[doc['source_text_sha256']]
                progress(stage='NER_inference',documents=ordinal-1,document_characters=len(text),planned_windows=len(full_windows(text)))
                predictions = []
                accepted = detect_person_spans(text, nlp, batch_size=args.batch_size, stats=stats,
                                              windows=full_windows(text), prediction_sink=predictions.append,progress=progress)
                accepted_keys = {(a,b) for a,b,_ in accepted}
                # One raw prediction per exact span/label; retain all window
                # provenance and raw PER not accepted by conservative filters.
                grouped = defaultdict(list)
                for p in predictions:
                    grouped[(p['start'],p['end'],p['label'],p['text'])].append([p['window_start'],p['window_end']])
                for (a,b,label,entity), windows in sorted(grouped.items()):
                    valid = 0 <= a < b <= len(text) and text[a:b]==entity
                    payload = {'document_id': doc['document_id'], 'start':a, 'end':b, 'entity':entity, 'ner_label':label,
                               'offsets_valid': valid,
                               'accepted_PER':label=='PER' and valid and (a,b)in accepted_keys, 'windows':sorted(windows)}
                    if label=='PER':
                        raw_per_count+=1
                        payload['mention_id']='per_'+digest(f"{doc['source_text_sha256']}:{a}:{b}")
                        if valid:
                            valid_per_count+=1
                            context=make_mention(doc,text,a,b,entity,args.context_chars)
                            for field in ('text','entity_start','entity_end','context_document_start','context_document_end','context_id'):
                                payload[field]=context[field]
                    predictions_file.write(json.dumps(payload,ensure_ascii=False)+'\n')
                for a,b,entity in accepted:
                    row = make_mention(doc,text,a,b,entity,args.context_chars)
                    row['inventory_origin']='full_coverage_pretrained_NER_automatic_filters'
                    mentions_file.write(json.dumps(row,ensure_ascii=False)+'\n'); count+=1
                mentions_file.flush(); predictions_file.flush()
                progress(stage='document_complete',documents=ordinal,candidates=count)
                print(f'Documents {ordinal}/{len(selected_docs)}; accepted mentions {count}; windows inferred {stats["ner_windows_processed"]}',flush=True)
        summary.update({'total_PER_mentions_complete':count if len(selected_docs)==len(documents) else None,
                        'NER_documents_processed':len(selected_docs),'accepted_mentions_this_run':count,
                        'inventory_complete':len(selected_docs)==len(documents),'ner_statistics':dict(stats),
                        'raw_PER_predictions_this_run':raw_per_count,'raw_valid_PER_predictions_this_run':valid_per_count,
                        'NER_elapsed_seconds_including_load':time.perf_counter()-ner_started})
    summary['dimension_scenarios_NOT_estimates'] = {str(n): {'annotation_rows_per_LLM': n, 'batches_at_100_per_batch': math.ceil(n/100),
                                                           'maximum_context_characters_approx': n*(2*args.context_chars+30)} for n in (10000,20000,40000)}
    assert all(hashlib.sha256(path.read_bytes()).hexdigest()==hashes[name] for name,path in inputs.items())
    write_jsonl(paths['documents.jsonl'],documents)
    if not args.run_ner:write_jsonl(paths['known_mentions_PARTIAL.jsonl'],recovered)
    if args.reuse_privacy_map:write_jsonl(paths['cached_span_review_PRIVATE.jsonl'],cache_log)
    task=annotation_task(args.taxonomy_config)
    for name,value in [('task.json',task),('manifest.json',{'version':VERSION,'inputs_sha256':hashes,'summary':summary,
                       'input_files':{name:{'path':str(path.resolve()),'sha256':hashes[name]}for name,path in inputs.items()},
                       'source_inventory':source_inventory,'source_files_skipped':audit.get('skipped_files',[]),
                       'ner_model':ner_metadata,'window_characters':6000,'window_overlap_characters':600,
                       'context_chars_each_side':args.context_chars,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       'extractor_sha256':hashlib.sha256((ROOT/'src/data/extract_role_candidates_v2.py').read_bytes()).hexdigest()})]:
        with paths[name].open('x',encoding='utf-8') as handle:json.dump(value,handle,ensure_ascii=False,indent=2)
    with args.report.open('x',encoding='utf-8') as handle:
        handle.write('# Experiência 19b — dimensão do corpus e inventário privado\n\n')
        handle.write(('Extração NER de cobertura integral por documento; sem LLM, transmissão, treino ou quotas por papel. A completude declarada refere-se ao processamento, não ao recall humano.\n\n' if args.run_ner else 'Planeamento local; sem LLM, transmissão, treino ou quotas por papel. O inventário conhecido é PARCIAL, não confundir com todas as menções.\n\n'))
        handle.write('```json\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n```\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
