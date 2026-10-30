import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CaseFile } from "./CaseFile";
import type { components } from "../api/schema";

type Investigation = components["schemas"]["Investigation"];

const mockInvestigation: Investigation = {
  id: "inv_01JA7Z6M0B2D4F6H8K0N2Q4S6V",
  survey_id: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3",
  verdict: "Thermal stress drove most of the bleaching; vessel pressure is a secondary signal.",
  findings: [
    {
      statement: "Bleaching detected across transect frames.",
      evidence: [
        { kind: "frame", id: "frm_06" },
        { kind: "tool_result", id: "tr_01JA7" },
      ],
    },
  ],
  hypotheses: [
    {
      cause: "heat_stress",
      confidence: 0.62,
      supporting: [{ kind: "tool_result", id: "tr_01JA7" }],
      contradicting: [],
      rationale: "DHW sat above 4 C-weeks for five weeks.",
    },
    {
      cause: "fishing_pressure",
      confidence: 0.24,
      supporting: [{ kind: "frame", id: "frm_04" }],
      contradicting: [],
      rationale: "Four detections inside no-take boundary.",
    },
  ],
  actions: [
    "Re-survey the same transect in February 2027.",
    "Ask the reef authority for September vessel tracks.",
  ],
  uncertain_frames: ["frm_04"],
  model: "Muse Spark Open",
};

describe("CaseFile", () => {
  it("renders verdict block, findings, hypotheses with confidence bars and actions", () => {
    const handleOpenEvidence = vi.fn();

    render(
      <CaseFile
        investigation={mockInvestigation}
        onOpenEvidence={handleOpenEvidence}
      />,
    );

    // Verdict block
    expect(
      screen.getByText(/Thermal stress drove most of the bleaching/i),
    ).toBeInTheDocument();

    // Findings
    expect(screen.getByRole("heading", { name: "Findings" })).toBeInTheDocument();
    expect(
      screen.getByText(/Bleaching detected across transect frames./i),
    ).toBeInTheDocument();

    // Hypotheses with confidence bars
    expect(screen.getByRole("heading", { name: "Hypotheses" })).toBeInTheDocument();
    expect(screen.getByText("Heat stress")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.getByText("Fishing pressure")).toBeInTheDocument();
    expect(screen.getByText("24%")).toBeInTheDocument();

    // Actions
    expect(screen.getByRole("heading", { name: "Actions" })).toBeInTheDocument();
    expect(
      screen.getByText(/Re-survey the same transect in February 2027./i),
    ).toBeInTheDocument();
  });

  it("labels chips by frame ordinal and tool name, and opens the evidence", () => {
    const handleOpenEvidence = vi.fn();

    render(
      <CaseFile
        investigation={mockInvestigation}
        onOpenEvidence={handleOpenEvidence}
        frames={[
          { id: "frm_04", thumbUrl: "/media/frames/04.jpg" },
          { id: "frm_06", thumbUrl: "/media/frames/06.jpg" },
        ]}
        toolCalls={[
          { callId: "c1", tool: "heat_stress", params: {}, status: "returned", toolResultId: "tr_01JA7" },
        ]}
      />,
    );

    const frameChip = screen.getByRole("button", { name: "Open evidence: Frame 02" });
    fireEvent.click(frameChip);
    expect(handleOpenEvidence).toHaveBeenCalledWith({ kind: "frame", id: "frm_06" });

    const toolChip = screen.getAllByRole("button", { name: "Open evidence: Heat stress" })[0];
    fireEvent.click(toolChip!);

    expect(handleOpenEvidence).toHaveBeenCalledWith({ kind: "tool_result", id: "tr_01JA7" });
  });

  it("draws an uncited finding as pending and shows a proven alert", () => {
    render(
      <CaseFile
        investigation={{
          ...mockInvestigation,
          findings: [{ statement: "Turbidity hides the deeper colonies.", evidence: [] }],
        }}
        onOpenEvidence={vi.fn()}
        alert="Bleaching alert level 1 · peak 6.8 °C-weeks"
      />,
    );

    expect(screen.getByText("No evidence cited yet")).toBeInTheDocument();
    expect(screen.getByText("Bleaching alert level 1 · peak 6.8 °C-weeks")).toBeInTheDocument();
  });
});
