"""Contract tests for ``reefcase.core.events`` (architecture §4.3).

The events are a discriminated union on ``type``; every member carries
``survey_id``, a monotonic ``seq`` and an aware ``ts``.
"""

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from reefcase.core.events import (
    Assessed,
    Disagreement,
    EventAdapter,
    FindingEvent,
    FrameScored,
    FramesExtracted,
    ReportReady,
    Segmented,
    SurveyFailed,
    SurveyStarted,
    ToolCalled,
    ToolReturned,
)
from reefcase.core.schemas import EvidenceRef, Finding, FrameAssessment, QualityScore, SegClass

BASE: dict[str, Any] = {
    "survey_id": "srv_0001",
    "ts": datetime(2026, 10, 26, 12, 0, tzinfo=UTC),
}

QUALITY = QualityScore(blur=0.12, color_cast=0.03, turbidity=0.21, passed=True)
FRAME_ASSESSMENT = FrameAssessment(
    id="asm_0001",
    frame_id="frm_0001",
    model="muse-spark-open",
    bleaching_severity=2,
    morphology=["branching"],
    damage=["none"],
    notes="Pale colony centre, no mortality.",
)
EVIDENCE = EvidenceRef(kind="tool_result", id="tr_0001")

SURVEY_STARTED = SurveyStarted(seq=1, site_id="site_0001", **BASE)
FRAMES_EXTRACTED = FramesExtracted(seq=2, count=120, **BASE)
FRAME_SCORED = FrameScored(
    seq=3,
    frame_id="frm_0001",
    quality=QUALITY,
    thumb_url="/thumbs/frm_0001.jpg",
    **BASE,
)
SEGMENTED = Segmented(
    seq=4,
    frame_id="frm_0001",
    backend="sam3",
    cover={SegClass.LIVE_CORAL: 0.5, SegClass.SAND: 0.5},
    mask_url="/masks/seg_0001.png",
    **BASE,
)
ASSESSED = Assessed(seq=5, assessment=FRAME_ASSESSMENT, **BASE)
DISAGREEMENT = Disagreement(seq=6, frame_id="frm_0001", iou=0.42, chosen="sam3", **BASE)
TOOL_CALLED = ToolCalled(
    seq=7,
    call_id="call_0001",
    tool="heat_stress",
    params={"site_id": "site_0001"},
    **BASE,
)
TOOL_RETURNED = ToolReturned(
    seq=8,
    call_id="call_0001",
    tool_result_id="tr_0001",
    summary="DHW 1.4, alert level 1",
    **BASE,
)
FINDING_EVENT = FindingEvent(
    seq=9,
    finding=Finding(
        statement="Live coral cover fell to 42%.",
        evidence=[EvidenceRef(kind="frame", id="frm_0001")],
    ),
    **BASE,
)
REPORT_READY = ReportReady(seq=10, investigation_id="inv_0001", **BASE)
SURVEY_FAILED = SurveyFailed(seq=11, reason="video unreadable", **BASE)

EVENTS = [
    SURVEY_STARTED,
    FRAMES_EXTRACTED,
    FRAME_SCORED,
    SEGMENTED,
    ASSESSED,
    DISAGREEMENT,
    TOOL_CALLED,
    TOOL_RETURNED,
    FINDING_EVENT,
    REPORT_READY,
    SURVEY_FAILED,
]

EVENT_TAGS = {
    "survey_started",
    "frames_extracted",
    "frame_scored",
    "segmented",
    "assessed",
    "disagreement",
    "tool_called",
    "tool_returned",
    "finding",
    "report_ready",
    "survey_failed",
}

BASE_JSON: dict[str, Any] = {"survey_id": "srv_0001", "ts": "2026-10-26T12:00:00Z"}


@pytest.mark.parametrize("event", EVENTS, ids=lambda event: event.type)
def test_every_event_type_round_trips(event: Any) -> None:
    raw = EventAdapter.dump_json(event)

    parsed = EventAdapter.validate_json(raw)

    assert type(parsed) is type(event)
    assert parsed == event


def test_event_type_tags_are_unique_and_complete() -> None:
    schema = EventAdapter.json_schema()
    discriminator = schema["discriminator"]

    assert discriminator["propertyName"] == "type"
    assert set(discriminator["mapping"]) == EVENT_TAGS


def test_unknown_event_type_rejected() -> None:
    raw = json.dumps({**BASE_JSON, "seq": 1, "type": "not_an_event"})

    with pytest.raises(ValidationError) as excinfo:
        EventAdapter.validate_json(raw)

    assert excinfo.value.errors()[0]["type"] == "union_tag_invalid"


@pytest.mark.parametrize("field", ["survey_id", "seq", "ts"])
def test_common_fields_required(field: str) -> None:
    payload: dict[str, Any] = {
        **BASE_JSON,
        "seq": 1,
        "type": "survey_started",
        "site_id": "site_0001",
    }
    del payload[field]

    with pytest.raises(ValidationError):
        EventAdapter.validate_json(json.dumps(payload))


def test_seq_starts_at_one() -> None:
    with pytest.raises(ValidationError):
        SurveyStarted(site_id="site_0001", seq=0, **BASE)


def test_naive_timestamp_rejected() -> None:
    payload: dict[str, Any] = {
        "survey_id": "srv_0001",
        "seq": 1,
        "type": "survey_started",
        "site_id": "site_0001",
        "ts": datetime(2026, 10, 26),
    }

    with pytest.raises(ValidationError):
        EventAdapter.validate_python(payload)


def test_nested_schema_payloads() -> None:
    cases = [
        (ASSESSED, "assessment", FrameAssessment),
        (FINDING_EVENT, "finding", Finding),
        (FRAME_SCORED, "quality", QualityScore),
    ]

    for event, field, expected_type in cases:
        parsed = EventAdapter.validate_json(EventAdapter.dump_json(event))
        value = getattr(parsed, field)

        assert type(parsed) is type(event)
        assert isinstance(value, expected_type)
        assert value == getattr(event, field)


def test_event_json_schema_has_oneof_and_discriminator() -> None:
    schema = EventAdapter.json_schema()
    mapping = schema["discriminator"]["mapping"]

    assert len(schema["oneOf"]) == 11
    assert all(ref.startswith("#/$defs/") for ref in mapping.values())
    assert mapping["survey_started"] == "#/$defs/SurveyStarted"
    assert mapping["finding"] == "#/$defs/FindingEvent"
