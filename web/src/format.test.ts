import { describe, expect, it } from "vitest";
import { catalogueNumber, isRuledOut } from "./format";

describe("format", () => {
  describe("catalogueNumber", () => {
    it("formats catalogue number from site name, dive date, and frame index", () => {
      expect(catalogueNumber("HAW-41", "2024-07-06", 16)).toBe("RC-HAW41-2024-F16");
    });

    it("handles special characters and lengths in site name", () => {
      expect(catalogueNumber("Lizard Island #2", "2023-11-20", 3)).toBe("RC-LIZARD-2023-F03");
    });
  });

  describe("isRuledOut", () => {
    it("returns true when confidence < 0.15 and at least one contradicting ref", () => {
      expect(
        isRuledOut({
          confidence: 0.05,
          contradicting: [{ kind: "tool_result", id: "tr_01" }],
        }),
      ).toBe(true);
    });

    it("returns false when confidence < 0.15 but no contradicting refs", () => {
      expect(
        isRuledOut({
          confidence: 0.05,
          contradicting: [],
        }),
      ).toBe(false);
    });

    it("returns false when confidence >= 0.15 even with contradicting refs", () => {
      expect(
        isRuledOut({
          confidence: 0.4,
          contradicting: [{ kind: "tool_result", id: "tr_01" }],
        }),
      ).toBe(false);
    });
  });
});

