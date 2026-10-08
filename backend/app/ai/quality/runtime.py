"""Providers explicitement configurés par l'opérateur, jamais depuis le document."""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=4)
def _embedding(path: str, version: str, device: str):
    from .providers import LocalEmbeddingProvider

    return LocalEmbeddingProvider(path, model_version=version, device=device)


def quality_options(settings, ir: dict) -> dict:
    options = {
        "quality_thresholds": settings.quality_thresholds,
        "max_context": settings.max_context,
        "source_sha256": ir.get("source_sha256"),
        "review_version": ir.get("review_version"),
    }
    if settings.quality_embedding_model_dir:
        if not settings.quality_embedding_model_version:
            raise ValueError("QUALITY_EMBEDDING_VERSION_REQUIRED")
        options["embedding_provider"] = _embedding(
            str(settings.quality_embedding_model_dir),
            settings.quality_embedding_model_version,
            settings.quality_embedding_device,
        )
    if settings.quality_private_judge_enabled:
        if (
            not settings.private_ai_base_url
            or not settings.private_ai_model
            or not settings.tokenizer_path
        ):
            raise ValueError("PRIVATE_JUDGE_CONFIGURATION_REQUIRED")
        from .providers import PrivateQwenJudgeProvider

        options["private_judge"] = PrivateQwenJudgeProvider(
            base_url=settings.private_ai_base_url,
            allowed_hosts=settings.private_hosts,
            model=settings.private_ai_model,
            tokenizer_path=settings.tokenizer_path,
            api_key=settings.private_ai_api_key,
            max_context=settings.max_context,
            safety_margin=settings.safety_margin,
            max_output=min(settings.max_output, 2048),
        )
    return options
