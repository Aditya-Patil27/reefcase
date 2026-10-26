---
status: approved
stepsCompleted: [validate-prerequisites, design-epics, create-stories, final-validation]
inputDocuments: [prd.md, architecture.md]
---

# ReefCase - Epic Breakdown

## Overview

This document breaks the PRD and Architecture down into epics and stories. Each story is sized for one coding-agent session (OpenCode + DeepSeek) and lists:

- **Owner**: A = vision ML, B = agent/backend (Aditya), C = frontend/demo, Opus = orchestrator-authored contract work
- **Priority**: P0/P1/P2 (PRD §7)
- **Depends on**: stories that must be `done` first
- **Files**: the only files the story may create or modify (plus their tests)
- **Done when**: the exact command that must pass

**Rules for the coding agent:** implement only the listed files, never edit `src/reefcase/core/` (except in Epic 1), and treat the interfaces in `architecture.md` §4–6 as fixed. If a story seems to need a contract change, stop and raise it to the orchestrator.

## Requirements Inventory

### Functional Requirements

FR1 upload video + site + date · FR2 frame extraction and quality scoring · FR3 fail fast on too few frames · FR4 class segmentation · FR5 percent cover · FR6 swappable segmenter backends · FR7 structured frame assessment · FR8 agent tools · FR9 typed Investigation · FR10 mandatory citations · FR11 teacher/student disagreement · FR12 site matching · FR13 site timeline · FR14 historical import · FR15 upload page · FR16 live investigation view · FR17 map view · FR18 case file with evidence · FR19 Telegram bot · FR20 pseudo-labelling · FR21 student evaluation · FR22 Glimmer-Reef fine-tune

### NonFunctional Requirements

NFR1 60 s clip ≤ 3 min · NFR2 first event ≤ 5 s · NFR3 providers via env only · NFR4 no live APIs in tests · NFR5 ruff + pyright strict · NFR6 licensed data only · NFR7 secrets in .env · NFR8 public repo, built-during-hackathon README

### Additional Requirements

- Layering enforced by import-linter (architecture §3).
- Kaggle scripts must run unchanged locally.
- Every dataset, clip and image is recorded in `data/LICENSES.md` before it is committed or used.

### UX Design Requirements

UX1 dark ocean theme · UX2 monospace live trace panel · UX3 mask overlay toggle on frames · UX4 every evidence chip is clickable · UX5 works at 1280×720 for the demo recording

### FR Coverage Map

| FR | Stories |
|---|---|
| FR1 | 2.1 |
| FR2, FR3 | 2.3, 2.4 |
| FR4, FR5, FR6 | 3.1, 3.2, 3.3, 3.4, 3.5, 7.4 |
| FR7 | 5.1 |
| FR8 | 4.1–4.6 |
| FR9, FR10 | 5.2, 5.3, 5.4 |
| FR11 | 5.5 |
| FR12 | 2.5 |
| FR13 | 6.6 |
| FR14 | 8.1 |
| FR15–FR18 | 6.1–6.5 |
| FR19 | 8.2 |
| FR20, FR21 | 7.1, 7.2, 7.3 |
| FR22 | 7.5, 7.6, 7.7 |

## Epic List

1. Foundation & contracts (Opus, Oct 27)
2. Survey pipeline backbone (B)
3. Reef vision (A)
4. Context tools (B)
5. Assessment & investigation agent (B)
6. Web app (C)
7. Distillation (A, B)
8. History, bot & ship (B, C)

### Schedule (IST)

| Day | A (vision) | B (backend/agent) | C (frontend) |
|---|---|---|---|
| Tue Oct 27 | 7.1 data + licences, SAM access | review Epic 1, 2.1 | 6.1 against mock events |
| Wed Oct 28 | 3.1, 3.2 | 2.2, 2.3, 2.4 | 6.2, 6.3 |
| Thu Oct 29 | 3.3, 3.5 | 2.5, 4.1, 4.2 | 6.3, 6.4 |
| Fri Oct 30 | 3.4, 7.1 run | 4.3–4.6, 5.1 | 6.4, 6.5 |
| Sat Oct 31 | 7.2 | 5.2, 5.3, 5.4 — **P0 demo e2e** | 6.5, polish |
| Sun Nov 1 | 7.3, 7.4 | 5.5, 8.1 | 6.6 |
| Mon Nov 2 | 7.5 → 7.6 | 8.3 deploy | 8.2 bot |
| Tue Nov 3 | 7.7 | deploy hardening | 8.4 demo rehearsal |
| Wed Nov 4 | — | 8.5 README | demo video, X post, **submit by 21:00 ET** |

---

## Epic 1: Foundation & contracts

Freeze the contracts that every other story builds against, so three people and a coding model can work in parallel without drifting.

### Story 1.1: Repository scaffold and quality gates

As a developer,
I want a repo where lint, types, import layering and tests run with one command,
So that every later story has an objective definition of done.

- Owner: Opus · Priority: P0 · Depends on: none
- Files: `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`, `src/reefcase/__init__.py`, `tests/test_smoke.py`, `.github/workflows/ci.yml`, `data/LICENSES.md` (`AGENTS.md` already exists and is frozen; don't edit it)
- Done when: `uv run poe gate` passes locally and in CI. `pyproject.toml` defines a poethepoet task `gate` that runs `ruff check`, `ruff format --check`, `pyright`, `lint-imports` and `pytest -m "not gpu and not live"`

**Acceptance Criteria:**

**Given** a fresh clone
**When** `uv sync` then the done-when command run
**Then** all four gates pass
**And** `lint-imports` contains the layer contract from architecture §3

**Given** `pyproject.toml`
**When** `uv run poe gate` runs
**Then** pytest registers the `gpu` and `live` markers, and the gate skips both

### Story 1.2: Core schemas, IDs and events

As a developer,
I want every domain type and event defined once in `reefcase.core`,
So that API, pipeline, agent and web all share one contract.

- Owner: Opus · Priority: P0 · Depends on: 1.1
- Files: `src/reefcase/core/{ids,schemas,events,errors}.py`, `tests/core/test_schemas.py`, `tests/core/test_events.py`
- Done when: the 1.1 gate command passes

**Acceptance Criteria:**

**Given** the schemas in architecture §4.2
**When** each model is built from valid data and round-tripped through JSON
**Then** it is equal to the original

**Given** a `Finding` or `Hypothesis` with empty evidence
**When** it is validated
**Then** validation fails

**Given** a JSON event of any type in §4.3
**When** parsed with `EventAdapter`
**Then** the correct event class is returned

### Story 1.3: Settings and model provider factory

As a developer,
I want providers configured only by environment variables,
So that we can switch between Baseten, Modal, Fireworks and Oxion without code changes (NFR3).

- Owner: Opus · Priority: P0 · Depends on: 1.2
- Files: `src/reefcase/core/config.py`, `src/reefcase/llm/providers.py`, `tests/llm/test_providers.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** `REEFCASE_LLM_AGENT_*` set
**When** `build_model("agent", settings)` is called
**Then** it returns an OpenAI-compatible pydantic-ai model pointing at that base URL and model name

**Given** no `REEFCASE_LLM_STUDENT_*` variables
**When** `build_model("student", settings)` is called
**Then** it returns `None`

### Story 1.4: Store foundation

As a developer,
I want a DuckDB store with migrations, repos and blob paths,
So that every stage persists through one writer.

- Owner: Opus · Priority: P0 · Depends on: 1.2
- Files: `src/reefcase/store/{db,repos,blobs}.py`, `src/reefcase/store/migrations/001_sites_surveys_events.sql`, `tests/store/test_store.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** an empty data dir
**When** `Store.open(path)` runs
**Then** migrations are applied once, the spatial extension is loaded, and `schema_migrations` lists `001`

**Given** a site and a survey
**When** saved and re-read via the repos
**Then** they equal the originals

**Given** two concurrent writes
**When** issued through `Store`
**Then** both succeed (serialized by the lock)

### Story 1.5: Test fixtures and fakes

As a developer,
I want shared fixtures and fake implementations,
So that every story's tests run offline and fast.

- Owner: Opus · Priority: P0 · Depends on: 1.2, 1.4
- Files: `tests/conftest.py`, `tests/fixtures/frames/*.jpg` (6 licensed frames), `tests/fixtures/masks/*.png` (hand masks), `tests/fixtures/clip_10s.mp4`, `src/reefcase/vision/fake.py`, `data/LICENSES.md`
- Done when: gate passes

**Acceptance Criteria:**

**Given** the fixtures
**When** listed in `data/LICENSES.md`
**Then** each has a source URL and licence

**Given** `FakeSegmenter`
**When** it segments any image
**Then** it returns a deterministic class map of the same height and width

---

## Epic 2: Survey pipeline backbone

A user can upload a clip, the job runs, frames are extracted and scored, and events stream back live.

### Story 2.1: Survey upload endpoint

As a diver,
I want to upload a clip with a location and date,
So that my dive becomes a survey (FR1).

- Owner: B · Priority: P0 · Depends on: 1.4
- Files: `src/reefcase/api/main.py`, `src/reefcase/api/routes/surveys.py`, `tests/api/test_upload.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a valid mp4 ≤ 500 MB with lat, lon and dive_date
**When** POSTed to `/api/surveys`
**Then** the response is `201` with a `Survey` in status `queued`, and the video is stored at `blobs/{survey_id}/video.mp4`

**Given** lat outside −90..90, or a non-video file
**When** POSTed
**Then** the response is `422` with a field-level error

### Story 2.2: Job runner, event bus and SSE

As a diver,
I want to see progress live,
So that I know the investigation is working (NFR2).

- Owner: B · Priority: P0 · Depends on: 2.1
- Files: `src/reefcase/pipeline/{runner,bus}.py`, `src/reefcase/api/routes/events.py`, `src/reefcase/store/migrations/002_events_index.sql`, `tests/pipeline/test_bus.py`, `tests/api/test_sse.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a submitted survey whose stages are stubbed
**When** a client opens `/api/surveys/{id}/events`
**Then** it receives `survey_started` within 5 s, with `id:` equal to `seq`

**Given** a client reconnecting with `Last-Event-ID: 3`
**When** the stream reopens
**Then** it receives events from seq 4 onward with no gaps or duplicates

**Given** a stage raising an exception
**When** the job runs
**Then** the survey becomes `failed` and `survey_failed` is emitted with the reason

### Story 2.3: Frame extraction

As the pipeline,
I want candidate frames sampled from the video,
So that later stages have images to analyse (FR2).

- Owner: B · Priority: P0 · Depends on: 2.2
- Files: `src/reefcase/ingest/frames.py`, `src/reefcase/store/migrations/003_frames.sql`, `tests/ingest/test_frames.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** `tests/fixtures/clip_10s.mp4`
**When** `extract_candidates(path, every_sec=0.5)` runs
**Then** it yields ~20 RGB frames with their `t_sec`, decoded with PyAV

**Given** a corrupt file
**When** extraction runs
**Then** it raises `IngestError("unreadable video")`

### Story 2.4: Quality scoring and fail-fast

As a diver,
I want bad footage rejected with a clear reason,
So that I'm not shown a meaningless report (FR2, FR3).

- Owner: B · Priority: P0 · Depends on: 2.3
- Files: `src/reefcase/ingest/quality.py`, `src/reefcase/pipeline/stages.py` (ingest stage only), `tests/ingest/test_quality.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a frame
**When** `score(image)` runs
**Then** it returns `QualityScore` with blur = variance of Laplacian, color_cast = mean |a*|+|b*| in CIELAB, turbidity = 1 − RMS contrast; `passed` uses thresholds from module constants

**Given** a survey
**When** the ingest stage runs
**Then** the top `KEEP_FRAMES` passing frames are saved as JPEG blobs with `frame_scored` events

**Given** fewer than `MIN_FRAMES` passing frames
**When** the ingest stage runs
**Then** the survey fails with the most common rejection reason ("too blurry", "too murky", "colour cast")

### Story 2.5: Site matching

As a park manager,
I want surveys of the same spot grouped into one site,
So that change over time is visible (FR12).

- Owner: B · Priority: P0 · Depends on: 2.1
- Files: `src/reefcase/store/repos.py` (add `find_site_near`), `tests/store/test_site_match.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** an existing site
**When** a survey is created 300 m away
**Then** it is attached to that site

**Given** no site within 500 m
**When** a survey is created
**Then** a new site is created with name `site_name`, or `"Reef @ lat,lon"` if none was given

---

## Epic 3: Reef vision

Every kept frame is segmented into reef classes with percent cover, behind a swappable backend.

### Story 3.1: Segmenter interface and cover computation

As the pipeline,
I want one segmenter interface and a cover calculator,
So that backends are interchangeable (FR5, FR6).

- Owner: A · Priority: P0 · Depends on: 1.5
- Files: `src/reefcase/vision/{segmenter,cover}.py`, `tests/vision/test_cover.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a mask with known class counts
**When** `cover_from_mask` runs
**Then** the fractions match and sum to 1.0 (±1e-6)

**Given** `REEFCASE_SEGMENTER=fake`
**When** `build_segmenter` is called
**Then** it returns `FakeSegmenter`

### Story 3.2: SAM 3 local backend

As the pipeline,
I want SAM 3 text-prompted segmentation turned into a class map,
So that frames get real reef segmentation (FR4).

- Owner: A · Priority: P0 · Depends on: 3.1
- Files: `src/reefcase/vision/sam3.py`, `tests/vision/test_sam3.py` (marked `gpu`)
- Done when: gate passes; `pytest -m gpu tests/vision/test_sam3.py` passes on a Kaggle T4

**Acceptance Criteria:**

**Given** a fixture frame
**When** `Sam3Segmenter.segment` runs
**Then** it returns an HxW uint8 map, painted in priority order sand < rubble < algae < coral (architecture §5.1)

**Given** the hand masks in `tests/fixtures/masks`
**When** compared with SAM 3 output
**Then** mean IoU for coral vs non-coral ≥ 0.5 (printed in the test output)

**Given** the four text prompts
**When** one frame is segmented
**Then** vision features are computed once and reused for every prompt (architecture §5.1)

**Given** the RTX 3050 (6 GB)
**When** the gpu test runs once in fp16
**Then** peak VRAM and ms/frame are recorded in the story's dev notes, or the OOM is. This decides the laptop fallback (architecture §12).

### Story 3.3: Bleached vs live coral split

As a park manager,
I want coral pixels split into live and bleached,
So that bleaching is measured, not guessed (FR4).

- Owner: A · Priority: P0 · Depends on: 3.1
- Files: `src/reefcase/vision/bleaching.py`, `tests/vision/test_bleaching.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a coral mask and an image
**When** `classify_coral_pixels` runs
**Then** pixels with L* ≥ 80 and chroma ≤ 12 become `bleached_coral`, and others `live_coral`

**Given** pure-white and saturated-brown synthetic patches
**When** classified
**Then** they are bleached and live respectively

### Story 3.4: SAM 3 on Modal

As the deployed demo,
I want segmentation served from a GPU endpoint,
So that the API container doesn't need a GPU.

- Owner: A · Priority: P0 · Depends on: 3.2
- Files: `ml/modal/sam_endpoint.py`, `src/reefcase/vision/modal_client.py`, `tests/vision/test_modal_client.py` (cassette)
- Done when: gate passes; `modal deploy ml/modal/sam_endpoint.py` succeeds

**Acceptance Criteria:**

**Given** a deployed endpoint
**When** `ModalSegmenter.segment` posts a JPEG
**Then** it receives a PNG class map with the same contract as 3.2

**Given** Modal credits are not granted
**When** this story is reached
**Then** it is skipped, and the demo uses the laptop fallback (architecture §12). The segmenter there is SAM 3 if the 3.2 VRAM check passed, otherwise ReefStudent (7.4), with demo-clip SAM 3 masks precomputed on Kaggle until 7.4 lands.

### Story 3.5: Segmentation stage

As a diver,
I want masks to appear live as frames are processed,
So that I can see the reef being analysed.

- Owner: A · Priority: P0 · Depends on: 2.4, 3.1, 3.3
- Files: `src/reefcase/pipeline/stages.py` (segment stage), `src/reefcase/store/migrations/004_segmentations.sql`, `tests/pipeline/test_segment_stage.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** kept frames and the `FakeSegmenter`
**When** the segment stage runs
**Then** each frame gets a stored mask PNG, a `Segmentation` row and a `segmented` event with `mask_url`

**Given** all frames are segmented
**When** the stage ends
**Then** `survey.cover` is the pixel-weighted mean of the frame covers

---

## Epic 4: Context tools

The agent can query ocean heat stress, vessel activity, reef geomorphology, MPA status and site history, with every result stored and citable.

### Story 4.1: Tool framework and result cache

As the agent,
I want tools with typed params that persist every result,
So that each piece of evidence has an ID to cite (FR8, FR10).

- Owner: B · Priority: P0 · Depends on: 1.4
- Files: `src/reefcase/tools/{http,registry}.py`, `src/reefcase/store/migrations/005_tool_results.sql`, `tests/tools/test_registry.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a tool called twice with the same params
**When** the second call runs
**Then** it returns the stored `ToolResult` with the same `tr_…` ID and makes no HTTP request

**Given** `GET /api/tool-results/{id}`
**When** called
**Then** it returns that `ToolResult`

### Story 4.2: heat_stress (NOAA Coral Reef Watch)

As the agent,
I want the degree-heating-week and SST-anomaly history at the site,
So that I can test the heat-stress hypothesis.

- Owner: B · Priority: P0 · Depends on: 4.1
- Files: `src/reefcase/tools/heat_stress.py`, `tests/tools/test_heat_stress.py`, `tests/cassettes/heat_stress/*.yaml`
- Done when: gate passes with `--record-mode=none`

**Acceptance Criteria:**

**Given** a site and a 90-day window
**When** `heat_stress` runs against the ERDDAP endpoint in architecture §9
**Then** `data` has daily `dhw`, `sst_anomaly`, `alert_level` and `max_dhw`, and `source_url` is the exact query URL

**Given** a site over land or outside coverage (all values missing)
**When** queried
**Then** it returns `data.available=false`, not an exception

### Story 4.3: vessel_activity (Global Fishing Watch)

As the agent,
I want satellite-radar vessel detections and fishing effort near the site,
So that I can test the fishing-pressure and physical-damage hypotheses.

- Owner: B · Priority: P0 · Depends on: 4.1
- Files: `src/reefcase/tools/vessels.py`, `tests/tools/test_vessels.py`, `tests/cassettes/vessels/*.yaml`
- Done when: gate passes with `--record-mode=none`

**Acceptance Criteria:**

**Given** a site, `radius_km` ≤ 20 and a date range
**When** `vessel_activity` runs against the GFW endpoints in architecture §9
**Then** `data` has `sar_detections.total`, `sar_detections.unmatched_to_ais` with points, and `fishing_hours`

**Given** `radius_km` > 20
**When** called
**Then** validation fails before any HTTP call

**Given** the result
**When** it is serialized
**Then** it contains no vessel names, MMSI or IMO numbers (activity patterns only — PRD §8)

**Given** two concurrent `vessel_activity` calls
**When** they run
**Then** GFW reports are requested one at a time, and a 524 is recovered via the last-report endpoint (architecture §9.1)

### Story 4.4: reef_map and mpa_boundary (offline GeoParquet)

As the agent,
I want reef zone and protected-area status for the site,
So that findings are placed in context (e.g. "inside a no-take zone").

- Owner: B · Priority: P0 · Depends on: 4.1
- Files: `scripts/build_geo.py`, `data/geo/reef_map.parquet`, `data/geo/mpa.parquet`, `src/reefcase/tools/{reef_map,mpa}.py`, `tests/tools/test_geo_tools.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** the downloaded Allen Coral Atlas and WDPA files for the demo region (licences in `data/LICENSES.md`)
**When** `scripts/build_geo.py` runs
**Then** it writes the two GeoParquet files clipped to the region

**Given** a point inside a known MPA polygon
**When** `mpa_boundary` runs
**Then** `inside_mpa=true` with its name and `no_take` flag

### Story 4.5: site_history

As the agent,
I want past surveys of this site,
So that I can describe change, not just state.

- Owner: B · Priority: P0 · Depends on: 4.1, 2.5
- Files: `src/reefcase/tools/history.py`, `tests/tools/test_history.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a site with 3 completed surveys
**When** `site_history` runs
**Then** it returns them ordered by dive_date with cover, excluding the current survey

### Story 4.6: Map layer endpoints

As the web map,
I want GeoJSON for MPA, reef and vessel layers,
So that the map shows the evidence the agent used.

- Owner: B · Priority: P0 · Depends on: 4.3, 4.4
- Files: `src/reefcase/api/routes/geo.py`, `tests/api/test_geo.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** `GET /api/geo/mpa` or `/api/geo/reef`
**When** called with a bbox
**Then** it returns a GeoJSON FeatureCollection clipped to the bbox

**Given** `GET /api/geo/vessels?survey_id=`
**When** that survey's agent called `vessel_activity`
**Then** it returns the detection points from that tool result

---

## Epic 5: Assessment & investigation agent

Frames get structured assessments, and the agent investigates causes and produces a cited case file.

### Story 5.1: Frame assessor

As the pipeline,
I want a structured health assessment per frame from Muse Spark Open,
So that the agent reasons over consistent evidence (FR7).

- Owner: B · Priority: P0 · Depends on: 1.3, 3.5
- Files: `src/reefcase/llm/assess.py`, `src/reefcase/pipeline/stages.py` (assess stage), `src/reefcase/store/migrations/006_assessments.sql`, `tests/llm/test_assess.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a frame, its image and its segmentation
**When** `assess_frame` runs with a `FunctionModel` returning valid JSON
**Then** a `FrameAssessment` is stored and an `assessed` event is emitted

**Given** the Agent definition
**When** inspected
**Then** it uses tool-call output, not `NativeOutput` (architecture §5.2)

**Given** a real Baseten key (manual, not in CI)
**When** `uv run python -m reefcase.llm.assess --smoke tests/fixtures/frames/01.jpg` runs
**Then** it returns a valid `FrameAssessment`. This confirms the model slug and the image-input payload format, which are UNVERIFIED in architecture §9.7. Record the working values in `.env.example`.

**Given** the model returns invalid output twice
**When** assessing
**Then** the frame is skipped with a logged warning, and the stage continues

**Given** 24 frames
**When** the stage runs
**Then** assessments run with concurrency 4

### Story 5.2: Investigator agent

As a park manager,
I want an agent that calls tools and concludes with ranked hypotheses,
So that I get a cause, not just a number (FR8, FR9).

- Owner: B · Priority: P0 · Depends on: 4.2, 4.3, 4.4, 4.5, 5.1
- Files: `src/reefcase/agent/investigator.py`, `src/reefcase/agent/prompts/investigator.md`, `tests/agent/test_investigator.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a `FunctionModel` scripted to call `heat_stress` then `vessel_activity` then return a draft
**When** `investigate` runs
**Then** `tool_called` and `tool_returned` events are emitted for each call in order, and an `Investigation` is returned

**Given** the system prompt
**When** read
**Then** it tells the model to consider every `Cause`, to cite frame IDs and `tr_…` IDs only, and never to name vessels

### Story 5.3: Citation validator and repair loop

As a judge,
I want every claim backed by evidence,
So that the agent is verifiable (FR10).

- Owner: B · Priority: P0 · Depends on: 5.2
- Files: `src/reefcase/agent/citations.py`, `tests/agent/test_citations.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a draft citing an unknown ID
**When** validated
**Then** `ModelRetry` is raised, listing the offending statements

**Given** the model fails to repair after 2 retries
**When** finalising
**Then** uncited findings are dropped, the verdict starts with "Partial:", and the remaining claims are all valid

### Story 5.4: Investigate stage and report persistence

As a diver,
I want the finished case file stored and announced,
So that the web view can show it.

- Owner: B · Priority: P0 · Depends on: 5.3
- Files: `src/reefcase/pipeline/stages.py` (investigate stage), `src/reefcase/store/migrations/007_investigations.sql`, `src/reefcase/api/routes/surveys.py` (add `/investigation`, `/frames`), `tests/pipeline/test_e2e_fake.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** the fake segmenter, a `FunctionModel` and cassette-backed tools
**When** a survey runs end to end
**Then** the event stream ends in `report_ready`, `GET /investigation` returns it, and the survey is `done`

### Story 5.5: Teacher/student disagreement

As a judge,
I want the system to notice when its fast model is unsure,
So that distillation doesn't silently degrade quality (FR11).

- Owner: B · Priority: P1 · Depends on: 5.4, 7.4
- Files: `src/reefcase/agent/disagreement.py`, `src/reefcase/pipeline/stages.py` (segment stage: dual mode), `tests/agent/test_disagreement.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** `REEFCASE_SEGMENTER=student` and SAM 3 available
**When** a frame's student mask has mean IoU < 0.5 against SAM 3 on live and bleached coral
**Then** the SAM 3 mask is used, a `disagreement` event is emitted, and the frame ID is added to `uncertain_frames`

---

## Epic 6: Web app

Divers upload and watch the investigation live. Managers explore the reef map and case files.

### Story 6.1: Web scaffold, typed client and event reducer

As a frontend developer,
I want a typed client generated from OpenAPI and a reducer for events,
So that the UI can't drift from the API.

- Owner: C · Priority: P0 · Depends on: 1.2
- Files: `web/**` scaffold, `web/src/api/{schema.d.ts,client.ts}`, `web/src/live/reducer.ts`, `web/src/live/reducer.test.ts`, `web/src/mocks/events.json`
- Done when: `pnpm typecheck && pnpm lint && pnpm test && pnpm build`

**Acceptance Criteria:**

**Given** `web/openapi.json`
**When** `pnpm gen:api` runs
**Then** `schema.d.ts` is regenerated, and the build fails if the code uses a field that doesn't exist

**Given** the mock event sequence
**When** fed to the reducer
**Then** the state has frames with covers and masks, the tool calls with results, the findings and `reportReady=true`

### Story 6.2: Upload page

As a diver,
I want to drop a clip and pin my dive site,
So that I can start an investigation in seconds (FR15).

- Owner: C · Priority: P0 · Depends on: 6.1, 2.1
- Files: `web/src/routes/upload.tsx`, `web/src/components/SitePicker.tsx`
- Done when: web gate passes

**Acceptance Criteria:**

**Given** a video file, a map pin and a date
**When** submitted
**Then** a progress bar shows the upload, and the page navigates to `/surveys/$id` when it completes

**Given** a 422 response
**When** shown
**Then** the field errors appear next to their inputs

### Story 6.3: Live investigation view

As a diver,
I want to watch frames, masks and the agent's tool calls appear live,
So that I trust what it concludes (FR16, UX2, UX3).

- Owner: C · Priority: P0 · Depends on: 6.1, 2.2
- Files: `web/src/routes/surveys.$id.tsx`, `web/src/live/useEventStream.ts`, `web/src/components/{FrameGrid,TracePanel}.tsx`
- Done when: web gate passes

**Acceptance Criteria:**

**Given** an open survey page
**When** events arrive
**Then** frame thumbnails fill in with a mask-overlay toggle, the trace panel appends tool calls with summaries, and findings appear as they are emitted

**Given** the connection drops
**When** it reconnects
**Then** there are no duplicate items (it resumes from the last seq)

### Story 6.4: Reef map

As a park manager,
I want sites coloured by health trend with evidence layers,
So that I can see where reefs are declining and what is nearby (FR17).

- Owner: C · Priority: P0 · Depends on: 6.1, 4.6
- Files: `web/src/routes/index.tsx`, `web/src/map/{ReefMap,layers}.tsx`
- Done when: web gate passes

**Acceptance Criteria:**

**Given** `/api/sites` and the geo layers
**When** the map loads
**Then** sites render as points coloured by cover trend, and MPA, reef and vessel layers can be toggled

**Given** any page of the app
**When** it renders
**Then** a single footer "Data credits" link opens a credits panel listing every attribution in architecture §9.9, including "Powered by Global Fishing Watch". No per-layer badges are needed.

**Given** a site is clicked
**When** the popover opens
**Then** it shows the latest cover and links to the site and its latest case file

### Story 6.5: Case file with evidence drawer

As a park manager,
I want to click any claim and see its evidence,
So that I can act on the report with confidence (FR18, UX4).

- Owner: C · Priority: P0 · Depends on: 6.3, 5.4
- Files: `web/src/components/{CaseFile,EvidenceDrawer}.tsx`
- Done when: web gate passes, plus one Playwright happy-path test

**Acceptance Criteria:**

**Given** a ready investigation
**When** rendered
**Then** it shows the verdict, findings, hypotheses with confidence bars and the actions

**Given** a frame evidence chip is clicked
**When** the drawer opens
**Then** it shows the frame with its mask overlay and assessment

**Given** a tool-result chip is clicked
**When** the drawer opens
**Then** it shows the tool name, its params, a chart (heat stress) or mini-map (vessels), and the source URL

### Story 6.6: Site timeline

As a park manager,
I want a site's cover trend over time,
So that I can see decline (FR13).

- Owner: C · Priority: P1 · Depends on: 6.4, 8.1
- Files: `web/src/routes/sites.$id.tsx`, `web/src/components/CoverChart.tsx`
- Done when: web gate passes

**Acceptance Criteria:**

**Given** a site with historical and new surveys
**When** opened
**Then** a stacked cover chart over dive dates is shown, with each survey linking to its case file

---

## Epic 7: Distillation

A fast ReefStudent segmenter distilled from SAM 3, with measured accuracy; optionally a Glimmer-Reef assessor distilled from Muse Spark Open.

### Story 7.1: Training corpus and SAM 3 pseudo-labels

As the vision engineer,
I want a licensed corpus of reef frames labelled by SAM 3,
So that the student has training data (FR20).

- Owner: A · Priority: P1 · Depends on: 3.2, 3.3
- Files: `ml/kaggle/pseudo_label.py`, `ml/kaggle/pseudo_label.ipynb`, `data/LICENSES.md`
- Done when: the script runs locally on 10 frames and on Kaggle on the full set; manifest committed (not the images)

**Acceptance Criteria:**

**Given** ≥ 2,000 licensed reef frames: the Coralscapes train + val splits (1,683; never the test split) plus NCRMP images from the non-demo regions (architecture §9.5, §9.8)
**When** `pseudo_label.py --in frames/ --out labels/` runs on Kaggle
**Then** it writes one class-map PNG per frame plus `manifest.jsonl` (frame, source, licence, cover), resuming if interrupted

### Story 7.2: Train ReefStudent

As the vision engineer,
I want a small U-Net trained on the pseudo-labels,
So that segmentation runs in real time on a laptop GPU.

- Owner: A · Priority: P1 · Depends on: 7.1
- Files: `ml/kaggle/train_student.py`, `ml/kaggle/train_student.ipynb`
- Done when: it produces `reefstudent.pt` and a loss curve

**Acceptance Criteria:**

**Given** the manifest
**When** training runs on a Kaggle GPU
**Then** it uses a 90/10 split by source (no leakage between frames from the same video), saves the best checkpoint by val mIoU, and logs per-class IoU

### Story 7.3: Evaluate against human labels

As a judge,
I want honest accuracy numbers,
So that the distillation claim is credible (FR21).

- Owner: A · Priority: P1 · Depends on: 7.2
- Files: `ml/kaggle/eval_student.py`, `ml/results/eval.json`, `ml/results/MODEL_CARD.md`
- Done when: `eval.json` is committed

**Acceptance Criteria:**

**Given** the Coralscapes test split mapped with `ml/coralscapes_map.json` (architecture §9.8)
**When** the evaluation runs
**Then** `eval.json` holds per-class IoU and mIoU for both ReefStudent and SAM 3, ms/frame for both on a Kaggle T4, and ReefStudent ms/frame on the RTX 3050

**Given** the model card
**When** read
**Then** it states the training data, licences, metrics and known failure modes

### Story 7.4: ReefStudent backend in the app

As the pipeline,
I want ReefStudent available as a segmenter,
So that the demo shows the fast model live (FR6).

- Owner: A · Priority: P1 · Depends on: 7.2, 3.1
- Files: `src/reefcase/vision/student.py`, `tests/vision/test_student.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** `REEFCASE_SEGMENTER=student` and the weights path
**When** `segment` runs
**Then** it returns a class map with the same contract, on CUDA when available and on CPU otherwise

### Story 7.5: Teacher assessment dataset

As the agent engineer,
I want Muse Spark Open frame assessments at scale,
So that Glimmer can be fine-tuned on them (FR22).

- Owner: B · Priority: P2 · Depends on: 5.1, 7.1
- Files: `ml/modal/gen_assessments.py`
- Done when: ≥ 3,000 JSONL rows written

**Acceptance Criteria:**

**Given** corpus frames and the teacher model (the Muse Model License permits distillation on outputs — architecture §9.7)
**When** the script runs over corpus frames
**Then** it writes JSONL in chat format (image + cover → `FrameAssessment` JSON), deduplicated and resumable

**Given** the output directory
**When** the dataset is written
**Then** it contains `LICENSE-MUSE.md` and the Usage Policy, because every model trained on it is a Muse Derivative

### Story 7.6: Glimmer-Reef LoRA fine-tune

As the agent engineer,
I want Muse Glimmer fine-tuned into a reef assessor,
So that we compete for the open-weights bonus (FR22).

- Owner: B · Priority: P2 · Depends on: 7.5
- Files: `ml/modal/finetune_glimmer.py`, `ml/results/glimmer_eval.json`
- Done when: the adapter is saved to a Modal volume and the eval JSON is committed

**Acceptance Criteria:**

**Given** the JSONL with a 90/10 split
**When** LoRA fine-tuning runs on a Modal GPU
**Then** the adapter is saved, and the eval reports JSON-validity rate and bleaching-severity agreement with the teacher for base Glimmer vs Glimmer-Reef

**Given** the saved adapter
**When** it is published or served
**Then** it ships with the Muse licence and Usage Policy, and every place it is shown (model card, README, `/api/health`) says "Built with Muse Spark Open"

### Story 7.7: Serve Glimmer-Reef

As the pipeline,
I want Glimmer-Reef behind an OpenAI-compatible endpoint,
So that it can be the student assessor via env config only.

- Owner: B · Priority: P2 · Depends on: 7.6
- Files: `ml/modal/glimmer_endpoint.py`
- Done when: setting `REEFCASE_LLM_STUDENT_*` makes the assess stage use it with no code change

**Acceptance Criteria:**

**Given** the deployed endpoint
**When** the assess stage runs with the student configured
**Then** assessments record `model="glimmer-reef"`, and the agent's output is unchanged in shape

---

## Epic 8: History, bot & ship

Real history for the demo site, a Telegram entry point, a deployed demo and a winning submission.

### Story 8.1: Historical survey import

As a park manager,
I want past public survey imagery loaded as earlier surveys,
So that the agent can describe change over years (FR14).

- Owner: B · Priority: P1 · Depends on: 3.5, 2.5
- Files: `scripts/import_history.py`, `data/demo/history_manifest.csv`, `tests/scripts/test_import_history.py`
- Done when: gate passes; the demo site has ≥ 2 historical surveys

**Acceptance Criteria:**

**Given** a manifest of (image path, lat, lon, date, source, licence) for one Hawaii NCRMP station's 2013, 2016 and 2019 images (architecture §9.5)
**When** the import runs
**Then** it creates `historical` surveys grouped by site and date, segmented by the configured segmenter, with no agent run

### Story 8.2: Telegram bot

As a diver,
I want to send my clip to a bot after the dive,
So that contributing takes no effort (FR19).

- Owner: C · Priority: P2 · Depends on: 5.4
- Files: `src/reefcase/bot/main.py`, `tests/bot/test_bot.py`
- Done when: gate passes; a manual test with a real bot token works

**Acceptance Criteria:**

**Given** a user sends a video and then a location
**When** the bot receives both
**Then** it POSTs to the API, replies "Investigating…", and on `report_ready` sends the verdict, the top 3 findings and the web link

### Story 8.3: Deployment

As a judge,
I want a live URL that works,
So that I can try the product (Demo 25%).

- Owner: B · Priority: P1 · Depends on: 5.4, 6.5
- Files: `Dockerfile`, `ml/modal/api_app.py` or `fly.toml`, `scripts/seed_demo.py`, `web/.env.production`
- Done when: the public URL runs the demo clip end to end

**Acceptance Criteria:**

**Given** the deployed stack
**When** the demo clip is uploaded from a fresh browser
**Then** the case file is ready in ≤ 3 min (NFR1)

**Given** the cloud deployment fails on demo day
**When** the fallback is used
**Then** the laptop and Cloudflare tunnel serve the same build

### Story 8.4: Demo dataset and rehearsal

As the team,
I want a scripted, rehearsed 3-minute demo,
So that the video is tight and the live demo can't surprise us.

- Owner: C · Priority: P1 · Depends on: 8.1, 8.3
- Files: `docs/demo-script.md`, `data/demo/*` (licensed)
- Done when: three uninterrupted rehearsals in under 3:00

**Acceptance Criteria:**

**Given** the script
**When** followed
**Then** it shows: the hook, the upload, live masks, tool calls landing on the map, the verdict with clickable evidence, ReefStudent speed vs SAM 3, and the impact close

**Given** the demo upload clip
**When** it is built
**Then** it is stitched from the same station's 2024 NCRMP images, and both the video and the README say so (architecture §9.5)

### Story 8.5: README and submission

As the team,
I want a README that makes our hackathon work unmistakable,
So that we pass the new-work rule and the judges can run it (NFR8).

- Owner: B · Priority: P0 · Depends on: 8.4
- Files: `README.md`
- Done when: submitted on the CV platform by Nov 4, 21:00 ET, with the X post linked

**Acceptance Criteria:**

**Given** the README
**When** read by a judge
**Then** it has: the problem, a demo GIF, the architecture diagram, the Meta models used and how, the eval numbers, how to run it, the data licences, and a "Built during the hackathon (Oct 26–Nov 4)" section listing every component
