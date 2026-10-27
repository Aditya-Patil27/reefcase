"""Story 1.5 AC 1 — every committed fixture is listed in data/LICENSES.md."""

from pathlib import Path

TESTS_DIR = Path(__file__).parent
REPO_ROOT = TESTS_DIR.parent
LICENSES_PATH = REPO_ROOT / "data" / "LICENSES.md"
FIXTURE_DIRS = [TESTS_DIR / "fixtures" / "frames", TESTS_DIR / "fixtures" / "masks"]
CLIP_PATH = TESTS_DIR / "fixtures" / "clip_10s.mp4"


def _licensed_names() -> set[str]:
    """Fixture file names in the 'Local fixtures' table with source and licence cells."""
    table = LICENSES_PATH.read_text(encoding="utf-8").split("## Local fixtures", 1)[1]
    licensed: set[str] = set()
    for line in table.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        if len(cells) < 3 or set(cells[0]) <= {"-", ":", " "}:
            continue
        if cells[1] and cells[2]:  # source URL and licence are both filled in
            licensed.add(Path(cells[0]).name)
    return licensed


def test_every_fixture_is_licensed() -> None:
    fixtures = {path.name for directory in FIXTURE_DIRS for path in directory.iterdir()}
    fixtures.add(CLIP_PATH.name)
    assert fixtures, "the fixture directories are empty"
    assert fixtures <= _licensed_names()


def test_clip_exists_and_is_a_real_file() -> None:
    assert CLIP_PATH.is_file()
    assert CLIP_PATH.stat().st_size > 0
