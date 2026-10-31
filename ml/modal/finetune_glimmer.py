"""Glimmer-Reef: a LoRA fine-tune of Muse Glimmer-30B on Muse Spark Open assessments (Story 7.6).

Glimmer learns to answer the assess stage's request (``reefcase.llm.assess``) the way its
teacher did. That request carries pydantic-ai's ``final_result`` output tool, so the target
is that tool call in Glimmer's native ATEM format, made at once with no reasoning turn first,
and the prompt holds the tool exactly as the chat template renders it for the app. The tool
is read from ``ASSESS_AGENT`` at launch, so it cannot drift from what the app sends. Rows
come from ``ml/modal/gen_assessments.py``.

- Split: 90/10 by Coralscapes frame, so a frame's two halves never sit on both sides.
- Train: bf16 LoRA (r=16) on the language model's attention and MLP projections; the vision
  tower stays frozen. Loss falls on the assistant turn only. Severity 3-4 rows, about 4% of
  the set, are repeated so the rare bleached frames are not drowned out.
- Eval: greedy decoding over the held-out 10%, for base Glimmer and Glimmer-Reef, with the
  same prompt and tool. It reports the JSON-validity rate (a ``final_result`` call whose
  arguments pass the schema) and the bleaching-severity agreement with the teacher.

Volumes: ``reefcase-assessments`` (read, ``/data/muse``) and ``reefcase-glimmer``:
``/base`` holds the Hub weights, ``/adapters/<name>`` the adapter, with the Muse licence,
the Usage Policy and a model card that says "Built with Muse Spark Open" (the rows are Muse
outputs, so the adapter is a Muse Derivative), and ``/eval/<name>.json`` the scores.

Run from the repo root:
    PYTHONUTF8=1 uv run --with modal modal run ml/modal/finetune_glimmer.py --action download
    PYTHONUTF8=1 uv run --with modal modal run ml/modal/finetune_glimmer.py --action smoke
    PYTHONUTF8=1 uv run --with modal modal run --detach ml/modal/finetune_glimmer.py --action full
    MSYS_NO_PATHCONV=1 PYTHONUTF8=1 uv run --with modal modal volume get --force \\
        reefcase-glimmer eval/glimmer-reef.json ml/results/glimmer_eval.json

Credit guards: one H100 ($3.95/h) at most, a timeout on every function, and a smoke run
first. The smoke run trains 20 rows and scores 8, then prints the s/row and peak memory
that the full run's cost follows from.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from reefcase.core.schemas import FrameAssessment

try:
    import modal
except ImportError:  # pragma: no cover - Modal is a human run dependency.
    modal = None

__all__ = [
    "MODEL_CARD",
    "label_ids",
    "output_tool",
    "oversample",
    "parse_assessment",
    "score",
    "severity",
    "split_rows",
]

BASE_REPO = "meta-models/Muse-Glimmer-30B"
ADAPTER_NAME = "glimmer-reef"
USD_PER_H100_HOUR = 3.95
TEST_FRACTION = 0.1
IGNORE = -100
_DATA = Path("/data/muse")
_BASE = Path("/glimmer/base")
_ADAPTERS = Path("/glimmer/adapters")
_EVAL = Path("/glimmer/eval")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")
_INVOKE = re.compile(r'<atem:invoke name="final_result">(.*?)</atem:invoke>', re.DOTALL)
# The tokenizer's own `response_template` pattern for an ATEM parameter.
_PARAM = re.compile(
    r'<atem:parameter\b[^>]*?\bname="(?P<key>[^"]+)"[^>]*?>(?P<value>.*?)</atem:parameter>',
    re.DOTALL,
)

MODEL_CARD = f"""---
base_model: {BASE_REPO}
library_name: peft
license: other
license_name: muse-model-license
license_link: LICENSE-MUSE.md
---

# Glimmer-Reef

**Built with Muse Spark Open.**

A LoRA adapter for {BASE_REPO} that reads one underwater survey frame and its segmentation
cover and returns a ReefCase `FrameAssessment` (bleaching severity 0-4, coral morphology,
damage, notes) through pydantic-ai's `final_result` tool. It was distilled from Muse Spark
Open's assessments of Coralscapes frames, so it is a Muse Derivative: it ships with the Muse
Model License (`LICENSE-MUSE.md`) and its Usage Policy (`USAGE_POLICY.md`), and any use must
follow both.
Scores against the teacher are in `ml/results/glimmer_eval.json` in the ReefCase repo.
"""


def severity(row: dict[str, Any]) -> int:
    """The teacher's bleaching severity for a dataset row."""
    return int(json.loads(row["messages"][-1]["content"])["bleaching_severity"])


def split_rows(
    rows: Iterable[dict[str, Any]], test_fraction: float = TEST_FRACTION
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """A deterministic train/test split by source frame, so both halves land on one side."""
    train: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    for row in rows:
        bucket = int(hashlib.sha256(row["frame"].encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        (test if bucket < test_fraction else train).append(row)
    return train, test


def oversample(
    rows: list[dict[str, Any]], min_severity: int = 3, copies: int = 3
) -> list[dict[str, Any]]:
    """The rows with each severe-bleaching row repeated ``copies`` times in all."""
    extra = [row for row in rows if severity(row) >= min_severity for _ in range(copies - 1)]
    return rows + extra


def label_ids(input_ids: list[int], start_id: int) -> list[int]:
    """Training labels: the tokens after the last ``<|start|>`` (the assistant turn), else IGNORE.

    The turn's header (``assistant to=final_result<|message|>``) is learned too, which is
    what teaches Glimmer to skip the reasoning turn (``to=self``) and call the tool at once.
    """
    last = len(input_ids) - 1 - input_ids[::-1].index(start_id)
    return [IGNORE] * (last + 1) + input_ids[last + 1 :]


def output_tool() -> dict[str, Any]:
    """The ``final_result`` tool that ``ASSESS_AGENT`` sends, in OpenAI's tool format."""
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    from reefcase.llm.assess import ASSESS_AGENT

    seen: list[Any] = []

    def capture(_: list[Any], info: AgentInfo) -> ModelResponse:
        seen.append(info.output_tools[0])
        args = {"bleaching_severity": 0, "morphology": [], "damage": ["none"], "notes": ""}
        return ModelResponse(parts=[ToolCallPart(seen[0].name, args)])

    ASSESS_AGENT.run_sync("capture", model=FunctionModel(capture))
    tool = seen[0]
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters_json_schema,
        },
    }


def _fields(text: str) -> Any:
    """The fields of the last ``final_result`` call in ``text``, else a bare JSON reply."""
    calls = _INVOKE.findall(text)
    if calls:
        fields: dict[str, Any] = {}
        for key, value in _PARAM.findall(calls[-1]):
            if key == "notes":
                fields[key] = value
                continue
            try:
                fields[key] = json.loads(value)
            except json.JSONDecodeError:
                fields[key] = value
        return fields
    if "<|message|>" in text:
        text = text.rsplit("<|message|>", 1)[1]
    for end in ("<|eot|>", "<|eom|>", "<|end_of_text|>"):
        text = text.split(end, 1)[0]
    return json.loads(_FENCE.sub("", text.strip()))


def parse_assessment(text: str) -> dict[str, Any] | None:
    """The assessment in a decoded completion, or None if it has none that passes the schema.

    A base-model completion may open with a reasoning turn, so only the last
    ``final_result`` call counts (or, failing that, a JSON reply after the last
    ``<|message|>``).
    """
    try:
        fields = _fields(text)
        FrameAssessment.model_validate({**fields, "id": "-", "frame_id": "-", "model": "-"})
    except json.JSONDecodeError, TypeError, ValidationError:
        return None
    return fields


def score(predictions: list[dict[str, Any] | None], teacher: list[int]) -> dict[str, Any]:
    """JSON validity and bleaching-severity agreement with the teacher.

    Agreement is over all rows, so an invalid answer counts as a miss; ``agree_valid`` is
    the agreement among the valid answers alone.
    """
    n = len(teacher)
    valid = [
        (p["bleaching_severity"], t)
        for p, t in zip(predictions, teacher, strict=True)
        if p is not None
    ]
    exact = sum(p == t for p, t in valid)
    return {
        "n": n,
        "json_valid": round(len(valid) / n, 4),
        "severity_exact": round(exact / n, 4),
        "severity_within_one": round(sum(abs(p - t) <= 1 for p, t in valid) / n, 4),
        "agree_valid": round(exact / len(valid), 4) if valid else 0.0,
        "teacher_bleached": sum(t >= 1 for t in teacher),
        "recall_bleached": round(
            sum(p >= 1 for p, t in valid if t >= 1) / max(1, sum(t >= 1 for t in teacher)), 4
        ),
    }


def _load_rows() -> list[dict[str, Any]]:
    lines = _DATA.joinpath("assessments.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _conversation(row: dict[str, Any], *, reply: bool, reasoning: str | None = None) -> list:
    """A row's messages with the image path made absolute and the reply as a ``final_result``
    call; without the reply when ``reply`` is off.

    ``reasoning`` adds the template's ``Reasoning strength:`` line to the system prompt; the
    app's prompt has none, so the template otherwise writes ``high``.
    """
    system, user, assistant = row["messages"]
    if reasoning:
        system = {**system, "content": f"{system['content']}\n\nReasoning strength: {reasoning}."}
    content = [
        {**part, "image": str(_DATA / part["image"])} if part["type"] == "image" else part
        for part in user["content"]
    ]
    messages = [system, {**user, "content": content}]
    if not reply:
        return messages
    call = {"name": "final_result", "arguments": json.loads(assistant["content"])}
    return [
        *messages,
        {"role": "assistant", "tool_calls": [{"type": "function", "function": call}]},
    ]


def _run(
    action: str, tool: dict[str, Any], train_limit: int | None, eval_limit: int | None
) -> dict[str, Any]:
    import math
    import random
    import shutil
    import time

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForMultimodalLM, AutoProcessor

    started = time.monotonic()
    smoke = action == "smoke"
    name = f"{ADAPTER_NAME}-smoke" if smoke else ADAPTER_NAME
    train_rows, test_rows = split_rows(_load_rows())
    test_rows = test_rows[:eval_limit] if eval_limit else test_rows
    processor = AutoProcessor.from_pretrained(_BASE)
    processor.tokenizer.padding_side = "left"
    tok = processor.tokenizer
    start_id, eot_id = tok.convert_tokens_to_ids(["<|start|>", "<|eot|>"])
    stop_ids = [eot_id, tok.convert_tokens_to_ids("<|end_of_text|>")]
    model = AutoModelForMultimodalLM.from_pretrained(_BASE, dtype=torch.bfloat16, device_map="cuda")
    report: dict[str, Any] = {
        "base_model": BASE_REPO,
        "adapter": name,
        "built_with": "Built with Muse Spark Open",
        "split": {"train": len(train_rows), "test": len(test_rows), "by": "frame"},
        "load_s": round(time.monotonic() - started, 1),
    }
    print(json.dumps(report), flush=True)

    def evaluate(label: str, reasoning: str | None, max_new_tokens: int) -> None:
        model.eval()
        model.config.use_cache = True
        t0 = time.monotonic()
        preds: list[dict[str, Any] | None] = []
        samples: list[str] = []
        truncated = 0
        batch, i = 16, 0
        while i < len(test_rows):
            rows = test_rows[i : i + batch]
            inputs = processor.apply_chat_template(
                [_conversation(r, reply=False, reasoning=reasoning) for r in rows],
                tools=[tool],
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
                padding=True,
            ).to(model.device)
            try:
                with torch.inference_mode():
                    out = model.generate(
                        **inputs,
                        max_new_tokens=max_new_tokens,
                        do_sample=False,
                        eos_token_id=stop_ids,
                        pad_token_id=tok.pad_token_id,
                    )
            except torch.OutOfMemoryError:
                # Long reasoning on a big batch can outgrow what the weights leave free.
                if batch == 1:
                    raise
                del inputs
                torch.cuda.empty_cache()
                batch //= 2
                print(f"{label} OOM, batch -> {batch}", flush=True)
                continue
            i += len(rows)
            for seq in out[:, inputs["input_ids"].shape[1] :]:
                text = tok.decode(seq, skip_special_tokens=False).replace(tok.pad_token, "")
                truncated += not any(t in seq.tolist() for t in stop_ids)
                preds.append(parse_assessment(text))
                if len(samples) < 3:
                    samples.append(text[-1500:])
        seconds = time.monotonic() - t0
        report[label] = {
            **score(preds, [severity(r) for r in test_rows]),
            "truncated": truncated,
            "reasoning": reasoning or "template default (as served)",
            "s_per_row": round(seconds / len(test_rows), 2),
            "samples": samples,
        }
        print(label, json.dumps(report[label]), flush=True)
        del out
        torch.cuda.empty_cache()

    evaluate("base", "low", 1024 if not smoke else 768)

    rows = oversample(train_rows)
    random.Random(7).shuffle(rows)
    rows = rows[:train_limit] if train_limit else rows
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=r".*language_model\.layers\.\d+\.(self_attn\.(q|k|v|o)_proj|mlp\.(gate|up|down)_proj)",
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()
    accumulate = 8
    steps = math.ceil(len(rows) / accumulate)
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=1e-4, weight_decay=0.0
    )
    warmup = max(1, steps // 20)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lambda s: min(1.0, (s + 1) / warmup) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / steps))),
    )
    model.train()
    torch.cuda.reset_peak_memory_stats()
    t0 = time.monotonic()
    losses: list[float] = []
    for i, row in enumerate(rows):
        inputs = processor.apply_chat_template(
            _conversation(row, reply=True),
            tools=[tool],
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)
        ids = inputs["input_ids"][0].tolist()
        labels = torch.tensor([label_ids(ids, start_id)], device=model.device)
        loss = model(**inputs, labels=labels).loss
        (loss / accumulate).backward()
        losses.append(loss.item())
        if (i + 1) % accumulate == 0 or i + 1 == len(rows):
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            step = (i + 1 + accumulate - 1) // accumulate
            if step % 10 == 0 or smoke:
                recent = losses[-accumulate:]
                elapsed = time.monotonic() - t0
                print(
                    f"step {step}/{steps} loss {sum(recent) / len(recent):.4f} "
                    f"{elapsed / (i + 1):.2f}s/row seq {len(ids)}",
                    flush=True,
                )
            if step % 100 == 0:
                model.save_pretrained(_ADAPTERS / name)
                glimmer.commit()
    train_s = time.monotonic() - t0
    report["train"] = {
        "rows": len(rows),
        "optimizer_steps": steps,
        "loss_first": round(sum(losses[:accumulate]) / min(accumulate, len(losses)), 4),
        "loss_last": round(sum(losses[-accumulate:]) / min(accumulate, len(losses)), 4),
        "s_per_row": round(train_s / len(rows), 2),
        "peak_gib": round(torch.cuda.max_memory_allocated() / 2**30, 1),
        "lora": {"r": 16, "alpha": 32, "lr": 1e-4, "batch": accumulate, "epochs": 1},
    }
    print("train", json.dumps(report["train"]), flush=True)

    target = _ADAPTERS / name
    model.save_pretrained(target)
    processor.save_pretrained(target)
    target.joinpath("README.md").write_text(MODEL_CARD, encoding="utf-8")
    for doc in ("LICENSE-MUSE.md", "USAGE_POLICY.md"):
        shutil.copy(_DATA / doc, target / doc)

    evaluate("tuned", None, 1024)
    report["gpu_s"] = round(time.monotonic() - started, 1)
    report["usd_est"] = round(report["gpu_s"] / 3600 * USD_PER_H100_HOUR, 2)
    _EVAL.mkdir(parents=True, exist_ok=True)
    _EVAL.joinpath(f"{name}.json").write_text(json.dumps(report, indent=2) + "\n")
    glimmer.commit()
    return report


if modal is not None:  # pragma: no cover - requires Modal CLI and credentials.
    app = modal.App("reefcase-finetune-glimmer")
    image = (
        modal.Image.debian_slim(python_version="3.14")
        .pip_install(
            # torch as in the `gpu` group of pyproject.toml; Glimmer needs transformers >= 5.22.
            "torch==2.14.1",
            "torchvision==0.29.1",
            "transformers==5.22.1",
            "peft==0.21.2",
            "accelerate",
            "huggingface_hub",
            "pillow",
            "pydantic",
        )
        .env({"PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
        .add_local_python_source("reefcase")
    )
    data = modal.Volume.from_name("reefcase-assessments")
    glimmer = modal.Volume.from_name("reefcase-glimmer", create_if_missing=True)

    @app.function(
        image=image, cpu=4.0, memory=8192, volumes={"/glimmer": glimmer}, timeout=2 * 3600
    )
    def download() -> str:
        from huggingface_hub import snapshot_download

        snapshot_download(BASE_REPO, local_dir=_BASE)
        glimmer.commit()
        return f"{sum(p.stat().st_size for p in _BASE.rglob('*') if p.is_file()) / 1e9:.1f} GB"

    @app.function(
        image=image,
        gpu="H100",
        cpu=8.0,
        memory=65536,
        volumes={"/data": data, "/glimmer": glimmer},
        max_containers=1,
        timeout=8 * 3600,
    )
    def train(
        action: str, tool: dict[str, Any], train_limit: int | None, eval_limit: int | None
    ) -> dict[str, Any]:
        return _run(action, tool, train_limit, eval_limit)

    @app.local_entrypoint()
    def main(action: str = "smoke") -> None:
        if action == "download":
            print(download.remote())
        elif action == "smoke":
            print(json.dumps(train.remote("smoke", output_tool(), 20, 8), indent=2))
        elif action == "full":
            # Spawned, not awaited: with --detach the call outlives this client, so a dropped
            # connection cannot cancel a multi-hour run. Follow it with `modal app logs`.
            call = train.spawn("full", output_tool(), None, None)
            print(f"spawned {call.object_id}; report -> reefcase-glimmer:eval/{ADAPTER_NAME}.json")
        else:
            raise SystemExit("--action is download, smoke or full")
