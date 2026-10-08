"""Server-side Interim authorisation.

Default: synthetic fixtures only. Real documents are refused unless the data
owner has issued an explicit, server-side, expiring authorisation listing the
exact source SHA-256 values (``owner_authorized_document`` scope). The
authorisation file is never part of Git, uploads or IR fields.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OWNER_SCOPE = "owner_authorized_document"
_OWNER_REQUIRED_FIELDS = ("authorization_id", "authorized_by", "decided_at", "expires_at", "decision",
                          "provider", "model", "document_sha256")


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


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def load_owner_authorization(path: str | Path | None) -> tuple[str | None, dict | None]:
    """Load and validate the owner authorisation record (fail-closed)."""
    if not path:
        return "INTERIM_OWNER_AUTHORIZATION_REQUIRED", None
    file = Path(path)
    if not file.is_file():
        return "INTERIM_OWNER_AUTHORIZATION_REQUIRED", None
    try:
        record = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "INTERIM_OWNER_AUTHORIZATION_INVALID", None
    if not isinstance(record, dict) or any(not record.get(key) for key in _OWNER_REQUIRED_FIELDS):
        return "INTERIM_OWNER_AUTHORIZATION_INVALID", None
    hashes = record["document_sha256"]
    if not isinstance(hashes, list) or not hashes or any(
        not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in hashes
    ):
        return "INTERIM_OWNER_AUTHORIZATION_INVALID", None
    if record["provider"] != "interim" or record["model"] != "gpt-5-mini":
        return "INTERIM_OWNER_AUTHORIZATION_PROVIDER_MISMATCH", None
    decided, expires = _parse_time(record["decided_at"]), _parse_time(record["expires_at"])
    now = datetime.now(UTC)
    if decided is None or expires is None or decided > now or expires <= decided:
        return "INTERIM_OWNER_AUTHORIZATION_INVALID", None
    if expires <= now:
        return "INTERIM_OWNER_AUTHORIZATION_EXPIRED", None
    return None, record


def authorize_interim_owner_document(ir: dict, options: dict) -> tuple[str | None, dict | None, str | None]:
    """Authorise one real document for Interim. Returns (issue_code, record, source_sha).

    Production/private environments stay forbidden whatever the authorisation.
    The SHA recorded at analysis must match the options SHA and be listed.
    """
    if options.get("environment", "local").lower() in {"prod", "production", "private"}:
        return "INTERIM_FORBIDDEN_IN_PRIVATE_PRODUCTION", None, None
    if options.get("interim_data_scope") != OWNER_SCOPE:
        return "INTERIM_OWNER_AUTHORIZATION_REQUIRED", None, None
    source_sha = options.get("source_sha256") or ir.get("versions", {}).get("source_sha256")
    declared_sha = ir.get("versions", {}).get("source_sha256") or ir.get("source_sha256")
    if not source_sha or not declared_sha or source_sha != declared_sha:
        return "INTERIM_OWNER_SOURCE_HASH_MISMATCH", None, None
    error, record = load_owner_authorization(options.get("interim_owner_authorization_file"))
    if error:
        return error, None, None
    if source_sha not in set(record["document_sha256"]):
        return "INTERIM_OWNER_DOCUMENT_NOT_AUTHORIZED", None, None
    return None, record, source_sha
