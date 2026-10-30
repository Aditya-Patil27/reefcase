"""Tests for Story 4.3 — vessel_activity (Global Fishing Watch).

AC 1: Given a site, radius_km <= 20 and a date range, vessel_activity returns
      sar_detections.total, sar_detections.unmatched_to_ais with points, and fishing_hours.
AC 2: Given radius_km > 20, validation fails before any HTTP call.
AC 3: Serialized result contains no vessel names, MMSI, or IMO numbers.
AC 4: Two concurrent calls are requested one at a time via asyncio.Semaphore(1),
      and a 524 status is recovered via the last-report endpoint.

The MockTransport payloads follow the documented 4Wings report shape,
``{"total": n, "entries": [{"<dataset>:vN": [row, ...]}]}``. ``test_recorded_report_kona``
replays a real GFW response from tests/cassettes/vessels/; it skips until that cassette is
recorded (ops/lead-d/handoff.md).
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import os
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from reefcase.core.errors import ConfigError, ExternalServiceError, NotFoundError
from reefcase.core.schemas import GeoPoint, Site, ToolResult
from reefcase.store.db import Store
from reefcase.tools import vessels
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import registry
from reefcase.tools.vessels import (
    GFW_LAST_REPORT_URL,
    GFW_REPORT_URL,
    VesselActivityParams,
    vessel_activity,
)

CASSETTE_DIR = Path(__file__).resolve().parents[1] / "cassettes" / "vessels"
KAILUA = GeoPoint(lat=19.64, lon=-155.99)
# The versions ":latest" resolved to when the Kona cassette was recorded.
SAR = "public-global-sar-presence:v5.0"
EFFORT = "public-global-fishing-effort:v5.0"


@pytest.fixture
def vcr_cassette_dir() -> str:
    return str(CASSETTE_DIR)


@pytest.fixture
def vcr_config() -> dict[str, Any]:
    return {"filter_headers": ["authorization"], "decode_compressed_response": True}


@pytest.fixture(autouse=True)
def _fast_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vessels, "LAST_REPORT_POLL_SECONDS", 0.0)


def _report(dataset: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"total": len(rows), "entries": [{dataset: rows}]}


def _zipped(data: Any) -> bytes:
    """Pack data into an in-memory zip archive, as GFW returns format=JSON."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.json", json.dumps(data).encode("utf-8"))
    return buf.getvalue()


def _respond(data: Any) -> httpx.Response:
    return httpx.Response(200, content=_zipped(data), headers={"Content-Type": "application/zip"})


EMPTY_SAR = _report(SAR, [])
EMPTY_EFFORT = _report(EFFORT, [])


async def _create_test_site(store: Store, site_id: str, location: GeoPoint = KAILUA) -> Site:
    site = Site(id=site_id, name="Kailua Bay", location=location, created_at=datetime.now(UTC))
    await store.sites.save(site)
    return site


def _params(site_id: str, radius_km: float = 10.0) -> VesselActivityParams:
    return VesselActivityParams(
        site_id=site_id, radius_km=radius_km, start=date(2025, 1, 1), end=date(2025, 1, 31)
    )


@pytest.mark.asyncio
async def test_vessel_activity_success(store: Store, make_settings: Any) -> None:
    """AC 1: Returns sar_detections.total, unmatched_to_ais with points, and fishing_hours."""
    site = await _create_test_site(store, "site_ac1")
    settings = make_settings(gfw_token="test_gfw_token")

    sar_total = _report(
        SAR,
        [
            {"date": "2025", "detections": 7, "flag": "USA", "lat": 19.64, "lon": -155.99},
            {"date": "2025", "detections": 3, "flag": None, "lat": 19.65, "lon": -155.98},
            {"date": "2025", "detections": 2, "flag": None, "lat": 19.63, "lon": -155.97},
        ],
    )
    sar_unmatched = _report(
        SAR,
        [
            {"date": "2025", "detections": 3, "flag": None, "lat": 19.65, "lon": -155.98},
            {"date": "2025", "detections": 2, "flag": None, "lat": 19.63, "lon": -155.97},
        ],
    )
    effort = _report(
        EFFORT,
        [
            {"date": "2025", "flag": "USA", "hours": 15.5, "lat": 19.64, "lon": -155.99},
            {"date": "2025", "flag": "JPN", "hours": 27.0, "lat": 19.62, "lon": -156.01},
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer test_gfw_token"
        assert request.method == "POST"
        assert str(request.url).startswith(GFW_REPORT_URL)
        assert "geojson" in json.loads(request.content)
        query = request.url.params
        assert query["format"] == "JSON"
        assert query["group-by"] == "FLAG"
        assert query["date-range"] == "2025-01-01,2025-01-31"
        if query.get("filters[0]") == "matched='false'":
            return _respond(sar_unmatched)
        if query["datasets[0]"] == "public-global-fishing-effort:latest":
            return _respond(effort)
        assert query["datasets[0]"] == "public-global-sar-presence:latest"
        return _respond(sar_total)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=settings)
        result = await vessel_activity(_params(site.id, radius_km=15.0), ctx)

    assert isinstance(result, ToolResult)
    assert result.tool == "vessel_activity"
    assert result.source_url == GFW_REPORT_URL
    assert result.id.startswith("tr_")
    assert result.data == {
        "sar_detections": {
            "total": 12,
            "unmatched_to_ais": {
                "count": 5,
                "points": [{"lat": 19.63, "lon": -155.97}, {"lat": 19.65, "lon": -155.98}],
            },
        },
        "fishing_hours": 42.5,
    }


@pytest.mark.asyncio
async def test_rows_across_several_entries_are_summed(store: Store, make_settings: Any) -> None:
    """A report may split rows over several entries; every one counts."""
    site = await _create_test_site(store, "site_multi")
    split = {
        "total": 2,
        "entries": [
            {SAR: [{"detections": 4, "lat": 19.6, "lon": -156.0}]},
            {SAR: [{"detections": 1, "lat": 19.7, "lon": -156.0}]},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["datasets[0]"].startswith("public-global-fishing-effort"):
            return _respond(EMPTY_EFFORT)
        return _respond(split)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings(gfw_token="t"))
        result = await vessel_activity(_params(site.id), ctx)

    assert result.data["sar_detections"]["total"] == 5
    assert result.data["sar_detections"]["unmatched_to_ais"]["count"] == 5
    assert result.data["fishing_hours"] == 0.0


@pytest.mark.asyncio
async def test_unexpected_report_shape_raises(store: Store, make_settings: Any) -> None:
    """A payload without an entries list is an error, not a silent zero."""
    site = await _create_test_site(store, "site_shape")

    def handler(request: httpx.Request) -> httpx.Response:
        return _respond({"data": [{"count": 12}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings(gfw_token="t"))
        with pytest.raises(ExternalServiceError, match="entries"):
            await vessel_activity(_params(site.id), ctx)


@pytest.mark.asyncio
async def test_radius_validation_fails_before_http(store: Store, make_settings: Any) -> None:
    """AC 2: When radius_km > 20, validation fails before any HTTP call."""
    site = await _create_test_site(store, "site_ac2")
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings(gfw_token="t"))

        with pytest.raises(ValidationError):
            _params(site.id, radius_km=25.0)

        with pytest.raises(ValidationError):
            await registry.call(
                "vessel_activity",
                {"site_id": site.id, "radius_km": 20.1, "start": "2025-01-01", "end": "2025-01-31"},
                ctx,
            )

    assert requests_seen == []


@pytest.mark.asyncio
async def test_missing_token_fails_before_http(store: Store, make_settings: Any) -> None:
    site = await _create_test_site(store, "site_notoken")
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings())
        with pytest.raises(ConfigError, match="REEFCASE_GFW_TOKEN"):
            await vessel_activity(_params(site.id), ctx)

    assert requests_seen == []


@pytest.mark.asyncio
async def test_result_serialization_anonymizes_vessels(store: Store, make_settings: Any) -> None:
    """AC 3: When serialized, contains no vessel names, MMSI, or IMO numbers."""
    site = await _create_test_site(store, "site_ac3")
    # Vessel-grouped rows carry identity fields; none may leave the tool.
    identified = {
        "detections": 1,
        "lat": 19.64,
        "lon": -155.99,
        "shipName": "SECRET_NAME_TITANIC",
        "mmsi": "999888777",
        "imo": "1234567",
        "callsign": "TOPSECRET",
        "vesselId": "abc-123-vessel",
        "vesselIDs": 1,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["datasets[0]"].startswith("public-global-fishing-effort"):
            return _respond(_report(EFFORT, [{**identified, "hours": 2.0}]))
        return _respond(_report(SAR, [identified]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings(gfw_token="t"))
        result = await vessel_activity(_params(site.id), ctx)

    serialized = result.model_dump_json()
    for leaked in ("SECRET_NAME_TITANIC", "999888777", "1234567", "TOPSECRET", "abc-123-vessel"):
        assert leaked not in serialized
    for key in ("shipName", "mmsi", "imo", "callsign", "vesselId", "vesselIDs"):
        assert key not in serialized


@pytest.mark.asyncio
async def test_concurrent_calls_serialized_and_524_recovered(
    store: Store, make_settings: Any
) -> None:
    """AC 4: Two concurrent calls serialize, and 524 recovers via last-report."""
    site = await _create_test_site(store, "site_ac4")

    active_reports = 0
    max_concurrent_reports = 0
    timed_out = False
    polls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active_reports, max_concurrent_reports, timed_out, polls
        url = str(request.url)

        if url.startswith(GFW_REPORT_URL):
            active_reports += 1
            max_concurrent_reports = max(max_concurrent_reports, active_reports)
            await asyncio.sleep(0.05)
            active_reports -= 1
            dataset = request.url.params["datasets[0]"]
            if dataset.startswith("public-global-fishing-effort") and not timed_out:
                timed_out = True
                return httpx.Response(524, content=b"Gateway Timeout")
            return _respond(EMPTY_EFFORT if "fishing-effort" in dataset else EMPTY_SAR)

        if url.startswith(GFW_LAST_REPORT_URL):
            assert request.method == "GET"
            polls += 1
            if polls < 3:
                return httpx.Response(
                    200,
                    json={"uri": "/v3/4wings/report?...", "status": "running", "lastUpdate": "x"},
                )
            return _respond(_report(EFFORT, [{"hours": 10.0, "lat": 19.64, "lon": -155.99}]))

        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings(gfw_token="t"))
        res1, res2 = await asyncio.gather(
            vessel_activity(_params(site.id, radius_km=5.0), ctx),
            vessel_activity(_params(site.id, radius_km=10.0), ctx),
        )

    assert max_concurrent_reports == 1
    assert polls == 3  # two "running" answers, then the finished report
    assert sorted([res1.data["fishing_hours"], res2.data["fishing_hours"]]) == [0.0, 10.0]


@pytest.mark.asyncio
async def test_failed_report_after_524_raises(store: Store, make_settings: Any) -> None:
    site = await _create_test_site(store, "site_524_fail")

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(GFW_LAST_REPORT_URL):
            return httpx.Response(200, json={"message": {"detail": "boom"}, "status": 422})
        return httpx.Response(524)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings(gfw_token="t"))
        with pytest.raises(ExternalServiceError, match="422") as excinfo:
            await vessel_activity(_params(site.id), ctx)

    assert excinfo.value.status_code == 422


@pytest.mark.asyncio
async def test_report_still_running_gives_up(
    store: Store, make_settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vessels, "LAST_REPORT_MAX_POLLS", 2)
    site = await _create_test_site(store, "site_524_slow")

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(GFW_LAST_REPORT_URL):
            return httpx.Response(200, json={"status": "running"})
        return httpx.Response(524)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings(gfw_token="t"))
        with pytest.raises(ExternalServiceError, match="still running"):
            await vessel_activity(_params(site.id), ctx)


@pytest.mark.asyncio
async def test_unknown_site_raises_not_found(store: Store, make_settings: Any) -> None:
    """Querying an unknown site_id raises NotFoundError."""
    async with httpx.AsyncClient() as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings(gfw_token="t"))
        with pytest.raises(NotFoundError):
            await vessel_activity(_params("site_nonexistent"), ctx)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_recorded_report_kona(store: Store, make_settings: Any, record_mode: str) -> None:
    """Replay a real GFW response (three reports, 20 km around Kailua-Kona, all of 2024)."""
    if record_mode == "none" and not (CASSETTE_DIR / "test_recorded_report_kona.yaml").is_file():
        pytest.skip("cassette not recorded yet; see ops/lead-d/handoff.md")
    token = os.environ.get("REEFCASE_GFW_TOKEN", "replayed-token")
    site = await _create_test_site(store, "site_kona_live")
    params = VesselActivityParams(
        site_id=site.id, radius_km=20.0, start=date(2024, 1, 1), end=date(2024, 12, 31)
    )

    async with httpx.AsyncClient(timeout=120.0) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=make_settings(gfw_token=token))
        result = await vessel_activity(params, ctx)

    # Recorded 2026-10-30: 29 SAR rows, 10 unmatched rows, 69 fishing-effort rows.
    sar = result.data["sar_detections"]
    assert sar["total"] == 34
    assert sar["unmatched_to_ais"]["count"] == 11
    assert len(sar["unmatched_to_ais"]["points"]) == 10
    assert result.data["fishing_hours"] == pytest.approx(98.99)
    for point in sar["unmatched_to_ais"]["points"]:
        assert set(point) == {"lat", "lon"}
        # Every cell centre lies within the 20 km circle (plus half a 0.01° cell).
        dlat = math.radians(point["lat"] - KAILUA.lat)
        dlon = math.radians(point["lon"] - KAILUA.lon) * math.cos(math.radians(KAILUA.lat))
        assert 6371.0 * math.hypot(dlat, dlon) <= 21.0
