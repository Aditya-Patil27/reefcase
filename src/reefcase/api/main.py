"""The FastAPI application factory (architecture §6.3).

``create_app(settings)`` builds the app with its ``Store`` already open —
``app.state.store`` must be usable the moment a request arrives, and FastAPI's
lifespan does not run under ``httpx.ASGITransport`` in tests, so build time is
the one hook that works in both worlds. On a real server the lifespan runs the
``JobRunner`` in the background, then stops it and closes the store on shutdown.

Configuration comes only from ``Settings`` (env vars); nothing here reads
``.env`` itself.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import PurePath

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from reefcase.api.routes import events, sites, surveys, tool_results
from reefcase.core.config import Settings
from reefcase.pipeline import stages
from reefcase.pipeline.bus import EventBus
from reefcase.pipeline.runner import JobRunner, RunStages
from reefcase.store.db import Store

__all__ = ["create_app"]


def _health_payload(settings: Settings) -> dict[str, object]:
    """Provider configuration status for ``GET /api/health`` (§6.3).

    ``status``, ``detail`` and ``providers`` are the OpenAPI ``Health`` shape the web
    shell reads; the flat flags stay for scripts that already check them.
    """
    agent = settings.llm_role("agent") is not None
    teacher = settings.llm_role("teacher") is not None
    return {
        "status": "ok" if agent else "degraded",
        "detail": "models ok" if agent else "agent model not configured",
        "providers": {
            "segmenter": settings.segmenter,
            "investigator": "configured" if agent else "missing",
            "assessor": "configured" if teacher else "missing",
        },
        "segmenter": settings.segmenter,
        "agent_llm": agent,
        "teacher_llm": teacher,
    }


def create_app(
    settings: Settings | None = None,
    run_stages: RunStages | None = stages.run_stages,
) -> FastAPI:
    """Build the API app: open the store, mount the routers, wire the lifespan.

    ``run_stages`` defaults to the real stage chain (``pipeline.stages``);
    tests inject a stub (2.2's SSE tests) or ``None`` for no stages.
    """
    resolved = settings if settings is not None else Settings()

    store = Store.open(resolved.data_dir)
    bus = EventBus(store)
    runner = JobRunner(store, run_stages, bus=bus)
    app = FastAPI(title="ReefCase", lifespan=_lifespan(store, runner))
    app.state.store = store
    app.state.settings = resolved
    app.state.health = _health_payload(resolved)
    app.state.bus = bus
    app.state.runner = runner

    app.include_router(surveys.router, prefix="/api")
    app.include_router(events.router, prefix="/api")
    app.include_router(tool_results.router, prefix="/api")
    app.include_router(sites.router, prefix="/api")
    app.get("/api/health")(_health_route)
    # Frames and masks for the web (§6.3); thumb_url and mask_url point here.
    app.mount("/media", StaticFiles(directory=store.blobs.root, check_dir=False), name="media")
    # Last, so every API route wins (§12: one origin for the API and the web build).
    if resolved.web_dist is not None:
        app.mount("/", _WebApp(directory=resolved.web_dist, html=True), name="web")

    return app


class _WebApp(StaticFiles):
    """The built web app; an unknown path outside ``/api`` is a client-side route."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or PurePath(path).parts[:1] == ("api",):
                raise
            return await super().get_response("index.html", scope)


def _health_route(request: Request) -> dict[str, object]:
    """Serve ``GET /api/health`` from the payload captured at build time."""
    health: dict[str, object] = request.app.state.health
    return health


def _lifespan(store: Store, runner: JobRunner):
    """Run queued surveys while the (real) server is up; on shutdown let the runs in flight
    finish, then close the store."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        task = asyncio.create_task(runner.run_forever())
        try:
            yield
        finally:
            runner.close()
            await task
            store.close()

    return lifespan
