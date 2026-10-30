"""Store foundation tests (architecture §6.4; story 1.4, AC 1-3).

Every test builds its own DuckDB file and blob tree under ``tmp_path``; nothing
touches ``var/``. The store is opened once per test through
``Store.open(data_dir)`` and closed by the ``with`` block.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from reefcase.core.errors import NotFoundError, StoreError
from reefcase.core.events import (
    Assessed,
    Event,
    FramesExtracted,
    Segmented,
    SurveyStarted,
)
from reefcase.core.schemas import FrameAssessment, GeoPoint, SegClass, Site, Survey, SurveyStatus
from reefcase.store.db import Store

CREATED_AT = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
SURVEY_ID = "srv_01J0000000000000000000001"
SITE_ID = "site_01J0000000000000000000001"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "var"


def open_store(data_dir: Path) -> Store:
    return Store.open(data_dir)


def make_site(site_id: str = SITE_ID, name: str = "Raja Ampat") -> Site:
    return Site(
        id=site_id,
        name=name,
        location=GeoPoint(lat=-0.5, lon=130.25),
        created_at=CREATED_AT,
    )


# --- AC 1: open, spatial, migrations ---------------------------------------


@pytest.mark.asyncio
async def test_open_creates_db_applies_001_and_loads_spatial(data_dir: Path) -> None:
    assert not data_dir.exists()

    with open_store(data_dir) as store:
        versions = await store.fetchall("SELECT version FROM schema_migrations ORDER BY version")
        loaded = await store.fetchall("SELECT extension_name FROM duckdb_extensions() WHERE loaded")

    assert (data_dir / "reefcase.duckdb").is_file()
    assert versions == [("001",), ("002",), ("003",), ("004",), ("005",)]
    assert "spatial" in {row[0] for row in loaded}


@pytest.mark.asyncio
async def test_migrations_run_once(data_dir: Path) -> None:
    site = make_site()

    with open_store(data_dir) as store:
        applied_at = await store.fetchone("SELECT applied_at FROM schema_migrations")
        await store.sites.save(site)

    with open_store(data_dir) as store:
        rows = await store.fetchall("SELECT version, applied_at FROM schema_migrations")
        reread = await store.sites.get(site.id)

    assert applied_at is not None
    assert rows[0] == ("001", applied_at[0])  # 001 ran once, before the reopen
    assert [version for version, _ in rows] == ["001", "002", "003", "004", "005"]
    assert reread == site


@pytest.mark.asyncio
async def test_migrations_apply_in_order_and_record_prefixes(
    data_dir: Path, tmp_path: Path
) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_alpha.sql").write_text("CREATE TABLE alpha (i INTEGER);", encoding="utf-8")
    (migrations / "002_beta.sql").write_text("CREATE TABLE beta (i INTEGER);", encoding="utf-8")

    with Store.open(data_dir, migrations_dir=migrations) as store:
        first = await store.fetchall("SELECT version FROM schema_migrations ORDER BY version")

    with Store.open(data_dir, migrations_dir=migrations) as store:
        second = await store.fetchall("SELECT version FROM schema_migrations ORDER BY version")

    broken = migrations / "003_broken.sql"
    broken.write_text("CREATE TABLE gamma (i INTEGER); SELEC nonsense;", encoding="utf-8")

    with pytest.raises(StoreError):
        Store.open(data_dir, migrations_dir=migrations)

    broken.unlink()
    with Store.open(data_dir, migrations_dir=migrations) as store:
        third = await store.fetchall("SELECT version FROM schema_migrations ORDER BY version")
        gamma = await store.fetchall(
            "SELECT table_name FROM duckdb_tables() WHERE table_name = 'gamma'"
        )

    assert first == [("001",), ("002",)]
    assert second == first
    assert third == first
    assert gamma == []


# --- AC 2: repos round-trip -------------------------------------------------


@pytest.mark.asyncio
async def test_site_round_trips(data_dir: Path) -> None:
    offset_created_at = datetime(
        2026, 10, 26, 17, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )
    without_mpa = Site(
        id=SITE_ID,
        name="Raja Ampat",
        location=GeoPoint(lat=-0.5, lon=130.25),
        created_at=offset_created_at,
    )
    with_mpa = Site(
        id="site_01J0000000000000000000002",
        name="Bunaken",
        location=GeoPoint(lat=1.62, lon=124.75),
        mpa_id="mpa_1",
        created_at=CREATED_AT,
    )

    with open_store(data_dir) as store:
        await store.sites.save(without_mpa)
        await store.sites.save(with_mpa)
        got_without = await store.sites.get(without_mpa.id)
        got_with = await store.sites.get(with_mpa.id)
        listed = await store.sites.list()

    assert got_without == without_mpa
    assert got_without.created_at.utcoffset() == timedelta(0)
    assert got_with == with_mpa
    assert listed == [without_mpa, with_mpa]


@pytest.mark.asyncio
async def test_survey_round_trips(data_dir: Path) -> None:
    with_cover = Survey(
        id=SURVEY_ID,
        site_id=SITE_ID,
        dive_date=date(2026, 10, 26),
        status=SurveyStatus.DONE,
        source="upload",
        video_path="blobs/srv_01J0000000000000000000001/video.mp4",
        cover={SegClass.LIVE_CORAL: 0.42, SegClass.SAND: 0.58},
        created_at=CREATED_AT,
    )
    without_cover = Survey(
        id="srv_01J0000000000000000000002",
        site_id=SITE_ID,
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.FAILED,
        source="historical",
        failure_reason="too blurry",
        created_at=CREATED_AT,
    )

    with open_store(data_dir) as store:
        await store.surveys.save(with_cover)
        await store.surveys.save(without_cover)
        got_with = await store.surveys.get(with_cover.id)
        got_without = await store.surveys.get(without_cover.id)
        listed = await store.surveys.list()
        by_site = await store.surveys.by_site(SITE_ID)
        other_site = await store.surveys.by_site("site_unknown")

    assert got_with == with_cover
    assert got_without == without_cover
    assert listed == [with_cover, without_cover]
    assert by_site == [without_cover, with_cover]
    assert other_site == []


@pytest.mark.asyncio
async def test_repos_raise_not_found(data_dir: Path) -> None:
    with open_store(data_dir) as store:
        with pytest.raises(NotFoundError):
            await store.sites.get("site_missing")
        with pytest.raises(NotFoundError):
            await store.surveys.get("srv_missing")


@pytest.mark.asyncio
async def test_save_is_an_upsert(data_dir: Path) -> None:
    site = make_site()
    renamed = site.model_copy(update={"name": "Renamed Reef"})

    with open_store(data_dir) as store:
        await store.sites.save(site)
        await store.sites.save(renamed)
        count = await store.fetchone("SELECT count(*) FROM sites")
        got = await store.sites.get(site.id)

    assert count == (1,)
    assert got == renamed


# --- AC 3: one writer -------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_writes_are_serialised(data_dir: Path) -> None:
    order: list[str] = []

    with open_store(data_dir) as store:

        async def enter_exit(label: str) -> None:
            async with store.locked():
                order.append(f"enter {label}")
                await asyncio.sleep(0)
                order.append(f"exit {label}")

        await asyncio.gather(enter_exit("a"), enter_exit("b"))

        site_a = make_site(site_id="site_a")
        site_b = make_site(site_id="site_b")
        await asyncio.gather(store.sites.save(site_a), store.sites.save(site_b))
        listed = await store.sites.list()

    assert order == ["enter a", "exit a", "enter b", "exit b"]
    assert listed == [site_a, site_b]


# --- Events (§4.3, §6.2) ----------------------------------------------------


@pytest.mark.asyncio
async def test_events_round_trip_and_resume(data_dir: Path) -> None:
    survey_started = SurveyStarted(survey_id=SURVEY_ID, seq=1, ts=CREATED_AT, site_id=SITE_ID)
    frames_extracted = FramesExtracted(survey_id=SURVEY_ID, seq=2, ts=CREATED_AT, count=120)
    segmented = Segmented(
        survey_id=SURVEY_ID,
        seq=3,
        ts=CREATED_AT,
        frame_id="frm_1",
        backend="sam3",
        cover={SegClass.LIVE_CORAL: 0.5},
        mask_url="blobs/srv_01J0000000000000000000001/masks/frm_1.png",
    )
    assessed = Assessed(
        survey_id=SURVEY_ID,
        seq=4,
        ts=CREATED_AT,
        assessment=FrameAssessment(
            id="asm_1",
            frame_id="frm_1",
            model="muse-spark-open",
            bleaching_severity=2,
            morphology=["branching"],
            damage=["none"],
            notes="Pale colony centre, no mortality.",
        ),
    )
    events: list[Event] = [survey_started, frames_extracted, segmented, assessed]

    with open_store(data_dir) as store:
        for event in events:
            await store.events.append(event)
        stored = await store.events.list(SURVEY_ID)
        resumed = await store.events.list(SURVEY_ID, after_seq=2)
        next_seq = await store.events.next_seq(SURVEY_ID)
        other_seq = await store.events.next_seq("srv_other")

    assert stored == events
    assert [event.seq for event in stored] == [1, 2, 3, 4]
    assert resumed == events[2:]
    assert next_seq == 5
    assert other_seq == 1


@pytest.mark.asyncio
async def test_duplicate_event_seq_is_a_store_error(data_dir: Path) -> None:
    event = SurveyStarted(survey_id=SURVEY_ID, seq=1, ts=CREATED_AT, site_id=SITE_ID)

    with open_store(data_dir) as store:
        await store.events.append(event)
        with pytest.raises(StoreError):
            await store.events.append(event)
        stored = await store.events.list(SURVEY_ID)

    assert stored == [event]


# --- Blobs (§6.4) -----------------------------------------------------------


def test_blob_paths_match_6_4(data_dir: Path) -> None:
    with open_store(data_dir) as store:
        blobs = store.blobs
        root = data_dir / "blobs"
        survey_dir = root / "srv_1"

        assert blobs.root == root
        assert blobs.survey_dir("srv_1") == survey_dir
        assert blobs.frame_path("srv_1", "frm_1") == survey_dir / "frames" / "frm_1.jpg"
        assert blobs.mask_path("srv_1", "frm_1") == survey_dir / "masks" / "frm_1.png"
        assert blobs.video_path("srv_1") == survey_dir / "video.mp4"
        assert blobs.video_path("srv_1", "mov") == survey_dir / "video.mov"
        assert blobs.video_path("srv_1", ".MOV") == survey_dir / "video.mov"


def test_blob_bytes_round_trip(data_dir: Path) -> None:
    with open_store(data_dir) as store:
        blobs = store.blobs
        frame_ref = blobs.save_frame("srv_1", "frm_1", b"jpeg")
        mask_ref = blobs.save_mask("srv_1", "frm_1", b"png")
        video_ref = blobs.save_video("srv_1", b"mp4")
        mov_ref = blobs.save_video("srv_1", b"mov", "mov")
        frame_bytes = blobs.read(frame_ref)
        mask_bytes = blobs.read(mask_ref)
        video_bytes = blobs.read(video_ref)
        mov_bytes = blobs.read(mov_ref)

    assert frame_ref == "blobs/srv_1/frames/frm_1.jpg"
    assert mask_ref == "blobs/srv_1/masks/frm_1.png"
    assert video_ref == "blobs/srv_1/video.mp4"
    assert mov_ref == "blobs/srv_1/video.mov"
    assert (data_dir / "blobs" / "srv_1" / "frames" / "frm_1.jpg").is_file()
    assert (frame_bytes, mask_bytes, video_bytes, mov_bytes) == (b"jpeg", b"png", b"mp4", b"mov")


def test_resolve_rejects_escape(data_dir: Path) -> None:
    with open_store(data_dir) as store:
        blobs = store.blobs
        ref = blobs.save_frame("srv_1", "frm_1", b"jpeg")

        with pytest.raises(StoreError):
            blobs.resolve("../secrets.txt")

        resolved = blobs.resolve(ref)

    assert resolved == (data_dir / "blobs" / "srv_1" / "frames" / "frm_1.jpg").resolve()
    assert resolved.is_absolute()


# --- Errors -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_error_wraps_duckdb(data_dir: Path) -> None:
    with open_store(data_dir) as store:
        with pytest.raises(StoreError):
            await store.execute("SELEC nonsense")

        versions = await store.fetchall("SELECT version FROM schema_migrations")

    assert versions == [("001",), ("002",), ("003",), ("004",), ("005",)]
