"""Contract tests for ``reefcase.core.config`` (architecture §4.4, §5.2, §9.7).

Every ``REEFCASE_*`` variable in ``.env.example`` feeds exactly one flat
``Settings`` field, secrets stay masked, and a *partly* configured LLM role is a
``ConfigError`` that names variables without echoing values.
"""

import os
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from reefcase.core.config import (
    DEFAULT_AGENT_REASONING_EFFORT,
    DEFAULT_DATA_DIR,
    DEFAULT_KEEP_FRAMES,
    DEFAULT_MIN_FRAMES,
    DEFAULT_SAM_MODEL_ID,
    DEFAULT_TEACHER_REASONING_EFFORT,
    LLMRole,
    LLMRoleConfig,
    Settings,
)
from reefcase.core.errors import ConfigError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never inherit a developer's shell or a real ``.env`` (AGENTS: never read it)."""
    for key in [k for k in os.environ if k.startswith("REEFCASE_")]:
        monkeypatch.delenv(key, raising=False)


def make_settings() -> Settings:
    """Settings built from the (cleaned) process env only, never from ``.env``.

    ``_env_file`` is a runtime-only pydantic-settings kwarg: pyright's pydantic
    plugin synthesises ``__init__`` from the fields, so it reports the kwarg as
    unknown (story 1.3 allows exactly this ignore).
    """
    return Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


# ``.env.example`` order, each row with a sample value and the value it must produce.
ENV_TABLE: list[tuple[str, str, object]] = [
    ("REEFCASE_DATA_DIR", "var/data", Path("var/data")),
    ("REEFCASE_SEGMENTER", "sam3_modal", "sam3_modal"),
    ("REEFCASE_SAM_MODEL_ID", "facebook/sam3.1", "facebook/sam3.1"),
    ("REEFCASE_SAM_MODAL_URL", "https://modal.example/sam", "https://modal.example/sam"),
    ("REEFCASE_STUDENT_WEIGHTS", "var/student.pt", Path("var/student.pt")),
    ("REEFCASE_LLM_AGENT_BASE_URL", "https://agent.example/v1", "https://agent.example/v1"),
    ("REEFCASE_LLM_AGENT_API_KEY", "sk-agent", "sk-agent"),
    ("REEFCASE_LLM_AGENT_MODEL", "agent-model", "agent-model"),
    ("REEFCASE_LLM_TEACHER_BASE_URL", "https://teacher.example/v1", "https://teacher.example/v1"),
    ("REEFCASE_LLM_TEACHER_API_KEY", "sk-teacher", "sk-teacher"),
    ("REEFCASE_LLM_TEACHER_MODEL", "teacher-model", "teacher-model"),
    ("REEFCASE_LLM_STUDENT_BASE_URL", "https://student.example/v1", "https://student.example/v1"),
    ("REEFCASE_LLM_STUDENT_API_KEY", "sk-student", "sk-student"),
    ("REEFCASE_LLM_STUDENT_MODEL", "student-model", "student-model"),
    ("REEFCASE_LLM_AGENT_REASONING_EFFORT", "high", "high"),
    ("REEFCASE_LLM_TEACHER_REASONING_EFFORT", "xhigh", "xhigh"),
    ("REEFCASE_GFW_TOKEN", "gfw-token", "gfw-token"),
    ("REEFCASE_TELEGRAM_TOKEN", "123:abc", "123:abc"),
    ("REEFCASE_KEEP_FRAMES", "48", 48),
    ("REEFCASE_MIN_FRAMES", "12", 12),
]


def unwrap(value: object) -> object:
    return value.get_secret_value() if isinstance(value, SecretStr) else value


def test_defaults_match_architecture() -> None:
    settings = make_settings()

    assert settings.data_dir == DEFAULT_DATA_DIR == Path("var")
    assert settings.segmenter == "fake"
    assert settings.sam_model_id == DEFAULT_SAM_MODEL_ID == "facebook/sam3"
    assert settings.sam_modal_url is None
    assert settings.student_weights is None
    assert settings.keep_frames == DEFAULT_KEEP_FRAMES == 24
    assert settings.min_frames == DEFAULT_MIN_FRAMES == 6
    assert settings.llm_agent_reasoning_effort == DEFAULT_AGENT_REASONING_EFFORT == "medium"
    assert settings.llm_teacher_reasoning_effort == DEFAULT_TEACHER_REASONING_EFFORT == "low"
    for field in (
        "llm_agent_base_url",
        "llm_agent_api_key",
        "llm_agent_model",
        "llm_teacher_base_url",
        "llm_teacher_api_key",
        "llm_teacher_model",
        "llm_student_base_url",
        "llm_student_api_key",
        "llm_student_model",
        "gfw_token",
        "telegram_token",
    ):
        assert getattr(settings, field) is None, field


def test_env_prefix_maps_flat_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REEFCASE_LLM_AGENT_BASE_URL", "https://inference.baseten.co/v1")
    monkeypatch.setenv("REEFCASE_LLM_AGENT_API_KEY", "sk-flat")
    monkeypatch.setenv("REEFCASE_LLM_AGENT_MODEL", "meta-models/muse-spark-open")

    settings = make_settings()

    assert settings.llm_agent_base_url == "https://inference.baseten.co/v1"
    assert isinstance(settings.llm_agent_api_key, SecretStr)
    assert settings.llm_agent_api_key.get_secret_value() == "sk-flat"
    assert settings.llm_agent_model == "meta-models/muse-spark-open"


@pytest.mark.parametrize(("env_var", "raw", "expected"), ENV_TABLE)
def test_every_4_4_variable_is_read(
    monkeypatch: pytest.MonkeyPatch, env_var: str, raw: str, expected: object
) -> None:
    field = env_var.removeprefix("REEFCASE_").lower()
    assert field in Settings.model_fields, f"{env_var} has no matching Settings field"

    monkeypatch.setenv(env_var, raw)
    settings = make_settings()

    assert unwrap(getattr(settings, field)) == expected


def test_every_env_example_variable_is_covered() -> None:
    """The table above is the full §4.4 surface: 20 variables, no more, no fewer."""
    assert len(ENV_TABLE) == 20
    assert len({row[0] for row in ENV_TABLE}) == 20


def test_empty_env_value_means_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REEFCASE_LLM_AGENT_BASE_URL", "")
    monkeypatch.setenv("REEFCASE_KEEP_FRAMES", "")
    monkeypatch.setenv("REEFCASE_SEGMENTER", "")

    settings = make_settings()

    assert settings.llm_agent_base_url is None
    assert settings.keep_frames == DEFAULT_KEEP_FRAMES
    assert settings.segmenter == "fake"


@pytest.mark.parametrize(
    ("env_var", "value"),
    [
        ("REEFCASE_SEGMENTER", "nope"),
        ("REEFCASE_LLM_TEACHER_REASONING_EFFORT", "extreme"),
        ("REEFCASE_LLM_AGENT_REASONING_EFFORT", "highest"),
    ],
)
def test_invalid_segmenter_and_effort_rejected(
    monkeypatch: pytest.MonkeyPatch, env_var: str, value: str
) -> None:
    monkeypatch.setenv(env_var, value)

    with pytest.raises(ValidationError):
        make_settings()


@pytest.mark.parametrize("env_var", ["REEFCASE_KEEP_FRAMES", "REEFCASE_MIN_FRAMES"])
def test_frame_limits_are_positive(monkeypatch: pytest.MonkeyPatch, env_var: str) -> None:
    monkeypatch.setenv(env_var, "0")

    with pytest.raises(ValidationError):
        make_settings()


def test_secrets_are_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REEFCASE_LLM_AGENT_API_KEY", "sk-secret")
    monkeypatch.setenv("REEFCASE_GFW_TOKEN", "gfw-secret")

    settings = make_settings()

    assert isinstance(settings.llm_agent_api_key, SecretStr)
    assert settings.llm_agent_api_key.get_secret_value() == "sk-secret"
    rendered = repr(settings) + settings.model_dump_json()
    assert "sk-secret" not in rendered
    assert "gfw-secret" not in rendered


def test_llm_role_none_when_unconfigured() -> None:
    settings = make_settings()

    assert settings.llm_role("agent") is None
    assert settings.llm_role("teacher") is None
    assert settings.llm_role("student") is None


def test_llm_role_complete_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REEFCASE_LLM_AGENT_BASE_URL", "https://agent.example/v1")
    monkeypatch.setenv("REEFCASE_LLM_AGENT_API_KEY", "sk-agent")
    monkeypatch.setenv("REEFCASE_LLM_AGENT_MODEL", "agent-model")
    monkeypatch.setenv("REEFCASE_LLM_STUDENT_BASE_URL", "https://student.example/v1")
    monkeypatch.setenv("REEFCASE_LLM_STUDENT_API_KEY", "sk-student")
    monkeypatch.setenv("REEFCASE_LLM_STUDENT_MODEL", "student-model")

    settings = make_settings()
    agent = settings.llm_role("agent")
    student = settings.llm_role("student")

    assert agent == LLMRoleConfig(
        base_url="https://agent.example/v1",
        api_key="sk-agent",
        model="agent-model",
        reasoning_effort="medium",
    )
    assert student is not None
    assert student.api_key == "sk-student"
    assert student.reasoning_effort is None


def test_llm_role_effort_comes_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REEFCASE_LLM_TEACHER_BASE_URL", "https://teacher.example/v1")
    monkeypatch.setenv("REEFCASE_LLM_TEACHER_API_KEY", "sk-teacher")
    monkeypatch.setenv("REEFCASE_LLM_TEACHER_MODEL", "teacher-model")
    monkeypatch.setenv("REEFCASE_LLM_TEACHER_REASONING_EFFORT", "high")

    teacher = make_settings().llm_role("teacher")

    assert teacher is not None
    assert teacher.reasoning_effort == "high"


@pytest.mark.parametrize("role", ["agent", "teacher", "student"])
def test_llm_role_partial_config_raises(monkeypatch: pytest.MonkeyPatch, role: LLMRole) -> None:
    prefix = f"REEFCASE_LLM_{role.upper()}"
    monkeypatch.setenv(f"{prefix}_BASE_URL", "https://partial.example/v1")
    monkeypatch.setenv(f"{prefix}_MODEL", "partial-model")

    with pytest.raises(ConfigError) as excinfo:
        make_settings().llm_role(role)

    message = str(excinfo.value)
    assert f"{prefix}_API_KEY" in message
    assert "partial.example" not in message
    assert "partial-model" not in message


def test_llm_role_partial_config_names_every_missing_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REEFCASE_LLM_AGENT_BASE_URL", "https://partial.example/v1")

    with pytest.raises(ConfigError) as excinfo:
        make_settings().llm_role("agent")

    message = str(excinfo.value)
    assert "REEFCASE_LLM_AGENT_API_KEY" in message
    assert "REEFCASE_LLM_AGENT_MODEL" in message
