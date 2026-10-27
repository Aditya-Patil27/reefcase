import json
import importlib.util
from pathlib import Path
from types import ModuleType

from PIL import Image

_SCRIPT = Path(__file__).resolve().parents[2] / "ml" / "kaggle" / "pseudo_label.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pseudo_label_script", _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load pseudo_label.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_frame(path: Path) -> None:
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(path, format="JPEG")


def test_pseudo_label_writes_png_and_manifest(tmp_path: Path) -> None:
    module = _load_script()
    frames = tmp_path / "frames"
    frames.mkdir()
    _write_frame(frames / "a.jpg")
    output = tmp_path / "out"

    count = module.pseudo_label_frames(
        in_dir=frames,
        out_dir=output,
        source="coralscapes_trainval",
        licence="Apache-2.0",
    )

    assert count == 1
    assert (output / "labels" / "a.png").exists()
    manifest = (output / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(manifest) == 1
    payload = json.loads(manifest[0])
    assert payload["frame"] == "a.jpg"
    assert payload["source"] == "coralscapes_trainval"
    assert payload["licence"] == "Apache-2.0"
    assert sorted(payload["cover"]) == sorted(
        ["live_coral", "bleached_coral", "algae", "rubble", "sand", "other"]
    )


def test_pseudo_label_resumes_without_duplicate_rows(tmp_path: Path) -> None:
    module = _load_script()
    frames = tmp_path / "frames"
    frames.mkdir()
    _write_frame(frames / "a.jpg")
    _write_frame(frames / "b.jpg")
    output = tmp_path / "out"

    first = module.pseudo_label_frames(
        in_dir=frames,
        out_dir=output,
        source="ncrmp_non_demo",
        licence="US Gov",
        limit=1,
    )
    second = module.pseudo_label_frames(
        in_dir=frames,
        out_dir=output,
        source="ncrmp_non_demo",
        licence="US Gov",
    )

    assert first == 1
    assert second == 1
    lines = (output / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
