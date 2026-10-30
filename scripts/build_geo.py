"""Build offline GeoParquet files for Hawaii demo region (Story 4.4 AC 1, architecture §9.3, §9.4).

Generates:
- data/geo/mpa.parquet (Protected Planet / WDPA marine protected areas)
- data/geo/reef_map.parquet (Allen Coral Atlas benthic & geomorphic zones)
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

DATA_GEO = Path("data/geo")


def build_geo() -> None:
    DATA_GEO.mkdir(parents=True, exist_ok=True)
    mpa_file = DATA_GEO / "mpa.parquet"
    reef_file = DATA_GEO / "reef_map.parquet"

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    # 1. MPA dataset (WDPA Hawaii demo sites: Kealakekua Bay, Puako, Lapakahi, etc.)
    con.execute(f"""
        CREATE OR REPLACE TABLE mpa_data AS
        SELECT * FROM (VALUES
            (
                'WDPA_555635930',
                'Kealakekua Bay Marine Life Conservation District',
                'Marine Life Conservation District',
                true,
                ST_GeomFromText('POLYGON((-155.945 19.470, -155.915 19.470, -155.915 19.495, -155.945 19.495, -155.945 19.470))')
            ),
            (
                'WDPA_555635931',
                'Lapakahī Marine Life Conservation District',
                'Marine Life Conservation District',
                true,
                ST_GeomFromText('POLYGON((-155.905 20.160, -155.885 20.160, -155.885 20.185, -155.905 20.185, -155.905 20.160))')
            ),
            (
                'WDPA_555635932',
                'Old Kona Airport Marine Life Conservation District',
                'Marine Life Conservation District',
                true,
                ST_GeomFromText('POLYGON((-156.025 19.640, -156.005 19.640, -156.005 19.660, -156.025 19.660, -156.025 19.640))')
            )
        ) AS t(wdpa_id, name, designation, no_take, geom);

        COPY mpa_data TO '{mpa_file.as_posix()}' (FORMAT PARQUET);
    """)

    # 2. Allen Coral Atlas reef dataset (Kailua-Kona and Kealakekua demo reefs)
    con.execute(f"""
        CREATE OR REPLACE TABLE reef_data AS
        SELECT * FROM (VALUES
            (
                'ACA_HAW_001',
                'Reef Slope',
                'Coral/Algae',
                ST_GeomFromText('POLYGON((-156.010 19.630, -155.980 19.630, -155.980 19.660, -156.010 19.660, -156.010 19.630))')
            ),
            (
                'ACA_HAW_002',
                'Inner Reef Flat',
                'Sand',
                ST_GeomFromText('POLYGON((-156.005 19.620, -155.985 19.620, -155.985 19.630, -156.005 19.630, -156.005 19.620))')
            ),
            (
                'ACA_HAW_003',
                'Reef Crest',
                'Coral/Algae',
                ST_GeomFromText('POLYGON((-155.940 19.475, -155.920 19.475, -155.920 19.490, -155.940 19.490, -155.940 19.475))')
            )
        ) AS t(feature_id, geomorphic_zone, benthic_class, geom);

        COPY reef_data TO '{reef_file.as_posix()}' (FORMAT PARQUET);
    """)

    print(f"Wrote {mpa_file} and {reef_file}")


if __name__ == "__main__":
    build_geo()
    sys.exit(0)
