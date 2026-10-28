import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FrameGrid } from "./FrameGrid";
import type { FrameView } from "../live/reducer";

const sampleFrames: FrameView[] = [
  {
    id: "frm_01JA7Z4CBW1S7A3B9C5E1G7J3M",
    thumbUrl: "/media/frames/01.jpg",
    maskUrl: "/media/masks/01.png",
    quality: { blur: 0.1, color_cast: 0.1, turbidity: 0.2, passed: true, reason: null },
    cover: {
      live_coral: 0.35,
      bleached_coral: 0.15,
      algae: 0.1,
      rubble: 0.2,
      sand: 0.18,
      other: 0.02,
    },
  },
  {
    id: "frm_pending_02",
    thumbUrl: "",
  },
];

describe("FrameGrid", () => {
  it("renders the FRAMES section header and segmented control", () => {
    render(<FrameGrid frames={sampleFrames} />);
    expect(screen.getByRole("heading", { name: "FRAMES" })).toBeInTheDocument();
    expect(screen.getByText("Frame")).toBeInTheDocument();
    expect(screen.getByText("Mask")).toBeInTheDocument();
    expect(screen.getByText("Both")).toBeInTheDocument();
  });

  it("renders thumbnails, cover strips, and skeletons for pending frames", () => {
    render(<FrameGrid frames={sampleFrames} />);

    // Frame 01 thumbnail
    const img = screen.getByAltText("Frame 01");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "/media/frames/01.jpg");

    // Frame 01 cover strip
    const coverStrip = screen.getByRole("img", { name: /Live coral/i });
    expect(coverStrip).toBeInTheDocument();

    // Frame 02 is pending, shows skeleton
    const skeletons = document.querySelectorAll("[data-skeleton='true']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("switches display mode when segmented control changes", () => {
    render(<FrameGrid frames={sampleFrames} />);
    const maskButton = screen.getByText("Mask");
    fireEvent.click(maskButton);

    // In Mask mode, mask image is visible
    const maskImg = screen.getByAltText("Frame 01 mask");
    expect(maskImg).toBeInTheDocument();
  });
});
