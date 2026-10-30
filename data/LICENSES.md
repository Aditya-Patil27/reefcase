# Data licences and attribution

Everything ReefCase downloads, ships or redistributes is listed here with its
licence and the obligation we carry. Demo and test fixtures are listed under
"Local fixtures".

| Source | Licence | Obligation |
|---|---|---|
| GFW | CC BY-NC 4.0 | "Powered by Global Fishing Watch"; non-commercial |
| NOAA CRW, NCRMP | US Gov | cite NOAA CRW / PIFSC ESD |
| Allen Coral Atlas | CC BY 4.0 | cite doi:10.5281/zenodo.3833242 |
| WDPA | non-commercial | cite UNEP-WCMC & IUCN |
| Coralscapes | Apache-2.0 | cite the paper |
| Ifremer clips | CC BY 4.0 | credit Ifremer |
| SAM 3 | SAM License | acknowledge SAM; include licence if redistributing |
| Muse Spark Open / Glimmer-Reef | Muse Model License | "Built with Muse Spark Open"; ship licence + Usage Policy |

## Shipped geo data

Built by `scripts/build_geo.py` for West Hawaii (bbox −156.10, 19.40, −155.80, 20.30). These are clipped
subsets only; the raw downloads stay in the gitignored `data/geo/raw/`.

| File | Source URL | Licence |
|---|---|---|
| `data/geo/mpa.parquet` | https://data-gis.unep-wcmc.org/server/rest/services/ProtectedSites/The_World_Database_of_Protected_Areas/MapServer/1 (WDPA, non-terrestrial) | WDPA terms, non-commercial; cite UNEP-WCMC & IUCN, Protected Planet |
| `data/geo/reef_map.parquet` | https://allencoralatlas.org/geoserver/ows (`coral-atlas:geomorphic_data_verbose`, `coral-atlas:benthic_data_verbose`) | CC BY 4.0; cite Allen Coral Atlas, doi:10.5281/zenodo.3833242 |

## Local fixtures

| Fixture | Source URL | Licence |
|---|---|---|
| `tests/fixtures/frames/01.jpg` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/frames/02.jpg` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/frames/03.jpg` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/frames/04.jpg` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/frames/05.jpg` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/frames/06.jpg` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/masks/01.png` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/masks/02.png` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/masks/03.png` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/masks/04.png` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/masks/05.png` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/masks/06.png` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `tests/fixtures/clip_10s.mp4` | self-authored, generated offline for tests (`.scratch/gen_fixtures.py`) | CC0 (test fixture) |
| `web/public/demo/frames/01–08.jpg`, `web/public/demo/masks/01–08.png` | https://huggingface.co/datasets/EPFL-ECEO/coralscapes (test split rows test-2/1/11, test-1/0/36, test-1/1/24, test-2/1/12, test-2/0/60, test-2/1/18, test-2/0/17, test-2/0/12; centre-cropped to 16:9, 960×540; masks are the Coralscapes labels remapped to the six §4.2 classes) | Apache-2.0; cite the Coralscapes paper |

The frames are painted from the hand masks (256×256, 8-bit grayscale, pixel value = §4.2 class
id); frame `06` is intentionally blurred. `clip_10s.mp4` is 10.0 s at 4 fps, cycling the six
frames, so a 0.5 s extraction stride yields ~20 candidates (Story 2.3).

## Distillation corpus sources (Epic 7)

| Dataset slice | Source URL | Licence |
|---|---|---|
| Coralscapes train + val (pseudo-label input only; excludes test split) | https://zenodo.org/records/7879150 | Apache-2.0 |
| NOAA NCRMP imagery (non-demo regions used for pseudo-labelling) | https://www.fisheries.noaa.gov/inport/item/27322 | US Gov |
