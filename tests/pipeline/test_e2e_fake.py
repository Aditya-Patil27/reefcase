"""Story 5.4 — End-to-end fake survey pipeline (architecture §5.5, §6.1, §6.3, §6.4).

Verifies the full pipeline:
- Video uploaded via POST /api/surveys
- JobRunner: ingest -> fake segment -> assess -> investigate (FunctionModel)
- Tools use seeded cache hits in store.tool_results (no network)
- Dynamic frame IDs cited from prompt (never invented IDs)
- Event stream ends in report_ready
- Survey status is done
- GET /api/surveys/{id}/investigation returns the persisted report
- GET /api/surveys/{id}/frames returns frames with segmentation and assessment
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from reefcase.api.main import create_app
from reefcase.core.schemas import (
    Cause,
    GeoPoint,
    Site,
    SurveyStatus,
    ToolResult,
)
from reefcase.pipeline import stages
from reefcase.store.db import Store
from reefcase.tools.heat_stress import HeatStressParams
from reefcase.tools.registry import canonical_params

CLIP_BYTES = (Path(__file__).parents[1] / "fixtures" / "clip_10s.mp4").read_bytes()
SITE_ID = "site_e2e_test"
SITE_LAT = 19.7292
SITE_LON = -157.4132
DIVE_DATE = "2026-10-01"
HEAT_START = "2026-07-01"
HEAT_END = "2026-10-01"


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_sse(body: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for block in body.split("\n\n"):
        record: dict[str, Any] = {}
        for line in block.splitlines():
            if line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            record[field] = value.lstrip(" ")
        if record:
            records.append(record)
    return records


@pytest.mark.asyncio
async def test_e2e_fake_survey_pipeline(make_settings, tmp_path: Path) -> None:
    settings = make_settings(
        data_dir=str(tmp_path / "var"),
        segmenter="fake",
        min_frames=1,
        keep_frames=2,
    )

    # 1. Teacher model for assess stage
    def teacher_respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        draft = {
            "bleaching_severity": 3,
            "morphology": ["branching", "massive"],
            "damage": ["broken"],
            "notes": "Severe paling on branching corals.",
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=draft)])

    teacher_model = FunctionModel(teacher_respond, model_name="spark-teacher-fake")

    # 2. Agent model for investigate stage:
    # First turn: calls heat_stress with the seeded params
    # Second turn: receives tool return, finds frame id from the initial user prompt,
    # and returns final_result citing the dynamic frame ID and seeded tool result ID.
    turn_count = 0

    def agent_respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="heat_stress",
                        args={"site_id": SITE_ID, "start": HEAT_START, "end": HEAT_END},
                        tool_call_id="call_heat_1",
                    )
                ]
            )

        # Extract frame IDs from the prompt dynamically (never invent IDs)
        prompt_text = ""
        for msg in messages:
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    prompt_text += part.content

        frame_ids = re.findall(r"frm_[A-Za-z0-9]+", prompt_text)
        assert frame_ids, "Agent did not receive frame IDs in prompt"

        # Find tool result id from ToolReturnPart
        tr_id = "tr_heat_e2e"
        for msg in messages:
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    content = part.content
                    if isinstance(content, dict) and "id" in content:
                        tr_id = str(content["id"])

        draft = {
            "findings": [
                {
                    "statement": "Over half of the branching coral colonies exhibit bleaching.",
                    "evidence": [{"kind": "frame", "id": frame_ids[0]}],
                }
            ],
            "hypotheses": [
                {
                    "cause": "heat_stress",
                    "confidence": 0.9,
                    "supporting": [{"kind": "tool_result", "id": tr_id}],
                    "contradicting": [],
                    "rationale": "Sustained high degree heating weeks over the past 90 days.",
                }
            ],
            "verdict": "Acute thermal bleaching driven by elevated ocean temperatures.",
            "actions": [
                "Deploy local water temperature loggers.",
                "Conduct follow-up survey in 30 days.",
            ],
            "uncertain_frames": [],
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=draft)])

    agent_model = FunctionModel(agent_respond, model_name="spark-agent-fake")

    # Wire stages runner using these models
    async def custom_run_stages(store: Store, survey_id: str) -> None:
        await stages.run_stages(
            store,
            survey_id,
            settings=settings,
            teacher_model=teacher_model,
            agent_model=agent_model,
        )

    app = create_app(settings, run_stages=custom_run_stages)
    store = app.state.store

    # Pre-seed site so upload attaches to this exact site
    site = Site(
        id=SITE_ID,
        name="Kona Reef",
        location=GeoPoint(lat=SITE_LAT, lon=SITE_LON),
        created_at=_now(),
    )
    await store.sites.save(site)

    # Pre-seed tool result in store.tool_results (cache hit: no network call)
    heat_params = HeatStressParams(
        site_id=SITE_ID,
        start=date.fromisoformat(HEAT_START),
        end=date.fromisoformat(HEAT_END),
    )
    heat_result = ToolResult(
        id="tr_heat_e2e",
        tool="heat_stress",
        params=heat_params.model_dump(mode="json"),
        data={
            "available": True,
            "lat": SITE_LAT,
            "lon": SITE_LON,
            "max_dhw": 8.7,
            "max_dhw_date": "2026-09-15",
            "daily": [],
        },
        source_url="https://pae-paha.pacioos.hawaii.edu/erddap/griddap/dhw_5km.json",
        retrieved_at=_now(),
    )
    await store.tool_results.save(heat_result, canonical_params(heat_params))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. Upload survey
        upload_resp = await client.post(
            "/api/surveys",
            data={"lat": str(SITE_LAT), "lon": str(SITE_LON), "dive_date": DIVE_DATE},
            files={"video": ("clip_10s.mp4", CLIP_BYTES, "video/mp4")},
        )
        assert upload_resp.status_code == 201
        survey_data = upload_resp.json()
        survey_id = survey_data["id"]
        assert survey_data["site_id"] == SITE_ID

        # 4. Run the runner to execute all stages end-to-end
        ran = await app.state.runner.run_once()
        assert ran is True

        # 5. Check survey status is DONE
        updated_survey = await store.surveys.get(survey_id)
        assert updated_survey.status == SurveyStatus.DONE

        # 6. Check event stream ends in report_ready
        events_resp = await client.get(f"/api/surveys/{survey_id}/events")
        assert events_resp.status_code == 200
        records = _parse_sse(events_resp.text)
        event_types = [r.get("event") for r in records]

        assert "survey_started" in event_types
        assert "frames_extracted" in event_types
        assert "frame_scored" in event_types
        assert "segmented" in event_types
        assert "assessed" in event_types
        assert "tool_called" in event_types
        assert "tool_returned" in event_types
        assert "finding" in event_types
        assert event_types[-1] == "report_ready"

        # 7. GET /api/surveys/{id}/investigation returns the persisted report
        inv_resp = await client.get(f"/api/surveys/{survey_id}/investigation")
        assert inv_resp.status_code == 200
        inv_data = inv_resp.json()
        assert inv_data["survey_id"] == survey_id
        assert (
            inv_data["verdict"] == "Acute thermal bleaching driven by elevated ocean temperatures."
        )
        assert len(inv_data["findings"]) == 1
        assert len(inv_data["hypotheses"]) == 1
        assert inv_data["hypotheses"][0]["cause"] == Cause.HEAT_STRESS.value
        assert len(inv_data["actions"]) == 2

        # 8. GET /api/surveys/{id}/frames returns frames with segmentation and assessment
        frames_resp = await client.get(f"/api/surveys/{survey_id}/frames")
        assert frames_resp.status_code == 200
        frames_data = frames_resp.json()
        assert len(frames_data) >= 1
        for fd in frames_data:
            assert "frame" in fd
            assert fd["frame"]["survey_id"] == survey_id
            assert "segmentation" in fd
            assert fd["segmentation"] is not None
            assert "assessment" in fd
            assert fd["assessment"] is not None
