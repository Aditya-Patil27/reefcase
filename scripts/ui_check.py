"""Style check for web/: the UI rules that can be checked as text (tokens, not raw colours or palette classes; no gradients, glass, emoji or filler copy).

    python scripts/ui_check.py            # from the repo root
    python ../scripts/ui_check.py         # from web/ (the gate does this)

Prints `path:line: rule: found -> fix` per hit and exits 1 if there are any.
Vendored Arc code (components/arc/), the token files (styles/), generated API
types and tests are skipped; they legitimately hold raw colours.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SKIP_DIRS = ("src/components/arc/", "src/styles/")
SKIP_FILES = re.compile(r"(\.test\.tsx?|\.d\.ts)$")
CODE = {".ts", ".tsx", ".css"}
TEXT = CODE | {".json", ".html"}

PALETTE = "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose"
RULES: list[tuple[str, re.Pattern[str], set[str], str]] = [
    ("raw-colour",
     re.compile(r"(?<![\w&/])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b|\b(?:rgba?|hsla?|oklch|oklab)\("),
     CODE, "use a token class (bg-surface, text-muted, ...) or import from src/styles/palette.ts"),
    ("tailwind-palette",
     re.compile(rf"\b(?:bg|text|border|ring|outline|fill|stroke|from|via|to|divide|shadow|decoration|caret)-(?:{PALETTE})-\d{{2,3}}\b"
                r"|\b(?:bg|text|border)-(?:white|black)\b"),
     CODE, "use the semantic token classes defined in src/styles/theme.css"),
    ("gradient",
     re.compile(r"\bbg-(?:gradient|linear|radial|conic)-|\bbg-clip-text\b|\b(?:linear|radial|conic)-gradient\("),
     CODE, "flat token surfaces; separate areas with hairline or dashed borders"),
    ("glass-or-glow",
     re.compile(r"\bbackdrop-blur|\bblur-(?:sm|md|lg|xl|2xl|3xl)\b|\bshadow-(?:lg|xl|2xl)\b|\bdrop-shadow|\bglow\b"),
     CODE, "solid surfaces; elevation only via --shadow-floating on drawers and popovers"),
    ("big-radius",
     re.compile(r"\brounded-(?:xl|2xl|3xl)\b"),
     CODE, "rounded-md for controls, rounded-lg for panels, rounded-full only for dots and pills"),
    ("arbitrary-type",
     re.compile(r"\btext-\[\d"),
     CODE, "use the type scale (text-label, text-body, text-title, text-figure) from theme.css"),
    ("emoji",
     re.compile("[\U0001F000-\U0001FAFF☀-➿⭐⬆⬇⬅➡]"),
     TEXT, "use a lucide-react icon, or plain words"),
    ("filler-copy",
     re.compile(r"\b(?:lorem|ipsum|acme|john doe|jane doe|coming soon|unlock|seamless(?:ly)?|revolutioni[sz]e|supercharge|game-?changer|cutting-edge|ai-powered|powered by ai|magic(?:al)?|site [0-9]+|test site)\b", re.I),
     TEXT, "specific, plain copy; mock data uses real reef sites"),
    ("font-cdn",
     re.compile(r"fonts\.googleapis\.com|fonts\.gstatic\.com"),
     TEXT, "self-host fonts with @fontsource-variable/* packages"),
]


def scan(path: Path) -> list[str]:
    rel = path.relative_to(WEB).as_posix()
    if rel.startswith(SKIP_DIRS) or SKIP_FILES.search(rel) or rel.endswith("schema.d.ts"):
        return []
    hits = []
    for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for name, pattern, exts, fix in RULES:
            if path.suffix in exts and (m := pattern.search(line)):
                hits.append(f"web/{rel}:{n}: {name}: {m.group(0)!r} -> {fix}")
    return hits


def main() -> None:
    if not WEB.is_dir():
        raise SystemExit("no web/ directory yet")
    files = [p for p in (WEB / "src").rglob("*") if p.is_file() and p.suffix in TEXT]
    files += [p for p in [WEB / "index.html"] if p.exists()]
    hits = [h for p in sorted(files) for h in scan(p)]
    print("\n".join(hits) if hits else f"ui_check: {len(files)} files clean")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
