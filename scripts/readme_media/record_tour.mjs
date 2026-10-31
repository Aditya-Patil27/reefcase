// Record the README tour of the live deployment: map, site history, case file, citations and
// tool trace, with an injected cursor and captions. Writes frames/ and frames.ffconcat to the
// current directory; the two page loads are left out of the concat list.
//
//   node scripts/readme_media/record_tour.mjs
//   ffmpeg -f concat -safe 0 -i frames.ffconcat -vf "fps=30,format=yuv420p" -c:v libx264 -crf 18 tour-raw.mp4
//   ffmpeg -i tour-raw.mp4 -c:v libx264 -crf 24 -pix_fmt yuv420p -movflags +faststart -an docs/media/tour.mp4
//
// The GIFs are cuts of tour-raw.mp4 (site page, then case file from its first frame):
//   ffmpeg -ss <a> -to <b> -i tour-raw.mp4 -vf "fps=10,scale=880:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" -loop 0 docs/media/site.gif
import { chromium } from "../../web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
const B = "https://app2732006--reefcase-api-api.us-east.modal.run";
const SITE = "site_01M670B0P2BPNT53XTS43KRVEP", SRV = "srv_01M670XD9XBCSC7X9Z0DG60202";
const W = 1440, H = 900;
fs.rmSync("frames", { recursive: true, force: true }); fs.mkdirSync("frames");

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: W, height: H } });
// Warm every page once so the recording never shows a spinner.
const warm = await ctx.newPage();
for (const u of ["/", `/sites/${SITE}`, `/surveys/${SRV}`]) await warm.goto(B + u, { waitUntil: "networkidle", timeout: 120000 });
await warm.getByText("Heat stress", { exact: true }).first().click();
await warm.getByText("Source", { exact: true }).waitFor({ timeout: 120000 });
await warm.keyboard.press("Escape");
await warm.getByRole("button", { name: /Frame 06/ }).first().click();
await warm.waitForFunction(() => { const im = [...document.querySelectorAll("[role=dialog] img")]; return im.length > 0 && im.every((i) => i.complete && i.naturalWidth > 0); }, null, { timeout: 120000 });
await warm.close();

const page = await ctx.newPage();
await page.addInitScript(() => {
  const css = `
  #__cur{position:fixed;left:0;top:0;width:22px;height:22px;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);transition:none}
  #__cur svg{filter:drop-shadow(0 1px 2px rgba(6,42,51,.45))}
  .__ring{position:fixed;z-index:2147483646;pointer-events:none;width:34px;height:34px;margin:-17px 0 0 -17px;border:2px solid #0b3d4a;border-radius:50%;animation:__r .5s ease-out forwards}
  @keyframes __r{from{transform:scale(.3);opacity:.9}to{transform:scale(1.4);opacity:0}}
  #__cap{position:fixed;left:28px;bottom:28px;z-index:2147483645;pointer-events:none;background:#fff6e3;color:#062a33;font:700 17px/24px "Public Sans Variable",system-ui,sans-serif;padding:10px 16px;border-left:4px solid #0b3d4a;box-shadow:0 6px 24px rgba(6,42,51,.18);opacity:0;transform:translateY(8px);transition:opacity .35s,transform .35s;max-width:640px}
  #__cap.on{opacity:1;transform:none}
  #__cap small{display:block;font-weight:400;font-size:13px;color:#2f5a5e;letter-spacing:.02em;text-transform:uppercase}`;
  const boot = () => {
    if (document.getElementById("__cur")) return;
    const s = document.createElement("style"); s.textContent = css; document.head.appendChild(s);
    const c = document.createElement("div"); c.id = "__cur";
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2l15 8.5-6.6 1.6L8.2 18z" fill="#062a33" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
    const cap = document.createElement("div"); cap.id = "__cap"; document.body.appendChild(cap);
    const xy = JSON.parse(sessionStorage.getItem("__xy") || "[-100,-100]");
    c.style.transform = `translate(${xy[0]}px,${xy[1]}px)`;
    addEventListener("mousemove", (e) => { c.style.transform = `translate(${e.clientX - 3}px,${e.clientY - 2}px)`; sessionStorage.setItem("__xy", JSON.stringify([e.clientX - 3, e.clientY - 2])); }, true);
    addEventListener("mousedown", (e) => { const r = document.createElement("div"); r.className = "__ring"; r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px"; document.body.appendChild(r); setTimeout(() => r.remove(), 600); }, true);
  };
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", boot); else boot();
});

let mx = W / 2, my = H / 2;
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
async function moveTo(x, y, ms = 700) {
  const n = Math.max(12, Math.round(ms / 16)), sx = mx, sy = my;
  for (let i = 1; i <= n; i++) { const t = ease(i / n); await page.mouse.move(sx + (x - sx) * t, sy + (y - sy) * t); await page.waitForTimeout(16); }
  mx = x; my = y;
}
async function hoverEl(loc, ms) { await loc.scrollIntoViewIfNeeded(); const b = await loc.boundingBox(); await moveTo(b.x + b.width / 2, b.y + b.height / 2, ms); }
async function clickEl(loc, ms = 700) { await hoverEl(loc, ms); await page.waitForTimeout(180); await page.mouse.down(); await page.mouse.up(); }
async function caption(kicker, text) {
  await page.evaluate(([k, t]) => { const c = document.getElementById("__cap"); c.classList.remove("on"); setTimeout(() => { c.innerHTML = `<small>${k}</small>${t}`; c.classList.add("on"); }, 200); }, [kicker, text]);
}
async function hideCaption() { await page.evaluate(() => document.getElementById("__cap")?.classList.remove("on")); }
async function smoothScroll(dy, ms = 1200) {
  const n = Math.round(ms / 16); let done = 0;
  for (let i = 1; i <= n; i++) { const target = Math.round(dy * ease(i / n)); await page.mouse.wheel(0, target - done); done = target; await page.waitForTimeout(16); }
}

const cdp = await ctx.newCDPSession(page);
const shots = [], cuts = [], lag = []; let k = 0;
cdp.on("Page.screencastFrame", async ({ data, metadata, sessionId }) => {
  const f = `frames/${String(k++).padStart(5, "0")}.jpg`;
  fs.writeFileSync(f, Buffer.from(data, "base64")); shots.push([f, metadata.timestamp]); lag.push(Date.now() / 1000 - metadata.timestamp);
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
});

await page.goto(B + "/", { waitUntil: "networkidle", timeout: 120000 });
await page.waitForTimeout(1500);
await page.mouse.move(mx, my);
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
const t0 = Date.now();

// 1. Map
await caption("01 · Reef map", "Every monitored site, with reef extent, MPA boundaries and vessel activity");
await page.waitForTimeout(1600);
// The map popup is cut from the video: cuts[] holds [start, end] wall-clock seconds.
await hoverEl(page.getByRole("listitem").filter({ hasText: "HAW-41" }), 900);
await page.waitForTimeout(400);
cuts.push([Date.now() / 1000]);
await page.mouse.down(); await page.mouse.up();
await page.getByRole("link", { name: "Open site" }).click();
await page.waitForURL(/\/sites\//); await page.waitForLoadState("networkidle");
await page.getByText("Cover by dive").waitFor(); await page.waitForTimeout(600);
cuts.at(-1).push(Date.now() / 1000);
await page.waitForTimeout(300);

// 2. Site timeline
await caption("02 · Site history", "NOAA surveys of HAW-41 since 2013, then the new dive");
await hoverEl(page.getByText("2019", { exact: true }).first(), 900);
await page.waitForTimeout(1300);
const tiles = page.locator('section[aria-label="Evidence"] button');
await caption("03 · Evidence", "Each frame segmented into live coral, bleached, algae, rubble, sand and other");
for (const i of [5, 10, 14]) { await hoverEl(tiles.nth(i), 600); await page.waitForTimeout(700); }
await moveTo(1220, 500, 700);
await smoothScroll(2600, 1800);
await page.waitForTimeout(500);
await clickEl(page.getByRole("link", { name: "Open full case file" }), 900);
await page.waitForTimeout(60);
cuts.push([Date.now() / 1000]);
await page.waitForURL(/\/surveys\//); await page.waitForLoadState("networkidle");
await page.getByText("Case file ready").first().waitFor(); await page.waitForTimeout(500);
cuts.at(-1).push(Date.now() / 1000);
await page.waitForTimeout(400);

// 3. Case file
await caption("04 · Case file", "Muse Spark Open writes a verdict and competing hypotheses, with confidences");
await page.waitForTimeout(2200);
await moveTo(400, 600, 600);
await smoothScroll(520, 1600);
await page.waitForTimeout(1200);
await caption("05 · Citations", "Every claim cites a frame or a tool result. Open one to check it");
await clickEl(page.getByRole("button", { name: /Frame 06/ }).first(), 900);
await page.waitForFunction(() => { const im = [...document.querySelectorAll("[role=dialog] img")]; return im.length > 0 && im.every((i) => i.complete && i.naturalWidth > 0); }, null, { timeout: 120000 });
await page.waitForTimeout(2600);
await page.keyboard.press("Escape"); await page.waitForTimeout(700);
await clickEl(page.getByRole("button", { name: /Heat stress/ }).filter({ hasNotText: "2024" }).first(), 900);
await page.getByText("Source", { exact: true }).waitFor();
await page.waitForTimeout(400);
await caption("06 · Tool trace", "The raw NOAA Coral Reef Watch query and result behind the claim");
await page.waitForTimeout(2600);
await page.keyboard.press("Escape"); await page.waitForTimeout(500);
await hideCaption();
await page.waitForTimeout(900);

await cdp.send("Page.stopScreencast");
await page.waitForTimeout(300);
console.log("recorded", ((Date.now() - t0) / 1000).toFixed(1), "s,", shots.length, "frames");
// ffconcat list with the real gap between frames, minus the cut spans; the last frame holds.
const off = lag.sort((a, b) => a - b)[lag.length >> 1]; console.log("clock offset", off.toFixed(3));
for (const c of cuts) { c[0] -= off + 0.15; c[1] -= off - 0.1; }
const inCut = (t) => cuts.some(([a, b]) => t > a && t < b);
const kept = shots.filter(([, t]) => !inCut(t));
const cutAt = (t0, t1) => cuts.filter(([a, b]) => a >= t0 && b <= t1).reduce((s, [a, b]) => s + (b - a), 0);
const lines = ["ffconcat version 1.0"];
for (let i = 0; i < kept.length; i++) {
  const d = i + 1 < kept.length ? Math.max(0.001, kept[i + 1][1] - kept[i][1] - cutAt(kept[i][1], kept[i + 1][1])) : 1.0;
  lines.push(`file '${kept[i][0]}'`, `duration ${d.toFixed(4)}`);
}
lines.push(`file '${kept.at(-1)[0]}'`);
console.log("cut", cuts.map(([a, b]) => (b - a).toFixed(1) + "s").join(", "));
fs.writeFileSync("frames.ffconcat", lines.join("\n"));
await browser.close();
