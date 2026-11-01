"""Tests for Story 4.4 — reef_map and mpa_boundary (offline GeoParquet).

AC 1: When scripts/build_geo.py runs, it writes the two GeoParquet files clipped to the region.
AC 2: Given a point inside a known MPA polygon, when mpa_boundary runs,
      then inside_mpa=true with its name and no_take flag.

A site outside the region the files were built for is available=false from both tools: "not in
an MPA" or "no reef" there would be a false claim.

The build test runs the script ``--offline`` on tiny inline GeoJSON. The tool tests query the
committed data/geo files, built from real WDPA and Allen Coral Atlas data for West Hawaii, so
the expected values below are real attributes of those polygons.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pytest

from reefcase.core.errors import NotFoundError, ToolError
from reefcase.core.schemas import GeoPoint, Site, ToolResult
from reefcase.store.db import Store
from reefcase.tools import geo_coverage as geo_coverage_module
from reefcase.tools import mpa as mpa_module
from reefcase.tools import reef_map as reef_map_module
from reefcase.tools.http import ToolContext
from reefcase.tools.mpa import MPABoundaryParams, mpa_boundary
from reefcase.tools.reef_map import ReefMapParams, reef_map
from reefcase.tools.registry import registry

# Inside Kealakekua Bay MLCD (WDPA 13086, NO_TAKE 'Part'), which sits outside the sanctuary.
KEALAKEKUA = (19.48, -155.93)
# North Kohala: a Reef Slope polygon over Coral/Algae, inside the humpback whale sanctuary.
KOHALA_REEF = (20.230846225, -155.89974295)
# Off Kona, inside the mapped region: no MPA and no mapped reef.
KONA_OFFSHORE = (20.0, -156.05)
# Outside the mapped region (data/geo/coverage.json).
OPEN_OCEAN = (19.0, -157.0)


async def _create_site(
    store: Store, site_id: str, lat: float, lon: float, name: str = "Test Site"
) -> Site:
    site = Site(
        id=site_id,
        name=name,
        location=GeoPoint(lat=lat, lon=lon),
        created_at=datetime.now(UTC),
    )
    await store.sites.save(site)
    return site


def _strict_mock_client() -> httpx.AsyncClient:
    """A client that fails if any HTTP call is attempted (verifying tools are offline)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected network call to {request.url}")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _square(x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return {"type": "Polygon", "coordinates": [ring]}


def _write_collection(path: Path, features: list[tuple[dict[str, Any], dict[str, Any]]]) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": props, "geometry": geom}
                    for props, geom in features
                ],
            }
        )
    )


def _run_build(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/build_geo.py", "--offline", *args],
        capture_output=True,
        text=True,
    )


def test_build_geo_clips_to_region(tmp_path: Path) -> None:
    """AC 1: build_geo.py turns the raw downloads into two GeoParquet files clipped to the box."""
    raw = tmp_path / "raw"
    raw.mkdir()

    def wdpa(site_id: int, name: str, no_take: str) -> dict[str, Any]:
        props = {"desig_eng": "Marine Protected Area", "no_take": no_take, "gis_m_area": 1.0}
        return {"site_id": site_id, "name": name, **props}

    _write_collection(
        raw / "wdpa.geojson",
        [
            (wdpa(1, "Straddling Reserve", "All"), _square(0.5, 0.5, 1.5, 1.5)),
            (wdpa(2, "Far Away Park", "None"), _square(2.0, 2.0, 3.0, 3.0)),
        ],
    )
    _write_collection(
        raw / "aca_geomorphic.geojson",
        [({"class_name": "Reef Slope"}, _square(0.1, 0.1, 0.4, 0.4))],
    )
    _write_collection(
        raw / "aca_benthic.geojson",
        [
            ({"class_name": "Coral/Algae"}, _square(0.8, -0.5, 1.2, 0.5)),
            ({"class_name": "Sand"}, _square(5.0, 5.0, 6.0, 6.0)),
        ],
    )

    result = _run_build("--bbox", "0,0,1,1", "--raw-dir", str(raw), "--out-dir", str(tmp_path))
    assert result.returncode == 0, f"build_geo.py failed: {result.stderr}\n{result.stdout}"

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    mpa_rows = con.execute(
        "SELECT wdpa_id, name, no_take, ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)"
        f" FROM read_parquet('{(tmp_path / 'mpa.parquet').as_posix()}')"
    ).fetchall()
    assert mpa_rows == [("1", "Straddling Reserve", "All", 0.5, 0.5, 1.0, 1.0)]

    reef_rows = con.execute(
        "SELECT layer, class_name, ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)"
        f" FROM read_parquet('{(tmp_path / 'reef_map.parquet').as_posix()}') ORDER BY layer"
    ).fetchall()
    assert reef_rows == [
        ("benthic", "Coral/Algae", 0.8, 0.0, 1.0, 0.5),
        ("geomorphic", "Reef Slope", 0.1, 0.1, 0.4, 0.4),
    ]
    assert json.loads((tmp_path / "coverage.json").read_text()) == {"bbox": [0.0, 0.0, 1.0, 1.0]}


def test_build_geo_offline_requires_raw_files(tmp_path: Path) -> None:
    result = _run_build("--raw-dir", str(tmp_path), "--out-dir", str(tmp_path))
    assert result.returncode == 1
    assert "missing" in result.stderr


@pytest.mark.asyncio
async def test_mpa_boundary_inside_known_mpa(store: Store, make_settings: Any) -> None:
    """AC 2: Point inside known MPA polygon returns inside_mpa=True, name, and no_take flag."""
    site = await _create_site(store, "site_mpa_in", *KEALAKEKUA, name="Kealakekua Bay")

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        result = await mpa_boundary(MPABoundaryParams(site_id=site.id), ctx)

    assert isinstance(result, ToolResult)
    assert result.tool == "mpa_boundary"
    assert result.id.startswith("tr_")
    assert result.source_url == "https://www.protectedplanet.net/en/thematic-areas/wdpa"
    assert result.data == {
        "available": True,
        "inside_mpa": True,
        "mpa_name": "Kealakekua Bay Marine Life Conservation District",
        # WDPA NO_TAKE is 'Part': no-take in some zones only, so not definite for the point.
        "no_take": None,
        "designation": "Marine Protected Area",
    }


@pytest.mark.asyncio
async def test_mpa_boundary_outside_mpa(store: Store, make_settings: Any) -> None:
    """Point in the mapped region but outside every MPA returns inside_mpa=False."""
    site = await _create_site(store, "site_mpa_out", *KONA_OFFSHORE, name="Off Kona")

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        result = await mpa_boundary(MPABoundaryParams(site_id=site.id), ctx)

    assert result.data == {
        "available": True,
        "inside_mpa": False,
        "mpa_name": None,
        "no_take": None,
        "designation": None,
    }


@pytest.mark.asyncio
async def test_reef_map_query(store: Store, make_settings: Any) -> None:
    """reef_map returns the geomorphic zone, benthic class and reef area within 1 km."""
    site = await _create_site(store, "site_kohala", *KOHALA_REEF, name="Kohala Reef")

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        result = await reef_map(ReefMapParams(site_id=site.id), ctx)

    assert isinstance(result, ToolResult)
    assert result.tool == "reef_map"
    assert result.id.startswith("tr_")
    assert result.source_url == "https://doi.org/10.5281/zenodo.3833242"

    data = result.data
    assert data["available"] is True
    assert data["geomorphic_zone"] == "Reef Slope"
    assert data["benthic_class"] == "Coral/Algae"
    # Mapped reef inside the 3.14 km² disk, measured in UTM zone 5N.
    assert data["reef_area_km2_within_1km"] == pytest.approx(0.345, abs=0.005)


@pytest.mark.asyncio
async def test_reef_map_open_water_has_no_reef(store: Store, make_settings: Any) -> None:
    site = await _create_site(store, "site_reef_out", *KONA_OFFSHORE, name="Off Kona")

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        result = await reef_map(ReefMapParams(site_id=site.id), ctx)

    assert result.data == {
        "available": True,
        "geomorphic_zone": None,
        "benthic_class": None,
        "reef_area_km2_within_1km": 0.0,
    }


@pytest.mark.asyncio
async def test_outside_mapped_region_is_unavailable(store: Store, make_settings: Any) -> None:
    """No 'not in an MPA' or 'no reef' claim for a site the data doesn't cover."""
    site = await _create_site(store, "site_elsewhere", *OPEN_OCEAN, name="Open Ocean")

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        results = [
            await mpa_boundary(MPABoundaryParams(site_id=site.id), ctx),
            await reef_map(ReefMapParams(site_id=site.id), ctx),
        ]

    for result in results:
        assert result.data["available"] is False
        assert "outside the mapped region" in result.data["reason"]
        assert "inside_mpa" not in result.data
        assert "reef_area_km2_within_1km" not in result.data


@pytest.mark.asyncio
async def test_missing_parquet_raises_tool_error(
    store: Store, make_settings: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No silent 'not in an MPA' answer when the data was never built."""
    monkeypatch.setattr(mpa_module, "DEFAULT_MPA_PARQUET", tmp_path / "mpa.parquet")
    monkeypatch.setattr(reef_map_module, "DEFAULT_REEF_PARQUET", tmp_path / "reef_map.parquet")
    site = await _create_site(store, "site_nodata", *KEALAKEKUA)

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        with pytest.raises(ToolError, match="build_geo"):
            await mpa_boundary(MPABoundaryParams(site_id=site.id), ctx)
        with pytest.raises(ToolError, match="build_geo"):
            await reef_map(ReefMapParams(site_id=site.id), ctx)


@pytest.mark.asyncio
async def test_missing_coverage_raises_tool_error(
    store: Store, make_settings: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the coverage file the tools can't tell 'no MPA' from 'no data', so they fail."""
    monkeypatch.setattr(geo_coverage_module, "DEFAULT_COVERAGE_JSON", tmp_path / "coverage.json")
    site = await _create_site(store, "site_nocoverage", *KEALAKEKUA)

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())
        with pytest.raises(ToolError, match="build_geo"):
            await mpa_boundary(MPABoundaryParams(site_id=site.id), ctx)
        with pytest.raises(ToolError, match="build_geo"):
            await reef_map(ReefMapParams(site_id=site.id), ctx)


@pytest.mark.asyncio
async def test_unknown_site_raises_not_found(store: Store, make_settings: Any) -> None:
    """Querying non-existent site raises NotFoundError for both tools."""
    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())

        with pytest.raises(NotFoundError):
            await mpa_boundary(MPABoundaryParams(site_id="unknown_site"), ctx)

        with pytest.raises(NotFoundError):
            await reef_map(ReefMapParams(site_id="unknown_site"), ctx)


@pytest.mark.asyncio
async def test_registry_integration(store: Store, make_settings: Any) -> None:
    """Both tools are registered in tool registry and callable via registry.call."""
    site = await _create_site(store, "site_reg", *KEALAKEKUA)

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=make_settings())

        res_mpa = await registry.call("mpa_boundary", {"site_id": site.id}, ctx)
        assert res_mpa.tool == "mpa_boundary"
        assert res_mpa.data["inside_mpa"] is True

        res_reef = await registry.call("reef_map", {"site_id": site.id}, ctx)
        assert res_reef.tool == "reef_map"
        assert res_reef.data["reef_area_km2_within_1km"] > 0
