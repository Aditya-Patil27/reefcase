"""Tests for /investigation and /frames endpoints (Story 5.4, §6.3)."""

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from reefcase.api.main import create_app
from reefcase.core.schemas import (
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
)


def _now() -> datetime:
    return datetime.now(UTC)


def build_app(make_settings, tmp_path: Path):
    settings = make_settings(data_dir=str(tmp_path / "var"), segmenter="fake")
    return create_app(settings)


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_investigation_404_when_survey_unknown(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        resp = await client.get("/api/surveys/srv_unknown/investigation")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_investigation_404_when_not_ready(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    store = app.state.store
    survey = Survey(
        id="srv_pending",
        site_id="site_test",
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.RUNNING,
        source="upload",
        created_at=_now(),
    )
    await store.surveys.save(survey)

    async with client_for(app) as client:
        resp = await client.get(f"/api/surveys/{survey.id}/investigation")
    assert resp.status_code == 404
    assert "Not ready yet" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_investigation_returns_stored_investigation(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    store = app.state.store
    survey = Survey(
        id="srv_ready",
        site_id="site_test",
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.DONE,
        source="upload",
        created_at=_now(),
    )
    await store.surveys.save(survey)

    investigation = Investigation(
        id="inv_test_01",
        survey_id=survey.id,
        findings=[
            Finding(
                statement="Severe bleaching observed.",
                evidence=[EvidenceRef(kind="frame", id="frm_01")],
            )
        ],
        hypotheses=[
            Hypothesis(
                cause=Cause.HEAT_STRESS,
                confidence=0.9,
                supporting=[EvidenceRef(kind="tool_result", id="tr_heat_01")],
                contradicting=[],
                rationale="DHW exceeded 8.",
            )
        ],
        verdict="Heat-induced thermal bleaching.",
        actions=["Schedule follow-up survey in 4 weeks."],
        uncertain_frames=[],
        model="spark-agent",
    )
    await store.investigations.save(investigation)

    async with client_for(app) as client:
        resp = await client.get(f"/api/surveys/{survey.id}/investigation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "inv_test_01"
    assert data["survey_id"] == survey.id
    assert len(data["findings"]) == 1
    assert data["findings"][0]["statement"] == "Severe bleaching observed."
    assert data["verdict"] == "Heat-induced thermal bleaching."


@pytest.mark.asyncio
async def test_get_frames_404_when_survey_unknown(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        resp = await client.get("/api/surveys/srv_unknown/frames")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_frames_returns_frame_details(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    store = app.state.store
    site = Site(
        id="site_test",
        name="Test Reef",
        location=GeoPoint(lat=-16.5, lon=145.5),
        created_at=_now(),
    )
    await store.sites.save(site)
    survey = Survey(
        id="srv_frames_test",
        site_id=site.id,
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.DONE,
        source="upload",
        created_at=_now(),
    )
    await store.surveys.save(survey)

    q = QualityScore(blur=120.0, color_cast=5.0, turbidity=0.2, passed=True)
    frame1 = Frame(
        id="frm_01",
        survey_id=survey.id,
        t_sec=1.0,
        image_path="blobs/srv_frames_test/frames/frm_01.jpg",
        quality=q,
    )
    frame2 = Frame(
        id="frm_02",
        survey_id=survey.id,
        t_sec=2.0,
        image_path="blobs/srv_frames_test/frames/frm_02.jpg",
        quality=q,
    )
    await store.frames.save(frame1)
    await store.frames.save(frame2)

    cover = {
        SegClass.LIVE_CORAL: 0.5,
        SegClass.BLEACHED_CORAL: 0.1,
        SegClass.ALGAE: 0.1,
        SegClass.RUBBLE: 0.1,
        SegClass.SAND: 0.1,
        SegClass.OTHER: 0.1,
    }
    seg1 = Segmentation(
        id="seg_01",
        frame_id=frame1.id,
        backend="fake",
        mask_path="blobs/srv_frames_test/masks/frm_01.png",
        cover=cover,
        latency_ms=10,
    )
    await store.segmentations.save(seg1)

    assessment1 = FrameAssessment(
        id="asm_01",
        frame_id=frame1.id,
        model="spark-teacher",
        bleaching_severity=2,
        morphology=["branching"],
        damage=["broken"],
        notes="Moderate bleaching.",
    )
    await store.assessments.save(assessment1)

    async with client_for(app) as client:
        resp = await client.get(f"/api/surveys/{survey.id}/frames")
    assert resp.status_code == 200
    details = resp.json()
    assert len(details) == 2

    # frame 1 has both segmentation and assessment
    d1 = details[0]
    assert d1["frame"]["id"] == "frm_01"
    assert d1["segmentation"] is not None
    assert d1["segmentation"]["id"] == "seg_01"
    assert d1["assessment"] is not None
    assert d1["assessment"]["id"] == "asm_01"
    assert d1["assessment"]["bleaching_severity"] == 2

    # frame 2 has neither
    d2 = details[1]
    assert d2["frame"]["id"] == "frm_02"
    assert d2["segmentation"] is None
    assert d2["assessment"] is None
