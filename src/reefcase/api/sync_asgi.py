"""A *sync* httpx transport that drives the ASGI app in-process (Story 2.1).

httpx 0.28.1 ships ``ASGITransport`` for ``AsyncClient`` only — its ``Client``
context-manager protocol calls ``transport.__enter__``, which the async
transport does not implement. The API test suite needs a sync client for
start-up checks, so this module adapts the ASGI callable to ``BaseTransport``:
each request runs the app once on a private event loop. No network, no port.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

__all__ = ["SyncASGITransport"]


class SyncASGITransport(httpx.BaseTransport):
    """Send httpx ``Client`` requests straight to an ASGI app."""

    def __init__(self, app: Any) -> None:
        self._app = app

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Run the ASGI app once for ``request`` and build the response."""
        scope: dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": request.method,
            "scheme": request.url.scheme,
            "path": request.url.path,
            "raw_path": request.url.path.encode(),
            "query_string": request.url.query,
            "root_path": "",
            "headers": [(key.lower(), value) for key, value in request.headers.raw],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        }
        status, raw_headers, chunks = asyncio.run(self._call_app(scope, request))
        return httpx.Response(
            status_code=status,
            headers=[
                (key.decode("latin-1"), value.decode("latin-1")) for key, value in raw_headers
            ],
            content=b"".join(chunks),
            request=request,
        )

    async def _call_app(
        self, scope: dict[str, Any], request: httpx.Request
    ) -> tuple[int, list[tuple[bytes, bytes]], list[bytes]]:
        """Drive ``receive``/``send`` and collect the response messages."""
        status = 0
        raw_headers: list[tuple[bytes, bytes]] = []
        chunks: list[bytes] = []
        body_sent = False

        async def receive() -> dict[str, Any]:
            nonlocal body_sent
            if body_sent:
                return {"type": "http.disconnect"}
            body_sent = True
            return {"type": "http.request", "body": await request.aread(), "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            nonlocal status, raw_headers, chunks
            if message["type"] == "http.response.start":
                status = message["status"]
                raw_headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        await self._app(scope, receive, send)
        return status, raw_headers, chunks
