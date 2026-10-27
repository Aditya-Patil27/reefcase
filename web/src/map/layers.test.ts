import { describe, expect, it } from "vitest";
import {
  getTrendColor,
  getTrendClass,
  mpaFillLayer,
  mpaLineLayer,
  reefFillLayer,
  vesselCircleLayer,
} from "./layers";

describe("map layers and styling", () => {
  it("maps site health trend to correct palette colours and CSS classes", () => {
    expect(getTrendColor("declining")).toBe("rgba(251, 108, 43, 1)");
    expect(getTrendColor("stable")).toBe("rgba(182, 169, 143, 1)");
    expect(getTrendColor("improving")).toBe("rgba(75, 195, 159, 1)");

    expect(getTrendClass("declining")).toContain("bg-heat-3");
    expect(getTrendClass("stable")).toContain("bg-reef-sand");
    expect(getTrendClass("improving")).toContain("bg-reef-live");
  });

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
    expect((vesselCircleLayer as any).paint?.["circle-color"]).toBe("rgba(220, 222, 135, 1)");
  });
});
