"""Tool for querying vessel activity from Global Fishing Watch API v3 (architecture §5.4, §9.1).

Queries SAR detections (total and unmatched-to-AIS) and apparent fishing effort
around a site within radius_km (<= 20 km) for a date range. Holds a process-wide
asyncio.Semaphore(1) to respect GFW concurrency limits, recovers 524 timeouts by polling
the last-report endpoint, and reads only counts and cell centres from report rows, so no
vessel names, MMSI, or IMO numbers are returned.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import zipfile
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any, cast

import httpx
from pydantic import Field

from reefcase.core.errors import ConfigError, ExternalServiceError
from reefcase.core.ids import TOOL_RESULT, new_id
from reefcase.core.schemas import ToolResult
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import ToolParams, tool

__all__ = [
    "GFW_LAST_REPORT_URL",
    "GFW_REPORT_URL",
    "GFW_SEMAPHORE",
    "VesselActivityParams",
    "vessel_activity",
]

GFW_REPORT_URL: str = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
GFW_LAST_REPORT_URL: str = "https://gateway.api.globalfishingwatch.org/v3/4wings/last-report"

# GFW limits users to one concurrent report; hold a process-wide semaphore (§5.4).
GFW_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(1)

# After a 524, poll last-report for up to 10 minutes (GFW keeps it for 30).
LAST_REPORT_POLL_SECONDS: float = 10.0
LAST_REPORT_MAX_POLLS: int = 60

_EARTH_RADIUS_KM: float = 6371.0088


class VesselActivityParams(ToolParams):
    """Parameters for vessel_activity tool."""

    site_id: str
    radius_km: float = Field(le=20.0, gt=0.0)
    start: date
    end: date


def _circle_polygon_feature_collection(
    lat: float, lon: float, radius_km: float, n_points: int = 32
) -> dict[str, Any]:
    """Generate GeoJSON FeatureCollection approximating a circle of radius_km around (lat, lon)."""
    phi1 = math.radians(lat)
    lambda1 = math.radians(lon)
    d_div_r = radius_km / _EARTH_RADIUS_KM

    ring: list[list[float]] = []
    for i in range(n_points):
        theta = 2.0 * math.pi * i / n_points
        sin_phi2 = math.sin(phi1) * math.cos(d_div_r) + math.cos(phi1) * math.sin(
            d_div_r
        ) * math.cos(theta)
        phi2 = math.asin(sin_phi2)
        y = math.sin(theta) * math.sin(d_div_r) * math.cos(phi1)
        x = math.cos(d_div_r) - math.sin(phi1) * math.sin(phi2)
        lambda2 = lambda1 + math.atan2(y, x)

        pt_lon = round(math.degrees(lambda2), 6)
        pt_lat = round(math.degrees(phi2), 6)
        ring.append([pt_lon, pt_lat])

    # Close the polygon ring
    ring.append(ring[0])

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [ring],
                },
            }
        ],
    }


def _extract_json_from_response(content: bytes) -> object:
    """Extract JSON payload from raw content, supporting in-memory zip archives."""
    if content.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                if name.endswith(".json"):
                    return json.loads(zf.read(name).decode("utf-8"))
            first = zf.namelist()[0]
            return json.loads(zf.read(first).decode("utf-8"))
    return json.loads(content.decode("utf-8"))


async def _fetch_gfw_report(
    ctx: ToolContext,
    query_params: Mapping[str, str],
    geojson_fc: dict[str, Any],
    headers: Mapping[str, str],
) -> object:
    """POST to GFW report endpoint with semaphore lock and 524 recovery."""
    async with GFW_SEMAPHORE:
        try:
            response = await ctx.http.post(
                GFW_REPORT_URL,
                params=query_params,
                json={"geojson": geojson_fc},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            msg = f"POST {GFW_REPORT_URL} failed: {exc}"
            raise ExternalServiceError(msg, url=GFW_REPORT_URL) from exc

        # Reports taking >100s return 524 but keep running; poll last-report (§9.1).
        if response.status_code == 524:
            return await _await_last_report(ctx, headers)

        if not response.is_success:
            raise ExternalServiceError(
                f"POST {GFW_REPORT_URL} returned {response.status_code}",
                status_code=response.status_code,
                url=str(response.request.url),
            )

        return _extract_json_from_response(response.content)


async def _await_last_report(ctx: ToolContext, headers: Mapping[str, str]) -> object:
    """Poll last-report until the timed-out report finishes.

    It answers ``{"status": "running", ...}`` while the report runs, the report body once it
    is done, and ``{"status": <code>, "message": ...}`` if the report failed.
    """
    for _ in range(LAST_REPORT_MAX_POLLS):
        await asyncio.sleep(LAST_REPORT_POLL_SECONDS)
        try:
            response = await ctx.http.get(GFW_LAST_REPORT_URL, headers=headers)
        except httpx.HTTPError as exc:
            msg = f"GET {GFW_LAST_REPORT_URL} after 524 failed: {exc}"
            raise ExternalServiceError(msg, status_code=524, url=GFW_LAST_REPORT_URL) from exc
        if not response.is_success:
            raise ExternalServiceError(
                f"GET {GFW_LAST_REPORT_URL} returned {response.status_code}",
                status_code=response.status_code,
                url=GFW_LAST_REPORT_URL,
            )
        payload = _extract_json_from_response(response.content)
        fields = _fields(payload)
        status = fields.get("status")
        if status == "running":
            continue
        if status is not None:
            message = fields.get("message")
            raise ExternalServiceError(
                f"GFW report failed ({status}): {message}",
                status_code=status if isinstance(status, int) else None,
                url=GFW_LAST_REPORT_URL,
            )
        return payload
    raise ExternalServiceError(
        f"GFW report still running after {LAST_REPORT_MAX_POLLS} polls",
        status_code=524,
        url=GFW_LAST_REPORT_URL,
    )


def _fields(payload: object) -> dict[str, object]:
    """A JSON object's fields, or none for any other JSON value."""
    return cast(dict[str, object], payload) if isinstance(payload, dict) else {}


def _report_rows(payload: object) -> list[dict[str, object]]:
    """Flatten a 4Wings report, ``{"total": n, "entries": [{"<dataset>:vN": [row, ...]}]}``.

    Each row is one grid cell (and flag), e.g. ``{"lat", "lon", "flag", "detections"}`` for SAR
    or ``{"lat", "lon", "flag", "hours", "vesselIDs"}`` for fishing effort.
    """
    entries = _fields(payload).get("entries")
    if not isinstance(entries, list):
        raise ExternalServiceError("GFW report has no entries list", url=GFW_REPORT_URL)
    rows: list[dict[str, object]] = []
    for entry in cast(list[object], entries):
        if not isinstance(entry, dict):
            continue
        for dataset_rows in cast(dict[str, object], entry).values():
            if isinstance(dataset_rows, list):
                rows.extend(
                    cast(dict[str, object], row)
                    for row in cast(list[object], dataset_rows)
                    if isinstance(row, dict)
                )
    return rows


def _number(row: Mapping[str, object], key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def _sum(rows: list[dict[str, object]], key: str) -> float:
    return sum(_number(row, key) for row in rows)


def _cell_points(rows: list[dict[str, object]]) -> list[dict[str, float]]:
    """Distinct grid-cell centres with detections; no other row field leaves this module."""
    cells: set[tuple[float, float]] = set()
    for row in rows:
        lat, lon = row.get("lat"), row.get("lon")
        has_cell = isinstance(lat, int | float) and isinstance(lon, int | float)
        if has_cell and _number(row, "detections") > 0:
            cells.add((float(cast(float, lat)), float(cast(float, lon))))
    return [{"lat": lat, "lon": lon} for lat, lon in sorted(cells)]


@tool(
    "vessel_activity",
    VesselActivityParams,
    description="Global Fishing Watch SAR detections and fishing effort",
)
async def vessel_activity(params: VesselActivityParams, ctx: ToolContext) -> ToolResult:
    """Query SAR detections and fishing effort near the site from GFW API v3."""
    site = await ctx.store.sites.get(params.site_id)
    if ctx.settings.gfw_token is None:
        raise ConfigError("REEFCASE_GFW_TOKEN is not configured")

    geojson_fc = _circle_polygon_feature_collection(
        lat=site.location.lat,
        lon=site.location.lon,
        radius_km=params.radius_km,
    )

    headers = {"Authorization": f"Bearer {ctx.settings.gfw_token.get_secret_value()}"}

    start_str = params.start.isoformat()
    end_str = params.end.isoformat()
    date_range = f"{start_str},{end_str}"

    base_query = {
        "format": "JSON",
        "group-by": "FLAG",
        "temporal-resolution": "ENTIRE",
        "spatial-resolution": "HIGH",
        "date-range": date_range,
    }

    # 1. Total SAR presence
    sar_total_query = {
        **base_query,
        "datasets[0]": "public-global-sar-presence:latest",
    }
    sar_rows = _report_rows(await _fetch_gfw_report(ctx, sar_total_query, geojson_fc, headers))

    # 2. Unmatched-to-AIS SAR presence (matched='false')
    sar_unmatched_query = {
        **base_query,
        "datasets[0]": "public-global-sar-presence:latest",
        "filters[0]": "matched='false'",
    }
    unmatched_rows = _report_rows(
        await _fetch_gfw_report(ctx, sar_unmatched_query, geojson_fc, headers)
    )

    # 3. Fishing effort
    fishing_query = {
        **base_query,
        "datasets[0]": "public-global-fishing-effort:latest",
    }
    fishing_rows = _report_rows(await _fetch_gfw_report(ctx, fishing_query, geojson_fc, headers))

    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool="vessel_activity",
        params=params.model_dump(mode="json"),
        data={
            "sar_detections": {
                "total": int(_sum(sar_rows, "detections")),
                "unmatched_to_ais": {
                    "count": int(_sum(unmatched_rows, "detections")),
                    "points": _cell_points(unmatched_rows),
                },
            },
            "fishing_hours": round(_sum(fishing_rows, "hours"), 2),
        },
        source_url=GFW_REPORT_URL,
        retrieved_at=datetime.now(UTC),
    )
