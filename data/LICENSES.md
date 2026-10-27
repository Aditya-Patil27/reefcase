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

The frames are painted from the hand masks (256×256, 8-bit grayscale, pixel value = §4.2 class
id); frame `06` is intentionally blurred. `clip_10s.mp4` is 10.0 s at 4 fps, cycling the six
frames, so a 0.5 s extraction stride yields ~20 candidates (Story 2.3).
