"""Muse Spark Open frame assessments, the distillation set for Glimmer-Reef (Story 7.5).

Each Coralscapes train + val frame (1024x2048; never the test split) is cut into its left
and right 1024x1024 halves, so 1,683 frames give 3,366 candidate rows. Every half goes to the
teacher with its SAM 3 cover (from ``ml/modal/pseudo_label_run.py``) and exactly the
instructions and prompt the app sends (``reefcase.llm.assess``), so Glimmer trains on the
input it will see.

Output, on the ``reefcase-assessments`` volume under ``/muse``:
- ``assessments.jsonl``: one chat-format row per half (system, user = image + prompt,
  assistant = the ``FrameAssessment`` fields as JSON), keyed by the JPEG's SHA-256, so
  re-running skips what is written (resumable) and no image appears twice (deduplicated).
- ``images/<sha>.jpg``: the halves the rows point at.
- ``LICENSE-MUSE.md`` and ``USAGE_POLICY.md``: any model trained on these rows is a Muse
  Derivative (architecture section 9.7).

Run from the repo root (the ``reefcase`` secret carries ``REEFCASE_LLM_TEACHER_*``):
    PYTHONUTF8=1 uv run --with modal modal run ml/modal/gen_assessments.py --limit 6
    PYTHONUTF8=1 uv run --with modal modal run --detach ml/modal/gen_assessments.py
    MSYS_NO_PATHCONV=1 PYTHONUTF8=1 uv run --with modal modal volume get --force \\
        reefcase-assessments muse var/assessments

Credit guards: CPU only, one container. The Baseten spend is capped by ``--budget-usd``,
estimated from the token usage Baseten reports.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import numpy as np

try:
    import modal
except ImportError:  # pragma: no cover - Modal is a human run dependency.
    modal = None

__all__ = ["chat_row", "cost_usd", "done_ids", "halves", "usage_policy"]

# Baseten's Muse Spark Open list price per million tokens (checked 2026-10-30).
USD_PER_M_INPUT = 1.25
USD_PER_M_OUTPUT = 4.25
_HUB = "https://huggingface.co"
_REPO = "EPFL-ECEO/coralscapes"
_MUSE_REPO = "meta-models/Muse-Spark-Open-816B-A42B"
_LABELS = Path("/labels/trainval/labels")
_OUT = Path("/out/muse")


def halves(image: np.ndarray, mask: np.ndarray) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """The left and right square halves of a frame and its class map."""
    side = image.shape[1] // 2
    return [
        ("left", image[:, :side], mask[:, :side]),
        ("right", image[:, side : 2 * side], mask[:, side : 2 * side]),
    ]


def chat_row(
    *,
    row_id: str,
    frame: str,
    half: str,
    instructions: str,
    prompt: str,
    assessment: dict[str, object],
    teacher: str,
    usage: dict[str, int],
) -> dict[str, object]:
    return {
        "id": row_id,
        "frame": frame,
        "half": half,
        "source": "coralscapes",
        "licence": "image Apache-2.0; assessment Muse Model License",
        "teacher": teacher,
        "usage": usage,
        "messages": [
            {"role": "system", "content": instructions},
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": f"images/{row_id}.jpg"},
                    {"type": "text", "text": prompt},
                ],
            },
            {"role": "assistant", "content": json.dumps(assessment)},
        ],
    }


def done_ids(path: Path) -> set[str]:
    """Row ids already written; a torn last line (killed mid-write) is ignored."""
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            ids.add(json.loads(line)["id"])
        except json.JSONDecodeError, KeyError:
            continue
    return ids


def cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * USD_PER_M_INPUT + output_tokens * USD_PER_M_OUTPUT) / 1_000_000


def usage_policy(licence: str) -> str:
    """Exhibit A of the Muse Model License: the Usage Policy it incorporates."""
    start = licence.index("**EXHIBIT A")
    return licence[start:]


async def _generate(limit: int | None, concurrency: int, budget_usd: float) -> str:
    import asyncio

    import duckdb
    import httpx
    from PIL import Image
    from pydantic_ai import BinaryContent

    from reefcase.core.config import Settings
    from reefcase.core.schemas import Frame, QualityScore, Segmentation
    from reefcase.llm.assess import _INSTRUCTIONS, ASSESS_AGENT, _prompt
    from reefcase.llm.providers import build_model
    from reefcase.vision.cover import cover_from_mask

    model = build_model("teacher", Settings())
    assert model is not None
    _OUT.joinpath("images").mkdir(parents=True, exist_ok=True)
    hub = httpx.Client(base_url=_HUB, follow_redirects=True, timeout=600)
    licence = hub.get(f"/{_MUSE_REPO}/resolve/main/LICENSE.md").raise_for_status().text
    _OUT.joinpath("LICENSE-MUSE.md").write_text(licence, encoding="utf-8")
    _OUT.joinpath("USAGE_POLICY.md").write_text(usage_policy(licence), encoding="utf-8")

    rows_path = _OUT / "assessments.jsonl"
    done = done_ids(rows_path)
    totals = {"written": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0}
    gate = asyncio.Semaphore(concurrency)
    quality = QualityScore(blur=0.0, color_cast=0.0, turbidity=0.0, passed=True)

    async def assess(name: str, half: str, image: np.ndarray, mask: np.ndarray) -> None:
        buf = io.BytesIO()
        Image.fromarray(np.ascontiguousarray(image)).save(buf, format="JPEG", quality=90)
        jpeg = buf.getvalue()
        row_id = hashlib.sha256(jpeg).hexdigest()[:16]
        if row_id in done:
            return
        done.add(row_id)
        frame = Frame(
            id=f"frm_{row_id}",
            survey_id="srv_coralscapes",
            t_sec=0.0,
            image_path=f"images/{row_id}.jpg",
            quality=quality,
        )
        seg = Segmentation(
            id=f"seg_{row_id}",
            frame_id=frame.id,
            backend="sam3",
            mask_path="",
            cover=cover_from_mask(mask),
            latency_ms=0,
        )
        prompt = _prompt(frame, seg)
        async with gate:
            if cost_usd(totals["input_tokens"], totals["output_tokens"]) >= budget_usd:
                return
            try:
                result = await ASSESS_AGENT.run(
                    [prompt, BinaryContent(data=jpeg, media_type="image/jpeg")], model=model
                )
            except Exception as error:  # skip the half; a re-run retries it
                done.discard(row_id)
                totals["failed"] += 1
                print(f"{name} {half}: {type(error).__name__}: {error}", flush=True)
                return
        usage = result.usage
        totals["input_tokens"] += usage.input_tokens
        totals["output_tokens"] += usage.output_tokens
        _OUT.joinpath("images", f"{row_id}.jpg").write_bytes(jpeg)
        row = chat_row(
            row_id=row_id,
            frame=name,
            half=half,
            instructions=_INSTRUCTIONS,
            prompt=prompt,
            assessment=result.output.model_dump(),
            teacher=model.model_name,
            usage={"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
        )
        with rows_path.open("a", encoding="utf-8") as rows:
            rows.write(json.dumps(row) + "\n")
        totals["written"] += 1
        if totals["written"] % 100 == 0:
            await out.commit.aio()
            print(
                f"{totals} ${cost_usd(totals['input_tokens'], totals['output_tokens']):.2f}",
                flush=True,
            )

    tree = hub.get(f"/api/datasets/{_REPO}/tree/main/data").raise_for_status().json()
    files = sorted(entry["path"] for entry in tree)
    queued = 0
    for split in ("train", "validation"):
        for file in (f for f in files if f.startswith(f"data/{split}-")):
            if limit is not None and queued >= limit:
                break
            local = Path("/tmp") / Path(file).name
            url = f"/datasets/{_REPO}/resolve/main/{file}"
            with hub.stream("GET", url) as response, local.open("wb") as parquet:
                for chunk in response.raise_for_status().iter_bytes():
                    parquet.write(chunk)
            tasks = []
            for (row,) in duckdb.execute(
                "SELECT image FROM read_parquet(?)", [str(local)]
            ).fetchall():
                name = row["path"]
                image = np.asarray(Image.open(io.BytesIO(row["bytes"])).convert("RGB"))
                mask = np.asarray(Image.open(_LABELS / name))
                for half, image_half, mask_half in halves(image, mask):
                    if limit is not None and queued >= limit:
                        break
                    queued += 1
                    tasks.append(assess(name, half, image_half, mask_half))
            await asyncio.gather(*tasks)
            local.unlink()
    await out.commit.aio()
    spent = cost_usd(totals["input_tokens"], totals["output_tokens"])
    return json.dumps({**totals, "rows_total": len(done_ids(rows_path)), "usd": round(spent, 2)})


if modal is not None:  # pragma: no cover - requires Modal CLI and credentials.
    app = modal.App("reefcase-gen-assessments")
    image = (
        modal.Image.debian_slim(python_version="3.14")
        .uv_sync(frozen=True, extra_options="--no-dev")
        .add_local_python_source("reefcase")
    )
    labels = modal.Volume.from_name("reefcase-pseudo-labels")
    out = modal.Volume.from_name("reefcase-assessments", create_if_missing=True)

    @app.function(
        image=image,
        cpu=2.0,
        memory=8192,
        volumes={"/labels": labels, "/out": out},
        secrets=[modal.Secret.from_name("reefcase")],
        max_containers=1,
        timeout=6 * 3600,
    )
    async def generate(limit: int | None, concurrency: int, budget_usd: float) -> str:
        return await _generate(limit, concurrency, budget_usd)

    @app.local_entrypoint()
    def main(limit: int | None = None, concurrency: int = 16, budget_usd: float = 20.0) -> None:
        print(generate.remote(limit, concurrency, budget_usd))
