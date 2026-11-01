"""Story 4.7 — ``GET /api/sites`` and ``GET /api/sites/{id}`` (§6.3, the web's SiteSummary)."""

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from reefcase.api.main import create_app
from reefcase.core.schemas import GeoPoint, SegClass, Site, Survey, SurveyStatus

CREATED = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def build_app(make_settings, tmp_path: Path):
    settings = make_settings(data_dir=str(tmp_path / "var"), segmenter="fake")
    return create_app(settings, run_stages=None)


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def site(site_id: str, mpa_id: str | None = None) -> Site:
    return Site(
        id=site_id,
        name=site_id.title(),
        location=GeoPoint(lat=-14.668, lon=145.461),
        mpa_id=mpa_id,
        created_at=CREATED,
    )


def cover(live: float) -> dict[SegClass, float]:
    rest = (1.0 - live) / 5
    return {c: live if c == SegClass.LIVE_CORAL else rest for c in SegClass}


def survey(
    survey_id: str,
    site_id: str,
    dive_date: str,
    live: float | None,
    status: SurveyStatus = SurveyStatus.DONE,
) -> Survey:
    return Survey(
        id=survey_id,
        site_id=site_id,
        dive_date=date.fromisoformat(dive_date),
        status=status,
        source="historical",
        cover=None if live is None else cover(live),
        created_at=CREATED,
    )


async def seed(app, sites: list[Site], surveys: list[Survey]) -> None:
    for s in sites:
        await app.state.store.sites.save(s)
    for s in surveys:
        await app.state.store.surveys.save(s)


@pytest.mark.asyncio
async def test_sites_list_latest_cover_and_trend(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    await seed(
        app,
        [site("site_a", mpa_id="mpa_a")],
        [
            survey("srv_2", "site_a", "2026-10-21", 0.30),
            survey("srv_1", "site_a", "2019-08-19", 0.45),
            # Still running: not the latest cover yet.
            survey("srv_3", "site_a", "2026-10-30", None, SurveyStatus.RUNNING),
        ],
    )

    async with client_for(app) as client:
        response = await client.get("/api/sites")

    assert response.status_code == 200
    [summary] = response.json()
    assert summary == {
        "id": "site_a",
        "name": "Site_A",
        "location": {"lat": -14.668, "lon": 145.461},
        "mpa_id": "mpa_a",
        "latest_cover": {c.value: pytest.approx(v) for c, v in cover(0.30).items()},
        "latest_dive_date": "2026-10-21",
        "first_dive_date": "2019-08-19",
        "live_coral_change": pytest.approx(-0.15),
        "trend": "declining",
    }


@pytest.mark.parametrize(
    ("first", "latest", "trend"),
    [
        (0.30, 0.45, "improving"),
        (0.40, 0.44, "stable"),
        (0.44, 0.40, "stable"),
        (0.45, 0.30, "declining"),
    ],
)
@pytest.mark.asyncio
async def test_trend_is_live_coral_since_the_first_survey(
    make_settings, tmp_path: Path, first: float, latest: float, trend: str
) -> None:
    app = build_app(make_settings, tmp_path)
    await seed(
        app,
        [site("site_a")],
        [
            survey("srv_1", "site_a", "2019-08-19", first),
            survey("srv_2", "site_a", "2026-10-21", latest),
        ],
    )

    async with client_for(app) as client:
        [summary] = (await client.get("/api/sites")).json()

    assert summary["trend"] == trend
    assert summary["live_coral_change"] == pytest.approx(latest - first)


@pytest.mark.asyncio
async def test_a_single_survey_is_stable(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    await seed(app, [site("site_a")], [survey("srv_1", "site_a", "2026-10-21", 0.30)])

    async with client_for(app) as client:
        [summary] = (await client.get("/api/sites")).json()

    assert summary["trend"] == "stable"
    assert summary["live_coral_change"] == 0.0
    assert summary["first_dive_date"] == summary["latest_dive_date"] == "2026-10-21"


@pytest.mark.asyncio
async def test_sites_without_a_completed_survey_are_left_out(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    await seed(
        app,
        [site("site_a"), site("site_b"), site("site_c")],
        [
            survey("srv_1", "site_a", "2026-10-21", 0.30),
            survey("srv_2", "site_b", "2026-10-21", None, SurveyStatus.FAILED),
        ],
    )

    async with client_for(app) as client:
        response = await client.get("/api/sites")

    assert [s["id"] for s in response.json()] == ["site_a"]


@pytest.mark.asyncio
async def test_site_detail_lists_every_survey_newest_first(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    await seed(
        app,
        [site("site_a"), site("site_b")],
        [
            survey("srv_1", "site_a", "2019-08-19", 0.45),
            survey("srv_3", "site_a", "2026-10-30", None, SurveyStatus.RUNNING),
            survey("srv_2", "site_a", "2026-10-21", 0.30),
            survey("srv_4", "site_b", "2026-10-22", 0.50),
        ],
    )

    async with client_for(app) as client:
        response = await client.get("/api/sites/site_a")

    assert response.status_code == 200
    body = response.json()
    assert body["site"] == {
        "id": "site_a",
        "name": "Site_A",
        "location": {"lat": -14.668, "lon": 145.461},
        "mpa_id": None,
        "created_at": "2026-10-01T09:00:00Z",
    }
    assert [s["id"] for s in body["surveys"]] == ["srv_3", "srv_2", "srv_1"]
    assert body["surveys"][0]["cover"] is None


@pytest.mark.asyncio
async def test_unknown_site_is_404(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)

    async with client_for(app) as client:
        response = await client.get("/api/sites/site_nope")

    assert response.status_code == 404
    assert "site_nope" in response.json()["detail"]
