import { describe, expect, it } from "vitest";
import {
  mpaFillLayer,
  mpaLineLayer,
  reefFillLayer,
  vesselCircleLayer,
} from "./layers";

describe("map layers and styling", () => {
  it("defines MPA layer with dashed outline and subtle accent fill", () => {
    expect(mpaFillLayer.type).toBe("fill");
    expect((mpaFillLayer as any).paint?.["fill-opacity"]).toBe(0.14);
    expect(mpaLineLayer.type).toBe("line");
    expect((mpaLineLayer as any).paint?.["line-dasharray"]).toEqual([2, 2]);
  });

  it("defines Reef layer with 20% opacity", () => {
    expect(reefFillLayer.type).toBe("fill");
    expect((reefFillLayer as any).paint?.["fill-opacity"]).toBe(0.2);
  });

  it("defines Vessel layer with vessel dots", () => {
    expect(vesselCircleLayer.type).toBe("circle");
    expect((vesselCircleLayer as any).paint?.["circle-color"]).toBe("rgba(75, 63, 143, 1)");
  });
});
