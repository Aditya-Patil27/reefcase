"""Tests for Story 4.3 — vessel_activity (Global Fishing Watch).

AC 1: Given a site, radius_km <= 20 and a date range, vessel_activity returns
      sar_detections.total, sar_detections.unmatched_to_ais with points, and fishing_hours.
AC 2: Given radius_km > 20, validation fails before any HTTP call.
AC 3: Serialized result contains no vessel names, MMSI, or IMO numbers.
AC 4: Two concurrent calls are requested one at a time via asyncio.Semaphore(1),
      and a 524 status is recovered via the last-report endpoint.
"""

from __future__ import annotations

import asyncio
import io
import json
import zipfile
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from reefcase.core.errors import NotFoundError
from reefcase.core.schemas import GeoPoint, Site, ToolResult
from reefcase.store.db import Store
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import registry
from reefcase.tools.vessels import (
    GFW_LAST_REPORT_URL,
    GFW_REPORT_URL,
    VesselActivityParams,
    vessel_activity,
)


def _make_zip_payload(data: Any) -> bytes:
    """Pack data into an in-memory zip archive containing report.json."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.json", json.dumps(data).encode("utf-8"))
    return buf.getvalue()


async def _create_test_site(store: Store, site_id: str = "site_01") -> Site:
    site = Site(
        id=site_id,
        name="Kailua Bay",
        location=GeoPoint(lat=19.64, lon=-155.99),
        created_at=datetime.now(UTC),
    )
    await store.sites.save(site)
    return site


@pytest.mark.asyncio
async def test_vessel_activity_success(store: Store, make_settings: Any) -> None:
    """AC 1: Returns sar_detections.total, unmatched_to_ais with points, and fishing_hours."""
    site = await _create_test_site(store, "site_ac1")
    settings = make_settings(gfw_token="test_gfw_token")

    total_sar_payload = {
        "entries": [
            {"count": 12, "flag": "USA"},
        ],
        "total": 12,
    }
    unmatched_sar_payload = {
        "entries": [
            {
                "lat": 19.641,
                "lon": -155.991,
                "matched": False,
                "vessel_name": "SENSITIVE_VESSEL_1",
                "mmsi": "111222333",
            },
            {
                "lat": 19.645,
                "lon": -155.985,
                "matched": False,
                "mmsi": "444555666",
            },
        ],
        "total": 2,
    }
    fishing_effort_payload = {
        "entries": [
            {"hours": 15.5, "flag": "USA"},
            {"hours": 27.0, "flag": "JPN"},
        ]
    }

    def transport_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        assert request.headers.get("authorization") == "Bearer test_gfw_token"
        assert request.method == "POST"
        body = json.loads(request.content)
        assert "geojson" in body

        if "filters" in url_str or "matched" in url_str:
            return httpx.Response(
                200,
                content=_make_zip_payload(unmatched_sar_payload),
                headers={"Content-Type": "application/zip"},
            )
        elif "public-global-fishing-effort" in url_str:
            return httpx.Response(
                200,
                content=_make_zip_payload(fishing_effort_payload),
                headers={"Content-Type": "application/zip"},
            )
        elif "public-global-sar-presence" in url_str:
            return httpx.Response(
                200,
                content=_make_zip_payload(total_sar_payload),
                headers={"Content-Type": "application/zip"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(transport_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=settings)
        params = VesselActivityParams(
            site_id=site.id,
            radius_km=15.0,
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
        )
        result = await vessel_activity(params, ctx)

    assert isinstance(result, ToolResult)
    assert result.tool == "vessel_activity"
    assert result.source_url == GFW_REPORT_URL
    assert result.id.startswith("tr_")

    data = result.data
    assert "sar_detections" in data
    assert data["sar_detections"]["total"] == 12

    unmatched = data["sar_detections"]["unmatched_to_ais"]
    assert unmatched["count"] == 2
    assert len(unmatched["points"]) == 2
    assert unmatched["points"][0] == {"lat": 19.641, "lon": -155.991}
    assert unmatched["points"][1] == {"lat": 19.645, "lon": -155.985}

    assert data["fishing_hours"] == 42.5


@pytest.mark.asyncio
async def test_radius_validation_fails_before_http(store: Store, make_settings: Any) -> None:
    """AC 2: When radius_km > 20, validation fails before any HTTP call."""
    site = await _create_test_site(store, "site_ac2")
    settings = make_settings()

    requests_seen: list[httpx.Request] = []

    def transport_handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200)

    transport = httpx.MockTransport(transport_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=settings)

        # 1. Direct model instantiation fails
        with pytest.raises(ValidationError):
            VesselActivityParams(
                site_id=site.id,
                radius_km=25.0,
                start=date(2025, 1, 1),
                end=date(2025, 1, 31),
            )

        # 2. Registry call with dict params fails validation before HTTP
        with pytest.raises(ValidationError):
            await registry.call(
                "vessel_activity",
                {
                    "site_id": site.id,
                    "radius_km": 20.1,
                    "start": "2025-01-01",
                    "end": "2025-01-31",
                },
                ctx,
            )

    assert len(requests_seen) == 0


@pytest.mark.asyncio
async def test_result_serialization_anonymizes_vessels(store: Store, make_settings: Any) -> None:
    """AC 3: When serialized, contains no vessel names, MMSI, or IMO numbers."""
    site = await _create_test_site(store, "site_ac3")
    settings = make_settings(gfw_token="token")

    sar_unmatched_with_pii = {
        "entries": [
            {
                "lat": 19.64,
                "lon": -155.99,
                "vessel_name": "SECRET_NAME_TITANIC",
                "mmsi": "999888777",
                "imo": "1234567",
                "shipname": "TOP_SECRET_BOAT",
            }
        ],
        "total": 1,
    }

    def transport_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "filters[0]=matched" in url_str:
            return httpx.Response(200, content=_make_zip_payload(sar_unmatched_with_pii))
        return httpx.Response(200, content=_make_zip_payload({"entries": [], "total": 0}))

    transport = httpx.MockTransport(transport_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=settings)
        params = VesselActivityParams(
            site_id=site.id,
            radius_km=10.0,
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
        )
        result = await vessel_activity(params, ctx)

    serialized = result.model_dump_json()
    assert "SECRET_NAME_TITANIC" not in serialized
    assert "999888777" not in serialized
    assert "1234567" not in serialized
    assert "TOP_SECRET_BOAT" not in serialized
    assert "vessel_name" not in serialized
    assert "mmsi" not in serialized
    assert "imo" not in serialized
    assert "shipname" not in serialized


@pytest.mark.asyncio
async def test_concurrent_calls_serialized_and_524_recovered(
    store: Store, make_settings: Any
) -> None:
    """AC 4: Two concurrent calls serialize, and 524 recovers via last-report."""
    site = await _create_test_site(store, "site_ac4")
    settings = make_settings(gfw_token="test_token")

    active_reports = 0
    max_concurrent_reports = 0
    recovered_524 = False

    async def transport_handler(request: httpx.Request) -> httpx.Response:
        nonlocal active_reports, max_concurrent_reports, recovered_524
        url_str = str(request.url)

        if url_str.startswith(GFW_REPORT_URL):
            active_reports += 1
            if active_reports > max_concurrent_reports:
                max_concurrent_reports = active_reports
            await asyncio.sleep(0.05)
            active_reports -= 1

            # Simulate 524 for public-global-fishing-effort on first call
            if "public-global-fishing-effort" in url_str and not recovered_524:
                return httpx.Response(524, content=b"Gateway Timeout")

            return httpx.Response(200, content=_make_zip_payload({"entries": [], "total": 0}))

        elif url_str.startswith(GFW_LAST_REPORT_URL):
            assert request.method == "GET"
            recovered_524 = True
            return httpx.Response(
                200, content=_make_zip_payload({"entries": [{"hours": 10.0}], "total": 1})
            )

        return httpx.Response(404)

    transport = httpx.MockTransport(transport_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        ctx = ToolContext(http=http_client, store=store, settings=settings)

        params1 = VesselActivityParams(
            site_id=site.id,
            radius_km=5.0,
            start=date(2025, 1, 1),
            end=date(2025, 1, 10),
        )
        params2 = VesselActivityParams(
            site_id=site.id,
            radius_km=10.0,
            start=date(2025, 1, 11),
            end=date(2025, 1, 20),
        )

        res1, res2 = await asyncio.gather(
            vessel_activity(params1, ctx),
            vessel_activity(params2, ctx),
        )

    assert max_concurrent_reports <= 1
    assert recovered_524 is True
    assert res1.data["fishing_hours"] == 10.0 or res2.data["fishing_hours"] == 10.0


@pytest.mark.asyncio
async def test_unknown_site_raises_not_found(store: Store, make_settings: Any) -> None:
    """Querying an unknown site_id raises NotFoundError."""
    settings = make_settings()
    ctx = ToolContext(http=httpx.AsyncClient(), store=store, settings=settings)
    params = VesselActivityParams(
        site_id="site_nonexistent",
        radius_km=5.0,
        start=date(2025, 1, 1),
        end=date(2025, 1, 10),
    )
    with pytest.raises(NotFoundError):
        await vessel_activity(params, ctx)
