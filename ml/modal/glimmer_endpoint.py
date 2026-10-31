"""Glimmer-Reef behind an OpenAI-compatible ``/v1/chat/completions`` (Story 7.7).

The assess stage switches to it with env config alone:
    REEFCASE_LLM_STUDENT_BASE_URL=https://<workspace>--reefcase-glimmer-endpoint-endpoint-serve.us-east.modal.run/v1
    REEFCASE_LLM_STUDENT_API_KEY=<GLIMMER_API_KEY from the ``reefcase-glimmer`` Modal secret>
    REEFCASE_LLM_STUDENT_MODEL=glimmer-reef

It serves Muse Glimmer-30B with the adapter merged in, through transformers rather than
vLLM, so prompts are rendered and completions decoded exactly as in the 7.6 eval: the
request's messages and tools go through Glimmer's ATEM chat template, and the last
``<atem:invoke>`` of a requested tool comes back as an OpenAI ``tool_calls`` entry.
Decoding is greedy. Requests that arrive together are generated as one batch: on one H100,
one 1024x1024 frame takes about 39 s warm and four concurrent frames about 70 s.

Deploy from the repo root (``GLIMMER_ADAPTER`` picks a directory under ``/adapters`` on the
``reefcase-glimmer`` volume; the default is v2, which beat v1 on bleached recall,
0.76 against 0.46-0.51, in ml/results/glimmer_v2_eval.json):
    modal secret create reefcase-glimmer GLIMMER_API_KEY=<random>
    GLIMMER_ADAPTER=glimmer-reef-v2 PYTHONUTF8=1 uv run --with modal modal deploy \\
        ml/modal/glimmer_endpoint.py

Credit guards: one H100 ($3.95/h) at most, scale to zero after 120 s idle, and no warm
containers. Do not add ``min_containers``: that bills around the clock.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from io import BytesIO
from typing import Any

try:
    import modal
except ImportError:  # pragma: no cover - Modal is a human deployment dependency.
    modal = None

__all__ = ["completion", "template_messages", "tool_call"]

ADAPTER = os.environ.get("GLIMMER_ADAPTER", "glimmer-reef-v2")
MAX_NEW_TOKENS = 1024
MAX_BATCH = 8
_INVOKE = re.compile(r'<atem:invoke name="(?P<name>[^"]+)">(?P<body>.*?)</atem:invoke>', re.DOTALL)
# The tokenizer's own `response_template` pattern for an ATEM parameter.
_PARAM = re.compile(
    r'<atem:parameter\b[^>]*?\bname="(?P<key>[^"]+)"[^>]*?>(?P<value>.*?)</atem:parameter>',
    re.DOTALL,
)
_ENDS = ("<|eot|>", "<|eom|>", "<|end_of_text|>")


def _part(part: dict[str, Any]) -> dict[str, Any]:
    if part.get("type") != "image_url":
        return part
    from PIL import Image

    url = part["image_url"]["url"]
    if not url.startswith("data:"):
        raise ValueError("only data: image URLs are accepted")
    raw = base64.b64decode(url.split(",", 1)[1])
    return {"type": "image", "image": Image.open(BytesIO(raw)).convert("RGB")}


def template_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """OpenAI chat messages in the shape Glimmer's chat template reads.

    Images become ``{"type": "image"}`` parts holding the decoded picture, and tool-call
    arguments become dicts, since the template cannot parse a JSON string.
    """
    out = []
    for message in messages:
        message = dict(message)
        if isinstance(message.get("content"), list):
            message["content"] = [_part(p) for p in message["content"]]
        if message.get("tool_calls"):
            message["tool_calls"] = [
                {**tc, "function": {**tc["function"], "arguments": json.loads(args)}}
                if isinstance(args := tc["function"]["arguments"], str)
                else tc
                for tc in message["tool_calls"]
            ]
        out.append(message)
    return out


def tool_call(text: str, tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The last ``<atem:invoke>`` of a requested tool in ``text``, as ``{name, arguments}``.

    A parameter whose schema type is ``string`` is kept verbatim; any other is read as
    JSON, falling back to the raw text, which leaves the schema check to the caller.
    """
    schemas = {t["function"]["name"]: t["function"].get("parameters", {}) for t in tools}
    calls = [m for m in _INVOKE.finditer(text) if m["name"] in schemas]
    if not calls:
        return None
    name, body = calls[-1]["name"], calls[-1]["body"]
    props = schemas[name].get("properties", {})
    arguments: dict[str, Any] = {}
    for key, value in _PARAM.findall(body):
        if props.get(key, {}).get("type") == "string":
            arguments[key] = value
            continue
        try:
            arguments[key] = json.loads(value)
        except json.JSONDecodeError:
            arguments[key] = value
    return {"name": name, "arguments": arguments}


def completion(
    text: str,
    tools: list[dict[str, Any]],
    model: str,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    truncated: bool,
) -> dict[str, Any]:
    """An OpenAI ``chat.completion`` for one decoded Glimmer reply."""
    call = tool_call(text, tools)
    if call is not None:
        fn = {"name": call["name"], "arguments": json.dumps(call["arguments"])}
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": f"call_{uuid.uuid4().hex[:24]}", "type": "function", "function": fn}
            ],
        }
        finish = "tool_calls"
    else:
        reply = text.rsplit("<|message|>", 1)[-1]
        for end in _ENDS:
            reply = reply.split(end, 1)[0]
        message = {"role": "assistant", "content": reply.strip()}
        finish = "length" if truncated else "stop"
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


if modal is not None:  # pragma: no cover - requires Modal CLI and credentials.
    import asyncio
    import hmac
    from collections import deque

    from fastapi import FastAPI, HTTPException, Request

    app = modal.App("reefcase-glimmer-endpoint")
    image = (
        modal.Image.debian_slim(python_version="3.14")
        .pip_install(
            # Same versions as ml/modal/finetune_glimmer.py, which produced the adapter.
            "torch==2.14.1",
            "torchvision==0.29.1",
            "transformers==5.22.1",
            "peft==0.21.2",
            "accelerate",
            "pillow",
            "fastapi[standard]",
        )
        .env({"GLIMMER_ADAPTER": ADAPTER})
    )
    glimmer = modal.Volume.from_name("reefcase-glimmer")

    @app.cls(
        image=image,
        gpu="H100",
        cpu=4.0,
        memory=65536,
        volumes={"/glimmer": glimmer},
        secrets=[modal.Secret.from_name("reefcase-glimmer")],
        max_containers=1,
        scaledown_window=120,
        timeout=600,
        startup_timeout=900,
    )
    @modal.concurrent(max_inputs=32)
    class Endpoint:
        @modal.enter()
        def load(self) -> None:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForMultimodalLM, AutoProcessor

            self.processor = AutoProcessor.from_pretrained("/glimmer/base")
            self.processor.tokenizer.padding_side = "left"
            tok = self.processor.tokenizer
            self.stop_ids = tok.convert_tokens_to_ids(["<|eot|>", "<|end_of_text|>"])
            base = AutoModelForMultimodalLM.from_pretrained(
                "/glimmer/base", dtype=torch.bfloat16, device_map="cuda"
            )
            self.model = PeftModel.from_pretrained(base, f"/glimmer/adapters/{ADAPTER}")
            self.model = self.model.merge_and_unload().eval()
            self.pending: deque[tuple[dict[str, Any], asyncio.Future]] = deque()
            self.wake = asyncio.Event()
            self.worker: asyncio.Task | None = None

        def _generate(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
            import torch

            tok = self.processor.tokenizer
            tools = batch[0].get("tools") or []
            inputs = self.processor.apply_chat_template(
                [template_messages(b["messages"]) for b in batch],
                tools=tools or None,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
                padding=True,
            ).to(self.model.device)
            limit = max(b.get("max_completion_tokens") or b.get("max_tokens") or 0 for b in batch)
            with torch.inference_mode():
                out = self.model.generate(
                    **inputs,
                    max_new_tokens=min(limit or MAX_NEW_TOKENS, MAX_NEW_TOKENS),
                    do_sample=False,
                    eos_token_id=self.stop_ids,
                    pad_token_id=tok.pad_token_id,
                )
            width = inputs["input_ids"].shape[1]
            results = []
            for b, prompt, seq in zip(batch, inputs["attention_mask"], out[:, width:], strict=True):
                ids = [t for t in seq.tolist() if t != tok.pad_token_id]
                results.append(
                    completion(
                        tok.decode(ids, skip_special_tokens=False),
                        tools,
                        b.get("model") or ADAPTER,
                        prompt_tokens=int(prompt.sum()),
                        completion_tokens=len(ids),
                        truncated=not any(t in ids for t in self.stop_ids),
                    )
                )
            return results

        async def _drain(self) -> None:
            # One request batches only with others that carry the same tools.
            while True:
                await self.wake.wait()
                self.wake.clear()
                while self.pending:
                    key = json.dumps(self.pending[0][0].get("tools"), sort_keys=True)
                    batch = []
                    for item in list(self.pending):
                        if (
                            len(batch) < MAX_BATCH
                            and json.dumps(item[0].get("tools"), sort_keys=True) == key
                        ):
                            batch.append(item)
                            self.pending.remove(item)
                    try:
                        results = await asyncio.to_thread(self._generate, [b for b, _ in batch])
                    except Exception as exc:  # every waiter gets the error
                        for _, future in batch:
                            future.set_exception(exc)
                        continue
                    for (_, future), result in zip(batch, results, strict=True):
                        future.set_result(result)

        @modal.asgi_app()
        def serve(self) -> FastAPI:
            api = FastAPI()
            key = os.environ["GLIMMER_API_KEY"]

            @api.post("/v1/chat/completions")
            async def chat(request: Request) -> dict[str, Any]:
                given = request.headers.get("authorization", "").removeprefix("Bearer ")
                if not hmac.compare_digest(given.encode(), key.encode()):
                    raise HTTPException(status_code=401, detail="bad API key")
                body = await request.json()
                if body.get("stream"):
                    raise HTTPException(status_code=400, detail="streaming is not supported")
                if self.worker is None:
                    self.worker = asyncio.create_task(self._drain())
                future = asyncio.get_running_loop().create_future()
                self.pending.append((body, future))
                self.wake.set()
                return await future

            return api
