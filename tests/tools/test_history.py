"""Tests for Story 4.5 — site_history.

AC: Given a site with 3 completed surveys
    When site_history runs
    Then it returns them ordered by dive_date with cover, excluding the current survey
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from reefcase.core.errors import NotFoundError
from reefcase.core.schemas import GeoPoint, SegClass, Site, Survey, SurveyStatus
from reefcase.store.db import Store
from reefcase.tools.history import SiteHistoryParams, site_history
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import registry


def _strict_mock_client() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected network call: {request.url}")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _create_site(store: Store, site_id: str) -> Site:
    site = Site(
        id=site_id,
        name="Kealakekua Bay",
        location=GeoPoint(lat=19.48, lon=-155.93),
        created_at=datetime.now(UTC),
    )
    await store.sites.save(site)
    return site


async def _save_survey(
    store: Store,
    site_id: str,
    survey_id: str,
    dive_date: date,
    status: SurveyStatus,
    live_coral: float | None = None,
) -> None:
    cover = None if live_coral is None else {SegClass.LIVE_CORAL: live_coral, SegClass.SAND: 0.2}
    await store.surveys.save(
        Survey(
            id=survey_id,
            site_id=site_id,
            dive_date=dive_date,
            status=status,
            source="upload",
            cover=cover,
            created_at=datetime.now(UTC),
        )
    )


@pytest.mark.asyncio
async def test_site_history_returns_done_surveys_by_dive_date(
    store: Store, make_settings: Any
) -> None:
    """AC: 3 completed surveys ordered by dive_date with cover; the current one is excluded."""
    site = await _create_site(store, "site_3_completed")
    # Saved out of order; the current survey is RUNNING while the investigator runs.
    await _save_survey(store, site.id, "srv_2024", date(2024, 11, 20), SurveyStatus.DONE, 0.40)
    await _save_survey(store, site.id, "srv_current", date(2026, 10, 25), SurveyStatus.RUNNING)
    await _save_survey(store, site.id, "srv_2021", date(2021, 5, 10), SurveyStatus.DONE, 0.55)
    await _save_survey(store, site.id, "srv_failed", date(2022, 3, 1), SurveyStatus.FAILED)
    await _save_survey(store, site.id, "srv_2023", date(2023, 8, 15), SurveyStatus.DONE, 0.45)

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        result = await site_history(SiteHistoryParams(site_id=site.id), ctx)

    assert result.tool == "site_history"
    assert result.id.startswith("tr_")
    assert result.source_url == "/sites/site_3_completed"
    assert result.data == {
        "surveys": [
            {
                "survey_id": "srv_2021",
                "dive_date": "2021-05-10",
                "cover": {"live_coral": 0.55, "sand": 0.2},
            },
            {
                "survey_id": "srv_2023",
                "dive_date": "2023-08-15",
                "cover": {"live_coral": 0.45, "sand": 0.2},
            },
            {
                "survey_id": "srv_2024",
                "dive_date": "2024-11-20",
                "cover": {"live_coral": 0.40, "sand": 0.2},
            },
        ]
    }


@pytest.mark.asyncio
async def test_site_history_empty_when_no_past_surveys(store: Store, make_settings: Any) -> None:
    site = await _create_site(store, "site_no_past")
    await _save_survey(store, site.id, "srv_only", date(2026, 10, 25), SurveyStatus.RUNNING)

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        result = await site_history(SiteHistoryParams(site_id=site.id), ctx)

    assert result.data == {"surveys": []}


@pytest.mark.asyncio
async def test_site_history_unknown_site_raises_not_found(store: Store, make_settings: Any) -> None:
    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        with pytest.raises(NotFoundError):
            await site_history(SiteHistoryParams(site_id="site_nonexistent"), ctx)


@pytest.mark.asyncio
async def test_registry_call(store: Store, make_settings: Any) -> None:
    site = await _create_site(store, "site_registry")
    await _save_survey(store, site.id, "srv_reg_1", date(2023, 1, 1), SurveyStatus.DONE, 0.5)

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        result = await registry.call("site_history", {"site_id": site.id}, ctx)

    assert [s["survey_id"] for s in result.data["surveys"]] == ["srv_reg_1"]


def test_investigator_offers_every_tool() -> None:
    """A fresh interpreter, so tool modules this test file imports cannot mask a missing one."""
    code = (
        "from reefcase.agent.investigator import INVESTIGATOR_TOOLS\n"
        "from reefcase.tools.registry import registry\n"
        "print(sorted(set(INVESTIGATOR_TOOLS) - set(registry.names())))\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"
