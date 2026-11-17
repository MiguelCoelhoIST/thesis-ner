"""Offline DGSI capture receipts: preserve display IDs, never guess S/5 edits.

Hashes verify integrity, not a remote server signature. A human confirms origin;
the frozen reference URL or saved-page origin must bind the official document.
"""

import hashlib
import re
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from src.data.role_provenance import extract_process_provenance, normalize_decision_id, normalize_process_group_id
from src.annotation.prepare_role_annotation_batch import identity_roots
from src.annotation.role_reference_provenance import fingerprint, formatting_text, enough_context, reference_index, match_reference

VERSION = 'dgsi-source-receipt-v2'
FAMILY_POLICY = 'literal_serial_all_years_courts_and_unverified_sources_v1'


def sha(data):return hashlib.sha256(data).hexdigest()


def official_document_key(url, *, allow_queryless=False):
    """Keep reviewer URLs strict; saved/reference decision URLs may omit query."""
    try:
        parsed = urlsplit(url)
        if (parsed.scheme.lower() not in ('http','https') or parsed.hostname not in ('dgsi.pt','www.dgsi.pt')
                or parsed.username or parsed.password or parsed.port is not None
                or not re.fullmatch(r'/jstj\.nsf/(?:(?:[0-9a-f]{32}|0|-)/)?[0-9a-f]{32}/?',parsed.path,re.I)
                or not ('opendocument' in parsed.query.lower().split('&')
                        or (allow_queryless and not parsed.query))):
            raise ValueError('dgsi_official_document_url_required')
        # The optional preceding GUID is a view, not the decision UNID.
        return 'dgsi.pt/jstj.nsf/'+parsed.path.rstrip('/').split('/')[-1].lower()
    except (TypeError,AttributeError,ValueError):
        raise ValueError('dgsi_official_document_url_required') from None


class VisibleHTML(HTMLParser):
    BLOCKS={'tr','td','th','p','div','br','li','table','h1','h2','h3','h4','h5','h6'}
    def __init__(self):
        super().__init__(convert_charrefs=True);self.hidden=0;self.parts=[];self.origins=[]
    def handle_starttag(self,tag,attrs):
        fields=dict(attrs)
        if tag=='meta' and (fields.get('property') or fields.get('name','')).lower()=='og:url':
            self.origins.append(fields.get('content',''))
        if tag=='link' and fields.get('rel','').lower()=='canonical':self.origins.append(fields.get('href',''))
        if tag in ('head','script','style','noscript'):self.hidden+=1
        if not self.hidden and tag in self.BLOCKS:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('head','script','style','noscript'):self.hidden=max(0,self.hidden-1)
        if not self.hidden and tag in self.BLOCKS:self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)
    def handle_comment(self,data):
        saved=re.search(r'saved from url=\(\d+\)(https?://\S+)',data,re.I)
        if saved:self.origins.append(saved[1])


def read_capture(path):
    raw=path.read_bytes();origins=[]
    if path.suffix.lower() in ('.mhtml','.mht'):
        message=BytesParser(policy=policy.default).parsebytes(raw)
        parts=[part for part in message.walk() if part.get_content_type()=='text/html']
        if len(parts)!=1:raise ValueError('dgsi_capture_html_part_ambiguous')
        charset=(parts[0].get_content_charset() or 'utf-8').lower()
        if charset not in ('utf-8','utf8','iso-8859-1','windows-1252','cp1252'):
            raise ValueError('dgsi_capture_charset_unsupported')
        text=parts[0].get_payload(decode=True).decode(charset)
        origins += [str(v) for v in (message.get('Snapshot-Content-Location'),message.get('Content-Location'),
                                      parts[0].get('Content-Location')) if v]
        html=True
    elif path.suffix.lower() in ('.html','.htm'):
        charset=re.search(br'charset\s*=\s*["\x27]?([A-Za-z0-9_-]+)',raw[:4096],re.I)
        encoding=charset[1].decode('ascii').lower() if charset else 'utf-8-sig'
        if encoding not in ('utf-8','utf-8-sig','iso-8859-1','windows-1252','cp1252'):
            raise ValueError('dgsi_capture_charset_unsupported')
        text=raw.decode(encoding);html=True
    elif path.suffix.lower() in ('.txt','.text'):
        text=raw.decode('utf-8-sig');html=False
    else:raise ValueError('dgsi_capture_format_unsupported')
    if html:
        parser=VisibleHTML();parser.feed(text)
        text=re.sub(r'\n(?:[^\S\r\n]*\n)+','\n',''.join(parser.parts));origins+=parser.origins
    return text,origins


def capture_identity(text,path):
    result=extract_process_provenance(text,path.name,header_chars=10000,header_lines=120)
    info=result['process_provenance']
    displayed={item['raw'] for item in info['display_header_evidence']}
    literal=next(iter(displayed)) if len(displayed)==1 else None
    canonical=normalize_decision_id(literal)
    if canonical is not None:
        if (info['status'] not in ('header_only','header_filename_agree') or info['unparsed_header_evidence']
                or result['decision_id_candidates']!=[canonical]):
            raise ValueError('dgsi_capture_identity_not_verified')
    else:
        # The official display value is documentary evidence, not a canonical
        # family root. Preserve filename candidates as unconfirmed evidence.
        result['unconfirmed_filename_identity_candidates']=result['decision_id_candidates']
        result.update(decision_id=None,decision_id_candidates=[],process_group_id=None,process_group_id_candidates=[])
    status='canonical' if canonical else 'noncanonical' if literal else 'missing' if not displayed else 'ambiguous'
    result.update(official_process_identifier=literal,official_process_identifiers=sorted(displayed),official_identifier_status=status,
                  family_identity_status='canonical_root_available' if canonical else 'unconfirmed')
    return result


def make_receipt(source_path,source_text,capture_path,url,reviewer,reason,refs,source_document_id=None):
    """Call only after explicit private human confirmation; no ID replacement."""
    official_document_key(url)
    capture_text,_=read_capture(capture_path)
    identity=capture_identity(capture_text,capture_path)
    copied=extract_process_provenance(source_text,source_path.name)
    return {'version':VERSION,'human_confirmed':True,'identity_discrepancy_reviewed':True,
            'reviewer':reviewer,'reason':reason,'official_url':url,
            'source_document_id':source_document_id,'source_path':str(source_path.resolve()),
            'source_sha256':sha(source_path.read_bytes()),'source_text_sha256':sha(source_text.encode('utf-8')),
            'capture_path':str(capture_path.resolve()),'capture_sha256':sha(capture_path.read_bytes()),
            'capture_text_sha256':sha(capture_text.encode('utf-8')),
            'verified_decision_id':identity['decision_id'],
            'official_document_key':official_document_key(url),
            'official_process_identifier':identity['official_process_identifier'],
            'official_process_identifiers':identity['official_process_identifiers'],
            'official_identifier_status':identity['official_identifier_status'],
            'family_identity_status':identity['family_identity_status'],
            'reference_fingerprints':[fingerprint(ref) for ref in refs],
            'copied_display_header_evidence':copied['process_provenance']['display_header_evidence'],
            'copied_unparsed_header_evidence':copied['process_provenance']['unparsed_header_evidence']}


def verify_receipt(receipt,source_path,source_text,ref,verified_artifacts):
    if (receipt.get('version') not in (VERSION,'dgsi-source-receipt-v1') or receipt.get('human_confirmed') is not True
            or receipt.get('identity_discrepancy_reviewed') is not True
            or not isinstance(receipt.get('reviewer'),str) or not receipt['reviewer'].strip()
            or not isinstance(receipt.get('reason'),str) or not receipt['reason'].strip()):
        raise ValueError('dgsi_human_confirmation_required')
    if (Path(receipt['source_path']).resolve()!=source_path.resolve()
            or receipt['source_sha256']!=sha(source_path.read_bytes())
            or receipt['source_text_sha256']!=sha(source_text.encode('utf-8'))
            or fingerprint(ref) not in receipt['reference_fingerprints']):
        raise ValueError('dgsi_receipt_source_or_reference_mismatch')
    capture_path=Path(receipt['capture_path']).resolve(strict=True)
    verified_artifacts={(Path(path).resolve(),kind,value) for path,kind,value in verified_artifacts}
    if (capture_path,'official_capture',receipt['capture_sha256']) not in verified_artifacts:
        raise ValueError('dgsi_capture_not_hash_verified_private_evidence')
    if receipt['capture_sha256']!=sha(capture_path.read_bytes()):raise ValueError('dgsi_capture_changed')
    text,origins=read_capture(capture_path)
    identity=capture_identity(text,capture_path)
    if (receipt['capture_text_sha256']!=sha(text.encode('utf-8')) or receipt['verified_decision_id']!=identity['decision_id']):
        raise ValueError('dgsi_capture_identity_receipt_mismatch')
    if receipt['version']==VERSION:
        if any(receipt.get(field)!=identity[field] for field in
               ('official_process_identifier','official_process_identifiers','official_identifier_status','family_identity_status')):
            raise ValueError('dgsi_capture_identity_receipt_mismatch')
    elif identity['official_identifier_status']!='canonical':
        raise ValueError('dgsi_v1_receipt_cannot_confirm_noncanonical_process')
    source_key=official_document_key(receipt['official_url'])
    if receipt['version']==VERSION and receipt.get('official_document_key')!=source_key:
        raise ValueError('dgsi_official_url_conflict')
    ref_key=None
    if ref.get('source_url'):
        ref_key=official_document_key(ref['source_url'],allow_queryless=True)
    origin_keys={official_document_key(url,allow_queryless=True) for url in origins}
    if (ref_key and ref_key!=source_key) or (origin_keys and origin_keys!={source_key}):
        raise ValueError('dgsi_official_url_conflict')
    if source_key not in origin_keys and ref_key!=source_key:
        raise ValueError('dgsi_capture_origin_not_bound')
    copied=extract_process_provenance(source_text,source_path.name)
    if ((identity['official_identifier_status']=='canonical' and
         any(value!=identity['decision_id'] for value in copied['decision_id_candidates'])) or
            receipt['copied_display_header_evidence']!=copied['process_provenance']['display_header_evidence'] or
            receipt['copied_unparsed_header_evidence']!=copied['process_provenance']['unparsed_header_evidence']):
        raise ValueError('dgsi_copied_identity_conflict_or_changed')
    target=formatting_text(ref['text'])
    if not enough_context(target):raise ValueError('dgsi_reference_context_insufficient')
    if target not in formatting_text(text) or target not in formatting_text(source_text):
        raise ValueError('dgsi_reference_context_not_in_both_sources')
    identity.update(document_identity_status='confirmed_official_document',official_document_key=source_key)
    return identity


def literal_serial(value):
    """Read only the unambiguous prefix; never interpret/correct year or court."""
    found=re.match(r'^(\d{1,7})/',value or '')
    return int(found[1]) if found else None


def family_guard(identity,documents,texts,ref,source_text,source_path):
    """A protective superset, not confirmation/absence of a legal case family.

    Under the existing base-process/alias grouping protocol, reserve every equal
    literal serial regardless of year/court, and EVERY source whose own header
    cannot corroborate the frozen inventory identity. Known links propagate in
    assess_protection. Unknowns are reserved, never deemed unrelated.
    """
    if identity.get('document_identity_status')!='confirmed_official_document':
        raise ValueError('dgsi_document_identity_not_confirmed')
    anchor=literal_serial(identity.get('official_process_identifier'))
    if anchor is None:raise ValueError('dgsi_unambiguous_base_serial_or_bound_family_evidence_required')
    serials={anchor}
    copied=extract_process_provenance(source_text,source_path.name)
    values=(list(identity_roots(ref))+copied['decision_id_candidates']+
            identity.get('unconfirmed_filename_identity_candidates',[]))
    values += [item['raw'] for item in copied['process_provenance']['display_header_evidence']]
    serials.update(n for n in (literal_serial(v) for v in values) if n is not None)
    required=set(match_reference(ref,reference_index(documents,texts))['methods'])
    evidence=[];unid=identity['official_document_key'].split('/')[-1]
    for doc in documents:
        doc_id=doc['document_id'];text=texts[doc_id]
        if sha(text.encode('utf-8'))!=doc['source_text_sha256']:
            raise ValueError('dgsi_corpus_source_fingerprint_mismatch')
        own=extract_process_provenance(text,doc['canonical_source']['source_file'])
        own_roots={normalize_process_group_id(item['decision_id']) for item in own['process_provenance']['header_evidence']}
        known=set(doc.get('potential_process_group_ids',[]))
        alias_roots=set().union(*(identity_roots(alias) for alias in doc.get('aliases',[])))
        known.update(alias_roots)
        reliable=(doc.get('requires_identity_review') is False and len(known)==1 and own_roots==known
                  and not own['process_provenance']['unparsed_header_evidence']
                  and own['process_provenance']['status'] in ('header_only','header_filename_agree')
                  and not any(a.get('process_provenance',{}).get('status') in ('conflict','unresolved') for a in doc.get('aliases',[])))
        codes=[]
        if not reliable:codes.append('UNVERIFIED_SOURCE_IDENTITY_RESERVED')
        if any(literal_serial(root) in serials for root in known|own_roots):codes.append('SAME_LITERAL_SERIAL_ANY_YEAR_COURT_RESERVED')
        # Positive references in the body can expose related decisions even
        # when the document's own header has a different canonical root.
        if any(int(m[1]) in serials for m in re.finditer(r'(?<!\d)(\d{1,7})\s*/',text)):
            codes.append('LITERAL_SERIAL_MENTION_RESERVED')
        if unid in text.casefold():codes.append('OFFICIAL_DOCUMENT_UNID_MENTION_RESERVED')
        if codes:required.add(doc_id)
        evidence.append({'document_id':doc_id,'source_text_sha256':doc['source_text_sha256'],
                         'source_identity_corroborated':reliable,'reservation_codes':codes})
    return {'policy':FAMILY_POLICY,'family_identity_status':'unconfirmed','protection_scope':'exploratory_exclusion_only',
            'inventory_fingerprint':fingerprint(documents),'official_document_key':identity['official_document_key'],
            'literal_serials_reserved':sorted(serials),'coverage':evidence,'required_document_ids':sorted(required),
            'external_absence_claimed':False,'training_eligibility':'NOT_ESTABLISHED'}
