---
status: in-progress
---

# Story 3.4: SAM 3 on Modal

As the deployed demo,
I want segmentation served from a GPU endpoint,
So that the API container doesn't need a GPU.

- Owner: A · Priority: P0 · Depends on: 3.2
- Files: `ml/modal/sam_endpoint.py`, `src/reefcase/vision/modal_client.py`, `tests/vision/test_modal_client.py` (cassette)
- Done when: gate passes; `modal deploy ml/modal/sam_endpoint.py` succeeds

## Acceptance Criteria

**Given** a deployed endpoint
**When** `ModalSegmenter.segment` posts a JPEG
**Then** it receives a PNG class map with the same contract as 3.2

**Given** Modal credits are not granted
**When** this story is reached
**Then** it is skipped, and the demo uses the laptop fallback (architecture §12). The segmenter there is SAM 3 if the 3.2 VRAM check passed, otherwise ReefStudent (7.4), with demo-clip SAM 3 masks precomputed on Kaggle until 7.4 lands.

## Architecture contract

`ModalSegmenter.segment(image: np.ndarray) -> np.ndarray` posts an RGB JPEG to
`Settings.sam_modal_url` and decodes the returned PNG HxW uint8 class map.
The endpoint exposes the same image-to-class-map contract and has an offline
`--dry-run` path.

## Tasks

1. [ ] Add an offline client test that proves JPEG request and PNG class-map response.
2. [ ] Implement the HTTP client and Modal endpoint with a CPU fake dry-run.
3. [ ] Run `uv run poe gate`; do not run `modal deploy` unattended.
4. [ ] Review the diff against the reviewer contract and record the human deploy command.

## Lessons

None relevant beyond the repository rules.

## Library check

HTTP uses the already-pinned `httpx`; image boundaries use Pillow.
Modal deployment is a human-only step and is not invoked by tests or the gate.
