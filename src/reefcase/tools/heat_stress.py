"""heat_stress: NOAA Coral Reef Watch daily 5 km at the site (architecture §5.4, §9.2).

One griddap query to PacIOOS ERDDAP (``dhw_5km``) returns the daily degree
heating weeks, SST anomaly and bleaching alert area for the 5 km cell nearest
the site. Land cells are all-NaN and a window outside the data is a 404 from
ERDDAP; both come back as ``available=false`` rather than an exception.

ERDDAP also 404s when the stop date is past its newest day (about two days
behind today), so a window ending within ``RECENT_DAYS`` asks for ``(last)``.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any, Self

import httpx
from pydantic import model_validator

from reefcase.core.errors import ExternalServiceError
from reefcase.core.ids import TOOL_RESULT, new_id
from reefcase.core.schemas import ToolResult
from reefcase.tools.http import ToolContext, get_json
from reefcase.tools.registry import ToolParams, tool

__all__ = ["ERDDAP_URL", "MAX_WINDOW_DAYS", "RECENT_DAYS", "HeatStressParams", "heat_stress"]

ERDDAP_URL = "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/dhw_5km.json"
_VARIABLES = ("CRW_DHW", "CRW_SSTANOMALY", "CRW_BAA")
MAX_WINDOW_DAYS = 366
RECENT_DAYS = 7


class HeatStressParams(ToolParams):
    """A site and an inclusive date window of at most ``MAX_WINDOW_DAYS``."""

    site_id: str
    start: date
    end: date

    @model_validator(mode="after")
    def _check_window(self) -> Self:
        if self.end < self.start:
            raise ValueError("end must not be before start")
        if (self.end - self.start).days > MAX_WINDOW_DAYS:
            raise ValueError(f"window must be at most {MAX_WINDOW_DAYS} days")
        return self


def _today() -> date:
    return datetime.now(UTC).date()


def _query_url(params: HeatStressParams, lat: float, lon: float) -> str:
    stop = "last" if params.end >= _today() - timedelta(days=RECENT_DAYS) else params.end
    dims = f"%5B({params.start}):1:({stop})%5D%5B({lat})%5D%5B({lon})%5D"
    return str(httpx.URL(f"{ERDDAP_URL}?" + ",".join(f"{var}{dims}" for var in _VARIABLES)))


def _summarise(rows: list[list[Any]]) -> dict[str, Any]:
    daily = [
        {"date": row[0][:10], "dhw": row[3], "sst_anomaly": row[4], "alert_level": row[5]}
        for row in rows
    ]
    with_dhw = [day for day in daily if day["dhw"] is not None]
    if not with_dhw:
        return {"available": False, "reason": "no data for this cell (land or no coverage)"}
    peak = max(with_dhw, key=lambda day: day["dhw"])
    return {
        "available": True,
        "lat": rows[0][1],
        "lon": rows[0][2],
        "daily": daily,
        "max_dhw": peak["dhw"],
        "max_dhw_date": peak["date"],
    }


@tool(
    "heat_stress",
    HeatStressParams,
    description="NOAA Coral Reef Watch daily degree heating weeks and SST anomaly at the site",
)
async def heat_stress(params: HeatStressParams, ctx: ToolContext) -> ToolResult:
    """Daily DHW, SST anomaly and alert level at the site's 5 km cell, plus ``max_dhw``."""
    site = await ctx.store.sites.get(params.site_id)
    url = _query_url(params, site.location.lat, site.location.lon)
    try:
        body: Any = await get_json(ctx, url)
        try:
            rows: list[list[Any]] = body["table"]["rows"]
        except (KeyError, TypeError) as exc:
            raise ExternalServiceError(f"GET {url} returned no table rows", url=url) from exc
        data = _summarise(rows)
    except ExternalServiceError as exc:
        if exc.status_code != 404:
            raise
        data = {"available": False, "reason": "window outside the NOAA CRW record"}
    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool="heat_stress",
        params=params.model_dump(mode="json"),
        data=data,
        source_url=url,
        retrieved_at=datetime.now(UTC),
    )
