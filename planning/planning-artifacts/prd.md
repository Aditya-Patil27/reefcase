---
status: approved
date: 2026-10-26
project: ReefCase (working name)
team: Yours Truly (3 people)
event: Meta Global AI Developer Hackathon — Indie track
deadline: 2026-11-04 21:00 ET (2026-11-05 07:30 IST)
---

# ReefCase — Product Requirements Document

## 1. Problem

Coral reefs are bleaching faster than scientists can survey them. A reef survey today means a trained diver photographing a transect and a scientist hand-annotating every image for hours. Meanwhile millions of recreational divers film reefs every year and that footage is never used.

Even when decline is measured, nobody connects it to the cause. Heat stress, anchor damage and illegal fishing inside no-take zones leave different signatures, but the evidence sits in separate systems: ocean temperature products, satellite vessel detections, reef maps, and survey photos. Marine park managers get a number ("coral cover down 20%") without a case they can act on.

## 2. Product

ReefCase turns a diver's reef clip into an evidence-backed investigation:

1. **Survey** — segments every usable frame into live coral, bleached coral, algae, rubble and sand, and estimates cover.
2. **Compare** — diffs the survey against earlier surveys of the same site.
3. **Investigate** — an agent pulls ocean heat stress, satellite-detected vessel activity, reef geomorphology and protected-area boundaries for that site and time window.
4. **Conclude** — writes a case file: findings, competing hypotheses with confidence, a verdict, and recommended actions. Every claim cites the frame or data record it came from.

## 3. Users

| User | Need | Surface |
|---|---|---|
| Recreational diver (primary) | Turn a dive into a useful contribution with zero effort | Web upload, Telegram bot |
| Marine park manager | Know which sites are declining and why, with evidence to act on | Web map + case files |
| Hackathon judge | See a working, impressive, verifiable agent in 3 minutes | Web demo + video |

## 4. Hackathon fit

- **Problem statement:** Push the Frontier (models meeting the physical world) The demo site is a Hawaii NOAA NCRMP permanent station, the only licensed repeat-survey imagery found (architecture §9.5). Indian reefs (Gulf of Mannar / Lakshadweep) are a Build for Your World stretch goal if licensed footage turns up.
- **Meta models (open weights only — the Meta Model API is unavailable to the team):** SAM 3, Muse Spark Open, Muse Glimmer.
- **Bonus targets:** Best Build on Meta Open Weight Models ($10K), Best Agentic Use-Case ($5K), Most Viral ($20K).
- **Rubric:** Impact 30% · Use of Meta tooling 25% · Technical depth 20% · Demo 25%.

## 5. Functional requirements

### Survey ingest
- **FR1** A user can upload a reef video (mp4/mov, ≤ 500 MB, ≤ 5 min) with a site location (lat/lon) and dive date.
- **FR2** The system extracts candidate frames and scores each for blur, colour cast and turbidity, keeping the best N (default 24) that pass thresholds.
- **FR3** If fewer than 6 frames pass, the survey fails fast with a reason the user can understand ("too murky", "too blurry").

### Vision
- **FR4** Each kept frame is segmented into classes: `live_coral`, `bleached_coral`, `algae`, `rubble`, `sand`, `other`.
- **FR5** The system computes per-frame and per-survey percent cover for each class.
- **FR6** Segmentation runs through one interface with two interchangeable backends: SAM 3 (teacher) and the distilled ReefStudent.
- **FR7** Each frame gets a structured assessment from a vision-language model: bleaching severity (0–4), dominant coral morphology, visible damage, and notes.

### Investigation agent
- **FR8** The agent can call these tools: `heat_stress`, `vessel_activity`, `reef_map`, `mpa_boundary`, `site_history`.
- **FR9** The agent produces a typed `Investigation`: findings, hypotheses (cause, confidence, supporting and contradicting evidence), verdict, and recommended actions.
- **FR10** Every finding and hypothesis must cite at least one evidence reference (frame ID or tool-result ID). Uncited claims are rejected and the agent is asked to repair them.
- **FR11** When the teacher and student models disagree beyond a threshold on a frame, the frame is flagged `uncertain` and the teacher's result is used.

### Sites and history
- **FR12** Surveys are attached to a site (matched by distance ≤ 500 m, otherwise a new site is created).
- **FR13** A site has a timeline of surveys with cover trends.
- **FR14** Historical survey imagery from public datasets can be imported as past surveys for a site.

### Web app
- **FR15** Upload page: drop a clip, pin the site on a map, set the dive date.
- **FR16** Live investigation view: streamed agent events (frames, masks, tool calls, findings) as they happen.
- **FR17** Map view: reef sites coloured by health trend, with layers for heat stress, vessel detections and MPA boundary.
- **FR18** Case file view: the report with clickable evidence (opens the frame + mask, or the tool result).

### Telegram bot (P2)
- **FR19** A user can send a video and location to the bot and receive the case-file summary and a link to the web view.

### Distillation (P1/P2)
- **FR20** A SAM 3 pseudo-labelling pipeline produces training masks for ReefStudent on Kaggle.
- **FR21** ReefStudent is evaluated against a human-labelled coral dataset and its scores are shown in the app.
- **FR22** (P2) Muse Glimmer is LoRA fine-tuned on Muse Spark Open frame assessments to produce Glimmer-Reef, served on Modal.

## 6. Non-functional requirements

- **NFR1** End-to-end investigation of a 60 s clip completes in ≤ 3 min on the demo deployment.
- **NFR2** The first streamed event reaches the browser within 5 s of upload completing.
- **NFR3** Every model provider is configured by environment variables only; switching provider needs no code change.
- **NFR4** Tests never call live external APIs; HTTP is replayed from recorded cassettes.
- **NFR5** All Python is type-checked (pyright strict on `src/reefcase/`) and linted (ruff); CI fails on errors.
- **NFR6** All data, imagery and footage used has a licence permitting this use; licences are recorded in `data/LICENSES.md`.
- **NFR7** Secrets live only in `.env` (git-ignored); `.env.example` lists every variable.
- **NFR8** The repository is public and the README states what was built during the hackathon.

## 7. Scope tiers

| Tier | Contents | Must be done by |
|---|---|---|
| **P0** | FR1–FR10, FR12, FR15–FR18 with SAM 3 as the only segmenter, one demo site | Sat Oct 31 |
| **P1** | FR11, FR13, FR14, FR20, FR21 | Mon Nov 2 |
| **P2** | FR19, FR22, multi-site | Tue Nov 3 |
| Freeze | Demo video, README, X post, submission | Wed Nov 4 |

## 8. Out of scope

- User accounts and auth (single demo tenant).
- Species-level coral identification.
- Real-time video streaming from a dive.
- Mobile native apps.
- Enforcement actions or naming specific vessels — reports describe activity patterns only.

## 9. Success metrics

- P0 demo runs end to end, live, on an unseen clip.
- ReefStudent reaches ≥ 0.6 mIoU on the Coralscapes test split, or within 10 points of SAM 3, at ≥ 5× SAM 3's speed on the same Kaggle T4. It must also run on the 6 GB RTX 3050.
- Every finding in the demo case file has a working evidence link.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Baseten/Modal credits not granted | Provider-agnostic LLM client; Fireworks and Oxion fallbacks; ReefStudent runs locally |
| SAM 3 Hugging Face access refused | All 3 teammates request access to `facebook/sam3`; any approved account runs the Kaggle and Modal jobs |
| SAM 3 doesn't fit the 6 GB RTX 3050 | SAM 3 runs on a Kaggle T4 or Modal; the laptop runs ReefStudent, which is the distillation pitch |
| No licensed repeat-survey footage | NOAA NCRMP permanent-site photoquadrats (2013/2016/2019 history, 2024 as the "new dive"), disclosed in the README |
| Muse Spark Open lacks JSON mode on Baseten | Structured output goes through tool calls (architecture §5.2) |
| GFW and WDPA are non-commercial licences | Fine for a hackathon; every attribution sits in one data-credits panel in the app footer, and in the README; a commercial path would need permission |
| Judges read vessel tracking as surveillance | Frame as conservation; report activity patterns, never identities |
| Weak coding model drifts from design | Contracts written first; every story names exact files, interfaces and passing tests |
