"""Tool for querying vessel activity from Global Fishing Watch API v3 (architecture §5.4, §9.1).

Queries SAR detections (total and unmatched-to-AIS) and apparent fishing effort
around a site within radius_km (<= 20 km) for a date range. Holds a process-wide
asyncio.Semaphore(1) to respect GFW concurrency limits, recovers 524 timeouts via
the last-report endpoint, and ensures no vessel names, MMSI, or IMO numbers are returned.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import math
import zipfile
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any, cast

import httpx
from pydantic import Field

from reefcase.core.errors import ExternalServiceError
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

        # Reports taking >100s return 524; retrieve through last-report (§9.1)
        if response.status_code == 524:
            try:
                last_report_resp = await ctx.http.get(GFW_LAST_REPORT_URL, headers=headers)
            except httpx.HTTPError as exc:
                msg = f"GET {GFW_LAST_REPORT_URL} after 524 failed: {exc}"
                raise ExternalServiceError(
                    msg,
                    status_code=524,
                    url=GFW_LAST_REPORT_URL,
                ) from exc

            if not last_report_resp.is_success:
                raise ExternalServiceError(
                    f"GET {GFW_LAST_REPORT_URL} returned {last_report_resp.status_code}",
                    status_code=last_report_resp.status_code,
                    url=GFW_LAST_REPORT_URL,
                )
            return _extract_json_from_response(last_report_resp.content)

        if not response.is_success:
            raise ExternalServiceError(
                f"POST {GFW_REPORT_URL} returned {response.status_code}",
                status_code=response.status_code,
                url=str(response.request.url),
            )

        return _extract_json_from_response(response.content)


def _extract_dict(val: object) -> dict[str, object] | None:
    """Safely narrow an object to a dict[str, object]."""
    if isinstance(val, dict):
        d: dict[str, object] = {}
        for k, v in cast(dict[object, object], val).items():
            if isinstance(k, str):
                d[k] = v
        return d
    return None


def _get_entries(payload: object) -> list[dict[str, object]]:
    payload_dict = _extract_dict(payload)
    if payload_dict is not None:
        entries_val = (
            payload_dict.get("entries") or payload_dict.get("data") or payload_dict.get("rows")
        )
        if isinstance(entries_val, list):
            res: list[dict[str, object]] = []
            for item in cast(list[object], entries_val):
                sub_dict = _extract_dict(item)
                if sub_dict is not None:
                    res.append(sub_dict)
            return res
        return []
    elif isinstance(payload, list):
        res: list[dict[str, object]] = []
        for item in cast(list[object], payload):
            sub_dict = _extract_dict(item)
            if sub_dict is not None:
                res.append(sub_dict)
        return res
    return []


def _parse_total_sar(payload: object) -> int:
    payload_dict = _extract_dict(payload)
    if payload_dict is not None and "total" in payload_dict:
        total_val = payload_dict["total"]
        if isinstance(total_val, (int, float, str)):
            with contextlib.suppress(ValueError, TypeError):
                return int(total_val)
    entries = _get_entries(payload)
    total = 0
    for e in entries:
        count = e.get("count", 1)
        if isinstance(count, (int, float, str)):
            with contextlib.suppress(ValueError, TypeError):
                total += int(count)
                continue
        total += 1
    return total


def _parse_unmatched_sar(payload: object) -> tuple[int, list[dict[str, float]]]:
    entries = _get_entries(payload)
    points: list[dict[str, float]] = []
    for e in entries:
        lat_val = e.get("lat") if "lat" in e else e.get("latitude")
        lon_val = e.get("lon") if "lon" in e else e.get("longitude")
        if isinstance(lat_val, (int, float, str)) and isinstance(lon_val, (int, float, str)):
            with contextlib.suppress(ValueError, TypeError):
                points.append({"lat": float(lat_val), "lon": float(lon_val)})

    count = len(points)
    payload_dict = _extract_dict(payload)
    if payload_dict is not None and "total" in payload_dict:
        total_val = payload_dict["total"]
        if isinstance(total_val, (int, float, str)):
            with contextlib.suppress(ValueError, TypeError):
                count = int(total_val)
    return count, points


def _parse_fishing_hours(payload: object) -> float:
    entries = _get_entries(payload)
    total_hours = 0.0
    for e in entries:
        val = (
            e.get("hours")
            if "hours" in e
            else e.get("apparentFishingHours")
            if "apparentFishingHours" in e
            else e.get("fishing_hours")
            if "fishing_hours" in e
            else e.get("value")
        )
        if isinstance(val, (int, float, str)):
            with contextlib.suppress(ValueError, TypeError):
                total_hours += float(val)
    return round(total_hours, 2)


@tool(
    "vessel_activity",
    VesselActivityParams,
    description="Global Fishing Watch SAR detections and fishing effort",
)
async def vessel_activity(params: VesselActivityParams, ctx: ToolContext) -> ToolResult:
    """Query SAR detections and fishing effort near the site from GFW API v3."""
    if params.radius_km > 20.0:
        raise ValueError("radius_km must be <= 20.0")

    site = await ctx.store.sites.get(params.site_id)

    geojson_fc = _circle_polygon_feature_collection(
        lat=site.location.lat,
        lon=site.location.lon,
        radius_km=params.radius_km,
    )

    headers: dict[str, str] = {}
    if ctx.settings.gfw_token is not None:
        headers["Authorization"] = f"Bearer {ctx.settings.gfw_token.get_secret_value()}"

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
    sar_total_payload = await _fetch_gfw_report(ctx, sar_total_query, geojson_fc, headers)
    total_sar_count = _parse_total_sar(sar_total_payload)

    # 2. Unmatched-to-AIS SAR presence (matched='false')
    sar_unmatched_query = {
        **base_query,
        "datasets[0]": "public-global-sar-presence:latest",
        "filters[0]": "matched='false'",
    }
    sar_unmatched_payload = await _fetch_gfw_report(ctx, sar_unmatched_query, geojson_fc, headers)
    unmatched_count, unmatched_points = _parse_unmatched_sar(sar_unmatched_payload)

    # 3. Fishing effort
    fishing_query = {
        **base_query,
        "datasets[0]": "public-global-fishing-effort:latest",
    }
    fishing_payload = await _fetch_gfw_report(ctx, fishing_query, geojson_fc, headers)
    fishing_hours = _parse_fishing_hours(fishing_payload)

    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool="vessel_activity",
        params=params.model_dump(mode="json"),
        data={
            "sar_detections": {
                "total": total_sar_count,
                "unmatched_to_ais": {
                    "count": unmatched_count,
                    "points": unmatched_points,
                },
            },
            "fishing_hours": fishing_hours,
        },
        source_url=GFW_REPORT_URL,
        retrieved_at=datetime.now(UTC),
    )
