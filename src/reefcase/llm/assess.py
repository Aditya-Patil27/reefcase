"""The frame assessor: one structured health reading per frame (architecture §5.3).

``assess_frame`` sends the frame's JPEG and its segmentation cover to the
teacher model and returns a ``FrameAssessment``. The Agent keeps pydantic-ai's
default tool-call output (§5.2): Muse Spark Open has no JSON mode, so
``NativeOutput`` is forbidden. One retry is allowed, so a second invalid output
raises ``UnexpectedModelBehavior`` and the caller decides what to skip.

Manual smoke test against the configured teacher (never run in CI)::

    uv run python -m reefcase.llm.assess --smoke tests/fixtures/frames/01.jpg
"""

import argparse
import asyncio
import io
import sys
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models import Model

from reefcase.core.config import Settings
from reefcase.core.errors import ConfigError
from reefcase.core.ids import ASSESSMENT, new_id
from reefcase.core.schemas import Frame, FrameAssessment, QualityScore, Segmentation
from reefcase.llm.providers import build_model
from reefcase.vision.cover import cover_from_mask
from reefcase.vision.fake import FakeSegmenter

__all__ = ["ASSESS_AGENT", "AssessmentDraft", "assess_frame"]


class AssessmentDraft(BaseModel):
    """What the model fills in: ``FrameAssessment`` minus id, frame_id and model."""

    bleaching_severity: int = Field(
        ge=0,
        le=4,
        description="0 none, 1 pale, 2 partly bleached, 3 mostly bleached, 4 fully white or dead",
    )
    morphology: list[str] = Field(
        description="Coral growth forms seen, e.g. branching, massive, tabular, encrusting"
    )
    damage: list[Literal["broken", "overturned", "anchor_scar", "disease", "none"]] = Field(
        description='Physical damage seen; ["none"] when there is none'
    )
    notes: str = Field(max_length=400, description="One or two plain sentences, under 400 chars")


_INSTRUCTIONS = """\
You are a coral reef scientist reading one underwater survey frame.
Judge only what is visible in the image. The segmentation cover is an automatic
estimate of what fraction of the frame each class covers; use it as a hint, not
as truth. Report bleaching severity, coral growth forms, physical damage and a
short note, and return them through the output tool."""

ASSESS_AGENT = Agent(output_type=AssessmentDraft, instructions=_INSTRUCTIONS, retries=1)


def _prompt(frame: Frame, seg: Segmentation) -> str:
    cover = ", ".join(f"{cls.value}: {fraction:.1%}" for cls, fraction in seg.cover.items())
    return f"Frame {frame.id} at {frame.t_sec:.1f} s. Segmentation cover ({seg.backend}): {cover}."


async def assess_frame(
    model: Model, frame: Frame, image_bytes: bytes, seg: Segmentation
) -> FrameAssessment:
    """Assess one frame; raises ``UnexpectedModelBehavior`` after two invalid outputs."""
    result = await ASSESS_AGENT.run(
        [_prompt(frame, seg), BinaryContent(data=image_bytes, media_type="image/jpeg")],
        model=model,
    )
    return FrameAssessment(
        id=new_id(ASSESSMENT),
        frame_id=frame.id,
        model=model.model_name,
        **result.output.model_dump(),
    )


async def _smoke(image_file: Path) -> FrameAssessment:
    model = build_model("teacher", Settings())
    if model is None:  # build_model only returns None for "student"
        raise ConfigError("REEFCASE_LLM_TEACHER_* is not configured")
    with Image.open(image_file) as img:
        rgb = img.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=90)
    segmenter = FakeSegmenter()
    frame = Frame(
        id="frm_smoke",
        survey_id="srv_smoke",
        t_sec=0.0,
        image_path=str(image_file),
        quality=QualityScore(blur=0.0, color_cast=0.0, turbidity=0.0, passed=True),
    )
    seg = Segmentation(
        id="seg_smoke",
        frame_id=frame.id,
        backend=segmenter.name,
        mask_path="",
        cover=cover_from_mask(segmenter.segment(np.asarray(rgb))),
        latency_ms=0,
    )
    return await assess_frame(model, frame, buf.getvalue(), seg)


def main(argv: list[str] | None = None) -> int:
    """``--smoke IMAGE``: assess one image with the configured teacher and print it."""
    parser = argparse.ArgumentParser(prog="python -m reefcase.llm.assess")
    parser.add_argument("--smoke", type=Path, required=True, metavar="IMAGE")
    args = parser.parse_args(argv)
    if not args.smoke.is_file():
        parser.error(f"no such image: {args.smoke}")
    assessment = asyncio.run(_smoke(args.smoke))
    sys.stdout.write(assessment.model_dump_json(indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
