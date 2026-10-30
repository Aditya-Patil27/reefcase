"""Past surveys of a site, from the store (architecture §5.4).

The survey under investigation is RUNNING while the investigator calls this tool, so keeping
only DONE surveys leaves exactly the past ones. Makes no network calls.
"""

from __future__ import annotations

from datetime import UTC, datetime

from reefcase.core.ids import TOOL_RESULT, new_id
from reefcase.core.schemas import SurveyStatus, ToolResult
from reefcase.tools.http import ToolContext
from reefcase.tools.registry import ToolParams, tool

__all__ = ["SiteHistoryParams", "site_history"]


class SiteHistoryParams(ToolParams):
    """Parameters for site_history tool."""

    site_id: str


@tool(
    "site_history",
    SiteHistoryParams,
    description="Past completed surveys of this site, oldest first, with reef cover per class",
)
async def site_history(params: SiteHistoryParams, ctx: ToolContext) -> ToolResult:
    """Return the site's DONE surveys ordered by dive date."""
    site = await ctx.store.sites.get(params.site_id)
    surveys = await ctx.store.surveys.by_site(site.id)  # ordered by dive_date, id
    return ToolResult(
        id=new_id(TOOL_RESULT),
        tool="site_history",
        params=params.model_dump(mode="json"),
        data={
            "surveys": [
                {
                    "survey_id": s.id,
                    "dive_date": s.dive_date.isoformat(),
                    "cover": None if s.cover is None else {c.value: v for c, v in s.cover.items()},
                }
                for s in surveys
                if s.status == SurveyStatus.DONE
            ]
        },
        # The site page in the web app, which shows the same surveys.
        source_url=f"/sites/{site.id}",
        retrieved_at=datetime.now(UTC),
    )
