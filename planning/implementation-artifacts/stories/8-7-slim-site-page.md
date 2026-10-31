---
status: ready-for-dev
---

# Story 8.7: Slim site page

As a judge,
I want the site page to tell one story at a glance,
So that I'm not reading the case file twice (Demo 25%).

- Owner: D · Priority: P1 · Depends on: 6.6
- Files: `web/src/routes/sites.$id.tsx`, `web/src/routes/sites.$id.test.tsx`,
  `web/e2e/timeline.spec.ts` (if it asserts the removed sections)
- Not yours: `web/src/components/{CaseFile,FrameGrid,TracePanel}.tsx` and
  `web/src/routes/surveys.$id.tsx` (the guide changed them in lead-b-reframe; merge main first)
- Done when: `pnpm -C web run gate` is green and the live HAW-41 page shows the verdict, the top
  hypothesis and one cover view

## Why

The site page embeds the whole case file (5 hypotheses, 11 findings, 5 actions) and then offers
"Open full case file", which is the same content again on `/surveys/:id`. It also shows the
same six cover numbers three times: the "Cover by dive" bars in the left column, the "Cover over
time" chart and the Surveys table.

## Acceptance Criteria

**Given** a site whose latest footage survey has an investigation
**When** the site page renders
**Then** the right column shows only: the verdict's first sentence, the top hypothesis (cause
label and confidence) and the "Open full case file" button. No findings, no other hypotheses,
no actions.

**Given** that site page
**When** the reader looks for cover over time
**Then** it appears once: the "Cover over time" chart plus a compact Surveys table (date, live
cover, composition bar, case-file link). The left column's "Cover by dive" bars and their
legend are gone.

**Given** a site with no investigation yet
**Then** the right column keeps today's empty-state text.

## Decisions

- **No API change.** Everything comes from `/api/sites/{id}` and
  `/api/surveys/{id}/investigation`, which the page already fetches.
- **First sentence:** use `splitFirstSentence` from `web/src/format.ts` (the case file already
  does). If there is no second sentence, it returns the whole verdict.
- **Cause labels:** use `causeLabel` from `web/src/format.ts` (it shows `unknown` as "Cause
  outside our data"). Don't hard-code a second copy.
- Keep the evidence board (frames) in the middle column. Clicking a citation still opens the
  `EvidenceDrawer`.

## Tasks

1. [ ] `git merge main` in `met-wt/lead-d`.
2. [ ] Tests first: right column has the verdict's first sentence, the top hypothesis and the
   button, and no "Findings" or "Actions" heading; no "Cover by dive" heading; the empty state
   is unchanged.
3. [ ] Slim `sites.$id.tsx`.
4. [ ] `pnpm -C web run gate`.
5. [ ] Self-review against `.opencode/agents/reviewer.md`, then
   `python scripts/integrate.py 8-7-slim-site-page --status review`.
