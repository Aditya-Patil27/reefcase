"""Shared offline fixtures for every story's tests (Story 1.5).

Paths into ``tests/fixtures/`` plus the two helpers later stories lean on: a
temp ``Store`` and a ``make_settings`` factory that clears inherited
``REEFCASE_*`` variables so a developer's real ``.env`` can never leak into a
test run (the 1-3 learning).
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from reefcase.core.config import Settings
from reefcase.store.db import Store

TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
FRAMES_DIR = FIXTURES_DIR / "frames"
MASKS_DIR = FIXTURES_DIR / "masks"
CLIP_PATH = FIXTURES_DIR / "clip_10s.mp4"

__all__ = [
    "CLIP_PATH",
    "FIXTURES_DIR",
    "FRAMES_DIR",
    "MASKS_DIR",
    "TESTS_DIR",
    "clip_path",
    "data_dir",
    "fixture_frame",
    "fixture_mask",
    "make_settings",
    "store",
]


def fixture_frame(name: str) -> Path:
    """A fixture frame JPEG, e.g. ``fixture_frame("01.jpg")``."""
    return FRAMES_DIR / name


def fixture_mask(name: str) -> Path:
    """A fixture hand-mask PNG, e.g. ``fixture_mask("01.png")``."""
    return MASKS_DIR / name


@pytest.fixture
def clip_path() -> Path:
    """The 10 s fixture clip (Story 2.3 decodes it)."""
    return CLIP_PATH


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """An empty data dir (the Store creates it)."""
    return tmp_path / "var"


@pytest.fixture
def store(data_dir: Path) -> Iterator[Store]:
    """An open Store over a temp DuckDB file, closed after the test."""
    opened = Store.open(data_dir)
    yield opened
    opened.close()


@pytest.fixture
def make_settings(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Settings]:
    """Build ``Settings`` with a clean env: no inherited ``REEFCASE_*``, no ``.env``."""

    def factory(**overrides: Any) -> Settings:
        for key in list(os.environ):
            if key.upper().startswith("REEFCASE_"):
                monkeypatch.delenv(key, raising=False)
        return Settings(_env_file=None, **overrides)  # pyright: ignore[reportCallIssue]

    return factory
