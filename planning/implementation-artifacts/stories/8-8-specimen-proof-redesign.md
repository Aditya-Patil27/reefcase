---
status: in-progress
---

# Story 8.8: Specimen Proof redesign

As a judge,
I want ReefCase to look like a reef scientist's specimen collection, not a dashboard of boxes,
So that the demo reads as a crafted instrument and the evidence carries the screen (Demo 25%).

- Owner: D · Priority: P1 · Depends on: 8-6, 8-7 (merge main first)
- Files: everything under `web/src/` except `components/arc/**` (vendored, never edited),
  `web/src/api/schema.d.ts` (generated) and `web/src/routeTree.gen.ts` (generated);
  `web/package.json` + `pnpm-lock.yaml` (fonts only); `web/e2e/*.spec.ts` only where a spec
  asserts the old look (see Decisions)
- Not yours: `web/DESIGN.md` and `web/.impeccable/**` (the guide records the new design system
  at review), `docs/agents/**`, the API, `src/reefcase/**`
- Reference sketch: `8-8-reference.html` next to this file, a static 1440×900 sketch of
  `/surveys/$id` with a finished report. It shows the world; it is not pixel law. It loads
  Google Fonts for convenience; the app must not (ui_check bans it).
- Done when: `CI=1 pnpm -C web run gate` is green, every existing route, query, SSE behaviour and
  test still works, and `/surveys/$id`, `/`, `/sites/$id` and `/upload` all render in the new
  world at 1440 and 390 with no horizontal scroll

## Why

The current UI is the Strobe world: a teal-tinted ground, Public Sans everywhere, chips with
1.5px borders, and every section a ruled box of the same weight. Users said it reads as AI-made:
three equal columns, a 24-tile grid where no frame matters more than another, and a case file that
stacks cards. The data is strong (24 graded frames, a cited verdict, struck-out hypotheses, a tool
trace). The redesign makes the layout show that, and changes nothing about what the app does.

## Direction contract

This is the whole design brief. Every visual decision answers to it.

- **Thesis.** Each frame is a catalogued specimen and the verdict is a proof set beside its
  evidence. Refuses the 24-tile grid, the card stack and the three equal columns.
- **Own world.** Near-white ground (`#f7f7f5`), one neutral ink scale, 1px rules, no cards, no
  radius, no shadows. One velvet-black stage (`#121413`) holds imagery. Label red (`#b3261e`) is
  only for citation keys and the selected frame. Hanken Grotesk for UI and headlines; IBM Plex
  Mono for catalogue numbers, keys, tool names and numbers in tables. A typed cream specimen label
  (`#f3efe2`) sits on the stage.
- **Story.** The visitor watches frames get accessioned and graded, reads a one-sentence verdict,
  sees the ruled-out hypotheses struck through rather than hidden, and clicks a red key to put
  that frame or tool result on the stage.
- **First viewport (`/surveys/$id`, 1440 wide).** Left 820px: six numbered pipeline steps as a
  ruled row, then the stage with one large frame, its catalogue label, the live-coral figure at
  60px and the six-class cover list, then a 24-frame tray with live % under each. Right: eyebrow,
  verdict headline at about 36px with the key number in red, lede, hypotheses on a fixed size ramp
  (top at 46px), struck ruled-out rows, then the tool trace T01–T05.
- **Signature interaction.** Clicking any citation key or tray frame moves that specimen onto the
  stage in place, without navigating. During the live run each new frame lands in the tray and
  takes the stage.
- **Avoid.** Dark neon "AI" looks, generic SaaS dashboards (sidebar + KPI cards + grid), anything
  too artsy to read. No gradients, glows, blur, rounded cards, emoji, or decorative motion.

## Acceptance Criteria

**Given** the tokens
**Then** `web/src/styles/theme.css` defines the new world: ground `#f7f7f5`, ink `#0d0e0d`, mute
`#5c5e5a` (4.5:1 or better on the ground), rule `#deded9`, stage `#121413`, stage text and stage
mute (4.5:1 or better on the stage), label cream `#f3efe2`, key red `#b3261e`, and the six reef
cover colours. Radius tokens are 0 and shadow tokens are none (the drawer may keep one hairline
edge). The type scale gains the sizes the layout needs (figure 60, verdict 36, hypothesis ramp)
as `@theme` tokens, never `text-[NNpx]`. `palette.ts` matches. Public Sans is removed;
`@fontsource-variable/hanken-grotesk` and `@fontsource/ibm-plex-mono` (400, 500, 600) are added.

**Given** the shell on any route
**Then** it is a 56px near-white bar with a 1px bottom rule: wordmark `ReefCase`, a mono crumb
for the current context (on a survey: site name · dive date · frame count; elsewhere omitted),
and the nav `Map`, `Upload a dive` on the right, the active one marked by a 1px ink underline. The
health readout stays (mono text, the dot becomes a 6px square). The footer keeps `Data credits`
and the model credit as one ruled line of mute text.

**Given** `/surveys/$id` with a finished report at ≥1280
**Then** the first viewport matches the contract's first viewport: steps row, velvet stage with
the frame, its specimen label and side panel, the tray, and on the right the case file in proof
order (eyebrow, verdict headline, lede, hypotheses, trace). `Findings`, `Actions` and `Ask this
case` follow below the trace in the right column, as ruled lists with the same headings as today.

**Given** the stage showing a frame
**Then** the frame image fills the left of the stage at its own aspect ratio (no crop of the
evidence) with the `Frame | Mask | Both` control, the specimen label sits on its bottom-left
corner, and the side panel shows `Live coral, this frame` at 60px, a context line (`highest of
24 · survey mean 5.3%` style, computed from the frames' covers and the survey cover), the six-class
cover list (swatch, class, mono %), and the frame's assessment (morphology, severity, damage,
notes) in stage text.

**Given** the specimen label
**Then** it reads, in mono on cream: catalogue number `RC-{SITE}-{YEAR}-F{nn}` (bold, the frame
number in red), then lat/lon and dive date, then morphology and bleaching severity from the
assessment, then `det. {segmentation backend} / {assessment model}`. Each line is omitted when its
data is missing; never invent a value.

**Given** the tray
**Then** all frames of the survey sit in one row of equal tiles (thumbnails in true colour, no
cast overlay) with the live % under each in mono. The frame on the stage has a 2px red outline
and its number in red. Frames the investigation cites get a 2px ink tick above the tile. Tiles are
buttons named like today's (`Open evidence: Frame 06`), and arrow keys move along the tray.

**Given** any citation key (`F09`, `T01`) in the verdict, lede, hypotheses, findings or answer
**Then** it is a red mono button (the evidence label stays its accessible name). A frame key puts
that frame on the stage. A tool key puts that tool result on the stage: source, retrieved date,
the heat-stress chart or radar counts, `Parameters` and `Result data`, the same content the
drawer shows today, in stage text. Nothing navigates and focus moves to the stage heading. A
`Back to frame` control returns to the last frame.

**Given** the hypotheses
**Then** they are a ruled list on a fixed size ramp by rank: the top confidence number at 46px,
the second at 30px, the rest at 20px, numbers in Hanken Grotesk tabular figures. A hypothesis that
`isRuledOut` (new in `format.ts`: confidence below 0.15 and at least one contradicting ref) sits at
the bottom and is shown as `ruled out` in place of its number: its label struck through in mute,
its rationale and keys not struck. `Supported by` and
`Weighed against` keys remain available on each row.

**Given** the live run (SSE still streaming)
**Then** the steps row marks done steps with an ink rule, the running step with a 2px red rule and
the existing shimmer (honouring reduced motion), and pending steps in mute. Before frames exist the
stage is empty velvet with `Waiting for frames` in stage mute. Each `frame_scored` frame lands in
the tray and takes the stage unless the reader has picked a frame. Until `reportReady` the right
column shows the trace and the findings as they arrive; the verdict headline appears when the
report is ready. Failure keeps today's `The run stopped: …` text.

**Given** `/sites/$id`
**Then** it uses the same world: site name large at the top left, the key figures line in mono,
the latest frame on a velvet stage with its label and the tray of the latest dive, then the case
file summary from 8-7 on the right (verdict first sentence as the headline, top hypothesis on the
ramp, `Open full case file`). `Cover over time` and the `Surveys` table sit below with 1px rules
and mono numbers. Keys open the existing `EvidenceDrawer` here (there is no case-file stage).

**Given** `/`
**Then** the map fills the area under the shell. The basemap stays CARTO Positron, which already
fits the near-white world. Sites are square ink pins sized by live cover; the selected one gets the
red outline. The side panel is a ruled list (name, mono `{n}% live`, trend as a signed mono
number, cover strip), no cards. The popup is a cream specimen label with the name, the live figure
and `Open site`.

**Given** `/upload`
**Then** it is one ruled column (max 720px): numbered sections `01 Clip`, `02 Site`, `03 Dive`,
mono labels for sizes and coordinates, the dropzone a 1px dashed ink rule (no fill, no radius),
the primary button solid ink with white text. Errors and focus behaviour are unchanged.

**Given** 390px wide
**Then** every route has no horizontal scroll. On `/surveys/$id` the stage goes full width with the
side panel under the frame, the tray scrolls sideways inside its own row, and the case file stacks
under the tray. Tap targets are at least 44px.

**Given** the whole app
**Then** `python ../scripts/agents/ui_check.py` prints `clean`, axe reports no serious or critical
violations, every interactive element shows a visible 2px ink focus ring (red on the stage keys is
the button colour, not the ring), and nothing animates except the running-step shimmer and a 150ms
stage swap that is skipped under reduced motion.

## Decisions

- **Same features.** No route, query key, API call, SSE event handling, reducer logic or copy of
  record changes. `useEventStream` and `src/live/reducer.ts` keep their behaviour; you may add
  derived selectors.
- **Tests.** Every existing test keeps asserting the same behaviour and data. You may change a test
  only where it asserts the old look (a class name, Strobe-only markup). One planned change:
  `e2e/casefile.spec.ts` currently expects a frame chip on `/surveys/$id` to open the drawer. Update
  it to expect the stage to show that frame (the `Both` control and the catalogue number) instead.
  Keep the drawer test, and add one e2e step that clicks a tool key and sees its source on the stage.
- **One evidence body, two hosts.** Split the content of `EvidenceDrawer` into an `EvidenceBody`
  (frame or tool result) that the drawer and the new stage both render, so the two never drift.
  The drawer stays for `/sites/$id` and the map; the stage is the surveys page's host.
- **Stage state.** The selected evidence lives in the surveys route as `{kind, id}` (the same
  `EvidenceRef` shape). Do not put it in the URL; this story adds no search params.
- **Catalogue number.** Add `catalogueNumber(siteName, diveDate, frameIndex)` to `format.ts`:
  site name with non-alphanumerics removed, upper-cased, first 6 characters; the dive year; `F`
  plus the frame index padded to 2. Unit-test it (`HAW-41`, 2024-07-06, 16 → `RC-HAW41-2024-F16`).
- **Rename the marks file.** `components/strobe.ts` becomes `components/marks.ts` with the new
  world's class strings (`KEY`, `RULE`, `BUTTON_PRIMARY`, `BUTTON_SECONDARY`, `TEXT_LINK`,
  `SECTION_HEADING`, `EYEBROW`, `STAGE_SELECTED`). Delete the Strobe ones and the `.water-cast`
  treatment. Nothing keeps a Strobe name.
- **Arc components.** Keep the vendored ones; theme them through tokens only. Drop `stepper` from
  the surveys page if the ruled steps row is simpler to build by hand.
- **No new imagery.** Frames come from the API as today. Don't add stock photos, illustrations or
  generated images.
- **Copy.** Sentence case everywhere except the mono eyebrow and steps row, which are uppercase
  mono with letter spacing (the one place that costume is allowed). `ruled out` replaces
  `contradicted` as the visible label; the data value doesn't change.
- **Supersedes** the Strobe direction in `docs/agents/ui.md` and `web/DESIGN.md`. Where they
  disagree with this story, this story wins. The guide rewrites both after review.

## Tasks

1. [x] `git merge main` in `met-wt/lead-d`.
2. [x] Fonts and tokens: `theme.css`, `palette.ts`, `marks.ts`; remove Public Sans and Strobe.
3. [x] Tests first for the new behaviour: `catalogueNumber`; `isRuledOut` (0.05 with a
   contradicting ref → true; 0.05 with none → false; 0.4 with one → false); tray selection puts a frame on the
   stage; a tool key puts a tool result on the stage; ruled-out hypotheses render struck with their
   note unstruck; the live run's newest frame takes the stage until the reader picks one.
4. [x] Shell and footer.
5. [x] `/surveys/$id`: steps row, stage + `EvidenceBody`, specimen label, tray, case file in proof
   order, findings / actions / ask below.
6. [x] `/sites/$id`, `/`, `/upload` in the same world.
7. [x] 390px pass on every route.
8. [x] `CI=1 pnpm -C web run gate` (make sure nothing else is serving on port 5173 first).
9. [x] Save screenshots of the four routes at 1440 and 390, plus the live run mid-stream, to
   `ops/lead-d/8-8/` as PNGs under 300 KB each, and list them in `ops/lead-d/handoff.md`.
10. [ ] Self-review against `.opencode/agents/reviewer.md`, then
    `python scripts/integrate.py 8-8-specimen-proof-redesign --status review`.
