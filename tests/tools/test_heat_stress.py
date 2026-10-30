"""Story 4.2 — heat_stress (NOAA Coral Reef Watch via PacIOOS ERDDAP, §9.2)."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

import reefcase.tools.heat_stress as heat_module
from reefcase.core.errors import ExternalServiceError
from reefcase.core.schemas import GeoPoint, Site
from reefcase.store.db import Store
from reefcase.tools.heat_stress import ERDDAP_URL, HeatStressParams, heat_stress
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import registry

KONA = GeoPoint(lat=19.64, lon=-155.99)  # reef off Kailua-Kona, Hawaii
LAND = GeoPoint(lat=19.6, lon=-155.5)  # Mauna Loa's flank
HEATWAVE = HeatStressParams(site_id="site_kona", start=date(2019, 8, 1), end=date(2019, 10, 29))


@pytest.fixture
def vcr_cassette_dir() -> str:
    return str(Path(__file__).resolve().parents[1] / "cassettes" / "heat_stress")


@pytest.fixture
def vcr_config() -> dict[str, Any]:
    return {"decode_compressed_response": True}  # readable YAML bodies


async def _site(store: Store, site_id: str, location: GeoPoint) -> None:
    await store.sites.save(
        Site(id=site_id, name="Test Reef", location=location, created_at=datetime.now(UTC))
    )


def _ctx(store: Store, settings: Any, transport: httpx.AsyncBaseTransport | None = None):
    client = httpx.AsyncClient(transport=transport, timeout=60.0)
    return ToolContext(http=client, store=store, settings=settings)


def _mock(status: int, payload: Any, seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if isinstance(payload, str):
            return httpx.Response(status, text=payload)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_ninety_day_window_returns_daily_series_and_max(store: Store, make_settings) -> None:
    await _site(store, "site_kona", KONA)

    result = await heat_stress(HEATWAVE, _ctx(store, make_settings()))

    data = result.data
    assert data["available"] is True
    assert (data["lat"], data["lon"]) == (19.625, -155.975)  # snapped 5 km cell
    assert len(data["daily"]) == 90
    assert data["daily"][0]["date"] == "2019-08-01"
    assert data["daily"][-1]["date"] == "2019-10-29"
    assert set(data["daily"][0]) == {"date", "dhw", "sst_anomaly", "alert_level"}
    dhws = [day["dhw"] for day in data["daily"] if day["dhw"] is not None]
    assert data["max_dhw"] == max(dhws)
    assert data["max_dhw"] > 4  # the 2019 Hawaii heatwave
    peak = next(day for day in data["daily"] if day["dhw"] == data["max_dhw"])
    assert data["max_dhw_date"] == peak["date"]

    assert result.tool == "heat_stress"
    assert result.params == HEATWAVE.model_dump(mode="json")
    assert result.id.startswith("tr_")
    assert result.source_url.startswith(f"{ERDDAP_URL}?CRW_DHW%5B(2019-08-01):1:(2019-10-29)%5D")
    for var in ("CRW_DHW", "CRW_SSTANOMALY", "CRW_BAA"):
        assert var in result.source_url


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_land_cell_is_unavailable_not_an_error(store: Store, make_settings) -> None:
    await _site(store, "site_land", LAND)
    params = HeatStressParams(site_id="site_land", start=date(2019, 9, 1), end=date(2019, 9, 7))

    result = await heat_stress(params, _ctx(store, make_settings()))

    assert result.data["available"] is False
    assert "reason" in result.data


@pytest.mark.asyncio
async def test_window_outside_coverage_is_unavailable(store: Store, make_settings) -> None:
    await _site(store, "site_kona", KONA)
    seen: list[httpx.Request] = []
    transport = _mock(404, 'Error {\n    code=404;\n    message="Not Found: ...";\n}', seen)
    params = HeatStressParams(site_id="site_kona", start=date(1980, 1, 1), end=date(1980, 2, 1))

    result = await heat_stress(params, _ctx(store, make_settings(), transport))

    assert result.data["available"] is False
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_recent_end_asks_erddap_for_its_last_day(
    store: Store, make_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _site(store, "site_kona", KONA)
    monkeypatch.setattr(heat_module, "_today", lambda: date(2026, 10, 30))
    seen: list[httpx.Request] = []
    rows = [["2026-10-28T12:00:00Z", 19.625, -155.975, 0.6, 0.4, 0]]
    payload = {"table": {"columnNames": [], "rows": rows}}
    params = HeatStressParams(site_id="site_kona", start=date(2026, 10, 1), end=date(2026, 10, 29))

    result = await heat_stress(params, _ctx(store, make_settings(), _mock(200, payload, seen)))

    assert "(2026-10-01):1:(last)" in str(seen[0].url).replace("%28", "(").replace("%29", ")")
    assert result.source_url == str(seen[0].url)
    assert result.data["daily"] == [
        {"date": "2026-10-28", "dhw": 0.6, "sst_anomaly": 0.4, "alert_level": 0}
    ]


@pytest.mark.asyncio
async def test_server_error_raises(store: Store, make_settings) -> None:
    await _site(store, "site_kona", KONA)
    seen: list[httpx.Request] = []
    with pytest.raises(ExternalServiceError):
        await heat_stress(HEATWAVE, _ctx(store, make_settings(), _mock(500, "boom", seen)))


def test_params_reject_reversed_or_oversized_windows() -> None:
    with pytest.raises(ValidationError):
        HeatStressParams(site_id="s", start=date(2019, 9, 2), end=date(2019, 9, 1))
    with pytest.raises(ValidationError):
        HeatStressParams(
            site_id="s", start=date(2019, 1, 1), end=date(2019, 1, 1) + timedelta(days=367)
        )


@pytest.mark.asyncio
async def test_registered_and_cached_through_the_registry(store: Store, make_settings) -> None:
    await _site(store, "site_kona", KONA)
    seen: list[httpx.Request] = []
    rows = [["2019-09-01T12:00:00Z", 19.625, -155.975, 2.68, 1.59, 2]]
    ctx = _ctx(store, make_settings(), _mock(200, {"table": {"rows": rows}}, seen))
    params = {"site_id": "site_kona", "start": "2019-09-01", "end": "2019-09-01"}

    first = await registry.call("heat_stress", params, ctx)
    second = await registry.call("heat_stress", params, ctx)

    assert "heat_stress" in registry.names()
    assert first == second
    assert len(seen) == 1
    assert first.data["max_dhw"] == 2.68


@pytest.mark.asyncio
async def test_body_without_table_rows_raises(store: Store, make_settings) -> None:
    await _site(store, "site_kona", KONA)
    seen: list[httpx.Request] = []
    with pytest.raises(ExternalServiceError, match="no table rows"):
        await heat_stress(HEATWAVE, _ctx(store, make_settings(), _mock(200, {"x": 1}, seen)))
