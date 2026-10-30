import importlib.util
import json
from pathlib import Path
from types import ModuleType

import numpy as np

_SCRIPT = Path(__file__).resolve().parents[2] / "ml" / "modal" / "gen_assessments.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_assessments_script", _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load gen_assessments.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_halves_split_frame_and_mask_into_squares() -> None:
    module = _load_script()
    image = np.zeros((4, 8, 3), dtype=np.uint8)
    image[:, 4:] = 255
    mask = np.zeros((4, 8), dtype=np.uint8)
    mask[:, 4:] = 5

    (left, left_image, left_mask), (right, right_image, right_mask) = module.halves(image, mask)

    assert (left, right) == ("left", "right")
    assert left_image.shape == right_image.shape == (4, 4, 3)
    assert left_image.max() == 0 and right_image.min() == 255
    assert left_mask.max() == 0 and right_mask.min() == 5


def test_done_ids_skips_a_torn_last_line(tmp_path: Path) -> None:
    module = _load_script()
    rows = tmp_path / "assessments.jsonl"
    rows.write_text(json.dumps({"id": "a"}) + "\n" + '{"id": "b", "mess', encoding="utf-8")

    assert module.done_ids(rows) == {"a"}
    assert module.done_ids(tmp_path / "missing.jsonl") == set()


def test_chat_row_holds_system_user_and_assistant_turns() -> None:
    module = _load_script()
    assessment = {"bleaching_severity": 1, "morphology": [], "damage": ["none"], "notes": "ok"}

    row = module.chat_row(
        row_id="abc",
        frame="site01_x.png",
        half="left",
        instructions="be a scientist",
        prompt="cover: ...",
        assessment=assessment,
        teacher="muse",
        usage={"input_tokens": 10, "output_tokens": 2},
    )

    system, user, assistant = row["messages"]
    assert system == {"role": "system", "content": "be a scientist"}
    assert user["content"][0] == {"type": "image", "image": "images/abc.jpg"}
    assert json.loads(assistant["content"]) == assessment


def test_cost_and_usage_policy() -> None:
    module = _load_script()

    assert module.cost_usd(1_000_000, 1_000_000) == 5.5
    assert module.usage_policy("licence text\n**EXHIBIT A - Policy**\nrules") == (
        "**EXHIBIT A - Policy**\nrules"
    )
