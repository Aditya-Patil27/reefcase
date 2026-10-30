"""Tests for Story 4.5 — site_history.

AC: Given a site with 3 completed surveys
    When site_history runs
    Then it returns them ordered by dive_date with cover, excluding the current survey
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from reefcase.core.errors import NotFoundError
from reefcase.core.schemas import GeoPoint, SegClass, Site, Survey, SurveyStatus, ToolResult
from reefcase.store.db import Store
from reefcase.tools.history import SITE_HISTORY_SOURCE_URL, SiteHistoryParams, site_history
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import registry


def _strict_mock_client() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected network call: {request.url}")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _create_site(store: Store, site_id: str = "site_history_test") -> Site:
    site = Site(
        id=site_id,
        name="Kealakekua Bay",
        location=GeoPoint(lat=19.48, lon=-155.93),
        created_at=datetime.now(UTC),
    )
    await store.sites.save(site)
    return site


@pytest.mark.asyncio
async def test_site_history_returns_ordered_completed_surveys_excluding_current(
    store: Store, make_settings: Any
) -> None:
    """AC: Returns completed surveys ordered by dive_date with cover, excluding current."""
    site = await _create_site(store, "site_3_completed")

    # Survey 1: 2021-05-10
    s1 = Survey(
        id="srv_past_1",
        site_id=site.id,
        dive_date=date(2021, 5, 10),
        status=SurveyStatus.DONE,
        source="upload",
        cover={
            SegClass.LIVE_CORAL: 0.55,
            SegClass.BLEACHED_CORAL: 0.05,
            SegClass.ALGAE: 0.10,
            SegClass.RUBBLE: 0.10,
            SegClass.SAND: 0.20,
            SegClass.OTHER: 0.0,
        },
        created_at=datetime(2021, 5, 10, 12, 0, tzinfo=UTC),
    )
    # Survey 2: 2023-08-15
    s2 = Survey(
        id="srv_past_2",
        site_id=site.id,
        dive_date=date(2023, 8, 15),
        status=SurveyStatus.DONE,
        source="upload",
        cover={
            SegClass.LIVE_CORAL: 0.45,
            SegClass.BLEACHED_CORAL: 0.15,
            SegClass.ALGAE: 0.15,
            SegClass.RUBBLE: 0.10,
            SegClass.SAND: 0.15,
            SegClass.OTHER: 0.0,
        },
        created_at=datetime(2023, 8, 15, 12, 0, tzinfo=UTC),
    )
    # Survey 3: 2024-11-20
    s3 = Survey(
        id="srv_past_3",
        site_id=site.id,
        dive_date=date(2024, 11, 20),
        status=SurveyStatus.DONE,
        source="upload",
        cover={
            SegClass.LIVE_CORAL: 0.40,
            SegClass.BLEACHED_CORAL: 0.20,
            SegClass.ALGAE: 0.15,
            SegClass.RUBBLE: 0.10,
            SegClass.SAND: 0.15,
            SegClass.OTHER: 0.0,
        },
        created_at=datetime(2024, 11, 20, 12, 0, tzinfo=UTC),
    )
    # Current Survey: 2026-10-25 (currently running / being investigated)
    s_current = Survey(
        id="srv_current",
        site_id=site.id,
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.RUNNING,
        source="upload",
        cover=None,
        created_at=datetime(2026, 10, 25, 12, 0, tzinfo=UTC),
    )

    # Save in non-chronological order to verify sorting
    await store.surveys.save(s3)
    await store.surveys.save(s1)
    await store.surveys.save(s_current)
    await store.surveys.save(s2)

    settings = make_settings()
    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)
        params = SiteHistoryParams(site_id=site.id, current_survey_id="srv_current")
        result = await site_history(params, ctx)

    assert isinstance(result, ToolResult)
    assert result.tool == "site_history"
    assert result.id.startswith("tr_")
    assert result.source_url == f"{SITE_HISTORY_SOURCE_URL}{site.id}"

    data = result.data
    surveys = data["surveys"]
    assert len(surveys) == 3

    # Verify chronological ordering
    assert surveys[0]["id"] == "srv_past_1"
    assert surveys[0]["date"] == "2021-05-10"
    assert surveys[0]["cover"]["live_coral"] == 0.55
    assert surveys[0]["live_coral"] == 0.55

    assert surveys[1]["id"] == "srv_past_2"
    assert surveys[1]["date"] == "2023-08-15"
    assert surveys[1]["cover"]["live_coral"] == 0.45
    assert surveys[1]["live_coral"] == 0.45

    assert surveys[2]["id"] == "srv_past_3"
    assert surveys[2]["date"] == "2024-11-20"
    assert surveys[2]["cover"]["live_coral"] == 0.40
    assert surveys[2]["live_coral"] == 0.40

    # Ensure current survey is excluded
    ids = [s["id"] for s in surveys]
    assert "srv_current" not in ids


@pytest.mark.asyncio
async def test_site_history_excludes_completed_current_survey(
    store: Store, make_settings: Any
) -> None:
    """When a survey is already marked DONE, passing current_survey_id still excludes it."""
    site = await _create_site(store, "site_exclude_completed")

    s1 = Survey(
        id="srv_old",
        site_id=site.id,
        dive_date=date(2022, 1, 1),
        status=SurveyStatus.DONE,
        source="upload",
        cover={SegClass.LIVE_CORAL: 0.6},
        created_at=datetime(2022, 1, 1, tzinfo=UTC),
    )
    s2 = Survey(
        id="srv_now_done",
        site_id=site.id,
        dive_date=date(2026, 1, 1),
        status=SurveyStatus.DONE,
        source="upload",
        cover={SegClass.LIVE_CORAL: 0.3},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await store.surveys.save(s1)
    await store.surveys.save(s2)

    settings = make_settings()
    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)
        params = SiteHistoryParams(site_id=site.id, current_survey_id="srv_now_done")
        result = await site_history(params, ctx)

    surveys = result.data["surveys"]
    assert len(surveys) == 1
    assert surveys[0]["id"] == "srv_old"


@pytest.mark.asyncio
async def test_site_history_empty_when_no_past_surveys(store: Store, make_settings: Any) -> None:
    """A site with only the current survey returns an empty list."""
    site = await _create_site(store, "site_no_past")
    s_only = Survey(
        id="srv_only",
        site_id=site.id,
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.RUNNING,
        source="upload",
        created_at=datetime.now(UTC),
    )
    await store.surveys.save(s_only)

    settings = make_settings()
    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)
        params = SiteHistoryParams(site_id=site.id, current_survey_id="srv_only")
        result = await site_history(params, ctx)

    assert result.data["surveys"] == []
    assert result.data["count"] == 0


@pytest.mark.asyncio
async def test_site_history_unknown_site_raises_not_found(store: Store, make_settings: Any) -> None:
    """Querying an unknown site_id raises NotFoundError."""
    settings = make_settings()
    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)
        with pytest.raises(NotFoundError):
            await site_history(SiteHistoryParams(site_id="site_nonexistent"), ctx)


@pytest.mark.asyncio
async def test_registry_integration(store: Store, make_settings: Any) -> None:
    """site_history is registered in the tool registry and can be invoked through registry.call."""
    site = await _create_site(store, "site_registry")
    s1 = Survey(
        id="srv_reg_1",
        site_id=site.id,
        dive_date=date(2023, 1, 1),
        status=SurveyStatus.DONE,
        source="upload",
        cover={SegClass.LIVE_CORAL: 0.5},
        created_at=datetime.now(UTC),
    )
    await store.surveys.save(s1)

    settings = make_settings()
    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)
        result = await registry.call("site_history", {"site_id": site.id}, ctx)

    assert result.tool == "site_history"
    assert len(result.data["surveys"]) == 1
