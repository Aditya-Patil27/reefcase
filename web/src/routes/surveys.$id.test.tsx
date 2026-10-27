import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { UseEventStreamResult } from "../live/useEventStream";

const mocks = vi.hoisted(() => ({
  surveyId: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3",
  useEventStream: vi.fn(),
}));

vi.mock("../live/useEventStream", () => ({
  useEventStream: (id: string | undefined) => mocks.useEventStream(id),
}));

vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>();
  return {
    ...actual,
    createFileRoute: () => (opts: Record<string, unknown>) => ({
      ...opts,
      useParams: () => ({ id: mocks.surveyId }),
    }),
  };
});

// Import after mocking createFileRoute
import { Route } from "./surveys.$id";
const SurveyRouteComponent = (Route as any).component;

describe("SurveyRoute", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  it("renders header strip with survey id, stage stepper, and frames + trace sections", async () => {
    mocks.useEventStream.mockReturnValue({
      state: {
        surveyId: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3",
        lastSeq: 3,
        frames: [
          {
            id: "frm_01",
            thumbUrl: "/media/frames/01.jpg",
            maskUrl: "/media/masks/01.png",
            cover: {
              live_coral: 0.35,
              bleached_coral: 0.15,
              algae: 0.1,
              rubble: 0.2,
              sand: 0.18,
              other: 0.02,
            },
          },
        ],
        toolCalls: [
          {
            callId: "call_01",
            tool: "heat_stress",
            params: { site_id: "site_lizard_island" },
            status: "returned",
            summary: "DHW 6.8 C-weeks",
          },
        ],
        findings: [
          {
            statement: "Bleaching detected across transect frames.",
            evidence: [{ kind: "frame", id: "frm_01" }],
          },
        ],
        investigationId: null,
        reportReady: false,
        failed: null,
      },
      status: "connected",
      reconnectSeq: null,
    } as UseEventStreamResult);

    render(
      <QueryClientProvider client={queryClient}>
        <SurveyRouteComponent />
      </QueryClientProvider>,
    );

    // Readout contains survey id
    expect(screen.getAllByText(/srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3/i).length).toBeGreaterThan(0);

    // Pipeline stages
    expect(screen.getAllByText("Frames").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Segment").length).toBeGreaterThan(0);

    // 01 FRAMES section
    expect(screen.getAllByRole("heading", { name: /01\s+FRAMES/i }).length).toBeGreaterThan(0);

    // 02 TRACE section
    expect(screen.getAllByRole("heading", { name: /02\s+TRACE/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("heat_stress").length).toBeGreaterThan(0);

    // 03 FINDINGS section
    expect(screen.getAllByRole("heading", { name: /03\s+FINDINGS/i }).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Bleaching detected across transect frames./i).length,
    ).toBeGreaterThan(0);
  });
});
