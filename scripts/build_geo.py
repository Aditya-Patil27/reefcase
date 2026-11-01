"""Build the offline GeoParquet files for the demo region (Story 4.4, architecture §9.3, §9.4).

Downloads, for one bounding box:
- WDPA marine/coastal protected areas from the UNEP-WCMC ArcGIS service (Protected Planet data)
- Allen Coral Atlas geomorphic and benthic polygons from the ACA WFS

The raw GeoJSON is cached in ``<out-dir>/raw/`` (gitignored). Both layers are then clipped to the
box and written as GeoParquet:
- ``mpa.parquet``: wdpa_id, name, designation, no_take ('All'|'Part'|'None'|...),
  marine_area_km2, geom
- ``reef_map.parquet``: layer ('geomorphic'|'benthic'), class_name, geom
- ``coverage.json``: the box itself, so the tools can tell "outside the data" from "no MPA"

Usage:
    uv run python scripts/build_geo.py                  # download if not cached, then build
    uv run python scripts/build_geo.py --offline        # build from the cached raw files only
    uv run python scripts/build_geo.py --bbox W,S,E,N   # another demo region (re-downloads)

Licences: WDPA non-commercial, cite UNEP-WCMC & IUCN; ACA CC BY 4.0, doi:10.5281/zenodo.3833242
(see data/LICENSES.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import duckdb
import httpx

# West Hawaii (Kona coast): Kealakekua Bay to Lapakahi.
DEFAULT_BBOX: tuple[float, float, float, float] = (-156.10, 19.40, -155.80, 20.30)
DEFAULT_OUT_DIR = Path("data/geo")

WDPA_QUERY_URL = (
    "https://data-gis.unep-wcmc.org/server/rest/services/ProtectedSites/"
    "The_World_Database_of_Protected_Areas/MapServer/1/query"
)
ACA_WFS_URL = "https://allencoralatlas.org/geoserver/ows"
ACA_LAYERS = ("geomorphic", "benthic")
RAW_FILES = ("wdpa.geojson", *(f"aca_{layer}.geojson" for layer in ACA_LAYERS))
PAGE_SIZE = 2000  # the WDPA service's maxRecordCount


def parse_bbox(text: str) -> tuple[float, float, float, float]:
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be W,S,E,N")
    w, s, e, n = parts
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise argparse.ArgumentTypeError(f"invalid bbox {text}")
    return w, s, e, n


def fetch_wdpa(client: httpx.Client, bbox: tuple[float, float, float, float]) -> list[Any]:
    """Every non-terrestrial WDPA polygon intersecting the box, paged by resultOffset."""
    features: list[Any] = []
    while True:
        response = client.get(
            WDPA_QUERY_URL,
            params={
                "geometry": ",".join(str(v) for v in bbox),
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "outSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "where": "realm <> 'Terrestrial'",
                "outFields": "site_id,name,desig_eng,no_take,gis_m_area",
                "returnGeometry": "true",
                "orderByFields": "objectid",
                "resultOffset": str(len(features)),
                "resultRecordCount": str(PAGE_SIZE),
                "f": "geojson",
            },
        )
        response.raise_for_status()
        page = response.json()
        if "error" in page:
            raise RuntimeError(f"WDPA query failed: {page['error']}")
        features.extend(page["features"])
        more = page.get("exceededTransferLimit") or page.get("properties", {}).get(
            "exceededTransferLimit"
        )
        if not more:
            return features


def fetch_aca(client: httpx.Client, layer: str, bbox: tuple[float, float, float, float]) -> list[Any]:
    """Every ACA polygon of one layer intersecting the box.

    The layers have no primary key, so GeoServer cannot page them (startIndex needs a stable
    order); fetch in one request and refuse a truncated answer.
    """
    w, s, e, n = bbox
    response = client.get(
        ACA_WFS_URL,
        params={
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": f"coral-atlas:{layer}_data_verbose",
            # WFS 2.0 with an EPSG URN takes lat/lon axis order.
            "bbox": f"{s},{w},{n},{e},urn:ogc:def:crs:EPSG::4326",
            "srsName": "EPSG:4326",
            "outputFormat": "application/json",
        },
    )
    response.raise_for_status()
    page = response.json()
    features: list[Any] = page["features"]
    matched = page.get("numberMatched")
    if isinstance(matched, int) and matched != len(features):
        raise RuntimeError(f"ACA {layer}: got {len(features)} of {matched} features; shrink bbox")
    return features


def download(raw_dir: Path, bbox: tuple[float, float, float, float]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=600.0, follow_redirects=True) as client:
        print("downloading WDPA ...", flush=True)
        _write_features(raw_dir / "wdpa.geojson", fetch_wdpa(client, bbox))
        for layer in ACA_LAYERS:
            print(f"downloading ACA {layer} ...", flush=True)
            _write_features(raw_dir / f"aca_{layer}.geojson", fetch_aca(client, layer, bbox))
    (raw_dir / "bbox.json").write_text(json.dumps(list(bbox)))


def _write_features(path: Path, features: list[Any]) -> None:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    print(f"  {path}: {len(features)} features")


def build(raw_dir: Path, out_dir: Path, bbox: tuple[float, float, float, float]) -> None:
    """Clip the cached raw layers to the box and write mpa.parquet and reef_map.parquet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    w, s, e, n = bbox
    envelope = f"ST_MakeEnvelope({w}, {s}, {e}, {n})"

    def clipped(path: Path) -> str:
        # ST_Read tags geometries EPSG:4326; drop the tag so they combine with the envelope.
        geom = "ST_MakeValid(geom::GEOMETRY)"
        return (
            f"SELECT *, ST_Intersection({geom}, {envelope}) AS clipped "
            f"FROM ST_Read('{path.as_posix()}') WHERE ST_Intersects({geom}, {envelope})"
        )

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    mpa_out = out_dir / "mpa.parquet"
    con.execute(f"""
        COPY (
            SELECT CAST(site_id AS VARCHAR) AS wdpa_id, name, desig_eng AS designation,
                   no_take, gis_m_area AS marine_area_km2, clipped AS geom
            FROM ({clipped(raw_dir / "wdpa.geojson")})
            WHERE NOT ST_IsEmpty(clipped)
            ORDER BY wdpa_id
        ) TO '{mpa_out.as_posix()}' (FORMAT PARQUET)
    """)

    reef_out = out_dir / "reef_map.parquet"
    layers = " UNION ALL ".join(
        f"SELECT '{layer}' AS layer, class_name, clipped AS geom "
        f"FROM ({clipped(raw_dir / f'aca_{layer}.geojson')}) WHERE NOT ST_IsEmpty(clipped)"
        for layer in ACA_LAYERS
    )
    con.execute(
        f"COPY ({layers} ORDER BY layer, class_name) TO '{reef_out.as_posix()}' (FORMAT PARQUET)"
    )

    (out_dir / "coverage.json").write_text(json.dumps({"bbox": list(bbox)}) + "\n")

    for out in (mpa_out, reef_out):
        row = con.execute(f"SELECT count(*) FROM read_parquet('{out.as_posix()}')").fetchone()
        print(f"wrote {out}: {row[0] if row else 0} rows")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build data/geo GeoParquet for the demo region")
    parser.add_argument("--bbox", type=parse_bbox, default=DEFAULT_BBOX, help="W,S,E,N")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--raw-dir", type=Path, help="default: <out-dir>/raw")
    parser.add_argument("--offline", action="store_true", help="never download; use raw-dir")
    args = parser.parse_args(argv)

    bbox: tuple[float, float, float, float] = args.bbox
    raw_dir: Path = args.raw_dir or args.out_dir / "raw"
    if args.offline:
        missing = [name for name in RAW_FILES if not (raw_dir / name).is_file()]
        if missing:
            print(f"--offline: missing {missing} in {raw_dir}", file=sys.stderr)
            return 1
    else:
        stamp = raw_dir / "bbox.json"
        if not (stamp.is_file() and tuple(json.loads(stamp.read_text())) == bbox):
            download(raw_dir, bbox)

    build(raw_dir, args.out_dir, bbox)
    return 0


if __name__ == "__main__":
    sys.exit(main())
