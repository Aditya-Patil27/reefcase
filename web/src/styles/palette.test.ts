import { describe, expect, it } from "vitest";
import { HEAT_PALETTE, REEF_PALETTE, SEG_CLASS_ORDER, VESSEL_COLOR, type RGBA } from "./palette";

const swatches: RGBA[] = [...Object.values(REEF_PALETTE), ...HEAT_PALETTE, VESSEL_COLOR];

describe("palette", () => {
  it("has one colour per SegClass in architecture §4.2 order", () => {
    expect(Object.keys(REEF_PALETTE)).toEqual(SEG_CLASS_ORDER);
    expect(SEG_CLASS_ORDER).toEqual([
      "live_coral",
      "bleached_coral",
      "algae",
      "rubble",
      "sand",
      "other",
    ]);
  });

  it("has five heat levels and a vessel colour", () => {
    expect(HEAT_PALETTE).toHaveLength(5);
    expect(VESSEL_COLOR).toHaveLength(4);
  });

  it("uses integer channels from 0 to 255 and an alpha from 0 to 1", () => {
    for (const swatch of swatches) {
      expect(swatch).toHaveLength(4);
      for (const channel of swatch.slice(0, 3)) {
        expect(Number.isInteger(channel)).toBe(true);
        expect(channel).toBeGreaterThanOrEqual(0);
        expect(channel).toBeLessThanOrEqual(255);
      }
      expect(swatch[3]).toBeGreaterThanOrEqual(0);
      expect(swatch[3]).toBeLessThanOrEqual(1);
    }
  });
});
