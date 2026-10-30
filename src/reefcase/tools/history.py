"""Past surveys history tool (architecture §5.4).

Queries the internal store for past completed surveys at a site, ordered
by dive date ascending, with cover breakdown per class. Excludes the current survey.
Runs entirely offline with zero network calls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from reefcase.core.ids import TOOL_RESULT, new_id
from reefcase.core.schemas import SegClass, SurveyStatus, ToolResult
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import ToolParams, tool

__all__ = ["SITE_HISTORY_SOURCE_URL", "SiteHistoryParams", "site_history"]

SITE_HISTORY_SOURCE_URL: str = "store://sites/"


class SiteHistoryParams(ToolParams):
    """Parameters for site_history tool."""

    site_id: str
    current_survey_id: str | None = None
    exclude_survey_id: str | None = None
    survey_id: str | None = None


@tool(
    "site_history",
    SiteHistoryParams,
    description="Past surveys of this site ordered by date with reef cover",
)
async def site_history(params: SiteHistoryParams, ctx: ToolContext) -> ToolResult:
    """Return completed surveys for a site ordered by dive_date, excluding current survey."""
    site = await ctx.store.sites.get(params.site_id)

    surveys = await ctx.store.surveys.by_site(params.site_id)
    exclude_id = params.current_survey_id or params.exclude_survey_id or params.survey_id

    # Filter for completed surveys and exclude the current survey
    past_surveys = [
        s
        for s in surveys
        if s.status == SurveyStatus.DONE and (exclude_id is None or s.id != exclude_id)
    ]

    # Ensure chronological order by dive_date then id
    past_surveys.sort(key=lambda s: (s.dive_date, s.id))

    history_records: list[dict[str, Any]] = []
    for s in past_surveys:
        cover_dict: dict[str, float] = {}
        live_coral: float = 0.0
        if s.cover:
            for cls, val in s.cover.items():
                cls_str = cls.value if hasattr(cls, "value") else str(cls)
                cover_dict[cls_str] = float(val)
            live_coral = float(s.cover.get(SegClass.LIVE_CORAL, 0.0))

        history_records.append(
            {
                "id": s.id,
                "survey_id": s.id,
                "date": s.dive_date.isoformat(),
                "dive_date": s.dive_date.isoformat(),
                "cover": cover_dict,
                "live_coral": live_coral,
            }
        )

    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool="site_history",
        params=params.model_dump(mode="json"),
        data={
            "site_id": site.id,
            "surveys": history_records,
            "count": len(history_records),
        },
        source_url=f"{SITE_HISTORY_SOURCE_URL}{site.id}",
        retrieved_at=datetime.now(UTC),
    )
