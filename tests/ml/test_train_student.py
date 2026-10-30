import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

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


def test_derive_group_is_the_coralscapes_dive_site() -> None:
    module = _load_script()

    assert module._derive_group("site29_000001_010000_leftImg8bit.png") == "site29"


def test_iou_from_confusion_indexes_classes_by_mask_index() -> None:
    module = _load_script()
    # Rows are targets, columns predictions, both in MASK_INDEX order (0 = other).
    confusion = np.zeros((6, 6), dtype=np.int64)
    confusion[0, 0] = 2
    confusion[1, 1] = 1
    confusion[1, 0] = 1

    per_class, miou = module.iou_from_confusion(confusion)

    assert per_class["other"] == 2 / 3
    assert per_class["live_coral"] == 0.5
    assert per_class["sand"] == 1.0  # absent from both sides
    assert miou == np.mean(list(per_class.values()))
