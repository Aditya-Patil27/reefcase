"""Build the animated README SVGs in docs/media/ (hero and pipeline).

The hero embeds a real HAW-41 frame, its SAM 3 mask and the Public Sans font, so it renders
the same everywhere GitHub shows it. Animation is SMIL, which GitHub plays inside <img>.

    uv run python scripts/readme_media/build_svgs.py <frame.jpg> <mask.png>

frame.jpg is a 640 px thumbnail from /media/<survey>/thumbs/<frame>.jpg and mask.png the
matching /media/<survey>/masks/<frame>.png.
"""

import base64
import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "media"
FONT = ROOT / "web/node_modules/@fontsource-variable/public-sans/files/public-sans-latin-wght-normal.woff2"
OTHER_RGB = (68, 79, 87)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def overlay(mask_path: Path, size: tuple[int, int]) -> tuple[bytes, dict[tuple[int, int, int], float]]:
    """Return the mask as an RGBA PNG with "other" transparent, plus each colour's share."""
    mask = Image.open(mask_path).convert("RGB").resize(size, Image.Resampling.NEAREST)
    rgba = Image.new("RGBA", size)
    shares: dict[tuple[int, int, int], float] = {}
    pixels = list(mask.get_flattened_data())
    rgba.putdata([(r, g, b, 0 if (r, g, b) == OTHER_RGB else 235) for r, g, b in pixels])
    for p in pixels:
        shares[p] = shares.get(p, 0) + 1 / len(pixels)
    buf = io.BytesIO()
    rgba.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), shares


def font_face() -> str:
    return (
        "@font-face{font-family:'Public Sans';font-weight:100 900;"
        f"src:url(data:font/woff2;base64,{b64(FONT.read_bytes())}) format('woff2')}}"
    )


def hero(frame: Path, mask: Path) -> str:
    img = Image.open(frame)
    png, shares = overlay(mask, img.size)
    live = shares.get((75, 195, 159), 0)
    bleached = shares.get((236, 232, 217), 0)
    other = 1 - live - bleached
    W, H = 1280, 520
    ix, iy, iw = 676, 64, 540
    ih = round(iw * img.height / img.width)
    loop = "9s"
    # One clock for every animation: keyTimes are fractions of the 9 s loop.
    scan = 'keyTimes="0;0.07;0.36;0.87;1" calcMode="spline" keySplines="0 0 1 1;.45 0 .25 1;0 0 1 1;0 0 1 1"'
    steps = ["Upload", "Frames", "Segment", "Assess", "Investigate", "Report"]
    step_svg = []
    for i, name in enumerate(steps):
        x = 72 + i * 92
        on = 0.07 + i * 0.058
        k = f"0;{on:.3f};{on + 0.02:.3f};0.87;0.92;1"
        if i:
            step_svg.append(
                f'<line x1="{x - 92 + 13}" y1="430" x2="{x - 13}" y2="430" stroke="#2f5a5e" stroke-width="2"/>'
                f'<line x1="{x - 92 + 13}" y1="430" x2="{x - 13}" y2="430" stroke="#4bc39f" stroke-width="2" opacity="0">'
                f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{k}" dur="{loop}" repeatCount="indefinite"/></line>'
            )
        step_svg.append(
            f'<g><circle cx="{x}" cy="430" r="11" fill="none" stroke="#4f8582" stroke-width="2"/>'
            f'<g opacity="0"><circle cx="{x}" cy="430" r="12" fill="#4bc39f"/>'
            f'<path d="M{x - 5} {430}l3.5 3.5 6.5-7" fill="none" stroke="#062a33" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{k}" dur="{loop}" repeatCount="indefinite"/></g>'
            f'<text x="{x}" y="466" class="step" text-anchor="middle">{name}</text></g>'
        )
    stat_y = iy + ih + 52
    bar_y = iy + ih + 18
    seg = [(live, "#4bc39f"), (bleached, "#ece8d9"), (other, "#a9c4c0")]
    bar, x0 = [], ix
    for share, colour in seg:
        w = iw * share
        bar.append(f'<rect x="{x0:.1f}" y="{bar_y}" width="{w:.1f}" height="8" fill="{colour}"/>')
        x0 += w
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">ReefCase</title>
<desc id="d">A real reef frame from NOAA station HAW-41 is swept by a light that reveals its SAM 3 segmentation: {live:.0%} live coral.</desc>
<style>{font_face()}
text{{font-family:'Public Sans',ui-sans-serif,system-ui,sans-serif}}
.kick{{font-size:15px;font-weight:600;letter-spacing:.14em;fill:#9cc3c0}}
.word{{font-size:104px;font-weight:800;letter-spacing:-.045em;fill:#fff}}
.tag{{font-size:30px;font-weight:500;letter-spacing:-.01em;fill:#d3e5e1}}
.step{{font-size:14px;font-weight:600;fill:#9cc3c0}}
.lab{{font-size:15px;font-weight:700;fill:#062a33}}
.stat{{font-size:17px;font-weight:600;fill:#d3e5e1}}
.statb{{font-size:17px;font-weight:800;fill:#4bc39f}}
</style>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b3d4a"/><stop offset="1" stop-color="#05232b"/></linearGradient>
<radialGradient id="ca" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#9cc3c0" stop-opacity=".16"/><stop offset="1" stop-color="#9cc3c0" stop-opacity="0"/></radialGradient>
<linearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff6e3" stop-opacity="0"/><stop offset=".7" stop-color="#fff6e3" stop-opacity=".55"/><stop offset="1" stop-color="#fff6e3"/></linearGradient>
<clipPath id="reveal"><rect x="{ix}" y="{iy}" width="0" height="{ih}">
<animate attributeName="width" values="0;0;{iw};{iw};0" {scan} dur="{loop}" repeatCount="indefinite"/></rect></clipPath>
<clipPath id="panel"><rect x="{ix}" y="{iy}" width="{iw}" height="{ih}"/></clipPath>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<ellipse cx="300" cy="120" rx="420" ry="180" fill="url(#ca)"><animateTransform attributeName="transform" type="translate" values="0 0;60 30;0 0" dur="14s" repeatCount="indefinite"/></ellipse>
<ellipse cx="980" cy="470" rx="460" ry="160" fill="url(#ca)"><animateTransform attributeName="transform" type="translate" values="0 0;-70 -20;0 0" dur="17s" repeatCount="indefinite"/></ellipse>

<text x="72" y="120" class="kick">NOAA NCRMP · STATION HAW-41 · DIVE 2024-07-06</text>
<text x="66" y="228" class="word">ReefCase</text>
<text x="72" y="286" class="tag">Turn a diver’s reef video</text>
<text x="72" y="324" class="tag">into a cited investigation.</text>
{''.join(step_svg)}

<g clip-path="url(#panel)">
<image x="{ix}" y="{iy}" width="{iw}" height="{ih}" href="data:image/jpeg;base64,{b64(frame.read_bytes())}"/>
<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" fill="#2c7d80" opacity=".62"/>
<g clip-path="url(#reveal)">
<image x="{ix}" y="{iy}" width="{iw}" height="{ih}" href="data:image/jpeg;base64,{b64(frame.read_bytes())}"/>
<image x="{ix}" y="{iy}" width="{iw}" height="{ih}" opacity=".78" href="data:image/png;base64,{b64(png)}"/>
</g>
<g><rect x="{ix - 90}" y="{iy}" width="90" height="{ih}" fill="url(#beam)"/><rect x="{ix - 2}" y="{iy}" width="3" height="{ih}" fill="#fff6e3"/>
<animateTransform attributeName="transform" type="translate" values="0 0;0 0;{iw} 0;{iw} 0;0 0" {scan} dur="{loop}" repeatCount="indefinite"/>
<animate attributeName="opacity" values="0;1;1;0;0;0" keyTimes="0;0.07;0.355;0.37;0.99;1" dur="{loop}" repeatCount="indefinite"/></g>
</g>
<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" fill="none" stroke="#9cc3c0" stroke-opacity=".45" stroke-width="1.5"/>
<rect x="{ix + 14}" y="{iy + 14}" width="88" height="28" fill="#fff6e3"/><text x="{ix + 24}" y="{iy + 33}" class="lab">Frame 15</text>

<rect x="{ix}" y="{bar_y}" width="{iw}" height="8" fill="#2f5a5e"/>
<g opacity="0">{''.join(bar)}
<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;0.36;0.4;0.87;0.92;1" dur="{loop}" repeatCount="indefinite"/></g>
<g opacity="0">
<text x="{ix}" y="{stat_y}" class="stat"><tspan class="statb">{live:.0%} live coral</tspan>  ·  {bleached:.1%} bleached  ·  {other:.0%} rock and other  ·  SAM 3</text>
<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;0.38;0.43;0.87;0.92;1" dur="{loop}" repeatCount="indefinite"/></g>
</svg>
"""


def pipeline(dark: bool) -> str:
    c = (
        dict(bg="#0d2a31", edge="#1d4650", ink="#e8f1ee", sub="#9cc3c0", idle="#2f5a5e", on="#4bc39f", check="#062a33", chip="#123840", chipon="#4bc39f", chipink="#e8f1ee", chipinkon="#062a33")
        if dark
        else dict(bg="#f6faf8", edge="#cfe0dc", ink="#062a33", sub="#2f5a5e", idle="#b3ccc8", on="#0b3d4a", check="#ffffff", chip="#e8f1ee", chipon="#0b3d4a", chipink="#062a33", chipinkon="#ffffff")
    )
    W, H, y = 1280, 368, 88
    stages = [
        ("Upload", ["Diver clip,", "site pin, dive date"]),
        ("Frames", ["Sampled and", "quality-scored"]),
        ("Segment", ["SAM 3 on Modal", "or ReefStudent"]),
        ("Assess", ["Muse Spark Open,", "one call per frame"]),
        ("Investigate", ["Agent with five", "data tools"]),
        ("Report", ["Case file, every", "claim cited"]),
    ]
    tools = ["Heat stress · NOAA CRW", "Vessels · Global Fishing Watch", "Reef map · Allen Coral Atlas", "MPA · WDPA", "Site history · NCRMP"]
    loop = "8s"
    step = 0.075
    xs = [96 + i * 217.6 for i in range(len(stages))]
    parts = []
    for i, x in enumerate(xs):
        on = 0.04 + i * step
        k = f"0;{on:.3f};{on + 0.02:.3f};0.9;0.95;1"
        anim = f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{k}" dur="{loop}" repeatCount="indefinite"/>'
        if i:
            px = xs[i - 1]
            parts.append(f'<line x1="{px + 18}" y1="{y}" x2="{x - 18}" y2="{y}" stroke="{c["idle"]}" stroke-width="2"/>')
            parts.append(
                f'<line x1="{px + 18}" y1="{y}" x2="{px + 18}" y2="{y}" stroke="{c["on"]}" stroke-width="2.5">'
                f'<animate attributeName="x2" values="{px + 18};{px + 18};{x - 18};{x - 18};{px + 18}" keyTimes="0;{on - step:.3f};{on:.3f};0.95;1" dur="{loop}" repeatCount="indefinite"/></line>'
            )
        name, lines = stages[i]
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="16" fill="{c["bg"]}" stroke="{c["idle"]}" stroke-width="2"/>'
            f'<g opacity="0"><circle cx="{x}" cy="{y}" r="17" fill="{c["on"]}"/>'
            f'<path d="M{x - 7} {y}l5 5 9-10" fill="none" stroke="{c["check"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>{anim}</g>'
            f'<text x="{x}" y="{y + 52}" class="name" text-anchor="middle">{name}</text>'
            + "".join(f'<text x="{x}" y="{y + 80 + j * 24}" class="desc" text-anchor="middle">{t}</text>' for j, t in enumerate(lines))
        )
    # Tool calls land one by one under Investigate, the way the live trace panel fills.
    inv = 0.04 + 4 * step
    tx, ty = 64, 296
    widths = [round(len(t) * 8.2 + 40) for t in tools]
    for j, (label, w) in enumerate(zip(tools, widths)):
        on = inv + 0.02 + j * 0.05
        k = f"0;{on:.3f};{on + 0.02:.3f};0.9;0.95;1"
        parts.append(
            f'<rect x="{tx}" y="{ty}" width="{w}" height="36" fill="{c["chip"]}" stroke="{c["edge"]}"/>'
            f'<text x="{tx + 14}" y="{ty + 24}" class="chip">{label}</text>'
            f'<g opacity="0"><rect x="{tx}" y="{ty}" width="{w}" height="36" fill="{c["chipon"]}"/>'
            f'<text x="{tx + 14}" y="{ty + 24}" class="chipon">{label}</text>'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{k}" dur="{loop}" repeatCount="indefinite"/></g>'
        )
        tx += w + 12
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
<title id="t">Pipeline: upload, frames, segment with SAM 3 or ReefStudent, assess with Muse Spark Open, investigate with five data tools, report a cited case file.</title>
<style>{font_face()}
text{{font-family:'Public Sans',ui-sans-serif,system-ui,sans-serif}}
.name{{font-size:23px;font-weight:800;letter-spacing:-.01em;fill:{c["ink"]}}}
.desc{{font-size:18px;font-weight:400;fill:{c["sub"]}}}
.kick{{font-size:14px;font-weight:700;letter-spacing:.14em;fill:{c["sub"]}}}
.chip{{font-size:17px;font-weight:600;fill:{c["chipink"]}}}
.chipon{{font-size:17px;font-weight:600;fill:{c["chipinkon"]}}}
</style>
<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" fill="{c["bg"]}" stroke="{c["edge"]}" stroke-width="1.5"/>
<text x="64" y="40" class="kick">ONE SURVEY, STREAMED LIVE OVER SSE</text>
<text x="64" y="280" class="kick">TOOLS THE AGENT CALLS, IN ORDER</text>
{''.join(parts)}
</svg>
"""


def main() -> None:
    frame, mask = Path(sys.argv[1]), Path(sys.argv[2])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hero.svg").write_text(hero(frame, mask), encoding="utf-8")
    (OUT / "pipeline-light.svg").write_text(pipeline(dark=False), encoding="utf-8")
    (OUT / "pipeline-dark.svg").write_text(pipeline(dark=True), encoding="utf-8")


if __name__ == "__main__":
    main()
