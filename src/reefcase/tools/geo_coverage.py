"""The region the offline geo files cover (written by ``scripts/build_geo.py``).

``mpa_boundary`` and ``reef_map`` only hold polygons inside this box. Outside it, "not in an
MPA" and "0 km² of reef" would be false claims, so both tools answer ``available=false``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reefcase.core.errors import ToolError

__all__ = ["DEFAULT_COVERAGE_JSON", "outside_coverage"]

DEFAULT_COVERAGE_JSON: Path = Path("data/geo/coverage.json")


def outside_coverage(lat: float, lon: float) -> dict[str, Any] | None:
    """The ``available=false`` payload when the point is outside the built region, else None."""
    if not DEFAULT_COVERAGE_JSON.is_file():
        raise ToolError(f"{DEFAULT_COVERAGE_JSON} missing; run scripts/build_geo.py")
    w, s, e, n = json.loads(DEFAULT_COVERAGE_JSON.read_text())["bbox"]
    if w <= lon <= e and s <= lat <= n:
        return None
    return {
        "available": False,
        "reason": f"site is outside the mapped region (W,S,E,N = {w},{s},{e},{n})",
    }
