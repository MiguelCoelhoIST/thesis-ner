"""Read-only evidence for reserving protected references; never legal labels.

Formatting-only matches reserve EVERY matching document, not a guessed identity.
No match is not evidence of absence. Manual decisions are bound to a reference,
the complete document inventory and private, hash-verified supporting artifacts.
"""

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from src.annotation.prepare_role_annotation_batch import identity_roots
from src.data.extract_role_candidates_v2 import read_documents
from src.data.role_provenance import extract_process_provenance, filename_identifier_evidence, normalize_process_group_id

RAW_ROOT = Path(__file__).resolve().parents[2]/'data/raw'
NORMALIZATION_VERSION = '19c-formatting-v1'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def formatting_text(text):
    text = unicodedata.normalize('NFC', text).replace('\u00ad', '').replace('\u200b', '').replace('\ufeff', '')
    text = re.sub(r'(?<=\w)-[ \t]*\r?\n[ \t]*(?=\w)', '', text)
    text = text.translate(str.maketrans({'\u2018':"'", '\u2019':"'", '\u201c':'"', '\u201d':'"'}))
    return ' '.join(text.casefold().split())


def enough_context(text):
    return len(text.split()) >= 8 and sum(c.isalpha() for c in text) >= 40


def reference_index(documents, texts):
    roots = defaultdict(set)
    for doc in documents:
        for root in doc['potential_process_group_ids']:
            roots[root].add(doc['document_id'])
        for alias in doc.get('aliases', []):
            for root in identity_roots(alias):roots[root].add(doc['document_id'])
    return {'documents':documents, 'roots':roots,
            'literal':{key:' '.join(text.casefold().split()) for key,text in texts.items()},
            'formatted':{key:formatting_text(text) for key,text in texts.items()}}


def match_reference(ref, index):
    roots = identity_roots(ref)
    methods = defaultdict(set)
    for root in roots:
        for doc_id in index['roots'].get(root, set()):methods[doc_id].add('PROCESS_ROOT')
    passage = ' '.join(ref['text'].casefold().split())
    formatted = formatting_text(ref['text'])
    # A filename-style process spelling is ONLY accepted when it positively
    # matches an inventory identity root. Never infer absence from this variant.
    variants = set()
    if not roots and isinstance(ref.get('process_number'), str):
        variants = {normalize_process_group_id(item['decision_id'])
                    for item in filename_identifier_evidence(ref['process_number'])} - {None}
        if len(variants) != 1:variants = set()
    for doc in index['documents']:
        doc_id = doc['document_id']
        aliases = doc.get('aliases', [])
        if doc['source_text_sha256'] == ref.get('source_text_sha256'):methods[doc_id].add('SOURCE_SHA256')
        if any(ref.get('source_file') == a.get('source_file') and
               ref.get('source_document_id') == a.get('source_document_id')
               for a in aliases if ref.get('source_file') and ref.get('source_document_id')):
            methods[doc_id].add('SOURCE_PAIR')
        if len(passage.split()) >= 5 and passage in index['literal'][doc_id]:methods[doc_id].add('VERBATIM_CONTEXT')
        if ref.get('document_id') == doc_id:methods[doc_id].add('DOCUMENT_ID_HASH')
        if enough_context(formatted) and formatted in index['formatted'][doc_id]:
            methods[doc_id].add('FORMATTING_NORMALIZED_CONTEXT')
    for root in variants:
        for doc_id in index['roots'].get(root, set()):methods[doc_id].add('PROCESS_FORMAT_WITH_INVENTORY_ROOT')
    legacy = {'PROCESS_ROOT', 'SOURCE_SHA256', 'SOURCE_PAIR', 'VERBATIM_CONTEXT'}
    return {'roots':sorted(roots), 'methods':{key:sorted(value) for key,value in sorted(methods.items())},
            'legacy_matches':sorted(key for key,value in methods.items() if value & legacy),
            'normalization_version':NORMALIZATION_VERSION,
            'reference_fingerprint':fingerprint(ref), 'normalized_context_sha256':fingerprint(formatted)}


def validate_decision(decision, ref, documents, texts, match):
    """Return conservative reservations, or verify an external source.

    Reservation packets are explicit human provenance judgments, not machine
    proof of identity. Outside-corpus claims additionally require an actual local
    source with a matching excerpt, an unambiguous header and no inventory roots.
    """
    if (decision.get('human_confirmed') is not True or not isinstance(decision.get('reviewer'), str)
            or not decision['reviewer'].strip() or not isinstance(decision.get('reason'), str)
            or not decision['reason'].strip()):
        raise ValueError('protection_decision_needs_human_review_and_reason')
    if decision.get('reference_sha256') != fingerprint(ref) or decision.get('inventory_fingerprint') != fingerprint(documents):
        raise ValueError('stale_or_unbound_protection_decision')
    evidence = decision.get('evidence')
    if not isinstance(evidence, list) or not evidence:raise ValueError('missing_protection_evidence')
    verified = []
    for item in evidence:
        path = Path(item['path']).resolve(strict=True)
        if not path.is_relative_to(RAW_ROOT.resolve()) or not path.is_file():
            raise ValueError('evidence_must_be_private_local_file')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item.get('sha256'):raise ValueError('protection_evidence_hash_mismatch')
        verified.append((item, path))
    dgsi_identities = {}
    receipts = [(value,p) for value,p in verified if value.get('kind')=='dgsi_identity_receipt']
    if receipts:
        from src.annotation.dgsi_source_evidence import verify_receipt
        candidates = [json.loads(p.read_text(encoding='utf-8')) for _,p in receipts]
        artifacts = {(p,meta.get('kind'),meta['sha256']) for meta,p in verified}
        for item,path in verified:
            if item.get('kind')!='external_source':continue
            extracted=read_documents(path)
            entries=[entry for entry in extracted if entry[0]==item.get('source_document_id')]
            if not entries and len(extracted)==1 and item.get('source_document_id') is None:entries=extracted
            if len(entries)!=1:raise ValueError('external_source_document_ambiguous')
            linked=[r for r in candidates if r.get('source_sha256')==item['sha256']
                    and r.get('source_document_id') in (None,entries[0][0])]
            if len(linked)!=1:raise ValueError('dgsi_receipt_source_binding_ambiguous')
            dgsi_identities[path]=verify_receipt(linked[0],path,entries[0][1],ref,artifacts)
        if not dgsi_identities:raise ValueError('dgsi_receipt_without_copied_source')
    opaque={path:identity for path,identity in dgsi_identities.items()
            if identity.get('official_identifier_status')!='canonical'}
    if opaque:
        # Document confirmation never licenses an external-family assertion.
        if decision.get('excluded_from_corpus') is not False:
            raise ValueError('dgsi_document_identity_does_not_prove_external_family')
        from src.annotation.dgsi_source_evidence import family_guard
        guards=[];required=set(match['methods']);index=reference_index(documents,texts)
        for item,path in verified:
            if item.get('kind')!='external_source':continue
            extracted=read_documents(path)
            entries=[entry for entry in extracted if entry[0]==item.get('source_document_id')]
            if not entries and len(extracted)==1 and item.get('source_document_id') is None:entries=extracted
            if len(entries)!=1:raise ValueError('external_source_document_ambiguous')
            if path in opaque:
                guard=family_guard(opaque[path],documents,texts,ref,entries[0][1],path)
                guards.append(guard);required.update(guard['required_document_ids'])
            else:
                for root in identity_roots(dgsi_identities[path]):required.update(index['roots'].get(root,set()))
        targets=decision.get('document_ids')
        docs={d['document_id']:d for d in documents}
        if (not isinstance(targets,list) or len(set(targets))!=len(targets) or
                any(d not in docs for d in targets) or not required<=set(targets)):
            raise ValueError('dgsi_uncertain_family_envelope_not_fully_reserved')
        packets=[p for meta,p in verified if meta.get('kind')=='dgsi_family_reservation_packet']
        if not packets:raise ValueError('dgsi_bound_family_reservation_packet_required')
        guard_fingerprints=sorted(fingerprint(g) for g in guards)
        for path in packets:
            packet=json.loads(path.read_text(encoding='utf-8'))
            if (packet.get('reference_sha256')!=fingerprint(ref) or
                    packet.get('inventory_fingerprint')!=fingerprint(documents) or
                    packet.get('guard_fingerprints')!=guard_fingerprints or
                    sorted(packet.get('document_ids',[]))!=sorted(targets) or
                    packet.get('document_source_hashes')!={d:docs[d]['source_text_sha256'] for d in targets}):
                raise ValueError('dgsi_family_reservation_packet_not_bound')
        return set(targets), {'kind':'official_document_with_conservative_family_reservations',
                             'document_identity_status':'confirmed', 'family_identity_status':'unconfirmed',
                             'protection_status':'conservative_exclusion_coverage_verified',
                             'external_absence_claimed':False,'family_guards':guards,'evidence':evidence}
    if decision.get('excluded_from_corpus') is True:
        if match['methods'] or decision.get('document_ids'):
            raise ValueError('manual_exclusion_conflicts_with_detected_overlap')
        external = [(item,path) for item,path in verified if item.get('kind') == 'external_source']
        if not external:raise ValueError('external_judgment_evidence_required')
        index = reference_index(documents, texts)
        target = formatting_text(ref['text'])
        if not enough_context(target):raise ValueError('external_context_insufficient')
        for item,path in external:
            extracted = read_documents(path)
            entries = [entry for entry in extracted if entry[0] == item.get('source_document_id')]
            if not entries and len(extracted) == 1 and item.get('source_document_id') is None:entries = extracted
            if len(entries) != 1:raise ValueError('external_source_document_ambiguous')
            _,text,_ = entries[0]
            provenance = extract_process_provenance(text, path.name)
            if path in dgsi_identities:provenance = dgsi_identities[path]
            external_roots = identity_roots(provenance)
            if (provenance['process_provenance']['status'] not in ('header_only','header_filename_agree')
                    or not provenance['process_provenance']['header_evidence'] or len(external_roots) != 1
                    or (set(match['roots']) and not set(match['roots']) <= external_roots)):
                raise ValueError('external_source_identity_not_verified')
            if (target not in formatting_text(text) or
                    any(root in index['roots'] for root in external_roots) or
                    {provenance['source_text_sha256'],hashlib.sha256(text.encode('utf-8')).hexdigest()}
                    & {d['source_text_sha256'] for d in documents}):
                raise ValueError('external_source_not_disjoint_or_context_not_verified')
        return set(), {'kind':'verified_external_source', 'evidence':evidence}
    targets = decision.get('document_ids')
    docs = {doc['document_id']:doc for doc in documents}
    if not isinstance(targets, list) or not targets or any(d not in docs for d in targets):
        raise ValueError('invalid_protection_resolution_document')
    if dgsi_identities:
        index=reference_index(documents,texts)
        required=set(match['methods'])
        for identity in dgsi_identities.values():
            for root in identity_roots(identity):required.update(index['roots'].get(root,set()))
        if not required <= set(targets):raise ValueError('dgsi_known_overlaps_not_fully_reserved')
    packets = [path for item,path in verified if item.get('kind') == 'reservation_packet']
    if not packets:raise ValueError('private_reservation_packet_required')
    for path in packets:
        packet = json.loads(path.read_text(encoding='utf-8'))
        if (packet.get('reference_sha256') != fingerprint(ref) or
                sorted(packet.get('document_ids', [])) != sorted(targets) or
                packet.get('document_source_hashes') != {d:docs[d]['source_text_sha256'] for d in targets}):
            raise ValueError('reservation_packet_not_bound_to_documents')
    return set(targets), {'kind':'human_document_reservation', 'evidence':evidence}
