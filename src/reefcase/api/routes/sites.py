"""GET /api/sites and /api/sites/{id} — the reef map and the site timeline (Story 4.7, §6.3).

The shapes are the web's ``SiteSummary`` and ``SiteDetail`` (``web/src/api/openapi.snapshot.json``).
"""

from datetime import date
from enum import StrEnum

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from reefcase.core.errors import NotFoundError
from reefcase.core.schemas import GeoPoint, SegClass, Site, Survey, SurveyStatus

__all__ = ["SiteDetail", "SiteSummary", "SiteTrend", "router"]

router = APIRouter()

# Live coral change, as a fraction, beyond which a site is no longer stable (5 percentage points).
TREND_THRESHOLD = 0.05


class SiteTrend(StrEnum):
    """Cover trend since the first survey at the site."""

    DECLINING = "declining"
    STABLE = "stable"
    IMPROVING = "improving"


class SiteSummary(BaseModel):
    """A site on the map: where it is and its latest completed survey.

    ``live_coral_change`` is latest minus first live coral, as a fraction, between the surveys dated
    ``first_dive_date`` and ``latest_dive_date``; ``trend`` names it. One survey gives 0.0.
    """

    id: str
    name: str
    location: GeoPoint
    mpa_id: str | None
    latest_cover: dict[SegClass, float]
    latest_dive_date: date
    first_dive_date: date
    live_coral_change: float
    trend: SiteTrend


class SiteDetail(BaseModel):
    """A site and its surveys, newest first."""

    site: Site
    surveys: list[Survey]


@router.get("/sites", response_model=list[SiteSummary])
async def list_sites(request: Request) -> list[SiteSummary]:
    """Every site with a completed survey, ordered by id."""
    store = request.app.state.store
    completed: dict[str, list[Survey]] = {}
    for survey in await store.surveys.list():
        if survey.status == SurveyStatus.DONE and survey.cover is not None:
            completed.setdefault(survey.site_id, []).append(survey)

    summaries: list[SiteSummary] = []
    for site in await store.sites.list():
        history = sorted(completed.get(site.id, []), key=lambda s: (s.dive_date, s.id))
        if history:
            summaries.append(_summary(site, history))
    return summaries


@router.get("/sites/{site_id}", response_model=SiteDetail)
async def get_site(site_id: str, request: Request) -> SiteDetail:
    """Return the site and every survey of it, newest first, or 404."""
    store = request.app.state.store
    try:
        site = await store.sites.get(site_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    surveys = await store.surveys.by_site(site_id)  # ordered by dive_date, id
    return SiteDetail(site=site, surveys=surveys[::-1])


def _summary(site: Site, history: list[Survey]) -> SiteSummary:
    """Summarise ``site`` from its completed surveys, oldest first."""
    first, latest = history[0], history[-1]
    assert first.cover is not None and latest.cover is not None
    change = latest.cover[SegClass.LIVE_CORAL] - first.cover[SegClass.LIVE_CORAL]
    return SiteSummary(
        id=site.id,
        name=site.name,
        location=site.location,
        mpa_id=site.mpa_id,
        latest_cover=latest.cover,
        latest_dive_date=latest.dive_date,
        first_dive_date=first.dive_date,
        live_coral_change=change,
        trend=_trend(change),
    )


def _trend(change: float) -> SiteTrend:
    if change < -TREND_THRESHOLD:
        return SiteTrend.DECLINING
    if change > TREND_THRESHOLD:
        return SiteTrend.IMPROVING
    return SiteTrend.STABLE
