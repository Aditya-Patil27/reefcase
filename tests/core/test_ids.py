"""Contract tests for ``reefcase.core.ids`` (architecture §4.1).

IDs are prefixed ULIDs: a 48-bit millisecond timestamp in 10 Crockford base32
chars, then 80 random bits in 16 chars. Fixed width MSB-first is what makes
plain string comparison order by creation time.
"""

import pytest

from reefcase.core.ids import (
    ASSESSMENT,
    FRAME,
    INVESTIGATION,
    SEGMENTATION,
    SITE,
    SURVEY,
    TOOL_RESULT,
    _ulid_from_ms,
    new_id,
)

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ULID_LENGTH = 26

PREFIXES = [SITE, SURVEY, FRAME, SEGMENTATION, ASSESSMENT, TOOL_RESULT, INVESTIGATION]


def test_prefixes_are_the_contract() -> None:
    assert PREFIXES == ["site", "srv", "frm", "seg", "asm", "tr", "inv"]


@pytest.mark.parametrize("prefix", PREFIXES)
def test_new_id_shape(prefix: str) -> None:
    identifier = new_id(prefix)

    assert identifier.startswith(f"{prefix}_")
    tail = identifier.removeprefix(f"{prefix}_")
    assert len(tail) == ULID_LENGTH
    assert set(tail) <= set(CROCKFORD)
    assert not set(tail) & set("ILOU")
    assert tail[0] in "01234567"


def test_new_id_unique() -> None:
    assert len({new_id(FRAME) for _ in range(1000)}) == 1000


def test_ulid_sorts_by_timestamp() -> None:
    first = _ulid_from_ms(1_700_000_000_000)
    second = _ulid_from_ms(1_700_000_000_001)
    third = _ulid_from_ms(1_700_000_000_002)

    assert first < second < third
    assert len(first) == ULID_LENGTH
