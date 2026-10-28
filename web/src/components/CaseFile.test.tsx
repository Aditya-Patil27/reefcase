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

    // 01 FINDINGS
    expect(screen.getByRole("heading", { name: /01\s+FINDINGS/i })).toBeInTheDocument();
    expect(
      screen.getByText(/Bleaching detected across transect frames./i),
    ).toBeInTheDocument();

    // 02 HYPOTHESES with confidence bars
    expect(screen.getByRole("heading", { name: /02\s+HYPOTHESES/i })).toBeInTheDocument();
    expect(screen.getByText("heat_stress")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.getByText("fishing_pressure")).toBeInTheDocument();
    expect(screen.getByText("24%")).toBeInTheDocument();

    // 03 ACTIONS
    expect(screen.getByRole("heading", { name: /03\s+ACTIONS/i })).toBeInTheDocument();
    expect(
      screen.getByText(/Re-survey the same transect in February 2027./i),
    ).toBeInTheDocument();
  });

  it("calls onOpenEvidence when clicking a frame or tool chip", () => {
    const handleOpenEvidence = vi.fn();

    render(
      <CaseFile
        investigation={mockInvestigation}
        onOpenEvidence={handleOpenEvidence}
      />,
    );

    const frameChip = screen.getByRole("button", { name: /frm_06/i });
    fireEvent.click(frameChip);
    expect(handleOpenEvidence).toHaveBeenCalledWith({ kind: "frame", id: "frm_06" });

    const toolChip = screen.getAllByRole("button", { name: /tr_01JA7/i })[0];
    fireEvent.click(toolChip!);

    expect(handleOpenEvidence).toHaveBeenCalledWith({ kind: "tool_result", id: "tr_01JA7" });
  });
});
