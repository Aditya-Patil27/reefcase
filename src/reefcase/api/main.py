"""The FastAPI application factory (architecture §6.3).

``create_app(settings)`` builds the app with its ``Store`` already open —
``app.state.store`` must be usable the moment a request arrives, and FastAPI's
lifespan does not run under ``httpx.ASGITransport`` in tests, so build time is
the one hook that works in both worlds. The lifespan still closes the store on
shutdown for real servers.

Configuration comes only from ``Settings`` (env vars); nothing here reads
``.env`` itself.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from reefcase.api.routes import events, surveys
from reefcase.core.config import Settings
from reefcase.pipeline.bus import EventBus
from reefcase.pipeline.runner import JobRunner, RunStages
from reefcase.store.db import Store

__all__ = ["create_app"]


def _health_payload(settings: Settings) -> dict[str, object]:
    """Provider configuration status for ``GET /api/health`` (§6.3)."""
    return {
        "segmenter": settings.segmenter,
        "agent_llm": settings.llm_role("agent") is not None,
        "teacher_llm": settings.llm_role("teacher") is not None,
    }


def create_app(
    settings: Settings | None = None,
    run_stages: RunStages | None = None,
) -> FastAPI:
    """Build the API app: open the store, mount the routers, wire the lifespan.

    ``run_stages`` is injected for tests (2.2's SSE tests stub the stage
    chain); production wires the real chain when the stage stories land.
    """
    resolved = settings if settings is not None else Settings()

    store = Store.open(resolved.data_dir)
    app = FastAPI(title="ReefCase", lifespan=_lifespan(store))
    app.state.store = store
    app.state.settings = resolved
    app.state.health = _health_payload(resolved)
    app.state.bus = EventBus(store)
    app.state.runner = JobRunner(store, run_stages, bus=app.state.bus)

    app.include_router(surveys.router, prefix="/api")
    app.include_router(events.router, prefix="/api")
    app.get("/api/health")(_health_route)

    return app


def _health_route(request: Request) -> dict[str, object]:
    """Serve ``GET /api/health`` from the payload captured at build time."""
    health: dict[str, object] = request.app.state.health
    return health


def _lifespan(store: Store):
    """Close the store when the (real) server shuts down."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        try:
            yield
        finally:
            store.close()

    return lifespan
