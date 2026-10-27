# Story 1.5: Test fixtures and fakes

Owner: Opus (lead-b) · Priority: P0 · Depends on: 1.2, 1.4 · Status: in-progress

## Story (verbatim from epics.md)

As a developer,
I want shared fixtures and fake implementations,
So that every story's tests run offline and fast.

- Owner: Opus · Priority: P0 · Depends on: 1.2, 1.4
- Files: `tests/conftest.py`, `tests/fixtures/frames/*.jpg` (6 licensed frames),
  `tests/fixtures/masks/*.png` (hand masks), `tests/fixtures/clip_10s.mp4`,
  `src/reefcase/vision/fake.py`, `data/LICENSES.md`
- Done when: gate passes

### Acceptance Criteria (verbatim)

**Given** the fixtures
**When** listed in `data/LICENSES.md`
**Then** each has a source URL and licence

**Given** `FakeSegmenter`
**When** it segments any image
**Then** it returns a deterministic class map of the same height and width

## Architecture sections this story touches

### §5.1 — Segmenter interface (the contract `FakeSegmenter` implements)

```python
class Segmenter(Protocol):
    name: Literal["sam3", "student", "fake"]
    def segment(self, image: np.ndarray) -> np.ndarray: ...   # HxWx3 uint8 RGB → HxW uint8 class ids (§4.2)

def build_segmenter(settings: Settings) -> Segmenter   # Story 3.1, NOT this story
def cover_from_mask(mask: np.ndarray) -> dict[SegClass, float]   # Story 3.1, NOT this story
```

The class map values are the §4.2 class indices (`MASK_INDEX` in `core/schemas.py`):
`OTHER=0, LIVE_CORAL=1, BLEACHED_CORAL=2, ALGAE=3, RUBBLE=4, SAND=5`.

### §11 — Testing strategy (what the fixtures must serve)

- "Fixture images in `tests/fixtures/frames/` (6 frames with hand masks); `FakeSegmenter` for
  pipeline tests; SAM 3 tests marked `@pytest.mark.gpu`".
- Story 2.3: "`Given tests/fixtures/clip_10s.mp4, when extract_candidates(path, every_sec=0.5)
  runs, then it yields ~20 RGB frames with their t_sec`" → the clip must be ≥ 10 s so a 0.5 s
  stride yields ~20 candidates.
- AGENTS.md: fixtures are small — a few KB per file, frames ≤ 256 px.

### Consumers of this story (why it exists)

- lead-a is **blocked on 1.5** (Stories 3.1–3.5 read the fixture frames + hand masks and call
  `build_segmenter` → `FakeSegmenter`).
- Story 2.3/2.4 decode `clip_10s.mp4` and score the frames.
- Stories 2.2/3.5/5.1/5.4 run pipeline stages against `FakeSegmenter`.

## Contract notes / decisions (do not deviate)

1. **`FakeSegmenter` lives in `src/reefcase/vision/fake.py`** with `name = "fake"` and
   `segment(self, image: np.ndarray) -> np.ndarray`. `build_segmenter` is Story 3.1's file
   (`vision/segmenter.py`) — do **not** create it here.
2. **Deterministic and content-independent.** `segment` is a pure function of the image *shape*:
   the same HxW always yields the same class map, so pipeline tests can assert exact covers. All
   six §4.2 class ids appear in the pattern so cover computations exercise every class; values are
   within `0..5` (`MASK_INDEX` order).
3. **numpy is a new runtime dependency** (`uv add numpy`): §5.1 types the segmenter I/O as
   `np.ndarray`, and `vision/` cannot import it without the package. Nothing else is added.
4. **Fixtures are synthetic and self-authored**, generated offline (no network, no licence
   obligations), and committed as small binaries: 6 frames at 256×256 JPEG (a few KB each), 6
   matching hand masks at 256×256 8-bit grayscale PNG whose pixel values are the §4.2 class ids
   (so SAM 3 output can be compared against them in Story 3.2), and `clip_10s.mp4` (10 s, 256×256,
   4 fps → 40 frames, built from the same frames). `data/LICENSES.md` "Local fixtures" lists each
   with source "self-authored, generated offline for tests" and licence "CC0 (test fixture)" —
   satisfying AC 1 ("each has a source URL and licence"). The generator stays in `.scratch/`
   (git-ignored): only the story's listed files are committed.
5. **The hand masks correspond to the frames**: each frame is painted from its mask's class
   regions with per-class reef-plausible colours (plus deterministic noise so quality metrics in
   Story 2.4 see texture, not flat fields). Frame `01` is sharp, `06` is intentionally blurred —
   quality-threshold tests have both sides available without synthesising blur at test time.
6. **`tests/conftest.py` holds only shared, offline helpers**:
   - `FIXTURES_DIR` / `FRAMES_DIR` / `MASKS_DIR` paths and `fixture_frame(name)` / `fixture_mask(name)`;
   - `clip_path` fixture (`tests/fixtures/clip_10s.mp4`);
   - `data_dir` (empty `tmp_path/"var"`) and `store` (`Store.open(data_dir)`, closed afterwards);
   - `make_settings(**overrides)` factory that clears inherited `REEFCASE_*` env vars and builds
     `Settings(_env_file=None)` — the learning from 1-3 (never let a developer's real `.env`
     leak into a test) is applied once, here, for every later story.
   No network client, no cassette plumbing yet — Stories 4.2/4.3 add what they need.
7. **Tests live in `tests/vision/test_fake.py`** (FakeSegmenter ACs + a licence-table test for
   AC 1) — "their tests" per the loop. The licence test asserts every committed fixture file
   appears in `data/LICENSES.md`.
8. `src/reefcase/core/` stays untouched; the import-linter layers are unchanged
   (`vision` → `store`, `core` only).

## Tasks (tests first, then code)

1. `uv add numpy` (runtime; §5.1 types). Commit `pyproject.toml` + `uv.lock` with the batch.
2. `tests/vision/test_fake.py` — write it **before** `vision/fake.py` exists; watch it fail red:
   - AC 2 — `test_segment_returns_same_shape_uint8_class_map`: HxW uint8 output for an HxWx3
     uint8 input; every value in `0..5`.
   - AC 2 — `test_segment_is_deterministic_and_content_independent`: two calls on the same image
     are equal; two *different* images of the same shape give the same map.
   - AC 2 — `test_segment_pattern_covers_all_six_classes`: the 256×256 map contains every value
     in `MASK_INDEX.values()` (so `cover_from_mask` in 3.1 will see all classes).
   - AC 2 — `test_segmenter_name_is_fake`: `FakeSegmenter().name == "fake"` (the §5.1 Protocol
     attribute).
3. `tests/test_fixtures.py` — AC 1 (red first):
   - `test_every_fixture_is_licensed`: every file under `tests/fixtures/frames/`,
     `tests/fixtures/masks/` and `clip_10s.mp4` is named in `data/LICENSES.md`'s "Local fixtures"
     table, and each listed row carries a non-empty source and licence cell.
   - `test_clip_is_at_least_10s`: PyAV is not a dependency yet (Story 2.3 adds it), so assert on
     file size (> 0) only; the duration is guaranteed by the generator and verified by 2.3's AC.
     (A duration probe here would add the `av` dependency to this story's list.)
4. `src/reefcase/vision/fake.py`: `FakeSegmenter` — row-band pattern over the §4.2 indices:
   top half SAND? no — bands in §-cover order so each class is a contiguous, exactly-shaped
   region: rows 0..h/2 SAND (0.5), h/2..3h/4 LIVE_CORAL (0.25), 3h/4..7h/8 ALGAE (0.125),
   7h/8..h RUBBLE (0.125), with the first 2 columns of the LIVE_CORAL band BLEACHED_CORAL and the
   first column of SAND OTHER so all six ids exist. Deterministic integer arithmetic only (no
   RNG at import time beyond fixed constants).
5. Generate fixtures (one-off, `.scratch/gen_fixtures.py`, stdlib-only PNG writer + ffmpeg for
   JPEG/MP4): 6 class layouts → 6 hand-mask PNGs → 6 painted JPEG frames (01 sharp … 06
   blurred) → `clip_10s.mp4` (256×256, 4 fps, 10 s, cycling the 6 frames). Check sizes
   (a few KB each, clip well under 1 MB).
6. `tests/conftest.py` per contract note 6.
7. `data/LICENSES.md`: fill the "Local fixtures" table (7 rows).
8. `uv run poe gate` until green; confirm `lint-imports` keeps both contracts
   (`vision` still imports only `store` and `core`).
9. Self-review against the six reviewer items, commit, integrate.

## Lessons (from `ops/*/learnings.md`, relevant to this story)

- [python] (1-1) ruff excludes already cover the trees this story touches; the gate command stays
  verbatim.
- [python] (1-2) `planning` is excluded from ruff — the story file's ```python fences are safe.
- [test] (1-3) `make_settings` in conftest implements the clear-`REEFCASE_*` + `_env_file=None`
  pattern once for all later stories.
- [store] (1-4) the `store` fixture relies on `Store.open` already bootstrapping spatial; nothing
  new here.

## Library check (nothing newer than training data is called)

- No third-party API is called by this story beyond `numpy` array creation/slicing (stable API,
  numpy ≥ 2.3 wheels exist for cp314) and stdlib `zlib`/`struct`/`ffmpeg` CLI (local tool, not a
  project dependency). Nothing needs the `researcher`.
- Story 2.3's Library check will cover PyAV; this story deliberately does not add `av`.
