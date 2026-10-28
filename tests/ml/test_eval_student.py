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
        student_masks=student,
        sam3_masks=sam3,
        human_masks=human,
        kaggle_t4_ms_student=10.0,
        kaggle_t4_ms_sam3=100.0,
        rtx3050_ms_student=15.0,
    )

    assert "student" in report and "sam3" in report
    assert "per_class_iou" in report["student"]
    assert "kaggle_t4" in report["student"]["ms_per_frame"]
    assert "rtx_3050" in report["student"]["ms_per_frame"]


def test_eval_script_writes_json(tmp_path: Path) -> None:
    module = _load_script()
    out = tmp_path / "eval.json"

    report = module.build_eval_report(
        student_masks=[np.zeros((2, 2), dtype=np.uint8)],
        sam3_masks=[np.zeros((2, 2), dtype=np.uint8)],
        human_masks=[np.zeros((2, 2), dtype=np.uint8)],
        kaggle_t4_ms_student=10.0,
        kaggle_t4_ms_sam3=100.0,
        rtx3050_ms_student=15.0,
    )
    out.write_text(json.dumps(report), encoding="utf-8")

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["sam3"]["ms_per_frame"]["kaggle_t4"] == 100.0
