# Story 6.1 — Web scaffold, typed client and event reducer

- Story key: `6-1-web-scaffold-typed-client-and-event-reducer`
- Owner: C (lead-c) · Priority: P0 · Depends on: none
- Dev subagent: `frontend-dev` (build), then `e2e-tester` (Playwright specs + screenshots)
- Gate: `pnpm -C web run gate` (run from the repo root)

## Story

As a frontend developer,
I want a typed client generated from OpenAPI and a reducer for events,
So that the UI can't drift from the API.

## Acceptance Criteria (verbatim)

**Given** `web/openapi.json` (or, until Story 2.1 lands, `web/src/api/openapi.snapshot.json`)
**When** `pnpm gen:api` runs
**Then** `schema.d.ts` is regenerated, and the build fails if the code uses a field that doesn't exist

**Given** `VITE_MOCK_API=1 pnpm dev`
**When** any route is opened
**Then** it renders inside the `AppShell` from MSW mock data with no backend running, using the tokens, fonts and shell described in `docs/agents/ui.md`

**Given** a cover dict with all six `SegClass` values
**When** `CoverStrip` renders
**Then** it draws one segment per class in §4.2 order, with widths equal to the fractions and an accessible label listing each percentage

**Given** the mock event sequence
**When** fed to the reducer
**Then** the state has frames with covers and masks, the tool calls with results, the findings and `reportReady=true`

## Files (verbatim from epics.md)

- Files: `web/**` scaffold, `web/src/api/{openapi.snapshot.json,schema.d.ts,client.ts}`, `web/src/live/reducer.ts`, `web/src/live/reducer.test.ts`, `web/src/mocks/{events.json,handlers.ts,browser.ts}`, `web/public/mockServiceWorker.js`, `web/src/styles/{theme.css,palette.ts}`, `web/src/config.ts`, `web/src/components/{AppShell,CoverStrip}.tsx`, `web/src/components/arc/**` (via `scripts/agents/arc_add.py`)
- Done when: `pnpm -C web run gate` passes. `gate` runs typecheck, lint, vitest, `playwright test` and `python ../scripts/ui_check.py`

`web/**` scaffold therefore also covers the build config, `index.html`, `src/main.tsx`, `src/test/setup.ts`, `src/vite-env.d.ts`, the route files needed for AC2 (`src/routes/{__root,index,upload,surveys.$id,sites.$id}.tsx`, generated `src/routeTree.gen.ts`), `web/e2e/**` and their tests.

**Route files belong to later stories.** `upload.tsx` (6.2), `surveys.$id.tsx` (6.3), `index.tsx` (6.4) and `sites.$id.tsx` (6.6) are created here only as minimal instrument-style placeholders so AC2 ("any route is opened") holds. Keep them to a labelled section plus one line of real copy; later stories replace their bodies and must not need a restructure. Same for the Data credits panel: build it here, and 6.4 may move it into the Arc `drawer`.

## Architecture the story touches

### §3 layout
`web/` is a Vite + React app at the repo root of the worktree: `web/src/…`, `web/public/…`, `web/e2e/…`.

### §7 Web app
- **Stack:** Vite + React + TypeScript (strict), TanStack Router (file routes), TanStack Query, deck.gl over MapLibre via react-map-gl, Tailwind.
- **API client:** `openapi-typescript` generates `src/api/schema.d.ts`; `openapi-fetch` is the client.
- **Events:** SSE via `EventSource`. Events are parsed into the generated `Event` union, and a reducer builds the live view state.
- **Routes:** `/` map of sites · `/upload` · `/surveys/$id` · `/sites/$id`.
- **Look:** dark ocean theme, monospace trace panel, segmentation overlay toggle on frames.

deck.gl, react-map-gl and maplibre are **not** installed in this story (6.4 adds them). Do not add them.

### §4.2 Schemas — the shapes that matter here
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
"§4.2 order" for the cover strip is the **declaration order of `SegClass`**: live_coral, bleached_coral, algae, rubble, sand, other. (That is *not* the mask index order.)

### §4.3 Events — the union the reducer consumes
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

`Event = Annotated[Union[...], Field(discriminator="type")]`.

Note there is **no `t_sec` in `frame_scored`**: the live view orders frames by arrival and numbers them 01…n. Do not invent fields.

### §5.4 Tools — exact tool names and params for the mock events
| Tool | Params | Returns in `data` |
|---|---|---|
| `heat_stress` | `site_id`, `start`, `end` | daily `dhw`, `sst_anomaly`, `alert_level` series; `max_dhw` |
| `vessel_activity` | `site_id`, `radius_km` (≤ 20), `start`, `end` | `sar_detections` (count, unmatched-to-AIS count, points), `fishing_hours` |
| `reef_map` | `site_id` | geomorphic zone, benthic class, reef area within 1 km |
| `mpa_boundary` | `site_id` | `inside_mpa`, `mpa_name`, `no_take`, `designation` |
| `site_history` | `site_id` | past surveys with dates and cover, ordered by date |

### §6.3 HTTP API — exactly the paths the snapshot and the MSW handlers cover
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

The OpenAPI schema is exported by `uv run python -m reefcase.api.export_openapi > web/openapi.json`. Until Story 2.1 lands, `web/src/api/openapi.snapshot.json` is the checked-in stand-in, built from this table plus §4.2/§4.3.

### §9.9 Licence summary (the Data credits content)
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

Plus CARTO and OpenStreetMap for the basemap (ui.md §`/`).

### §10 versions (pinned)
react 19.3.1 · vite 8.3.5 · typescript 7.0.2 · @tanstack/react-router 1.170.46 · @tanstack/react-query 5.105.0 · tailwindcss 4.3.3 · openapi-typescript 7.13.0 · @playwright/test 1.64.1

## UI contract — the parts 6.1 builds

`docs/agents/ui.md` is the design contract. Paste-ready summary of what 6.1 owns; the file itself wins if they ever differ.

### Direction
Near-black tinted-toward-deep-water surfaces, separated by 1px hairlines and dashed dividers — no box-in-box. One lagoon-cyan accent for primary action, focus and live state; all other colour is data colour. Numbers, IDs, coordinates, timestamps, durations and tool names in Geist Mono with `tabular-nums`; prose in Geist. Small muted numbered mono section labels (`01  FRAMES`). Dense instrument layout: big figure, small muted label. No marketing hero, no centred card on an empty page, no welcome banner.

The **cover strip** is a 4px-tall stacked bar of the six `SegClass` fractions in §4.2 order, in the reef colours; it appears everywhere a cover value appears. It is built once, here, as `web/src/components/CoverStrip.tsx`, and reused by every later story.

### Tokens (build exactly these files)
- `web/src/styles/theme.css`: imports, overrides and the Tailwind `@theme`. Starts like this, with these exact values:
```css
@import "tailwindcss";
@import "@fontsource-variable/geist";
@import "@fontsource-variable/geist-mono";
@import "../components/arc/foundation.css";

/* <html data-theme="dark"> is set in index.html; Arc's dark theme, retinted to deep water. */
:root[data-theme="dark"] {
  --background: oklch(15.5% 0.014 235);
  --surface: oklch(18% 0.016 235);
  --surface-raised: oklch(21% 0.018 235);
  --surface-muted: oklch(23.5% 0.018 235);
  --foreground: oklch(95% 0.008 220);
  --text-secondary: oklch(77% 0.015 225);
  --text-muted: oklch(64% 0.016 230);
  --border-subtle: oklch(24% 0.016 235);
  --border: oklch(29% 0.018 235);
  --border-strong: oklch(40% 0.02 235);
  --accent: oklch(80% 0.11 190);
  --accent-strong: oklch(88% 0.09 190);
  --accent-subtle: oklch(80% 0.11 190 / 0.14);
  --accent-foreground: oklch(18% 0.03 220);
  --focus-ring: oklch(80% 0.11 190 / 0.6);
  --font-body: "Geist Variable", sans-serif;

  /* one per SegClass (architecture §4.2) */
  --reef-live: oklch(74% 0.12 170);      /* live_coral */
  --reef-bleached: oklch(93% 0.02 95);   /* bleached_coral, bone white */
  --reef-algae: oklch(60% 0.09 100);     /* algae, olive */
  --reef-rubble: oklch(55% 0.025 60);    /* rubble, warm grey */
  --reef-sand: oklch(74% 0.04 85);       /* sand */
  --reef-other: oklch(42% 0.02 240);     /* other */
  --heat-0: oklch(64% 0.02 230);         /* no stress */
  --heat-1: oklch(86% 0.14 95);          /* watch */
  --heat-2: oklch(79% 0.16 70);          /* warning */
  --heat-3: oklch(70% 0.19 42);          /* alert level 1 */
  --heat-4: oklch(62% 0.21 25);          /* alert level 2 and above */
  --vessel: oklch(88% 0.11 110);
}

@theme inline {
  --color-bg: var(--background);
  --color-surface: var(--surface);
  --color-raised: var(--surface-raised);
  --color-sunken: var(--surface-muted);
  --color-fg: var(--foreground);
  --color-secondary: var(--text-secondary);
  --color-muted: var(--text-muted);
  --color-hairline: var(--border-subtle);
  --color-border: var(--border);
  --color-border-strong: var(--border-strong);
  --color-accent: var(--accent);
  --color-accent-strong: var(--accent-strong);
  --color-accent-subtle: var(--accent-subtle);
  --color-on-accent: var(--accent-foreground);
  --color-danger: var(--danger);
  --color-warning: var(--warning);
  --color-success: var(--success);
  --color-reef-live: var(--reef-live);
  --color-reef-bleached: var(--reef-bleached);
  --color-reef-algae: var(--reef-algae);
  --color-reef-rubble: var(--reef-rubble);
  --color-reef-sand: var(--reef-sand);
  --color-reef-other: var(--reef-other);
  --color-heat-0: var(--heat-0);
  --color-heat-1: var(--heat-1);
  --color-heat-2: var(--heat-2);
  --color-heat-3: var(--heat-3);
  --color-heat-4: var(--heat-4);
  --color-vessel: var(--vessel);

  --font-sans: "Geist Variable", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "Geist Mono Variable", ui-monospace, monospace;

  --text-label: 11px;   --text-label--line-height: 16px;  --text-label--letter-spacing: 0.06em;
  --text-body: 13px;    --text-body--line-height: 20px;
  --text-ui: 14px;      --text-ui--line-height: 20px;
  --text-title: 20px;   --text-title--line-height: 28px;  --text-title--letter-spacing: -0.015em;
  --text-display: 28px; --text-display--line-height: 34px; --text-display--letter-spacing: -0.02em;
  --text-figure: 32px;  --text-figure--line-height: 36px;
}
```
- Using them: colour classes are the token names (`bg-bg`, `bg-surface`, `bg-raised`, `text-fg`, `text-secondary`, `text-muted`, `border-hairline`, `bg-accent text-on-accent`, `bg-reef-live`, `text-heat-3`). Type classes: `text-label`, `text-body`, `text-ui`, `text-title`, `text-display`, `text-figure`. Radius: `rounded-md` controls, `rounded-lg` panels, `rounded-full` dots and pills. Elevation: only `--shadow-floating` on drawers and popovers. 4px spacing grid, panels `p-4`, dense rows `py-2 px-3`. Icons: `lucide-react` at 16px, `strokeWidth={1.5}`. Motion: 120–240ms, opacity/transform only, honour `useReducedMotion`. The only looping animation is the shimmer on something actually running.
- `web/src/styles/palette.ts`: the **same** data colours as RGBA arrays for deck.gl and SVG — one entry per `SegClass` (in §4.2 order), the five heat levels, and the vessel colour. Raw colour values exist only in `theme.css` and `palette.ts` (and vendored Arc code).
- `web/src/config.ts`: env-driven settings, e.g. `BASEMAP_STYLE` = `import.meta.env.VITE_BASEMAP_STYLE` defaulting to `https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json`. Also `API_URL` (`VITE_API_URL`, default `""`) and `MOCK_API` (`VITE_MOCK_API === "1"`). No hard-coded provider, URL or model ID beyond these defaults.

### Shell (this story builds it)
- **Top bar** (48px, `border-b border-hairline`): left, wordmark `ReefCase` in `text-ui font-semibold`, then nav links `Map` (`/`) and `Upload` (`/upload`); the active link is `text-fg` with a 2px accent underline. Right, a health readout from `/api/health`, e.g. a dot plus `models ok` in mono `text-label`; the dot is green, amber or red.
- **Footer** (32px, `text-label text-muted`): the `Data credits` button (one panel listing every attribution above, architecture §9.9, plus CARTO and OpenStreetMap — including "Powered by Global Fishing Watch") and `Open-weight models · SAM 3 · Muse Spark Open`.
- `index.html` sets `<html lang="en" data-theme="dark">` and `<title>ReefCase</title>`.
- **Mock mode.** `VITE_MOCK_API=1 pnpm -C web dev` serves every route from MSW handlers in `web/src/mocks/` (fixtures shaped exactly like architecture §4 and §6.3), so the UI runs with no backend.

### Mock data — real sites, plausible values
Use real reef sites; never write `Site 1`. Site fixture rows (ui.md): Lizard Island −14.668, 145.461 · Heron Island −23.442, 151.914 · Swaraj Dweep, Andaman 11.98, 93.01 · Kavaratti, Lakshadweep 10.563, 72.642 · Krusadai Island, Gulf of Mannar 9.247, 79.212 · Netrani Island 14.016, 74.330 · Cape Kri, Raja Ampat −0.556, 130.690 · Tubbataha 8.950, 119.870. Live cover between 8% and 45%, several sites declining after the 2024 bleaching event. Tool names and params match §5.4 above.

The mock survey is **Lizard Island, dive date 2026-10-21**, matching ui.md's header readout example.

### Slop check
`python ../scripts/ui_check.py` from `web/` must print `clean` (the gate runs it). Each hit prints its own fix; apply it as given and never reword code to dodge the pattern. `src/styles/`, `src/components/arc/`, `*.test.tsx`, `*.d.ts` and `schema.d.ts` are skipped by the checker — everything else is scanned, including `web/index.html` and `web/src/mocks/events.json`.

### Visual evidence (e2e-tester)
Every route the story touches gets a Playwright check at 390×844 asserting `document.documentElement.scrollWidth <= window.innerWidth` and no console errors. Screenshots at 1440×900 and 390×844, taken in mock mode, go to `.scratch/ui/6-1-web-scaffold-typed-client-and-event-reducer/<route>-<width>.png`.

## Decisions fixed by this story file

1. **Lint is `oxlint@1.89.0`, not eslint.** `typescript-eslint@8.72.1` peers `typescript: ">=4.8.4 <6.1.0"`; the pinned `typescript@7.0.2` is the native compiler and exports no JS API (`import ts from "typescript"` gives only `version`), so any typescript-eslint setup is dead on arrival. oxlint parses TS/TSX itself, implements `react/rules-of-hooks` and `react/exhaustive-deps`, and satisfies ui.md's intent ("exclude `src/components/arc/**` from lint, keep it under `tsc`"). Record this in the story report; do **not** add eslint.
2. **`gate`** (in `web/package.json`), exactly:
   `"gate": "pnpm run typecheck && pnpm run lint && pnpm run test && pnpm run e2e && python ../scripts/ui_check.py"` with
   `typecheck` = `tsc --noEmit -p tsconfig.json`, `lint` = `oxlint src e2e --deny-warnings`, `test` = `vitest run`, `e2e` = `playwright test`, `gen:api` = `openapi-typescript src/api/openapi.snapshot.json -o src/api/schema.d.ts`.
3. **Types come only from the generated schema.** `web/src/api/schema.d.ts` is generated; nothing hand-writes an `Event`, `SegClass`, `Cover` or `Survey` type. `reducer.ts`, `client.ts`, `CoverStrip.tsx`, `handlers.ts` and the later routes import from `src/api/schema`. `CoverStrip` takes its cover type as `Cover` from the schema. That is what makes AC1's "build fails if the code uses a field that doesn't exist" true: `tsc` is the build's typecheck.
4. **Snapshot shape.** `openapi.snapshot.json` is OpenAPI 3.1.0: `info` title `ReefCase API`, the eleven §6.3 paths above (POST `/api/surveys` with `multipart/form-data` body and a `422` validation-error response; `/api/surveys/{survey_id}/events` as `text/event-stream`), and `components.schemas` for `GeoSegments`: `SegClass`, `Cover` (exactly six required numeric properties, `additionalProperties: false`), `GeoPoint`, `Site`, `Survey`, `QualityScore`, `Frame`, `Segmentation`, `FrameAssessment`, `EvidenceRef`, `ToolResult`, `Finding`, `Cause`, `Hypothesis`, `Investigation`, one schema per §4.3 event plus `Event` as `oneOf` with `discriminator.propertyName = "type"` (each event's `type` is `"type": "string", "enum": ["<name>"]` so it generates a literal), and `Health`. Path parameter names are `{survey_id}`, `{site_id}`, `{tool_result_id}`, `{layer}`.
5. **Reducer contract** (`web/src/live/reducer.ts`, no React imports):
   ```ts
   export type FrameView = {
     id: string; thumbUrl: string;
     quality?: QualityScore; cover?: Cover; maskUrl?: string; assessment?: FrameAssessment;
   };
   export type ToolCallView = {
     callId: string; tool: string; params: Record<string, unknown>;
     status: "running" | "returned"; toolResultId?: string; summary?: string;
   };
   export type LiveState = {
     surveyId: string | null; lastSeq: number;
     frames: FrameView[]; toolCalls: ToolCallView[]; findings: Finding[];
     investigationId: string | null; reportReady: boolean; failed: string | null;
   };
   export const initialLiveState: LiveState;
   export type LiveAction = { type: "event"; event: Event } | { type: "reset"; surveyId: string };
   export function liveReducer(state: LiveState, action: LiveAction): LiveState;
   ```
   - Drop any `event.seq <= state.lastSeq` (reconnect replay must not duplicate) and any event whose `survey_id` differs from `state.surveyId` once it is set.
   - `frame_scored` upserts a frame keyed by `frame_id`, preserving arrival order; `segmented` sets `cover` + `maskUrl`; `assessed` sets `assessment` on its `frame_id`.
   - `tool_called` appends a running call keyed by `call_id`; `tool_returned` flips that call to `returned` with `toolResultId` + `summary`.
   - `finding` appends; `report_ready` sets `investigationId` and `reportReady = true`; `survey_failed` sets `failed`; `disagreement` and `frames_extracted` change nothing but `lastSeq`.
   - Pure and immutable: return new objects, never mutate `state` or arrays in place. Unknown/dropped events leave the reference unchanged.
6. **`CoverStrip` contract** (`web/src/components/CoverStrip.tsx`):
   `export function CoverStrip({ cover, className }: { cover: Cover; className?: string })`
   − 4px tall (`h-1`), full width, six segments in §4.2 order, each `width: <fraction>%` and `bg-reef-<class>`; `role="img"` with `aria-label` of the form `Live coral 42%, bleached coral 12%, algae 8%, rubble 14%, sand 22%, other 2%` (percentages rounded to at most one decimal, trailing `.0` dropped). Missing values are 0. No raw colours.
7. **`web/src/mocks/events.json`** is a JSON **array** of §4.3 events for survey `srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3`, site `site_lizard_island`, 41 events with `seq` 1…41 and increasing ISO `ts`:
   1 `survey_started` · 2 `frames_extracted` (`count: 8`) · 3–10 `frame_scored` (8 frames, `frm_…` ids, plausible `quality`) · 11–18 `segmented` (6-key `cover` **summing to 1.0**, `mask_url`) · 19–26 `assessed` (one `FrameAssessment` each, `bleaching_severity` 0–4) · 27 `disagreement` (`iou: 0.62`, `chosen: "sam3"`) · 28–37 five `tool_called`/`tool_returned` pairs in §5.4 order (`heat_stress`, `vessel_activity`, `reef_map`, `mpa_boundary`, `site_history`) with params per §5.4 · 38–40 three `finding` events citing frame and tool-result ids that exist in the sequence · 41 `report_ready`.
   Thumbnails/masks point at `/media/<survey_id>/frames/<frame_id>.jpg` and `/media/<survey_id>/masks/<frame_id>.png`.
8. **MSW** handles every §6.3 GET plus the POST, so no route 404s in mock mode. `/api/surveys/{id}/events` responds `text/event-stream` with the whole sequence serialised in SSE frames (`id: <seq>`, `event: <type>`, `data: <json>`, blank line). `msw init public --save` generates `web/public/mockServiceWorker.js`. `main.tsx` starts the worker only when `config.MOCK_API`, and renders after it resolves.
9. **Torch the defaults.** TS 7 rejects `baseUrl`, `esModuleInterop: false`, `module: AMD|UMD|System`, `moduleResolution: classic|node10`, `target: ES3/ES5`. Use `module: "ESNext"`, `moduleResolution: "bundler"`, `target: "ES2023"`, `jsx: "react-jsx"`, `strict: true`, `noUncheckedIndexedAccess: true`, `noEmit: true`, `verbatimModuleSyntax: true`, `types: ["vite/client", "node"]`, and `include: ["src", "e2e", "vite.config.ts", "vitest.config.ts", "playwright.config.ts"]`. No `baseUrl`, no path aliases — relative imports.

## Tasks

Write the tests for each AC first, then the code. Tick each task as it lands.

1. **Scaffold** (`web/`): `package.json` (pinned versions from §10 + the Library check), `tsconfig.json` (decision 9), `vite.config.ts` (plugins in this order: `tanstackRouter({ target: "react", autoCodeSplitting: true })`, `react()`, `tailwindcss()`; `server: { port: 5173, strictPort: true }`, `preview: { port: 4173, strictPort: true }`), `vitest.config.ts` (jsdom, `globals: true`, `setupFiles: ["./src/test/setup.ts"]`), `playwright.config.ts` (decision in Library check §7: `testDir: "./e2e"`, `webServer` = `pnpm dev` on `http://localhost:5173` with `env: { VITE_MOCK_API: "1" }`, `reuseExistingServer: !process.env.CI`, projects `desktop-1440` 1440×900 and `mobile-390` 390×844), `.oxlintrc.json`, `index.html`, `src/vite-env.d.ts`, `src/test/setup.ts`. Packages via `pnpm -C web add` / `pnpm -C web add -D`.
2. **Tokens**: `src/styles/theme.css` and `src/styles/palette.ts` exactly as the UI contract above; wire `theme.css` in `main.tsx`. `src/styles/palette.test.ts`: one entry per reef class in §4.2 order, five heat levels, vessel; every channel an integer 0–255; alpha 0–1.
3. **Types**: write `src/api/openapi.snapshot.json` per decision 4 → `pnpm gen:api` → `src/api/schema.d.ts`. Then `src/api/client.ts` (`createClient<paths>({ baseUrl: config.API_URL })`). Check `pnpm gen:api` is idempotent (run twice, `git status --porcelain src/api/schema.d.ts` empty).
4. **AC4 tests first**: `src/live/reducer.test.ts`. Import the events with `import events from "../mocks/events.json"` (assert it is `Event[]`), fold them through `liveReducer`, then assert: 8 frames, every frame has a 6-key `cover` summing to ≈1.0 and a `maskUrl`, every frame has an `assessment`; 5 tool calls, each `status === "returned"` with `toolResultId` and `summary`; 3 findings with non-empty evidence; `reportReady === true` and `investigationId === "inv_…"`; `lastSeq === 41`. Plus: replaying the whole sequence twice leaves the state deep-equal (idempotent, no duplicates); an event with a lower `seq` is ignored; an event from another survey is ignored after `surveyId` is set; `survey_failed` sets `failed`; `reset` returns a clean state for the given survey; the reducer never mutates its input (freeze the input state).
5. **Implement** `src/live/reducer.ts` per decision 5.
6. **AC3 tests first**: `src/components/CoverStrip.test.tsx`: six segments rendered in §4.2 order, each `width` equal to `fraction × 100%`, `role="img"`, `aria-label` lists every percentage (e.g. `live coral 42%`), zero-value classes still occupy a segment, and a partial dict renders without crashing.
7. **Implement** `src/components/CoverStrip.tsx`; then `src/components/AppShell.tsx` (top bar, health readout via TanStack Query on `/api/health`, footer + Data credits panel per the UI contract) and the stub routes `src/routes/{__root,index,upload,surveys.$id,sites.$id}.tsx`, `src/main.tsx` (QueryClientProvider + RouterProvider), and let the router plugin generate `src/routeTree.gen.ts` (commit it). Every stub route renders inside `AppShell` with a numbered section label and one line of real copy.
8. **Mocks**: `src/mocks/events.json` (decision 7), `src/mocks/handlers.ts` (decision 8, plus real-site fixtures from the UI contract), `src/mocks/browser.ts`; `pnpm -C web exec msw init public --save`. `src/mocks/handlers.test.ts` (vitest, `setupServer` from `msw/node`): GET `/api/health` → 200 with `status`, GET `/api/sites` → 8 sites with the ui.md coordinates, GET `/api/surveys/<id>/events` → `text/event-stream` body containing 41 `id:` lines and `event: report_ready`, GET an unknown `/api/…` path → 404 (so a missing handler is visible).
9. **Packages**: `python scripts/agents/arc_add.py arc-foundation` has already vendor-written `src/components/arc/{foundation.css,motion-tokens.ts,lib/motion-tokens.ts}`; add any npm deps it reported (`pnpm -C web add`). Do not edit files under `src/components/arc/`.
10. **e2e (e2e-tester)**: `web/e2e/*.spec.ts` for the 6.1 flow. Until the tester's specs land, `frontend-dev` leaves **one** smoke spec in `web/e2e/shell.spec.ts` (loads `/` in mock mode, asserts the wordmark, no console errors) so `playwright test` can be green and the gate runnable; the tester then owns and expands `web/e2e/**`. Full expectation for the tester: — open `/`, `/upload`, `/surveys/<mock survey id>` and `/sites/<mock site id>` with `VITE_MOCK_API=1`; assert the wordmark, both nav links, the health readout, the footer `Data credits` button and the "Powered by Global Fishing Watch" line after clicking it; assert no console errors and no horizontal overflow at 390×844 on each route; save the screenshots listed under "Visual evidence". `pnpm -C web exec playwright install chromium` first if the browser is missing.
11. **Green**: `pnpm -C web run gate` passes from the repo root, `pnpm -C web run gen:api` then `git status --porcelain` shows no `schema.d.ts` change, and `ui_check.py` prints `clean`.

## Lessons

Every `ops/*/learnings.md` is empty at the time this story was written — no rules to carry in yet.

## Library check

Confirmed against the registries and official docs for the exact pinned versions (researcher, 2026-10-27). Where a doc snapshot was older than the pin, it is marked.

### Vite 8.3.5 + @vitejs/plugin-react 6.1.2
```ts
// web/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
});
```
- Node floor `^20.19.0 || >=22.12.0`; Node 22.19 is fine. plugin-react 6 peers `vite: ^8.0.0`.
- Vite 8 replaced esbuild+Rollup with **Rolldown + Oxc**: use `build.rolldownOptions` (not `rollupOptions`); `optimizeDeps.esbuildOptions` and `resolve.alias[].customResolver` are deprecated. Do not copy a Vite 7 config.
- Default `build.target` is `baseline-widely-available`.

### Tailwind 4.3.3 (CSS-first)
```ts
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({ plugins: [tailwindcss()] });
```
- `@import "tailwindcss";` + a top-level `@theme inline { … }` still works; `--text-label--line-height` / `--text-label--letter-spacing` still drive the `text-label` utility's line-height and tracking. No `tailwind.config.js`, no PostCSS.
- `@tailwindcss/vite@4.3.3` peers `vite: ^5.2 || ^6 || ^7 || ^8`.
- `@fontsource-variable/*` is unrelated to Tailwind: import the package from JS (`import "@fontsource-variable/geist";`) rather than relying on a CSS `@import` resolution inside Tailwind. *UNVERIFIED* that a CSS `@import "@fontsource-variable/geist";` resolves through the Tailwind plugin — use the JS import in `main.tsx`; keep the two `@import`s in `theme.css` as the contract writes them only if they resolve, otherwise move them to `main.tsx` and note it.

### TanStack Router 1.170.46 (file-based)
```ts
import { tanstackRouter } from "@tanstack/router-plugin/vite";
// plugins: [tanstackRouter({ target: "react", autoCodeSplitting: true }), react()]
```
- Plugin package is `@tanstack/router-plugin` (1.168.48, peers `@tanstack/react-router: ^1.170.46`); the old `@tanstack/router-vite-plugin` is a deprecated shim. The plugin **must come before** `react()`.
- Defaults: `routesDirectory = ./src/routes`, `generatedRouteTree = ./src/routeTree.gen.ts`. Never hand-edit the generated tree.
- Naming: `.` nests, `$` is a param (`src/routes/surveys.$id.tsx` → `/surveys/$id`), `_` is pathless, a leading `-` excludes a file from the tree.
```tsx
// src/routes/__root.tsx
import { createRootRoute, Outlet } from "@tanstack/react-router";
export const Route = createRootRoute({ component: () => <AppShell><Outlet /></AppShell> });

// src/routes/surveys.$id.tsx
import { createFileRoute } from "@tanstack/react-router";
export const Route = createFileRoute("/surveys/$id")({
  component: function SurveyRoute() { const { id } = Route.useParams(); return <p>{id}</p>; },
});

// src/main.tsx
const router = createRouter({ routeTree, defaultPreload: "intent" });
declare module "@tanstack/react-router" { interface Register { router: typeof router } }
createRoot(document.getElementById("root")!).render(<StrictMode><RouterProvider router={router} /></StrictMode>);
```
The `createFileRoute("/surveys/$id")` literal must match what the generator emits.

### openapi-typescript 7.13.0 + openapi-fetch 0.17.0
```bash
pnpm -C web exec openapi-typescript src/api/openapi.snapshot.json -o src/api/schema.d.ts
```
- A local JSON (or YAML) path is still a valid input.
```ts
import createClient from "openapi-fetch";
import type { paths } from "./schema";
export const api = createClient<paths>({ baseUrl: config.API_URL });
```
- `client.GET(path, { params })` returns `{ data } | { data?: never; error; response }`; `error` carries no status discriminant — branch on `response.status` and narrow with the generated response type. Path strings must be literals.

### MSW 3.0.3
```ts
import { http, HttpResponse } from "msw";          // unchanged from v2
import { setupWorker } from "msw/browser";
export const worker = setupWorker(...handlers);
await worker.start();                               // don't pass onUnhandledRequest: v3 renamed the option and it is unconfirmed
import { setupServer } from "msw/node";             // for vitest
```
- `pnpm -C web exec msw init public --save` writes `web/public/mockServiceWorker.js` (version-locked to the installed msw; a mismatch warns at runtime).
- v3 is **ESM-only**, needs Node ≥22.12 and TS ≥5.9, and **`worker.stop()` now returns a Promise**. `graphql` moved to `msw/graphql`. *UNVERIFIED:* the exact `onUnhandledRequest` → `onUnhandledFrame` rename — plain `worker.start()` is safe; for the vitest `setupServer` use `server.listen({ onUnhandledRequest: "error" })` only if it type-checks, otherwise assert the 404 handler instead.
- Alternative in v3: the `msw/vite` plugin + `virtual:msw`; it removes the `public/` worker flow. Do **not** use it — the story's Files list `web/public/mockServiceWorker.js`.

### Vitest 5.0.5
```ts
// web/vitest.config.ts  (must live in web/ — v5 no longer searches parent dirs)
import { defineConfig } from "vitest/config";
export default defineConfig({
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"] },
});
```
- Prereqs: Vite ≥ 6.4, Node ≥ 22.12. `vite` is a peer. `vitest.config.ts` **overrides** `vite.config.ts` `test`; it also needs the React plugin if a test imports JSX directly (it does — `CoverStrip.test.tsx`), so include `react()` in it.
- Breaking from v3: `clearMocks` defaults to **true**; `test.sequential` removed; unawaited assertions **fail**; `vi.mock` must be top-level; config is not found in parent dirs. Jest matcher globals are gone — `import "@testing-library/jest-dom/vitest";` in `setup.ts` is required.
- `@testing-library/react@16.3.3` has a **non-optional** peer `@testing-library/dom@^10`; install it explicitly.

### @playwright/test 1.64.1
```ts
export default defineConfig({
  testDir: "./e2e",
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:5173",
    env: { VITE_MOCK_API: "1" },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  use: { baseURL: "http://localhost:5173" },
  projects: [
    { name: "desktop-1440", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "mobile-390", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } } },
  ],
});
```
- `webServer.port` is deprecated — use `url`. `env` inherits `process.env` plus `PLAYWRIGHT_TEST=1`.
- 1.64 forwards `screen` from `devices[…]`, so `window.screen` sees the emulated size; set `screen: undefined` after spreading a device if that ever matters.
- Browsers: `pnpm -C web exec playwright install chromium` (once).

### Lucide 1.61.0
`peerDependencies.react: ^19.0.0` ✓. The package is now **1.x** (tutorials showing `0.4xx` are stale). `<Waves size={16} strokeWidth={1.5} aria-hidden />`; default `strokeWidth` is 2, so pass 1.5 explicitly.

### TypeScript 7.0.2 (the native compiler)
- `tsc --noEmit -p tsconfig.json` works (`bin/tsc` spawns the native binary and propagates its exit code).
- It ships **no JS API**: `import ts from "typescript"` exposes only `version` / `versionMajorMinor`. This is why typescript-eslint is unusable here (see decision 1).
- Options that are **errors** in TS 7: `baseUrl`, `charset`, `importsNotUsedAsValues`, `preserveValueImports`, `prepend`, `noImplicitUseStrict`, `noStrictGenericChecks`, `keyofStringsOnly`, `suppressExcessPropertyErrors`, `suppressImplicitAnyIndexErrors`, `out`, `outFile`, `downlevelIteration`, `target: ES3|ES5`, `module: AMD|UMD|System`, `moduleResolution: classic|node10`, `esModuleInterop: false`, `allowSyntheticDefaultImports: false`, `alwaysStrict: false`. Decision 9's tsconfig avoids all of them.
- Defaults changed in 6/7: `strict` true, `module` esnext, `target` ≈ es2025, `types` `[]`, `noUncheckedSideEffectImports` true. Set what you rely on explicitly.

### oxlint 1.89.0
```bash
oxlint src e2e --deny-warnings          # exit 1 on lint errors, warnings (with --deny-warnings), no files, or bad config
```
```jsonc
// web/.oxlintrc.json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["eslint", "typescript", "unicorn", "oxc", "react"],
  "categories": { "correctness": "error" },
  "env": { "browser": true },
  "ignorePatterns": ["dist/**", "src/components/arc/**", "src/api/schema.d.ts", "src/routeTree.gen.ts", "public/mockServiceWorker.js"],
  "rules": { "react/rules-of-hooks": "error", "react/exhaustive-deps": "error" }
}
```
- Plugin ids include `eslint, react, unicorn, typescript, oxc, import, jsdoc, jest, vitest, jsx-a11y, nextjs, react-perf, promise, node, vue`. There is **no** `react-hooks` plugin id: `react` provides both `react/rules-of-hooks` (category `pedantic`, so set it explicitly) and `react/exhaustive-deps` (category `correctness`, on via the category too). `plugins` **replaces** the default set (`eslint, typescript, unicorn, oxc`), so list every plugin you want.
- `ignorePatterns` is gitignore-style, rooted at the config dir.
- *UNVERIFIED:* the exact default lintable-extension list; `.tsx` handling is the premise of the react rules, and `oxlint --print-config src` will confirm locally.
