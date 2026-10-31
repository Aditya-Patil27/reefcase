"""Tests for the ask agent and citation validation (Story 8.6)."""

from datetime import UTC, date, datetime

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from reefcase.agent.ask import ask
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

SURVEY_ID = "srv_test_ask_01"
FRAME_ID = "frm_ask_01"
TR_ID = "tr_heat_ask"


def _now() -> datetime:
    return datetime.now(UTC)


def _survey() -> Survey:
    return Survey(
        id=SURVEY_ID,
        site_id="site_test",
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.DONE,
        source="upload",
        created_at=_now(),
    )


def _investigation() -> Investigation:
    return Investigation(
        id="inv_test_ask",
        survey_id=SURVEY_ID,
        findings=[
            Finding(
                statement="Severe bleaching observed across reef.",
                evidence=[EvidenceRef(kind="frame", id=FRAME_ID)],
            )
        ],
        hypotheses=[
            Hypothesis(
                cause=Cause.HEAT_STRESS,
                confidence=0.85,
                supporting=[EvidenceRef(kind="tool_result", id=TR_ID)],
                contradicting=[],
                rationale="Extreme degree heating weeks in summer.",
            )
        ],
        verdict="Bleaching driven primarily by thermal stress.",
        actions=["Conduct follow-up survey in 6 months."],
        uncertain_frames=[],
        model="Muse Spark Open",
    )


def _frame() -> Frame:
    return Frame(
        id=FRAME_ID,
        survey_id=SURVEY_ID,
        t_sec=2.5,
        image_path="test.jpg",
        quality=QualityScore(blur=120.0, color_cast=5.0, turbidity=0.4, passed=True),
    )


def _seg() -> Segmentation:
    return Segmentation(
        id=f"seg_{FRAME_ID}",
        frame_id=FRAME_ID,
        backend="fake",
        mask_path="mask.png",
        cover={
            SegClass.LIVE_CORAL: 0.25,
            SegClass.BLEACHED_CORAL: 0.40,
            SegClass.ALGAE: 0.10,
            SegClass.RUBBLE: 0.10,
            SegClass.SAND: 0.10,
            SegClass.OTHER: 0.05,
        },
        latency_ms=10,
    )


def _assessment() -> FrameAssessment:
    return FrameAssessment(
        id=f"asm_{FRAME_ID}",
        frame_id=FRAME_ID,
        model="spark-teacher",
        bleaching_severity=3,
        morphology=["branching"],
        damage=["none"],
        notes="High proportion of bleached colonies.",
    )


def _tool_result() -> ToolResult:
    return ToolResult(
        id=TR_ID,
        tool="heat_stress",
        params={"site_id": "site_test", "start": "2026-07-25", "end": "2026-10-25"},
        data={"max_dhw": 9.2, "alert_level": 2},
        source_url="https://example.test/crw",
        retrieved_at=_now(),
    )


@pytest.mark.asyncio
async def test_ask_valid_citations_pass_through() -> None:
    calls: list[tuple[list[ModelMessage], AgentInfo]] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append((messages, info))
        # Ensure agent has no function tools registered
        assert len(info.function_tools) == 0
        draft = {
            "answer": "Bleaching was driven by extreme marine heatwaves reaching level 2.",
            "citations": [
                {"kind": "frame", "id": FRAME_ID},
                {"kind": "tool_result", "id": TR_ID},
            ],
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=draft)])

    model = FunctionModel(respond, model_name="fake-ask")
    ans = await ask(
        "Why not heat stress?",
        _investigation(),
        [_frame()],
        [_seg()],
        [_assessment()],
        [_tool_result()],
        model=model,
    )

    assert len(calls) == 1
    assert "heatwaves" in ans.answer
    assert ans.citations == [
        EvidenceRef(kind="frame", id=FRAME_ID),
        EvidenceRef(kind="tool_result", id=TR_ID),
    ]


@pytest.mark.asyncio
async def test_ask_bad_citation_triggers_retry_then_succeeds() -> None:
    calls: list[tuple[list[ModelMessage], AgentInfo]] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append((messages, info))
        if len(calls) == 1:
            # First turn: bad citation ID
            draft = {
                "answer": "Bleaching occurred.",
                "citations": [{"kind": "frame", "id": "frm_invented"}],
            }
        else:
            # Second turn: repaired with valid frame ID
            draft = {
                "answer": "Bleaching occurred as seen in frame evidence.",
                "citations": [{"kind": "frame", "id": FRAME_ID}],
            }
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=draft)])

    model = FunctionModel(respond, model_name="fake-ask")
    ans = await ask(
        "What bleaching occurred?",
        _investigation(),
        [_frame()],
        [_seg()],
        [_assessment()],
        [_tool_result()],
        model=model,
    )

    assert len(calls) == 2
    # Verify the retry message prompted about the invalid ID
    retry_message = calls[1][0][-1]
    assert any(
        isinstance(part, ToolReturnPart) and "frm_invented" in str(part.content)
        for part in retry_message.parts
    )
    assert ans.citations == [EvidenceRef(kind="frame", id=FRAME_ID)]


@pytest.mark.asyncio
async def test_ask_second_bad_draft_drops_bad_ref() -> None:
    calls: list[tuple[list[ModelMessage], AgentInfo]] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append((messages, info))
        # Keep returning bad citation alongside good one
        draft = {
            "answer": "Heat stress was severe.",
            "citations": [
                {"kind": "tool_result", "id": TR_ID},
                {"kind": "tool_result", "id": "tr_invented_bad"},
            ],
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=draft)])

    model = FunctionModel(respond, model_name="fake-ask")
    ans = await ask(
        "Why heat stress?",
        _investigation(),
        [_frame()],
        [_seg()],
        [_assessment()],
        [_tool_result()],
        model=model,
    )

    # Exactly 1 retry happened (2 total calls), then the bad ref was dropped
    assert len(calls) == 2
    assert ans.citations == [EvidenceRef(kind="tool_result", id=TR_ID)]


@pytest.mark.asyncio
async def test_ask_agent_has_no_tools_and_includes_context() -> None:
    seen_prompt = ""

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal seen_prompt
        assert len(info.function_tools) == 0
        for m in messages:
            for p in m.parts:
                if isinstance(p, (UserPromptPart, SystemPromptPart, TextPart)) and isinstance(
                    p.content, str
                ):
                    seen_prompt += p.content
        draft = {
            "answer": "Thermal stress drove the decline.",
            "citations": [{"kind": "frame", "id": FRAME_ID}],
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=draft)])

    model = FunctionModel(respond, model_name="fake-ask")
    await ask(
        "Why did the reef decline?",
        _investigation(),
        [_frame()],
        [_seg()],
        [_assessment()],
        [_tool_result()],
        model=model,
    )

    # Check that prompt context includes investigation, frame line, and tool result
    assert "Bleaching driven primarily by thermal stress" in seen_prompt
    assert FRAME_ID in seen_prompt
    assert TR_ID in seen_prompt
    assert "Why did the reef decline?" in seen_prompt
