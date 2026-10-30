"""One DuckDB file, migrations, and the single writer (architecture §6.4).

``Store.open`` takes the data *directory* (``REEFCASE_DATA_DIR``): the database
is ``<data_dir>/reefcase.duckdb`` and blobs live under ``<data_dir>/blobs``.
One connection is guarded by one ``asyncio.Lock``; reads and writes both take
it. ``duckdb.Error`` never escapes this package — it becomes ``StoreError``.
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from reefcase.core.errors import StoreError
from reefcase.store.blobs import Blobs
from reefcase.store.repos import (
    AssessmentRepo,
    EventRepo,
    FrameRepo,
    SegmentationRepo,
    SiteRepo,
    SurveyRepo,
    ToolResultRepo,
)

__all__ = ["DB_FILENAME", "MIGRATIONS_DIR", "SPATIAL_BOOTSTRAP", "Store"]

DB_FILENAME = "reefcase.duckdb"
MIGRATIONS_DIR = Path(__file__).with_name("migrations")
SPATIAL_BOOTSTRAP = "INSTALL AND LOAD spatial;"
#: ``schema_migrations`` is created by code, not by a migration, so 001 is the first row.
_SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL
);
"""
_SPATIAL_LOADED_SQL = "SELECT loaded FROM duckdb_extensions() WHERE extension_name = 'spatial'"


def _close_quietly(connection: duckdb.DuckDBPyConnection | None) -> None:
    """Close ``connection`` if present; never raise."""
    if connection is None:
        return
    with contextlib.suppress(Exception):
        connection.close()


def _apply_migrations(connection: duckdb.DuckDBPyConnection, migrations_dir: Path) -> None:
    """Apply every unapplied ``*.sql`` in ``migrations_dir``, in filename order."""
    applied = {
        row[0] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.stem.split("_")[0]
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        connection.execute("BEGIN")
        try:
            connection.execute(sql)
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                [version, datetime.now(UTC)],
            )
            connection.execute("COMMIT")
        except duckdb.Error as exc:
            with contextlib.suppress(duckdb.Error):
                connection.execute("ROLLBACK")
            raise StoreError(f"migration {path.name} failed: {exc}") from exc
        applied.add(version)


class Store:
    """The only writer to the DuckDB file, serialised by one asyncio lock."""

    def __init__(self, data_dir: Path, connection: duckdb.DuckDBPyConnection) -> None:
        self._connection = connection
        self._lock = asyncio.Lock()
        self.blobs = Blobs(Path(data_dir))
        self.sites = SiteRepo(self)
        self.surveys = SurveyRepo(self)
        self.events = EventRepo(self)
        self.frames = FrameRepo(self)
        self.segmentations = SegmentationRepo(self)
        self.assessments = AssessmentRepo(self)
        self.tool_results = ToolResultRepo(self)

    @classmethod
    def open(cls, data_dir: Path | str, *, migrations_dir: Path | str | None = None) -> Store:
        """Open (or create) ``<data_dir>/reefcase.duckdb``, load spatial, apply migrations."""
        root = Path(data_dir)
        if root.exists() and not root.is_dir():
            raise StoreError(f"data dir is not a directory: {root}")
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StoreError(f"could not create the data dir {root}: {exc}") from exc

        connection: duckdb.DuckDBPyConnection | None = None
        try:
            connection = duckdb.connect(str(root / DB_FILENAME), config={"TimeZone": "UTC"})
            connection.execute(SPATIAL_BOOTSTRAP)
            loaded = connection.execute(_SPATIAL_LOADED_SQL).fetchone()
            if loaded != (True,):
                raise StoreError("the duckdb spatial extension is not loaded")
            connection.execute(_SCHEMA_MIGRATIONS_DDL)
            _apply_migrations(
                connection, Path(migrations_dir) if migrations_dir is not None else MIGRATIONS_DIR
            )
        except duckdb.Error as exc:
            _close_quietly(connection)
            raise StoreError(f"could not open the store at {root}: {exc}") from exc
        except StoreError:
            _close_quietly(connection)
            raise

        return cls(root, connection)

    @asynccontextmanager
    async def locked(self) -> AsyncGenerator[duckdb.DuckDBPyConnection]:
        """Hold the write lock and yield the connection."""
        async with self._lock:
            yield self._connection

    async def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> None:
        """Run one statement."""
        await self._run(lambda connection: connection.execute(sql, parameters))

    async def fetchall(
        self, sql: str, parameters: Sequence[Any] | None = None
    ) -> list[tuple[Any, ...]]:
        """Return every row."""
        return await self._run(lambda connection: connection.execute(sql, parameters).fetchall())

    async def fetchone(
        self, sql: str, parameters: Sequence[Any] | None = None
    ) -> tuple[Any, ...] | None:
        """Return the first row (or ``None``)."""
        return await self._run(lambda connection: connection.execute(sql, parameters).fetchone())

    async def _run[T](self, query: Callable[[duckdb.DuckDBPyConnection], T]) -> T:
        """Run ``query`` under the lock, wrapping ``duckdb.Error`` in ``StoreError``."""
        async with self.locked() as connection:
            try:
                return query(connection)
            except duckdb.Error as exc:
                raise StoreError(f"query failed: {exc}") from exc

    def close(self) -> None:
        """Close the connection; idempotent and never raises."""
        _close_quietly(self._connection)

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
