"""GET /api/geo/{layer} — map layers for MPA, reef and vessels (Story 4.6, §5.4, §6.3).

Returns GeoJSON FeatureCollections for:
- ``mpa``: protected area boundaries from ``data/geo/mpa.parquet``
- ``reef``: reef extent and geomorphology from ``data/geo/reef_map.parquet``
- ``vessels``: detection points from the survey's ``vessel_activity`` tool result
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from reefcase.core.errors import NotFoundError
from reefcase.core.events import ToolReturned
from reefcase.core.schemas import ToolResult
from reefcase.tools.mpa import DEFAULT_MPA_PARQUET
from reefcase.tools.reef_map import DEFAULT_REEF_PARQUET

if TYPE_CHECKING:
    from reefcase.store.db import Store

__all__ = ["GeoJsonFeature", "GeoJsonFeatureCollection", "GeoLayer", "router"]

router = APIRouter()

#: WDPA NO_TAKE, mapped as the mpa_boundary tool does: 'Part' and 'Not Reported' become null.
_NO_TAKE: dict[str, bool] = {"All": True, "None": False}


class GeoLayer(StrEnum):
    """The supported map layers (architecture §6.3, web/src/api/openapi.snapshot.json)."""

    MPA = "mpa"
    REEF = "reef"
    VESSELS = "vessels"


class GeoJsonFeature(BaseModel):
    """A GeoJSON feature."""

    type: Literal["Feature"] = "Feature"
    properties: dict[str, Any] = Field(default_factory=dict)
    geometry: dict[str, Any]


class GeoJsonFeatureCollection(BaseModel):
    """A GeoJSON FeatureCollection."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJsonFeature] = Field(default_factory=list[GeoJsonFeature])


def _parse_bbox(text: str) -> tuple[float, float, float, float]:
    """Parse comma-separated W,S,E,N bbox coordinates or raise HTTPException(422)."""
    parts = text.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid bbox '{text}'; expected 4 values: min_lon,min_lat,max_lon,max_lat",
        )
    try:
        w, s, e, n = (float(p.strip()) for p in parts)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid bbox '{text}'; values must be floats: {exc}",
        ) from exc

    if not (-180.0 <= w < e <= 180.0 and -90.0 <= s < n <= 90.0):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid bbox '{text}'; out of range (-180<=w<e<=180, -90<=s<n<=90)",
        )
    return w, s, e, n


@router.get(
    "/geo/{layer}",
    response_model=GeoJsonFeatureCollection,
    operation_id="getGeoLayer",
    summary="GeoJSON for a map layer",
    responses={
        200: {
            "description": "A GeoJSON FeatureCollection.",
        }
    },
)
async def get_geo_layer(
    layer: GeoLayer,
    request: Request,
    survey_id: str | None = None,
) -> GeoJsonFeatureCollection:
    """Return a GeoJSON FeatureCollection for ``layer`` (mpa, reef, or vessels)."""
    bbox_str = request.query_params.get("bbox")
    bbox = _parse_bbox(bbox_str) if bbox_str is not None else None

    store = request.app.state.store

    if layer is GeoLayer.MPA:
        return await _get_mpa_layer(store, bbox)
    if layer is GeoLayer.REEF:
        return await _get_reef_layer(store, bbox)
    return await _get_vessels_layer(store, survey_id, bbox)


async def _get_mpa_layer(
    store: Store, bbox: tuple[float, float, float, float] | None
) -> GeoJsonFeatureCollection:
    if not DEFAULT_MPA_PARQUET.is_file():
        return GeoJsonFeatureCollection()

    parquet_str = DEFAULT_MPA_PARQUET.as_posix()
    if bbox is not None:
        w, s, e, n = bbox
        query = """
            SELECT name, designation, no_take, wdpa_id, marine_area_km2,
                   ST_AsGeoJSON(ST_Intersection(geom, ST_MakeEnvelope(?, ?, ?, ?)))
            FROM read_parquet(?)
            WHERE ST_Intersects(geom, ST_MakeEnvelope(?, ?, ?, ?))
        """
        rows = await store.fetchall(query, [w, s, e, n, parquet_str, w, s, e, n])
    else:
        query = """
            SELECT name, designation, no_take, wdpa_id, marine_area_km2,
                   ST_AsGeoJSON(geom)
            FROM read_parquet(?)
        """
        rows = await store.fetchall(query, [parquet_str])

    features: list[GeoJsonFeature] = []
    for row in rows:
        geojson_str = row[5]
        if not geojson_str:
            continue
        geom = json.loads(geojson_str)
        if not geom or not geom.get("coordinates"):
            continue
        features.append(
            GeoJsonFeature(
                properties={
                    "name": row[0],
                    "designation": row[1],
                    "no_take": _NO_TAKE.get(row[2]),
                    "wdpa_id": row[3],
                    "marine_area_km2": row[4],
                },
                geometry=geom,
            )
        )
    return GeoJsonFeatureCollection(features=features)


async def _get_reef_layer(
    store: Store, bbox: tuple[float, float, float, float] | None
) -> GeoJsonFeatureCollection:
    if not DEFAULT_REEF_PARQUET.is_file():
        return GeoJsonFeatureCollection()

    parquet_str = DEFAULT_REEF_PARQUET.as_posix()
    if bbox is not None:
        w, s, e, n = bbox
        query = """
            SELECT layer, class_name,
                   ST_AsGeoJSON(ST_Intersection(geom, ST_MakeEnvelope(?, ?, ?, ?)))
            FROM read_parquet(?)
            WHERE ST_Intersects(geom, ST_MakeEnvelope(?, ?, ?, ?))
        """
        rows = await store.fetchall(query, [w, s, e, n, parquet_str, w, s, e, n])
    else:
        query = """
            SELECT layer, class_name,
                   ST_AsGeoJSON(geom)
            FROM read_parquet(?)
        """
        rows = await store.fetchall(query, [parquet_str])

    features: list[GeoJsonFeature] = []
    for row in rows:
        geojson_str = row[2]
        if not geojson_str:
            continue
        geom = json.loads(geojson_str)
        if not geom or not geom.get("coordinates"):
            continue
        features.append(
            GeoJsonFeature(
                properties={
                    "layer": row[0],
                    "class_name": row[1],
                },
                geometry=geom,
            )
        )
    return GeoJsonFeatureCollection(features=features)


async def _get_vessels_layer(
    store: Store,
    survey_id: str | None,
    bbox: tuple[float, float, float, float] | None,
) -> GeoJsonFeatureCollection:
    if survey_id is None:
        return GeoJsonFeatureCollection()

    try:
        await store.surveys.get(survey_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Only the results this survey's agent got back; another survey's calls are not its evidence.
    features: list[GeoJsonFeature] = []
    seen: set[str] = set()
    for event in await store.events.list(survey_id):
        if not isinstance(event, ToolReturned) or event.tool_result_id in seen:
            continue
        seen.add(event.tool_result_id)
        result = await store.tool_results.get(event.tool_result_id)
        if result.tool == "vessel_activity":
            features.extend(_vessel_features(result, bbox))
    return GeoJsonFeatureCollection(features=features)


def _vessel_features(
    result: ToolResult, bbox: tuple[float, float, float, float] | None
) -> list[GeoJsonFeature]:
    """Point features for the SAR detections unmatched to AIS (tools/vessels.py data shape)."""
    sar = cast(dict[str, Any], result.data.get("sar_detections", {}))
    unmatched = cast(dict[str, Any], sar.get("unmatched_to_ais", {}))
    features: list[GeoJsonFeature] = []
    for point in cast(list[dict[str, float]], unmatched.get("points", [])):
        lat, lon = point["lat"], point["lon"]
        if bbox is not None:
            w, s, e, n = bbox
            if not (w <= lon <= e and s <= lat <= n):
                continue
        features.append(
            GeoJsonFeature(
                properties={"unmatched_to_ais": True, "tool_result_id": result.id},
                geometry={"type": "Point", "coordinates": [lon, lat]},
            )
        )
    return features
