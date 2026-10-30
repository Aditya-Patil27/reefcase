"""Process settings, read only from ``REEFCASE_*`` environment variables (§4.4).

One flat field per variable, so ``env_prefix="REEFCASE_"`` maps
``llm_agent_base_url`` to ``REEFCASE_LLM_AGENT_BASE_URL`` with no nesting and no
aliases. Secrets stay in ``SecretStr`` and are only unwrapped by the LLM factory.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from reefcase.core.errors import ConfigError

__all__ = [
    "DEFAULT_AGENT_REASONING_EFFORT",
    "DEFAULT_DATA_DIR",
    "DEFAULT_KEEP_FRAMES",
    "DEFAULT_MIN_FRAMES",
    "DEFAULT_SAM_MODEL_ID",
    "DEFAULT_TEACHER_REASONING_EFFORT",
    "LLMRole",
    "LLMRoleConfig",
    "ReasoningEffort",
    "SegmenterName",
    "Settings",
]

LLMRole = Literal["agent", "teacher", "student"]
ReasoningEffort = Literal["low", "medium", "high", "xhigh"]
SegmenterName = Literal["fake", "sam3_local", "sam3_modal", "student"]

DEFAULT_DATA_DIR = Path("var")
DEFAULT_SAM_MODEL_ID = "facebook/sam3"
DEFAULT_AGENT_REASONING_EFFORT: ReasoningEffort = "medium"
DEFAULT_TEACHER_REASONING_EFFORT: ReasoningEffort = "low"
DEFAULT_KEEP_FRAMES = 24
DEFAULT_MIN_FRAMES = 6

#: The three variables every LLM role is configured with, in error-message order.
_ROLE_VARIABLES = ("BASE_URL", "API_KEY", "MODEL")


@dataclass(frozen=True, slots=True)
class LLMRoleConfig:
    """One configured OpenAI-compatible endpoint.

    ``api_key`` is already unwrapped from ``SecretStr``; ``reasoning_effort`` is
    ``None`` for ``student``, which has no effort variable in §4.4.
    """

    base_url: str
    api_key: str
    model: str
    reasoning_effort: ReasoningEffort | None


class Settings(BaseSettings):
    """Every ``REEFCASE_*`` variable in ``.env.example``, in one place.

    ``env_ignore_empty`` makes ``REEFCASE_X=`` in a copied ``.env`` mean "unset",
    and ``extra="ignore"`` lets a stale key survive a start-up.
    """

    model_config = SettingsConfigDict(
        env_prefix="REEFCASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    data_dir: Path = DEFAULT_DATA_DIR
    web_dist: Path | None = None
    segmenter: SegmenterName = "fake"
    sam_model_id: str = DEFAULT_SAM_MODEL_ID
    sam_modal_url: str | None = None
    sam_modal_token: SecretStr | None = None
    student_weights: Path | None = None

    llm_agent_base_url: str | None = None
    llm_agent_api_key: SecretStr | None = None
    llm_agent_model: str | None = None
    llm_teacher_base_url: str | None = None
    llm_teacher_api_key: SecretStr | None = None
    llm_teacher_model: str | None = None
    llm_student_base_url: str | None = None
    llm_student_api_key: SecretStr | None = None
    llm_student_model: str | None = None

    llm_agent_reasoning_effort: ReasoningEffort = DEFAULT_AGENT_REASONING_EFFORT
    llm_teacher_reasoning_effort: ReasoningEffort = DEFAULT_TEACHER_REASONING_EFFORT

    gfw_token: SecretStr | None = None
    telegram_token: SecretStr | None = None

    keep_frames: int = Field(default=DEFAULT_KEEP_FRAMES, ge=1)
    min_frames: int = Field(default=DEFAULT_MIN_FRAMES, ge=1)

    def llm_role(self, role: LLMRole) -> LLMRoleConfig | None:
        """Configured endpoint for ``role``: ``None`` when the role is unconfigured.

        Raises ``ConfigError`` when the role is *partly* configured, naming the
        missing ``REEFCASE_LLM_<ROLE>_*`` variables and never echoing values.
        """
        base_url, api_key, model = self._role_values(role)
        if base_url is not None and api_key is not None and model is not None:
            return LLMRoleConfig(
                base_url=base_url,
                api_key=api_key.get_secret_value(),
                model=model,
                reasoning_effort=self._reasoning_effort(role),
            )
        if base_url is None and api_key is None and model is None:
            return None

        prefix = f"REEFCASE_LLM_{role.upper()}"
        missing = ", ".join(
            f"{prefix}_{name}"
            for name, value in zip(_ROLE_VARIABLES, (base_url, api_key, model), strict=True)
            if value is None
        )
        raise ConfigError(f"{prefix}_* is partly configured; missing {missing}")

    def _role_values(self, role: LLMRole) -> tuple[str | None, SecretStr | None, str | None]:
        if role == "agent":
            return self.llm_agent_base_url, self.llm_agent_api_key, self.llm_agent_model
        if role == "teacher":
            return self.llm_teacher_base_url, self.llm_teacher_api_key, self.llm_teacher_model
        return self.llm_student_base_url, self.llm_student_api_key, self.llm_student_model

    def _reasoning_effort(self, role: LLMRole) -> ReasoningEffort | None:
        if role == "agent":
            return self.llm_agent_reasoning_effort
        if role == "teacher":
            return self.llm_teacher_reasoning_effort
        return None
