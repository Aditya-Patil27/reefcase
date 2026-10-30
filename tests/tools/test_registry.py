"""Story 4.1 — the tool framework: every result is persisted and cached (§5.4).

AC 1 is the cache rule: a second call with the same params returns the stored
``ToolResult`` (same ``tr_…`` id) and the transport sees no second request.
The rest of the framework's edges (canonical keys, persistence, unknown tools,
foreign params, a lying tool, ``get_json`` error mapping) are covered here too.

Everything is offline: HTTP goes through ``httpx.MockTransport`` and storage is
the conftest ``store`` fixture over ``tmp_path``.
"""

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from reefcase.core.errors import ExternalServiceError, ToolError
from reefcase.core.ids import TOOL_RESULT, new_id
from reefcase.core.schemas import ToolResult
from reefcase.store.db import Store
from reefcase.tools.http import (
    DEFAULT_TIMEOUT_S,
    USER_AGENT,
    ToolContext,
    build_client,
    get_json,
)
from reefcase.tools.registry import (
    ToolParams,
    ToolRegistry,
    ToolSpec,
    call_tool,
    canonical_params,
    registry,
    tool,
)

DHW_URL = "https://example.test/erddap/dhw"


class HeatParams(ToolParams):
    """The shape later stories give ``heat_stress`` (§5.4)."""

    site_id: str
    start: str
    end: str


class OtherParams(ToolParams):
    """A params model for a different tool, used to prove re-validation."""

    survey_id: str


class NestedParams(ToolParams):
    """Nested containers, to prove the canonical key is order-independent."""

    site_id: str
    window: dict[str, str]
    tags: list[str] | None = None


class Counter:
    """A ``MockTransport`` handler that records every request it sees."""

    def __init__(self, payload: Any = None, status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.payload = {"ok": True} if payload is None else payload
        self.status = status

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.payload)


def make_ctx(store: Store, settings: Any, transport: httpx.MockTransport) -> ToolContext:
    """A context whose HTTP client speaks to ``transport`` (never the network)."""
    return ToolContext(
        http=httpx.AsyncClient(transport=transport, headers={"User-Agent": "reefcase-test"}),
        store=store,
        settings=settings,
    )


def result_for(params: ToolParams, data: Any, *, tool_name: str = "heat_stress") -> ToolResult:
    """Build the sort of result a real tool returns."""
    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool=tool_name,
        params=params.model_dump(mode="json"),
        data=data,
        source_url=DHW_URL,
        retrieved_at=datetime.now(UTC),
    )


def heat_tool(calls: list[HeatParams]) -> Any:
    """A fake heat-stress tool that records invocations and fetches JSON."""

    async def heat_stress(params: HeatParams, ctx: ToolContext) -> ToolResult:
        calls.append(params)
        data = await get_json(ctx, DHW_URL, {"site_id": params.site_id})
        return result_for(params, data)

    return heat_stress


def make_registry() -> tuple[ToolRegistry, list[HeatParams]]:
    """A private registry with one fake tool and its invocation log."""
    calls: list[HeatParams] = []
    private = ToolRegistry()
    private.register(
        ToolSpec(
            name="heat_stress",
            params_type=HeatParams,
            fn=heat_tool(calls),
            description="NOAA CRW daily DHW and SST anomaly",
        )
    )
    return private, calls


PARAMS = {"site_id": "site_1", "start": "2026-01-01", "end": "2026-02-01"}


# --- AC 1: the second identical call is a cache hit -------------------------


@pytest.mark.asyncio
async def test_same_params_return_the_stored_result_without_http(
    store: Store, make_settings
) -> None:
    counter = Counter()
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))
    private, calls = make_registry()

    first = await private.call("heat_stress", dict(PARAMS), ctx)
    second = await private.call("heat_stress", dict(PARAMS), ctx)
    await ctx.http.aclose()

    assert first == second
    assert first.id.startswith("tr_")
    assert len(counter.requests) == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_param_order_does_not_change_the_cache_key(store: Store, make_settings) -> None:
    counter = Counter()
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))
    private, calls = make_registry()
    reordered = {"end": "2026-02-01", "site_id": "site_1", "start": "2026-01-01"}

    first = await private.call("heat_stress", dict(PARAMS), ctx)
    second = await private.call("heat_stress", reordered, ctx)
    await ctx.http.aclose()

    assert first.id == second.id
    assert len(counter.requests) == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_changed_params_miss_the_cache(store: Store, make_settings) -> None:
    counter = Counter()
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))
    private, calls = make_registry()

    first = await private.call("heat_stress", dict(PARAMS), ctx)
    second = await private.call("heat_stress", {**PARAMS, "end": "2026-03-01"}, ctx)
    count = await store.fetchone("SELECT count(*) FROM tool_results")
    await ctx.http.aclose()

    assert first.id != second.id
    assert len(counter.requests) == 2
    assert len(calls) == 2
    assert count == (2,)


# --- Persistence ------------------------------------------------------------


@pytest.mark.asyncio
async def test_result_round_trips_through_the_repo(store: Store, make_settings) -> None:
    counter = Counter(payload={"max_dhw": 4.5})
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))
    private, _calls = make_registry()

    result = await private.call("heat_stress", dict(PARAMS), ctx)
    stored = await store.tool_results.get(result.id)
    cached = await store.tool_results.find(
        "heat_stress", canonical_params(HeatParams.model_validate(PARAMS))
    )
    await ctx.http.aclose()

    assert stored == result
    assert stored.params == {"site_id": "site_1", "start": "2026-01-01", "end": "2026-02-01"}
    assert stored.data == {"max_dhw": 4.5}
    assert stored.source_url == DHW_URL
    assert stored.retrieved_at == result.retrieved_at
    assert cached == result


@pytest.mark.asyncio
async def test_cached_result_survives_a_reopened_store(
    data_dir, store: Store, make_settings
) -> None:
    counter = Counter()
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))
    private, _calls = make_registry()

    first = await private.call("heat_stress", dict(PARAMS), ctx)
    await ctx.http.aclose()
    store.close()

    reopened = Store.open(data_dir)
    try:
        again = await reopened.tool_results.get(first.id)
        found = await reopened.tool_results.find(
            "heat_stress", canonical_params(HeatParams.model_validate(PARAMS))
        )
    finally:
        reopened.close()

    assert again == first
    assert found == first


# --- Framework edges --------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_tool_is_a_tool_error(store: Store, make_settings) -> None:
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(Counter().handler))
    private, _calls = make_registry()

    with pytest.raises(ToolError):
        await private.call("vessel_activity", dict(PARAMS), ctx)
    with pytest.raises(ToolError):
        private.spec("vessel_activity")
    await ctx.http.aclose()


@pytest.mark.asyncio
async def test_foreign_or_extra_params_are_validation_errors(store: Store, make_settings) -> None:
    counter = Counter()
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))
    private, calls = make_registry()

    with pytest.raises(ValidationError):
        await private.call("heat_stress", OtherParams(survey_id="srv_1"), ctx)
    with pytest.raises(ValidationError):
        await private.call("heat_stress", {**PARAMS, "radius_km": 5}, ctx)
    await ctx.http.aclose()

    assert counter.requests == []
    assert calls == []


@pytest.mark.asyncio
async def test_result_naming_another_tool_is_a_tool_error(store: Store, make_settings) -> None:
    counter = Counter()
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))
    private = ToolRegistry()

    async def lies(params: HeatParams, _ctx: ToolContext) -> ToolResult:
        return result_for(params, {"ok": True}, tool_name="vessel_activity")

    private.register(ToolSpec("heat_stress", HeatParams, lies))

    with pytest.raises(ToolError):
        await private.call("heat_stress", dict(PARAMS), ctx)
    count = await store.fetchone("SELECT count(*) FROM tool_results")
    await ctx.http.aclose()

    assert count == (0,)


@pytest.mark.asyncio
async def test_result_with_other_params_is_a_tool_error(store: Store, make_settings) -> None:
    counter = Counter()
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))
    private = ToolRegistry()

    async def rewrites(params: HeatParams, _ctx: ToolContext) -> ToolResult:
        result = result_for(params, {"ok": True})
        return result.model_copy(update={"params": {**result.params, "end": "2026-12-31"}})

    private.register(ToolSpec("heat_stress", HeatParams, rewrites))

    with pytest.raises(ToolError):
        await private.call("heat_stress", dict(PARAMS), ctx)
    await ctx.http.aclose()


def test_registry_names_are_sorted() -> None:
    private = ToolRegistry()

    async def noop(_params: Any, _ctx: ToolContext) -> ToolResult:
        raise AssertionError("never called")

    private.register(ToolSpec("vessel_activity", OtherParams, noop))
    private.register(ToolSpec("heat_stress", HeatParams, noop))

    assert private.names() == ["heat_stress", "vessel_activity"]
    assert private.spec("heat_stress").description == ""


def test_tool_decorator_registers_and_returns_the_function() -> None:
    @tool("test_decorator_probe", HeatParams, description="probe")
    async def probe(_params: HeatParams, _ctx: ToolContext) -> ToolResult:
        raise AssertionError("never called")

    assert registry.spec("test_decorator_probe").fn is probe
    assert registry.spec("test_decorator_probe").description == "probe"
    assert "test_decorator_probe" in registry.names()


@pytest.mark.asyncio
async def test_call_tool_goes_through_the_module_registry(store: Store, make_settings) -> None:
    counter = Counter()
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))
    calls: list[HeatParams] = []

    @tool("test_call_tool_probe", HeatParams, description="probe")
    async def probe(params: HeatParams, _ctx: ToolContext) -> ToolResult:
        calls.append(params)
        return result_for(params, {"ok": True}, tool_name="test_call_tool_probe")

    first = await call_tool("test_call_tool_probe", dict(PARAMS), ctx)
    second = await call_tool("test_call_tool_probe", dict(PARAMS), ctx)
    await ctx.http.aclose()

    assert first == second
    assert len(calls) == 1


# --- Streaming errors -------------------------------------------------------


@pytest.mark.asyncio
async def test_get_json_maps_a_server_error(store: Store, make_settings) -> None:
    counter = Counter(status=500)
    ctx = make_ctx(store, make_settings(), httpx.MockTransport(counter.handler))

    with pytest.raises(ExternalServiceError) as caught:
        await get_json(ctx, DHW_URL)
    await ctx.http.aclose()

    error = caught.value
    assert error.status_code == 500
    assert error.retry_after is None
    assert error.url == str(counter.requests[0].url)


@pytest.mark.asyncio
async def test_get_json_carries_retry_after(store: Store, make_settings) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, headers={"Retry-After": "120"})

    ctx = make_ctx(store, make_settings(), httpx.MockTransport(handler))

    with pytest.raises(ExternalServiceError) as caught:
        await get_json(ctx, DHW_URL, {"site_id": "site_1"})
    await ctx.http.aclose()

    error = caught.value
    assert error.status_code == 503
    assert error.retry_after == 120.0
    assert error.url is not None
    assert "site_1" in error.url


@pytest.mark.asyncio
async def test_get_json_maps_transport_errors(store: Store, make_settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    ctx = make_ctx(store, make_settings(), httpx.MockTransport(handler))

    with pytest.raises(ExternalServiceError) as caught:
        await get_json(ctx, DHW_URL)
    await ctx.http.aclose()

    error = caught.value
    assert error.status_code is None
    assert error.retry_after is None
    assert error.url == DHW_URL


# --- Canonical keys and the client -----------------------------------------


def test_canonical_params_is_order_independent_and_stable() -> None:
    a = NestedParams(
        site_id="site_1", window={"start": "2026-01-01", "end": "2026-02-01"}, tags=["x", "y"]
    )
    b = NestedParams(
        site_id="site_1", window={"end": "2026-02-01", "start": "2026-01-01"}, tags=["x", "y"]
    )

    assert canonical_params(a) == canonical_params(b)
    assert canonical_params(a) == json.dumps(
        a.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    assert canonical_params(a) == canonical_params(a.model_copy())


def test_build_client_uses_the_documented_timeout_and_agent() -> None:
    client = build_client()

    assert client.timeout == httpx.Timeout(DEFAULT_TIMEOUT_S)
    assert client.headers["user-agent"] == USER_AGENT
