"""The investigator: tool calls in, ranked hypotheses out (architecture §5.5).

``investigate`` gives the agent model the per-frame evidence and the context
tools from the registry, then returns its draft as an ``Investigation``. Every
tool call goes through ``registry.call`` (so its result is persisted and has a
``tr_…`` id to cite) and emits ``tool_called`` then ``tool_returned``. Tools run
one at a time: events stay in call order and GFW's one-report limit holds.

A tool that fails answers ``{"error": ...}`` to the model instead of failing
the survey. Citation checking is ``agent.citations`` (story 5.3).
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext, Tool
from pydantic_ai.models import Model
from pydantic_ai.toolsets import FunctionToolset

from reefcase.agent.citations import repair, validate
from reefcase.core.errors import ReefCaseError
from reefcase.core.events import Event, ToolCalled, ToolReturned
from reefcase.core.ids import INVESTIGATION, new_id
from reefcase.core.schemas import (
    Finding,
    Frame,
    FrameAssessment,
    Hypothesis,
    Investigation,
    Segmentation,
    Survey,
)
from reefcase.tools import heat_stress, history, mpa, reef_map, vessels
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import ToolSpec, registry

__all__ = [
    "INVESTIGATOR_AGENT",
    "INVESTIGATOR_PROMPT",
    "INVESTIGATOR_TOOLS",
    "InvestigationDraft",
    "investigate",
]

# Importing a tool module registers its tool.
_TOOL_MODULES = (heat_stress, history, mpa, reef_map, vessels)

INVESTIGATOR_TOOLS = ("heat_stress", "vessel_activity", "reef_map", "mpa_boundary", "site_history")
INVESTIGATOR_PROMPT = (Path(__file__).parent / "prompts" / "investigator.md").read_text(
    encoding="utf-8"
)
SUMMARY_CHARS = 200

Emit = Callable[[Event], Awaitable[None]]


class InvestigationDraft(BaseModel):
    """What the model fills in: ``Investigation`` minus id, survey_id and model."""

    findings: list[Finding] = Field(min_length=1, description="Cited statements about the reef")
    hypotheses: list[Hypothesis] = Field(
        min_length=1, description="Candidate causes, highest confidence first"
    )
    verdict: str = Field(description="One or two plain sentences for the park manager")
    actions: list[str] = Field(description="Concrete next steps")
    uncertain_frames: list[str] = Field(description="Frame IDs that could not be judged")


@dataclass(slots=True)
class _Deps:
    survey_id: str
    ctx: ToolContext
    emit: Emit
    known_ids: set[str]


INVESTIGATOR_AGENT = Agent(
    output_type=InvestigationDraft,
    instructions=INVESTIGATOR_PROMPT,
    deps_type=_Deps,
    retries=2,
)


@INVESTIGATOR_AGENT.output_validator
def _validate_citations(ctx: RunContext[_Deps], draft: InvestigationDraft) -> InvestigationDraft:
    offending = validate(draft, ctx.deps.known_ids)
    if not offending:
        return draft
    if ctx.retry >= ctx.max_retries:
        return repair(draft, ctx.deps.known_ids)
    bullet_list = "\n".join(f"- {s}" for s in offending)
    raise ModelRetry(
        f"The following statements cite unknown or missing evidence IDs:\n{bullet_list}\n"
        "Every statement must cite only valid frame IDs or tool_result IDs from this survey."
    )


def _now() -> datetime:
    return datetime.now(UTC)


async def _emit(deps: _Deps, event_type: type[ToolCalled | ToolReturned], **fields: Any) -> None:
    seq = await deps.ctx.store.events.next_seq(deps.survey_id)
    await deps.emit(event_type(survey_id=deps.survey_id, seq=seq, ts=_now(), **fields))


def _agent_tool(spec: ToolSpec) -> Tool[_Deps]:
    async def run(run_ctx: RunContext[_Deps], **kwargs: Any) -> dict[str, Any]:
        deps = run_ctx.deps
        try:
            params = spec.params_type.model_validate(kwargs)
        except ValidationError as exc:
            raise ModelRetry(f"invalid {spec.name} params: {exc}") from exc
        call_id = run_ctx.tool_call_id or ""
        await _emit(
            deps,
            ToolCalled,
            call_id=call_id,
            tool=spec.name,
            params=params.model_dump(mode="json"),
        )
        try:
            result = await registry.call(spec.name, params, deps.ctx)
        except ReefCaseError as exc:
            summary = f"error: {exc}"[:SUMMARY_CHARS]
            await _emit(deps, ToolReturned, call_id=call_id, tool_result_id="", summary=summary)
            return {"error": str(exc)}
        summary = json.dumps(result.data, separators=(",", ":"), default=str)[:SUMMARY_CHARS]
        await _emit(deps, ToolReturned, call_id=call_id, tool_result_id=result.id, summary=summary)
        deps.known_ids.add(result.id)
        return result.model_dump(mode="json", exclude={"params"})

    return Tool[_Deps].from_schema(
        run,
        name=spec.name,
        description=spec.description,
        json_schema=spec.params_type.model_json_schema(),
        takes_ctx=True,
        sequential=True,
    )


def _tools() -> list[Tool[_Deps]]:
    available = set(registry.names())
    return [_agent_tool(registry.spec(name)) for name in INVESTIGATOR_TOOLS if name in available]


def _frame_line(frame: Frame, seg: Segmentation | None, assessment: FrameAssessment | None) -> str:
    cover = (
        ", ".join(f"{cls.value}: {share * 100:.1f}%" for cls, share in seg.cover.items())
        if seg is not None
        else "no segmentation"
    )
    if assessment is None:
        health = "no assessment"
    else:
        health = (
            f"bleaching {assessment.bleaching_severity}/4, "
            f"morphology: {', '.join(assessment.morphology) or 'none'}, "
            f"damage: {', '.join(assessment.damage) or 'none'} | notes: {assessment.notes}"
        )
    return f"- {frame.id} at {frame.t_sec:.1f} s | cover: {cover} | {health}"


def _prompt(
    survey: Survey,
    frames: list[Frame],
    segs: list[Segmentation],
    assessments: list[FrameAssessment],
) -> str:
    seg_by_frame = {seg.frame_id: seg for seg in segs}
    assessment_by_frame = {a.frame_id: a for a in assessments}
    lines = [
        f"Survey {survey.id} at site {survey.site_id}, dive date {survey.dive_date.isoformat()}.",
        f"Frames ({len(frames)}):",
        *(
            _frame_line(frame, seg_by_frame.get(frame.id), assessment_by_frame.get(frame.id))
            for frame in frames
        ),
    ]
    return "\n".join(lines)


async def investigate(
    survey: Survey,
    frames: list[Frame],
    segs: list[Segmentation],
    assessments: list[FrameAssessment],
    ctx: ToolContext,
    emit: Emit,
    *,
    model: Model,
) -> Investigation:
    """Run the agent over the survey's evidence and return its ``Investigation``."""
    known_ids = {frame.id for frame in frames}
    deps = _Deps(survey_id=survey.id, ctx=ctx, emit=emit, known_ids=known_ids)
    result = await INVESTIGATOR_AGENT.run(
        _prompt(survey, frames, segs, assessments),
        model=model,
        deps=deps,
        toolsets=[FunctionToolset(_tools())],
    )
    return Investigation(
        id=new_id(INVESTIGATION),
        survey_id=survey.id,
        model=model.model_name,
        **result.output.model_dump(),
    )
