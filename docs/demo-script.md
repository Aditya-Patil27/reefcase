# ReefCase demo script

The 3-minute submission video. Rubric: Impact 30%, Use of Meta tooling 25%, Technical 20%,
Demo 25%. Done when three uninterrupted rehearsals come in under 3:00 (story 8.4).

## Before recording

- [ ] Final deploy is live: the API on 2 CPUs segmenting with SAM 3 on Modal, map layers served.
      `/api/health` reports `sam3_modal`. Warm the SAM 3 endpoint too, not just the API.
- [ ] The live-view speed-up label matches the re-timed run. 0:35–1:25 assumes about 200 s of
      pipeline at 4×; re-pick the factor from the 8.3 NFR1 re-time.
- [x] Decided: Muse Spark Open stays the live assessor and Glimmer-Reef (7.6, 7.7) is not served
      during the recording. Keep the Glimmer line at 2:15 as a trained model (80% agreement with
      the teacher against base Glimmer's 70%); don't show it running live.
- [ ] Record after the last volume reseed. Survey IDs change on every reseed and old links break.
- [ ] Open `/api/health` 1–2 minutes before recording so the container is warm. It scales to zero
      after 10 minutes idle.
- [ ] Fresh browser, no dev tools, 1920×1080.

## Voice-over (final cut, 2:45)

Timed to the rendered film (2:45, light redesign, Tunetank "Documentary Nature Music" bed).
Each line must start at or after its time and finish inside its window. The music plays at
full level for 0:00–0:04 and 2:37–2:45, so no voice there. Pace is about 2 words a second,
calm and documentary.

| # | Window | On screen | Line |
|---|---|---|---|
| 1 | 0:04.5–0:09.5 | Map of Hawaiʻi, pin on HAW-41, North Kohala | "This is HAW-41, a NOAA survey site off North Kohala, Hawaiʻi." |
| 2 | 0:10–0:19.5 | Live coral cover: 4.9, 8.5, 40.2 (2019), then 5 (2024 dive), "−35 pts" | "In 2019, NOAA divers measured forty percent live coral here. Our July 2024 dive reads five. What happened?" |
| 3 | 0:20.5–0:35.5 | Upload: clip, pin, date. Caption: footage stitched from NCRMP 2024 photos | "A diver uploads the clip, pins the site and sets the dive date. This clip is stitched from NOAA's own 2024 survey photos of HAW-41." |
| 4 | 0:37–0:48 | Segment, 6× speed badge, masks arriving per frame | "SAM 3 masks every sampled frame into live coral, bleaching, algae, rubble and sand, shown here at six times speed." |
| 5 | 0:49–0:55 | Assess, 24× speed badge | "Muse Spark Open then grades every frame for bleaching." |
| 6 | 0:56–1:05 | Investigate: tool calls land in the trace | "An agent investigates: heat stress from NOAA Coral Reef Watch, vessel activity from Global Fishing Watch, the reef map, protected areas and the site's history." |
| 7 | 1:05–1:16.5 | Case file ready (04:21): verdict, hypotheses 78 / 18 / 12 / 5% | "Four minutes later, a case file. The reef has collapsed to turf algae, with no sign of heat stress or physical damage. Each competing cause gets its own score." |
| 8 | 1:17–1:23.5 | Citations, a tool result opens | "Every claim cites a frame or a tool result. Open one to check it." |
| 9 | 1:24.5–1:29.5 | Evidence drawer: Source, Query, Result boxes | "This is the exact record the agent got back: source, query, result." |
| 10 | 1:30–1:34 | Degree heating weeks chart, big "0" | "Heat stress in the eighty-nine days before the dive: zero." |
| 11 | 1:34.5–1:39 | "Every claim cited.", ringed citations | "Claims without a citation are rejected and repaired before you see them." |
| 12 | 1:40–1:46.5 | "What to do first.": 01 Resurvey, 02 Report the shift | "Then, what to do first: resurvey, and report the shift to the sanctuary." |
| 13 | 1:47–1:53.5 | Model 01, ReefStudent masks scanning over reef photos | "Everything under the hood is open-weight. ReefStudent is a small segmenter trained on Coralscapes." |
| 14 | 1:54–1:59.5 | mIoU bars: 0.683 vs SAM 3's 0.300 | "On the Coralscapes test set it scores 0.68. SAM 3 scores 0.30." |
| 15 | 2:00–2:05.5 | Per-frame race, "≈ 8× faster" | "It's about eight times faster. It segmented this site's survey history; live uploads run SAM 3." |
| 16 | 2:06–2:12.5 | Muse Spark Open teacher line, 3,366, Glimmer-Reef, ≈ $8.59 of GPU | "Muse Spark Open labelled 3,366 frames to train Glimmer-Reef, for under nine dollars of GPU." |
| 17 | 2:13–2:19 | Waffles: 70% vs 80% exact agreement, 354 held-out frames | "It matches its teacher on eighty percent of held-out frames, up from seventy for the base model." |
| 18 | 2:20–2:24.5 | Seconds per frame, "1.9×", "Built with Muse Spark Open" | "And it runs nearly twice as fast. Built with Muse Spark Open." |
| 19 | 2:26–2:32.5 | "A cited case in minutes. Not a field season." | "For a park manager, that's a cited case in minutes. Not a field season." |
| 20 | 2:34–2:36.8 | ReefCase lockup, URL, team | "ReefCase. By Team Yours Truly." |

Say "3,366" as "three thousand, three hundred sixty-six". Hawaiʻi: ha-VAI-ee. Kohala: ko-HAH-la.

Levels: voice integrated about −16 LUFS, peaks no higher than −6 dBFS. The music bed in
0:06–2:35 already sits at about −22 LUFS (−20 from 1:47), so it needs no extra ducking under the voice.

## Rules for the recording

- Label every speed-up on screen. Don't present a cut as real time.
- Vessels are activity patterns for conservation, never named ships or accusations.
- Show the "other" class as it is; don't hide it to make the chart cleaner.
- Credits on screen at the end: "Built with Muse Spark Open", "Powered by Global Fishing
  Watch", NOAA CRW / NCRMP, Allen Coral Atlas, WDPA (see `data/LICENSES.md`).
- Don't claim numbers the run didn't produce. Read the verdict and findings off the actual
  case file, and fill in the Glimmer-Reef numbers from `ml/results/glimmer_v2_eval.json`.

## Rehearsals

| # | Date | Length | Notes |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
