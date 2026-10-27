"""Repos over the store's single connection (architecture §4.2, §4.3, §6.4).

Every repo goes through ``Store.execute``/``fetch*``, so no repo ever touches
the connection directly and none nests ``locked()``. Every SQL string is inline
here and every value is a ``?`` parameter. Reading rebuilds each model field by
field, in the order the SELECT list spells out.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from reefcase.core.errors import NotFoundError
from reefcase.core.events import Event, EventAdapter
from reefcase.core.schemas import GeoPoint, SegClass, Site, Survey

if TYPE_CHECKING:
    from reefcase.store.db import Store

__all__ = ["EventRepo", "SiteRepo", "SurveyRepo"]

#: Columns ``events`` stores as its own fields; the rest goes to ``data`` as JSON.
_EVENT_OWN_COLUMNS = frozenset({"survey_id", "seq", "ts", "type"})


def _site_from_row(row: tuple[Any, ...]) -> Site:
    return Site(
        id=row[0],
        name=row[1],
        location=GeoPoint(lat=row[2], lon=row[3]),
        mpa_id=row[4],
        created_at=row[5],
    )


def _encode_cover(cover: dict[SegClass, float] | None) -> str | None:
    if cover is None:
        return None
    return json.dumps({key.value: value for key, value in cover.items()})


def _decode_cover(raw: str | None) -> dict[SegClass, float] | None:
    if raw is None:
        return None
    return {SegClass(key): value for key, value in json.loads(raw).items()}


def _survey_from_row(row: tuple[Any, ...]) -> Survey:
    return Survey(
        id=row[0],
        site_id=row[1],
        dive_date=row[2],
        status=row[3],
        source=row[4],
        video_path=row[5],
        cover=_decode_cover(row[6]),
        failure_reason=row[7],
        created_at=row[8],
    )


class SiteRepo:
    """Reads and writes ``sites``."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def save(self, site: Site) -> None:
        """Insert ``site`` or update the row with its id."""
        await self._store.execute(
            """
            INSERT INTO sites (id, name, lat, lon, mpa_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                name = excluded.name,
                lat = excluded.lat,
                lon = excluded.lon,
                mpa_id = excluded.mpa_id,
                created_at = excluded.created_at
            """,
            [
                site.id,
                site.name,
                site.location.lat,
                site.location.lon,
                site.mpa_id,
                site.created_at,
            ],
        )

    async def get(self, site_id: str) -> Site:
        """Return the site, or raise ``NotFoundError``."""
        row = await self._store.fetchone(
            """
            SELECT id, name, lat, lon, mpa_id, created_at FROM sites
            WHERE id = ?
            """,
            [site_id],
        )
        if row is None:
            raise NotFoundError(f"unknown site: {site_id}")
        return _site_from_row(row)

    async def list(self) -> list[Site]:
        """Return every site, ordered by id."""
        rows = await self._store.fetchall(
            "SELECT id, name, lat, lon, mpa_id, created_at FROM sites ORDER BY id"
        )
        return [_site_from_row(row) for row in rows]


class SurveyRepo:
    """Reads and writes ``surveys``."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def save(self, survey: Survey) -> None:
        """Insert ``survey`` or update the row with its id."""
        await self._store.execute(
            """
            INSERT INTO surveys
                (id, site_id, dive_date, status, source, video_path, cover, failure_reason,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                site_id = excluded.site_id,
                dive_date = excluded.dive_date,
                status = excluded.status,
                source = excluded.source,
                video_path = excluded.video_path,
                cover = excluded.cover,
                failure_reason = excluded.failure_reason,
                created_at = excluded.created_at
            """,
            [
                survey.id,
                survey.site_id,
                survey.dive_date,
                survey.status.value,
                survey.source,
                survey.video_path,
                _encode_cover(survey.cover),
                survey.failure_reason,
                survey.created_at,
            ],
        )

    async def get(self, survey_id: str) -> Survey:
        """Return the survey, or raise ``NotFoundError``."""
        row = await self._store.fetchone(
            """
            SELECT id, site_id, dive_date, status, source, video_path, cover,
                   failure_reason, created_at
            FROM surveys
            WHERE id = ?
            """,
            [survey_id],
        )
        if row is None:
            raise NotFoundError(f"unknown survey: {survey_id}")
        return _survey_from_row(row)

    async def list(self) -> list[Survey]:
        """Return every survey, ordered by id."""
        rows = await self._store.fetchall(
            """
            SELECT id, site_id, dive_date, status, source, video_path, cover,
                   failure_reason, created_at
            FROM surveys
            ORDER BY id
            """
        )
        return [_survey_from_row(row) for row in rows]

    async def by_site(self, site_id: str) -> list[Survey]:
        """Return one site's surveys, ordered by dive date then id."""
        rows = await self._store.fetchall(
            """
            SELECT id, site_id, dive_date, status, source, video_path, cover,
                   failure_reason, created_at
            FROM surveys
            WHERE site_id = ?
            ORDER BY dive_date, id
            """,
            [site_id],
        )
        return [_survey_from_row(row) for row in rows]


class EventRepo:
    """Appends to and reads the per-survey event log (§4.3, §6.2)."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def append(self, event: Event) -> None:
        """Persist ``event``; a duplicate ``(survey_id, seq)`` raises ``StoreError``."""
        payload = {
            key: value
            for key, value in event.model_dump(mode="json").items()
            if key not in _EVENT_OWN_COLUMNS
        }
        await self._store.execute(
            "INSERT INTO events (survey_id, seq, type, ts, data) VALUES (?, ?, ?, ?, ?)",
            [
                event.survey_id,
                event.seq,
                event.type,
                event.ts,
                json.dumps(payload),
            ],
        )

    async def next_seq(self, survey_id: str) -> int:
        """Return the next free ``seq`` for the survey (1 when it has none)."""
        row = await self._store.fetchone(
            "SELECT coalesce(max(seq), 0) + 1 FROM events WHERE survey_id = ?",
            [survey_id],
        )
        if row is None:
            return 1
        return int(row[0])

    async def list(self, survey_id: str, after_seq: int = 0) -> list[Event]:
        """Return the survey's events with ``seq > after_seq``, oldest first."""
        rows = await self._store.fetchall(
            """
            SELECT survey_id, seq, type, ts, data FROM events
            WHERE survey_id = ? AND seq > ?
            ORDER BY seq
            """,
            [survey_id, after_seq],
        )
        return [
            EventAdapter.validate_python(
                {
                    "survey_id": row[0],
                    "seq": row[1],
                    "type": row[2],
                    "ts": row[3],
                    **json.loads(row[4]),
                }
            )
            for row in rows
        ]
