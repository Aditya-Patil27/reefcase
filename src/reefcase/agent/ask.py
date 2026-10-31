"""Agent answering follow-up questions about a survey's case file (Story 8.6, §5.5).

Grounded exclusively on the stored Investigation, frame quality/segmentation/assessment,
and the tool results this survey's agent received. Register no tools and make no live fetches.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.usage import UsageLimits

from reefcase.agent.investigator import frame_line
from reefcase.core.schemas import (
    EvidenceRef,
    Frame,
    FrameAssessment,
    Investigation,
    Segmentation,
    ToolResult,
)

__all__ = [
    "ASK_AGENT",
    "ASK_PROMPT",
    "Answer",
    "AskRequest",
    "ask",
]

ASK_PROMPT = (Path(__file__).parent / "prompts" / "ask.md").read_text(encoding="utf-8")


class AskRequest(BaseModel):
    """Question asked about a survey's investigation."""

    question: str = Field(description="Question about the case file")

    @field_validator("question")
    @classmethod
    def _validate_question(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("question must not be empty")
        if len(stripped) > 500:
            raise ValueError("question must not exceed 500 characters")
        return stripped


class Answer(BaseModel):
    """A cited answer to a question about the case file."""

    answer: str = Field(description="2 to 4 plain sentences answering the question")
    citations: list[EvidenceRef] = Field(
        default_factory=list[EvidenceRef],
        description="Every frame or tool result cited in the answer",
    )


@dataclass(slots=True)
class _AskDeps:
    known_ids: set[str]


ASK_AGENT = Agent(
    output_type=Answer,
    instructions=ASK_PROMPT,
    deps_type=_AskDeps,
    retries=1,
)


@ASK_AGENT.output_validator
def _validate_ask_citations(ctx: RunContext[_AskDeps], answer: Answer) -> Answer:
    known = ctx.deps.known_ids
    bad_refs = [ref for ref in answer.citations if ref.id not in known]
    if not bad_refs:
        return answer
    if ctx.retry >= ctx.max_retries:
        valid_citations = [ref for ref in answer.citations if ref.id in known]
        return answer.model_copy(update={"citations": valid_citations})
    bullet_list = "\n".join(f"- {ref.id}" for ref in bad_refs)
    raise ModelRetry(
        f"The following citations cite unknown evidence IDs:\n{bullet_list}\n"
        "Every citation must cite only valid frame IDs or tool_result IDs from this survey."
    )


def _build_prompt(
    question: str,
    investigation: Investigation,
    frames: list[Frame],
    segs: list[Segmentation],
    assessments: list[FrameAssessment],
    tool_results: list[ToolResult],
) -> str:
    seg_by_frame = {seg.frame_id: seg for seg in segs}
    assessment_by_frame = {a.frame_id: a for a in assessments}

    lines: list[str] = [
        f"# Case File for Survey {investigation.survey_id}",
        f"Verdict: {investigation.verdict}",
        "",
        "## Hypotheses:",
    ]
    for h in investigation.hypotheses:
        cause_val = h.cause.value if hasattr(h.cause, "value") else str(h.cause)
        sup = ", ".join(f"{r.kind}:{r.id}" for r in h.supporting)
        con = ", ".join(f"{r.kind}:{r.id}" for r in h.contradicting)
        lines.append(
            f"- Cause: {cause_val} (confidence {h.confidence:.2f}): "
            f"{h.rationale} [supporting: {sup or 'none'}, contradicting: {con or 'none'}]"
        )

    lines.append("\n## Findings:")
    for f in investigation.findings:
        ev = ", ".join(f"{r.kind}:{r.id}" for r in f.evidence)
        lines.append(f"- {f.statement} [evidence: {ev or 'none'}]")

    if investigation.actions:
        lines.append("\n## Actions:")
        for act in investigation.actions:
            lines.append(f"- {act}")

    lines.append(f"\n## Frame Evidence ({len(frames)} frames):")
    for frame in frames:
        lines.append(
            frame_line(frame, seg_by_frame.get(frame.id), assessment_by_frame.get(frame.id))
        )

    lines.append(f"\n## Tool Results ({len(tool_results)} results):")
    for tr in tool_results:
        data_str = json.dumps(tr.data, separators=(",", ":"), default=str)
        lines.append(f"- {tr.id} (tool: {tr.tool}): {data_str}")

    lines.append(f"\n## Question:\n{question}")
    return "\n".join(lines)


async def ask(
    question: str,
    investigation: Investigation,
    frames: list[Frame],
    segs: list[Segmentation],
    assessments: list[FrameAssessment],
    tool_results: list[ToolResult],
    *,
    model: Model,
) -> Answer:
    """Answer a question about the survey's investigation, citing only valid evidence."""
    known_ids = {f.id for f in frames} | {tr.id for tr in tool_results}
    deps = _AskDeps(known_ids=known_ids)
    prompt = _build_prompt(question, investigation, frames, segs, assessments, tool_results)
    result = await ASK_AGENT.run(
        prompt,
        model=model,
        deps=deps,
        model_settings=OpenAIChatModelSettings(openai_reasoning_effort="low", max_tokens=1500),
        usage_limits=UsageLimits(request_limit=3),
    )
    return result.output
