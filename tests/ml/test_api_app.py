"""Story 8.3: the Modal app pins where the deployed API keeps its data and web build."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "ml" / "modal" / "api_app.py"


def _load_script() -> ModuleType:
    module_name = "api_app_script"
    spec = importlib.util.spec_from_file_location(module_name, _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load api_app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


api_app = _load_script()


def test_api_settings_pin_the_volume_and_web_build(monkeypatch: pytest.MonkeyPatch) -> None:
    # A copied .env in the Modal secret must not move the data off the volume.
    monkeypatch.setenv("REEFCASE_DATA_DIR", "var")
    monkeypatch.setenv("REEFCASE_WEB_DIST", "elsewhere")
    monkeypatch.setenv("REEFCASE_SEGMENTER", "sam3_local")
    monkeypatch.setenv("REEFCASE_STUDENT_WEIGHTS", "elsewhere.pt")

    settings = api_app.api_settings()

    assert settings.data_dir == Path("/data")
    assert settings.web_dist == Path("/app/web/dist")
    assert settings.segmenter == "student"
    assert settings.student_weights == Path("/data/models/reefstudent.pt")


def test_seed_env_uses_the_volume_and_student() -> None:
    env = api_app.seed_env(
        {
            "REEFCASE_SEGMENTER": "fake",
            "REEFCASE_STUDENT_WEIGHTS": "elsewhere.pt",
            "REEFCASE_DATA_DIR": "var",
            "PATH": "/bin",
        }
    )

    assert env == {
        "REEFCASE_SEGMENTER": "student",
        "REEFCASE_STUDENT_WEIGHTS": "/data/models/reefstudent.pt",
        "REEFCASE_DATA_DIR": "/data",
        "OMP_NUM_THREADS": "2",
        "PATH": "/bin",
    }
