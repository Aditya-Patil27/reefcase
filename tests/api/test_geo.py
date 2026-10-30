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


def _offline_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected network call: {request.url}")

    return httpx.MockTransport(handler)


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
        assert "class_name" in feat["properties"]


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


@pytest.mark.asyncio
async def test_get_geo_vessels_returns_detection_points(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    store = app.state.store

    site = Site(
        id="site_geo_test",
        name="Kona Reef",
        location=GeoPoint(lat=19.64, lon=-155.99),
        created_at=_now(),
    )
    await store.sites.save(site)

    survey = Survey(
        id="srv_vessel_test",
        site_id=site.id,
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.DONE,
        source="upload",
        created_at=_now(),
    )
    await store.surveys.save(survey)

    # Seed tool result with detection points
    params = VesselActivityParams(
        site_id=site.id,
        radius_km=10.0,
        start=date(2026, 9, 25),
        end=date(2026, 10, 25),
    )
    result = ToolResult(
        id="tr_vessel_test_01",
        tool="vessel_activity",
        params=params.model_dump(mode="json"),
        data={
            "sar_detections": {
                "total": 3,
                "unmatched_to_ais": {
                    "count": 2,
                    "points": [
                        {"lat": 19.641, "lon": -155.991},
                        {"lat": 19.645, "lon": -155.985},
                    ],
                },
            },
            "fishing_hours": 1.5,
        },
        source_url="https://gateway.api.globalfishingwatch.org/v3/4wings/report",
        retrieved_at=_now(),
    )
    await store.tool_results.save(result, canonical_params(params))

    # Append events so survey history points to tool result
    await store.events.append(
        ToolCalled(
            survey_id=survey.id,
            seq=await store.events.next_seq(survey.id),
            ts=_now(),
            call_id="call_v_01",
            tool="vessel_activity",
            params=params.model_dump(mode="json"),
        )
    )
    await store.events.append(
        ToolReturned(
            survey_id=survey.id,
            seq=await store.events.next_seq(survey.id),
            ts=_now(),
            call_id="call_v_01",
            tool_result_id=result.id,
            summary="vessels found",
        )
    )

    async with client_for(app) as client:
        resp = await client.get(f"/api/geo/vessels?survey_id={survey.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2

    p1 = data["features"][0]
    assert p1["type"] == "Feature"
    assert p1["geometry"]["type"] == "Point"
    assert p1["geometry"]["coordinates"] == [-155.991, 19.641]
    assert p1["properties"]["unmatched_to_ais"] is True

    p2 = data["features"][1]
    assert p2["geometry"]["coordinates"] == [-155.985, 19.645]


@pytest.mark.asyncio
async def test_get_geo_vessels_filtered_by_bbox(make_settings, tmp_path: Path) -> None:
    app = build_app(make_settings, tmp_path)
    store = app.state.store

    site = Site(
        id="site_geo_bbox",
        name="Kona Reef",
        location=GeoPoint(lat=19.64, lon=-155.99),
        created_at=_now(),
    )
    await store.sites.save(site)

    survey = Survey(
        id="srv_vessel_bbox",
        site_id=site.id,
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.DONE,
        source="upload",
        created_at=_now(),
    )
    await store.surveys.save(survey)

    params = VesselActivityParams(
        site_id=site.id,
        radius_km=10.0,
        start=date(2026, 9, 25),
        end=date(2026, 10, 25),
    )
    result = ToolResult(
        id="tr_vessel_bbox_01",
        tool="vessel_activity",
        params=params.model_dump(mode="json"),
        data={
            "sar_detections": {
                "total": 2,
                "unmatched_to_ais": {
                    "count": 2,
                    "points": [
                        {"lat": 19.641, "lon": -155.991},
                        {"lat": 19.700, "lon": -155.900},
                    ],
                },
            },
            "fishing_hours": 0.0,
        },
        source_url="https://gateway.api.globalfishingwatch.org/v3/4wings/report",
        retrieved_at=_now(),
    )
    await store.tool_results.save(result, canonical_params(params))

    # Query with bbox that only covers the first point
    bbox = "-156.0,19.6,-155.95,19.65"
    async with client_for(app) as client:
        resp = await client.get(f"/api/geo/vessels?survey_id={survey.id}&bbox={bbox}")
    assert resp.status_code == 200
    features = resp.json()["features"]
    assert len(features) == 1
    assert features[0]["geometry"]["coordinates"] == [-155.991, 19.641]
