# ReefCase demo script

The 3-minute submission video. Rubric: Impact 30%, Use of Meta tooling 25%, Technical 20%,
Demo 25%. Done when three uninterrupted rehearsals come in under 3:00 (story 8.4).

## Before recording

- [ ] Final deploy is live: the API on 2 CPUs segmenting with SAM 3 on Modal, map layers served.
      `/api/health` reports `sam3_modal`. Warm the SAM 3 endpoint too, not just the API.
- [ ] The live-view speed-up label matches the re-timed run. 0:35–1:25 assumes about 200 s of
      pipeline at 4×; re-pick the factor from the 8.3 NFR1 re-time.
- [ ] Glimmer-Reef (7.6, 7.7) is served as the student assessor, or the decision is made to
      record without it. If it's skipped, drop the Glimmer line at 2:15 and give the time to the
      case file.
- [ ] Record after the last volume reseed. Survey IDs change on every reseed and old links break.
- [ ] Open `/api/health` 1–2 minutes before recording so the container is warm. It scales to zero
      after 10 minutes idle.
- [ ] Fresh browser, no dev tools, 1920×1080.

## Script

| Time | Screen | Voice-over (draft) |
|---|---|---|
| 0:00–0:20 | Reef map → HAW-41 site timeline, coral cover for 2013, 2016 and 2019 | "This is HAW-41, a NOAA monitoring station off West Hawaii. Its live coral has been falling for a decade. Is it still dying, and why?" |
| 0:20–0:35 | Upload: pick the clip, pin HAW-41, set 2024-07-06. Cut the upload wait. Caption: *clip stitched from NCRMP 2024 survey photos of HAW-41* | "A diver surfaces with a new clip. They upload it, pin the site, set the date." |
| 0:35–1:25 | Live view at a labelled 4× speed: masks arriving per frame, assessments, then tool calls landing on the map (heat stress, vessels, MPA) | "ReefCase segments every usable frame into live coral, bleaching, algae, rubble and sand, then an agent investigates: heat stress from NOAA Coral Reef Watch, vessel activity from Global Fishing Watch, the reef map and protected-area boundaries." |
| 1:25–2:15 | Case file: verdict, competing hypotheses with confidences. Click a finding: the evidence drawer opens on the exact frame or tool record | "The result is a case file, not a dashboard. Every finding cites a frame or a data record, and uncited claims are rejected and repaired before you see them." |
| 2:15–2:45 | Model slide: ReefStudent (0.683 mIoU vs SAM 3's 0.300 on the Coralscapes test split, about 8× faster); Muse Spark Open teacher → 3,366 frame assessments → Glimmer-Reef. "Built with Muse Spark Open" | "Everything is open-weight. ReefStudent, a small segmenter trained on human-labelled reef images, beats SAM 3 on the Coralscapes benchmark at about eight times the speed, and it segmented this site's decade of history. Live uploads use SAM 3, which held up better on new footage. Muse Spark Open labelled 3,366 frames to fine-tune Glimmer-Reef, a Muse Glimmer that assesses frames." |
| 2:45–3:00 | Live URL, team name, data credits | "A park manager gets a cited case in minutes instead of a field season. ReefCase, by Yours Truly." |

## Rules for the recording

- Label every speed-up on screen. Don't present a cut as real time.
- Vessels are activity patterns for conservation, never named ships or accusations.
- Show the "other" class as it is; don't hide it to make the chart cleaner.
- Credits on screen at the end: "Built with Muse Spark Open", "Powered by Global Fishing
  Watch", NOAA CRW / NCRMP, Allen Coral Atlas, WDPA (see `data/LICENSES.md`).
- Don't claim numbers the run didn't produce. Read the verdict and findings off the actual
  case file, and fill in the Glimmer-Reef numbers from `ml/results/glimmer_eval.json`.

## Rehearsals

| # | Date | Length | Notes |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
