"""Contract tests for ``reefcase.llm.providers`` (architecture §5.2, §9.7).

Construction only: ``build_model`` wires the role's environment into an
OpenAI-compatible pydantic-ai model and never performs I/O. No ``.run()``,
``TestModel`` or ``FunctionModel`` here — the gate must stay offline.
"""

import os
import socket

import pytest
from pydantic_ai.models.openai import OpenAIChatModel

from reefcase.core.config import LLMRole, Settings
from reefcase.core.errors import ConfigError
from reefcase.llm.providers import build_model

AGENT_ENV = {
    "REEFCASE_LLM_AGENT_BASE_URL": "https://inference.baseten.co/v1",
    "REEFCASE_LLM_AGENT_API_KEY": "sk-test",
    "REEFCASE_LLM_AGENT_MODEL": "meta-models/muse-spark-open",
}
TEACHER_ENV = {
    "REEFCASE_LLM_TEACHER_BASE_URL": "https://teacher.inference.example/v2",
    "REEFCASE_LLM_TEACHER_API_KEY": "sk-teacher",
    "REEFCASE_LLM_TEACHER_MODEL": "meta-models/spark-teacher",
}
STUDENT_ENV = {
    "REEFCASE_LLM_STUDENT_BASE_URL": "https://student.inference.example/v1",
    "REEFCASE_LLM_STUDENT_API_KEY": "sk-student",
    "REEFCASE_LLM_STUDENT_MODEL": "reef/glimmer-reef",
}
STUDENT_VARS = tuple(STUDENT_ENV)


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


def set_env(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_build_agent_model_uses_configured_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch, AGENT_ENV)

    model = build_model("agent", make_settings())

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "meta-models/muse-spark-open"
    assert model.client.api_key == "sk-test"
    assert str(model.client.base_url).rstrip("/") == "https://inference.baseten.co/v1"


def test_agent_reasoning_effort_defaults_to_medium(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch, AGENT_ENV)

    model = build_model("agent", make_settings())

    assert model is not None
    assert model.settings == {"openai_reasoning_effort": "medium"}


def test_agent_reasoning_effort_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch, AGENT_ENV)
    monkeypatch.setenv("REEFCASE_LLM_AGENT_REASONING_EFFORT", "xhigh")

    model = build_model("agent", make_settings())

    assert model is not None
    assert model.settings == {"openai_reasoning_effort": "xhigh"}


def test_teacher_uses_teacher_variables_and_low_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch, AGENT_ENV)
    set_env(monkeypatch, TEACHER_ENV)

    model = build_model("teacher", make_settings())

    assert model is not None
    assert model.model_name == "meta-models/spark-teacher"
    assert str(model.client.base_url).rstrip("/") == "https://teacher.inference.example/v2"
    assert model.client.api_key == "sk-teacher"
    assert model.settings == {"openai_reasoning_effort": "low"}


def test_student_is_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    assert build_model("student", make_settings()) is None

    for key in STUDENT_VARS:
        monkeypatch.delenv(key, raising=False)
    assert build_model("student", make_settings()) is None


def test_student_builds_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch, STUDENT_ENV)

    model = build_model("student", make_settings())

    assert model is not None
    assert model.model_name == "reef/glimmer-reef"
    assert str(model.client.base_url).rstrip("/") == "https://student.inference.example/v1"
    assert model.client.api_key == "sk-student"
    assert model.settings is None


@pytest.mark.parametrize(
    ("role", "variable"),
    [("agent", "REEFCASE_LLM_AGENT"), ("teacher", "REEFCASE_LLM_TEACHER")],
)
def test_agent_unconfigured_raises_config_error(role: LLMRole, variable: str) -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_model(role, make_settings())

    assert variable in str(excinfo.value)


def test_two_roles_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch, AGENT_ENV)
    set_env(monkeypatch, TEACHER_ENV)
    settings = make_settings()

    agent = build_model("agent", settings)
    teacher = build_model("teacher", settings)

    assert agent is not None
    assert teacher is not None
    assert agent.model_name != teacher.model_name
    assert agent.client.base_url != teacher.client.base_url


def test_build_model_does_not_leak_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch, AGENT_ENV)

    settings = make_settings()
    build_model("agent", settings)

    assert "sk-test" not in repr(settings)
    assert "sk-test" not in settings.model_dump_json()


def test_build_model_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructing a model must not open a socket, for any role."""

    def refuse_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("build_model opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse_connect)
    set_env(monkeypatch, AGENT_ENV)
    set_env(monkeypatch, TEACHER_ENV)
    set_env(monkeypatch, STUDENT_ENV)
    settings = make_settings()

    roles: tuple[LLMRole, ...] = ("agent", "teacher", "student")
    for role in roles:
        model = build_model(role, settings)
        assert model is not None
