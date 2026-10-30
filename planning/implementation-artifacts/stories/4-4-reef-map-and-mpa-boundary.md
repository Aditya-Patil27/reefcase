# Story 4.4: reef_map and mpa_boundary (offline GeoParquet)

Owner: D (lead-d) · Priority: P0 · Depends on: 4.1 · Status: backlog

## Story (verbatim from epics.md)

As the agent,
I want reef zone and protected-area status for the site,
So that findings are placed in context (e.g. "inside a no-take zone").

- Owner: B · Priority: P0 · Depends on: 4.1
- Files: `scripts/build_geo.py`, `data/geo/reef_map.parquet`, `data/geo/mpa.parquet`, `src/reefcase/tools/{reef_map,mpa}.py`, `tests/tools/test_geo_tools.py`
- Done when: gate passes

### Acceptance Criteria (verbatim)

**Given** the downloaded Allen Coral Atlas and WDPA files for the demo region (licences in `data/LICENSES.md`)
**When** `scripts/build_geo.py` runs
**Then** it writes the two GeoParquet files clipped to the region

**Given** a point inside a known MPA polygon
**When** `mpa_boundary` runs
**Then** `inside_mpa=true` with its name and `no_take` flag

## Architecture sections this story touches

### §3 — Layering
- `src/reefcase/tools/{reef_map,mpa}.py` live in `reefcase.tools`.
- May import `reefcase.core` and `reefcase.tools.{http,registry}`.
- May not import `api` or `pipeline`.

### §4.2 — Schemas (`src/reefcase/core/schemas.py`)
- `ToolResult(id: str, tool: str, params: dict[str, Any], data: dict[str, Any], source_url: str, retrieved_at: AwareDatetime)`
- `Site(id: str, name: str, location: GeoPoint, ...)`
- `GeoPoint(lat: float, lon: float)`

### §5.4 — Tools (`src/reefcase/tools/`)
- Tools are async functions `(params: XParams, ctx: ToolContext) -> ToolResult`.
- `reef_map` params: `site_id: str`. Returns in `data`:
  - `geomorphic_zone: str | None`
  - `benthic_class: str | None`
  - `reef_area_km2: float` (reef area within 1 km)
- `mpa_boundary` params: `site_id: str`. Returns in `data`:
  - `inside_mpa: bool`
  - `mpa_name: str | None`
  - `no_take: bool | None`
  - `designation: str | None`
- Runtime constraint: `reef_map` and `mpa_boundary` read pre-downloaded GeoParquet in `data/geo/` through DuckDB spatial (`INSTALL AND LOAD spatial;`). They make **no network calls at runtime**.

### §6.4 — Storage
- DuckDB spatial extension integration. In DuckDB 2.0.0: `INSTALL AND LOAD spatial;` on every connection.

### §9.3 & §9.4 — Geodata Specifications
- Allen Coral Atlas classes:
  - Geomorphic: Shallow Lagoon, Deep Lagoon, Inner Reef Flat, Outer Reef Flat, Reef Crest, Terrestrial Reef Flat, Sheltered Reef Slope, Reef Slope, Plateau, Back Reef Slope, Patch Reef.
  - Benthic: Sand, Rubble, Rock, Seagrass, Coral/Algae, Microalgal Mats.
- WDPA attributes: `NAME`, `DESIG` (designation), `NO_TAKE` ("All" / "Part" / "None" or boolean flag mapped to boolean `no_take`).

## Tasks

1. Write unit tests in `tests/tools/test_geo_tools.py`:
   - AC 1: `scripts/build_geo.py` generates clipped `data/geo/reef_map.parquet` and `data/geo/mpa.parquet`.
   - AC 2: Point query inside known MPA polygon returns `inside_mpa=True`, `mpa_name`, and `no_take` flag.
   - Point query outside MPA returns `inside_mpa=False`, `mpa_name=None`, `no_take=None`.
   - `reef_map` query returns geomorphic zone, benthic class, and reef area within 1 km.
   - Assert no network calls are performed by offline DuckDB spatial queries.
2. Implement `scripts/build_geo.py`:
   - Download/read source polygon geometries for Allen Coral Atlas & WDPA.
   - Filter/clip to the Hawaii demo region bounding box.
   - Write out compact GeoParquet files to `data/geo/reef_map.parquet` and `data/geo/mpa.parquet`.
3. Implement `src/reefcase/tools/mpa.py`:
   - Define `MPABoundaryParams(site_id: str)`.
   - Query `data/geo/mpa.parquet` using DuckDB `ST_Within(ST_Point(lon, lat), geom)` via `ctx.store` or in-memory DuckDB connection with `INSTALL AND LOAD spatial;`.
   - Return formatted `ToolResult`.
4. Implement `src/reefcase/tools/reef_map.py`:
   - Define `ReefMapParams(site_id: str)`.
   - Query `data/geo/reef_map.parquet` using DuckDB spatial point-in-polygon and distance buffer queries (`ST_DWithin`).
   - Return formatted `ToolResult`.
5. Run `uv run poe gate` to verify formatting, type-safety, imports, and offline test suite.

## Lessons

- `[store] (1-4) RULE`: Bootstrap DuckDB spatial with `INSTALL AND LOAD spatial;` on every new connection, and keep `pytz` a runtime dependency.
- `[test] (1-4) RULE`: For async tests, put `@pytest.mark.asyncio` on each `async def test_...`; do not edit `[tool.pytest.ini_options]`.
- `[python] (1-3) RULE`: In tests, build `Settings` with `Settings(_env_file=None)  # pyright: ignore[reportCallIssue]` inside `make_settings()` helper.
- `[tools rule]`: `reef_map` and `mpa_boundary` make no network calls at runtime; queries execute strictly offline against local GeoParquet via DuckDB spatial.

## Library check

Confirmed DuckDB 2.0.0 spatial usage:
- `INSTALL AND LOAD spatial;`
- GeoParquet reading: `SELECT * FROM read_parquet('data/geo/mpa.parquet') WHERE ST_Intersects(geom, ST_Point(lon, lat))`
- Spatial functions: `ST_Point(x, y)`, `ST_Intersects`, `ST_DWithin`.
