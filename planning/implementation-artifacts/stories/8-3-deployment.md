---
status: done
---

# Story 8.3: Deployment

As a judge,
I want a live URL that works,
So that I can try the product (Demo 25%).

- Owner: B (taken by guide: Claude Code) · Priority: P1 · Depends on: 5.4, 6.5
- Files: `ml/modal/api_app.py`, `src/reefcase/api/main.py` (serve the web build),
  `src/reefcase/core/config.py` (`REEFCASE_WEB_DIST`), `tests/api/test_web_dist.py`,
  `tests/ml/test_api_app.py`
- Also: `.env.example`, `tests/core/test_config.py`, architecture §4.4 and §12
- Done when: the public URL runs the demo clip end to end

## Acceptance Criteria

**Given** the deployed stack
**When** the demo clip is uploaded from a fresh browser
**Then** the case file is ready in ≤ 3 min (NFR1)

**Given** the cloud deployment fails on demo day
**When** the fallback is used
**Then** the laptop and Cloudflare tunnel serve the same build

## Architecture contract

- §12: the API runs as a Modal ASGI app (the Modal credits landed on 2026-10-28); segmentation
  runs on the Modal SAM 3 endpoint; demo data is seeded at deploy time from `data/demo/`.
- §4.4: configuration only through `REEFCASE_*` variables.
- NFR1: a case file in ≤ 3 min.

## Decisions

- **One origin.** The API serves the built web app (`REEFCASE_WEB_DIST`, unset by default)
  instead of a separate Cloudflare Pages site. The web already defaults `VITE_API_URL` to the
  same origin and `/media` URLs are relative, so there is no CORS to add, no
  `web/.env.production`, and the laptop fallback (uvicorn + `cloudflared tunnel`) serves the
  exact same build: AC 2 with one command.
- Any unknown path outside `/api` gets `index.html`, so the client-side routes (`/case/...`)
  survive a reload. An unknown `/api/...` path stays a JSON 404.
- **No Dockerfile.** The Docker daemon isn't part of the workflow and the SAM 3 endpoint
  already builds its image with Modal. The API image is `debian_slim` + `uv_sync(--no-dev)` from
  the lockfile, plus `reefcase`, `data/geo` and `web/dist`. PyAV wheels carry FFmpeg.
- **Data on a Modal Volume** (`reefcase-data`, mounted at `/data`). Modal commits it in the
  background and at shutdown, and the last writer wins, so exactly one container writes it:
  the API function has `max_containers=1`, and the seed runs before the API is deployed.
- **Credit guards:** CPU only, one container, no `min_containers`, scale to zero after 10 min
  idle (long enough for a ≤ 3 min run while nobody is watching the SSE stream).
- The Modal secret `reefcase` carries the `.env` keys (LLM, SAM endpoint, GFW). The data dir and
  web dist are pinned in code, so a stale `REEFCASE_DATA_DIR` in `.env` can't move them.
- **Core change, on purpose:** `REEFCASE_WEB_DIST` is one new optional `Settings` field;
  architecture §4.4 and §12 are amended to match.
- `seed` runs `scripts/import_history.py` (8.1) on the volume with
  `REEFCASE_SEGMENTER=sam3_modal`, so the historical covers are real SAM 3 output.

## Tasks

1. [x] Tests: the web build is served at `/`, client routes fall back to `index.html`, `/api`
   404s stay JSON, nothing is served at `/` when `REEFCASE_WEB_DIST` is unset; the Modal app
   pins its data dir and web dist over the env.
2. [x] `REEFCASE_WEB_DIST` in `Settings`, `.env.example`, §4.4.
3. [x] `create_app` serves the web build.
4. [x] `ml/modal/api_app.py`: `api` (ASGI) and `seed`.
5. [x] `uv run poe gate`.
6. [x] Review against `.opencode/agents/reviewer.md`.
7. [ ] Human-approved: create the secret, seed, deploy, upload the demo clip (needs 5.4).
   - [x] 2026-10-30: secret `reefcase` created from `.env`; seed imported HAW-41 2013/2016/2019
     (92 photos, SAM 3 on Modal); deployed at https://app2732006--reefcase-api-api.us-east.modal.run
     (`/api/health` sam3_modal + both LLMs, `/` and `/case/...` HTML, `/api/nope` JSON 404,
     `/api/sites` lists HAW-41).
   - [x] 2026-10-30: demo clip built (`scripts/build_demo_clip.py`: NCRMP 2024 OCC-HAW-002,
     30 photos x 0.5 s = 15 s, 1920x1280, 25.6 MB) and uploaded (lat 20.268249, lon
     -155.860434, 2024-07-06); it joined HAW-41. It sat `queued` until the runner fix below,
     then ran on the redeploy: case file ready, 8 cited findings, 5 tools.
   - [ ] AC 1 timing NOT met yet: 256 s from first poll to case file (12 s cold start + 240 s
     run) against NFR1's 180 s, for a 15 s clip. Run breakdown: ingest + scoring 9 s, segment
     (SAM 3, 24 frames, T4 cold) 84 s, assess (teacher, 4 at once) 104 s, investigate 43 s. The
     upload itself took 124 s over a home uplink (25.6 MB). Levers, for the stage owners:
     segment concurrency, `ASSESS_CONCURRENCY`, fewer `keep_frames`, a warm SAM 3 before the demo.
   - [ ] Redeploy after 4.6 so the map layers are served.

## Lessons

- Verified locally with the real build: `REEFCASE_WEB_DIST=web/dist uv run uvicorn --factory
  reefcase.api.main:create_app` serves `/` and `/case/...` as the app, `/api/health` as JSON, and
  `/api/nope` as a JSON 404. uvicorn comes in through pydantic-ai's mcp extra, so the laptop
  needs nothing extra.
- `Image.add_local_python_source` ships only `.py` files by default (`ignore=NON_PYTHON_FILES`):
  the first seed died on the missing `agent/prompts/investigator.md`, and the API would have
  died on the missing store migrations. `ignore=[]` ships the package data.
- The deployed segmenter is pinned to `sam3_modal` in code: the secret is the laptop `.env`,
  which may say `fake` or `sam3_local`.
- Nothing started the `JobRunner` on a real server: `create_app` built it but the lifespan only
  closed the store, so every upload stayed `queued`. Tests use `httpx.ASGITransport`, which skips
  the lifespan, so nothing caught it until the first live upload. Fixed in `api/main.py` with a
  `TestClient` (lifespan-running) test.
- Status stays `review` until task 7: AC 1 can only be proven on the deployed URL after 5.4.

## Library check

- modal 1.x: `Image.uv_sync(uv_project_dir, *, frozen, extra_options, ...)` syncs the locked
  dependencies without installing the project (so `add_local_python_source("reefcase")`);
  `@app.function(max_containers=, scaledown_window=, timeout=, volumes=, secrets=)`,
  `@modal.concurrent(max_inputs=)`, `@modal.asgi_app()`. Volumes commit "every few seconds" and
  "on container shutdown"; "last write wins" for concurrent writers (modal.com/docs/guide/volumes).
- Starlette `StaticFiles(html=True).get_response` raises `HTTPException(404)` for a missing file.
