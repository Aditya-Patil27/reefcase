import importlib.util
import json
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[2] / "ml" / "modal" / "finetune_glimmer.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("finetune_glimmer_script", _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load finetune_glimmer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(frame: str, severity: int) -> dict[str, object]:
    answer = {"bleaching_severity": severity, "morphology": [], "damage": ["none"], "notes": ""}
    return {
        "id": f"{frame}-{severity}",
        "frame": frame,
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": []},
            {"role": "assistant", "content": json.dumps(answer)},
        ],
    }


def test_split_keeps_both_halves_of_a_frame_together() -> None:
    module = _load_script()
    rows = [_row(f"frame{i}", 0) for i in range(200) for _ in range(2)]

    train, test = module.split_rows(rows)

    assert len(train) + len(test) == 400
    assert 0 < len(test) < 80
    assert not {r["frame"] for r in train} & {r["frame"] for r in test}
    assert module.split_rows(rows) == (train, test)


def test_oversample_repeats_only_severe_rows() -> None:
    module = _load_script()
    rows = [_row("a", 0), _row("b", 2), _row("c", 3), _row("d", 4)]

    out = module.oversample(rows)

    assert [module.severity(r) for r in out].count(3) == 3
    assert [module.severity(r) for r in out].count(4) == 3
    assert [module.severity(r) for r in out].count(0) == 1


def test_label_ids_keep_only_the_last_turn() -> None:
    module = _load_script()
    start = 9

    labels = module.label_ids([1, start, 5, 6, start, 7, 8], start)

    assert labels == [-100] * 5 + [7, 8]


def test_parse_assessment_reads_the_user_channel_after_reasoning() -> None:
    module = _load_script()
    answer = {
        "bleaching_severity": 2,
        "morphology": ["branching"],
        "damage": ["none"],
        "notes": "x",
    }
    reasoned = (
        f" to=self<|message|>thinking {{not json}}<|eom|><|start|>assistant"
        f" to=user<|message|>```json\n{json.dumps(answer)}\n```<|eot|>"
    )

    assert module.parse_assessment(reasoned) == answer
    assert module.parse_assessment(f" to=user<|message|>{json.dumps(answer)}<|eot|>") == answer
    assert module.parse_assessment(" to=user<|message|>not json<|eot|>") is None
    bad = {**answer, "bleaching_severity": 7}
    assert module.parse_assessment(f"<|message|>{json.dumps(bad)}<|eot|>") is None
    assert module.parse_assessment("<|message|>[1, 2]<|eot|>") is None


def test_parse_assessment_reads_the_last_final_result_call() -> None:
    module = _load_script()
    call = (
        '<atem:function_calls>\n<atem:invoke name="final_result">\n'
        '<atem:parameter name="bleaching_severity">{sev}</atem:parameter>\n'
        '<atem:parameter name="morphology">["massive"]</atem:parameter>\n'
        '<atem:parameter name="damage">["none"]</atem:parameter>\n'
        '<atem:parameter name="notes">42</atem:parameter>\n'
        "</atem:invoke>\n</atem:function_calls>"
    )
    text = (
        f" to=self<|message|>draft {call.format(sev=9)}<|eom|>"
        f"<|start|>assistant to=final_result<|message|>{call.format(sev=1)}<|eot|>"
    )

    assert module.parse_assessment(text) == {
        "bleaching_severity": 1,
        "morphology": ["massive"],
        "damage": ["none"],
        "notes": "42",
    }
    assert module.parse_assessment(call.format(sev=9)) is None


def test_output_tool_is_the_assess_agents_final_result() -> None:
    module = _load_script()

    tool = module.output_tool()

    assert tool["type"] == "function"
    assert tool["function"]["name"] == "final_result"
    params = tool["function"]["parameters"]
    assert set(params["properties"]) == {"bleaching_severity", "morphology", "damage", "notes"}


def test_score_counts_invalid_answers_as_misses() -> None:
    module = _load_script()
    preds = [{"bleaching_severity": 0}, {"bleaching_severity": 2}, None, {"bleaching_severity": 1}]

    result = module.score(preds, [0, 1, 3, 1])

    assert result["n"] == 4
    assert result["json_valid"] == 0.75
    assert result["severity_exact"] == 0.5
    assert result["severity_within_one"] == 0.75
    assert result["agree_valid"] == round(2 / 3, 4)
    assert result["teacher_bleached"] == 3
    assert result["recall_bleached"] == round(2 / 3, 4)


def test_model_card_credits_muse() -> None:
    module = _load_script()

    assert "Built with Muse Spark Open" in module.MODEL_CARD
    assert "LICENSE-MUSE.md" in module.MODEL_CARD and "USAGE_POLICY.md" in module.MODEL_CARD
