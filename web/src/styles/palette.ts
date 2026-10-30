/**
 * The data colours of theme.css as RGBA arrays, for MapLibre paint and SVG.
 * Raw colour values live only here and in theme.css (DESIGN.md).
 */
import type { components } from "../api/schema";

export type SegClass = components["schemas"]["SegClass"];
export type RGBA = readonly [number, number, number, number];

/** One per SegClass, in architecture §4.2 declaration order; matches --reef-* in theme.css. */
export const REEF_PALETTE: Record<SegClass, RGBA> = {
  live_coral: [15, 122, 108, 1],
  bleached_coral: [244, 238, 223, 1],
  algae: [125, 139, 58, 1],
  rubble: [138, 123, 110, 1],
  sand: [199, 185, 142, 1],
  other: [169, 196, 192, 1],
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
  [157, 184, 180, 1],
  [227, 193, 92, 1],
  [221, 143, 54, 1],
  [204, 90, 42, 1],
  [179, 50, 31, 1],
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

/** The deep-water shell colour, --deep in theme.css. */
export const DEEP_HEX = "#0b3d4a";
/** The light an opened frame sits under, --strobe in theme.css. */
export const STROBE_HEX = "#fff6e3";
/** Ink, --foreground in theme.css. */
export const INK_HEX = "#062a33";
/** Rules on the ground, --border in theme.css. */
export const RULE_HEX = "#b3ccc8";

export const BORDER_STRONG_HEX = DEEP_HEX;
export const STROKE_DARK_HEX = STROBE_HEX;
export const MPA_FILL_COLOR = DEEP_HEX;
export const REEF_FILL_COLOR = toRgbaString(REEF_PALETTE.live_coral, 1);
export const VESSEL_CIRCLE_COLOR = toRgbaString(VESSEL_COLOR);
