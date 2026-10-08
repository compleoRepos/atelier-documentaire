"""Server-side synthetic-only authorisation. Never sends corpus data to a proxy."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]


def corpus_sha256(input_dir: Path | None = None) -> set[str]:
    """Local immutable input hash denylist, never embedded in code/Git/telemetry."""
    input_dir=input_dir or ROOT/'dataset/input'
    return {hashlib.sha256(path.read_bytes()).hexdigest() for path in input_dir.glob('*.pdf') if path.is_file()}


def synthetic_payload_sha256(ir: dict, options: dict | None = None) -> str:
    # A payload allowlist also prevents reusing an approved fixture file SHA with
    # a forged IR containing confidential OCR text, history or metadata.
    payload={key:value for key,value in ir.items() if key not in {'synthetic_fixture_authorized','synthetic_fixture_id','_translation_telemetry'}}
    options=options or {}
    context_fields=('memory','glossary','terms','protected_entities','document_context',
                    'document_memory','previous_decisions','previous','decisions','country_context','style','target_language')
    payload['outbound_context_options']={key:options[key] for key in context_fields if options.get(key)}
    encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def authorize_interim_fixture(ir: dict, options: dict) -> str | None:
    """Return an explicit issue code; caller must abort before tokenizer/network.

    Allowlisted hashes originate only from trusted server/env configuration, not
    from IR/document fields or user upload parameters. There is no public opt-in
    or 'send real documents' switch in this implementation.
    """
    source_sha=options.get('source_sha256') or ir.get('source_sha256') or ir.get('versions',{}).get('source_sha256')
    declared_sha=ir.get('versions',{}).get('source_sha256') or ir.get('source_sha256')
    denied=corpus_sha256(options.get('_corpus_input_dir'))
    if source_sha in denied or declared_sha in denied:
        return 'INTERIM_REAL_CORPUS_FORBIDDEN'
    if options.get('environment','local').lower() in {'prod','production','private'}:
        return 'INTERIM_FORBIDDEN_IN_PRIVATE_PRODUCTION'
    if ir.get('synthetic_fixture_authorized') is not True or options.get('interim_data_scope')!='synthetic_fixture':
        return 'INTERIM_SYNTHETIC_FIXTURE_REQUIRED'
    allowlist=options.get('interim_synthetic_payload_sha256_allowlist') or []
    if isinstance(allowlist,str):
        allowlist=[x.strip() for x in allowlist.split(',') if x.strip()]
    if synthetic_payload_sha256(ir,options) not in allowlist:
        return 'INTERIM_SYNTHETIC_PAYLOAD_NOT_ALLOWLISTED'
    if source_sha and declared_sha and source_sha!=declared_sha:
        return 'INTERIM_SYNTHETIC_SOURCE_HASH_MISMATCH'
    return None
