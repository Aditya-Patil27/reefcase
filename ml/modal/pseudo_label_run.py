"""Run SAM 3 over Coralscapes on a Modal T4 (Stories 7.1 and 7.3).

Kaggle kernels pushed from the CLI cannot read the ``HF_TOKEN`` secret that the gated
``facebook/sam3`` weights need, so the SAM 3 passes run here, beside the endpoint:

- train + validation (1,683 frames) -> ``pseudo_label.py`` -> ``/trainval`` (labels + manifest)
- test (392 frames, eval only, never trained on) -> ``/sam3_test`` (labels + ms/frame)

Run from the repo root, then fetch the results:
    PYTHONUTF8=1 uv run --with modal modal run ml/modal/pseudo_label_run.py
    uv run --with modal modal volume get reefcase-pseudo-labels / var/pseudo-labels

Credit guard: two T4 containers at most, about an hour in total (~$0.60).
"""

from __future__ import annotations

import modal

app = modal.App("reefcase-pseudo-label")
image = (
    modal.Image.debian_slim(python_version="3.14")
    .pip_install(
        # Same versions as the `gpu` group in pyproject.toml.
        "torch==2.14.1",
        "torchvision==0.29.1",
        "transformers==5.20.2",
        "huggingface_hub",
        "pyarrow",
        "numpy",
        "pillow",
        "pydantic",
        "pydantic-settings",
    )
    .add_local_python_source("reefcase")
    .add_local_file("ml/kaggle/pseudo_label.py", "/root/pseudo_label.py")
)
hf_cache = modal.Volume.from_name("reefcase-hf-cache", create_if_missing=True)
out = modal.Volume.from_name("reefcase-pseudo-labels", create_if_missing=True)

_REPO = "EPFL-ECEO/coralscapes"


@app.function(
    gpu="T4",
    cpu=4.0,
    memory=16384,
    image=image,
    secrets=[modal.Secret.from_name("huggingface")],
    volumes={"/root/.cache/huggingface": hf_cache, "/out": out},
    max_containers=2,
    timeout=3 * 3600,
)
def label(splits: list[str], limit: int | None = None) -> str:
    import json
    import statistics
    import time
    from pathlib import Path

    import numpy as np
    from PIL import Image

    frames = Path("/tmp/frames")
    names = _dump_frames(splits, frames, limit)

    if splits != ["test"]:
        from pseudo_label import pseudo_label_frames

        written = pseudo_label_frames(
            in_dir=frames,
            out_dir=Path("/out/trainval"),
            source="coralscapes",
            licence="Apache-2.0",
            segmenter="sam3_local",
        )
        out.commit()
        return f"{splits}: {len(names)} frames, {written} new labels"

    from reefcase.vision.sam3 import Sam3Segmenter

    segmenter = Sam3Segmenter()
    labels = Path("/out/sam3_test/labels")
    labels.mkdir(parents=True, exist_ok=True)
    timings: list[float] = []
    for name in names:
        image = np.asarray(Image.open(frames / name).convert("RGB"), dtype=np.uint8)
        start = time.perf_counter()
        mask = segmenter.segment(image)
        timings.append((time.perf_counter() - start) * 1000)
        Image.fromarray(mask, mode="L").save(labels / f"{Path(name).stem}.png")
    # The first frame pays for CUDA kernel compilation; it is not a steady-state number.
    steady = timings[1:] or timings
    summary = {
        "gpu": "T4 (Modal)",
        "frames": len(timings),
        "input": "1024x2048 RGB",
        "ms_per_frame_mean": statistics.fmean(steady),
        "ms_per_frame_median": statistics.median(steady),
    }
    Path("/out/sam3_test/timing.json").write_text(json.dumps(summary, indent=2))
    out.commit()
    return f"test: {json.dumps(summary)}"


def _dump_frames(splits: list[str], frames, limit: int | None) -> list[str]:
    """Write each split's images under their Coralscapes names (``siteNN_...png``)."""
    import pyarrow.parquet as pq
    from huggingface_hub import HfApi, hf_hub_download

    frames.mkdir(parents=True, exist_ok=True)
    files = sorted(HfApi().list_repo_files(_REPO, repo_type="dataset"))
    names: list[str] = []
    for split in splits:
        for file in (f for f in files if f.startswith(f"data/{split}-")):
            local = hf_hub_download(_REPO, file, repo_type="dataset", cache_dir="/tmp/hf")
            for row in pq.read_table(local, columns=["image"]).column("image").to_pylist():
                if limit is not None and len(names) >= limit:
                    return names
                (frames / row["path"]).write_bytes(row["bytes"])
                names.append(row["path"])
    return names


@app.local_entrypoint()
def main(limit: int | None = None) -> None:
    calls = [label.spawn(["train", "validation"], limit), label.spawn(["test"], limit)]
    for call in calls:
        print(call.get())
