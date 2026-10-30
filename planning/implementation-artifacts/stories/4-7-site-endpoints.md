---
status: done
---

# Story 4.7: Site endpoints

As a judge on the reef map,
I want every surveyed site with its latest cover and trend, and each site's survey timeline,
So that the map and the site page show real data instead of mocks.

- Owner: B (taken by guide: Claude Code) · Priority: P0 · Depends on: 1.4, 4.5
- Files: `src/reefcase/api/routes/sites.py`, `src/reefcase/api/main.py`, `tests/api/test_sites.py`
- Done when: the web's `listSites` and `getSite` calls are served by the API, not the mocks

No story owned these two §6.3 rows: 6.4 (reef map) and 6.5 (site page) were built against the
mocks in `web/src/mocks/handlers.ts`, and 4.5 serves the same history to the agent as a tool.

## Acceptance Criteria

**Given** sites in the store, some with completed surveys
**When** `GET /api/sites` is called
**Then** each site with a completed survey is listed with its location, MPA, latest cover, latest
dive date and trend, in the shape of the web's `SiteSummary`

**Given** a known site
**When** `GET /api/sites/{id}` is called
**Then** the site and all its surveys come back, newest first (`SiteDetail`)

**Given** an unknown site id
**When** `GET /api/sites/{id}` is called
**Then** the answer is 404

## Architecture contract

- §6.3: `GET /api/sites` "sites with latest cover and trend"; `GET /api/sites/{id}` "site and
  survey timeline".
- The web's contract is `web/src/api/openapi.snapshot.json` (`SiteSummary`, `SiteDetail`,
  `SiteTrend`): `latest_cover` is required and not null; `SiteTrend` is "cover trend since the
  first survey at the site", one of `declining`, `stable`, `improving`.

## Decisions

- **Only completed surveys count** for the summary (as in 4.5's `site_history`): a site with no
  DONE survey with a cover has no `latest_cover`, so it is left off the map until its first run
  finishes. The detail endpoint still returns every survey, so a running one shows on the
  timeline.
- **Trend** compares live coral in the latest completed survey with the first one: a drop of more
  than 5 percentage points is `declining`, a rise of more than 5 is `improving`, anything else
  (or a single survey) is `stable`. Live coral is the measure the site page headlines, and
  bleaching moves cover from live to bleached, so it shows up as a drop.
- The response models live in the route module: they are API views over `Site` and `Survey`, not
  new domain types, so `core/schemas.py` stays as it is.
- One `surveys.list()` for the map, grouped in Python, instead of one query per site.

## Tasks

1. [x] Tests: the summary shape, latest and trend rules, sites without completed surveys left
   out, detail newest first, 404.
2. [x] `routes/sites.py`, registered under `/api`.
3. [x] `uv run poe gate`.
4. [x] Review against `.opencode/agents/reviewer.md`.

## Lessons

- `request.app.state.store` is untyped, so a bare `[]` built from it is `list[Unknown]` to
  pyright: annotate the accumulator.
- The real OpenAPI types `latest_cover` as an open `{SegClass: number}` map, as it already does
  `Survey.cover`; the web snapshot names it `Cover` with six required keys. Same values on the
  wire (cover always carries every class); left for the web-types check after 4.6 and 5.4.

## Library check

- FastAPI 0.162: `response_model=list[Model]` validates and filters the list; `StrEnum` fields
  serialise as their values, and the class docstring becomes the schema `description`.
