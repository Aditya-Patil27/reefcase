"""Build the animated README SVGs in docs/media/ (hero.svg and pipeline.svg).

Both are drawn from the real HAW-41 run on the live app: frame thumbnails, SAM 3 masks,
Muse Spark assessments, tool results and the investigation. Fonts and images are embedded
as data URIs and the animation is SMIL, so GitHub plays them inside <img>.

    uv run python scripts/readme_media/build_svgs.py <cache_dir> <fonts_dir>

cache_dir holds the API responses and images; anything missing is fetched from the app.
fonts_dir holds woff2 subsets of Newsreader (400, 400 italic, 500) and IBM Plex Mono (400,
500) from @fontsource 5.3.0 on jsDelivr, cut with
    pyftsubset <font>.woff2 --unicodes="U+0020-007E,U+00B0,U+00B2,U+00B7,U+00D7,U+2013,U+2014,U+2018,U+2019,U+201C,U+201D,U+2026,U+2191-2193,U+2264,U+2265" \
        --layout-features="kern,liga,tnum,lnum" --flavor=woff2 --output-file=<fonts_dir>/<font>.woff2
"""

import base64
import io
import json
import random
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "media"
APP = "https://app2732006--reefcase-api-api.us-east.modal.run"
SURVEY = "srv_01M670XD9XBCSC7X9Z0DG60202"
OTHER_RGB = (68, 79, 87)
LIVE_RGB, BLEACHED_RGB = (75, 195, 159), (236, 232, 217)

WATER = ("#0b1823", "#07111a", "#03070b")
BONE, SUB, AMBER, TAPE = "#ede4cf", "#93a8b8", "#f2a541", "#d8b25c"
EASE = ".16 1 .3 1"
LINEAR = "0 0 1 1"


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def fetch(cache: Path, name: str, path: str) -> Path:
    target = cache / name
    if not target.exists():
        with urllib.request.urlopen(APP + path, timeout=180) as resp:
            target.write_bytes(resp.read())
    return target


def jpeg(path: Path, width: int, quality: int = 80) -> str:
    img = Image.open(path).convert("RGB")
    img = img.resize((width, round(width * img.height / img.width)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + b64(buf.getvalue())


def overlay(mask_path: Path, width: int, fill: int = 90) -> str:
    """Return the mask as a PNG data URI: "other" transparent, classes as a light wash with solid outlines."""
    mask = Image.open(mask_path).convert("RGB")
    mask = mask.resize((width, round(width * mask.height / mask.width)), Image.Resampling.NEAREST)
    edge = Image.new("L", mask.size, 0)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        diff = ImageChops.difference(mask, ImageChops.offset(mask, dx, dy)).convert("L")
        edge = ImageChops.lighter(edge, diff.point(lambda v: 255 if v else 0))
    rgba = Image.new("RGBA", mask.size)
    rgba.putdata(
        [
            (r, g, b, 0 if (r, g, b) == OTHER_RGB else 255 if e else fill)
            for (r, g, b), e in zip(mask.get_flattened_data(), edge.get_flattened_data())
        ]
    )
    buf = io.BytesIO()
    rgba.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + b64(buf.getvalue())


def fonts_css(fonts: Path, faces: list[tuple[str, int, str, str]]) -> str:
    return "".join(
        f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:{style};"
        f"src:url(data:font/woff2;base64,{b64((fonts / file).read_bytes())}) format('woff2')}}"
        for family, weight, style, file in faces
    )


def kf(attr: str, frames: list[tuple], dur: float, tag: str = "animate", extra: str = "") -> str:
    """One looping SMIL animation from (seconds, value[, spline into this key]) keyframes."""
    if frames[0][0] > 0:
        frames = [(0, frames[0][1]), *frames]
    if frames[-1][0] < dur:
        frames = [*frames, (dur, frames[-1][1])]
    values = ";".join(str(f[1]) for f in frames)
    times = ";".join(f"{f[0] / dur:.4f}" for f in frames)
    splines = ";".join(f[2] if len(f) > 2 else EASE for f in frames[1:])
    return (
        f'<{tag} attributeName="{attr}"{extra} values="{values}" keyTimes="{times}" calcMode="spline" '
        f'keySplines="{splines}" dur="{dur}s" repeatCount="indefinite"/>'
    )


def fade_in(at: float, dur: float, out: float, length: float = 0.6) -> str:
    return kf("opacity", [(at, 0), (at + length, 1), (out, 1, LINEAR), (out + 0.6, 0)], dur)


def diver() -> str:
    """The diver in local coordinates, facing +x, kicking. Origin is mid-torso."""
    kick = "1.3s"

    def leg(y_hip: float, knee: tuple[float, float], ankle: tuple[float, float], phase: str) -> str:
        ax, ay = ankle
        swing = f'<animateTransform attributeName="transform" type="rotate" values="-7 -56 {y_hip};7 -56 {y_hip};-7 -56 {y_hip}" dur="{kick}" begin="{phase}" calcMode="spline" keyTimes="0;.5;1" keySplines=".45 0 .55 1;.45 0 .55 1" repeatCount="indefinite"/>'
        whip = f'<animateTransform attributeName="transform" type="rotate" values="-14 {ax} {ay};16 {ax} {ay};-14 {ax} {ay}" dur="{kick}" begin="{phase}" calcMode="spline" keyTimes="0;.5;1" keySplines=".6 0 .4 1;.6 0 .4 1" repeatCount="indefinite"/>'
        fin = f"M{ax} {ay - 5}L{ax - 50} {ay - 13}C{ax - 58} {ay - 10} {ax - 58} {ay + 8} {ax - 50} {ay + 10}L{ax} {ay + 5}Z"
        return (
            f'<g>{swing}<path d="M-56 {y_hip}L{knee[0]} {knee[1]}" stroke-width="12"/><path d="M{knee[0]} {knee[1]}L{ax} {ay}" stroke-width="9"/>'
            f'<g>{whip}<path d="{fin}" stroke="none"/></g></g>'
        )

    return f"""<g fill="#010409" stroke="#010409" stroke-linecap="round" stroke-linejoin="round">
{leg(-4, (-87, -7), (-117, -3), "-0.65s")}
{leg(5, (-87, 9), (-117, 13), "0s")}
<path d="M-64 -9C-40 -16 18 -17 40 -12C51 -9 53 9 40 13C18 17 -40 15 -64 9Z" stroke-width="1"/>
<rect x="-52" y="-29" width="80" height="17" rx="8.5" stroke="none"/>
<rect x="27" y="-27" width="9" height="10" rx="2" stroke="none"/>
<path d="M34 -22C48 -26 60 -14 62 4" fill="none" stroke-width="2.4"/>
<circle cx="57" cy="-2" r="12" stroke="none"/>
<path d="M30 4L52 17L80 14" fill="none" stroke-width="7"/>
<rect x="78" y="5" width="24" height="17" rx="3" stroke="none"/>
<rect x="101" y="8" width="7" height="11" rx="1.5" stroke="none"/>
<path d="M84 6L90 -14L106 -21M84 21L92 37L108 40" fill="none" stroke-width="3"/>
<rect x="104" y="-28" width="13" height="10" rx="2" stroke="none" transform="rotate(28 110 -23)"/>
<rect x="106" y="35" width="13" height="10" rx="2" stroke="none" transform="rotate(28 112 40)"/>
<rect x="61" y="-7" width="8" height="9" rx="2" fill="#3b4652" stroke="none"/>
</g>
<path d="M-64 -9C-40 -16 18 -17 40 -12M-52 -29H20M45 -12C51 -9 53 9 40 13" fill="none" stroke="#33495b" stroke-width="1.1" opacity=".8"/>"""


def hero(cache: Path, fonts: Path) -> str:
    frames = json.loads(fetch(cache, "frames.json", f"/api/surveys/{SURVEY}/frames").read_text())
    by_n = {i + 1: f for i, f in enumerate(frames)}
    W, H, dur = 1280, 600, 12.0
    band, tw = 340, 390
    th = round(tw * 427 / 640)
    # Four consecutive frames of the dive make the reef; Frame 15 is the one the last flash develops.
    tiles = [(11, -70), (14, 320), (15, 710), (16, 1100)]
    thumbs = {n: fetch(cache, f"t{n:02d}.jpg", f"/media/{SURVEY}/thumbs/{by_n[n]['frame']['id']}.jpg") for n, _ in tiles}
    f15 = by_n[15]
    mask15 = fetch(cache, "m15.png", f"/media/{SURVEY}/masks/{f15['frame']['id']}.png")
    cover = f15["segmentation"]["cover"]

    # The diver's path: steady fin kicks, then a hover over Frame 15 for the last shot.
    path = [(0, -400), (2.4, -40, LINEAR), (5.1, 365, LINEAR), (7.3, 718, LINEAR), (8.2, 755), (11.0, 772, LINEAR), (12.0, 790, LINEAR)]

    def x_at(t: float) -> float:
        for (t0, x0, *_), (t1, x1, *_) in zip(path, path[1:]):
            if t0 <= t <= t1:
                return x0 + (x1 - x0) * (t - t0) / (t1 - t0)
        return path[-1][1]

    move = kf("transform", [(t, f"{x} 0", *s) for t, x, *s in path], dur, "animateTransform", ' type="translate"')
    flashes = [2.4, 5.1, 8.0]
    hold_end = 11.0

    images = "".join(
        f'<image x="{x}" y="{band}" width="{tw}" height="{th}" href="{jpeg(thumbs[n], 560, 72)}"/>' for n, x in tiles
    )
    reef = f'<g id="reef">{images}</g>'
    tape_y = 452
    ticks = []
    for m in range(0, 27):
        x = 30 + m * 48
        tall = m % 5 == 0
        ticks.append(f'<path d="M{x} {tape_y - 3}v{8 if tall else 5}" stroke="{TAPE}" stroke-width="1.4"/>')
        if tall:
            ticks.append(f'<text x="{x + 4}" y="{tape_y + 19}" class="tape">{m} m</text>')
    tape = f'<g id="tape"><rect x="-10" y="{tape_y - 4}" width="{W + 20}" height="7" fill="{TAPE}" opacity=".85"/>{"".join(ticks)}</g>'

    def patch(cx: float, cy: float, rx: float, ry: float, t: float) -> str:
        return (
            f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#lit)" opacity="0">'
            + kf("opacity", [(t - 0.02, 0), (t + 0.04, 1, LINEAR), (t + 1.9, 0)], dur)
            + "</ellipse>"
        )

    light = (
        f'<g>{move}<ellipse cx="150" cy="468" rx="140" ry="62" fill="url(#lit)" opacity=".42"/></g>'
        + patch(x_at(flashes[0]) + 150, 470, 175, 115, flashes[0])
        + patch(x_at(flashes[1]) + 150, 470, 175, 115, flashes[1])
        + f'<ellipse cx="905" cy="470" rx="200" ry="140" fill="url(#litwide)" opacity="0">'
        + kf("opacity", [(flashes[2] - 0.02, 0), (flashes[2] + 0.04, 1, LINEAR), (hold_end, 1, LINEAR), (hold_end + 0.8, 0)], dur)
        + "</ellipse>"
    )
    blooms = "".join(
        f'<ellipse cx="{x_at(t) + 140}" cy="420" rx="420" ry="280" fill="url(#bloom)" opacity="0">'
        + kf("opacity", [(t - 0.02, 0), (t + 0.04, 1, LINEAR), (t + 0.5, 0)], dur)
        + "</ellipse>"
        for t in flashes
    )
    strobe_glow = (
        '<g opacity="0">'
        + kf("opacity", [p for t in flashes for p in ((t - 0.02, 0), (t + 0.03, 1, LINEAR), (t + 0.3, 0))], dur)
        + '<circle cx="117" cy="-17" r="16" fill="url(#strobe)"/><circle cx="119" cy="46" r="16" fill="url(#strobe)"/></g>'
    )
    cone = (
        '<path d="M112 -18L121 46L250 228L40 228Z" fill="url(#cone)" opacity=".5">'
        + kf("opacity", [p for t in flashes for p in ((t - 0.02, 0.5), (t + 0.03, 1, LINEAR), (t + 0.5, 0.5))], dur)
        + "</path>"
    )

    rng = random.Random(41)
    snow = []
    for _ in range(90):
        x, y = rng.uniform(0, W), rng.uniform(0, H - 40)
        dx, dy, d = rng.uniform(-24, 24), rng.uniform(-30, 10), rng.uniform(9, 19)
        snow.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rng.uniform(0.5, 1.7):.1f}" opacity="{rng.uniform(0.15, 0.55):.2f}">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;{dx:.0f} {dy:.0f};0 0" dur="{d:.1f}s" '
            f'calcMode="spline" keyTimes="0;.5;1" keySplines=".45 0 .55 1;.45 0 .55 1" repeatCount="indefinite"/></circle>'
        )

    bubbles = []
    for t in (0.9, 2.5, 4.1, 5.7, 7.3, 8.9):
        hx = x_at(t) + 60
        if hx < -20:
            continue
        for j, r in enumerate((2.6, 1.9, 1.4)):
            t0 = t + j * 0.14
            x0, wob = hx + rng.uniform(-3, 3), rng.uniform(5, 10)
            y0 = 320
            bubbles.append(
                f'<circle cx="{x0:.0f}" cy="{y0}" r="{r}" fill="none" stroke="#a9c1d1" stroke-width="1" opacity="0">'
                + kf("opacity", [(t0 - 0.02, 0), (t0 + 0.05, 0.8, LINEAR), (t0 + 1.4, 0, LINEAR)], dur)
                + kf("cy", [(t0, y0), (t0 + 1.45, y0 - 120, ".3 0 .7 1")], dur)
                + kf("cx", [(t0, f"{x0:.1f}"), (t0 + 0.5, f"{x0 + wob:.1f}", ".45 0 .55 1"), (t0 + 1.0, f"{x0 - wob / 2:.1f}", ".45 0 .55 1"), (t0 + 1.45, f"{x0 + wob / 2:.1f}", ".45 0 .55 1")], dur)
                + "</circle>"
            )

    wipe_at = flashes[2] + 0.5
    mx = 710
    callout = (
        f'<g opacity="0">{fade_in(wipe_at + 0.4, dur, hold_end)}'
        f'<path d="M1100 372H1112" stroke="{AMBER}" stroke-width="1.2"/>'
        f'<text x="1120" y="377" class="lab">FRAME 15</text>'
        f'<text x="1120" y="401" class="data">t {f15["frame"]["t_sec"]:.1f} s</text>'
        f'<rect x="1120" y="415" width="10" height="10" fill="rgb{LIVE_RGB}"/><text x="1138" y="425" class="data">live coral {cover["live_coral"]:.1%}</text>'
        f'<rect x="1120" y="439" width="10" height="10" fill="rgb{BLEACHED_RGB}"/><text x="1138" y="449" class="data">bleached {cover["bleached_coral"]:.1%}</text>'
        f'<text x="1120" y="473" class="data dim">SAM 3 mask</text></g>'
    )

    css = fonts_css(
        fonts,
        [
            ("Newsreader", 500, "normal", "newsreader-latin-500-normal.woff2"),
            ("Newsreader", 400, "italic", "newsreader-latin-400-italic.woff2"),
            ("Plex Mono", 400, "normal", "ibm-plex-mono-latin-400-normal.woff2"),
            ("Plex Mono", 500, "normal", "ibm-plex-mono-latin-500-normal.woff2"),
        ],
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">ReefCase</title>
<desc id="d">At night, a diver swims a survey transect over reef station HAW-41. Each camera strobe lights the real reef; the last frame develops into its SAM 3 segmentation, {cover["live_coral"]:.0%} live coral.</desc>
<style>{css}
.word{{font:500 124px 'Newsreader',Georgia,serif;letter-spacing:-.025em;fill:{BONE}}}
.tag{{font:italic 400 33px 'Newsreader',Georgia,serif;fill:{BONE}}}
.field{{font:400 14px 'Plex Mono',ui-monospace,monospace;letter-spacing:.02em;fill:{SUB}}}
.tape{{font:500 12px 'Plex Mono',ui-monospace,monospace;fill:{TAPE}}}
.lab{{font:500 13px 'Plex Mono',ui-monospace,monospace;letter-spacing:.08em;fill:{AMBER}}}
.data{{font:400 14px 'Plex Mono',ui-monospace,monospace;fill:{BONE}}}
.dim{{fill:{SUB}}}
</style>
<defs>
<linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{WATER[0]}"/><stop offset=".5" stop-color="{WATER[1]}"/><stop offset="1" stop-color="{WATER[2]}"/></linearGradient>
<radialGradient id="lit"><stop offset="0" stop-color="#fff"/><stop offset=".45" stop-color="#fff" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<radialGradient id="litwide"><stop offset="0" stop-color="#fff"/><stop offset=".7" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<radialGradient id="bloom"><stop offset="0" stop-color="#ffdca6" stop-opacity=".34"/><stop offset="1" stop-color="#ffdca6" stop-opacity="0"/></radialGradient>
<radialGradient id="strobe"><stop offset="0" stop-color="#fff6e6"/><stop offset=".35" stop-color="{AMBER}" stop-opacity=".9"/><stop offset="1" stop-color="{AMBER}" stop-opacity="0"/></radialGradient>
<linearGradient id="cone" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd59a" stop-opacity=".22"/><stop offset="1" stop-color="#ffd59a" stop-opacity="0"/></linearGradient>
<linearGradient id="feather" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000"/><stop offset=".22" stop-color="#fff"/></linearGradient>
<mask id="band" maskUnits="userSpaceOnUse" x="0" y="{band}" width="{W}" height="{H - band}"><rect x="0" y="{band}" width="{W}" height="{H - band}" fill="url(#feather)"/></mask>
<mask id="light" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">{light}</mask>
<clipPath id="wipe"><rect x="{mx}" y="{band}" width="0" height="{th}">{kf("width", [(wipe_at, 0), (wipe_at + 1.1, tw), (hold_end, tw, LINEAR), (hold_end + 0.8, tw)], dur)}</rect></clipPath>
</defs>
<rect width="{W}" height="{H}" fill="url(#water)"/>
<g mask="url(#band)">
{reef}
<use href="#tape"/>
<rect x="0" y="{band}" width="{W}" height="{H - band}" fill="#03070b" opacity=".92"/>
<g mask="url(#light)"><use href="#reef"/>{tape}</g>
<g clip-path="url(#wipe)" opacity="0">{kf("opacity", [(wipe_at, 1), (hold_end, 1, LINEAR), (hold_end + 0.8, 0)], dur)}
<image x="{mx}" y="{band}" width="{tw}" height="{th}" href="{overlay(mask15, tw * 2)}"/></g>
</g>
{blooms}
<g fill="#a9c1d1">{"".join(snow)}</g>
<g>{"".join(bubbles)}</g>
<g>{move}{kf("opacity", [(0, 1), (hold_end, 1, LINEAR), (hold_end + 0.7, 0), (dur - 0.05, 0, LINEAR), (dur, 1, LINEAR)], dur)}
<g transform="translate(0 318) rotate(9)">{cone}<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" dur="3.2s" calcMode="spline" keyTimes="0;.5;1" keySplines=".45 0 .55 1;.45 0 .55 1" repeatCount="indefinite"/>
{diver()}{strobe_glow}</g></g></g>
{callout}
<text x="64" y="128" class="word">ReefCase</text>
<text x="70" y="180" class="tag">Turn a diver’s reef video</text>
<text x="70" y="218" class="tag">into a cited investigation.</text>
<text x="71" y="256" class="field">HAW-41 · 20.27°N 155.86°W · dive 2024-07-06 · {len(frames)} frames</text>
</svg>
"""


def pipeline(cache: Path, fonts: Path) -> str:
    """The evidence chain: each stage of one real survey, shown as the artifact it produced."""
    frames = json.loads(fetch(cache, "frames.json", f"/api/surveys/{SURVEY}/frames").read_text())
    inv = json.loads(fetch(cache, "investigation.json", f"/api/surveys/{SURVEY}/investigation").read_text())
    tool_ids = {e["id"] for f in inv["findings"] for e in f["evidence"] if e["kind"] == "tool_result"}
    tools = {}
    for tid in sorted(tool_ids):
        result = json.loads(fetch(cache, f"{tid}.json", f"/api/tool-results/{tid}").read_text())
        tools[result["tool"]] = result
    f06 = frames[5]
    seg, asm = f06["segmentation"], f06["assessment"]
    mask06 = fetch(cache, "m06.png", f"/media/{SURVEY}/masks/{f06['frame']['id']}.png")
    thumbs = [fetch(cache, f"t{i + 1:02d}.jpg", f"/media/{SURVEY}/thumbs/{f['frame']['id']}.jpg") for i, f in enumerate(frames[:12])]

    W, H, dur, hold_end = 1280, 384, 13.0, 12.1
    colw, gap, x0, top, boxh = 230, 25, 30, 30, 260
    xs = [x0 + i * (colw + gap) for i in range(5)]
    starts = [0.3 + i * 1.6 for i in range(5)]
    parts: list[str] = []

    def reveal(i: int, body: str) -> str:
        at = starts[i]
        rise = kf("transform", [(at, "0 8"), (at + 0.7, "0 0"), (hold_end, "0 0", LINEAR), (hold_end + 0.6, "0 0")], dur, "animateTransform", ' type="translate"')
        return f'<g opacity="0">{fade_in(at, dur, hold_end)}{rise}{body}</g>'

    # 1. Frames: a contact sheet of the sampled frames, filling in order.
    x = xs[0]
    tw, th, tg = 72, 48, 7
    sheet = []
    for i, path in enumerate(thumbs):
        tx, ty = x + (i % 3) * (tw + tg), top + (i // 3) * (th + tg)
        sheet.append(
            f'<image x="{tx}" y="{ty}" width="{tw}" height="{th}" preserveAspectRatio="xMidYMid slice" href="{jpeg(path, tw * 2, 72)}" opacity="0">'
            + fade_in(starts[0] + i * 0.07, dur, hold_end, 0.4)
            + "</image>"
        )
    sel_x, sel_y = x + 2 * (tw + tg), top + th + tg
    sheet.append(
        f'<rect x="{sel_x - 1.5}" y="{sel_y - 1.5}" width="{tw + 3}" height="{th + 3}" fill="none" stroke="{AMBER}" stroke-width="2" opacity="0">'
        + fade_in(starts[1] - 0.3, dur, hold_end, 0.3)
        + "</rect>"
    )
    last = frames[-1]["frame"]["t_sec"]
    sheet.append(f'<text x="{x}" y="{top + boxh - 10}" class="mono dim">{len(frames)} frames, 0–{last:.1f} s</text>')
    parts.append(reveal(0, "".join(sheet)))

    # 2. Segment: Frame 06 with its SAM 3 mask wiping on.
    x = xs[1]
    ih = round(colw / 1.5)
    wipe = starts[1] + 0.5
    cover = seg["cover"]
    bleached = cover["bleached_coral"]
    parts.append(
        reveal(
            1,
            f'<clipPath id="seg"><rect x="{x}" y="{top}" width="0" height="{ih}">{kf("width", [(wipe, 0), (wipe + 1.0, colw), (hold_end + 0.6, colw, LINEAR)], dur)}</rect></clipPath>'
            f'<image x="{x}" y="{top}" width="{colw}" height="{ih}" href="{jpeg(thumbs[5], colw * 2, 78)}"/>'
            f'<image x="{x}" y="{top}" width="{colw}" height="{ih}" clip-path="url(#seg)" href="{overlay(mask06, colw * 2, 110)}"/>'
            f'<text x="{x}" y="{top + ih + 24}" class="lab">FRAME 06</text>'
            f'<rect x="{x}" y="{top + ih + 39}" width="10" height="10" fill="rgb{LIVE_RGB}"/><text x="{x + 18}" y="{top + ih + 49}" class="mono">live coral {cover["live_coral"]:.1%}</text>'
            f'<rect x="{x}" y="{top + ih + 61}" width="10" height="10" fill="rgb{BLEACHED_RGB}"/><text x="{x + 18}" y="{top + ih + 71}" class="mono">bleached {"&lt;0.1%" if bleached < 0.001 else f"{bleached:.1%}"}</text>'
            f'<text x="{x}" y="{top + boxh - 10}" class="mono dim">SAM 3, {seg["latency_ms"] / 1000:.1f} s</text>',
        )
    )

    # 3. Assess: Muse Spark's note on the same frame, written up like a dive slate.
    x = xs[2]
    note = asm["notes"].split(" as ", 1)[1].split(".")[0]
    words, lines, line = note.split(), [], ""
    for w in words:
        if len(line) + len(w) + 1 > 21 and line:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    lines.append(line)
    lines[0] = "“" + lines[0][0].upper() + lines[0][1:]
    lines[-1] += ".”"
    form = asm["morphology"]
    fields = [("severity", str(asm["bleaching_severity"])), ("form", form[0]), *[("", m) for m in form[1:]], ("damage", ", ".join(asm["damage"]))]
    slate = [f'<rect x="{x}" y="{top}" width="{colw}" height="{boxh}" rx="6" fill="#e6e0cf"/>', f'<text x="{x + 16}" y="{top + 26}" class="lab slab">FRAME 06</text>']
    for j, text in enumerate(lines):
        slate.append(f'<text x="{x + 16}" y="{top + 60 + j * 25}" class="quote">{text}</text>')
    fy = top + 60 + len(lines) * 25 + 10
    for j, (k, v) in enumerate(fields):
        slate.append(
            f'<g opacity="0">{fade_in(starts[2] + 0.5 + j * 0.12, dur, hold_end, 0.4)}<text x="{x + 16}" y="{fy + j * 19}" class="mono ink"><tspan class="inkdim">{k:<9}</tspan>{v}</text></g>'
        )
    slate.append(f'<text x="{x + 16}" y="{top + boxh - 14}" class="small inkdim">{asm["model"].split("/")[-1]}</text>')
    parts.append(reveal(2, "".join(slate)))

    # 4. Investigate: the five tool calls, each landing with the value the agent read.
    x = xs[3]
    heat = tools["heat_stress"]["data"]["daily"]
    vessels = tools["vessel_activity"]
    hist = tools["site_history"]["data"]["surveys"]
    peak = max(hist, key=lambda s: s["cover"]["live_coral"])
    mpa = tools["mpa_boundary"]["data"]
    rows = [
        ("Heat stress, NOAA", f"max DHW {max(d['dhw'] for d in heat):g}, {len(heat)} days"),
        ("Vessels, GFW", f"{vessels['data']['fishing_hours']:g} fishing h, {vessels['params']['radius_km']:g} km"),
        ("Reef map, Allen Atlas", f"{tools['reef_map']['data']['reef_area_km2_within_1km']:.1f} km² within 1 km"),
        ("MPA, WDPA", ("inside" if mpa["inside_mpa"] else "outside") + (", no-take" if mpa["no_take"] else ", not no-take")),
        ("Site history, NCRMP", f"{peak['cover']['live_coral']:.1%} coral in {peak['dive_date'][:4]}"),
    ]
    trace = [f'<rect x="{x}" y="{top}" width="{colw}" height="{boxh}" rx="6" fill="#0c1620" stroke="#1d2c39"/>']
    for j, (label, value) in enumerate(rows):
        ry = top + 14 + j * 49
        trace.append(
            f'<g opacity="0">{fade_in(starts[3] + 0.3 + j * 0.22, dur, hold_end, 0.4)}'
            f'<text x="{x + 14}" y="{ry + 17}" class="tool">{label}</text><text x="{x + 14}" y="{ry + 38}" class="mono">{value}</text></g>'
        )
    parts.append(reveal(3, "".join(trace)))

    # 5. Report: the verdict and every hypothesis with the confidence the agent gave it.
    x = xs[4]
    verdict = ["Collapsed from 40% live", "coral in 2019 to an algae", "and sediment dominated", "state."]
    report = [f'<rect x="{x}" y="{top}" width="{colw}" height="{boxh}" rx="6" fill="#0c1620" stroke="#1d2c39"/>']
    report += [f'<text x="{x + 14}" y="{top + 30 + j * 22}" class="verdict">{t}</text>' for j, t in enumerate(verdict)]
    bw = colw - 28
    for j, h in enumerate(inv["hypotheses"]):
        hy = top + 136 + j * 24
        at = starts[4] + 0.5 + j * 0.15
        report.append(
            f'<text x="{x + 14}" y="{hy}" class="small dim">{h["cause"].replace("_", " ")}</text>'
            f'<text x="{x + colw - 14}" y="{hy}" class="small" text-anchor="end">{h["confidence"]:.0%}</text>'
            f'<rect x="{x + 14}" y="{hy + 6}" width="{bw}" height="3" fill="#1d2c39"/>'
            f'<rect x="{x + 14}" y="{hy + 6}" width="0" height="3" fill="{AMBER}">'
            + kf("width", [(at, 0), (at + 0.9, round(bw * h["confidence"], 1)), (hold_end, round(bw * h["confidence"], 1), LINEAR), (hold_end + 0.6, 0)], dur)
            + "</rect>"
        )
    parts.append(reveal(4, "".join(report)))

    names = [
        ("Frames", "Sampled from the clip"),
        ("Segment", "SAM 3, or ReefStudent"),
        ("Assess", "Muse Spark Open, per frame"),
        ("Investigate", "An agent with five tools"),
        ("Report", "Every claim cited"),
    ]
    for i, (name, sub) in enumerate(names):
        at = starts[i]
        parts.append(
            f'<g opacity=".38">{kf("opacity", [(at, 0.38), (at + 0.5, 1), (hold_end, 1, LINEAR), (hold_end + 0.6, 0.38)], dur)}'
            f'<text x="{xs[i]}" y="{top + boxh + 40}" class="name">{name}</text>'
            f'<text x="{xs[i]}" y="{top + boxh + 66}" class="sub">{sub}</text></g>'
        )

    css = fonts_css(
        fonts,
        [
            ("Newsreader", 400, "normal", "newsreader-latin-400-normal.woff2"),
            ("Newsreader", 500, "normal", "newsreader-latin-500-normal.woff2"),
            ("Newsreader", 400, "italic", "newsreader-latin-400-italic.woff2"),
            ("Plex Mono", 400, "normal", "ibm-plex-mono-latin-400-normal.woff2"),
            ("Plex Mono", 500, "normal", "ibm-plex-mono-latin-500-normal.woff2"),
        ],
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
<title id="t">One real survey, stage by stage: 24 frames sampled from the clip; Frame 06 segmented by SAM 3; Muse Spark Open's note on it; five tool calls (heat stress, vessels, reef map, MPA, site history); the verdict with confidence for each hypothesis.</title>
<style>{css}
.name{{font:500 25px 'Newsreader',Georgia,serif;fill:{BONE}}}
.sub{{font:italic 400 18px 'Newsreader',Georgia,serif;fill:{SUB}}}
.quote{{font:italic 400 20px 'Newsreader',Georgia,serif;fill:#1b232c}}
.verdict{{font:400 18px 'Newsreader',Georgia,serif;fill:{BONE}}}
.tool{{font:400 16px 'Newsreader',Georgia,serif;fill:{SUB}}}
.mono{{font:400 14px 'Plex Mono',ui-monospace,monospace;fill:{BONE};white-space:pre}}
.small{{font:400 12.5px 'Plex Mono',ui-monospace,monospace;fill:{BONE}}}
.lab{{font:500 12.5px 'Plex Mono',ui-monospace,monospace;letter-spacing:.08em;fill:{AMBER}}}
.slab{{fill:#8a5a12}}
.ink{{fill:#1b232c}}
.inkdim{{fill:#5d6670}}
.dim{{fill:{SUB}}}
</style>
<rect width="{W}" height="{H}" rx="10" fill="{WATER[1]}"/>
{"".join(parts)}
</svg>
"""


def main() -> None:
    cache, fonts = Path(sys.argv[1]), Path(sys.argv[2])
    cache.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hero.svg").write_text(hero(cache, fonts), encoding="utf-8")
    (OUT / "pipeline.svg").write_text(pipeline(cache, fonts), encoding="utf-8")


if __name__ == "__main__":
    main()
