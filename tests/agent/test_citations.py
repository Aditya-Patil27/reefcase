"""Story 5.3 — Citation validator and repair loop (architecture §5.5, §4.2).

Tests use ``FunctionModel``:
(a) unknown id → retry message names the statement, repaired draft accepted;
(b) model never repairs → ``Partial:`` verdict, only valid claims left, no exception.
"""

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
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from reefcase.agent.investigator import InvestigationDraft, investigate
from reefcase.core.events import Event
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
    ToolResult,
)
from reefcase.pipeline.bus import EventBus
from reefcase.store.db import Store
from reefcase.tools.heat_stress import HeatStressParams
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import canonical_params

SITE_ID = "site_cite_test"
SURVEY_ID = "srv_cite_test_01"
HEAT_ARGS = {"site_id": SITE_ID, "start": "2026-07-27", "end": "2026-10-25"}
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
            id=f"frm_cite_{i}",
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
            notes="Paling on branching colonies.",
        )
        for f in frames
    ]


async def _seed(store: Store) -> ToolResult:
    """Cache one heat result, so ``registry.call`` is a cache hit."""
    await store.sites.save(
        Site(
            id=SITE_ID,
            name="Test Reef",
            location=GeoPoint(lat=19.64, lon=-155.99),
            created_at=_now(),
        )
    )
    heat_params = HeatStressParams.model_validate(HEAT_ARGS)
    heat = ToolResult(
        id="tr_heat_cite",
        tool="heat_stress",
        params=heat_params.model_dump(mode="json"),
        data={"available": True, "max_dhw": 8.4},
        source_url="https://example.test/erddap",
        retrieved_at=_now(),
    )
    await store.tool_results.save(heat, canonical_params(heat_params))
    return heat


def _offline_client() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected HTTP call: {request.url}")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ctx(store: Store, make_settings: Any) -> ToolContext:
    return ToolContext(http=_offline_client(), store=store, settings=make_settings())


def _call(tool: str, args: dict[str, Any], call_id: str) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=tool, args=args, tool_call_id=call_id)])


def _final(draft: dict[str, Any]) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name="final_result", args=draft)])


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


# ---------- helpers for test readability ----------


def _good_draft(frame_id: str, tr_id: str) -> dict[str, Any]:
    """A fully-cited draft: one frame ref, one tool_result ref."""
    return {
        "findings": [
            {
                "statement": "Bleaching exceeds 30%.",
                "evidence": [{"kind": "frame", "id": frame_id}],
            }
        ],
        "hypotheses": [
            {
                "cause": "heat_stress",
                "confidence": 0.8,
                "supporting": [{"kind": "tool_result", "id": tr_id}],
                "contradicting": [],
                "rationale": "DHW peaked above 8.",
            }
        ],
        "verdict": "Heat-driven bleaching.",
        "actions": ["Resurvey in 6 weeks."],
        "uncertain_frames": [],
    }


def _bad_draft_unknown_finding(frame_id: str, tr_id: str) -> dict[str, Any]:
    """Draft with one finding citing an unknown id and one citing a valid id."""
    return {
        "findings": [
            {
                "statement": "Bleaching exceeds 30%.",
                "evidence": [{"kind": "frame", "id": frame_id}],
            },
            {
                "statement": "Fish populations have declined.",
                "evidence": [{"kind": "tool_result", "id": "tr_FAKE_ID"}],
            },
        ],
        "hypotheses": [
            {
                "cause": "heat_stress",
                "confidence": 0.8,
                "supporting": [{"kind": "tool_result", "id": tr_id}],
                "contradicting": [],
                "rationale": "DHW peaked above 8.",
            }
        ],
        "verdict": "Heat-driven bleaching.",
        "actions": ["Resurvey in 6 weeks."],
        "uncertain_frames": [],
    }


def _always_bad_draft() -> dict[str, Any]:
    """Every single ref is unknown — the model never repairs."""
    return {
        "findings": [
            {
                "statement": "Fish populations have declined.",
                "evidence": [{"kind": "tool_result", "id": "tr_INVENTED"}],
            },
            {
                "statement": "Anchor damage seen.",
                "evidence": [{"kind": "frame", "id": "frm_INVENTED"}],
            },
        ],
        "hypotheses": [
            {
                "cause": "fishing_pressure",
                "confidence": 0.5,
                "supporting": [{"kind": "tool_result", "id": "tr_ALSO_FAKE"}],
                "contradicting": [],
                "rationale": "Many vessels spotted.",
            }
        ],
        "verdict": "Fishing pressure is the main cause.",
        "actions": ["Report to coast guard."],
        "uncertain_frames": [],
    }


def _mixed_bad_draft(frame_id: str, tr_id: str) -> dict[str, Any]:
    """Some valid, some invalid — used for the partial fallback path."""
    return {
        "findings": [
            {
                "statement": "Bleaching exceeds 30%.",
                "evidence": [{"kind": "frame", "id": frame_id}],
            },
            {
                "statement": "Ghost nets observed.",
                "evidence": [{"kind": "tool_result", "id": "tr_GHOST"}],
            },
        ],
        "hypotheses": [
            {
                "cause": "heat_stress",
                "confidence": 0.8,
                "supporting": [{"kind": "tool_result", "id": tr_id}],
                "contradicting": [],
                "rationale": "DHW peaked above 8.",
            },
            {
                "cause": "fishing_pressure",
                "confidence": 0.3,
                "supporting": [{"kind": "tool_result", "id": "tr_GHOST"}],
                "contradicting": [],
                "rationale": "Ghost nets suggest trawling.",
            },
        ],
        "verdict": "Heat-driven bleaching with some fishing damage.",
        "actions": ["Resurvey in 6 weeks."],
        "uncertain_frames": [],
    }


# ────────────────── (a) unknown id -> retry, repaired draft accepted ──────────────────


@pytest.mark.asyncio
async def test_unknown_id_triggers_retry_then_repaired_draft_accepted(
    store: Store, make_settings: Any
) -> None:
    """First draft has an unknown tr_FAKE_ID; retry message names the statement;
    model returns a repaired draft on retry and it is accepted."""
    heat = await _seed(store)
    frame_id = "frm_cite_0"

    steps = [
        # 1. Model calls heat_stress
        _call("heat_stress", HEAT_ARGS, "call_h"),
        # 2. Model returns a draft with one bad finding
        _final(_bad_draft_unknown_finding(frame_id, heat.id)),
        # 3. After ModelRetry, model returns a good draft
        _final(_good_draft(frame_id, heat.id)),
    ]

    investigation, _emitted, seen = await _run(store, make_settings, steps)

    # The investigation completed (no exception).
    assert investigation.survey_id == SURVEY_ID
    assert investigation.verdict == "Heat-driven bleaching."
    assert not investigation.verdict.startswith("Partial:")
    # All findings are valid.
    assert len(investigation.findings) == 1
    assert investigation.findings[0].evidence[0].id == frame_id

    # The retry message referenced the offending statement.
    last_messages = seen[2][0]
    retry_parts = [
        part
        for msg in last_messages
        if isinstance(msg, ModelRequest)
        for part in msg.parts
        if isinstance(part, ToolReturnPart)
    ]
    retry_text = " ".join(str(p.content) for p in retry_parts)
    assert "Fish populations have declined" in retry_text


# ────────── (b) model never repairs -> Partial: verdict, only valid claims ──────────


@pytest.mark.asyncio
async def test_exhausted_retries_produces_partial_verdict_with_valid_claims_only(
    store: Store, make_settings: Any
) -> None:
    """Model returns bad citations every time; after retry exhaustion the validator
    drops uncited findings, prefixes verdict with 'Partial:', and no exception is raised."""
    heat = await _seed(store)
    frame_id = "frm_cite_0"

    mixed = _mixed_bad_draft(frame_id, heat.id)
    steps = [
        _call("heat_stress", HEAT_ARGS, "call_h"),
        _final(mixed),  # attempt 0: has bad refs -> ModelRetry
        _final(mixed),  # attempt 1: still bad -> ModelRetry
        _final(mixed),  # attempt 2 (max_retries): drop bad, return Partial:
    ]

    investigation, _emitted, _seen = await _run(store, make_settings, steps)

    # No exception was raised.
    assert investigation.survey_id == SURVEY_ID
    # Verdict is prefixed with "Partial:".
    assert investigation.verdict.startswith("Partial:")
    # Only the valid finding survived.
    assert len(investigation.findings) == 1
    assert investigation.findings[0].statement == "Bleaching exceeds 30%."
    for finding in investigation.findings:
        for ref in finding.evidence:
            assert ref.id in {frame_id, heat.id}
    # Only hypotheses with valid supporting evidence survived.
    assert len(investigation.hypotheses) == 1
    assert investigation.hypotheses[0].cause == Cause.HEAT_STRESS
    for hyp in investigation.hypotheses:
        for ref in hyp.supporting:
            assert ref.id in {frame_id, heat.id}


@pytest.mark.asyncio
async def test_all_citations_invalid_produces_partial_with_minimal_content(
    store: Store, make_settings: Any
) -> None:
    """When every single citation is fake, the partial fallback still returns an
    Investigation with Partial: verdict and at least minimal structure."""
    await _seed(store)

    bad = _always_bad_draft()
    steps = [
        _final(bad),  # attempt 0: all bad -> ModelRetry
        _final(bad),  # attempt 1: all bad -> ModelRetry
        _final(bad),  # attempt 2: all bad -> drop everything, Partial:
    ]

    investigation, _emitted, _seen = await _run(store, make_settings, steps)

    assert investigation.verdict.startswith("Partial:")
    assert len(investigation.findings) >= 1
    assert len(investigation.hypotheses) >= 1


# ────────── validate() unit tests (direct, no agent) ──────────


def test_validate_returns_empty_for_fully_cited_draft() -> None:
    from reefcase.agent.citations import validate

    draft = InvestigationDraft(
        findings=[
            Finding(
                statement="Bleaching detected.",
                evidence=[EvidenceRef(kind="frame", id="frm_1")],
            )
        ],
        hypotheses=[
            Hypothesis(
                cause=Cause.HEAT_STRESS,
                confidence=0.8,
                supporting=[EvidenceRef(kind="tool_result", id="tr_1")],
                contradicting=[],
                rationale="DHW above threshold.",
            )
        ],
        verdict="Heat stress.",
        actions=["Resurvey."],
        uncertain_frames=[],
    )
    offending = validate(draft, {"frm_1", "tr_1"})
    assert offending == []


def test_validate_returns_offending_statements_for_unknown_ids() -> None:
    from reefcase.agent.citations import validate

    draft = InvestigationDraft(
        findings=[
            Finding(
                statement="Ghost nets observed.",
                evidence=[EvidenceRef(kind="tool_result", id="tr_GHOST")],
            ),
            Finding(
                statement="Bleaching detected.",
                evidence=[EvidenceRef(kind="frame", id="frm_1")],
            ),
        ],
        hypotheses=[
            Hypothesis(
                cause=Cause.HEAT_STRESS,
                confidence=0.8,
                supporting=[EvidenceRef(kind="tool_result", id="tr_1")],
                contradicting=[],
                rationale="DHW above threshold.",
            )
        ],
        verdict="Heat stress.",
        actions=["Resurvey."],
        uncertain_frames=[],
    )
    offending = validate(draft, {"frm_1", "tr_1"})
    assert offending == ["Ghost nets observed."]
