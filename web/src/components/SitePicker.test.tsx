import { describe, expect, it } from "vitest";
import { clampDiveSite, formatCoordinates, formatLatitude, formatLongitude } from "./SitePicker";

describe("dive site readouts", () => {
  it("writes a latitude with four decimals and its hemisphere", () => {
    expect(formatLatitude(-14.668)).toBe("14.6680° S");
    expect(formatLatitude(14.668)).toBe("14.6680° N");
    expect(formatLatitude(0)).toBe("0.0000° N");
    expect(formatLatitude(-0.5)).toBe("0.5000° S");
  });

  it("writes a longitude with four decimals and its hemisphere", () => {
    expect(formatLongitude(145.461)).toBe("145.4610° E");
    expect(formatLongitude(-72.642)).toBe("72.6420° W");
    expect(formatLongitude(0)).toBe("0.0000° E");
  });

  it("joins the pair with two spaces", () => {
    expect(formatCoordinates({ lat: -14.668, lon: 145.461 })).toBe("14.6680° S  145.4610° E");
  });

  it("clamps a pin to the globe", () => {
    expect(clampDiveSite({ lat: 91, lon: 181 })).toEqual({ lat: 90, lon: 180 });
    expect(clampDiveSite({ lat: -91, lon: -181 })).toEqual({ lat: -90, lon: -180 });
    expect(clampDiveSite({ lat: -14.668, lon: 145.461 })).toEqual({ lat: -14.668, lon: 145.461 });
  });
});
