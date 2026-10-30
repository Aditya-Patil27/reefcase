---
status: done
---

# Story 4.2: heat_stress (NOAA Coral Reef Watch)

As the agent,
I want the degree-heating-week and SST-anomaly history at the site,
So that I can test the heat-stress hypothesis.

- Owner: B (sprint-status says C; taken by guide: Claude Code) · Priority: P0 · Depends on: 4.1
- Files: `src/reefcase/tools/heat_stress.py`, `tests/tools/test_heat_stress.py`, `tests/cassettes/heat_stress/*.yaml`
- Done when: gate passes with `--record-mode=none`

## Acceptance Criteria

**Given** a site and a 90-day window
**When** `heat_stress` runs against the ERDDAP endpoint in architecture §9
**Then** `data` has daily `dhw`, `sst_anomaly`, `alert_level` and `max_dhw`, and `source_url` is the exact query URL

**Given** a site over land or outside coverage (all values missing)
**When** queried
**Then** it returns `data.available=false`, not an exception

## Architecture contract

- §5.4: `heat_stress(params, ctx) -> ToolResult`, params `site_id`, `start`, `end`; registered
  through `tools.registry.tool`; HTTP only through `tools.http.get_json`.
- §9.2: PacIOOS ERDDAP `dhw_5km`, variables `CRW_DHW`, `CRW_SSTANOMALY`, `CRW_BAA`
  (raw value as `alert_level`); record the snapped lat/lon; all-NaN → `available=false`.

## Decisions

- Live probe (2026-10-30): a stop date after the newest data (~2 days behind today)
  is a **404**, not a clipped result. So when `end` is within `RECENT_DAYS` (7) of
  today the query's stop is ERDDAP's `(last)`; a fresh dive would otherwise never
  get heat data.
- ERDDAP's 404 ("query produced no matching results", e.g. a window before 1985 or
  after the data) is "outside coverage" → `available=false`. Other failures raise
  `ExternalServiceError` from `get_json`.
- `data` shape: `available`, `lat`, `lon` (snapped cell), `daily` =
  `[{date, dhw, sst_anomaly, alert_level}]`, `max_dhw`, `max_dhw_date`; missing
  days keep `null`.
- Params: `end >= start` and a window of at most 366 days, so one call stays small.

## Tasks

1. [x] Record cassettes (Hawaii 2019 heatwave window; a land cell).
2. [x] Tests: AC1 via cassette, AC2 via cassette + 404, `(last)` for a recent end,
   5xx raises, a body without `table.rows` raises, param validation, registry wiring.
3. [x] `tools/heat_stress.py`.
4. [x] `uv run poe gate`.
5. [x] Review against `.opencode/agents/reviewer.md`.

## Lessons

- ERDDAP 404s on a stop date past its newest day (~2 days behind); `(last)` fixes recent windows.
- httpx's default 5 s timeout is too short for ERDDAP; the recording client uses 60 s.
- `decode_compressed_response` in `vcr_config` keeps cassette bodies readable JSON.

## Library check

ERDDAP griddap `.json` (`table.columnNames` / `rows`), probed live 2026-10-30.
pytest-recording 0.14.0 (`@pytest.mark.vcr`, `vcr_cassette_dir` fixture, default
`--record-mode=none`), vcrpy 9.2.0 with httpx.
