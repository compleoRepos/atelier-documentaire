"""Modes de fonctionnement du RAG et calcul du mode effectif.

Le mode effectif est le minimum du mode global (configuration), du mode
maximal autorisé pour le tenant (``rag_tenant_settings``, DISABLED par défaut)
et des réductions de sécurité liées au moteur. Aucun tenant ne peut donc
dépasser le mode global.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.settings import RAG_MODES

MODES: tuple[str, ...] = RAG_MODES
_ORDER = {mode: index for index, mode in enumerate(MODES)}

# Seul le moteur privé construit un prompt à partir des canaux de contexte.
# - « interim » (fournisseur temporaire) est extérieur à l'environnement privé :
#   aucun contexte RAG ne lui est jamais envoyé ;
# - « offline » (mémoire + glossaire) ignore document_memory et country_context :
#   une injection serait sans effet, elle n'est donc pas faite.
# Dans ces deux cas le mode est plafonné à SHADOW (recherche observée seulement).
INJECTING_ENGINES = frozenset({"private"})
_ENGINE_REDUCTION = {"interim": "ENGINE_NOT_PRIVATE", "offline": "ENGINE_IGNORES_CONTEXT"}


def normalize_mode(value: object) -> str:
    mode = str(value or "").strip().upper()
    if mode not in _ORDER:
        raise ValueError("Mode RAG inconnu")
    return mode


def mode_rank(mode: str) -> int:
    return _ORDER[normalize_mode(mode)]


def lowest(*modes: str) -> str:
    return min((normalize_mode(mode) for mode in modes), key=_ORDER.__getitem__)


@dataclass(frozen=True)
class EffectiveMode:
    mode: str
    global_mode: str
    tenant_max_mode: str
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def injects(self) -> bool:
        return self.mode in {"ASSISTED", "ACTIVE"}

    @property
    def searches(self) -> bool:
        return self.mode != "DISABLED"


def effective_mode(global_mode: str, tenant_max_mode: str | None, engine: str) -> EffectiveMode:
    """Mode réellement appliqué pour un traitement, avec les motifs de réduction."""
    global_mode = normalize_mode(global_mode)
    tenant_mode = normalize_mode(tenant_max_mode or "DISABLED")
    mode = lowest(global_mode, tenant_mode)
    reasons: list[str] = []
    if mode_rank(tenant_mode) < mode_rank(global_mode):
        reasons.append("TENANT_MAX_MODE")
    if mode_rank(mode) > mode_rank("SHADOW") and engine not in INJECTING_ENGINES:
        mode = "SHADOW"
        reasons.append(_ENGINE_REDUCTION.get(str(engine), "ENGINE_NOT_PRIVATE"))
    return EffectiveMode(mode, global_mode, tenant_mode, tuple(reasons))


def token_budget(mode: str, settings: object) -> int:
    """Budget maximal de jetons RAG par requête (0 si le mode n'injecte rien)."""
    mode = normalize_mode(mode)
    if mode == "ASSISTED":
        return int(getattr(settings, "rag_assisted_max_tokens", 800))
    if mode == "ACTIVE":
        return int(getattr(settings, "rag_active_max_tokens", 1500))
    return 0
