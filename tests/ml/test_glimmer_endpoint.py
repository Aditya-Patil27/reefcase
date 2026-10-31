import base64
import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType

from PIL import Image

_SCRIPT = Path(__file__).resolve().parents[2] / "ml" / "modal" / "glimmer_endpoint.py"
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "final_result",
            "description": "d",
            "parameters": {
                "type": "object",
                "properties": {
                    "bleaching_severity": {"type": "integer"},
                    "morphology": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
            },
        },
    }
]
CALL = (
    '<atem:function_calls>\n<atem:invoke name="final_result">\n'
    '<atem:parameter name="bleaching_severity">{sev}</atem:parameter>\n'
    '<atem:parameter name="morphology">["massive"]</atem:parameter>\n'
    '<atem:parameter name="notes">42</atem:parameter>\n'
    "</atem:invoke>\n</atem:function_calls>"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("glimmer_endpoint_script", _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load glimmer_endpoint.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_template_messages_decode_images_and_tool_arguments() -> None:
    module = _load_script()
    buf = io.BytesIO()
    Image.new("RGB", (4, 2)).save(buf, format="JPEG")
    url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    call = {"id": "c1", "type": "function", "function": {"name": "f", "arguments": '{"a": 1}'}}
    messages = [
        {"role": "system", "content": "s"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "t"},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        },
        {"role": "assistant", "content": None, "tool_calls": [call]},
        {"role": "tool", "tool_call_id": "c1", "content": "retry"},
    ]

    out = module.template_messages(messages)

    assert out[1]["content"][0] == {"type": "text", "text": "t"}
    assert out[1]["content"][1]["type"] == "image"
    assert out[1]["content"][1]["image"].size == (4, 2)
    assert out[2]["tool_calls"][0]["function"]["arguments"] == {"a": 1}
    assert out[3] == messages[3]
    assert messages[2]["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'


def test_tool_call_reads_the_last_call_of_a_requested_tool() -> None:
    module = _load_script()
    other = CALL.replace("final_result", "other_tool").format(sev=3)
    text = f" to=self<|message|>{CALL.format(sev=9)}<|eom|>{CALL.format(sev=1)}{other}<|eot|>"

    assert module.tool_call(text, TOOLS) == {
        "name": "final_result",
        "arguments": {"bleaching_severity": 1, "morphology": ["massive"], "notes": "42"},
    }
    assert module.tool_call("<|message|>plain text<|eot|>", TOOLS) is None


def test_completion_is_an_openai_tool_call_or_text_reply() -> None:
    module = _load_script()

    called = module.completion(
        CALL.format(sev=2) + "<|eot|>",
        TOOLS,
        "glimmer-reef",
        prompt_tokens=10,
        completion_tokens=5,
        truncated=False,
    )
    text = module.completion(
        " to=user<|message|>Healthy reef.<|eot|>",
        TOOLS,
        "glimmer-reef",
        prompt_tokens=10,
        completion_tokens=5,
        truncated=False,
    )

    choice = called["choices"][0]
    assert called["object"] == "chat.completion" and called["model"] == "glimmer-reef"
    assert choice["finish_reason"] == "tool_calls"
    fn = choice["message"]["tool_calls"][0]["function"]
    assert fn["name"] == "final_result"
    assert json.loads(fn["arguments"])["bleaching_severity"] == 2
    assert called["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert text["choices"][0]["message"] == {"role": "assistant", "content": "Healthy reef."}
    assert text["choices"][0]["finish_reason"] == "stop"
