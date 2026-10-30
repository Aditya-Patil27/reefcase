import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

_SCRIPT = Path(__file__).resolve().parents[2] / "ml" / "kaggle" / "eval_student.py"


def _load_script() -> ModuleType:
    module_name = "eval_student_script"
    spec = importlib.util.spec_from_file_location(module_name, _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load eval_student.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_build_eval_report_contains_required_fields() -> None:
    module = _load_script()
    human = [np.zeros((4, 4), dtype=np.uint8)]
    student = [np.zeros((4, 4), dtype=np.uint8)]
    sam3 = [np.zeros((4, 4), dtype=np.uint8)]

    report = module.build_eval_report(
        student_masks={"distilled": student, "supervised": human},
        sam3_masks=sam3,
        human_masks=human,
        kaggle_t4_ms_student={"distilled": 10.0, "supervised": 11.0},
        kaggle_t4_ms_sam3=100.0,
        rtx3050_ms_student=15.0,
    )

    assert "sam3" in report
    assert set(report["students"]) == {"distilled", "supervised"}
    assert "per_class_iou" in report["students"]["distilled"]
    assert report["students"]["supervised"]["ms_per_frame"]["kaggle_t4"] == 11.0
    assert report["students"][report["shipped"]]["ms_per_frame"]["rtx_3050"] == 15.0


def test_report_ships_the_student_with_the_best_miou() -> None:
    module = _load_script()
    human = [np.array([[1, 5]], dtype=np.uint8)]

    report = module.build_eval_report(
        student_masks={"distilled": [np.zeros((1, 2), dtype=np.uint8)], "supervised": human},
        sam3_masks=human,
        human_masks=human,
        kaggle_t4_ms_student={"distilled": 10.0, "supervised": 10.0},
        kaggle_t4_ms_sam3=100.0,
        rtx3050_ms_student=15.0,
    )

    assert report["shipped"] == "supervised"
    assert "rtx_3050" not in report["students"]["distilled"]["ms_per_frame"]


def test_eval_script_writes_json(tmp_path: Path) -> None:
    module = _load_script()
    out = tmp_path / "eval.json"

    report = module.build_eval_report(
        student_masks={"distilled": [np.zeros((2, 2), dtype=np.uint8)]},
        sam3_masks=[np.zeros((2, 2), dtype=np.uint8)],
        human_masks=[np.zeros((2, 2), dtype=np.uint8)],
        kaggle_t4_ms_student={"distilled": 10.0},
        kaggle_t4_ms_sam3=100.0,
        rtx3050_ms_student=15.0,
    )
    out.write_text(json.dumps(report), encoding="utf-8")

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["sam3"]["ms_per_frame"]["kaggle_t4"] == 100.0


def test_report_uses_mask_index_and_skips_ignored_pixels() -> None:
    module = _load_script()
    ignore = module.IGNORE
    human = [np.array([[1, 1], [0, ignore]], dtype=np.uint8)]
    student = [np.array([[1, 0], [0, 5]], dtype=np.uint8)]

    report = module.build_eval_report(
        student_masks={"distilled": student},
        sam3_masks=human,
        human_masks=human,
        kaggle_t4_ms_student={"distilled": 10.0},
        kaggle_t4_ms_sam3=100.0,
        rtx3050_ms_student=None,
    )

    iou = report["students"]["distilled"]["per_class_iou"]
    assert iou["live_coral"] == 0.5
    assert iou["other"] == 0.5
    assert iou["sand"] == 1.0  # its one pixel is ignored
    assert report["sam3"]["miou"] == 1.0


def test_human_lut_follows_the_committed_coralscapes_map() -> None:
    module = _load_script()
    mapping = json.loads((_SCRIPT.parents[1] / "coralscapes_map.json").read_text(encoding="utf-8"))

    lut = module.human_lut(mapping)

    assert lut[0] == module.IGNORE  # unlabelled
    assert lut[6] == 1  # "other coral alive" -> live_coral
    assert lut[4] == 2  # "other coral bleached" -> bleached_coral
    assert lut[3] == 0  # "other coral dead" -> other
    assert lut[5] == 5  # sand
