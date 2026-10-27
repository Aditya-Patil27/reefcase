"""Prefixed ULID identifiers (architecture §4.1).

An id is ``<prefix>_<ulid>``. The ULID is 26 uppercase Crockford base32 chars:
10 for the 48-bit big-endian millisecond timestamp, then 16 for 80 random bits.
Fixed width MSB-first means plain string comparison orders ids by creation
time; within a millisecond ``Event.seq`` is the contract's tiebreaker.

The format is implemented here rather than with a package because
architecture §3 keeps ``core`` on the standard library plus pydantic.
"""

import os
import time

__all__ = [
    "ASSESSMENT",
    "FRAME",
    "INVESTIGATION",
    "SEGMENTATION",
    "SITE",
    "SURVEY",
    "TOOL_RESULT",
    "new_id",
]

SITE = "site"
SURVEY = "srv"
FRAME = "frm"
SEGMENTATION = "seg"
ASSESSMENT = "asm"
TOOL_RESULT = "tr"
INVESTIGATION = "inv"

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_id(prefix: str) -> str:
    """Return a new prefixed ULID for ``prefix``."""
    return f"{prefix}_{_ulid_from_ms(time.time_ns() // 1_000_000)}"


def _ulid_from_ms(ms: int) -> str:
    """Encode a millisecond timestamp as a full 26-char ULID."""
    return _encode(ms.to_bytes(6, "big"), 10) + _encode(os.urandom(10), 16)


def _encode(data: bytes, length: int) -> str:
    """Encode ``data`` as fixed-width Crockford base32, MSB first."""
    value = int.from_bytes(data, "big")
    return "".join(
        _CROCKFORD[(value >> (5 * (length - 1 - index))) & 0x1F] for index in range(length)
    )
