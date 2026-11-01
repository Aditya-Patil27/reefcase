import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SpecimenTray } from "./SpecimenTray";
import type { FrameView } from "../live/reducer";

describe("SpecimenTray", () => {
  const mockFrames: FrameView[] = [
    {
      id: "frm_01",
      thumbUrl: "/media/frames/01.jpg",
      cover: {
        live_coral: 0.12,
        bleached_coral: 0.05,
        algae: 0.4,
        rubble: 0.2,
        sand: 0.2,
        other: 0.03,
      },
    },
    {
      id: "frm_02",
      thumbUrl: "/media/frames/02.jpg",
      cover: {
        live_coral: 0.25,
        bleached_coral: 0.1,
        algae: 0.3,
        rubble: 0.15,
        sand: 0.18,
        other: 0.02,
      },
    },
  ];

  it("renders thumbnails and calls onSelectFrame on click", () => {
    const handleSelect = vi.fn();
    render(
      <SpecimenTray
        frames={mockFrames}
        selectedFrameId="frm_01"
        citedFrameIds={new Set(["frm_02"])}
        onSelectFrame={handleSelect}
      />,
    );

    const btn1 = screen.getByRole("button", { name: "Open Frame 01" });
    const btn2 = screen.getByRole("button", { name: "Open Frame 02" });

    expect(btn1).toBeInTheDocument();
    expect(btn2).toBeInTheDocument();

    fireEvent.click(btn2);
    expect(handleSelect).toHaveBeenCalledWith("frm_02");
  });

  it("navigates with ArrowRight and ArrowLeft keys", () => {
    const handleSelect = vi.fn();
    render(
      <SpecimenTray
        frames={mockFrames}
        selectedFrameId="frm_01"
        onSelectFrame={handleSelect}
      />,
    );

    const btn1 = screen.getByRole("button", { name: "Open Frame 01" });
    btn1.focus();

    fireEvent.keyDown(btn1, { key: "ArrowRight" });
    expect(handleSelect).toHaveBeenCalledWith("frm_02");
  });
});

