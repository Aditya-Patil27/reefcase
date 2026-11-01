<img src="docs/media/hero.svg" width="100%" alt="ReefCase. A diver swims a transect at NOAA station HAW-41 at night; each camera strobe lights the real reef, and the last flash develops Frame 15 with its SAM 3 mask: 13.0% live coral, 0.2% bleached.">

<p align="center">
  <a href="https://app2732006--reefcase-api-api.us-east.modal.run"><b>Open the live app</b></a>
  &nbsp;·&nbsp;
  <a href="docs/media/tour.mp4">Watch the 52-second tour</a>
  &nbsp;·&nbsp;
  <a href="#how-it-works">How it works</a>
  &nbsp;·&nbsp;
  <a href="#two-segmenters-that-check-each-other">Evaluation</a>
</p>

<p align="center">
  Team <b>Yours Truly</b> · Meta Global AI Developer Hackathon, Oct 26–Nov 4, 2026<br>
  Built with Muse Spark Open and SAM 3. Powered by Global Fishing Watch.
</p>

<br>

A marine park manager gets a number: "coral cover down 20%". ReefCase gives them a case. Upload a
reef clip, pin the dive site and set the date. About three minutes later there is a case file that
says what happened to the reef, which causes the data supports and which it rules out, with every
claim linked to the frame or the dataset it came from.

## See it work

<table>
<tr>
<td width="50%" valign="top">
<img src="docs/media/site.gif" width="100%" alt="The reef map with HAW-41, then the site page: 5% live coral, down 35 points since 2019, cover over time since 2013, and two of the 24 frames from the 2024 dive opened with their segmentation masks.">
<p><b>The site.</b> HAW-41's NOAA survey history since 2013, and the new dive split frame by
frame into live coral, bleached coral, algae, rubble, sand and other.</p>
</td>
<td width="50%" valign="top">
<img src="docs/media/casefile.gif" width="100%" alt="The case file: verdict, hypotheses each scored on its own, a cited frame opened on the evidence stage, then the raw NOAA Coral Reef Watch tool result.">
<p><b>The case file.</b> A verdict and competing causes. Open any citation to see the frame, or
the exact query and result the agent got back from NOAA Coral Reef Watch.</p>
</td>
</tr>
</table>

<sub>Screen capture of the live deployment, not a mock-up. The 2024 "dive" is stitched from that
station's NCRMP survey photos.</sub>

## Why it matters

Reefs are bleaching faster than scientists can survey them, while millions of recreational divers
film reefs every year and the footage goes unused. Even when a decline is measured, nobody ties it
to a cause: heat stress, anchor damage and fishing inside no-take zones leave different
signatures, but the evidence sits in separate systems.

ReefCase segments every usable frame, compares the cover with earlier surveys of the site, and
sends an agent through heat stress, vessel activity, reef map and protected-area data for that
place and time. Every claim in the case file must cite a frame or a tool result. A claim without
a valid citation is rejected and repaired before anyone sees it.

## How it works

<img src="docs/media/pipeline.svg" width="100%" alt="The evidence chain from the real HAW-41 run. Frames: 24 sampled from the clip. Segment: Frame 06 masked by SAM 3, 7.0% live coral. Assess: Muse Spark Open notes most colonies appear pale white. Investigate: five tools, from NOAA heat stress to the NCRMP site history of 40.2% coral in 2019. Report: a verdict with five ranked hypotheses.">

Each stage streams to the browser as it runs, so the live view fills in frame by frame and tool
call by tool call. Tool results are stored with the survey, so every citation opens to the data the
agent actually saw. On the deployment, a 24-frame clip goes from upload to case file in 3 to 5 minutes.

**Stack:** Python 3.14, FastAPI, pydantic-ai and DuckDB ([src/reefcase/](src/reefcase/)) · React 19,
Vite, TanStack and MapLibre ([web/](web/)) · SAM 3 and ReefStudent on Modal ([ml/](ml/)).

## Meta models and how we use them

We use open-weight Meta models only.

| Model | Where | What it does |
|---|---|---|
| **SAM 3** (`facebook/sam3`) | Modal T4 endpoint ([ml/modal/sam_endpoint.py](ml/modal/sam_endpoint.py)) | Text-prompted segmentation of each frame into six reef classes. Also the teacher that pseudo-labelled training frames for ReefStudent. |
| **Muse Spark Open** (Baseten) | Frame assessor ([src/reefcase/llm/assess.py](src/reefcase/llm/assess.py)) | Reads each frame with its segmentation and returns a bleaching severity (0–4), growth forms, damage and notes. |
| **Muse Spark Open** | Investigator agent ([src/reefcase/agent/investigator.py](src/reefcase/agent/investigator.py)) | Calls the five data tools, weighs the evidence and writes the cited case file. |
| **Muse Spark Open** | Teacher dataset ([ml/modal/gen_assessments.py](ml/modal/gen_assessments.py)) | 3,366 frame assessments of Coralscapes images, as training data for a Muse Glimmer frame assessor. |
| **Glimmer-Reef** (LoRA on Muse Glimmer-30B) | Optional frame assessor ([ml/modal/glimmer_endpoint.py](ml/modal/glimmer_endpoint.py)) | Distilled from those assessments; agrees with Muse Spark Open's severity on 80% of held-out frames (base Glimmer 70%) and, like base Glimmer, catches 76% of bleached ones (the v1 adapter caught 46%) ([ml/results/glimmer_v2_eval.json](ml/results/glimmer_v2_eval.json)). Off by default: at about 39 s a frame on one H100 it is slower than the teacher. |

## Two segmenters that check each other

ReefStudent is a U-Net (EfficientNet-B0) we trained on Coralscapes. All models were scored on the
same held-out 392-frame test split.

| Model | Test mIoU | ms per frame (T4) |
|---|---|---|
| **ReefStudent, supervised** | **0.683** | **161** |
| ReefStudent, distilled from SAM 3 | 0.291 | 161 |
| SAM 3 (teacher) | 0.300 | 1,247 |

ReefStudent wins the benchmark at 8× the speed, but the win didn't transfer to our Hawaiian demo
site: it read 46% live coral where SAM 3 and the assessor both put it near 5%. So live uploads
segment with SAM 3. When ReefStudent is the segmenter, an optional disagreement check
(`REEFCASE_DISAGREEMENT_CHECK=true`) also runs SAM 3 on every frame: where their coral masks
overlap by less than 0.5 IoU, the case file keeps the SAM 3 mask and flags the frame as uncertain. Details are in [ml/results/MODEL_CARD.md](ml/results/MODEL_CARD.md).

## Real diver footage

The demo dive is stitched from survey photos. To test ReefCase on real video, we cut 15 clips from
12 public videos made by reef agencies, NGOs and divers. Each clip keeps only the underwater
stretch, without talking heads or title cards. They include hard cases on purpose: rubble, a diver
blocking the view, 1998 VHS footage and edited films with many cuts.

Five clips have been through the full pipeline so far. The dive dates are guesses based on each
video's upload date, and the dive positions are approximate.

| Clip | Live coral | Bleached | What the case file said |
|---|---|---|---|
| DLNR, Kāneʻohe Bay, Oʻahu, Feb 2019 | 67% | 2% | Healthy, with minor paling and no heat stress (DHW 0). The video's title says DLNR was investigating a new threat to these corals. It was most likely the Caribbean corkscrew anemone, first found in the bay a month earlier ([DLNR](https://dlnr.hawaii.gov/ais/2020/08/28/august-september-ais-team-update/)): in the clip a diver points into a crevice and takes a sample. ReefCase measures coral cover and bleaching, so it can't see a small anemone. |
| TRACC transect, Malaysia, 2014 | 12% | 0% | Sparse coral, no bleaching, DHW 0.67. It flagged 8 of 24 frames as uncertain and said the diver blocking the reef limits certainty. |
| DLNR, Molokini, Maui, autumn 2015 | 28% | 3% | Heat stress, at 0.95 confidence. Heat stress (DHW) peaked at 9.26 on 20 Oct 2015, above the severe threshold of 8. Branching corals were bleached white while massive ones kept their colour. This matches the 2015 Hawaiʻi bleaching event. |
| DLNR, Hanauma Bay, Oʻahu, late 2014 | | | Rejected: too few frames passed the blur check, so no case file was made. |
| Reef Check manta tow, Haiti, Feb 2011 | | | Rejected: too blurry, so no case file was made. |

We don't redistribute the clips. Each link below opens the source video at the clip's start. None of
the clips are US federal footage, so each owner's permission is needed before a clip is published.

<details>
<summary><b>The 15 clips</b></summary>

| Clip | Owner | Place, date | What it tests |
|---|---|---|---|
| [1:30–2:30](https://youtu.be/D-j2S26klx8?t=90), [2:30–3:30](https://youtu.be/D-j2S26klx8?t=150) | Hawaii DLNR, Division of Aquatic Resources | Oʻahu, ~Feb 2019 | Unedited snorkel pass over dense, pale coral |
| [0:18–1:18](https://youtu.be/q0PIDDzhM7w?t=18) | Hawaii DLNR | Hanauma Bay, Oʻahu, late 2014 | Rocky reef, partial bleaching, fish |
| [0:17–0:40](https://youtu.be/Dgr2hdx2kEA?t=17), [0:56–1:42](https://youtu.be/Dgr2hdx2kEA?t=56) | Hawaii DLNR, Division of Aquatic Resources | Oʻahu, Jan 2015 | Bleached patches on a reef flat |
| [0:55–1:48](https://youtu.be/E_J3IjQ7hAU?t=55) | Hawaii DLNR, Division of Aquatic Resources | Hawaiʻi, 2015–16 | Survey divers on a transect, heavy bleaching |
| [0:12–0:40](https://youtu.be/FImsdAkjBCw?t=12) | Kuleana Coral Restoration | Oʻahu, 2020 | Transect line, tagged bleached colonies |
| [1:30–2:18](https://youtu.be/CMJ_y9vy75U?t=90) | Kuleana Coral Restoration | Maunalua Bay, Oʻahu, ≤2021 | Low coral cover, mostly rubble |
| [0:06–0:45](https://youtu.be/HnCeWFl5WXY?t=6), [0:54–1:16](https://youtu.be/HnCeWFl5WXY?t=54) | TRACC | Malaysia, ≤2014 | A real line-transect survey |
| [0:25–1:40](https://youtu.be/WklM-N5WkVo?t=25) | Reef Check Foundation | Haiti, Feb 2011 | Manta tow over a sparse, overfished reef |
| [1:20–1:52](https://youtu.be/9FhnHh7U94s?t=80) | Reef Relief Founders | Cuba, 1998 | Old VHS-quality survey video |
| [0:00–0:19](https://youtu.be/XPr0K6595Zc) | petercrocker314 | Koh Ra, Thailand, ≤2009 | Diver blocking most of the reef |
| [5:24–6:12](https://youtu.be/15oIS_j7bDs?t=324) | Roundglass Sustain | Andaman and Nicobar Islands, ≤2024 | Edited documentary with many cuts |
| [1:03–1:38](https://youtu.be/e93NGHwbWjw?t=63) | ReefWatch Marine Conservation | India, mixed locations, ≤2016 | Edited film with many cuts |

Places and dates come from each video's title, description, title cards and upload date, not from
GPS. Where only the upload date is known, the date is shown as ≤ that date.

</details>

## Run it yourself

<details>
<summary><b>Running locally</b></summary>

You need [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/).

```bash
uv sync                       # add --group gpu for real SAM 3 / ReefStudent weights
pnpm -C web install
cp .env.example .env          # fill in the values you need
pnpm -C web build
REEFCASE_WEB_DIST=web/dist uv run uvicorn --factory reefcase.api.main:create_app
```

Then open http://localhost:8000. The defaults run offline with no GPU or keys
(`REEFCASE_SEGMENTER=fake`). `.env.example` lists every variable for real runs.

</details>

<details>
<summary><b>Tests</b></summary>

```bash
uv run poe gate               # ruff, format, pyright strict, import-linter, pytest
pnpm -C web run gate          # typecheck, oxlint, vitest, playwright
```

Tests run offline: HTTP calls replay from cassettes and models are replaced by fakes.

</details>

## Built during the hackathon (Oct 26–Nov 4)

The first commit (`4207fe3`) holds only planning and tooling: the PRD, architecture and story list
in [planning/planning-artifacts/](planning/planning-artifacts/), plus agent configs. It has
no application code. Everything below was built after it, story by story, as tracked in
[sprint-status.yaml](planning/implementation-artifacts/sprint-status.yaml):

- The FastAPI service and DuckDB store, with the live event stream
- The pipeline: frame sampling and quality scoring, segmentation, the Muse Spark Open frame assessor
- The investigator agent, its five data tools and the citation validator with its repair loop
- The React web app: reef map, site timeline, live view and case file with the evidence drawer
- The Telegram bot ([src/reefcase/bot/](src/reefcase/bot/))
- ReefStudent: SAM 3 pseudo-labels, training and the evaluation against human labels
- The Modal apps: the SAM 3 endpoint, the API deploy and the Glimmer-Reef endpoint
- The Muse Spark Open teacher dataset and the Glimmer-Reef LoRA fine-tune
- The NCRMP history import and the demo-clip scripts

## Data and licences

ReefCase uses data from Global Fishing Watch, NOAA Coral Reef Watch and NCRMP, the Allen Coral
Atlas, WDPA and Coralscapes. Some sources are licensed for non-commercial use only. Third-party
libraries, models and datasets are used, not modified. See [data/LICENSES.md](data/LICENSES.md)
for each source's licence and attribution.

The ReefCase code is under the [MIT licence](LICENSE). It doesn't cover the data, the models or
their weights, which keep their own licences.
