"""Story 2.5 — Site matching: surveys within 500 m share a site (FR12)."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from reefcase.api.main import create_app
from reefcase.core.schemas import GeoPoint, Site
from reefcase.store.db import Store
from reefcase.store.repos import SITE_MATCH_RADIUS_M

CLIP_BYTES = (Path(__file__).parents[1] / "fixtures" / "clip_10s.mp4").read_bytes()
BASE = GeoPoint(lat=19.7292, lon=-157.4132)
METRES_PER_DEG_LAT = 111_195.0  # mean Earth radius 6371 km


def _north_of(point: GeoPoint, metres: float) -> GeoPoint:
    return GeoPoint(lat=point.lat + metres / METRES_PER_DEG_LAT, lon=point.lon)


def _site(site_id: str, location: GeoPoint) -> Site:
    return Site(id=site_id, name=site_id, location=location, created_at=datetime.now(UTC))


def test_match_radius_is_500_m() -> None:
    assert SITE_MATCH_RADIUS_M == 500.0


@pytest.mark.asyncio
async def test_find_site_near_matches_a_site_300_m_away(store: Store) -> None:
    await store.sites.save(_site("site_a", BASE))
    found = await store.sites.find_site_near(_north_of(BASE, 300))
    assert found is not None
    assert found.id == "site_a"


@pytest.mark.asyncio
async def test_find_site_near_ignores_sites_beyond_500_m(store: Store) -> None:
    await store.sites.save(_site("site_a", BASE))
    assert await store.sites.find_site_near(_north_of(BASE, 600)) is None


@pytest.mark.asyncio
async def test_find_site_near_returns_the_nearest_site(store: Store) -> None:
    await store.sites.save(_site("site_far", _north_of(BASE, 400)))
    await store.sites.save(_site("site_near", _north_of(BASE, 100)))
    found = await store.sites.find_site_near(BASE)
    assert found is not None
    assert found.id == "site_near"


@pytest.mark.asyncio
async def test_find_site_near_on_an_empty_store(store: Store) -> None:
    assert await store.sites.find_site_near(BASE) is None


async def _post(client: httpx.AsyncClient, location: GeoPoint, site_name: str | None = None):
    fields = {"lat": str(location.lat), "lon": str(location.lon), "dive_date": "2026-10-01"}
    if site_name is not None:
        fields["site_name"] = site_name
    files = {"video": ("clip.mp4", CLIP_BYTES, "video/mp4")}
    response = await client.post("/api/surveys", data=fields, files=files)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_upload_300_m_away_attaches_to_the_existing_site(make_settings, tmp_path) -> None:
    app = create_app(make_settings(data_dir=str(tmp_path / "var")))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await _post(client, BASE, site_name="Horseshoe Reef")
        second = await _post(client, _north_of(BASE, 300), site_name="Another name")

    assert second["site_id"] == first["site_id"]
    store: Store = app.state.store
    assert len(await store.sites.list()) == 1
    assert (await store.sites.get(first["site_id"])).name == "Horseshoe Reef"
    assert {s.id for s in await store.surveys.by_site(first["site_id"])} == {
        first["id"],
        second["id"],
    }


@pytest.mark.asyncio
async def test_upload_with_no_site_within_500_m_creates_one(make_settings, tmp_path) -> None:
    app = create_app(make_settings(data_dir=str(tmp_path / "var")))
    transport = httpx.ASGITransport(app=app)
    far = _north_of(BASE, 1_000)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await _post(client, BASE, site_name="Horseshoe Reef")
        unnamed = await _post(client, far)

    assert unnamed["site_id"] != first["site_id"]
    site = await app.state.store.sites.get(unnamed["site_id"])
    assert site.name == f"Reef @ {far.lat:.5f}, {far.lon:.5f}"
    assert site.location == far
