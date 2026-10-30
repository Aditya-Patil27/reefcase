---
status: done
---

# Story 8.1: Historical survey import

As a park manager,
I want past public survey imagery loaded as earlier surveys,
So that the agent can describe change over years (FR14).

- Owner: B (taken by guide: Claude Code) · Priority: P1 · Depends on: 3.5, 2.5
- Files: `scripts/import_history.py`, `data/demo/history_manifest.csv`, `tests/scripts/test_import_history.py`
- Also: `.gitignore` (the downloaded photos), `data/LICENSES.md` (NCRMP rows)
- Done when: gate passes; the demo site has ≥ 2 historical surveys

## Acceptance Criteria

**Given** a manifest of (image path, lat, lon, date, source, licence) for one Hawaii NCRMP
station's 2013, 2016 and 2019 images (architecture §9.5)
**When** the import runs
**Then** it creates `historical` surveys grouped by site and date, segmented by the configured
segmenter, with no agent run

## Architecture contract

- §4.2 `Survey.source = "historical"`; §9.5 NOAA PIFSC ESD NCRMP benthic images, cite PIFSC ESD.
- §2.5 / FR12: a survey within 500 m of an existing site joins it (`sites.find_site_near`).
- 4.5 `site_history` lists only `DONE` surveys with their `cover`, so an imported survey must
  end `DONE` with the cover set by the segment stage.

## Decisions

- Demo station: **HAW-41** (North Kohala, West Hawaii, 20.268 N, 155.860 W). It is the one
  station with photos in 2013 (03 Aug), 2016 (15 Aug) and 2019 (15 Jul) whose 2024 revisit
  (`OCC-HAW-002`) is within 6 m, and it lies inside the `build_geo.py` West Hawaii box.
  Coordinates and dates come from each accession's site-info CSV; 30 + 32 + 30 photos.
- The manifest adds a `site` column (the station code, used as the site name when the import
  creates the site). `source` is the photo's NCEI URL; `image_path` is relative to the manifest.
- Photos are 4000×3000 JPEGs of about 3.3 MB, so they are not committed: the import downloads
  any missing one from its `source` into the gitignored `data/demo/history/`.
- Each photo becomes one frame (`t_sec` = its index), shrunk to at most 1920 px and stored as
  JPEG, scored for quality but never dropped (they are curated survey photos), then the
  existing `segment_stage` segments it and sets the survey cover. No assess or agent stage.
- A site that already has a `DONE` historical survey on that date is skipped, so re-running is
  safe. A survey whose segmentation fails is saved `FAILED` with the reason.
- The licence is validated as non-empty per row; attribution lives in `data/LICENSES.md`
  (Survey has no licence field and core is frozen).

## Tasks

1. [x] Tests: manifest parsing and validation, grouping by site and date, sites 500 m apart,
   re-run skip, download of a missing photo, the shipped manifest.
2. [x] `data/demo/history_manifest.csv` for HAW-41.
3. [x] `scripts/import_history.py`.
4. [x] Run it on the real photos with the fake segmenter.
5. [x] `uv run poe gate`.
6. [x] Review against `.opencode/agents/reviewer.md`.

## Lessons

- Real run (fake segmenter, scratch data dir): downloaded the 92 photos (568 MB, ~8 min on
  this link), imported 3 `done` surveys (30/32/30 frames), `site_history` lists all three; a
  re-run skips them. The demo deployment must run it with `REEFCASE_SEGMENTER=sam3_modal` so
  the covers are real (8-3 / 8-4).
- A script loaded through importlib must be in `sys.modules` before `exec_module`, or
  `@dataclass` crashes during class creation.

## Library check

No new library. httpx (already a dependency) downloads the photos; NCEI serves each accession
file over plain HTTPS under `https://www.ncei.noaa.gov/data/oceans/archive/arcNNNN/<acc>/1.1/data/0-data/`.
