# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

All three are first-class; no screen may serve one by failing another.

- **Recreational diver**: just surfaced with a reef clip; wants to know what their dive showed and that it counted. Uploads a clip, pins the site, sets the dive date, then watches the result arrive.
- **Marine park manager**: responsible for sites that are declining; needs to know which sites, why, and with what evidence to act. Reads site timelines and case files.
- **Hackathon judge / demo viewer**: has three minutes, often via a recorded video; must see a real agent investigate a real site and land a verdict with every claim traceable.

## Product Purpose

ReefCase turns a diver's reef clip into an evidence-backed investigation: segment every usable frame into live coral, bleached coral, algae, rubble, sand and other; compare against earlier surveys of the same site; have an agent pull heat stress, vessel activity, reef map and protected-area data for that site and window; and write a case file with findings, competing hypotheses with confidence, a verdict and recommended actions. Success: a reader can follow any claim to the frame or data record behind it.

## Positioning

Not a reef-health dashboard. ReefCase builds a *case*: every finding and hypothesis must cite a frame or tool result, uncited claims are rejected and repaired, and the reasoning is streamed live as it happens. Identity: a forensic case file built from evidence.

## Operating Context

- Demo site: NOAA NCRMP permanent station HAW-41 (Hawaii), historical surveys 2013, 2016, 2019 and a 2024 "new dive".
- Routes: reef map (`/`), upload (`/upload`), site timeline (`/sites/:id`), survey live view and case file (`/surveys/:id`), evidence drawer for frames and tool results.
- Live investigation streams over SSE: frames, masks, tool calls, findings.

## Capabilities and Constraints

- Stack fixed: React 19, TanStack Router/Query, Tailwind 4, MapLibre via react-map-gl, motion. Served from the FastAPI app on Modal.
- Segmentation classes are fixed: `live_coral`, `bleached_coral`, `algae`, `rubble`, `sand`, `other`. "Other" is often the largest share (rock, turf, unclassified) and must be presented honestly.
- Data sources are non-commercial licensed (GFW, WDPA) and need visible credits.
- Models are open-weight only: SAM 3, Muse Spark Open, Muse Glimmer; the UI states this.

## Brand Commitments

- Name: ReefCase. Team: Yours Truly.
- Must show "Built with Muse Spark Open" wherever Glimmer-Reef output appears.
- No binding visual commitments; the current look may be replaced freely.

## Evidence on Hand

- Real NOAA NCRMP survey photos for HAW-41 (92 photos) with SAM 3 masks, served at `/media/...`.
- Real NOAA Coral Reef Watch heat stress, GFW vessel activity, Allen Coral Atlas and WDPA data via the agent tools.
- No testimonials, users, accuracy benchmarks or partner logos exist; none may be invented.

## Product Principles

1. Every number points to its evidence; nothing on screen is a claim without a source.
2. Show the machine working: frames, masks and tool calls are content, not loading states.
3. Honest uncertainty: confidence, "other" share and disagreement are shown, not hidden.
4. One story per screen: what changed at this reef, and why.
