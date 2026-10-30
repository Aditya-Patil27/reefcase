---
name: ReefCase
description: A forensic reef case file that sits in blue-green water until the reader opens the evidence.
colors:
  ground: "#e8f1ee"
  case-paper: "#f6faf8"
  raised-paper: "#fbfdfc"
  first-band: "#d3e5e1"
  deep: "#0b3d4a"
  deep-ink: "#9cc3c0"
  strobe: "#fff6e3"
  cast: "#4f8582"
  ink: "#062a33"
  text-secondary: "#2f5a5e"
  text-muted: "#3e6a6e"
  hairline: "#cfe0dc"
  rule: "#b3ccc8"
  on-deep: "#ffffff"
  success: "#0f7a6c"
  warning: "#8a5a00"
  danger: "#b3321f"
  reef-live: "#0f7a6c"
  reef-bleached: "#f4eedf"
  reef-algae: "#7d8b3a"
  reef-rubble: "#8a7b6e"
  reef-sand: "#c7b98e"
  reef-other: "#a9c4c0"
  heat-0: "#9db8b4"
  heat-1: "#e3c15c"
  heat-2: "#dd8f36"
  heat-3: "#cc5a2a"
  heat-4: "#b3321f"
  vessel: "#4b3f8f"
typography:
  hero:
    fontFamily: "Public Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "72px"
    fontWeight: 800
    lineHeight: "72px"
    letterSpacing: "-0.04em"
  site:
    fontFamily: "Public Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "56px"
    fontWeight: 800
    lineHeight: "56px"
    letterSpacing: "-0.04em"
  figure:
    fontFamily: "Public Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "36px"
    fontWeight: 700
    lineHeight: "40px"
    letterSpacing: "-0.03em"
  display:
    fontFamily: "Public Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: "34px"
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Public Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: "28px"
    letterSpacing: "-0.015em"
  ui:
    fontFamily: "Public Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: "22px"
  body:
    fontFamily: "Public Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: "22px"
    fontFeature: "tnum"
  label:
    fontFamily: "Public Sans Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "18px"
rounded:
  control: "0px"
  panel: "0px"
  surface: "0px"
spacing:
  gutter-mobile: "16px"
  gutter: "28px"
  section: "28px"
  stack: "12px"
  chip-x: "8px"
  button-x: "16px"
components:
  button-primary:
    backgroundColor: "{colors.deep}"
    textColor: "{colors.on-deep}"
    typography: "{typography.ui}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
  button-primary-hover:
    backgroundColor: "{colors.ink}"
  button-secondary:
    textColor: "{colors.ink}"
    typography: "{typography.ui}"
    rounded: "{rounded.control}"
    padding: "10.5px 16px"
  chip:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "2px 8px"
  chip-hover:
    backgroundColor: "{colors.strobe}"
  chip-alert:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.on-deep}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "2px 8px"
  shell:
    backgroundColor: "{colors.deep}"
    textColor: "{colors.on-deep}"
    height: "56px"
  frame-label:
    backgroundColor: "{colors.strobe}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    padding: "2px 6px"
  evidence-drawer:
    backgroundColor: "{colors.raised-paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "24px"
    width: "480px"
---

# Design System: ReefCase

## Overview

**Creative North Star: "Strobe"**

The app sits in blue-green water. Everything a reader has not opened yet (survey frames, masks) is seen through the water's cast; the moment a frame is hovered, focused or opened, the cast lifts, a single strobe flash fires, and the frame shows in true colour. That one gesture is the whole world: evidence is lit when you ask for it, and the light is warm against a cool sea.

Around the evidence, the page is a case file printed on pale sea-glass paper. A deep-water shell runs across the top; under it, square columns of text separated by hairline rules, never boxed into cards. Hierarchy comes from Public Sans weight and size alone: very heavy, tightly tracked numbers and verdicts, bold sentence-case labels, plain body. One colour acts (deep water). One colour alarms (red), and only when Coral Reef Watch has proven an alert.

The density is that of a working document: tabular numerals, citations as small ruled chips, and the agent's trace laid out as a numbered list. Nothing floats, nothing blurs, nothing is rounded.

**Key Characteristics:**
- Square corners on every surface, control and image (radius 0).
- Unopened evidence sits under a blue-green cast; opened evidence is lit in true colour with a strobe ring.
- One action colour (deep), one alarm colour (danger), reserved strictly.
- Rules instead of cards: hairline dividers, 3px left rules for cited claims, 1.5px outlines for chips.
- Bold sentence-case labels; no eyebrow or kicker above any heading.
- Trends and failures are said in words, not in colour.

## Colors

A cool water column (pale sea-glass grounds, a deep teal shell) with a single warm light, plus data ramps that exist only to encode reef classes and heat stress.

### Primary
- **Deep Water** (deep): the shell header, the primary button, the chip outline, the cited-claim rule, focus outlines, the selected site's left rule, and the only filled control colour. If something on screen invites a click and is filled, it is deep.
- **Strobe Light** (strobe): the light a frame is opened under. The flash over a lit frame, the outer ring of the lit-frame ring, the active nav underline, the frame-number tag on a lit tile, chip hover, text selection and the "models ok" dot. Never a background for a region.

### Secondary
- **Water Cast** (cast): the colour-blend layer over every unopened frame. It exists only inside the water-cast treatment.

### Neutral
- **Sea-Glass Ground** (ground): the page.
- **Case Paper** (case-paper): column surfaces that hold reading (site list, trace column, case-file column).
- **Raised Paper** (raised-paper): the evidence drawer, map popups, the data-credits popover, a selected or hovered site row.
- **First Depth Band** (first-band): sunken tracks: confidence-bar tracks, empty cover-chart bars, segmented-control wells.
- **Abyss Ink** (ink): all primary text, and the primary button's hover fill.
- **Kelp Ink** (text-secondary): supporting sentences, inactive rows, coordinates.
- **Silt Ink** (text-muted): footnotes, credits, axis ticks.
- **Hairline** (hairline) and **Rule** (rule): the two divider weights; hairline between rows, rule around tables and between columns.
- **Deep Ink** (deep-ink): secondary text and inactive nav on the deep shell only.

### Data colours
- **Reef classes** (reef-live, reef-bleached, reef-algae, reef-rubble, reef-sand, reef-other): one per segmentation class, used in cover strips, the cover chart, legends and masks. Bleached is bone white and is always drawn with a 1px inset rule outline so it never vanishes into paper. "Other" reads as water, not data.
- **Heat ramp** (heat-0 to heat-4): Coral Reef Watch stress levels 0 to 4, for heat-stress data only.
- **Vessel** (vessel): vessel detections on the map.
- **Success** (success): the "done" check on a finished tool call. **Warning** (warning): the reconnecting notice on the live trace.

### Named Rules
**The Proven Alert Rule.** Danger red (danger) appears only for a Coral Reef Watch alert that a cited heat_stress result has proven (alert level 1 or above), drawn as the alert chip under the verdict. Validation errors, run failures, stopped stages and declining trends are never red. When a vendored component paints its error state with danger, re-scope the variable locally (to deep on the pipeline stepper, to ink on the upload form) instead of letting red through.

**The One Action Rule.** Deep water is the only action colour. One filled primary button per view; every other action is the outlined secondary or a text link.

**The Water Before Light Rule.** Raw colour values live only in the theme stylesheet and the palette module that mirrors it for map paint and SVG. Components use tokens.

## Typography

**Display Font:** Public Sans Variable (with ui-sans-serif, system-ui)
**Body Font:** Public Sans Variable (with ui-sans-serif, system-ui)
**Label/Mono Font:** ui-monospace, Cascadia Mono, SF Mono, only where the vendored JSON viewer shows raw tool output

**Character:** One civic sans carries everything; contrast comes from weight (400 to 800) and tight negative tracking at the large sizes, so a verdict or a cover figure lands like a stamped finding. Numerals are tabular throughout.

### Hierarchy
- **Hero** (800, 72px/72px, -0.04em): the site's headline live-coral figure on the site timeline.
- **Site** (800, 56px/56px, -0.04em): the site name heading the timeline.
- **Figure** (700, 36px/40px, -0.03em): the key figure in a map popup.
- **Display** (700, 30px/34px, -0.02em): the verdict in a case file and the upload headings; the site name heading a live run steps up to 800.
- **Title** (700, 22px/28px, -0.015em): section headings in columns (Sites, Trace, Evidence, Cover by dive) and the wordmark (800).
- **UI** (700, 15px/22px): labels, row names, button text, small section headings (Hypotheses, Findings, Layers).
- **Body** (400, 15px/22px): running text, held to about 65ch where it is prose.
- **Label** (400 or 700, 13px/18px): chips, metadata, legends, axis ticks, credits.

### Named Rules
**The No Kicker Rule.** A heading stands alone. Section headings are bold sentence case (UI or Title) with nothing above them: no eyebrow, no uppercase tracked label, no category line.

**The Weight Not Case Rule.** Emphasis is weight. Nothing in the system is uppercased or letter-spaced open.

## Layout

The page is a deep 56px shell, then full-height columns separated by vertical rules, then a thin credits footer. Gutters are 16px on phones and 28px from 640px up; column interiors stack in 28px sections with 12px inside a section.

- **Map:** a 320px site list (case paper, right rule) beside the full-bleed map from 768px; below that the map takes the top 60% and the list the bottom 40%.
- **Site timeline:** three columns at 1280px (site facts, evidence frames, case file), two at 1024px with the case file spanning beneath, one stacked column on phones.
- **Live run / case file:** a header band with the pipeline stepper (hidden under 640px, replaced by "Stage n of 6"), then resizable frames and trace panels on desktop (62/38, 380px minimum each), stacked tabs on phones.
- **Evidence drawer:** slides in from the right, full width on phones, 480px max from 640px.

Tables and long strips scroll horizontally inside their own rules rather than squeezing.

## Elevation & Depth

Flat. Depth is a water metaphor carried by tone (ground, case paper, raised paper, first band) and by rules, not by shadows. Surfaces rest with no shadow. The only lifted things are those that genuinely float above the page: popovers, map popups, the site-picker pin.

### Shadow Vocabulary
- **Raised** (`box-shadow: 0 0 0 1px #0b3d4a1f`): a 1px deep-tinted edge, used where a vendored component asks for a raised surface.
- **Floating** (`box-shadow: 0 0 0 1px #0b3d4a29, 0 14px 32px #062a3324`): popovers and map popups only.
- **Lit ring** (`box-shadow: 0 0 0 3px var(--strobe), 0 0 0 4px var(--deep)`): a 3px strobe band edged in deep, worn by an opened frame and by a selected or focused map marker. It is a state, not elevation.

### Named Rules
**The No Frost Rule.** Nothing blurs the page. The drawer overlay is a flat 45% deep tint with backdrop-filter removed.

## Shapes

Every corner is square (radius 0 for controls, panels and surfaces). Form comes from rules: 1px hairlines between rows, a 1.5px deep outline for chips and secondary buttons, a 3px left rule for claims, a 2px strobe underline for the active nav item. Frames are 4:3 tiles clipped square; the drawer frame is 16:9. Where a vendored component hardcodes rounded corners, the build forces them square inside a scoped wrapper rather than editing the vendored source.

## Components

### Buttons
Blunt and square; the label says what happens.
- **Shape:** square (0px).
- **Primary:** deep fill, white bold UI text, 12px by 16px; hover deepens to ink. One per view.
- **Secondary:** transparent with a 1.5px deep outline, ink bold text, padding trimmed to keep the same height; hover takes the faint deep tint (#0b3d4a14).
- **Disabled:** 50% opacity, not-allowed cursor.
- **Focus:** a 2px deep outline offset 2px, everywhere.

### Chips
- **Citation chip:** a 1.5px deep outline around bold 13px ink text, 2px by 8px; a frame citation carries a small reef-class swatch. Hover lights it with strobe. Chips name the evidence a claim rests on (tool results, frames) and open it in the drawer.
- **Alert chip:** danger fill and outline, white bold text. The only red on screen (see The Proven Alert Rule).
- **Status chip:** the citation chip without an action ("Case file ready", "MPA protected").

### Claims
- **Cited:** a solid 3px deep left rule, 14px inset. Findings, and the failed-run notice.
- **Pending:** the same rule dashed in silt ink with secondary text, while a claim is still being checked.
- **Hypotheses:** a bold name and tabular percentage over a deep confidence bar on a first-band track, then "Supported by" and "Weighed against" chip rows.

### Containers
- **Corner Style:** square.
- **Background:** ground or case paper by column; never a card on a card.
- **Shadow Strategy:** none at rest (see Elevation & Depth).
- **Border:** columns are divided by rule-coloured vertical lines; lists by hairlines with a rule above and below.
- **Internal Padding:** 28px column padding (16px on phones), 24px in the drawer and trace column.

### Inputs / Fields
- **Style:** the vendored form fields and switches, retinted through the theme variables; square.
- **Focus:** the 2px deep outline.
- **Error:** validation messages render in ink, not red, by re-scoping the danger variable on the upload form.

### Navigation
The deep shell holds the heavy white wordmark, then text links in deep ink; hover turns them white, the active route is white semibold over a 2px strobe underline. On phones "Upload a dive" shortens to "Upload". A model-health readout sits at the right in label size. The footer is a single hairline-topped row of muted credits with a "Data credits" popover.

### Water-cast frame (signature)
Every survey frame tile sits under a colour-blend layer of the cast with the image dimmed (brightness 0.82, contrast 0.92). On hover, focus or when lit, the cast fades out over 180ms, the image returns to true colour, and one strobe flash fires (to 70% then out over 300ms on the exit curve), skipped under reduced motion. A lit tile wears the lit ring, and its frame number moves onto a strobe tag. Each tile carries a thin cover strip and its live-coral share beneath it.

### Evidence drawer
A raised-paper panel from the right with a hairline left rule, showing the lit frame (or the tool result) and its citations. Inside it, everything is forced square and the page behind is a flat deep tint.

### Pipeline stepper and run states
The vendored stepper shows Upload, Frames, Segment, Assess, Investigate, Report; its error mark is re-scoped to deep. A failed run is a cited-rule notice: "The run stopped:" with the reason, a sentence naming the stage after which nothing ran, and the primary "Upload the clip again" button.

### Load failures
A failed fetch is said in a sentence that ends with what to do ("Sites did not load. Check the API and reload the page."), in ink, never as an empty state and never in red. An honest empty state (a site with no surveys) is a separate, worded case.

## Do's and Don'ts

### Do:
- **Do** keep every corner square (0px), including inside vendored components; force it with a scoped override if a component hardcodes a radius.
- **Do** put unopened evidence under the water cast and light only what the reader opens, with the lit ring and one strobe flash.
- **Do** use deep (#0b3d4a) as the single action colour, with one filled primary button per view.
- **Do** separate content with hairlines and rules; mark cited claims with the 3px left rule and cite them with chips.
- **Do** write headings in bold sentence case and let weight carry emphasis.
- **Do** state trends in words ("Declining", "−17.0 pp since 2019") and failures in sentences that say what did not load and what to do next.
- **Do** outline bleached coral swatches with a 1px rule wherever they appear.

### Don't:
- **Don't** use danger red for anything but a proven Coral Reef Watch alert: not validation errors, not run failures, not stopped stages, not trends.
- **Don't** colour a trend.
- **Don't** put an eyebrow, kicker or uppercase tracked label above a heading.
- **Don't** wrap content in cards or add resting shadows.
- **Don't** blur or frost the page behind an overlay.
- **Don't** show an empty state when a request failed; say it "did not load".
- **Don't** edit the vendored component kit; re-scope its CSS variables from the outside.
