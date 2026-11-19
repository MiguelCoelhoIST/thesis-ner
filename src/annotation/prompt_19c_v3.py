"""Offline v3 message construction; no change to historical runners or parser."""

import json
from pathlib import Path

from src.annotation import annotate_stj_silver_19c as core

VERSION = '19c-v3-legal-roles'
POLICY_VERSION = '19c-legal-role-policy-v1'
PROMPT_PATH = Path(__file__).resolve().parents[2] / 'config/prompts/role_annotation_19c_v3_legal_roles.txt'
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding='utf-8')


def build_messages(record):
    original = core.build_messages(record)  # Exact offsets, no labels/markers already stored.
    return [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': 'Target mention (verbatim JSON string): '
         + json.dumps(record['entity'], ensure_ascii=False)
         + '\nMarked context:\n' + original[1]['content']},
    ]


def configuration():
    return {'prompt_version': VERSION, 'policy_version': POLICY_VERSION,
            'prompt_sha256': core.file_hash(PROMPT_PATH),
            'message_builder_sha256': core.file_hash(Path(__file__)),
            'parser_sha256': core.file_hash(Path(core.__file__)),
            'taxonomy_sha256': core.file_hash(core.TAXONOMY),
            'human_validated': False, 'external_transmission_authorized': False}
