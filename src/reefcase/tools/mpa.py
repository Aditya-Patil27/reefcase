"""Protected Area (MPA) boundary tool (architecture §5.4, §9.4).

Queries pre-downloaded GeoParquet in data/geo/mpa.parquet through DuckDB spatial
to determine if a site lies within a Marine Protected Area (MPA) and whether it
is a no-take reserve. Runs entirely offline with zero network calls at runtime.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reefcase.core.ids import TOOL_RESULT, new_id
from reefcase.core.schemas import ToolResult
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import ToolParams, tool

__all__ = ["MPA_SOURCE_URL", "MPABoundaryParams", "mpa_boundary"]

MPA_SOURCE_URL: str = "https://www.protectedplanet.net/"
DEFAULT_MPA_PARQUET: Path = Path("data/geo/mpa.parquet")


class MPABoundaryParams(ToolParams):
    """Parameters for mpa_boundary tool."""

    site_id: str


@tool(
    "mpa_boundary",
    MPABoundaryParams,
    description="Protected Planet / WDPA marine protected area status",
)
async def mpa_boundary(params: MPABoundaryParams, ctx: ToolContext) -> ToolResult:
    """Query whether a site is within an MPA polygon using DuckDB spatial."""
    site = await ctx.store.sites.get(params.site_id)

    lon = site.location.lon
    lat = site.location.lat

    # Query local GeoParquet via ctx.store (which loads spatial extension)
    rows: list[Any] = []
    if DEFAULT_MPA_PARQUET.exists():
        parquet_path = DEFAULT_MPA_PARQUET.as_posix()
        query = f"""
            SELECT name, designation, no_take
            FROM read_parquet('{parquet_path}')
            WHERE ST_Within(ST_Point(?, ?), geom)
            LIMIT 1
        """
        rows = await ctx.store.fetchall(query, [lon, lat])

    inside_mpa = False
    mpa_name: str | None = None
    no_take: bool | None = None
    designation: str | None = None

    if rows:
        row = rows[0]
        inside_mpa = True
        mpa_name = str(row[0]) if row[0] is not None else None
        designation = str(row[1]) if row[1] is not None else None
        no_take = bool(row[2]) if row[2] is not None else None

    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool="mpa_boundary",
        params=params.model_dump(mode="json"),
        data={
            "inside_mpa": inside_mpa,
            "mpa_name": mpa_name,
            "no_take": no_take,
            "designation": designation,
        },
        source_url=MPA_SOURCE_URL,
        retrieved_at=datetime.now(UTC),
    )
