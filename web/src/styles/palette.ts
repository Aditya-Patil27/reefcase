/**
 * The data colours of theme.css as RGBA arrays, for deck.gl and SVG.
 * Raw colour values live only here and in theme.css (docs/agents/ui.md).
 */
import type { components } from "../api/schema";

export type SegClass = components["schemas"]["SegClass"];
export type RGBA = readonly [number, number, number, number];

/** One per SegClass, in architecture §4.2 declaration order. */
export const REEF_PALETTE: Record<SegClass, RGBA> = {
  live_coral: [75, 195, 159, 1],
  bleached_coral: [236, 232, 217, 1],
  algae: [141, 129, 61, 1],
  rubble: [125, 110, 99, 1],
  sand: [182, 169, 143, 1],
  other: [68, 79, 87, 1],
};

/** The six SegClass values in architecture §4.2 order. */
export const SEG_CLASS_ORDER: readonly SegClass[] = [
  "live_coral",
  "bleached_coral",
  "algae",
  "rubble",
  "sand",
  "other",
];

/** Heat-stress levels 0–4: no stress, watch, warning, alert 1, alert 2 and above. */
export const HEAT_PALETTE: readonly RGBA[] = [
  [128, 143, 150, 1],
  [238, 208, 89, 1],
  [251, 166, 42, 1],
  [251, 108, 43, 1],
  [234, 60, 63, 1],
];

/** Vessel detections. */
export const VESSEL_COLOR: RGBA = [220, 222, 135, 1];

export function toRgbaString(
  rgba: RGBA,
  overrideAlpha?: number,
): string {
  const [r, g, b, a] = rgba;
  return `rgba(${r}, ${g}, ${b}, ${overrideAlpha ?? a})`;
}

export const BORDER_STRONG_HEX = "#5a6578";
export const STROKE_DARK_HEX = "#18181b";
export const MPA_FILL_COLOR = "rgba(75, 195, 159, 1)";
export const REEF_FILL_COLOR = toRgbaString(REEF_PALETTE.live_coral, 1);
export const VESSEL_CIRCLE_COLOR = toRgbaString(VESSEL_COLOR);
const heat3 = HEAT_PALETTE[3]!;
export const TREND_DECLINING_COLOR = toRgbaString(heat3);
export const TREND_STABLE_COLOR = toRgbaString(REEF_PALETTE.sand);
export const TREND_IMPROVING_COLOR = toRgbaString(REEF_PALETTE.live_coral);
