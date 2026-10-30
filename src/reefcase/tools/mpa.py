"""Protected Area (MPA) boundary tool (architecture §5.4, §9.4).

Queries the GeoParquet built by ``scripts/build_geo.py`` (data/geo/mpa.parquet) through DuckDB
spatial to find the WDPA protected area a site lies in and whether it is no-take. Where areas
nest (an MLCD inside a national marine sanctuary) the smallest, most specific one wins. Runs
entirely offline with zero network calls at runtime.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from reefcase.core.errors import ToolError
from reefcase.core.ids import TOOL_RESULT, new_id
from reefcase.core.schemas import ToolResult
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import ToolParams, tool

__all__ = ["MPA_SOURCE_URL", "MPABoundaryParams", "mpa_boundary"]

MPA_SOURCE_URL: str = "https://www.protectedplanet.net/en/thematic-areas/wdpa"
DEFAULT_MPA_PARQUET: Path = Path("data/geo/mpa.parquet")

#: WDPA NO_TAKE: 'All' is fully no-take, 'None' allows take; 'Part' and 'Not Reported' say
#: nothing definite about a given point, so they map to None.
_NO_TAKE: dict[str, bool] = {"All": True, "None": False}


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
    if not DEFAULT_MPA_PARQUET.is_file():
        raise ToolError(f"{DEFAULT_MPA_PARQUET} missing; run scripts/build_geo.py")

    row = await ctx.store.fetchone(
        f"""
        SELECT name, designation, no_take
        FROM read_parquet('{DEFAULT_MPA_PARQUET.as_posix()}')
        WHERE ST_Within(ST_Point(?, ?), geom)
        ORDER BY marine_area_km2 ASC NULLS LAST
        LIMIT 1
        """,
        [site.location.lon, site.location.lat],
    )

    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool="mpa_boundary",
        params=params.model_dump(mode="json"),
        data={
            "inside_mpa": row is not None,
            "mpa_name": row[0] if row else None,
            "no_take": _NO_TAKE.get(row[2]) if row else None,
            "designation": row[1] if row else None,
        },
        source_url=MPA_SOURCE_URL,
        retrieved_at=datetime.now(UTC),
    )
