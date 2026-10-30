"""Story 5.2 — Investigator agent (architecture §5.5, §4.3, §5.4)."""

from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from reefcase.agent.investigator import INVESTIGATOR_PROMPT, InvestigationDraft, investigate
from reefcase.core.events import Event, ToolCalled, ToolReturned
from reefcase.core.schemas import (
    Cause,
    Frame,
    FrameAssessment,
    GeoPoint,
    Investigation,
    QualityScore,
    SegClass,
    Segmentation,
    Site,
    Survey,
    SurveyStatus,
    ToolResult,
)
from reefcase.pipeline.bus import EventBus
from reefcase.store.db import Store
from reefcase.tools.heat_stress import HeatStressParams
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import canonical_params
from reefcase.tools.vessels import VesselActivityParams

SITE_ID = "site_test_inv"
SURVEY_ID = "srv_test_inv_01"
HEAT_ARGS = {"site_id": SITE_ID, "start": "2026-07-27", "end": "2026-10-25"}
VESSEL_ARGS = {"site_id": SITE_ID, "radius_km": 10.0, "start": "2026-09-25", "end": "2026-10-25"}
COVER = {
    SegClass.LIVE_CORAL: 0.3,
    SegClass.BLEACHED_CORAL: 0.35,
    SegClass.ALGAE: 0.1,
    SegClass.RUBBLE: 0.1,
    SegClass.SAND: 0.1,
    SegClass.OTHER: 0.05,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _survey() -> Survey:
    return Survey(
        id=SURVEY_ID,
        site_id=SITE_ID,
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.RUNNING,
        source="upload",
        created_at=_now(),
    )


def _frames() -> list[Frame]:
    quality = QualityScore(blur=150.0, color_cast=10.0, turbidity=0.5, passed=True)
    return [
        Frame(
            id=f"frm_inv_{i}",
            survey_id=SURVEY_ID,
            t_sec=1.0 + i,
            image_path="x.jpg",
            quality=quality,
        )
        for i in range(2)
    ]


def _segs(frames: list[Frame]) -> list[Segmentation]:
    return [
        Segmentation(
            id=f"seg_{f.id}",
            frame_id=f.id,
            backend="fake",
            mask_path="m.png",
            cover=COVER,
            latency_ms=5,
        )
        for f in frames
    ]


def _assessments(frames: list[Frame]) -> list[FrameAssessment]:
    return [
        FrameAssessment(
            id=f"asm_{f.id}",
            frame_id=f.id,
            model="spark-teacher",
            bleaching_severity=3,
            morphology=["branching"],
            damage=["none"],
            notes="Widespread paling on branching colonies.",
        )
        for f in frames
    ]


def _draft(frame_id: str, tr_ids: list[str]) -> dict[str, Any]:
    def _ref(ref_id: str) -> dict[str, str]:
        kind = "frame" if ref_id.startswith("frm_") else "tool_result"
        return {"kind": kind, "id": ref_id}

    return {
        "findings": [
            {
                "statement": "Over a third of the reef is bleached.",
                "evidence": [{"kind": "frame", "id": frame_id}],
            }
        ],
        "hypotheses": [
            {
                "cause": "heat_stress",
                "confidence": 0.8,
                "supporting": [_ref(tr_ids[0])],
                "contradicting": [],
                "rationale": "Degree heating weeks peaked above 8.",
            },
            {
                "cause": "fishing_pressure",
                "confidence": 0.1,
                "supporting": [_ref(tr_ids[1])],
                "contradicting": [],
                "rationale": "Little vessel activity nearby.",
            },
        ],
        "verdict": "Heat-driven bleaching.",
        "actions": ["Resurvey in 6 weeks."],
        "uncertain_frames": [],
    }


async def _seed(store: Store) -> tuple[ToolResult, ToolResult]:
    """Cache one heat and one vessel result, so ``registry.call`` makes no HTTP call."""
    await store.sites.save(
        Site(
            id=SITE_ID,
            name="Test Reef",
            location=GeoPoint(lat=19.64, lon=-155.99),
            created_at=_now(),
        )
    )
    heat_params = HeatStressParams.model_validate(HEAT_ARGS)
    vessel_params = VesselActivityParams.model_validate(VESSEL_ARGS)
    heat = ToolResult(
        id="tr_heat",
        tool="heat_stress",
        params=heat_params.model_dump(mode="json"),
        data={"available": True, "max_dhw": 8.4},
        source_url="https://example.test/erddap",
        retrieved_at=_now(),
    )
    vessel = ToolResult(
        id="tr_vessel",
        tool="vessel_activity",
        params=vessel_params.model_dump(mode="json"),
        data={"fishing_hours": 0.0},
        source_url="https://example.test/gfw",
        retrieved_at=_now(),
    )
    await store.tool_results.save(heat, canonical_params(heat_params))
    await store.tool_results.save(vessel, canonical_params(vessel_params))
    return heat, vessel


def _offline_client() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected HTTP call: {request.url}")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ctx(store: Store, make_settings: Any) -> ToolContext:
    return ToolContext(http=_offline_client(), store=store, settings=make_settings())


def _scripted(
    steps: list[ModelResponse], seen: list[tuple[list[ModelMessage], AgentInfo]]
) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append((messages, info))
        step = steps[len(seen) - 1]
        return ModelResponse(
            parts=[
                ToolCallPart(tool_name=info.output_tools[0].name, args=part.args)
                if isinstance(part, ToolCallPart) and part.tool_name == "final_result"
                else part
                for part in step.parts
            ]
        )

    return FunctionModel(respond, model_name="spark-agent")


def _call(tool: str, args: dict[str, Any], call_id: str) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=tool, args=args, tool_call_id=call_id)])


def _final(draft: dict[str, Any]) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name="final_result", args=draft)])


async def _run(
    store: Store, make_settings: Any, steps: list[ModelResponse]
) -> tuple[Investigation, list[Event], list[tuple[list[ModelMessage], AgentInfo]]]:
    frames = _frames()
    emitted: list[Event] = []
    bus = EventBus(store)

    async def emit(event: Event) -> None:
        emitted.append(event)
        await bus.publish(event)

    seen: list[tuple[list[ModelMessage], AgentInfo]] = []
    investigation = await investigate(
        _survey(),
        frames,
        _segs(frames),
        _assessments(frames),
        _ctx(store, make_settings),
        emit,
        model=_scripted(steps, seen),
    )
    return investigation, emitted, seen


def _tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    return [
        part
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]


def test_draft_is_investigation_minus_ids_and_model() -> None:
    assert set(InvestigationDraft.model_fields) == set(Investigation.model_fields) - {
        "id",
        "survey_id",
        "model",
    }


@pytest.mark.asyncio
async def test_heat_then_vessels_emits_ordered_events_and_returns_investigation(
    store: Store, make_settings: Any
) -> None:
    heat, vessel = await _seed(store)
    steps = [
        _call("heat_stress", HEAT_ARGS, "call_heat"),
        _call("vessel_activity", VESSEL_ARGS, "call_vessel"),
        _final(_draft("frm_inv_0", [heat.id, vessel.id])),
    ]

    investigation, emitted, seen = await _run(store, make_settings, steps)

    assert [
        (type(e).__name__, e.call_id) for e in emitted if isinstance(e, ToolCalled | ToolReturned)
    ] == [
        ("ToolCalled", "call_heat"),
        ("ToolReturned", "call_heat"),
        ("ToolCalled", "call_vessel"),
        ("ToolReturned", "call_vessel"),
    ]
    called = [e for e in emitted if isinstance(e, ToolCalled)]
    returned = [e for e in emitted if isinstance(e, ToolReturned)]
    assert [(e.tool, e.params) for e in called] == [
        ("heat_stress", HEAT_ARGS),
        ("vessel_activity", VESSEL_ARGS),
    ]
    assert [e.tool_result_id for e in returned] == ["tr_heat", "tr_vessel"]
    assert "8.4" in returned[0].summary
    seqs = [e.seq for e in emitted]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert [e.seq for e in await store.events.list(SURVEY_ID)] == seqs

    assert investigation.id.startswith("inv_")
    assert investigation.survey_id == SURVEY_ID
    assert investigation.model == "spark-agent"
    assert [h.cause for h in investigation.hypotheses] == [
        Cause.HEAT_STRESS,
        Cause.FISHING_PRESSURE,
    ]
    assert investigation.findings[0].evidence[0].id == "frm_inv_0"

    # The model saw the tr_ ids it has to cite.
    last_messages, info = seen[-1]
    assert [r.tool_call_id for r in _tool_returns(last_messages)] == ["call_heat", "call_vessel"]
    assert "tr_heat" in str(_tool_returns(last_messages)[0].content)
    assert {"heat_stress", "vessel_activity"} <= {t.name for t in info.function_tools}
    assert info.allow_text_output is False
    assert info.model_request_parameters.output_mode == "tool"


@pytest.mark.asyncio
async def test_prompts_carry_instructions_and_frame_evidence(
    store: Store, make_settings: Any
) -> None:
    await _seed(store)

    _, _, seen = await _run(
        store, make_settings, [_final(_draft("frm_inv_1", ["frm_inv_0", "frm_inv_1"]))]
    )

    request = seen[0][0][0]
    assert isinstance(request, ModelRequest)
    assert request.instructions is not None
    assert INVESTIGATOR_PROMPT.strip() in request.instructions
    prompt = next(part for part in request.parts if isinstance(part, UserPromptPart))
    text = str(prompt.content)
    for expected in (
        SURVEY_ID,
        SITE_ID,
        "2026-10-25",
        "frm_inv_0",
        "frm_inv_1",
        "bleached_coral: 35.0%",
    ):
        assert expected in text
    assert "bleaching 3/4" in text
    assert "Widespread paling" in text


def test_system_prompt_covers_causes_citations_and_vessel_names() -> None:
    text = INVESTIGATOR_PROMPT.lower()
    for cause in Cause:
        assert cause.value in text
    assert "tr_" in text
    assert "frame id" in text
    assert "never name" in text and "vessel" in text


@pytest.mark.asyncio
async def test_invalid_params_retry_without_events(store: Store, make_settings: Any) -> None:
    heat, _ = await _seed(store)
    bad = {**HEAT_ARGS, "end": "2026-01-01"}  # end before start
    steps = [
        _call("heat_stress", bad, "call_bad"),
        _call("heat_stress", HEAT_ARGS, "call_good"),
        _final(_draft("frm_inv_0", [heat.id, "frm_inv_1"])),
    ]

    _, emitted, seen = await _run(store, make_settings, steps)

    assert [e.call_id for e in emitted if isinstance(e, ToolCalled)] == ["call_good"]
    # pydantic-ai 2.62 hands a tool's ModelRetry back as a ToolReturnPart with the message.
    retry = _tool_returns(seen[1][0])[-1]
    assert retry.tool_call_id == "call_bad"
    assert "invalid heat_stress params" in str(retry.content)


@pytest.mark.asyncio
async def test_failed_tool_reports_error_to_model_and_keeps_going(
    store: Store, make_settings: Any
) -> None:
    await _seed(store)
    missing = {**HEAT_ARGS, "site_id": "site_missing"}  # NotFoundError before any HTTP
    steps = [
        _call("heat_stress", missing, "call_missing"),
        _final(_draft("frm_inv_0", ["frm_inv_0", "frm_inv_1"])),
    ]

    investigation, emitted, seen = await _run(store, make_settings, steps)

    returned = [e for e in emitted if isinstance(e, ToolReturned)]
    assert [(e.call_id, e.tool_result_id) for e in returned] == [("call_missing", "")]
    assert returned[0].summary.startswith("error:")
    tool_return = _tool_returns(seen[-1][0])[0]
    assert "error" in str(tool_return.content)
    assert investigation.survey_id == SURVEY_ID
