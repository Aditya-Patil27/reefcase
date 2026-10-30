"""Story 5.1 — Frame assessor (architecture §5.2, §5.3, §6.1)."""

import asyncio
import io
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import (
    BinaryContent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

import reefcase.pipeline.stages as stages_module
from reefcase.core.config import Settings
from reefcase.core.events import Assessed
from reefcase.core.schemas import (
    Frame,
    FrameAssessment,
    GeoPoint,
    QualityScore,
    SegClass,
    Segmentation,
    Site,
    Survey,
    SurveyStatus,
)
from reefcase.llm.assess import AssessmentDraft, assess_frame
from reefcase.pipeline.runner import JobRunner
from reefcase.pipeline.stages import ASSESS_CONCURRENCY, assess_stage
from reefcase.store.db import Store

CLIP_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "clip_10s.mp4"
SURVEY_ID = "srv_test_assess_01"
VALID = {
    "bleaching_severity": 2,
    "morphology": ["branching", "massive"],
    "damage": ["broken"],
    "notes": "Pale branching colonies on the left; one broken table.",
}
COVER = {
    SegClass.LIVE_CORAL: 0.4,
    SegClass.BLEACHED_CORAL: 0.1,
    SegClass.ALGAE: 0.2,
    SegClass.RUBBLE: 0.1,
    SegClass.SAND: 0.15,
    SegClass.OTHER: 0.05,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.full((16, 16, 3), 90, dtype=np.uint8)).save(buf, format="JPEG")
    return buf.getvalue()


def _frame(frame_id: str = "frm_assess_01", t_sec: float = 0.5) -> Frame:
    return Frame(
        id=frame_id,
        survey_id=SURVEY_ID,
        t_sec=t_sec,
        image_path=f"blobs/{SURVEY_ID}/frames/{frame_id}.jpg",
        quality=QualityScore(blur=150.0, color_cast=10.0, turbidity=0.5, passed=True),
    )


def _seg(frame_id: str = "frm_assess_01") -> Segmentation:
    return Segmentation(
        id=f"seg_{frame_id}",
        frame_id=frame_id,
        backend="fake",
        mask_path=f"blobs/{SURVEY_ID}/masks/{frame_id}.png",
        cover=COVER,
        latency_ms=5,
    )


def _answer(info: AgentInfo, args: dict[str, Any]) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=args)])


def _valid_model(
    seen: list[tuple[list[ModelMessage], AgentInfo]] | None = None,
) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if seen is not None:
            seen.append((messages, info))
        return _answer(info, VALID)

    return FunctionModel(respond, model_name="spark-test")


def _invalid_model(calls: list[int]) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        return _answer(info, {**VALID, "bleaching_severity": 9})

    return FunctionModel(respond, model_name="spark-test")


async def _create_survey(store: Store, video_ref: str | None = None) -> None:
    site = Site(
        id="site_test_assess",
        name="Test Reef",
        location=GeoPoint(lat=-16.5, lon=145.5),
        created_at=_now(),
    )
    await store.sites.save(site)
    await store.surveys.save(
        Survey(
            id=SURVEY_ID,
            site_id=site.id,
            dive_date=date(2026, 10, 25),
            status=SurveyStatus.QUEUED,
            source="upload",
            video_path=video_ref,
            created_at=_now(),
        )
    )


async def _save_frames(store: Store, count: int) -> list[Frame]:
    frames: list[Frame] = []
    for i in range(count):
        frame_id = f"frm_assess_{i:02d}"
        store.blobs.save_frame(SURVEY_ID, frame_id, _jpeg())
        frame = _frame(frame_id, t_sec=0.5 * (i + 1))
        await store.frames.save(frame)
        await store.segmentations.save(_seg(frame_id))
        frames.append(frame)
    return frames


def test_draft_is_frame_assessment_minus_ids_and_model() -> None:
    assert set(AssessmentDraft.model_fields) == set(FrameAssessment.model_fields) - {
        "id",
        "frame_id",
        "model",
    }


@pytest.mark.asyncio
async def test_agent_uses_tool_call_output_not_native() -> None:
    seen: list[tuple[list[ModelMessage], AgentInfo]] = []
    await assess_frame(_valid_model(seen), _frame(), _jpeg(), _seg())

    _, info = seen[0]
    assert [tool.name for tool in info.output_tools]  # an output tool exists
    assert info.allow_text_output is False
    assert info.model_request_parameters.output_mode == "tool"


@pytest.mark.asyncio
async def test_assess_frame_sends_image_and_cover_and_fills_ids() -> None:
    seen: list[tuple[list[ModelMessage], AgentInfo]] = []
    image = _jpeg()

    assessment = await assess_frame(_valid_model(seen), _frame(), image, _seg())

    assert assessment.id.startswith("asm_")
    assert assessment.frame_id == "frm_assess_01"
    assert assessment.model == "spark-test"
    assert assessment.model_dump(include=set(VALID)) == VALID

    messages, _ = seen[0]
    request = messages[0]
    assert isinstance(request, ModelRequest)
    prompt = next(part for part in request.parts if isinstance(part, UserPromptPart))
    assert isinstance(prompt.content, list)
    images = [item for item in prompt.content if isinstance(item, BinaryContent)]
    assert len(images) == 1
    assert images[0].data == image
    assert images[0].media_type == "image/jpeg"
    text = " ".join(item for item in prompt.content if isinstance(item, str))
    assert "live_coral: 40.0%" in text
    assert "bleached_coral: 10.0%" in text


@pytest.mark.asyncio
async def test_two_invalid_outputs_raise_after_one_retry() -> None:
    calls: list[int] = []
    with pytest.raises(UnexpectedModelBehavior):
        await assess_frame(_invalid_model(calls), _frame(), _jpeg(), _seg())
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_assessment_repo_round_trip_orders_by_frame_time(store: Store) -> None:
    await _create_survey(store)
    frames = await _save_frames(store, 2)
    late = FrameAssessment(id="asm_b", frame_id=frames[1].id, model="m", **VALID)
    early = FrameAssessment(id="asm_a", frame_id=frames[0].id, model="m", **VALID)
    await store.assessments.save(late)
    await store.assessments.save(early)

    assert await store.assessments.list_by_survey(SURVEY_ID) == [early, late]
    assert await store.assessments.list_by_survey("srv_other") == []


@pytest.mark.asyncio
async def test_assess_stage_stores_and_emits_per_frame(store: Store) -> None:
    await _create_survey(store)
    frames = await _save_frames(store, 3)

    result = await assess_stage(store, SURVEY_ID, frames, model=_valid_model())

    stored = await store.assessments.list_by_survey(SURVEY_ID)
    assert [a.frame_id for a in stored] == [f.id for f in frames]
    assert result == stored
    events = [e for e in await store.events.list(SURVEY_ID) if isinstance(e, Assessed)]
    assert sorted(e.assessment.frame_id for e in events) == [f.id for f in frames]
    assert {e.assessment.id for e in events} == {a.id for a in stored}
    seqs = [e.seq for e in await store.events.list(SURVEY_ID)]
    assert len(seqs) == len(set(seqs))


@pytest.mark.asyncio
async def test_assess_stage_skips_a_frame_after_two_invalid_outputs(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    await _create_survey(store)
    frames = await _save_frames(store, 3)
    bad_frame = frames[1].id

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        request = messages[0]
        assert isinstance(request, ModelRequest)
        prompt = next(part for part in request.parts if isinstance(part, UserPromptPart))
        if bad_frame in str(prompt.content):
            return ModelResponse(parts=[TextPart("not a tool call")])
        return _answer(info, VALID)

    with caplog.at_level(logging.WARNING, logger="reefcase.pipeline.stages"):
        result = await assess_stage(
            store, SURVEY_ID, frames, model=FunctionModel(respond, model_name="spark-test")
        )

    assert [a.frame_id for a in result] == [frames[0].id, frames[2].id]
    assert [a.frame_id for a in await store.assessments.list_by_survey(SURVEY_ID)] == [
        frames[0].id,
        frames[2].id,
    ]
    assert any(bad_frame in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_assess_stage_runs_four_at_a_time(store: Store) -> None:
    await _create_survey(store)
    frames = await _save_frames(store, 24)
    in_flight = 0
    peak = 0

    async def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0)  # yield so the other in-flight calls overlap
        in_flight -= 1
        return _answer(info, VALID)

    result = await assess_stage(
        store, SURVEY_ID, frames, model=FunctionModel(respond, model_name="spark-test")
    )

    assert ASSESS_CONCURRENCY == 4
    assert peak == 4
    assert len(result) == 24


@pytest.mark.asyncio
async def test_run_stages_assesses_kept_frames_with_the_teacher(
    store: Store,
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(
        llm_teacher_base_url="https://teacher.example/v1",
        llm_teacher_api_key="sk-test",
        llm_teacher_model="spark-teacher",
    )
    monkeypatch.setattr(stages_module, "Settings", lambda: settings)
    roles: list[str] = []

    def fake_build_model(role: str, _settings: Settings) -> FunctionModel:
        roles.append(role)
        return _valid_model()

    monkeypatch.setattr(stages_module, "build_model", fake_build_model)
    await _create_survey(store, store.blobs.save_video(SURVEY_ID, CLIP_PATH.read_bytes()))

    assert await JobRunner(store, stages_module.run_stages).run_once() is True

    survey = await store.surveys.get(SURVEY_ID)
    assert survey.status is SurveyStatus.DONE, survey.failure_reason
    frames = await store.frames.list_by_survey(SURVEY_ID)
    assessed = await store.assessments.list_by_survey(SURVEY_ID)
    assert roles == ["teacher"]
    assert [a.frame_id for a in assessed] == [f.id for f in frames]


@pytest.mark.asyncio
async def test_run_stages_skips_assessment_without_a_teacher(
    store: Store,
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = make_settings()
    monkeypatch.setattr(stages_module, "Settings", lambda: settings)
    await _create_survey(store, store.blobs.save_video(SURVEY_ID, CLIP_PATH.read_bytes()))

    with caplog.at_level(logging.WARNING, logger="reefcase.pipeline.stages"):
        assert await JobRunner(store, stages_module.run_stages).run_once() is True

    survey = await store.surveys.get(SURVEY_ID)
    assert survey.status is SurveyStatus.DONE, survey.failure_reason
    assert await store.assessments.list_by_survey(SURVEY_ID) == []
    assert any("TEACHER" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_assess_stage_skips_a_frame_when_the_model_api_fails(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    await _create_survey(store)
    frames = await _save_frames(store, 3)
    bad_frame = frames[1].id

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        request = messages[0]
        assert isinstance(request, ModelRequest)
        prompt = next(part for part in request.parts if isinstance(part, UserPromptPart))
        if bad_frame in str(prompt.content):
            raise ModelHTTPError(status_code=503, model_name="spark-test")
        return _answer(info, VALID)

    with caplog.at_level(logging.WARNING, logger="reefcase.pipeline.stages"):
        result = await assess_stage(
            store, SURVEY_ID, frames, model=FunctionModel(respond, model_name="spark-test")
        )

    assert [a.frame_id for a in result] == [frames[0].id, frames[2].id]
    assert any(bad_frame in r.getMessage() and "503" in r.getMessage() for r in caplog.records)
