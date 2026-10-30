"""Schémas d'entrée des routes RAG (validation stricte, champs inconnus refusés)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Mode = Literal["DISABLED", "SHADOW", "ASSISTED", "ACTIVE"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)


class SearchRequest(_Strict):
    text: str = Field(min_length=1, max_length=2000)
    source_language: str = Field(min_length=2, max_length=12)
    target_language: str = Field(default="fr", min_length=2, max_length=12)
    domain: str | None = Field(default=None, max_length=40)
    limit: int = Field(default=10, ge=1, le=50)


class DocumentContextRequest(_Strict):
    source_language: str | None = Field(default=None, max_length=12)
    target_language: str | None = Field(default=None, max_length=12)
    source_country: str | None = Field(default=None, min_length=2, max_length=2)
    target_country: str | None = Field(default=None, min_length=2, max_length=2)
    jurisdiction: str | None = Field(default=None, max_length=80)
    document_date: date | None = None
    legal_reference_date: date | None = None


class ReferentialRequest(_Strict):
    kind: Literal["linguistic", "business", "regulatory"]
    name: str = Field(min_length=1, max_length=200)
    domain: str | None = Field(default=None, max_length=40)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    jurisdiction: str | None = Field(default=None, max_length=80)
    languages: list[str] = Field(default_factory=list, max_length=20)


class ActiveRequest(_Strict):
    active: bool


class DraftRequest(_Strict):
    copy_from: str | None = Field(default=None, max_length=36)


class EntryRequest(_Strict):
    source_language: str = Field(min_length=2, max_length=12)
    source_term: str = Field(min_length=1, max_length=500)
    target_language: str = Field(min_length=2, max_length=12)
    target_term: str = Field(min_length=1, max_length=500)
    synonyms: list[str] | None = Field(default=None, max_length=50)
    regional_variants: list[str] | None = Field(default=None, max_length=50)
    definition: str | None = Field(default=None, max_length=4000)
    usage_context: str | None = Field(default=None, max_length=4000)
    # « register » masquerait un attribut de BaseModel : alias JSON conservé.
    usage_register: str | None = Field(default=None, max_length=40, alias="register")
    domain: str | None = Field(default=None, max_length=40)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    jurisdiction: str | None = Field(default=None, max_length=80)
    provenance: str | None = Field(default=None, max_length=200)


class EntriesRequest(_Strict):
    entries: list[EntryRequest] = Field(min_length=1, max_length=500)


class TransitionRequest(_Strict):
    action: Literal["submit", "reject", "validate", "publish", "retire", "restore"]
    comment: str | None = Field(default=None, max_length=500)


class RoleRequest(_Strict):
    user_id: str = Field(min_length=1, max_length=36)
    role: Literal["rag_admin", "terminology_manager", "legal_manager", "reader"]
    grant: bool = True


class TenantModeRequest(_Strict):
    max_mode: Mode
