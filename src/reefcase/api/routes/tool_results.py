"""GET /api/tool-results/{id} — the stored evidence a finding cites (Story 4.1, §6.3)."""

from fastapi import APIRouter, HTTPException, Request

from reefcase.core.errors import NotFoundError
from reefcase.core.schemas import ToolResult

__all__ = ["router"]

router = APIRouter()


@router.get("/tool-results/{tool_result_id}", response_model=ToolResult)
async def get_tool_result(tool_result_id: str, request: Request) -> ToolResult:
    """Return the stored result, or 404 when the id is unknown."""
    try:
        return await request.app.state.store.tool_results.get(tool_result_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
