import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[2] / "ml" / "kaggle" / "train_student.py"


def _load_script() -> ModuleType:
    module_name = "train_student_script"
    spec = importlib.util.spec_from_file_location(module_name, _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load train_student.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_split_manifest_is_grouped_and_near_90_10() -> None:
    module = _load_script()
    items = [
        module.ManifestItem(frame="vid_a_1.jpg", source="coralscapes", source_group="vid_a"),
        module.ManifestItem(frame="vid_a_2.jpg", source="coralscapes", source_group="vid_a"),
        module.ManifestItem(frame="vid_b_1.jpg", source="ncrmp", source_group="vid_b"),
        module.ManifestItem(frame="vid_c_1.jpg", source="ncrmp", source_group="vid_c"),
        module.ManifestItem(frame="vid_d_1.jpg", source="ncrmp", source_group="vid_d"),
        module.ManifestItem(frame="vid_e_1.jpg", source="ncrmp", source_group="vid_e"),
        module.ManifestItem(frame="vid_f_1.jpg", source="ncrmp", source_group="vid_f"),
        module.ManifestItem(frame="vid_g_1.jpg", source="ncrmp", source_group="vid_g"),
        module.ManifestItem(frame="vid_h_1.jpg", source="ncrmp", source_group="vid_h"),
        module.ManifestItem(frame="vid_i_1.jpg", source="ncrmp", source_group="vid_i"),
    ]

    train, val = module.split_manifest(items)

    assert {item.source_group for item in train}.isdisjoint({item.source_group for item in val})
    assert len(val) == 2
    assert len(train) == 8


def test_train_from_manifest_writes_best_checkpoint_and_metrics(tmp_path: Path) -> None:
    module = _load_script()
    manifest = tmp_path / "manifest.jsonl"
    lines = [
        {"frame": "vid_a_1.jpg", "source": "coralscapes", "source_group": "vid_a"},
        {"frame": "vid_a_2.jpg", "source": "coralscapes", "source_group": "vid_a"},
        {"frame": "vid_b_1.jpg", "source": "ncrmp", "source_group": "vid_b"},
    ]
    manifest.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

    metrics = module.train_from_manifest(manifest_path=manifest, out_dir=tmp_path / "out", epochs=3)

    checkpoint = json.loads((tmp_path / "out" / "reefstudent.pt").read_text(encoding="utf-8"))
    assert checkpoint["epoch"] == metrics["best_epoch"] == 3
    assert "live_coral" in checkpoint["class_iou"]
    curve = json.loads((tmp_path / "out" / "curve.json").read_text(encoding="utf-8"))
    assert len(curve) == 3
