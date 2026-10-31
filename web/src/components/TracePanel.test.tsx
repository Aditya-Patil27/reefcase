import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TracePanel } from "./TracePanel";
import type { ToolCallView } from "../live/reducer";
import type { components } from "../api/schema";

type Finding = components["schemas"]["Finding"];

const sampleCalls: ToolCallView[] = [
  {
    callId: "call_01",
    tool: "heat_stress",
    params: { site_id: "site_lizard_island", start: "2026-08-01", end: "2026-10-21" },
    status: "returned",
    summary: "DHW peaked at 6.8 C-weeks on 2026-09-14; alert level 1 held for 22 days.",
  },
  {
    callId: "call_02",
    tool: "vessel_activity",
    params: { site_id: "site_lizard_island", radius_km: 10 },
    status: "running",
  },
];

const sampleFindings: Finding[] = [
  {
    statement: "Live coral cover averages 37% with bleaching on five frames.",
    evidence: [
      { kind: "frame", id: "frm_01" },
      { kind: "tool_result", id: "tr_01" },
    ],
  },
];

describe("TracePanel", () => {
  it("renders TRACE heading and tool calls", () => {
    render(<TracePanel toolCalls={sampleCalls} findings={[]} />);
    expect(screen.getByRole("heading", { name: "Trace" })).toBeInTheDocument();
    expect(screen.getByText("Heat stress")).toBeInTheDocument();
    expect(screen.getByText("Vessel activity")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("names the site instead of printing its id", () => {
    const call: ToolCallView = {
      callId: "call_03",
      tool: "site_history",
      params: { site_id: "site_lizard_island" },
      status: "returned",
    };
    render(<TracePanel toolCalls={[call]} findings={[]} siteName="Lizard Island" />);
    expect(screen.getByText("Lizard Island")).toBeInTheDocument();
    expect(screen.queryByText(/site_lizard_island/)).not.toBeInTheDocument();
  });

  it("shows reconnecting alert when reconnectSeq is provided", () => {
    render(
      <TracePanel
        toolCalls={sampleCalls}
        findings={[]}
        status="reconnecting"
        reconnectSeq={41}
      />,
    );
    expect(screen.getByText(/Reconnecting… resuming from event 41/i)).toBeInTheDocument();
  });

  it("expands a tool call row to reveal its result summary", () => {
    render(<TracePanel toolCalls={sampleCalls} findings={[]} />);
    const heatStressRow = screen.getByText("Heat stress").closest("button");
    expect(heatStressRow).toBeInTheDocument();
    if (heatStressRow) {
      fireEvent.click(heatStressRow);
      expect(
        screen.getByText(/DHW peaked at 6.8 C-weeks on 2026-09-14/i),
      ).toBeInTheDocument();
    }
  });

  it("opens a stored tool result in the evidence drawer instead of expanding", () => {
    const onSelectEvidence = vi.fn();
    const calls: ToolCallView[] = [{ ...sampleCalls[0]!, toolResultId: "tr_01" }];
    render(<TracePanel toolCalls={calls} findings={[]} onSelectEvidence={onSelectEvidence} />);
    fireEvent.click(screen.getByText("Heat stress").closest("button")!);
    expect(onSelectEvidence).toHaveBeenCalledWith("tool_result", "tr_01");
    expect(screen.queryByText(/DHW peaked at 6.8 C-weeks/i)).not.toBeInTheDocument();
  });

  it("renders FINDINGS when findings are emitted", () => {
    render(<TracePanel toolCalls={sampleCalls} findings={sampleFindings} frameIds={["frm_01"]} />);
    expect(screen.getByRole("heading", { name: "Findings" })).toBeInTheDocument();
    expect(
      screen.getByText(/Live coral cover averages 37% with bleaching on five frames./i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open evidence: Frame 01" })).toBeInTheDocument();
  });
});
