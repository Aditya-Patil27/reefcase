---
status: approved
date: 2026-10-26
inputDocuments: [prd.md]
---

# ReefCase — Architecture

This document is the contract every story is built against. Stories may not change anything in sections 3–6 without a change to this file first.

## 1. Principles

1. **Contracts first.** Schemas, events and interfaces in `reefcase.core` are written and frozen before feature stories start. Feature code depends on them; they depend on nothing.
2. **One seam per external dependency.** Every model, API and storage backend sits behind a small interface with a fake implementation used in tests.
3. **Typed end to end.** Pydantic models → OpenAPI → generated TypeScript types. No hand-written API types in the web app.
4. **Evidence or it didn't happen.** Agent output that is not linked to a frame or tool result is invalid.
5. **Boring infrastructure.** One Python process, one DuckDB file, one folder of blobs. No queues, no Redis, no Kubernetes.

## 2. System overview

```
 diver ──► web (React) ──POST /surveys──► api (FastAPI) ──► JobRunner (asyncio)
   │                    ◄──SSE events──┘                     │
   └──► telegram bot ──► api                                  ▼
                                    ┌──────────── pipeline stages ────────────┐
                                    │ ingest → vision → assess → investigate  │
                                    └─────┬──────────┬────────────┬───────────┘
                                          │          │            │
                                   Segmenter     ChatModels     Tools ──► NOAA CRW / GFW /
                                (SAM 3 | Student) (Baseten/Modal)        Allen Atlas / WDPA
                                          │          │            │
                                          └──────► store (DuckDB + blobs) ◄┘
```

## 3. Repository layout

```
reefcase/
├── pyproject.toml            # uv project, ruff, pyright, pytest, import-linter config
├── uv.lock
├── AGENTS.md                 # rules for coding agents (OpenCode/DeepSeek)
├── .env.example
├── src/reefcase/
│   ├── core/                 # schemas.py, events.py, ids.py, config.py, errors.py
│   ├── store/                # db.py, migrations/*.sql, repos.py, blobs.py
│   ├── ingest/               # frames.py, quality.py
│   ├── vision/               # segmenter.py, sam3.py, student.py, bleaching.py, cover.py, modal_client.py
│   ├── llm/                  # providers.py, assess.py
│   ├── tools/                # http.py, heat_stress.py, vessels.py, reef_map.py, mpa.py, history.py, registry.py
│   ├── agent/                # investigator.py, citations.py, disagreement.py, prompts/
│   ├── pipeline/             # runner.py, bus.py, stages.py
│   ├── api/                  # main.py, routes/{surveys,sites,events,media}.py
│   └── bot/                  # main.py (aiogram)
├── tests/                    # mirrors src/reefcase/; fixtures/ and cassettes/
├── ml/
│   ├── kaggle/               # pseudo_label.py, train_student.py, eval_student.py (+ notebooks)
│   └── modal/                # sam_endpoint.py, gen_assessments.py, finetune_glimmer.py, glimmer_endpoint.py
├── web/                      # Vite + React app (pnpm)
├── data/
│   ├── LICENSES.md           # every dataset, clip and image with its licence and URL
│   ├── geo/                  # reef_map.parquet, mpa.parquet (GeoParquet, demo region only)
│   └── demo/                 # demo clips and historical frames
└── var/                      # runtime: reefcase.duckdb, blobs/ (git-ignored)
```

### Layering (enforced by import-linter)

```
api, bot ──► pipeline ──► agent ──► tools, llm ──► store ──► core
                     └──► vision, ingest ─────────► store ──► core
```

A module may import only from layers to its right. `core` imports only the standard library and pydantic.

## 4. Core contracts (`reefcase.core`)

### 4.1 Identifiers (`ids.py`)
All IDs are prefixed ULID strings: `site_…`, `srv_…` (survey), `frm_…` (frame), `seg_…`, `asm_…` (assessment), `tr_…` (tool result), `inv_…`. Helper: `new_id(prefix: str) -> str`.

### 4.2 Schemas (`schemas.py`)

```python
class SegClass(StrEnum):
    LIVE_CORAL = "live_coral"; BLEACHED_CORAL = "bleached_coral"; ALGAE = "algae"
    RUBBLE = "rubble"; SAND = "sand"; OTHER = "other"
# class index in masks: OTHER=0, LIVE_CORAL=1, BLEACHED_CORAL=2, ALGAE=3, RUBBLE=4, SAND=5

class GeoPoint(BaseModel):   lat: float (−90..90); lon: float (−180..180)

class Site(BaseModel):       id; name; location: GeoPoint; mpa_id: str | None; created_at

class SurveyStatus(StrEnum): QUEUED, RUNNING, DONE, FAILED

class Survey(BaseModel):     id; site_id; dive_date: date; status; source: Literal["upload","bot","historical"]
                             video_path: str | None; cover: dict[SegClass, float] | None
                             failure_reason: str | None; created_at

class QualityScore(BaseModel): blur: float; color_cast: float; turbidity: float; passed: bool; reason: str | None

class Frame(BaseModel):      id; survey_id; t_sec: float; image_path: str; quality: QualityScore

class Segmentation(BaseModel): id; frame_id; backend: Literal["sam3","student","fake"]
                               mask_path: str; cover: dict[SegClass, float]; latency_ms: int

class FrameAssessment(BaseModel): id; frame_id; model: str
                                  bleaching_severity: int (0..4); morphology: list[str]
                                  damage: list[Literal["broken","overturned","anchor_scar","disease","none"]]
                                  notes: str (≤ 400 chars)

class EvidenceRef(BaseModel): kind: Literal["frame","tool_result"]; id: str

class ToolResult(BaseModel): id; tool: str; params: dict; data: dict; source_url: str; retrieved_at

class Finding(BaseModel):    statement: str; evidence: list[EvidenceRef] (min_length=1)

class Cause(StrEnum):        HEAT_STRESS, PHYSICAL_DAMAGE, FISHING_PRESSURE, DISEASE, UNKNOWN

class Hypothesis(BaseModel): cause: Cause; confidence: float (0..1)
                             supporting: list[EvidenceRef] (min 1); contradicting: list[EvidenceRef]
                             rationale: str

class Investigation(BaseModel): id; survey_id; findings: list[Finding] (min 1)
                                hypotheses: list[Hypothesis] (min 1); verdict: str
                                actions: list[str]; uncertain_frames: list[str]; model: str
```

### 4.3 Events (`events.py`)
A discriminated union on `type`. Every event has `survey_id`, `seq: int` (monotonic per survey, from 1) and `ts: datetime`.

| type | payload |
|---|---|
| `survey_started` | `site_id` |
| `frames_extracted` | `count` |
| `frame_scored` | `frame_id`, `quality`, `thumb_url` |
| `segmented` | `frame_id`, `backend`, `cover`, `mask_url` |
| `assessed` | `assessment: FrameAssessment` |
| `disagreement` | `frame_id`, `iou`, `chosen: "sam3"` |
| `tool_called` | `call_id`, `tool`, `params` |
| `tool_returned` | `call_id`, `tool_result_id`, `summary` |
| `finding` | `finding: Finding` |
| `report_ready` | `investigation_id` |
| `survey_failed` | `reason` |

`Event = Annotated[Union[...], Field(discriminator="type")]`, plus `EventAdapter = TypeAdapter(Event)`.

### 4.4 Configuration (`config.py`)
`Settings(BaseSettings)` loaded from env / `.env`, prefix `REEFCASE_`:

| Variable | Meaning |
|---|---|
| `REEFCASE_DATA_DIR` | default `var/` |
| `REEFCASE_SEGMENTER` | `fake` \| `sam3_local` \| `sam3_modal` \| `student` |
| `REEFCASE_SAM_MODEL_ID` | HF model id (default `facebook/sam3`, loaded through Transformers; see §9.6) |
| `REEFCASE_SAM_MODAL_URL` | URL of the Modal SAM endpoint |
| `REEFCASE_SAM_MODAL_TOKEN` | Modal proxy-auth token for that endpoint, `<id>.<secret>` |
| `REEFCASE_STUDENT_WEIGHTS` | path to ReefStudent weights |
| `REEFCASE_LLM_AGENT_{BASE_URL,API_KEY,MODEL}` | agent model (OpenAI-compatible) |
| `REEFCASE_LLM_TEACHER_{BASE_URL,API_KEY,MODEL}` | frame assessor teacher |
| `REEFCASE_LLM_STUDENT_{BASE_URL,API_KEY,MODEL}` | frame assessor student (Glimmer-Reef), optional |
| `REEFCASE_LLM_{AGENT,TEACHER}_REASONING_EFFORT` | `low` \| `medium` \| `high` \| `xhigh`; defaults `medium` (agent) and `low` (teacher), because Muse Spark Open defaults to `xhigh`, which would break NFR1 |
| `REEFCASE_GFW_TOKEN` | Global Fishing Watch API token |
| `REEFCASE_TELEGRAM_TOKEN` | bot token, optional |
| `REEFCASE_KEEP_FRAMES` | default 24 |
| `REEFCASE_MIN_FRAMES` | default 6 |

## 5. Interfaces

### 5.1 Segmenter (`vision/segmenter.py`)
```python
class Segmenter(Protocol):
    name: Literal["sam3", "student", "fake"]
    def segment(self, image: np.ndarray) -> np.ndarray: ...   # HxWx3 uint8 RGB → HxW uint8 class ids (§4.2)

def build_segmenter(settings: Settings) -> Segmenter
def cover_from_mask(mask: np.ndarray) -> dict[SegClass, float]   # fractions summing to 1.0
```
**SAM 3 strategy:** load `Sam3Model` + `Sam3Processor` from Transformers (fp16 on CUDA). For each image, compute `model.get_vision_features(...)` once, then run text-prompted concept segmentation with prompts `coral`, `algae`, `sand`, `rubble` against those features, and merge each prompt's instance masks with `post_process_instance_segmentation(threshold=0.5, mask_threshold=0.5)`. Paint masks into a class map in the priority order sand < rubble < algae < coral (later wins). Split coral pixels into `live_coral` / `bleached_coral` with `bleaching.classify_coral_pixels(image, coral_mask)`: a pixel is bleached when CIELAB L* ≥ 80 and chroma ≤ 12 (tunable constants, unit-tested on fixtures).

**ReefStudent:** `segmentation_models_pytorch.Unet` with an `efficientnet-b0` encoder, 6 output classes, trained on SAM 3 pseudo-labels (§8).

### 5.2 Chat models (`llm/providers.py`)
```python
def build_model(role: Literal["agent", "teacher", "student"], settings: Settings) -> pydantic_ai.models.Model
```
Uses `OpenAIChatModel(model, provider=OpenAIProvider(base_url=..., api_key=...))` with the role's settings, and passes `reasoning_effort` through the model settings. Returns `None` for `student` when unconfigured.

**Structured output rule:** Muse Spark Open on Baseten does not support JSON mode or structured outputs (§9.7). Every `Agent` therefore uses pydantic-ai's default tool-call output (`output_type=SomeModel`). `NativeOutput` is forbidden. `PromptedOutput` is the fallback if a provider can't do tool calls. Tests use `pydantic_ai.models.test.TestModel` / `FunctionModel`.

### 5.3 Frame assessor (`llm/assess.py`)
```python
async def assess_frame(model, frame: Frame, image_bytes: bytes, seg: Segmentation) -> FrameAssessment
```
A pydantic-ai `Agent` with `output_type=FrameAssessment` (minus id/frame_id, which the caller fills in). The prompt includes the image and the cover fractions.

### 5.4 Tools (`tools/`)
Each tool is an async function `(params: XParams, ctx: ToolContext) -> ToolResult`, where `ToolContext` holds the `httpx.AsyncClient`, the store and the settings. `registry.py` exposes them to the agent. Every result is persisted and cached: the key is `(tool, canonical JSON params)` and cache hits return the stored `ToolResult`.

| Tool | Params | Returns in `data` |
|---|---|---|
| `heat_stress` | `site_id`, `start`, `end` | daily `dhw`, `sst_anomaly`, `alert_level` series; `max_dhw` |
| `vessel_activity` | `site_id`, `radius_km` (≤ 20), `start`, `end` | `sar_detections` (count, unmatched-to-AIS count, points), `fishing_hours` |
| `reef_map` | `site_id` | geomorphic zone, benthic class, reef area within 1 km |
| `mpa_boundary` | `site_id` | `inside_mpa`, `mpa_name`, `no_take`, `designation` |
| `site_history` | `site_id` | past surveys with dates and cover, ordered by date |

`reef_map` and `mpa_boundary` read pre-downloaded GeoParquet in `data/geo/` through DuckDB spatial. They make no network calls at runtime.

`vessel_activity` holds a process-wide `asyncio.Semaphore(1)` around GFW report calls, because GFW allows one report at a time per user (§9.1).

### 5.5 Investigator (`agent/investigator.py`)
```python
async def investigate(survey: Survey, frames: list[Frame], segs: list[Segmentation],
                      assessments: list[FrameAssessment], ctx: ToolContext,
                      emit: Callable[[Event], Awaitable[None]]) -> Investigation
```
- A pydantic-ai `Agent(output_type=InvestigationDraft, tools=[...])`. Every tool call emits `tool_called` / `tool_returned`.
- An output validator runs `citations.validate(draft, known_ids)`. Unknown or missing evidence IDs raise `ModelRetry` with the list of offending claims. The maximum is 2 retries; after that, uncited claims are dropped and the verdict is prefixed with "Partial:".
- The system prompt lives in `agent/prompts/investigator.md`.

### 5.6 Disagreement (`agent/disagreement.py`) — P1
`iou_per_class(mask_a, mask_b) -> dict[SegClass, float]`. When mean IoU on {live, bleached} is < 0.5, the frame is marked uncertain and the SAM 3 result wins.

## 6. Pipeline and API

### 6.1 JobRunner (`pipeline/runner.py`)
- An in-process `asyncio` runner with a concurrency limit of 2 surveys.
- `submit(survey_id)`, then the stages run in order: `ingest → segment → assess → investigate`.
- Any exception moves the survey to FAILED and emits `survey_failed`.
- CPU/GPU-heavy work (frame decode, segmentation) runs in `asyncio.to_thread`.

### 6.2 Event bus (`pipeline/bus.py`)
`publish(event)` persists the event to the `events` table first, then fans it out to live subscribers. `subscribe(survey_id, after_seq)` yields stored events after `after_seq`, then live ones. So SSE reconnects (the `Last-Event-ID` header) replay without gaps.

### 6.3 HTTP API (`api/`)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/surveys` | multipart: `video`, `lat`, `lon`, `dive_date`, optional `site_name` → `201 Survey` |
| GET | `/api/surveys/{id}` | `Survey` |
| GET | `/api/surveys/{id}/events` | `text/event-stream`, `id:` = seq, `event:` = type, `data:` = JSON |
| GET | `/api/surveys/{id}/investigation` | `Investigation`, or 404 until ready |
| GET | `/api/surveys/{id}/frames` | frames with quality, segmentation and assessment |
| GET | `/api/sites` | sites with latest cover and trend |
| GET | `/api/sites/{id}` | site and survey timeline |
| GET | `/api/tool-results/{id}` | `ToolResult` |
| GET | `/api/geo/{layer}` | GeoJSON for map layers: `mpa`, `reef`, `vessels?survey_id=` |
| GET | `/media/{path}` | static frames and masks from the blob dir |
| GET | `/api/health` | provider configuration status |

The OpenAPI schema is exported by `uv run python -m reefcase.api.export_openapi > web/openapi.json`.

### 6.4 Storage (`store/`)
- One DuckDB file, with the `spatial` extension loaded on connect.
- Migrations are numbered SQL files in `store/migrations/`, applied in order at startup and tracked in `schema_migrations`.
- Each story adds only the tables it needs.
- Blobs go to `var/blobs/{survey_id}/frames/{frame_id}.jpg`, `…/masks/{frame_id}.png` and `…/video.<ext>`.
- DuckDB has a single writer. All writes go through one `Store` object holding one connection guarded by an `asyncio.Lock`.

## 7. Web app (`web/`)
- **Stack:** Vite + React + TypeScript (strict), TanStack Router (file routes), TanStack Query, deck.gl over MapLibre via react-map-gl, Tailwind.
- **API client:** `openapi-typescript` generates `src/api/schema.d.ts`; `openapi-fetch` is the client.
- **Events:** SSE via `EventSource`. Events are parsed into the generated `Event` union, and a reducer builds the live view state.
- **Routes:**
  - `/` — map of sites
  - `/upload`
  - `/surveys/$id` — live view, then case file
  - `/sites/$id` — timeline
- **Look:** dark ocean theme, monospace trace panel, segmentation overlay toggle on frames.

## 8. ML pipelines (`ml/`)

| Job | Where | Input → Output |
|---|---|---|
| `pseudo_label.py` | Kaggle GPU | licensed reef frames → SAM 3 class masks (`.png`) + manifest |
| `train_student.py` | Kaggle GPU | masks → `reefstudent.pt` + training curve |
| `eval_student.py` | Kaggle / local | Coralscapes test split → mIoU per class for student and SAM 3, latency for both on a Kaggle T4, and student latency on the RTX 3050 → `ml/results/eval.json` |
| `sam_endpoint.py` | Modal | HTTP endpoint wrapping the SAM 3 segmenter (same class-map contract) |
| `gen_assessments.py` | Baseten | frames → teacher `FrameAssessment` JSONL (P2) |
| `finetune_glimmer.py` | Modal GPU | JSONL → Glimmer-Reef LoRA adapter (P2) |
| `glimmer_endpoint.py` | Modal | OpenAI-compatible endpoint serving Glimmer + adapter (P2) |

Kaggle jobs are plain Python scripts. The notebook is a thin wrapper that pip-installs the repo and calls the script, so the same code runs locally.

## 9. External sources (verified 2026-10-26)

Items marked **UNVERIFIED** must be checked by the story that first uses them. Each such check is listed in that story's acceptance criteria.

### 9.1 Global Fishing Watch API v3 — `vessel_activity`
- **Endpoint:** `POST https://gateway.api.globalfishingwatch.org/v3/4wings/report`. Header: `Authorization: Bearer $REEFCASE_GFW_TOKEN`. The body is `{"geojson": <FeatureCollection>}`: a polygon approximating the circle `radius_km` around the site.
- **Query params:**
  - `format=JSON` (the response is a zip, so unzip it in memory)
  - `group-by=FLAG`
  - `temporal-resolution=ENTIRE`
  - `spatial-resolution=HIGH` (0.01°). The docs spell it inconsistently, so test both `HIGH` and `HIGHT` in the cassette recording.
  - `date-range=YYYY-MM-DD,YYYY-MM-DD`
  - `datasets[0]=...`
- **SAR detections:** `datasets[0]=public-global-sar-presence:latest`. Make two calls: no filter (total), and `filters[0]=matched='false'` (unmatched to AIS).
- **Fishing effort:** `datasets[0]=public-global-fishing-effort:latest`.
- **Limits:**
  - One report at a time per user, otherwise HTTP 429.
  - Reports slower than 100 s return 524; retrieve them via the "last report" endpoint.
  - 50k requests/day per user.
- We use plain `httpx` rather than `gfw-api-python-client` 1.4.0, because the client only documents `region={dataset,id}`, not custom GeoJSON (**UNVERIFIED**), and plain HTTP records cleanly into cassettes.
- **Licence:** CC BY-NC 4.0, non-commercial. "Powered by Global Fishing Watch" with a link appears in the app's single data-credits panel (footer link) and in the README. The token stays server-side and is never sent to the web app.
- Docs: https://globalfishingwatch.org/our-apis/documentation/docs/v3/4wings/report

### 9.2 NOAA Coral Reef Watch daily 5 km (v3.1) — `heat_stress`
- **Primary server (tested live):** PacIOOS ERDDAP, dataset `dhw_5km`. Coverage runs 1985-04-01 to the present, with no auth.
  `https://pae-paha.pacioos.hawaii.edu/erddap/griddap/dhw_5km.json?CRW_DHW[(START):1:(END)][(LAT)][(LON)],CRW_SSTANOMALY[...],CRW_BAA[...]`
- **Variables used:**
  - `CRW_DHW` (°C-weeks)
  - `CRW_SSTANOMALY` (°C)
  - `CRW_BAA` (bleaching alert area). Store the raw value as `alert_level`.
- **Grid:** dims are `[time][latitude][longitude]`, latitude descending. The server snaps to the nearest 5 km cell; record the snapped lat/lon in `data`. Land cells return NaN. If every value is NaN, return `available=false`.
- **Interpretation thresholds for the prompt:** DHW ≥ 4 means significant bleaching is likely; DHW ≥ 8 means widespread bleaching and mortality.
- **Fallback server:** `https://coastwatch.noaa.gov/erddap/griddap/noaacrwdhwDaily` (responds, but its data may end around April 2025 — **UNVERIFIED**).
- **Licence:** NOAA data, public domain. Cite NOAA Coral Reef Watch.

### 9.3 Allen Coral Atlas — `reef_map`
- **Source:** download the demo region from the ACA website (free account), benthic and geomorphic layers. The exact export format (GeoJSON or GeoPackage) is **UNVERIFIED**. The alternative is the Earth Engine asset `ACA/reef_habitat/v2_0` (5 m), which needs a GEE account.
- **Classes:**
  - Geomorphic: 11 Shallow Lagoon, 12 Deep Lagoon, 13 Inner Reef Flat, 14 Outer Reef Flat, 15 Reef Crest, 16 Terrestrial Reef Flat, 21 Sheltered Reef Slope, 22 Reef Slope, 23 Plateau, 24 Back Reef Slope, 25 Patch Reef.
  - Benthic: 11 Sand, 12 Rubble, 13 Rock, 14 Seagrass, 15 Coral/Algae, 18 Microalgal Mats.
- **Licence:** CC BY 4.0. Cite doi:10.5281/zenodo.3833242.

### 9.4 Protected Planet (WDPA) — `mpa_boundary`
- **Preferred source:** the bulk download (shapefile or GDB) for the demo country from protectedplanet.net, filtered to marine areas and clipped in `scripts/build_geo.py`.
- **API alternative:** v4 at `https://api.protectedplanet.net/v4/protected_areas/search?country=XXX&marine=true&with_geometry=true&per_page=50&token=...`. v3 is retired. The API has **no bbox or point search**, so you fetch by country and intersect locally.
- **Fields:** take `no_take` from the WDPA `NO_TAKE` attribute.
- **Licence:** no commercial use without UNEP-WCMC permission. Cite UNEP-WCMC & IUCN, Protected Planet.

### 9.5 Imagery and video
- **History:** NOAA PIFSC ESD NCRMP "Benthic Images at Permanent Sites across the US Pacific since 2010" (InPort 71813).
  - JPEG + CSV, 30 photos per station.
  - Download from `https://www.ncei.noaa.gov/archive/accession/download/<acc>`.
  - Hawaii accessions: 0159172 (2013), 0164296 (2016), 0240600 (2019), 0317534 (2024).
  - The use constraint is "cite PIFSC ESD"; public-domain status is **UNVERIFIED**.
  - Same-quadrat revisits are **UNVERIFIED**: stations are "permanent sites", so treat them as site-level comparisons, not pixel-level.
- **Demo site:** one Hawaii NCRMP station surveyed in 2013, 2016 and 2019 is imported as history (Story 8.1). The 2024 images of the same station become the "new dive" upload, stitched into a clip. The README states this openly. The Hawaii surveys span the 2014–2015 and 2019 marine heatwaves; the actual DHW at the chosen station must come from `heat_stress`, not from this document.
- **Extra CC clips:** Ifremer Coral Sea Marine Park clips on Wikimedia Commons, CC BY 4.0. Search the Commons API with `srsearch=coral reef filetype:video`. Avoid cold-water reef clips.

### 9.6 SAM 3
- **Model:** `facebook/sam3` through Transformers (`Sam3Model`, `Sam3Processor`). It is gated and has 0.9B params.
  - **Licence:** SAM License — royalty-free, no field-of-use limit, bans military/ITAR uses, requires acknowledgement.
  - **Access:** each teammate must request it on HF.
- **Why not SAM 3.1:** `facebook/sam3.1` has original checkpoints only, with no Transformers integration. Its changes (Object Multiplex) are for video multi-object tracking, which we don't use.
- **Memory:** the official guide recommends ≥ 16 GB; a community report says ~12 GB for one image. A Kaggle T4 (16 GB) works. **The RTX 3050 6 GB is UNVERIFIED** — Story 3.2 measures fp16 on it once.

### 9.7 Muse Spark Open and Muse Glimmer
- **Muse Spark Open** (`meta-models/Muse-Spark-Open-816B-A42B`, Muse Model License):
  - Fine-tuning and distillation are permitted.
  - Any model trained on its outputs is a Derivative. It must ship the licence, the copyright notice and the Usage Policy, and display **"Built with Muse Spark Open"**.
- **Muse Glimmer** (`meta-models/Muse-Glimmer-30B`, Apache-2.0): text + image input, function calling. Once fine-tuned on Spark Open outputs, Glimmer-Reef carries the Muse licence terms on top of Apache-2.0.
- **Baseten:**
  - Base URL: `https://inference.baseten.co/v1`.
  - Model slug: `meta-models/muse-spark-open` per the changelog. The `-1026` suffix is **UNVERIFIED**; check with `GET /v1/models`.
  - Supports tool calling, but **not JSON mode or structured outputs** (see the §5.2 rule).
  - The image-input payload format is **UNVERIFIED**; Story 5.1 checks it.
- **Spark Open capabilities:** text, image, video and audio input; 1M context; `reasoning_effort` defaults to `xhigh`. Recommended sampling: temperature 1.0, top_p 1.0.

### 9.8 Labelled segmentation data
- **Coralscapes:** `EPFL-ECEO/coralscapes` on HF, Apache-2.0. Dense masks; 2,075 Red Sea images, split 1517/166/392; 39 classes.
  - Used as the ReefStudent training corpus (train split, re-labelled by SAM 3) and as the human-labelled eval set (test split).
  - The class mapping is generated from the dataset's `id2label` by name and committed as `ml/coralscapes_map.json`:
    - names containing "bleached" → `bleached_coral`
    - "alive" → `live_coral`
    - "rubble" → `rubble`
    - "sand" → `sand`
    - "algae" → `algae`
    - everything else, including dead coral → `other`
- **Seaview** (CC BY 3.0, **UNVERIFIED**) and CoralNet/ReefNet (mixed or non-commercial licences) give point labels only. They are not used.

### 9.9 Licence summary (goes into `data/LICENSES.md` and the README)
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

## 10. Toolchain and versions (live registries, 2026-10-26)

Pin these minimums in `pyproject.toml` and `web/package.json`. `uv.lock` and `pnpm-lock.yaml` are committed.

**Python 3.14** (`.python-version`). Python 3.15 is out, but torch 2.14.1 has wheels only up to cp314 and aiogram 3.31 requires < 3.15.

| Python package | Version | Note |
|---|---|---|
| uv | 0.13.5 | |
| ruff | 0.17.2 | |
| pyright | 1.1.414 | strict on `src/reefcase/` |
| import-linter | latest | |
| fastapi | 0.162.0 | |
| pydantic | 2.14.1 | |
| pydantic-ai | 2.61.0 | `OpenAIChatModel` + `OpenAIProvider` |
| duckdb | 2.0.0 | spatial does not autoload: `INSTALL spatial; LOAD spatial;` |
| av (PyAV) | 19.0.2 | |
| aiogram | 3.31.0 | |
| pytest | 9.1.1 | |
| pytest-recording / vcrpy | 0.14.0 / 9.2.0 | |
| transformers | 5.20.2 | `Sam3Model` |
| torch | 2.14.1 | CUDA build on Kaggle/Modal; CPU in the API image |
| segmentation-models-pytorch | latest | ReefStudent |
| playwright | 1.64.1 | |

| npm package | Version |
|---|---|
| react | 19.3.1 |
| vite | 8.3.5 |
| typescript | 7.0.2 |
| @tanstack/react-router | 1.170.46 |
| @tanstack/react-query | 5.105.0 |
| deck.gl | 9.4.0 |
| maplibre-gl | 6.16.0 |
| react-map-gl | 8.1.3 |
| tailwindcss | 4.3.3 |
| openapi-typescript | 7.13.0 |
| @playwright/test | 1.64.1 |

## 11. Testing strategy

| Layer | How |
|---|---|
| core | Schema round-trip and validation tests |
| store | Temp-dir DuckDB per test |
| ingest/vision | Fixture images in `tests/fixtures/frames/` (6 frames with hand masks); `FakeSegmenter` for pipeline tests; SAM 3 tests marked `@pytest.mark.gpu` and skipped in CI |
| tools | `pytest-recording` cassettes in `tests/cassettes/`; CI runs with `--record-mode=none` |
| agent | `FunctionModel` scripts the model's tool calls and outputs; tests cover citation repair and the partial-verdict fallback |
| api | `httpx.AsyncClient` with an ASGI transport; SSE tested by reading the stream |
| web | `tsc --noEmit`, eslint, vitest for the event reducer, one Playwright run of the happy path against a fake-backed API |

Definition of done for every story: `uv run ruff check && uv run ruff format --check && uv run pyright && uv run lint-imports && uv run pytest` all pass (web: `pnpm typecheck && pnpm lint && pnpm test && pnpm build`).

## 12. Deployment (demo)
- **API:** a Docker image (python slim + ffmpeg libs) deployed as a Modal ASGI app if Modal credits land, otherwise Fly.io. Segmentation runs on the Modal SAM endpoint; ReefStudent runs on CPU in the API container.
- **Web:** a static build on Cloudflare Pages, with `VITE_API_URL` pointing at the API.
- **Data:** demo DuckDB and blobs are seeded at deploy time from `data/demo/`.
- **Fallback for the live demo:** run everything on the team laptop (RTX 3050) behind a Cloudflare tunnel, with `REEFCASE_SEGMENTER=student`. SAM 3 may not fit in 6 GB (§9.6), so demo-site SAM 3 masks are precomputed on Kaggle and seeded. This fallback is also the distillation story: the student runs where the teacher cannot.
