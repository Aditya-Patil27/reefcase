"""Tests for POST /api/surveys/{survey_id}/ask endpoint (Story 8.6, §6.3)."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import reefcase.api.routes.surveys as surveys_route
from reefcase.api.main import create_app
from reefcase.core.events import ToolReturned
from reefcase.core.schemas import (
    Cause,
    EvidenceRef,
    Finding,
    Frame,
    FrameAssessment,
    Hypothesis,
    Investigation,
    QualityScore,
    SegClass,
    Segmentation,
    Survey,
    SurveyStatus,
    ToolResult,
)


def _now() -> datetime:
    return datetime.now(UTC)


def build_app(make_settings, tmp_path: Path):
    settings = make_settings(data_dir=str(tmp_path / "var"), segmenter="fake")
    return create_app(settings)


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_ask_404_when_survey_unknown(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        resp = await client.post(
            "/api/surveys/srv_nonexistent/ask",
            json={"question": "Why not heat stress?"},
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ask_409_when_survey_has_no_investigation_yet(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    store = app.state.store
    survey = Survey(
        id="srv_no_inv",
        site_id="site_test",
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.RUNNING,
        source="upload",
        created_at=_now(),
    )
    await store.surveys.save(survey)

    async with client_for(app) as client:
        resp = await client.post(
            f"/api/surveys/{survey.id}/ask",
            json={"question": "Why not heat stress?"},
        )
    assert resp.status_code == 409
    assert "no investigation" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ask_422_when_question_empty_or_whitespace(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        # Empty string
        resp1 = await client.post(
            "/api/surveys/srv_any/ask",
            json={"question": ""},
        )
        assert resp1.status_code == 422

        # Pure whitespace (must fail after stripping)
        resp2 = await client.post(
            "/api/surveys/srv_any/ask",
            json={"question": "   \n\t  "},
        )
        assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_ask_422_when_question_over_500_characters(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        resp = await client.post(
            "/api/surveys/srv_any/ask",
            json={"question": "a" * 501},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_200_with_fake_model(
    make_settings, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = build_app(make_settings, tmp_path)
    store = app.state.store

    survey = Survey(
        id="srv_ask_ok",
        site_id="site_test",
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.DONE,
        source="upload",
        created_at=_now(),
    )
    await store.surveys.save(survey)

    frame = Frame(
        id="frm_ask_ok_1",
        survey_id=survey.id,
        t_sec=1.5,
        image_path="test.jpg",
        quality=QualityScore(blur=100.0, color_cast=2.0, turbidity=0.1, passed=True),
    )
    await store.frames.save(frame)

    seg = Segmentation(
        id="seg_ask_ok_1",
        frame_id=frame.id,
        backend="fake",
        mask_path="mask.png",
        cover={SegClass.LIVE_CORAL: 0.3, SegClass.BLEACHED_CORAL: 0.4},
        latency_ms=10,
    )
    await store.segmentations.save(seg)

    asm = FrameAssessment(
        id="asm_ask_ok_1",
        frame_id=frame.id,
        model="spark-teacher",
        bleaching_severity=3,
        morphology=["branching"],
        damage=["none"],
        notes="High bleaching on slope.",
    )
    await store.assessments.save(asm)

    tr = ToolResult(
        id="tr_heat_ok_1",
        tool="heat_stress",
        params={"site_id": "site_test"},
        data={"max_dhw": 8.5},
        source_url="https://example.test",
        retrieved_at=_now(),
    )
    await store.tool_results.save(tr, "key_tr_1")

    # Add tool_returned event for this survey
    ev = ToolReturned(
        survey_id=survey.id,
        seq=1,
        ts=_now(),
        call_id="c_1",
        tool_result_id=tr.id,
        summary="heat stress peak 8.5",
    )
    await store.events.append(ev)

    investigation = Investigation(
        id="inv_ask_ok_1",
        survey_id=survey.id,
        findings=[
            Finding(
                statement="Severe bleaching observed.",
                evidence=[EvidenceRef(kind="frame", id=frame.id)],
            )
        ],
        hypotheses=[
            Hypothesis(
                cause=Cause.HEAT_STRESS,
                confidence=0.88,
                supporting=[EvidenceRef(kind="tool_result", id=tr.id)],
                contradicting=[],
                rationale="DHW exceeded 8.",
            )
        ],
        verdict="Heat stress caused severe bleaching.",
        actions=["Follow-up survey."],
        uncertain_frames=[],
        model="Muse Spark Open",
    )
    await store.investigations.save(investigation)

    def fake_build_model(role: str, _settings: Any) -> FunctionModel:
        def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            draft = {
                "answer": "Heat stress was the primary factor due to 8.5 DHW.",
                "citations": [
                    {"kind": "tool_result", "id": tr.id},
                    {"kind": "frame", "id": frame.id},
                ],
            }
            return ModelResponse(
                parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=draft)]
            )

        return FunctionModel(respond, model_name="fake-ask-model")

    monkeypatch.setattr(surveys_route, "build_model", fake_build_model)

    async with client_for(app) as client:
        resp = await client.post(
            f"/api/surveys/{survey.id}/ask",
            json={"question": "Why not heat stress?"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "Heat stress was the primary factor" in data["answer"]
    assert len(data["citations"]) == 2
    assert data["citations"][0]["id"] == tr.id
    assert data["citations"][1]["id"] == frame.id
