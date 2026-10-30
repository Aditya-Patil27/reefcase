"""Story 4.1 AC 2 — ``GET /api/tool-results/{id}`` serves a stored result (§6.3).

The store is read through ``app.state.store`` because ``httpx.ASGITransport``
does not run FastAPI's lifespan (the 2-1 learning).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from reefcase.api.main import create_app
from reefcase.core.ids import TOOL_RESULT, new_id
from reefcase.core.schemas import ToolResult


def build_app(make_settings, tmp_path: Path):
    settings = make_settings(data_dir=str(tmp_path / "var"), segmenter="fake")
    return create_app(settings)


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def make_result() -> ToolResult:
    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool="heat_stress",
        params={"site_id": "site_1", "start": "2026-01-01", "end": "2026-02-01"},
        data={"max_dhw": 4.5, "available": True},
        source_url="https://example.test/erddap/dhw",
        retrieved_at=datetime(2026, 2, 2, 9, 30, tzinfo=UTC),
    )


def params_key(result: ToolResult) -> str:
    return json.dumps(result.params, sort_keys=True, separators=(",", ":"))


@pytest.mark.asyncio
async def test_get_tool_result_returns_the_stored_result(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    result = make_result()
    await app.state.store.tool_results.save(result, params_key(result))

    async with client_for(app) as client:
        response = await client.get(f"/api/tool-results/{result.id}")

    assert response.status_code == 200
    assert response.json() == result.model_dump(mode="json")


@pytest.mark.asyncio
async def test_unknown_tool_result_is_404(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)

    async with client_for(app) as client:
        response = await client.get("/api/tool-results/tr_missing")

    assert response.status_code == 404
