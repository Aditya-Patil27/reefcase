# Story 2.4: Quality scoring and fail-fast

## Status: in-progress
- **Owner:** lead-b
- **Epic:** 2 — Pipeline Foundation
- **Files:**
  - `src/reefcase/ingest/quality.py`
  - `src/reefcase/pipeline/stages.py` (ingest stage only)
  - `src/reefcase/store/repos.py` (add `FrameRepo`)
  - `src/reefcase/store/db.py` (expose `store.frames`)
  - `src/reefcase/ingest/__init__.py` (re-export only)
  - `tests/ingest/test_quality.py`
- **Done when:** gate passes (`uv run poe gate`)

## Story (verbatim from `epics.md`)

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

## Architecture (frozen contract — §3, §4, §6)

### §4.2 Schemas (`reefcase.core.schemas`, already implemented — do not change)
```python
class QualityScore(BaseModel): blur: float; color_cast: float; turbidity: float; passed: bool; reason: str | None
class Frame(BaseModel):      id; survey_id; t_sec: float; image_path: str; quality: QualityScore
```

### §4.3 Events (`reefcase.core.events`, already implemented — do not change)
Every event has `survey_id`, `seq: int` (monotonic per survey, from 1) and `ts: datetime`.

| type | payload |
|---|---|
| `frames_extracted` | `count` |
| `frame_scored` | `frame_id`, `quality`, `thumb_url` |
| `survey_failed` | `reason` |

Publish through `EventBus(store)`; take `seq` from `await store.events.next_seq(survey_id)`.

### §4.4 Configuration (`reefcase.core.config.Settings`, already implemented)
`REEFCASE_KEEP_FRAMES` (default 24) → `settings.keep_frames`; `REEFCASE_MIN_FRAMES` (default 6) → `settings.min_frames`.
Never hard-code 24/6; read the settings.

### §6.1 JobRunner (already implemented — **do not modify `pipeline/runner.py`**)
Any exception from the stages moves the survey to FAILED, sets `failure_reason = str(exc)` and emits `survey_failed(reason)`. So raising `QualityError("too blurry")` from the ingest stage is the whole fail-fast mechanism.

### §6.4 Storage (already implemented)
- `store.blobs.save_frame(survey_id, frame_id, jpeg_bytes) -> str` writes `var/blobs/{survey_id}/frames/{frame_id}.jpg` and returns the blob ref.
- `store.blobs.resolve(ref) -> Path`.
- `frames` table + index exist (migration `003_frames.sql`, added by 2.3): `id, survey_id, t_sec, image_path, quality` (quality is JSON).
- All DB access goes through `Store.execute/fetchone/fetchall`; repos never touch the connection.

### §3 Layout
`ingest/` holds `frames.py` and `quality.py`; `pipeline/` holds `runner.py`, `bus.py`, `stages.py`.

## Exact signatures to implement

`src/reefcase/ingest/quality.py`
```python
BLUR_THRESHOLD: float          # minimum variance of Laplacian
TURBIDITY_THRESHOLD: float     # maximum turbidity
COLOR_CAST_THRESHOLD: float    # maximum mean |a*| + |b*|

class QualityError(ReefCaseError): ...

def score(image: np.ndarray) -> QualityScore: ...
```
`score` takes **only** `image` (plus nothing else). `passed` and `reason` are computed from the module constants only. Pick the constant values so that the real sharp fixture `tests/fixtures/frames/01.jpg` passes and the synthetic bad images below fail on exactly one criterion each.

`src/reefcase/pipeline/stages.py`
```python
async def ingest_stage(store: Store, survey_id: str, *, bus: EventBus | None = None,
                       settings: Settings | None = None) -> list[Frame]: ...
async def run_stages(store: Store, survey_id: str) -> None: ...   # ingest stage only for now
```

`src/reefcase/store/repos.py` — **append** `FrameRepo` (do not touch `SiteRepo`/`SurveyRepo`):
```python
class FrameRepo:
    def __init__(self, store: Store) -> None: ...
    async def save(self, frame: Frame) -> None: ...
    async def get(self, frame_id: str) -> Frame: ...              # NotFoundError when missing
    async def list_by_survey(self, survey_id: str) -> list[Frame]: ...  # ORDER BY t_sec, id
```
`src/reefcase/store/db.py` — `self.frames = FrameRepo(self)` alongside the other repos.

## Tasks (tests first)

1. **Tests** in `tests/ingest/test_quality.py` — one test per AC, written before the code:
   - AC1: `score` returns `QualityScore`; sharp fixture passes; each metric's bad image fails with its reason (`"too blurry"`, `"too murky"`, `"colour cast"`), and `score` has no threshold-override parameters.
   - AC2: ingest stage on `tests/fixtures/clip_10s.mp4` saves between `MIN_FRAMES` and `KEEP_FRAMES` frames, each `passed is True`, each blob file exists on disk, one `frames_extracted` event with `count >= len(frames)`, and one `frame_scored` event per saved frame with `thumb_url == f"/media/{survey_id}/frames/{frame_id}.jpg"`.
   - AC3: fewer than `MIN_FRAMES` passing frames → the ingest stage raises `QualityError` with the most common reason; and through `JobRunner(store, wrapper)` (inject a wrapper that calls `ingest_stage`, **do not** rely on a runner default) the survey ends `SurveyStatus.FAILED` with `failure_reason == "colour cast"` and one `survey_failed` event.
   - Use `@pytest.mark.asyncio` on async tests; use the `store` fixture from `tests/conftest.py`.
2. Implement `quality.py` to the signature above.
3. Implement `FrameRepo` (additive) and `store.frames`.
4. Implement `stages.py` ingest stage: extract candidates, score, pick the top `keep_frames` passing frames (sharpest first, then saved chronologically), save JPEG blobs via `store.blobs.save_frame`, persist `Frame` rows, publish events.
5. Keep the additive re-exports in `src/reefcase/ingest/__init__.py`; ensure the file ends with a newline.
6. Run `PYTHONIOENCODING=utf-8 uv run poe gate` until green.

## Do not
- Do not modify `src/reefcase/pipeline/runner.py`, `src/reefcase/api/**`, `tests/store/**`, `tests/api/**`, `tests/conftest.py`, or `src/reefcase/core/**` (frozen after Epic 1).
- Do not rewrite `SiteRepo`/`SurveyRepo`: keep `SurveyRepo.list`, `SurveyRepo.by_site`, the `ON CONFLICT (id) DO UPDATE` SQL, the docstrings and the `unknown site:` / `unknown survey:` error messages exactly as they are. `tests/store/test_store.py` depends on them.
- Do not add a `frames` migration (it already exists) and do not change blob paths.
- Do not put a threshold override kwarg on `score`.

## Lessons (from `ops/*/learnings.md`, relevant here)
- [test] (1-4) RULE: For async tests, add `@pytest.mark.asyncio` on each `async def test_…`; do not edit `[tool.pytest.ini_options]`.
- [python] (1-2) RULE: On a pydantic model field, write `Field(default_factory=list[Foo])`, not `Field(default_factory=list)`.
- [python] (1-3) RULE: On a `BaseSettings` that loads a human-copied `.env`, keep `env_ignore_empty=True` and `extra="ignore"` (already done — do not build `Settings()` in a way that reads a developer's real `.env`; prefer the `settings` argument / `make_settings()` helpers).
- [python] (2-1) RULE: Set `PYTHONIOENCODING=utf-8` for `uv run poe gate` on this Windows box (bash: `PYTHONIOENCODING=utf-8 uv run poe gate`). WHY: import-linter's spinner emoji crashes under cp1252.
- [python] (1-2) RULE: pyright strict is on for `src/reefcase/`; a redundant `cast` or an `Unknown` from an untyped repo attribute is a gate failure — annotate numpy results explicitly.

## Library check
- `numpy` / `Pillow` are long-stable and already dependencies (2.3 uses PyAV 19.0.2 and Pillow for decoding). This story uses only `np.var`, `np.std`, `np.mean`, `np.abs`, `np.cbrt` and `Image.fromarray(img).save(BytesIO(), format="JPEG", quality=90)` — no API newer than training data, so no researcher call is needed. If you need anything beyond that, reply `NEEDS_RESEARCH: <question>` instead of guessing.
- `duckdb` / `EventBus` / `Store` usage is already demonstrated by 2.3 in `stages`-adjacent code and `tests/store/test_store.py`; follow those patterns.
