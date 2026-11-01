import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SpecimenLabel } from "./SpecimenLabel";
import type { FrameView } from "../live/reducer";

describe("SpecimenLabel", () => {
  it("renders catalogue number, coordinates, morphology, and detection models", () => {
    const mockFrame: FrameView = {
      id: "frm_16",
      thumbUrl: "/media/frames/16.jpg",
      assessment: {
        id: "fa_16",
        frame_id: "frm_16",
        model: "muse-spark-open-1026",
        bleaching_severity: 2,
        morphology: ["branching"],
        damage: ["none"],
        notes: "Pocillopora-like colonies",
      },
    };

    render(
      <SpecimenLabel
        siteName="HAW-41"
        diveDate="2024-07-06"
        frameIndex={16}
        frame={mockFrame}
        lat={20.79}
        lon={-156.47}
        segBackend="sam3"
      />,
    );

    expect(screen.getByText("RC-HAW41-2024-")).toBeInTheDocument();
    expect(screen.getByText("F16")).toBeInTheDocument();
    expect(screen.getByText(/20.79°N 156.47°W · 2024-07-06/)).toBeInTheDocument();
    expect(screen.getByText(/Branching, severity 2/)).toBeInTheDocument();
    expect(screen.getByText(/det. SAM 3 \/ Muse Spark Open/)).toBeInTheDocument();
  });

  it("omits lines when data is missing without inventing values", () => {
    const emptyFrame: FrameView = {
      id: "frm_01",
      thumbUrl: "/media/frames/01.jpg",
    };

    render(
      <SpecimenLabel
        siteName="LIZARD"
        diveDate="2023-01-01"
        frameIndex={1}
        frame={emptyFrame}
      />,
    );

    expect(screen.getByText("RC-LIZARD-2023-")).toBeInTheDocument();
    expect(screen.getByText("F01")).toBeInTheDocument();
    expect(screen.queryByText(/det\./)).not.toBeInTheDocument();
    expect(screen.queryByText(/severity/)).not.toBeInTheDocument();
  });
});

