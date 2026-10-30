"""The tool registry: typed params, one cache key, persisted results (§5.4).

A tool is ``(params, ctx) -> ToolResult``. ``ToolRegistry.call`` validates the
params against the tool's own model, derives the canonical-JSON cache key,
returns a stored result on a hit, and only otherwise runs the tool — then
checks the result describes this call before persisting it. So every piece of
evidence the agent cites has a ``tr_…`` id, and a repeated call costs no HTTP.
"""

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from reefcase.core.errors import ToolError
from reefcase.core.schemas import ToolResult
from reefcase.tools.http import ToolContext

__all__ = [
    "ToolFn",
    "ToolParams",
    "ToolRegistry",
    "ToolSpec",
    "call_tool",
    "canonical_params",
    "registry",
    "tool",
]


class ToolParams(BaseModel):
    """Base for every tool's params model; unknown fields are an error."""

    model_config = ConfigDict(extra="forbid")


ToolFn = Callable[[Any, ToolContext], Awaitable[ToolResult]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One registered tool: its name, params model, function and description."""

    name: str
    params_type: type[ToolParams]
    fn: ToolFn
    description: str = ""


def canonical_params(params: BaseModel) -> str:
    """The cache-key half for ``params``: sorted, compact, JSON-mode keys."""
    return json.dumps(params.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class ToolRegistry:
    """The name → ``ToolSpec`` map, with validation and caching in ``call``."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        """Register ``spec`` under its name (a later registration replaces it)."""
        self._specs[spec.name] = spec
        return spec

    def spec(self, name: str) -> ToolSpec:
        """Return the tool called ``name``, or raise ``ToolError``."""
        spec = self._specs.get(name)
        if spec is None:
            raise ToolError(f"unknown tool: {name}")
        return spec

    def names(self) -> list[str]:
        """Every registered tool name, sorted."""
        return sorted(self._specs)

    async def call(
        self,
        name: str,
        params: ToolParams | Mapping[str, Any],
        ctx: ToolContext,
    ) -> ToolResult:
        """Validate, serve from cache or run, then persist and return the result."""
        spec = self.spec(name)
        validated = spec.params_type.model_validate(params)
        key = canonical_params(validated)

        hit = await ctx.store.tool_results.find(name, key)
        if hit is not None:
            return hit

        result = await spec.fn(validated, ctx)
        if result.tool != name:
            raise ToolError(f"tool {name!r} returned a result for {result.tool!r}")
        if result.params != validated.model_dump(mode="json"):
            raise ToolError(f"tool {name!r} returned params that do not match the call")
        await ctx.store.tool_results.save(result, key)
        return result


registry = ToolRegistry()


def tool(
    name: str, params_type: type[ToolParams], *, description: str = ""
) -> Callable[[ToolFn], ToolFn]:
    """Register ``fn`` under ``name`` and return it unchanged."""

    def register_fn(fn: ToolFn) -> ToolFn:
        registry.register(
            ToolSpec(name=name, params_type=params_type, fn=fn, description=description)
        )
        return fn

    return register_fn


async def call_tool(
    name: str, params: ToolParams | Mapping[str, Any], ctx: ToolContext
) -> ToolResult:
    """``registry.call(...)``, for callers that only import this module."""
    return await registry.call(name, params, ctx)
