import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AskCase } from "./AskCase";
import type { FrameView, ToolCallView } from "../live/reducer";

const mockFrames: FrameView[] = [
  {
    id: "frm_01",
    thumbUrl: "/media/frames/01.jpg",
    imageUrl: "/media/frames/01.jpg",
    cover: {
      live_coral: 0.3,
      bleached_coral: 0.4,
      algae: 0.1,
      rubble: 0.1,
      sand: 0.05,
      other: 0.05,
    },
    assessment: {
      id: "fa_01",
      frame_id: "frm_01",
      model: "muse_spark_open",
      bleaching_severity: 3,
      morphology: ["branching"],
      damage: ["none"],
      notes: "Advanced bleaching",
    },
  },
];

const mockToolCalls: ToolCallView[] = [
  {
    callId: "call_1",
    tool: "heat_stress",
    toolResultId: "tr_heat_1",
    params: {},
    status: "returned",
  },
];

const server = setupServer(
  http.post("http://localhost/api/surveys/:survey_id/ask", async ({ request }) => {
    const body = (await request.json()) as { question: string };
    return HttpResponse.json({
      answer: `Answer to: ${body.question}. Thermal stress was severe.`,
      citations: [
        { kind: "tool_result", id: "tr_heat_1" },
        { kind: "frame", id: "frm_01" },
      ],
    });
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      POST: vi.fn(async (path: string, options: any) => {
        const url = `http://localhost${path.replace("{survey_id}", options.params.path.survey_id)}`;
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(options.body),
        });
        const data = await res.json();
        return { data, response: res };
      }),
    },
  };
});

describe("AskCase", () => {
  it("renders closed by default, opens to show 3 suggestions, posts question on click and calls drawer opener on chip click", async () => {
    const handleOpenEvidence = vi.fn();

    render(
      <AskCase
        surveyId="srv_test_01"
        onOpenEvidence={handleOpenEvidence}
        frames={mockFrames}
        toolCalls={mockToolCalls}
      />,
    );

    // Closed by default
    expect(screen.getByRole("button", { name: /Ask this case/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("Why not heat stress?")).not.toBeInTheDocument();

    // Click to open panel
    fireEvent.click(screen.getByRole("button", { name: /Ask this case/i }));
    expect(screen.getByRole("button", { name: /Ask this case/i })).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    // Three suggestion buttons are rendered
    const btn1 = screen.getByRole("button", { name: "Why not heat stress?" });
    const btn2 = screen.getByRole("button", { name: "What changed since 2019?" });
    const btn3 = screen.getByRole("button", { name: "What should the park do first?" });
    expect(btn1).toBeInTheDocument();
    expect(btn2).toBeInTheDocument();
    expect(btn3).toBeInTheDocument();

    // Clicking a suggestion button sends the question immediately
    fireEvent.click(btn1);

    // Answer rendered
    expect(
      await screen.findByText(/Answer to: Why not heat stress\?\. Thermal stress was severe\./i),
    ).toBeInTheDocument();

    // Evidence chips are rendered
    const toolChip = screen.getByRole("button", { name: /Open evidence: Heat stress/i });
    expect(toolChip).toBeInTheDocument();

    const frameChip = screen.getByRole("button", { name: /Open evidence: Frame 01/i });
    expect(frameChip).toBeInTheDocument();

    // Clicking an evidence chip calls onOpenEvidence
    fireEvent.click(toolChip);
    expect(handleOpenEvidence).toHaveBeenCalledWith({
      kind: "tool_result",
      id: "tr_heat_1",
    });

    fireEvent.click(frameChip);
    expect(handleOpenEvidence).toHaveBeenCalledWith({
      kind: "frame",
      id: "frm_01",
    });
  });
});
