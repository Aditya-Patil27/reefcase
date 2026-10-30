"""Story 4.6 — Map layer endpoints: /api/geo/{layer} (architecture §5.4, §6.3)."""

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from reefcase.api.main import create_app
from reefcase.core.events import ToolCalled, ToolReturned
from reefcase.core.schemas import GeoPoint, Site, Survey, SurveyStatus, ToolResult
from reefcase.tools.registry import canonical_params
from reefcase.tools.vessels import VesselActivityParams


def _now() -> datetime:
    return datetime.now(UTC)


def build_app(make_settings, tmp_path: Path):
    settings = make_settings(data_dir=str(tmp_path / "var"))
    return create_app(settings)


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


@pytest.mark.asyncio
async def test_get_geo_unknown_layer_returns_422(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        resp = await client.get("/api/geo/unknown")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_geo_invalid_bbox_returns_422(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        resp = await client.get("/api/geo/mpa?bbox=not,a,valid,bbox")
        assert resp.status_code == 422

        resp2 = await client.get("/api/geo/mpa?bbox=1,2,3")
        assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_get_geo_mpa_without_bbox_returns_all_features(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        resp = await client.get("/api/geo/mpa")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    feature = data["features"][0]
    assert feature["type"] == "Feature"
    assert "geometry" in feature
    assert "properties" in feature
    assert "name" in feature["properties"]
    assert all(f["properties"]["no_take"] in (True, False, None) for f in data["features"])


@pytest.mark.asyncio
async def test_get_geo_mpa_with_bbox_clips_features(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    # Box around Kealakekua Bay
    bbox = "-156.0,19.4,-155.8,19.6"
    async with client_for(app) as client:
        resp = await client.get(f"/api/geo/mpa?bbox={bbox}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1
    feat = data["features"][0]
    assert "Kealakekua" in feat["properties"]["name"]

    # Disjoint box returns 0 features
    disjoint = "0.0,0.0,0.1,0.1"
    async with client_for(app) as client:
        resp_empty = await client.get(f"/api/geo/mpa?bbox={disjoint}")
    assert resp_empty.status_code == 200
    assert resp_empty.json()["features"] == []


@pytest.mark.asyncio
async def test_get_geo_reef_with_bbox(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    bbox = "-156.0,19.4,-155.8,19.6"
    async with client_for(app) as client:
        resp = await client.get(f"/api/geo/reef?bbox={bbox}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    for feat in data["features"][:5]:
        assert feat["type"] == "Feature"
        assert set(feat["properties"]) == {"layer", "class_name"}


@pytest.mark.asyncio
async def test_get_geo_vessels_without_survey_id_returns_empty_collection(
    make_settings, tmp_path: Path
) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        resp = await client.get("/api/geo/vessels")
    assert resp.status_code == 200
    assert resp.json() == {"type": "FeatureCollection", "features": []}


@pytest.mark.asyncio
async def test_get_geo_vessels_unknown_survey_returns_404(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    async with client_for(app) as client:
        resp = await client.get("/api/geo/vessels?survey_id=srv_nonexistent")
    assert resp.status_code == 404


async def _seed_vessel_survey(
    store, survey_id: str, points: list[dict[str, float]], *, returned: bool = True
) -> str:
    """A Kona survey whose vessel_activity result holds ``points``; returns the result id.

    With ``returned=False`` the result is only in the shared cache, as if another survey's
    agent had fetched it.
    """
    site = Site(
        id="site_geo_test",
        name="Kona Reef",
        location=GeoPoint(lat=19.64, lon=-155.99),
        created_at=_now(),
    )
    await store.sites.save(site)
    await store.surveys.save(
        Survey(
            id=survey_id,
            site_id=site.id,
            dive_date=date(2026, 10, 25),
            status=SurveyStatus.DONE,
            source="upload",
            created_at=_now(),
        )
    )
    params = VesselActivityParams(
        site_id=site.id,
        radius_km=10.0,
        start=date(2026, 9, 25),
        end=date(2026, 10, 25),
    )
    result = ToolResult(
        id=f"tr_{survey_id}",
        tool="vessel_activity",
        params=params.model_dump(mode="json"),
        data={
            "sar_detections": {
                "total": len(points) + 1,
                "unmatched_to_ais": {"count": len(points), "points": points},
            },
            "fishing_hours": 1.5,
        },
        source_url="https://gateway.api.globalfishingwatch.org/v3/4wings/report",
        retrieved_at=_now(),
    )
    await store.tool_results.save(result, canonical_params(params))
    if returned:
        await store.events.append(
            ToolCalled(
                survey_id=survey_id,
                seq=await store.events.next_seq(survey_id),
                ts=_now(),
                call_id="call_v_01",
                tool="vessel_activity",
                params=params.model_dump(mode="json"),
            )
        )
        await store.events.append(
            ToolReturned(
                survey_id=survey_id,
                seq=await store.events.next_seq(survey_id),
                ts=_now(),
                call_id="call_v_01",
                tool_result_id=result.id,
                summary="vessels found",
            )
        )
    return result.id


@pytest.mark.asyncio
async def test_get_geo_vessels_returns_detection_points(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    points = [{"lat": 19.641, "lon": -155.991}, {"lat": 19.645, "lon": -155.985}]
    result_id = await _seed_vessel_survey(app.state.store, "srv_vessel_test", points)

    async with client_for(app) as client:
        resp = await client.get("/api/geo/vessels?survey_id=srv_vessel_test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert [f["geometry"] for f in data["features"]] == [
        {"type": "Point", "coordinates": [-155.991, 19.641]},
        {"type": "Point", "coordinates": [-155.985, 19.645]},
    ]
    assert data["features"][0]["properties"] == {
        "unmatched_to_ais": True,
        "tool_result_id": result_id,
    }


@pytest.mark.asyncio
async def test_get_geo_vessels_ignores_results_the_survey_did_not_get(
    make_settings, tmp_path: Path
) -> None:
    app = build_app(make_settings, tmp_path)
    store = app.state.store
    # Another survey at the same site fetched vessel activity; this one never called the tool.
    await _seed_vessel_survey(store, "srv_other", [{"lat": 19.641, "lon": -155.991}])
    await _seed_vessel_survey(store, "srv_quiet", [], returned=False)

    async with client_for(app) as client:
        resp = await client.get("/api/geo/vessels?survey_id=srv_quiet")
    assert resp.status_code == 200
    assert resp.json()["features"] == []


@pytest.mark.asyncio
async def test_get_geo_vessels_filtered_by_bbox(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    points = [{"lat": 19.641, "lon": -155.991}, {"lat": 19.700, "lon": -155.900}]
    await _seed_vessel_survey(app.state.store, "srv_vessel_bbox", points)

    # Query with bbox that only covers the first point
    bbox = "-156.0,19.6,-155.95,19.65"
    async with client_for(app) as client:
        resp = await client.get(f"/api/geo/vessels?survey_id=srv_vessel_bbox&bbox={bbox}")
    assert resp.status_code == 200
    features = resp.json()["features"]
    assert len(features) == 1
    assert features[0]["geometry"]["coordinates"] == [-155.991, 19.641]
