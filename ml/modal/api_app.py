"""ReefCase API and web app on Modal (Story 8.3, architecture §12).

One origin: the API serves the web build too (``REEFCASE_WEB_DIST``). The DuckDB store and
blobs live on the ``reefcase-data`` volume. Live uploads segment with SAM 3 on its Modal GPU
endpoint (the secret's ``REEFCASE_SAM_MODAL_*``); the historical seed uses ReefStudent on CPU
(``/data/models/reefstudent.pt``).

Human deployment steps, from a clean checkout (the image is synced from ``uv.lock``):
    pnpm -C web build
    modal secret create reefcase --from-dotenv .env      # once: LLM, SAM endpoint, GFW keys
    modal volume put reefcase-data <local reefstudent.pt> /models/reefstudent.pt
    PYTHONUTF8=1 uv run --with modal modal run ml/modal/api_app.py::seed
    PYTHONUTF8=1 uv run --with modal modal deploy ml/modal/api_app.py

Seed before deploying (or after ``modal app stop reefcase-api``): a volume keeps the last
writer's copy, so only one container may write the store at a time.

Laptop fallback (AC 2), the same build behind a Cloudflare tunnel:
    pnpm -C web build
    REEFCASE_WEB_DIST=web/dist uv run uvicorn --factory reefcase.api.main:create_app
    cloudflared tunnel --url http://localhost:8000

Credit guards: CPU only, one container, scale to zero after 10 min idle, no warm containers.
Do not add ``min_containers``: that bills around the clock.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from reefcase.core.config import Settings

try:
    import modal
except ImportError:  # pragma: no cover - Modal is a human deployment dependency.
    modal = None

APP_DIR = "/app"
DATA_DIR = "/data"
WEB_DIST = f"{APP_DIR}/web/dist"
# The API calls SAM 3 over HTTP; the seed runs ReefStudent in its own container.
API_CPU = 2
SEED_CPU = 2


def api_settings() -> Settings:
    """The deployed settings: the volume, the baked web build and SAM 3 on Modal win over the
    secret's env (a laptop ``.env`` may say ``fake`` or ``sam3_local``).

    Not ReefStudent: on the 2024 demo clip it read 46% live coral where SAM 3, the 2013-2019
    history and the assessor all say about 5%, and the investigator looped on the contradiction.
    """
    return Settings(data_dir=Path(DATA_DIR), web_dist=Path(WEB_DIST), segmenter="sam3_modal")


def seed_env(environ: Mapping[str, str]) -> dict[str, str]:
    """The import's env: write to the volume, and segment with ReefStudent on CPU so the covers
    are real."""
    return {
        **environ,
        "REEFCASE_DATA_DIR": DATA_DIR,
        "REEFCASE_SEGMENTER": "student",
        "REEFCASE_STUDENT_WEIGHTS": DATA_DIR + "/models/reefstudent.pt",
        # torch sizes its pool to the host's cores, not the container's; ReefStudent was
        # benchmarked at 807 ms a frame on 2 threads.
        "OMP_NUM_THREADS": str(SEED_CPU),
    }


if modal is not None:  # pragma: no cover - requires Modal CLI and credentials.
    app = modal.App("reefcase-api")
    image = (
        modal.Image.debian_slim(python_version="3.14")
        .uv_sync(frozen=True, extra_options="--no-dev --group gpu")
        .workdir(APP_DIR)
        # The geo tools read data/geo/*.parquet relative to the working directory.
        .add_local_dir("data/geo", f"{APP_DIR}/data/geo", ignore=["raw"])
        .add_local_file(
            "data/demo/history_manifest.csv", f"{APP_DIR}/data/demo/history_manifest.csv"
        )
        .add_local_file("scripts/import_history.py", f"{APP_DIR}/scripts/import_history.py")
        .add_local_dir("web/dist", WEB_DIST)
        # The default ships only .py files; the store's migrations (.sql) and the agent's
        # prompt (.md) are package data too.
        .add_local_python_source("reefcase", ignore=[])
    )
    data = modal.Volume.from_name("reefcase-data", create_if_missing=True)
    secrets = [modal.Secret.from_name("reefcase")]

    @app.function(
        image=image,
        # Frame extraction, JPEG work and ReefStudent starve on the 0.125-core default.
        cpu=float(API_CPU),
        volumes={DATA_DIR: data},
        secrets=secrets,
        max_containers=1,
        # A pipeline run outlives the upload request; keep the container up while it finishes.
        scaledown_window=600,
        # Long enough for an SSE stream to follow a whole run.
        timeout=1800,
    )
    @modal.concurrent(max_inputs=100)
    @modal.asgi_app()
    def api():
        from reefcase.api.main import create_app

        return create_app(api_settings())

    @app.function(image=image, cpu=float(SEED_CPU), volumes={DATA_DIR: data}, secrets=secrets, timeout=3600)
    def seed() -> None:
        """Import the historical surveys (8.1) onto the volume."""
        subprocess.run(
            [sys.executable, "scripts/import_history.py"], check=True, env=seed_env(os.environ)
        )
        data.commit()
