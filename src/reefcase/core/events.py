"""Pipeline events streamed to the bot and web (architecture §4.3).

Every event carries ``survey_id``, a per-survey monotonic ``seq`` (from 1) and
an aware ``ts``. ``Event`` is a discriminated union on ``type``; parse with
``EventAdapter`` so an unknown tag fails validation instead of silently
producing the wrong class.
"""

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import AwareDatetime, BaseModel, Field, TypeAdapter

from reefcase.core.schemas import Finding, FrameAssessment, QualityScore, SegBackend, SegClass

__all__ = [
    "Assessed",
    "Disagreement",
    "Event",
    "EventAdapter",
    "FindingEvent",
    "FrameScored",
    "FramesExtracted",
    "ReportReady",
    "Segmented",
    "SurveyFailed",
    "SurveyStarted",
    "ToolCalled",
    "ToolReturned",
]


class _EventBase(BaseModel):
    """Fields every event shares."""

    survey_id: str
    seq: int = Field(ge=1)
    ts: AwareDatetime


class SurveyStarted(_EventBase):
    """The worker picked up a queued survey."""

    type: Literal["survey_started"] = "survey_started"
    site_id: str


class FramesExtracted(_EventBase):
    """Frame extraction finished."""

    type: Literal["frames_extracted"] = "frames_extracted"
    count: int


class FrameScored(_EventBase):
    """A frame's quality was scored."""

    type: Literal["frame_scored"] = "frame_scored"
    frame_id: str
    quality: QualityScore
    thumb_url: str


class Segmented(_EventBase):
    """A frame was segmented."""

    type: Literal["segmented"] = "segmented"
    frame_id: str
    backend: SegBackend
    cover: dict[SegClass, float]
    mask_url: str


class Assessed(_EventBase):
    """The vision model assessed a frame."""

    type: Literal["assessed"] = "assessed"
    assessment: FrameAssessment


class Disagreement(_EventBase):
    """Teacher and student segmentations disagreed; sam3 won."""

    type: Literal["disagreement"] = "disagreement"
    frame_id: str
    iou: float
    chosen: Literal["sam3"]


class ToolCalled(_EventBase):
    """The agent called a context tool."""

    type: Literal["tool_called"] = "tool_called"
    call_id: str
    tool: str
    params: dict[str, Any]


class ToolReturned(_EventBase):
    """A context tool returned a result."""

    type: Literal["tool_returned"] = "tool_returned"
    call_id: str
    tool_result_id: str
    summary: str


class FindingEvent(_EventBase):
    """The agent recorded a cited finding.

    Named ``FindingEvent`` because ``Finding`` is the §4.2 schema name.
    """

    type: Literal["finding"] = "finding"
    finding: Finding


class ReportReady(_EventBase):
    """The investigation is ready to read."""

    type: Literal["report_ready"] = "report_ready"
    investigation_id: str


class SurveyFailed(_EventBase):
    """The pipeline gave up on a survey."""

    type: Literal["survey_failed"] = "survey_failed"
    reason: str


# The contract spells the alias with ``TypeAlias``; keep that form (rather than a
# PEP 695 ``type`` statement) so pyright and pydantic see exactly the shape the
# architecture documents.
Event: TypeAlias = Annotated[  # noqa: UP040
    (
        SurveyStarted
        | FramesExtracted
        | FrameScored
        | Segmented
        | Assessed
        | Disagreement
        | ToolCalled
        | ToolReturned
        | FindingEvent
        | ReportReady
        | SurveyFailed
    ),
    Field(discriminator="type"),
]

EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)
