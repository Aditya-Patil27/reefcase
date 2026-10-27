"""pydantic-ai models for each LLM role, built purely from ``Settings`` (§5.2).

Muse Spark Open on Baseten has no JSON mode or structured output (§9.7), so
callers must keep pydantic-ai's default tool-call output; ``NativeOutput`` is
forbidden. Reasoning effort is pinned per role because the provider defaults to
``xhigh``, which would break the latency budget (NFR1).
"""

from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from reefcase.core.config import LLMRole, LLMRoleConfig, Settings
from reefcase.core.errors import ConfigError

__all__ = ["build_model"]


def build_model(role: LLMRole, settings: Settings) -> OpenAIChatModel | None:
    """OpenAI-compatible model for ``role``, or ``None`` when ``student`` is unset.

    ``agent`` and ``teacher`` are mandatory, so an unconfigured one raises
    ``ConfigError`` instead of passing ``None`` into an ``Agent`` later.
    """
    cfg = settings.llm_role(role)
    if cfg is None:
        if role == "student":
            return None
        raise ConfigError(f"REEFCASE_LLM_{role.upper()}_* is not configured")

    provider = OpenAIProvider(base_url=cfg.base_url, api_key=cfg.api_key)
    return OpenAIChatModel(cfg.model, provider=provider, settings=_model_settings(cfg))


def _model_settings(cfg: LLMRoleConfig) -> OpenAIChatModelSettings | None:
    if cfg.reasoning_effort is None:
        return None
    return OpenAIChatModelSettings(openai_reasoning_effort=cfg.reasoning_effort)
