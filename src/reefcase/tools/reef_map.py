"""Allen Coral Atlas reef map and geomorphology tool (architecture §5.4, §9.3).

Queries the GeoParquet built by ``scripts/build_geo.py`` (data/geo/reef_map.parquet) through
DuckDB spatial: the geomorphic zone and benthic class under the site, and the mapped reef area
(geomorphic polygons) within 1 km. A site outside the region the file was built for is
``available=false``, not "no reef". Runs entirely offline with zero network calls at runtime.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

from reefcase.core.errors import ToolError
from reefcase.core.ids import TOOL_RESULT, new_id
from reefcase.core.schemas import ToolResult
from reefcase.tools.geo_coverage import outside_coverage
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import ToolParams, tool

__all__ = ["REEF_MAP_SOURCE_URL", "ReefMapParams", "reef_map"]

REEF_MAP_SOURCE_URL: str = "https://doi.org/10.5281/zenodo.3833242"
DEFAULT_REEF_PARQUET: Path = Path("data/geo/reef_map.parquet")
RADIUS_M: float = 1000.0


class ReefMapParams(ToolParams):
    """Parameters for reef_map tool."""

    site_id: str


def _utm_epsg(lon: float, lat: float) -> str:
    """The WGS 84 UTM zone holding the point, so the 1 km buffer and areas are in metres."""
    zone = min(int((lon + 180.0) // 6.0) + 1, 60)
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


@tool(
    "reef_map",
    ReefMapParams,
    description="Allen Coral Atlas geomorphic zone, benthic class and local reef area",
)
async def reef_map(params: ReefMapParams, ctx: ToolContext) -> ToolResult:
    """Query reef geomorphology and benthic class for a site using DuckDB spatial."""
    site = await ctx.store.sites.get(params.site_id)
    if not DEFAULT_REEF_PARQUET.is_file():
        raise ToolError(f"{DEFAULT_REEF_PARQUET} missing; run scripts/build_geo.py")

    lon = site.location.lon
    lat = site.location.lat
    unavailable = outside_coverage(lat, lon)
    if unavailable is not None:
        return ToolResult(
            id=new_id(TOOL_RESULT),
            tool="reef_map",
            params=params.model_dump(mode="json"),
            data=unavailable,
            source_url=REEF_MAP_SOURCE_URL,
            retrieved_at=datetime.now(UTC),
        )

    parquet = f"read_parquet('{DEFAULT_REEF_PARQUET.as_posix()}')"

    rows = await ctx.store.fetchall(
        f"SELECT layer, class_name FROM {parquet} WHERE ST_Within(ST_Point(?, ?), geom)",
        [lon, lat],
    )
    classes = {layer: class_name for layer, class_name in rows}

    # Prefilter with a degree box a little wider than 1 km, then intersect in metres.
    dlat = 1.1 * RADIUS_M / 111_320.0
    dlon = dlat / max(math.cos(math.radians(lat)), 0.01)
    utm = _utm_epsg(lon, lat)
    to_utm = f"'EPSG:4326', '{utm}', always_xy := true"
    area_row = await ctx.store.fetchone(
        f"""
        WITH c AS (SELECT ST_Buffer(ST_Transform(ST_Point(?, ?), {to_utm}), {RADIUS_M}) AS disk)
        SELECT COALESCE(SUM(ST_Area(ST_Intersection(
            ST_Transform(r.geom::GEOMETRY, {to_utm}), c.disk))), 0) / 1e6
        FROM {parquet} r, c
        WHERE r.layer = 'geomorphic'
          AND ST_Intersects(r.geom::GEOMETRY, ST_MakeEnvelope(?, ?, ?, ?))
        """,
        [lon, lat, lon - dlon, lat - dlat, lon + dlon, lat + dlat],
    )
    reef_area_km2 = round(float(area_row[0]), 3) if area_row else 0.0

    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool="reef_map",
        params=params.model_dump(mode="json"),
        data={
            "available": True,
            "geomorphic_zone": classes.get("geomorphic"),
            "benthic_class": classes.get("benthic"),
            "reef_area_km2_within_1km": reef_area_km2,
        },
        source_url=REEF_MAP_SOURCE_URL,
        retrieved_at=datetime.now(UTC),
    )
