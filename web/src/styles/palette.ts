/**
 * The data colours of theme.css as RGBA arrays, for MapLibre paint and SVG.
 * Raw colour values live only here and in theme.css (Specimen Proof).
 */
import type { components } from "../api/schema";

export type SegClass = components["schemas"]["SegClass"];
export type RGBA = readonly [number, number, number, number];

/** One per SegClass, in architecture §4.2 declaration order; matches --reef-* in theme.css. */
export const REEF_PALETTE: Record<SegClass, RGBA> = {
  live_coral: [86, 184, 132, 1],
  bleached_coral: [239, 238, 230, 1],
  algae: [124, 138, 82, 1],
  rubble: [155, 142, 116, 1],
  sand: [214, 210, 192, 1],
  other: [107, 113, 110, 1],
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
  [154, 158, 150, 1],
  [227, 193, 92, 1],
  [221, 143, 54, 1],
  [204, 90, 42, 1],
  [179, 38, 30, 1],
];

/** Vessel detections. */
export const VESSEL_COLOR: RGBA = [75, 63, 143, 1];

export function toRgbaString(
  rgba: RGBA,
  overrideAlpha?: number,
): string {
  const [r, g, b, a] = rgba;
  return `rgba(${r}, ${g}, ${b}, ${overrideAlpha ?? a})`;
}

export const INK_HEX = "#0d0e0d";
export const BG_HEX = "#f7f7f5";
export const SURFACE_HEX = "#f7f7f5";
export const RULE_HEX = "#deded9";
export const STAGE_HEX = "#121413";
export const KEY_RED_HEX = "#b3261e";
export const LABEL_CREAM_HEX = "#f3efe2";
export const MUTE_HEX = "#5c5e5a";

export const BORDER_STRONG_HEX = INK_HEX;
export const STROKE_DARK_HEX = INK_HEX;
export const MPA_FILL_COLOR = INK_HEX;
export const REEF_FILL_COLOR = toRgbaString(REEF_PALETTE.live_coral, 1);
export const VESSEL_CIRCLE_COLOR = toRgbaString(VESSEL_COLOR);
