"""Configuration fail-closed, explicite et validée avant démarrage."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[3]


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
    interim_data_scope: Literal["synthetic_fixture"] = "synthetic_fixture"
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
    ocr_backend: Literal["tesseract", "paddle"] = "tesseract"
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

    @field_validator("paddle_model_dir", "quality_embedding_model_dir", mode="before")
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
        if self.environment.lower() == "private" and self.engine == "interim":
            raise ValueError("Environnement privé : provider Interim temporaire interdit")
        if self.job_hard_timeout_seconds <= self.job_soft_timeout_seconds:
            raise ValueError("Le timeout dur doit dépasser le timeout souple")
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
        return self

    @property
    def origins(self):
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

    @property
    def private_hosts(self):
        return [x.strip().lower() for x in self.private_ai_allowed_hosts.split(",") if x.strip()]

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
