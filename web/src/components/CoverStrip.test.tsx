import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { components } from "../api/schema";
import { CoverStrip } from "./CoverStrip";

type Cover = components["schemas"]["Cover"];

const cover: Cover = {
  live_coral: 0.42,
  bleached_coral: 0.12,
  algae: 0.08,
  rubble: 0.14,
  sand: 0.22,
  other: 0.02,
};

function segments(): HTMLElement[] {
  const strip = screen.getByRole("img");
  return Array.from(strip.querySelectorAll<HTMLElement>("[data-segment]"));
}

describe("CoverStrip", () => {
  it("draws one segment per SegClass in architecture §4.2 order", () => {
    render(<CoverStrip cover={cover} />);
    expect(segments().map((segment) => segment.dataset.segment)).toEqual([
      "live_coral",
      "bleached_coral",
      "algae",
      "rubble",
      "sand",
      "other",
    ]);
  });

  it("gives each segment a width equal to its fraction", () => {
    render(<CoverStrip cover={cover} />);
    expect(segments().map((segment) => segment.style.width)).toEqual([
      "42%",
      "12%",
      "8%",
      "14%",
      "22%",
      "2%",
    ]);
  });

  it("rounds half percentages to one decimal place", () => {
    render(<CoverStrip cover={{ ...cover, algae: 0.125, sand: 0.115 }} />);
    const widths = segments().map((segment) => segment.style.width);
    expect(widths[2]).toBe("12.5%");
    expect(widths[4]).toBe("11.5%");
  });

  it("labels every percentage for assistive technology", () => {
    render(<CoverStrip cover={cover} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Live coral 42%, bleached coral 12%, algae 8%, rubble 14%, sand 22%, other 2%",
    );
  });

  it("keeps a segment for a class with zero cover", () => {
    render(<CoverStrip cover={{ ...cover, algae: 0 }} />);
    const algae = segments().find((segment) => segment.dataset.segment === "algae");
    expect(segments()).toHaveLength(6);
    expect(algae?.style.width).toBe("0%");
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Live coral 42%, bleached coral 12%, algae 0%, rubble 14%, sand 22%, other 2%",
    );
  });

  it("renders a partial cover without crashing", () => {
    render(<CoverStrip cover={{ live_coral: 0.5 } as Cover} />);
    expect(segments()).toHaveLength(6);
    expect(segments()[0]?.style.width).toBe("50%");
    expect(segments()[1]?.style.width).toBe("0%");
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Live coral 50%, bleached coral 0%, algae 0%, rubble 0%, sand 0%, other 0%",
    );
  });

  it("takes an optional className", () => {
    render(<CoverStrip cover={cover} className="my-hairline" />);
    expect(screen.getByRole("img")).toHaveClass("my-hairline");
  });
});
