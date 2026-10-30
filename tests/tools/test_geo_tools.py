"""Tests for Story 4.4 — reef_map and mpa_boundary (offline GeoParquet).

AC 1: When scripts/build_geo.py runs, it writes the two GeoParquet files clipped to the region.
AC 2: Given a point inside a known MPA polygon, when mpa_boundary runs,
      then inside_mpa=true with its name and no_take flag.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pytest

from reefcase.core.errors import NotFoundError
from reefcase.core.schemas import GeoPoint, Site, ToolResult
from reefcase.store.db import Store
from reefcase.tools.http import ToolContext
from reefcase.tools.mpa import MPABoundaryParams, mpa_boundary
from reefcase.tools.reef_map import ReefMapParams, reef_map
from reefcase.tools.registry import registry

GEO_DIR = Path("data/geo")
MPA_PARQUET = GEO_DIR / "mpa.parquet"
REEF_PARQUET = GEO_DIR / "reef_map.parquet"


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


def test_build_geo_creates_parquet_files() -> None:
    """AC 1: scripts/build_geo.py runs and writes mpa.parquet and reef_map.parquet."""
    result = subprocess.run(
        [sys.executable, "scripts/build_geo.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"build_geo.py failed: {result.stderr}\n{result.stdout}"

    assert MPA_PARQUET.is_file(), f"{MPA_PARQUET} does not exist"
    assert REEF_PARQUET.is_file(), f"{REEF_PARQUET} does not exist"

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    # Verify MPA schema and content
    mpa_sql = (
        "SELECT name, designation, no_take, ST_AsText(geom) "
        f"FROM read_parquet('{MPA_PARQUET.as_posix()}')"
    )
    mpa_rows = con.execute(mpa_sql).fetchall()
    assert len(mpa_rows) > 0

    # Verify Reef Map schema and content
    reef_sql = (
        "SELECT geomorphic_zone, benthic_class, ST_AsText(geom) "
        f"FROM read_parquet('{REEF_PARQUET.as_posix()}')"
    )
    reef_rows = con.execute(reef_sql).fetchall()
    assert len(reef_rows) > 0


@pytest.mark.asyncio
async def test_mpa_boundary_inside_known_mpa(store: Store, make_settings: Any) -> None:
    """AC 2: Point inside known MPA polygon returns inside_mpa=True, name, and no_take flag."""
    # Kealakekua Bay MLCD coordinates (~19.48 N, -155.93 W)
    site = await _create_site(store, "site_mpa_in", lat=19.48, lon=-155.93, name="Kealakekua Bay")
    settings = make_settings()

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)
        params = MPABoundaryParams(site_id=site.id)
        result = await mpa_boundary(params, ctx)

    assert isinstance(result, ToolResult)
    assert result.tool == "mpa_boundary"
    assert result.id.startswith("tr_")
    assert result.source_url == "https://www.protectedplanet.net/"

    data = result.data
    assert data["inside_mpa"] is True
    assert data["mpa_name"] == "Kealakekua Bay Marine Life Conservation District"
    assert data["no_take"] is True
    assert data["designation"] == "Marine Life Conservation District"


@pytest.mark.asyncio
async def test_mpa_boundary_outside_mpa(store: Store, make_settings: Any) -> None:
    """Point outside known MPAs returns inside_mpa=False with None fields."""
    # Open ocean point well off the Kona coast (~19.0 N, -157.0 W)
    site = await _create_site(store, "site_mpa_out", lat=19.0, lon=-157.0, name="Open Ocean")
    settings = make_settings()

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)
        params = MPABoundaryParams(site_id=site.id)
        result = await mpa_boundary(params, ctx)

    data = result.data
    assert data["inside_mpa"] is False
    assert data["mpa_name"] is None
    assert data["no_take"] is None
    assert data["designation"] is None


@pytest.mark.asyncio
async def test_reef_map_query(store: Store, make_settings: Any) -> None:
    """Querying reef_map returns geomorphic zone, benthic class, and reef area within 1 km."""
    # Kailua Bay reef point (~19.64 N, -155.99 W)
    site = await _create_site(store, "site_kailua", lat=19.64, lon=-155.99, name="Kailua Reef")
    settings = make_settings()

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)
        params = ReefMapParams(site_id=site.id)
        result = await reef_map(params, ctx)

    assert isinstance(result, ToolResult)
    assert result.tool == "reef_map"
    assert result.id.startswith("tr_")
    assert result.source_url == "https://doi.org/10.5281/zenodo.3833242"

    data = result.data
    assert data["geomorphic_zone"] == "Reef Slope"
    assert data["benthic_class"] == "Coral/Algae"
    assert data["reef_area_km2_within_1km"] > 0


@pytest.mark.asyncio
async def test_unknown_site_raises_not_found(store: Store, make_settings: Any) -> None:
    """Querying non-existent site raises NotFoundError for both tools."""
    settings = make_settings()
    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)

        with pytest.raises(NotFoundError):
            await mpa_boundary(MPABoundaryParams(site_id="unknown_site"), ctx)

        with pytest.raises(NotFoundError):
            await reef_map(ReefMapParams(site_id="unknown_site"), ctx)


@pytest.mark.asyncio
async def test_registry_integration(store: Store, make_settings: Any) -> None:
    """Both tools are registered in tool registry and callable via registry.call."""
    site = await _create_site(store, "site_reg", lat=19.48, lon=-155.93)
    settings = make_settings()

    async with _strict_mock_client() as client:
        ctx = ToolContext(http=client, store=store, settings=settings)

        res_mpa = await registry.call("mpa_boundary", {"site_id": site.id}, ctx)
        assert res_mpa.tool == "mpa_boundary"
        assert res_mpa.data["inside_mpa"] is True

        res_reef = await registry.call("reef_map", {"site_id": site.id}, ctx)
        assert res_reef.tool == "reef_map"
