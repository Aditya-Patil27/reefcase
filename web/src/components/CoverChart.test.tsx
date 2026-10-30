import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { CoverChart } from "./CoverChart";
import type { components } from "../api/schema";

vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>();
  return {
    ...actual,
    Link: ({ to, children, ...props }: any) => (
      <a href={typeof to === "string" ? to : "#"} {...props}>
        {children}
      </a>
    ),
  };
});

type Survey = components["schemas"]["Survey"];

const mockSurveys: Survey[] = [
  {
    id: "srv_01",
    site_id: "site_lizard_island",
    dive_date: "2021-11-03",
    status: "done",
    source: "historical",
    video_path: null,
    cover: {
      live_coral: 0.52,
      bleached_coral: 0.04,
      algae: 0.08,
      rubble: 0.12,
      sand: 0.22,
      other: 0.02,
    },
    failure_reason: null,
    created_at: "2021-11-03T08:00:00Z",
  },
  {
    id: "srv_02",
    site_id: "site_lizard_island",
    dive_date: "2024-03-12",
    status: "done",
    source: "historical",
    video_path: null,
    cover: {
      live_coral: 0.48,
      bleached_coral: 0.05,
      algae: 0.08,
      rubble: 0.11,
      sand: 0.26,
      other: 0.02,
    },
    failure_reason: null,
    created_at: "2024-03-12T08:00:00Z",
  },
  {
    id: "srv_03",
    site_id: "site_lizard_island",
    dive_date: "2026-10-21",
    status: "done",
    source: "upload",
    video_path: "/media/clips/lizard.mp4",
    cover: {
      live_coral: 0.37,
      bleached_coral: 0.17,
      algae: 0.09,
      rubble: 0.14,
      sand: 0.21,
      other: 0.02,
    },
    failure_reason: null,
    created_at: "2026-10-21T08:00:00Z",
  },
];

describe("CoverChart", () => {
  it("renders stacked bars for dive dates and legend swatches", () => {
    render(<CoverChart surveys={mockSurveys} />);

    // Legend classes
    expect(screen.getByText("Live coral")).toBeInTheDocument();
    expect(screen.getByText("Bleached coral")).toBeInTheDocument();
    expect(screen.getByText("Algae")).toBeInTheDocument();
    expect(screen.getByText("Rubble")).toBeInTheDocument();
    expect(screen.getByText("Sand")).toBeInTheDocument();
    expect(screen.getByText("Rock and unclassified")).toBeInTheDocument();

    // Bars with dive dates
    expect(screen.getByText("2021-11-03")).toBeInTheDocument();
    expect(screen.getByText("2024-03-12")).toBeInTheDocument();
    expect(screen.getByText("2026-10-21")).toBeInTheDocument();

    // Live coral percentages
    expect(screen.getByText("52%")).toBeInTheDocument();
    expect(screen.getByText("48%")).toBeInTheDocument();
    expect(screen.getByText("37%")).toBeInTheDocument();
  });
});
