"""GET /api/geo/{layer} — map layers for MPA, reef and vessels (Story 4.6, §5.4, §6.3).

Returns GeoJSON FeatureCollections for:
- ``mpa``: protected area boundaries from ``data/geo/mpa.parquet``
- ``reef``: reef extent and geomorphology from ``data/geo/reef_map.parquet``
- ``vessels``: detection points from the survey's ``vessel_activity`` tool result
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from reefcase.core.errors import NotFoundError
from reefcase.core.events import ToolReturned
from reefcase.core.schemas import ToolResult

if TYPE_CHECKING:
    from reefcase.store.db import Store

__all__ = ["GeoJsonFeature", "GeoJsonFeatureCollection", "GeoLayer", "router"]

router = APIRouter()

DEFAULT_MPA_PARQUET = Path("data/geo/mpa.parquet")
DEFAULT_REEF_PARQUET = Path("data/geo/reef_map.parquet")

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
        no_take_raw = row[2]
        no_take_val = _NO_TAKE.get(no_take_raw, no_take_raw) if no_take_raw is not None else None
        features.append(
            GeoJsonFeature(
                properties={
                    "name": row[0],
                    "designation": row[1],
                    "no_take": no_take_val,
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
                    "benthic_class": row[1],
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
        survey = await store.surveys.get(survey_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Search in events first
    vessel_results: list[ToolResult] = []
    events = await store.events.list(survey_id)
    for e in events:
        if isinstance(e, ToolReturned) and e.tool_result_id:
            try:
                tr = await store.tool_results.get(e.tool_result_id)
                if tr.tool == "vessel_activity":
                    vessel_results.append(tr)
            except NotFoundError:
                pass

    # If no vessel results in event stream, check tool_results table for survey's site
    if not vessel_results:
        rows = await store.fetchall(
            """
            SELECT id, tool, params, data, source_url, retrieved_at
            FROM tool_results WHERE tool = 'vessel_activity'
            """,
        )
        for row in rows:
            params_dict = json.loads(row[2])
            if params_dict.get("site_id") == survey.site_id:
                vessel_results.append(
                    ToolResult(
                        id=row[0],
                        tool=row[1],
                        params=params_dict,
                        data=json.loads(row[3]),
                        source_url=row[4],
                        retrieved_at=row[5],
                    )
                )

    features: list[GeoJsonFeature] = []
    for tr in vessel_results:
        sar = cast(dict[str, Any], tr.data.get("sar_detections", {}))
        unmatched = cast(dict[str, Any], sar.get("unmatched_to_ais", {}))
        points: list[Any] = unmatched.get("points", [])
        if not points and "points" in tr.data:
            points = cast(list[Any], tr.data.get("points", []))

        for raw_pt in points:
            if not isinstance(raw_pt, dict):
                continue
            pt_dict = cast(dict[str, object], raw_pt)
            lat_val = pt_dict.get("lat")
            lon_val = pt_dict.get("lon")
            if not isinstance(lat_val, int | float) or not isinstance(lon_val, int | float):
                continue
            lat = float(lat_val)
            lon = float(lon_val)
            if bbox is not None:
                w, s, e, n = bbox
                if not (w <= lon <= e and s <= lat <= n):
                    continue

            props: dict[str, object] = {
                str(k): v for k, v in pt_dict.items() if str(k) not in ("lat", "lon")
            }
            props["unmatched_to_ais"] = True
            features.append(
                GeoJsonFeature(
                    properties=props,
                    geometry={"type": "Point", "coordinates": [lon, lat]},
                )
            )

    return GeoJsonFeatureCollection(features=features)
