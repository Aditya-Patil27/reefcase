---
status: done
---

# Story 4.6: Map layer endpoints

As the web map,
I want GeoJSON for MPA, reef and vessel layers,
So that the map shows the evidence the agent used.

- Owner: B (taken by lead-d) · Priority: P0 · Depends on: 4.3, 4.4
- Files: `src/reefcase/api/routes/geo.py`, `src/reefcase/api/main.py`, `tests/api/test_geo.py`
- Done when: gate passes

## Acceptance Criteria

**Given** `GET /api/geo/mpa` or `/api/geo/reef`
**When** called with a bbox
**Then** it returns a GeoJSON FeatureCollection clipped to the bbox

**Given** `GET /api/geo/mpa` or `/api/geo/reef`
**When** called without a bbox
**Then** it returns all features in the layer

**Given** `GET /api/geo/vessels?survey_id=`
**When** that survey's agent called `vessel_activity`
**Then** it returns the detection points from that tool result as a GeoJSON FeatureCollection of Point features

**Given** `GET /api/geo/vessels` without `survey_id` or with no detections
**Then** it returns an empty GeoJSON FeatureCollection (`{"type": "FeatureCollection", "features": []}`)

**Given** `GET /api/geo/vessels?survey_id=` with unknown `survey_id`
**Then** it returns 404 (NotFoundError)

## Architecture contract

- §5.4: tool results and layer Parquet files.
- §6.3: `GET /api/geo/{layer}` "GeoJSON for map layers: `mpa`, `reef`, `vessels?survey_id=`".
- Web contract: `web/src/api/openapi.snapshot.json` (`operationId="getGeoLayer"`, `layer` path param, `survey_id` query param, 200 response with `type="FeatureCollection"` and `features`).

## Decisions

- **Bbox query parameter**: Parsed directly from `request.query_params.get("bbox")` so the OpenAPI snapshot schema (which does not define bbox in parameters) remains verbatim while still supporting bbox clipping for map viewport queries.
- **DuckDB spatial clipping**: Uses `ST_Intersection(geom, ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat))` on `data/geo/mpa.parquet` and `data/geo/reef_map.parquet`. If no bbox is provided, converts entire layer geometry to GeoJSON via `ST_AsGeoJSON(geom)`.
- **Vessel detections**: Re-uses `ToolResult` from `store.tool_results` or survey events for `vessel_activity`. Each detection item is converted to a GeoJSON Point feature with its properties (`vessel_id`, `mmsi`, `timestamp`, `confidence`, etc.).
- **Response models**: Defined in `src/reefcase/api/routes/geo.py` with `ConfigDict(extra="allow")` and strict pyright annotations without mutating `core/schemas.py`.

## Tasks

1. [x] Tests: unit and integration tests covering bbox clipping, full layers, vessels with and without survey_id, unknown survey 404, invalid bbox 422, unknown layer 422.
2. [x] `routes/geo.py` with DuckDB spatial and store integration.
3. [x] Register router under `/api` in `src/reefcase/api/main.py`.
4. [x] `uv run poe gate` green.
5. [x] `pnpm -C web run gate` green.
6. [x] Review against `.opencode/agents/reviewer.md`.

