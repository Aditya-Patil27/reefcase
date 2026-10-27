# Story 6.2 — Upload page

- Story key: `6-2-upload-page`
- Owner: C (lead-c) · Priority: P0 · Depends on: 6.1 (done)
- Dev subagent: `frontend-dev` (build), then `e2e-tester` (Playwright specs + screenshots)
- Gate: `pnpm -C web run gate` (run from the repo root)

## Story

As a diver,
I want to drop a clip and pin my dive site,
So that I can start an investigation in seconds (FR15).

## Acceptance Criteria (verbatim)

**Given** a video file, a map pin and a date
**When** submitted
**Then** a progress bar shows the upload, and the page navigates to `/surveys/$id` when it completes

**Given** a 422 response
**When** shown
**Then** the field errors appear next to their inputs

## Files (verbatim from epics.md)

- Files: `web/src/routes/upload.tsx`, `web/src/components/SitePicker.tsx`
- Done when: web gate passes

**Scope note (this story file).** Story 6.2 also touches, and is allowed to change:
`web/src/routes/upload.test.tsx`, `web/src/components/SitePicker.test.tsx`, a new
`web/src/api/upload.ts` + `web/src/api/upload.test.ts` (the XHR upload transport; the
route must not carry network code), `web/src/mocks/handlers.ts` +
`web/src/mocks/handlers.test.ts` (the POST `/api/surveys` mock, including its 422 shape),
`web/e2e/upload.spec.ts`, `web/playwright.config.ts` (only if WebGL needs browser flags),
vendored `web/src/components/arc/**` written by `scripts/agents/arc_add.py`, and
`web/package.json` / `pnpm-lock.yaml` via `pnpm add`. Do not restructure files that 6.1
owns; only add to them (`handlers.ts`, `handlers.test.ts`, `playwright.config.ts`).

## Architecture the story touches

### §7 Web app
- Stack: Vite + React + TypeScript (strict), TanStack Router (file routes), TanStack Query, deck.gl over MapLibre via react-map-gl, Tailwind.
- API client: `openapi-typescript` generates `src/api/schema.d.ts`; `openapi-fetch` is the client. The upload POST is the one call that uses `XMLHttpRequest` instead, because `fetch` reports no upload progress (decision 3).
- Routes: `/` map of sites · `/upload` · `/surveys/$id` · `/sites/$id`.
- Look: dark ocean theme, monospace trace panel, segmentation overlay toggle on frames.

### §4.2 schemas — the shapes this page produces and reads
```python
class GeoPoint(BaseModel):   lat: float (−90..90); lon: float (−180..180)
class SurveyStatus(StrEnum): QUEUED, RUNNING, DONE, FAILED
class Survey(BaseModel):     id; site_id; dive_date: date; status; source: Literal["upload","bot","historical"]
                             video_path: str | None; cover: dict[SegClass, float] | None
                             failure_reason: str | None; created_at
```
The POST returns a `Survey`; the page needs only `id` (to navigate) and may show `site_id`,
`dive_date`, `status` in the confirmation readout.

### §6.3 HTTP API — the one endpoint this story calls
| Method | Path | Notes |
|---|---|---|
| POST | `/api/surveys` | multipart: `video`, `lat`, `lon`, `dive_date`, optional `site_name` → `201 Survey` |

`web/src/api/openapi.snapshot.json` (checked in by 6.1, still the source of truth until
Story 2.1 lands) declares this operation as:

- request body `multipart/form-data`, required `video` (binary string), `lat` (number,
  −90..90), `lon` (number, −180..180), `dive_date` (string, `format: date`), optional
  `site_name` (string);
- `201` → `Survey`;
- `422` → FastAPI's validation shape, inline and **not** a named schema:
  `{ "detail": [ { "loc": string[], "msg": string, "type": string } ] }` where `loc` is
  e.g. `["body", "lat"]` and the last element is the field name.

Do not invent a new schema for the 422 body, and do not hand-write TypeScript: derive both
types from `paths["/api/surveys"]["post"]` in `src/api/schema.d.ts` (decision 3).

`web/src/mocks/handlers.ts` already answers `POST /api/surveys` with a fixed `201`. This
story makes it read the multipart body and validate it (decision 6).

## UI contract — `/upload` (paste from `docs/agents/ui.md`)

### `/upload` (6.2)

- **Wide screens (≥1024):** two columns.
  - Left: `01  CLIP`, a `file-dropzone`. Once a file is chosen, show its name, then size and duration in mono.
  - Right: `02  SITE`, the `SitePicker`, a 360px map with a draggable pin. Below it, lat/lon as `number-field`s in mono (`14.6680° S  145.4610° E`), then an optional site name and the dive date (`date-picker`).
- **Submit:** a full-width accent `button` labelled `Start investigation`.
- **Uploading:** a 2px accent `progress` bar with the readout `42% · 18.3 / 43.6 MB`.
- **422 errors:** the message sits under its own field in `text-danger text-body`, and focus moves to the first invalid field.
- **Narrow screens:** one column, clip first.

### Rules from the same file that apply here
- Tokens only (6.1 built them): colour classes `bg-bg`, `bg-surface`, `text-fg`, `text-secondary`, `text-muted`, `border-hairline`, `bg-accent text-on-accent`, `text-danger`; type classes `text-label`, `text-body`, `text-ui`, `text-title`, `text-figure`; radius `rounded-md` controls / `rounded-lg` panels; flat surfaces, hairlines, no box-in-box, no gradients, no blur/glass, no shadows except `--shadow-floating` on drawers and popovers.
- Numbers, coordinates, sizes, durations and timestamps use Geist Mono with `tabular-nums`; prose and labels use Geist.
- Section labels are small, muted, numbered mono labels (`01  CLIP`, `02  SITE`).
- Icons: `lucide-react` at 16px with `strokeWidth={1.5}`.
- Motion: 120–240ms, opacity/transform only, honour `useReducedMotion`; the only looping animation is the shimmer on something actually running.
- Copy: a field scientist's voice, sentence case, no exclamation marks; buttons say what happens; every error names the real thing.
- Slop check: `python ../scripts/agents/ui_check.py` from `web/` must print `clean`. No raw colours outside `src/styles/` and `src/components/arc/`, no Tailwind palette colours, no arbitrary text sizes, no emoji, no filler copy.

## Decisions fixed by this story

1. **Packages.** `pnpm -C web add maplibre-gl@6.16.0 react-map-gl@8.1.3` (architecture §10 pins). These are the map stack 6.4 also builds on; deck.gl is still **not** installed. Arc components are vendored, never installed:
   `python scripts/agents/arc_add.py file-dropzone date-picker input number-field button progress`
   then `pnpm -C web add` the dependency line it prints. Read the generated files under
   `web/src/components/arc/**` for their props — they are the API reference. Never edit them;
   they stay out of `oxlint` and inside `tsc`.
2. **`SitePicker` contract** (`web/src/components/SitePicker.tsx`, no other file owns it):
   ```ts
   export type DiveSite = { lat: number; lon: number };

   export function SitePicker(props: { value: DiveSite; onChange: (next: DiveSite) => void }): ReactElement;

   export function clampDiveSite(value: DiveSite): DiveSite;          // lat to −90..90, lon to −180..180
   export function formatLatitude(lat: number): string;               // −14.668 → "14.6680° S"; 14.668 → "14.6680° N"
   export function formatLongitude(lon: number): string;              // 145.461 → "145.4610° E"; −72.642 → "72.6420° W"
   export function formatCoordinates(value: DiveSite): string;        // "14.6680° S  145.4610° E" (two spaces between)
   ```
   - The map is a **360px-tall** panel filling its column, `mapStyle={config.BASEMAP_STYLE}`, `initialViewState` centred on `value` at zoom 10, `dragRotate={false}`. Wrap it in an element with `aria-label="Dive site map"` (role `group`) so the e2e test can find it.
   - One draggable `Marker` at `value`; `onDragEnd` calls `onChange(clampDiveSite({ lat: e.lngLat.lat, lon: e.lngLat.lng }))`. A map click also moves the pin. Render the pin as a token-styled child element (`bg-accent` dot with `border-fg`), not Marker's default blue.
   - No raw colours; no `color` prop with a literal.
3. **Upload transport** (`web/src/api/upload.ts`, new; the route imports it):
   ```ts
   import type { paths } from "./schema";
   type CreateSurveyMultipart = paths["/api/surveys"]["post"]["requestBody"]["content"]["multipart/form-data"];
   type ValidationError = paths["/api/surveys"]["post"]["responses"][422]["content"]["application/json"];

   export type UploadInput = { video: File; lat: number; lon: number; diveDate: string; siteName?: string };
   export type UploadProgress = { loaded: number; total: number };
   export type FieldError = { field: "video" | "lat" | "lon" | "dive_date" | "site_name" | string; message: string };
   export type UploadOutcome =
     | { ok: true; survey: Survey }
     | { ok: false; status: number | null; fieldErrors: FieldError[]; message: string };

   export function uploadSurvey(
     input: UploadInput,
     options: { onProgress?: (progress: UploadProgress) => void },
   ): Promise<UploadOutcome>;

   export function formatBytes(bytes: number): string;     // 43600000 → "43.6 MB"; 18300000 → "18.3 MB"
   export function formatDuration(seconds: number): string; // 62.4 → "01:02"
   ```
   - `XMLHttpRequest`, `POST` to `` `${config.API_URL}/api/surveys` ``, a `FormData` with `video`, `lat`, `lon`, `dive_date`, and `site_name` **only when non-empty**. Send `lat`/`lon` as decimal strings; `dive_date` as `YYYY-MM-DD`.
   - `xhr.upload.onprogress` → `onProgress({ loaded: event.loaded, total: event.total })` when `event.lengthComputable`.
   - `onload`: `201` → parse the JSON body as `Survey` and return `{ ok: true, survey }`; `422` → parse `{ detail: [...] }`, map each entry's `loc` **last element** to a `FieldError` (`["body","lat"]` → `lat`; if `loc` has no field name, use `""` and the route shows it as a form-level error) and return `{ ok: false, status: 422, fieldErrors, message }`; any other status → `{ ok: false, status, fieldErrors: [], message }` with a real sentence.
   - `onerror`/`ontimeout` → `{ ok: false, status: null, fieldErrors: [], message: "Couldn't reach the ReefCase API. Check the connection and try again." }`.
   - **Mock-mode progress.** MSW's service-worker interception never fires XHR upload progress (researcher; `mswjs.io/guides/recipes/xmlhttprequest-progress-events`). When `config.MOCK_API` is true, animate progress inside `uploadSurvey` on a 120ms interval from 0 to 92% of `video.size` and snap to 100% on `load`, clearing the interval in every terminal branch. Comment it as mock-only. Real mode stays driven only by `onprogress`.
   - No `openapi-fetch` for this call; do not hand-write a duplicate request/response type.
4. **Upload route** (`web/src/routes/upload.tsx`, replacing the 6.1 placeholder; keep the file's `createFileRoute("/upload")` literal and the `01  CLIP` label):
   - Layout: `<form className="grid gap-4 p-4 lg:grid-cols-2">` with CLIP first in DOM order (narrow: one column, clip first), then SITE, then the submit button full width across both columns (`lg:col-span-2`). Gaps and padding on the 4px grid.
   - **CLIP.** Arc `file-dropzone` with `accept="video/*"`. Once chosen: file name (`text-ui text-fg`), then `size · duration` in mono `text-label text-muted tabular-nums` via `formatBytes` and `formatDuration`. Duration comes from a `<video>` element's `loadedmetadata` via `URL.createObjectURL` (revoke it on unmount/change); if metadata never loads, show `—` for the duration rather than blocking. Field error renders under the dropzone.
   - **SITE.** `SitePicker` at the top, then a two-column grid of Arc `number-field`s for latitude and longitude in mono with the formatted readout under each (`formatLatitude(value)`, `formatLongitude(value)`). The fields hold **signed decimal degrees** and stay in sync with the pin in both directions. Then the optional site name (`input`) and the dive date (`date-picker`, default today). Lat/lon/date errors render under their own fields.
   - **Submit.** Arc `button` with variant `primary` (or the closest accent variant the vendored file exposes) labelled exactly `Start investigation`, `type="submit"`, full width. Disabled while a request is in flight; **not** disabled for missing fields (pressing it shows the validation errors, which is how a first-time user learns the form).
   - **Progress.** While in flight: Arc `progress` (or a 2px accent bar if the vendored component can't do 2px — keep the accent colour and `role="progressbar"`), with the mono readout `42% · 18.3 / 43.6 MB` computed from `formatBytes(loaded) / formatBytes(total)`, and `aria-valuenow`/`aria-valuemin`/`aria-valuemax`. It replaces the button label area, not the whole form.
   - **Errors.** On `{ ok: false }`: put each `fieldErrors` message under its field (`text-danger text-body`) and move focus to the first invalid field; a form-level message (no field) renders above the submit button in `text-danger text-body`. Clear a field's error when that field changes. Use `aria-invalid` and `aria-describedby`.
   - **Success.** `await navigate({ to: "/surveys/$id", params: { id: outcome.survey.id } })`. Await it (TanStack Router 1.170 returns `Promise<void>`).
   - Client-side pre-checks (required clip, lat −90..90, lon −180..180, date present) produce the same `FieldError` shape **without** a request, so the 422 path and the client path share one renderer.
5. **Tests before code** (decisions 3–4 are the contracts under test):
   - `web/src/api/upload.test.ts`: fake `XMLHttpRequest` via `vi.stubGlobal` (and `vi.unstubAllGlobals()` after each). Assert: `FormData` fields and that `site_name` is omitted when blank; progress events reach `onProgress`; 201 → `{ ok: true, survey }`; 422 → mapped `fieldErrors` for `["body","lat"]`; `onerror` → the "Couldn't reach the ReefCase API…" message; `formatBytes(18_300_000) === "18.3 MB"`, `formatDuration(62.4) === "01:02"`.
   - `web/src/components/SitePicker.test.tsx` (pure helpers only — never mount MapLibre in jsdom): all four formatters, S/N and E/W, four decimals always, clamping, and the two-space coordinate join.
   - `web/src/routes/upload.test.tsx`: `vi.mock("../api/upload")` and `vi.mock("../components/SitePicker")` (a stub that renders its readouts), and mock `useNavigate` from `@tanstack/react-router`. Assert: submit is possible without a clip and shows the clip error; choosing a file, a valid pin and a date then submitting shows `role="progressbar"` while pending and calls `navigate({ to: "/surveys/$id", params: { id } })` on success; a 422 outcome renders each message next to its input, sets `aria-invalid`, and `document.activeElement` is the first invalid field; changing a field clears its error.
   - `web/src/mocks/handlers.test.ts` (extend): `setupServer` with the real handlers; a valid multipart POST → 201 `Survey`; a POST missing `video`, or with `lat: 91` → 422 whose body is `{ detail: [{ loc: ["body", "<field>"], msg, type }] }`.
   - e2e (`e2e-tester`, decision 7).
6. **Mock handler** (`web/src/mocks/handlers.ts`, add to the existing POST, don't rewrite the file): `await request.formData()`, validate `video`, `lat` (−90..90), `lon` (−180..180), `dive_date` (ISO `YYYY-MM-DD`); on success `await delay(600)` and return the existing `survey` with 201; on failure return `HttpResponse.json({ detail: [{ loc: ["body", field], msg, type }] }, { status: 422 })`. Keep every other handler and the `/api/*` 404 fallback unchanged.
7. **e2e (e2e-tester)**: extend `web/e2e/upload.spec.ts` (new file) and keep `e2e/support.ts` helpers. For `/upload`, in **mock mode**:
   - assert the two section labels (`CLIP`, `SITE`), the map group with `aria-label="Dive site map"`, the lat/lon readouts, the `Start investigation` button, the filename/size readout after `setInputFiles` with an in-memory `lizard-island.mp4` buffer, and no console errors;
   - happy path: submit → a `role="progressbar"` appears → the URL becomes `/surveys/srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3` and the survey route renders that id;
   - no horizontal overflow at 390×844 (the mobile project already runs at that size);
   - screenshots at 1440×900 and 390×844 in `.scratch/ui/6-2-upload-page/upload-<width>.png`, taken in mock mode.
   - Call `stubBasemap(page)` before `goto` so the map never touches the network. If headless Chromium cannot create a WebGL context, add `launchOptions: { args: ["--use-angle=swiftshader"] }` to `web/playwright.config.ts` (that is the only 6.1 file this story may touch) and note it in the report.
   - `pnpm -C web exec playwright install chromium` first if the browser is missing.
8. **Green.** `pnpm -C web run gate` passes from the repo root; `python scripts/agents/ui_check.py` (run by the gate from `web/`) prints `clean`; `pnpm gen:api` leaves `src/api/schema.d.ts` unchanged.

## Tasks

Write the tests for each AC first, then the code.

1. **Vendor Arc + packages.** `python scripts/agents/arc_add.py file-dropzone date-picker input number-field button progress`, then `pnpm -C web add` its dependency line; `pnpm -C web add maplibre-gl@6.16.0 react-map-gl@8.1.3`. Read the vendored sources and record the prop names you will use.
2. **Tests: transport.** Write `web/src/api/upload.test.ts` against decision 3.
3. **Code: transport.** Write `web/src/api/upload.ts`; make task 2 green.
4. **Tests: SitePicker helpers.** Write `web/src/components/SitePicker.test.tsx` against decision 2.
5. **Code: SitePicker.** Write `web/src/components/SitePicker.tsx` (map + helpers) per decision 2, including the MapLibre worker URL (Library check).
6. **Tests: route.** Write `web/src/routes/upload.test.tsx` for both ACs per decision 5.
7. **Code: route.** Replace the `upload.tsx` placeholder body per decision 4; keep the route literal and section labels.
8. **Mocks.** Extend `handlers.ts` (decision 6) and `handlers.test.ts`.
9. **Green.** `pnpm -C web run gate`; fix ui_check hits as printed; re-run `pnpm -C web run gen:api` and confirm no `schema.d.ts` diff.
10. **e2e (e2e-tester).** Add `web/e2e/upload.spec.ts` per decision 7, run `pnpm -C web run e2e`, and save the screenshots.

## Lessons

Relevant entries from `ops/*/learnings.md` (all leads):

- [web] (6.1) RULE: Treat `typescript@7` as a type checker only — it ships no JS API, so no tool that imports the compiler API can run on it. Use oxlint for `web/` lint, and run `openapi-typescript` from `openapi-gen` pinned to `typescript@5.9.3`. WHY: typescript-eslint and openapi-typescript crash on TS 7; the gate depends on this split.
- [web] (6.1) RULE: In MSW 3 the `worker.start()` option is `onUnhandledFrame`, not `onUnhandledRequest`; a bare `worker.start()` warns on every document navigation. WHY: v3 renamed it, so a v2 snippet silently does nothing.
- [web] (6.1) RULE: Name OpenAPI event schemas by their `type` string when the union is discriminated on a property. WHY: openapi-typescript takes a discriminator's literal from the schema key, not the `enum`; long names generate a literal the reducer can never match. (No new schema here — do not add one for the 422 body.)

## Library check

Confirmed by the `researcher` subagent on 2026-10-27 against the pinned versions (unpkg tarballs for the exact versions, official docs, the vendored `.d.ts` files). Marked UNVERIFIED where the evidence was indirect.

### react-map-gl 8.1.3 + maplibre-gl 6.16.0
```tsx
import Map, { Marker } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";

<Map
  mapStyle={config.BASEMAP_STYLE}
  initialViewState={{ longitude, latitude, zoom: 10 }}
  style={{ width: "100%", height: 360 }}
  dragRotate={false}
  workerUrl={workerUrl}
>
  <Marker
    longitude={value.lon}
    latitude={value.lat}
    draggable
    onDragEnd={(event) => onChange(clampDiveSite({ lat: event.lngLat.lat, lon: event.lngLat.lng }))}
  >
    <span className="block size-3.5 rounded-full border-2 border-fg bg-accent" />
  </Marker>
</Map>
```
- `react-map-gl/maplibre` re-exports `@vis.gl/react-maplibre@8.1.3`; `Map` is the default export, `Marker` is named. The CSS is **not** auto-imported; import `maplibre-gl/dist/maplibre-gl.css`.
- `Map` defaults to `width:100%; height:100%; position:relative`, and `style` overrides it, so `{ width: "100%", height: 360 }` gives the 360px panel.
- `initialViewState` is uncontrolled (right for a picker). Adding `viewState` switches to controlled mode and requires `onMove` plus `width`/`height` in the object — don't.
- `Marker` takes `longitude`, `latitude`, `draggable`, `anchor` (default `center`), `onDragStart/onDrag/onDragEnd`, and renders React `children` as the marker element. `onDragEnd` receives `{ type: "dragend", lngLat }`, so `event.lngLat.lat` / `.lng`.
- **Worker gotcha (maplibre-gl 6.16.0):** the worker is no longer inlined. `dist/maplibre-gl.mjs` builds its URL dynamically (`new URL('./maplibre-gl-worker.mjs', import.meta.url)`), which Vite cannot rewrite, so the pre-bundled dep and the prod chunk 404 on it. The supported fix is the `workerUrl` prop on `<Map>` (it calls `maplibregl.setWorkerUrl(workerUrl)`); import the worker with Vite's `?url` suffix as above. Verify once with `pnpm -C web dev` and once with `pnpm -C web run build` (the build is not part of the gate, but check it once).
- The maplibre import happens inside `Map`'s `useEffect`, so no SSR/window guard is needed.
- `Map`/`Marker` TypeScript types: if `workerUrl` is missing from the installed `.d.ts` despite the runtime support, do **not** cast; import maplibre as `import maplibregl from "maplibre-gl"` in SitePicker and call `maplibregl.setWorkerUrl(workerUrl)` once at module scope instead.

### MSW 3.0.3 + XHR upload progress
- `xhr.upload.onprogress` does **not** fire under `setupWorker`: "the browser integration of MSW does not support the progress and upload progress events on XMLHttpRequest" (mswjs.io guides/recipes/xmlhttprequest-progress-events; mswjs/msw#2549). Hence decision 3's mock-only animation. The alternative (`@mswjs/interceptors` + `getResponse`) is more machinery for the same demo; don't add it.
- Handler signature is `http.post(path, async ({ request }) => …)`; `request` is a `StrictRequest` (`Request`), so `await request.formData()` works for multipart, and `HttpResponse.json(body, { status: 422 })` is the response.
- `delay(ms)` is exported from `msw` and works in both browser and node handlers.

### TanStack Router 1.170.46
- `useNavigate()` returns `(opts: NavigateOptions) => Promise<void>`. Use the route **pattern** with params: `navigate({ to: "/surveys/$id", params: { id } })`; an interpolated `` `/surveys/${id}` `` fails the registered-route type check. Awaiting it lets tests assert after commit.

### TanStack Query 5.105.0
- Hook-level `onSuccess`/`onError`/`onSettled` still exist on `useMutation` (v5 removed them only from `useQuery`); `mutation.isPending` is the v5 name. `mutateAsync` rejection is standard v5 behaviour (*UNVERIFIED* in source this session; wrap in `try/catch` anyway).

### Vitest 5.0.5 + jsdom 30.1.3
- Stub XHR with `vi.stubGlobal("XMLHttpRequest", FakeXHR)` and restore with `vi.unstubAllGlobals()`.
- jsdom 30.1.3 does **not** implement `URL.createObjectURL`. Any test that renders the CLIP preview must stub it (`URL.createObjectURL = vi.fn(() => "blob:preview")`, `URL.revokeObjectURL = vi.fn()`).
- `File`, `Blob`, `FileList`, `FileReader`, `FormData`, `XMLHttpRequest` and `XMLHttpRequestUpload` all exist in jsdom 30.
- jsdom 30 requires Node `^22.22.2 || ^24.15.0 || >=26`.

### Arc components
There is no external doc to trust here: `scripts/agents/arc_add.py` writes the component source into `web/src/components/arc/**`, and that generated source is the API reference. Read it, then use the props it actually declares. Never edit vendored files, and theme only through the tokens 6.1 built.
