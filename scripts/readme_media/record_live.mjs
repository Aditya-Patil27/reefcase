// Record the README tour as a real run on the live deployment: upload the HAW-41 demo clip, watch
// SAM 3 frames and agent tool calls stream in, then open citations in the finished case file. The
// pipeline wait plays at FAST× in the ffconcat list; everything the cursor does is real time.
// Writes frames/, frames.ffconcat and marks.json to the current directory.
//
//   node scripts/readme_media/record_live.mjs <clip.mp4> [--dry]
//   ffmpeg -f concat -safe 0 -i frames.ffconcat -vf "fps=30,format=yuv420p" -c:v libx264 -crf 18 tour-raw.mp4
//   ffmpeg -i tour-raw.mp4 -c:v libx264 -crf 24 -pix_fmt yuv420p -movflags +faststart -an docs/media/tour.mp4
//
// --dry fills the form and stops before "Start investigation", so nothing runs on Baseten or Modal.
// A real run adds a survey to HAW-41 on the deployment; delete it afterwards.
import { chromium } from "../../web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
import path from "node:path";
const B = "https://app2732006--reefcase-api-api.us-east.modal.run";
const W = 1440, H = 900, FAST = 6;
const clip = path.resolve(process.argv[2] ?? "");
const dry = process.argv.includes("--dry");
if (!fs.existsSync(clip)) throw new Error(`clip not found: ${clip}`);
fs.rmSync("frames", { recursive: true, force: true }); fs.mkdirSync("frames");

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: W, height: H }, locale: "en-US" });
const page = await ctx.newPage();
await page.addInitScript(({ fast }) => {
  const css = `
  #__cur{position:fixed;left:0;top:0;width:22px;height:22px;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);transition:none}
  #__cur svg{filter:drop-shadow(0 1px 2px rgba(6,42,51,.45))}
  .__ring{position:fixed;z-index:2147483646;pointer-events:none;width:34px;height:34px;margin:-17px 0 0 -17px;border:2px solid #0b3d4a;border-radius:50%;animation:__r .5s ease-out forwards}
  @keyframes __r{from{transform:scale(.3);opacity:.9}to{transform:scale(1.4);opacity:0}}
  #__cap{position:fixed;left:28px;bottom:28px;z-index:2147483645;pointer-events:none;background:#fff6e3;color:#062a33;font:700 17px/24px "Public Sans Variable",system-ui,sans-serif;padding:10px 16px;border-left:4px solid #0b3d4a;box-shadow:0 6px 24px rgba(6,42,51,.18);opacity:0;transform:translateY(8px);transition:opacity .35s,transform .35s;max-width:640px}
  #__cap.on{opacity:1;transform:none}
  #__cap small{display:block;font-weight:400;font-size:13px;color:#2f5a5e;letter-spacing:.02em;text-transform:uppercase}
  #__ff{position:fixed;right:28px;bottom:28px;z-index:2147483645;pointer-events:none;background:#062a33;color:#fff6e3;font:700 15px/20px "Public Sans Variable",system-ui,sans-serif;padding:8px 14px;opacity:0;transition:opacity .3s}
  #__ff.on{opacity:1}`;
  const boot = () => {
    if (document.getElementById("__cur")) return;
    const s = document.createElement("style"); s.textContent = css; document.head.appendChild(s);
    const c = document.createElement("div"); c.id = "__cur";
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2l15 8.5-6.6 1.6L8.2 18z" fill="#062a33" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
    const cap = document.createElement("div"); cap.id = "__cap"; document.body.appendChild(cap);
    const ff = document.createElement("div"); ff.id = "__ff"; ff.textContent = `${fast}× speed`; document.body.appendChild(ff);
    if (sessionStorage.getItem("__ffon")) ff.classList.add("on");
    const prev = sessionStorage.getItem("__cap");
    if (prev) { cap.innerHTML = prev; cap.classList.add("on"); }
    const xy = JSON.parse(sessionStorage.getItem("__xy") || "[-100,-100]");
    c.style.transform = `translate(${xy[0]}px,${xy[1]}px)`;
    addEventListener("mousemove", (e) => { c.style.transform = `translate(${e.clientX - 3}px,${e.clientY - 2}px)`; sessionStorage.setItem("__xy", JSON.stringify([e.clientX - 3, e.clientY - 2])); }, true);
    addEventListener("mousedown", (e) => { const r = document.createElement("div"); r.className = "__ring"; r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px"; document.body.appendChild(r); setTimeout(() => r.remove(), 600); }, true);
  };
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", boot); else boot();
}, { fast: FAST });

let mx = W / 2, my = H / 2;
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
async function moveTo(x, y, ms = 700) {
  const n = Math.max(12, Math.round(ms / 16)), sx = mx, sy = my;
  for (let i = 1; i <= n; i++) { const t = ease(i / n); await page.mouse.move(sx + (x - sx) * t, sy + (y - sy) * t); await page.waitForTimeout(16); }
  mx = x; my = y;
}
async function hoverEl(loc, ms) { await loc.scrollIntoViewIfNeeded(); const b = await loc.boundingBox(); await moveTo(b.x + b.width / 2, b.y + b.height / 2, ms); }
async function clickEl(loc, ms = 700) { await hoverEl(loc, ms); await page.waitForTimeout(180); await page.mouse.down(); await page.mouse.up(); }
// The caption survives the upload → survey navigation through sessionStorage.
async function caption(kicker, text) {
  await page.evaluate(([k, t]) => { const c = document.getElementById("__cap"); const html = `<small>${k}</small>${t}`; sessionStorage.setItem("__cap", html); c.classList.remove("on"); setTimeout(() => { c.innerHTML = html; c.classList.add("on"); }, 200); }, [kicker, text]);
}
async function hideCaption() { await page.evaluate(() => { sessionStorage.removeItem("__cap"); document.getElementById("__cap")?.classList.remove("on"); }); }
async function fastBadge(on) { await page.evaluate((v) => { if (v) sessionStorage.setItem("__ffon", "1"); else sessionStorage.removeItem("__ffon"); document.getElementById("__ff")?.classList.toggle("on", v); }, on); }
async function smoothScroll(dy, ms = 1200) {
  const n = Math.round(ms / 16); let done = 0;
  for (let i = 1; i <= n; i++) { const target = Math.round(dy * ease(i / n)); await page.mouse.wheel(0, target - done); done = target; await page.waitForTimeout(16); }
}

const cdp = await ctx.newCDPSession(page);
const shots = [], lag = [], marks = {}; let k = 0;
const mark = (name) => { marks[name] = Date.now() / 1000; console.log(name, ((marks[name] - (marks.start ?? marks[name]))).toFixed(1)); };
cdp.on("Page.screencastFrame", async ({ data, metadata, sessionId }) => {
  const f = `frames/${String(k++).padStart(5, "0")}.jpg`;
  fs.writeFileSync(f, Buffer.from(data, "base64")); shots.push([f, metadata.timestamp]); lag.push(Date.now() / 1000 - metadata.timestamp);
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
});

await page.goto(B + "/upload", { waitUntil: "networkidle", timeout: 120000 });
await page.getByRole("group", { name: "Dive site map" }).waitFor();
await page.waitForTimeout(1500);
await page.mouse.move(mx, my);
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 85, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
mark("start");

// 1. Upload
await caption("01 · Upload", "One dive clip, the pin where you dived and the dive date");
await page.waitForTimeout(1400);
const chooser = page.waitForEvent("filechooser");
await clickEl(page.getByText("Drop a clip here or choose one from your device"), 900);
await (await chooser).setFiles(clip);
await page.getByText(/^Length [0-9]/).waitFor();
await page.waitForTimeout(900);
await hoverEl(page.getByRole("group", { name: "Dive site map" }), 800);
await page.waitForTimeout(900);
await clickEl(page.locator("#upload-dive_date-input"), 800);
const cal = page.getByRole("dialog", { name: "Dive date calendar" });
await cal.waitFor();
await page.waitForTimeout(300);
// The calendar opens on today; step back to July 2024 a month at a time so the strip reads.
const prev = cal.getByRole("button", { name: "Previous month" });
await hoverEl(prev, 500);
const day = cal.locator('button[data-date="2024-07-06"]').first();
for (let i = 0; i < 40 && !(await day.isVisible()); i++) { await page.mouse.down(); await page.mouse.up(); await page.waitForTimeout(90); }
await page.waitForTimeout(300);
await clickEl(day, 600);
await page.waitForTimeout(400);
if (await cal.isVisible()) await page.keyboard.press("Escape");
await page.waitForTimeout(700);
const start = page.getByRole("button", { name: "Start investigation" });
if (dry) {
  await hoverEl(start, 700);
  await page.waitForTimeout(800);
  await page.screenshot({ path: "dry.png" });
  await cdp.send("Page.stopScreencast");
  console.log("dry run: stopped before submit,", shots.length, "frames");
  await browser.close();
  process.exit(0);
}
await clickEl(start, 700);
await page.waitForTimeout(800);

// 2. Live run, played at FAST×
mark("fast0");
await fastBadge(true);
await caption("02 · Upload sent", "The clip goes to the deployment and the run starts");
await page.waitForURL(/\/surveys\//, { timeout: 300000 });
mark("survey");
const tiles = page.locator('section[aria-labelledby="frames-heading"] button[aria-label^="Open "]');
await tiles.first().waitFor({ timeout: 600000 });
mark("frame1");
await caption("03 · Segment", "Each sampled frame is masked by SAM 3 as it arrives");
await moveTo(W - 120, 140, 400);
const trace = page.locator('aside[aria-labelledby="trace-heading"] button');
await trace.first().waitFor({ timeout: 600000 });
mark("tool1");
await caption("04 · Investigate", "The agent queries NOAA heat stress, vessel activity, reef map, MPA and site history");
await page.getByRole("status").getByText("Case file ready").waitFor({ timeout: 900000 });
mark("ready");
await page.waitForTimeout(600);
await fastBadge(false);
mark("fast1");

// 3. Case file, real time
await caption("05 · Case file", "A verdict, competing causes scored on their own, and what to do next");
await page.waitForTimeout(3200);
await moveTo(520, 620, 700);
await smoothScroll(560, 1800);
await page.waitForTimeout(1600);
await caption("06 · Citations", "Every claim cites a frame or a tool result. Open one to check it");
await clickEl(page.getByRole("button", { name: /^Open evidence: Frame/ }).first(), 900);
await page.waitForFunction(() => { const im = [...document.querySelectorAll("[role=dialog] img")]; return im.length > 0 && im.every((i) => i.complete && i.naturalWidth > 0); }, null, { timeout: 120000 });
await page.waitForTimeout(2800);
await page.keyboard.press("Escape"); await page.waitForTimeout(700);
const toolChip = page.getByRole("button", { name: /^Open evidence: (?!Frame)/ }).first();
await clickEl(toolChip, 900);
await page.getByText("Source", { exact: true }).waitFor({ timeout: 120000 });
await caption("07 · Tool result", "The exact query and data the agent got back, stored with the survey");
await page.waitForTimeout(3000);
await page.keyboard.press("Escape"); await page.waitForTimeout(600);
await hideCaption();
await page.waitForTimeout(1200);
mark("end");

await cdp.send("Page.stopScreencast");
await page.waitForTimeout(300);
console.log("survey", page.url());
// ffconcat list with the real gap between frames; the pipeline wait plays FAST× faster.
const off = lag.sort((a, b) => a - b)[lag.length >> 1];
const f0 = marks.fast0 - off, f1 = marks.fast1 - off;
const lines = ["ffconcat version 1.0"];
let total = 0;
for (let i = 0; i < shots.length; i++) {
  const [f, t] = shots[i];
  let d = i + 1 < shots.length ? Math.max(0.001, shots[i + 1][1] - t) : 1.0;
  if (t >= f0 && t < f1) d /= FAST;
  total += d;
  lines.push(`file '${f}'`, `duration ${d.toFixed(4)}`);
}
lines.push(`file '${shots.at(-1)[0]}'`);
fs.writeFileSync("frames.ffconcat", lines.join("\n"));
fs.writeFileSync("marks.json", JSON.stringify({ ...marks, offset: off, survey: page.url() }, null, 2));
console.log("frames", shots.length, "video length", total.toFixed(1), "s");
await browser.close();
