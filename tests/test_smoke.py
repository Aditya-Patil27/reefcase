"""Smoke tests for the repository scaffold (Story 1.1).

These assert the shape of the scaffold itself: the package is importable, every
layer package that import-linter names exists, and ``pyproject.toml`` declares
the markers, the ``gate`` task and the layering contract from architecture §3.

They are intentionally dependency-free apart from pytest, ``tomllib`` and
``importlib``; they read ``pyproject.toml`` as data rather than through a
project library.
"""

import importlib
import tomllib
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Architecture §3, high → low, flattening each independent sibling group.
LAYER_ORDER = [
    "api",
    "bot",
    "pipeline",
    "agent",
    "tools",
    "llm",
    "vision",
    "ingest",
    "store",
    "core",
]

# Architecture §4.4, in table order.
CONFIG_VARIABLES = [
    "REEFCASE_DATA_DIR",
    "REEFCASE_WEB_DIST",
    "REEFCASE_SEGMENTER",
    "REEFCASE_SAM_MODEL_ID",
    "REEFCASE_SAM_MODAL_URL",
    "REEFCASE_SAM_MODAL_TOKEN",
    "REEFCASE_STUDENT_WEIGHTS",
    "REEFCASE_LLM_AGENT_BASE_URL",
    "REEFCASE_LLM_AGENT_API_KEY",
    "REEFCASE_LLM_AGENT_MODEL",
    "REEFCASE_LLM_TEACHER_BASE_URL",
    "REEFCASE_LLM_TEACHER_API_KEY",
    "REEFCASE_LLM_TEACHER_MODEL",
    "REEFCASE_LLM_STUDENT_BASE_URL",
    "REEFCASE_LLM_STUDENT_API_KEY",
    "REEFCASE_LLM_STUDENT_MODEL",
    "REEFCASE_LLM_AGENT_REASONING_EFFORT",
    "REEFCASE_LLM_TEACHER_REASONING_EFFORT",
    "REEFCASE_GFW_TOKEN",
    "REEFCASE_TELEGRAM_TOKEN",
    "REEFCASE_KEEP_FRAMES",
    "REEFCASE_MIN_FRAMES",
]


def load_pyproject() -> dict[str, Any]:
    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    parsed: dict[str, Any] = tomllib.loads(text)
    return parsed


def gate_commands(pyproject: dict[str, Any]) -> list[str]:
    """Flatten the ``gate`` task's ``sequence`` into plain command strings."""
    sequence = pyproject["tool"]["poe"]["tasks"]["gate"]["sequence"]
    commands: list[str] = []
    for step in sequence:
        if isinstance(step, dict):
            commands.append(str(step["cmd"]))
        else:
            commands.append(str(step))
    return commands


def test_package_imports() -> None:
    import reefcase

    assert reefcase.__version__ == "0.1.0"


@pytest.mark.parametrize("name", LAYER_ORDER)
def test_layer_packages_importable(name: str) -> None:
    # import-linter treats a missing layer as a hard error, so the contract and
    # the packages under src/reefcase/ must agree.
    assert importlib.import_module(f"reefcase.{name}") is not None


def test_pytest_markers_registered() -> None:
    pyproject = load_pyproject()
    markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]

    assert any(str(marker).startswith("gpu:") for marker in markers)
    assert any(str(marker).startswith("live:") for marker in markers)


def test_gate_task_runs_five_checks() -> None:
    commands = gate_commands(load_pyproject())
    expected = [
        "ruff check",
        "ruff format --check",
        "pyright",
        "lint-imports",
        'pytest -m "not gpu and not live"',
    ]

    positions: list[int] = []
    for needle in expected:
        matches = [index for index, command in enumerate(commands) if needle in command]
        assert matches, f"gate task is missing {needle!r}; commands are {commands}"
        positions.append(matches[0])

    assert positions == sorted(positions), f"gate task runs the checks out of order: {commands}"
    assert len(positions) == len(set(positions)), f"gate task is ambiguous: {commands}"


def test_import_linter_declares_architecture_layers() -> None:
    importlinter = load_pyproject()["tool"]["importlinter"]

    assert importlinter["root_packages"] == ["reefcase"]

    contracts = importlinter["contracts"]
    layers_contracts = [c for c in contracts if c["type"] == "layers"]
    assert len(layers_contracts) == 1
    layers_contract = layers_contracts[0]
    assert layers_contract["containers"] == ["reefcase"]

    declared: list[str] = []
    for layer in layers_contract["layers"]:
        declared.extend(part.strip() for part in str(layer).split("|"))
    assert declared == LAYER_ORDER

    forbidden_contracts = [c for c in contracts if c["type"] == "forbidden"]
    assert len(forbidden_contracts) == 1
    forbidden_contract = forbidden_contracts[0]
    assert forbidden_contract["source_modules"] == ["reefcase.core"]
    assert sorted(forbidden_contract["forbidden_modules"]) == sorted(
        f"reefcase.{name}" for name in LAYER_ORDER if name != "core"
    )


def test_env_example_lists_every_setting() -> None:
    lines = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    values = {
        key: value
        for key, _, value in (
            line.partition("=") for line in lines if "=" in line and not line.startswith("#")
        )
    }

    assert list(values) == CONFIG_VARIABLES
    assert all(value == "" for value in values.values()), "secrets must never be committed"


@pytest.mark.gpu
def test_gpu_marker_is_deselected_by_the_gate() -> None:
    # The gate runs `pytest -m "not gpu and not live"`, so this never runs
    # there. It exists so the marker is exercised, not to test anything.
    assert True


@pytest.mark.live
def test_live_marker_is_deselected_by_the_gate() -> None:
    # Same as above: deselected by the gate, present so `live` is registered
    # and the gate's selector is exercised.
    assert True
