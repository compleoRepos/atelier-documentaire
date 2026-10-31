"""Configuration fail-closed, explicite et validée avant démarrage."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[3]
# DICE (RAG) : modes ordonnés du plus restrictif au plus permissif.
RAG_MODES = ("DISABLED", "SHADOW", "ASSISTED", "ACTIVE")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRANSLATOR_", env_file=".env", extra="ignore")
    app_name: str = "Atelier documentaire"
    environment: str = "local"
    database_url: str = f"sqlite:///{(_ROOT / 'runtime' / 'translator.db').as_posix()}"
    data_dir: Path = _ROOT / "runtime"
    auto_create_schema: bool = True
    jwt_secret: str | None = None
    jwt_issuer: str = "ai-document-translator"
    jwt_audience: str = "atelier-documentaire"
    jwt_expire_minutes: int = Field(default=60, ge=1, le=1440)
    auth_mode: Literal["bearer", "hybrid", "cookie"] = "hybrid"
    cookie_secure: bool = False
    session_cookie: str = "translator_session"
    csrf_cookie: str = "translator_csrf"
    storage_backend: Literal["local", "s3"] = "local"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_prefix: str = "documents"
    execution_mode: Literal["inline", "background", "celery"] = "inline"
    celery_broker_url: str = "redis://localhost:6379/0"
    job_soft_timeout_seconds: int = Field(default=1800, ge=1)
    job_hard_timeout_seconds: int = Field(default=1860, ge=2)
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1)
    max_pages: int = Field(default=200, ge=1, le=10000)
    allowed_origins: str = ""
    frontend_dir: Path | None = None
    report_dir: Path | None = None
    expected_dir: Path = _ROOT / "dataset" / "expected"
    engine: Literal["offline", "private", "interim"] = "offline"
    interim_model: Literal["gpt-5-mini"] = "gpt-5-mini"
    interim_api_base: str | None = Field(default=None, repr=False, exclude=True)
    interim_api_key: str | None = Field(default=None, repr=False, exclude=True)
    interim_data_scope: Literal["synthetic_fixture", "owner_authorized_document"] = "synthetic_fixture"
    # Server-side owner authorisation (outside Git): listed source SHA-256,
    # author, decision time and expiry. Required for owner_authorized_document.
    interim_owner_authorization_file: Path | None = None
    interim_synthetic_payload_sha256_allowlist: str = ""
    interim_total_generation_cap_verified: bool = True
    interim_capability_proof: str | None = None
    private_ai_base_url: str | None = None
    private_ai_allowed_hosts: str = ""
    private_ai_model: str | None = None
    private_ai_api_key: str | None = None
    private_ai_model_version: str | None = None
    tokenizer_path: str | None = None
    max_context: int = Field(default=32768, ge=1, le=32768)
    target_input: int = Field(default=22000, ge=1)
    max_output: int = Field(default=8000, ge=1)
    safety_margin: int = Field(default=2768, ge=1)
    # OCR : Surya par défaut (service local services/ocr-surya). Tesseract ne
    # sert plus que sur sélection explicite (référence historique des tests de
    # non-régression) ; aucun repli automatique d'un moteur vers l'autre.
    ocr_backend: Literal["surya", "tesseract", "paddle"] = "surya"
    surya_ocr_url: str | None = None
    surya_ocr_allowed_hosts: str = "127.0.0.1,localhost,::1"
    surya_ocr_token: str | None = None
    surya_ocr_timeout_seconds: float = Field(default=900, ge=10, le=3600)
    # Les poids Surya sont sous licence OpenRAIL-M modifiée (seuil de chiffre
    # d'affaires/financement) : l'exploitant doit attester son éligibilité.
    surya_weights_license_acknowledged: bool = False
    image_preprocessing_profile: Literal["auto", "clean_scan", "noisy_scan", "old_document", "mobile_photo", "complex_document"] = "auto"
    paddle_model_dir: Path | None = None
    soffice_path: str = "/usr/bin/soffice"
    quality_embedding_model_dir: Path | None = None
    quality_embedding_model_version: str | None = None
    quality_embedding_device: str = "cpu"
    quality_private_judge_enabled: bool = False
    quality_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "ocr_score": 0.95,
            "translation_score": 0.90,
            "semantic_score": 0.95,
            "layout_score": 0.90,
            "visual_score": 0.90,
        }
    )
    av_scan_enabled: bool = False
    av_host: str = "clamav"
    av_port: int = Field(default=3310, ge=1, le=65535)
    av_timeout_seconds: float = Field(default=30, ge=1, le=120)
    metrics_enabled: bool = True
    metrics_token: str | None = None
    # DICE (RAG) — désactivé par défaut. En DISABLED aucun module app.rag n'est
    # importé et les options de traduction ne sont pas modifiées.
    rag_mode: Literal["DISABLED", "SHADOW", "ASSISTED", "ACTIVE"] = "DISABLED"
    rag_admin_enabled: bool = False
    rag_assisted_max_tokens: int = Field(default=800, ge=1, le=4000)
    rag_active_max_tokens: int = Field(default=1500, ge=1, le=4000)
    rag_max_entries: int = Field(default=16, ge=1, le=16)
    rag_shadow_task_expires_seconds: int = Field(default=3600, ge=60, le=86400)
    # Publication SHADOW hors du chemin critique (thread éditeur, file bornée) :
    # délai court vers le courtier, disjoncteur, et stratégie si le courtier est
    # indisponible (« drop » : observation perdue et comptée ; « local » : recherche
    # exécutée dans le thread local borné du processus).
    rag_shadow_broker_timeout_seconds: float = Field(default=2.0, ge=0.1, le=30.0)
    rag_shadow_breaker_seconds: int = Field(default=60, ge=1, le=3600)
    rag_shadow_queue_max: int = Field(default=64, ge=1, le=10000)
    rag_shadow_on_broker_failure: Literal["drop", "local"] = "drop"
    # LOT 2 : import CSV/XLSX de référentiels (tout ou rien, dans un brouillon).
    rag_import_max_bytes: int = Field(default=5_000_000, ge=1024, le=50_000_000)
    rag_import_max_rows: int = Field(default=5000, ge=1, le=100_000)

    @field_validator("rag_mode", mode="before")
    @classmethod
    def normalize_rag_mode(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator(
        "paddle_model_dir", "quality_embedding_model_dir", "interim_owner_authorization_file", mode="before"
    )
    @classmethod
    def empty_optional_path(cls, value):
        return None if value is None or (isinstance(value, str) and not value.strip()) else value

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, value):
        if value is not None and len(value) < 32:
            raise ValueError("TRANSLATOR_JWT_SECRET doit contenir au moins 32 caractères")
        return value

    @field_validator("quality_thresholds", mode="before")
    @classmethod
    def validate_thresholds(cls, value):
        if not isinstance(value, dict) or not value:
            raise ValueError("Seuils de qualité requis")
        for key, score in value.items():
            if key not in {
                "ocr_score",
                "translation_score",
                "semantic_score",
                "layout_score",
                "visual_score",
            }:
                raise ValueError("Métrique inconnue")
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not 0 <= score <= 1
            ):
                raise ValueError("Seuil invalide : nombre fini entre 0 et 1")
        return value

    @model_validator(mode="after")
    def configuration_contract(self):
        if self.target_input + self.max_output + self.safety_margin > self.max_context:
            raise ValueError("Budget entrée/sortie/marge supérieur au contexte maximal")
        self._rag_contract()
        if self.environment.lower() == "private" and self.engine == "interim":
            raise ValueError("Environnement privé : provider Interim temporaire interdit")
        if self.interim_data_scope == "owner_authorized_document" and not self.interim_owner_authorization_file:
            raise ValueError("Périmètre Interim propriétaire : fichier d'autorisation serveur requis")
        if self.job_hard_timeout_seconds <= self.job_soft_timeout_seconds:
            raise ValueError("Le timeout dur doit dépasser le timeout souple")
        if self.ocr_backend == "surya" and self.surya_ocr_url:
            self._surya_contract()
        if self.environment.lower() in {"prod", "production"}:
            if (
                self.engine != "private"
                or self.storage_backend != "s3"
                or self.execution_mode != "celery"
            ):
                raise ValueError("Production : IA privée, stockage S3 et queue Celery requis")
            if not self.database_url.startswith("postgresql") or self.auto_create_schema:
                raise ValueError("Production : PostgreSQL migré requis, create_all interdit")
            if (
                not self.jwt_secret
                or len(self.jwt_secret) < 64
                or self.auth_mode != "cookie"
                or not self.cookie_secure
            ):
                raise ValueError(
                    "Production : secret JWT >=64 et cookies sécurisés HttpOnly requis"
                )
            if not self.av_scan_enabled or not self.metrics_token:
                raise ValueError(
                    "Production : antivirus fail-closed et accès métriques protégé requis"
                )
            for url in (self.private_ai_base_url, self.s3_endpoint_url):
                if not url or urlparse(url).scheme != "https":
                    raise ValueError("Production : endpoints privés HTTPS requis")
            if (
                not self.private_ai_model
                or not self.private_ai_model_version
                or not self.tokenizer_path
                or not self.private_hosts
            ):
                raise ValueError(
                    "Production : modèle/version/tokenizer/allowlist explicites requis"
                )
            if "*" in self.origins or any(not x.startswith("https://") for x in self.origins):
                raise ValueError("Production : origines HTTPS explicites uniquement")
            if self.ocr_backend == "surya":
                if not self.surya_ocr_url:
                    raise ValueError(
                        "Production : TRANSLATOR_SURYA_OCR_URL requis pour l'OCR Surya"
                    )
                if not self.surya_weights_license_acknowledged:
                    raise ValueError(
                        "Production : éligibilité à la licence des poids Surya non attestée "
                        "(TRANSLATOR_SURYA_WEIGHTS_LICENSE_ACKNOWLEDGED)"
                    )
        return self

    def _surya_contract(self) -> None:
        """URL OCR : hôte explicitement autorisé ; HTTP clair seulement en boucle locale."""
        parsed = urlparse(self.surya_ocr_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not host or host not in self.surya_hosts:
            raise ValueError(
                "TRANSLATOR_SURYA_OCR_URL : hôte absent de TRANSLATOR_SURYA_OCR_ALLOWED_HOSTS"
            )
        if parsed.username or parsed.password:
            raise ValueError("TRANSLATOR_SURYA_OCR_URL : identifiants interdits dans l'URL")
        if parsed.scheme == "http" and self.environment.lower() in {"prod", "production"}:
            if host not in {"127.0.0.1", "localhost", "::1"}:
                raise ValueError("Production : OCR Surya en HTTPS requis hors boucle locale")

    def _rag_contract(self) -> None:
        """Refuse une configuration RAG incohérente ou une variable RAG inconnue."""
        if max(self.rag_assisted_max_tokens, self.rag_active_max_tokens) >= self.target_input:
            raise ValueError("Budget RAG supérieur ou égal au budget d'entrée")
        known = {f"TRANSLATOR_{name.upper()}" for name in type(self).model_fields if name.startswith("rag_")}
        declared = {key.upper() for key in os.environ}
        env_file = self.model_config.get("env_file")
        if isinstance(env_file, str) and Path(env_file).is_file():
            from dotenv import dotenv_values

            declared |= {key.upper() for key in dotenv_values(env_file)}
        unknown = sorted(k for k in declared if k.startswith("TRANSLATOR_RAG_") and k not in known)
        if unknown:
            raise ValueError("Variable RAG inconnue (jamais ignorée) : " + ", ".join(unknown))

    @property
    def origins(self):
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

    @property
    def private_hosts(self):
        return [x.strip().lower() for x in self.private_ai_allowed_hosts.split(",") if x.strip()]

    @property
    def surya_hosts(self):
        return [x.strip().lower() for x in self.surya_ocr_allowed_hosts.split(",") if x.strip()]

    @property
    def translation_budgets(self):
        return {
            k: getattr(self, k)
            for k in ("max_context", "target_input", "max_output", "safety_margin")
        }

    def ensure_directories(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.report_dir:
            self.report_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def require_jwt_secret(settings: Settings | None = None) -> str:
    secret = (settings or get_settings()).jwt_secret
    if not secret:
        raise RuntimeError("Configuration invalide : TRANSLATOR_JWT_SECRET est requis")
    return secret
