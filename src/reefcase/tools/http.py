"""The HTTP plumbing every context tool shares (architecture §5.4).

One ``ToolContext`` carries the client, the store and the settings. ``get_json``
is the only way tools talk to an upstream source: it maps every ``httpx``
failure onto ``ExternalServiceError`` so no tool ever leaks an httpx type, and
it reads ``Retry-After`` itself because ``raise_for_status`` would drop it.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from reefcase.core.config import Settings
from reefcase.core.errors import ExternalServiceError
from reefcase.store.db import Store

__all__ = ["DEFAULT_TIMEOUT_S", "USER_AGENT", "ToolContext", "build_client", "get_json"]

DEFAULT_TIMEOUT_S: float = 30.0
USER_AGENT: str = "reefcase/0.1"


@dataclass(slots=True)
class ToolContext:
    """What a tool call gets handed: HTTP, storage and configuration."""

    http: httpx.AsyncClient
    store: Store
    settings: Settings


def build_client() -> httpx.AsyncClient:
    """An ``AsyncClient`` with ``DEFAULT_TIMEOUT_S`` and ``USER_AGENT``."""
    return httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_S,
        headers={"User-Agent": USER_AGENT},
    )


def _retry_after(headers: httpx.Headers) -> float | None:
    """Seconds from a ``Retry-After`` header, or ``None`` when absent/unparsable."""
    raw = headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


async def get_json(ctx: ToolContext, url: str, params: Mapping[str, Any] | None = None) -> Any:
    """GET ``url`` and return the decoded JSON body.

    Raises ``ExternalServiceError`` on a non-2xx status (carrying the status,
    the sent URL and ``Retry-After`` when present) and on any ``httpx`` error.
    """
    try:
        response = await ctx.http.get(url, params=params)
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"GET {url} failed: {exc}", url=url) from exc

    sent_url = str(response.request.url)
    if not response.is_success:
        raise ExternalServiceError(
            f"GET {sent_url} returned {response.status_code}",
            status_code=response.status_code,
            url=sent_url,
            retry_after=_retry_after(response.headers),
        )
    return response.json()
