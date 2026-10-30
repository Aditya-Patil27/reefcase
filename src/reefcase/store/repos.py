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
from reefcase.core.schemas import (
    Frame,
    FrameAssessment,
    GeoPoint,
    QualityScore,
    SegClass,
    Segmentation,
    Site,
    Survey,
    ToolResult,
)

if TYPE_CHECKING:
    from reefcase.store.db import Store

__all__ = [
    "SITE_MATCH_RADIUS_M",
    "AssessmentRepo",
    "EventRepo",
    "FrameRepo",
    "SegmentationRepo",
    "SiteRepo",
    "SurveyRepo",
    "ToolResultRepo",
]

#: A survey within this distance of an existing site joins it (FR12, Story 2.5).
SITE_MATCH_RADIUS_M = 500.0

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

    async def find_site_near(
        self, location: GeoPoint, radius_m: float = SITE_MATCH_RADIUS_M
    ) -> Site | None:
        """Return the nearest site within ``radius_m`` of ``location`` (FR12), if any.

        Great-circle (haversine) distance on a sphere of radius 6371 km.
        """
        row = await self._store.fetchone(
            """
            SELECT id, name, lat, lon, mpa_id, created_at FROM (
                SELECT *, 2 * 6371000 * asin(sqrt(
                    pow(sin(radians(lat - ?) / 2), 2)
                    + cos(radians(?)) * cos(radians(lat)) * pow(sin(radians(lon - ?) / 2), 2)
                )) AS distance_m
                FROM sites
            )
            WHERE distance_m <= ?
            ORDER BY distance_m, id
            LIMIT 1
            """,
            [location.lat, location.lat, location.lon, radius_m],
        )
        return None if row is None else _site_from_row(row)

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
        assert row is not None  # an aggregate always returns one row
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


def _frame_from_row(row: tuple[Any, ...]) -> Frame:
    return Frame(
        id=row[0],
        survey_id=row[1],
        t_sec=row[2],
        image_path=row[3],
        quality=QualityScore.model_validate_json(row[4]),
    )


class FrameRepo:
    """Reads and writes ``frames`` (§4.2, §6.4)."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def save(self, frame: Frame) -> None:
        """Insert ``frame`` or update the row with its id."""
        await self._store.execute(
            """
            INSERT INTO frames (id, survey_id, t_sec, image_path, quality)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                survey_id = excluded.survey_id,
                t_sec = excluded.t_sec,
                image_path = excluded.image_path,
                quality = excluded.quality
            """,
            [
                frame.id,
                frame.survey_id,
                frame.t_sec,
                frame.image_path,
                frame.quality.model_dump_json(),
            ],
        )

    async def get(self, frame_id: str) -> Frame:
        """Return the frame, or raise ``NotFoundError``."""
        row = await self._store.fetchone(
            """
            SELECT id, survey_id, t_sec, image_path, quality FROM frames
            WHERE id = ?
            """,
            [frame_id],
        )
        if row is None:
            raise NotFoundError(f"unknown frame: {frame_id}")
        return _frame_from_row(row)

    async def list_by_survey(self, survey_id: str) -> list[Frame]:
        """Return one survey's frames, ordered by timestamp then id."""
        rows = await self._store.fetchall(
            """
            SELECT id, survey_id, t_sec, image_path, quality FROM frames
            WHERE survey_id = ?
            ORDER BY t_sec, id
            """,
            [survey_id],
        )
        return [_frame_from_row(row) for row in rows]


def _segmentation_from_row(row: tuple[Any, ...]) -> Segmentation:
    cover = _decode_cover(row[4])
    assert cover is not None  # the column is NOT NULL
    return Segmentation(
        id=row[0],
        frame_id=row[1],
        backend=row[2],
        mask_path=row[3],
        cover=cover,
        latency_ms=row[5],
    )


class SegmentationRepo:
    """Reads and writes ``segmentations`` (§4.2, §6.4)."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def save(self, segmentation: Segmentation) -> None:
        """Insert ``segmentation`` or update the row with its id."""
        await self._store.execute(
            """
            INSERT INTO segmentations (id, frame_id, backend, mask_path, cover, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                frame_id = excluded.frame_id,
                backend = excluded.backend,
                mask_path = excluded.mask_path,
                cover = excluded.cover,
                latency_ms = excluded.latency_ms
            """,
            [
                segmentation.id,
                segmentation.frame_id,
                segmentation.backend,
                segmentation.mask_path,
                _encode_cover(segmentation.cover),
                segmentation.latency_ms,
            ],
        )

    async def get_by_frame(self, frame_id: str) -> Segmentation:
        """Return the frame's latest segmentation, or raise ``NotFoundError``."""
        row = await self._store.fetchone(
            """
            SELECT id, frame_id, backend, mask_path, cover, latency_ms FROM segmentations
            WHERE frame_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            [frame_id],
        )
        if row is None:
            raise NotFoundError(f"no segmentation for frame: {frame_id}")
        return _segmentation_from_row(row)


def _assessment_from_row(row: tuple[Any, ...]) -> FrameAssessment:
    return FrameAssessment(
        id=row[0],
        frame_id=row[1],
        model=row[2],
        bleaching_severity=row[3],
        morphology=json.loads(row[4]),
        damage=json.loads(row[5]),
        notes=row[6],
    )


class AssessmentRepo:
    """Reads and writes ``assessments`` (§4.2, §5.3)."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def save(self, assessment: FrameAssessment) -> None:
        """Insert ``assessment`` or update the row with its id."""
        await self._store.execute(
            """
            INSERT INTO assessments
                (id, frame_id, model, bleaching_severity, morphology, damage, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                frame_id = excluded.frame_id,
                model = excluded.model,
                bleaching_severity = excluded.bleaching_severity,
                morphology = excluded.morphology,
                damage = excluded.damage,
                notes = excluded.notes
            """,
            [
                assessment.id,
                assessment.frame_id,
                assessment.model,
                assessment.bleaching_severity,
                json.dumps(assessment.morphology),
                json.dumps(assessment.damage),
                assessment.notes,
            ],
        )

    async def list_by_survey(self, survey_id: str) -> list[FrameAssessment]:
        """Return the survey's assessments in frame order (``t_sec``)."""
        rows = await self._store.fetchall(
            """
            SELECT a.id, a.frame_id, a.model, a.bleaching_severity, a.morphology,
                   a.damage, a.notes
            FROM assessments a
            JOIN frames f ON f.id = a.frame_id
            WHERE f.survey_id = ?
            ORDER BY f.t_sec, a.id
            """,
            [survey_id],
        )
        return [_assessment_from_row(row) for row in rows]


def _tool_result_from_row(row: tuple[Any, ...]) -> ToolResult:
    return ToolResult(
        id=row[0],
        tool=row[1],
        params=json.loads(row[2]),
        data=json.loads(row[3]),
        source_url=row[4],
        retrieved_at=row[5],
    )


class ToolResultRepo:
    """Persists and caches tool results by ``(tool, canonical params)`` (§5.4)."""

    _SELECT = "SELECT id, tool, params, data, source_url, retrieved_at FROM tool_results"

    def __init__(self, store: Store) -> None:
        self._store = store

    async def save(self, result: ToolResult, params_key: str) -> None:
        """Insert ``result``; a duplicate ``(tool, params_key)`` keeps the first row."""
        await self._store.execute(
            """
            INSERT INTO tool_results
                (id, tool, params_key, params, data, source_url, retrieved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tool, params_key) DO NOTHING
            """,
            [
                result.id,
                result.tool,
                params_key,
                json.dumps(result.params),
                json.dumps(result.data),
                result.source_url,
                result.retrieved_at,
            ],
        )

    async def get(self, tool_result_id: str) -> ToolResult:
        """Return the result, or raise ``NotFoundError``."""
        row = await self._store.fetchone(
            f"{self._SELECT} WHERE id = ?",
            [tool_result_id],
        )
        if row is None:
            raise NotFoundError(f"unknown tool result: {tool_result_id}")
        return _tool_result_from_row(row)

    async def find(self, tool: str, params_key: str) -> ToolResult | None:
        """Return the cached result for ``(tool, params_key)``, or ``None``."""
        row = await self._store.fetchone(
            f"{self._SELECT} WHERE tool = ? AND params_key = ?",
            [tool, params_key],
        )
        return None if row is None else _tool_result_from_row(row)
