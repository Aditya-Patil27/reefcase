"""Contract tests for ``reefcase.core.schemas`` (architecture §4.2).

Every model is built from valid data, round-tripped through JSON, and checked
against the limits the contract specifies. The instances below double as the
canonical examples the API and pipeline share.
"""

import json
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from reefcase.core.schemas import (
    MASK_INDEX,
    Cause,
    EvidenceRef,
    Finding,
    Frame,
    FrameAssessment,
    GeoPoint,
    Hypothesis,
    Investigation,
    QualityScore,
    SegClass,
    Segmentation,
    Site,
    Survey,
    SurveyStatus,
    ToolResult,
)

# A non-UTC offset so the round-trip proves offset handling, not just UTC.
IST = timezone(timedelta(hours=5, minutes=30))
CREATED_AT = datetime(2026, 10, 26, 9, 30, tzinfo=IST)

GEO_POINT = GeoPoint(lat=18.4655, lon=-66.1057)
SITE = Site(
    id="site_0001",
    name="La Parguera",
    location=GEO_POINT,
    mpa_id="mpa_0001",
    created_at=CREATED_AT,
)
SURVEY = Survey(
    id="srv_0001",
    site_id="site_0001",
    dive_date=date(2026, 10, 25),
    status=SurveyStatus.DONE,
    source="upload",
    video_path="var/video.mp4",
    cover={SegClass.LIVE_CORAL: 0.42},
    failure_reason=None,
    created_at=CREATED_AT,
)
QUALITY = QualityScore(blur=0.12, color_cast=0.03, turbidity=0.21, passed=True, reason=None)
FRAME = Frame(
    id="frm_0001",
    survey_id="srv_0001",
    t_sec=12.5,
    image_path="frames/frm_0001.jpg",
    quality=QUALITY,
)
SEGMENTATION = Segmentation(
    id="seg_0001",
    frame_id="frm_0001",
    backend="sam3",
    mask_path="masks/seg_0001.png",
    cover={SegClass.LIVE_CORAL: 0.5, SegClass.SAND: 0.5},
    latency_ms=812,
)
FRAME_ASSESSMENT = FrameAssessment(
    id="asm_0001",
    frame_id="frm_0001",
    model="muse-spark-open",
    bleaching_severity=2,
    morphology=["branching"],
    damage=["none"],
    notes="Pale colony centre, no mortality.",
)
EVIDENCE = EvidenceRef(kind="frame", id="frm_0001")
TOOL_RESULT = ToolResult(
    id="tr_0001",
    tool="heat_stress",
    params={"site_id": "site_0001"},
    data={"dhw": 1.4},
    source_url="https://example.test/heat",
    retrieved_at=datetime(2026, 10, 26, 12, 0, tzinfo=UTC),
)
FINDING = Finding(statement="Live coral cover fell to 42%.", evidence=[EVIDENCE])
HYPOTHESIS = Hypothesis(
    cause=Cause.HEAT_STRESS,
    confidence=0.72,
    supporting=[EVIDENCE],
    contradicting=[],
    rationale="Elevated DHW precedes the paling.",
)
INVESTIGATION = Investigation(
    id="inv_0001",
    survey_id="srv_0001",
    findings=[FINDING],
    hypotheses=[HYPOTHESIS],
    verdict="Heat stress is the leading cause.",
    actions=["Re-survey in 3 months."],
    uncertain_frames=["frm_0002"],
    model="muse-spark-open",
)

ALL_MODELS = [
    GEO_POINT,
    SITE,
    SURVEY,
    QUALITY,
    FRAME,
    SEGMENTATION,
    FRAME_ASSESSMENT,
    EVIDENCE,
    TOOL_RESULT,
    FINDING,
    HYPOTHESIS,
    INVESTIGATION,
]

FRAME_ASSESSMENT_KWARGS: dict[str, Any] = {
    "id": "asm_0001",
    "frame_id": "frm_0001",
    "model": "muse-spark-open",
    "bleaching_severity": 2,
    "morphology": ["branching"],
    "damage": ["none"],
    "notes": "Pale colony centre, no mortality.",
}

# Field names from architecture §4.2, as JSON Schema property sets.
CONTRACT_PROPERTIES: dict[str, list[str]] = {
    "GeoPoint": ["lat", "lon"],
    "Site": ["created_at", "id", "location", "mpa_id", "name"],
    "Finding": ["evidence", "statement"],
    "Hypothesis": ["cause", "confidence", "contradicting", "rationale", "supporting"],
    "EvidenceRef": ["id", "kind"],
    "Investigation": [
        "actions",
        "findings",
        "hypotheses",
        "id",
        "model",
        "survey_id",
        "uncertain_frames",
        "verdict",
    ],
}


def test_seg_class_values_and_mask_order() -> None:
    assert {member.name: member.value for member in SegClass} == {
        "LIVE_CORAL": "live_coral",
        "BLEACHED_CORAL": "bleached_coral",
        "ALGAE": "algae",
        "RUBBLE": "rubble",
        "SAND": "sand",
        "OTHER": "other",
    }
    assert MASK_INDEX == {
        SegClass.OTHER: 0,
        SegClass.LIVE_CORAL: 1,
        SegClass.BLEACHED_CORAL: 2,
        SegClass.ALGAE: 3,
        SegClass.RUBBLE: 4,
        SegClass.SAND: 5,
    }


def test_survey_status_values() -> None:
    assert [member.value for member in SurveyStatus] == ["queued", "running", "done", "failed"]


def test_cause_values() -> None:
    assert [member.value for member in Cause] == [
        "heat_stress",
        "physical_damage",
        "fishing_pressure",
        "disease",
        "unknown",
    ]


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda model: type(model).__name__)
def test_every_schema_round_trips(model: Any) -> None:
    raw = model.model_dump_json()

    assert isinstance(raw, str)  # JSON mode, not a Python-mode dump
    assert isinstance(json.loads(raw), dict)
    assert type(model).model_validate_json(raw) == model


def test_cover_keys_round_trip_as_enum_members() -> None:
    raw = SEGMENTATION.model_dump_json()

    assert json.loads(raw)["cover"] == {"live_coral": 0.5, "sand": 0.5}

    parsed = Segmentation.model_validate_json(raw)
    assert parsed == SEGMENTATION
    assert {key.name for key in parsed.cover} == {"LIVE_CORAL", "SAND"}
    assert all(isinstance(key, SegClass) for key in parsed.cover)


@pytest.mark.parametrize(
    "kwargs",
    [{"lat": 91.0, "lon": 0.0}, {"lat": 0.0, "lon": -181.0}],
    ids=["lat-too-high", "lon-too-low"],
)
def test_geopoint_rejects_out_of_range(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        GeoPoint(**kwargs)


@pytest.mark.parametrize(
    "overrides",
    [
        {"bleaching_severity": 5},
        {"notes": "x" * 401},
        {"damage": ["nonsense"]},
    ],
    ids=["severity-too-high", "notes-too-long", "unknown-damage"],
)
def test_frame_assessment_limits(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        FrameAssessment(**{**FRAME_ASSESSMENT_KWARGS, **overrides})

    accepted = FrameAssessment(**{**FRAME_ASSESSMENT_KWARGS, "notes": "x" * 400})
    assert len(accepted.notes) == 400


def test_finding_requires_evidence() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Finding(statement="Coral cover fell.", evidence=[])

    assert "evidence" in excinfo.value.errors()[0]["loc"]


def test_hypothesis_requires_supporting() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Hypothesis(
            cause=Cause.UNKNOWN,
            confidence=0.5,
            supporting=[],
            contradicting=[],
            rationale="No evidence either way.",
        )

    assert "supporting" in excinfo.value.errors()[0]["loc"]


@pytest.mark.parametrize("confidence", [1.01, -0.01])
def test_hypothesis_confidence_bounds(confidence: float) -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            cause=Cause.HEAT_STRESS,
            confidence=confidence,
            supporting=[EVIDENCE],
            contradicting=[],
            rationale="Out of range.",
        )


@pytest.mark.parametrize("field", ["findings", "hypotheses"])
def test_investigation_requires_findings_and_hypotheses(field: str) -> None:
    kwargs: dict[str, Any] = {
        "id": "inv_0001",
        "survey_id": "srv_0001",
        "findings": [FINDING],
        "hypotheses": [HYPOTHESIS],
        "verdict": "Heat stress is the leading cause.",
        "actions": [],
        "uncertain_frames": [],
        "model": "muse-spark-open",
    }

    with pytest.raises(ValidationError):
        Investigation(**{**kwargs, field: []})


def test_none_fields_default() -> None:
    site = Site(id="site_0001", name="La Parguera", location=GEO_POINT, created_at=CREATED_AT)
    survey = Survey(
        id="srv_0001",
        site_id="site_0001",
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.QUEUED,
        source="bot",
        created_at=CREATED_AT,
    )
    quality = QualityScore(blur=0.0, color_cast=0.0, turbidity=0.0, passed=False)
    hypothesis = Hypothesis(
        cause=Cause.UNKNOWN,
        confidence=0.0,
        supporting=[EVIDENCE],
        rationale="Uncertain.",
    )

    assert site.mpa_id is None
    assert survey.video_path is None
    assert survey.cover is None
    assert survey.failure_reason is None
    assert quality.reason is None
    assert hypothesis.contradicting == []


def test_model_json_schema_is_stable() -> None:
    expected_defs = {
        "Site": {"GeoPoint"},
        "Investigation": {"Finding", "Hypothesis", "EvidenceRef"},
    }

    for model in (Site, Investigation):
        schema = model.model_json_schema()
        json.dumps(schema)  # Story 6.1 generates TypeScript from this

        found = {model.__name__: sorted(schema["properties"])}
        for definition in schema.get("$defs", {}).values():
            if "properties" in definition:
                found[definition["title"]] = sorted(definition["properties"])

        assert set(found) - {model.__name__} == expected_defs[model.__name__]
        for title, properties in found.items():
            assert properties == CONTRACT_PROPERTIES[title]
