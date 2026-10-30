---
status: done
---

# Story 2.5: Site matching

As a park manager,
I want surveys of the same spot grouped into one site,
So that change over time is visible (FR12).

- Owner: B · Priority: P0 · Depends on: 2.1
- Files: `src/reefcase/store/repos.py` (add `find_site_near`), `tests/store/test_site_match.py`
- Done when: gate passes

## Acceptance Criteria

**Given** an existing site
**When** a survey is created 300 m away
**Then** it is attached to that site

**Given** no site within 500 m
**When** a survey is created
**Then** a new site is created with name `site_name`, or `"Reef @ lat,lon"` if none was given

## Architecture contract

- §4.2: `Site.location` is a WGS84 `GeoPoint`; `sites` stores `lat`/`lon` columns.
- §6.3: `POST /api/surveys` takes `lat`, `lon`, `dive_date`, optional `site_name`.

## Decisions

- `SiteRepo.find_site_near(location, radius_m=SITE_MATCH_RADIUS_M)` returns the
  **nearest** site within 500 m (haversine in SQL, R = 6371 km), so two nearby
  sites never split surveys arbitrarily. Plain SQL math, no `spatial` call.
- Wiring it into `POST /api/surveys` (`api/routes/surveys.py`) is needed for the
  ACs ("when a survey is created"). A matched site keeps its own name; a new
  `site_name` on a later upload does not rename it.
- `tests/api/test_upload.py::test_upload_names_the_site` posted twice at the same
  spot; it now posts the named survey ~11 km away so each still gets its own site.

## Tasks

1. [x] Tests: repo (300 m match, 600 m miss, nearest of two, empty) and API
   (300 m attaches, 1 km creates a `Reef @` site).
2. [x] `find_site_near` + `SITE_MATCH_RADIUS_M` in `store/repos.py`.
3. [x] Use it in `POST /api/surveys`.
4. [x] `uv run poe gate`.
5. [x] Review against `.opencode/agents/reviewer.md`.

## Lessons

None beyond the repository rules.

## Library check

No third-party API; DuckDB built-in math functions (`asin`, `sqrt`, `radians`, `pow`).
