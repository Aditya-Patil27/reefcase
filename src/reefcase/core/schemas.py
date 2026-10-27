"""Domain schemas shared by API, pipeline, agent and web (architecture §4.2).

This module is the single source of truth for the contract: the API returns
these models, the pipeline writes them, and Story 6.1 generates TypeScript from
``model_json_schema()``. Field names, wire values and limits are frozen.
"""

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field

__all__ = [
    "MASK_INDEX",
    "Cause",
    "EvidenceRef",
    "Finding",
    "Frame",
    "FrameAssessment",
    "GeoPoint",
    "Hypothesis",
    "Investigation",
    "QualityScore",
    "SegBackend",
    "SegClass",
    "Segmentation",
    "Site",
    "Survey",
    "SurveyStatus",
    "ToolResult",
]


#: Which segmentation backend produced a mask. A plain alias, so pydantic inlines it.
SegBackend = Literal["sam3", "student", "fake"]


class SegClass(StrEnum):
    """Segmentation classes; the value is the JSON wire value."""

    LIVE_CORAL = "live_coral"
    BLEACHED_CORAL = "bleached_coral"
    ALGAE = "algae"
    RUBBLE = "rubble"
    SAND = "sand"
    OTHER = "other"


# Class index in segmentation masks. The legend lives in the contract, so it
# lives in code too: the model, the store and the web legend all read this.
MASK_INDEX: dict[SegClass, int] = {
    SegClass.OTHER: 0,
    SegClass.LIVE_CORAL: 1,
    SegClass.BLEACHED_CORAL: 2,
    SegClass.ALGAE: 3,
    SegClass.RUBBLE: 4,
    SegClass.SAND: 5,
}


class GeoPoint(BaseModel):
    """A WGS84 position."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Site(BaseModel):
    """A dive site."""

    id: str
    name: str
    location: GeoPoint
    mpa_id: str | None = None
    created_at: AwareDatetime


class SurveyStatus(StrEnum):
    """Lifecycle of a survey through the pipeline."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Survey(BaseModel):
    """One dive video and its pipeline state."""

    id: str
    site_id: str
    dive_date: date
    status: SurveyStatus
    source: Literal["upload", "bot", "historical"]
    video_path: str | None = None
    cover: dict[SegClass, float] | None = None
    failure_reason: str | None = None
    created_at: AwareDatetime


class QualityScore(BaseModel):
    """Whether a frame is usable, and why not."""

    blur: float
    color_cast: float
    turbidity: float
    passed: bool
    reason: str | None = None


class Frame(BaseModel):
    """One extracted frame."""

    id: str
    survey_id: str
    t_sec: float
    image_path: str
    quality: QualityScore


class Segmentation(BaseModel):
    """A segmentation mask for one frame."""

    id: str
    frame_id: str
    backend: SegBackend
    mask_path: str
    cover: dict[SegClass, float]
    latency_ms: int


class FrameAssessment(BaseModel):
    """The vision model's reading of one frame."""

    id: str
    frame_id: str
    model: str
    bleaching_severity: int = Field(ge=0, le=4)
    morphology: list[str]
    damage: list[Literal["broken", "overturned", "anchor_scar", "disease", "none"]]
    notes: str = Field(max_length=400)


class EvidenceRef(BaseModel):
    """A pointer to the frame or tool result that backs a claim."""

    kind: Literal["frame", "tool_result"]
    id: str


class ToolResult(BaseModel):
    """The output of one context tool call.

    ``params`` and ``data`` are free-form because they mirror the tool's own
    schema, so no ``extra="forbid"`` here.
    """

    id: str
    tool: str
    params: dict[str, Any]
    data: dict[str, Any]
    source_url: str
    retrieved_at: AwareDatetime


class Finding(BaseModel):
    """A cited statement about the survey."""

    statement: str
    evidence: list[EvidenceRef] = Field(min_length=1)


class Cause(StrEnum):
    """The causes the agent may hypothesise."""

    HEAT_STRESS = "heat_stress"
    PHYSICAL_DAMAGE = "physical_damage"
    FISHING_PRESSURE = "fishing_pressure"
    DISEASE = "disease"
    UNKNOWN = "unknown"


class Hypothesis(BaseModel):
    """A candidate cause with its supporting and contradicting evidence."""

    cause: Cause
    confidence: float = Field(ge=0, le=1)
    supporting: list[EvidenceRef] = Field(min_length=1)
    contradicting: list[EvidenceRef] = Field(default_factory=list[EvidenceRef])
    rationale: str


class Investigation(BaseModel):
    """The agent's final report for one survey."""

    id: str
    survey_id: str
    findings: list[Finding] = Field(min_length=1)
    hypotheses: list[Hypothesis] = Field(min_length=1)
    verdict: str
    actions: list[str]
    uncertain_frames: list[str]
    model: str
