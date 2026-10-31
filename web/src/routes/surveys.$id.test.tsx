vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  api: {
    GET: vi.fn((path: string) => {
      if (path.endsWith("/frames")) return Promise.resolve({ data: mocks.frames });
      if (path === "/api/surveys/{survey_id}") return Promise.resolve({ data: mocks.survey });
      if (path.includes("/api/surveys/") && path.includes("/investigation")) {
        return Promise.resolve({
          data: {
            id: "inv_01JA7Z6M0B2D4F6H8K0N2Q4S6V",
            survey_id: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3",
            verdict: "Thermal stress drove most of the bleaching; vessel pressure is a secondary signal.",
            findings: [
              {
                statement: "Bleaching detected across transect frames.",
                evidence: [{ kind: "frame", id: "frm_06" }],
              },
            ],
            hypotheses: [
              {
                cause: "heat_stress",
                confidence: 0.62,
                supporting: [{ kind: "frame", id: "frm_06" }],
                contradicting: [],
                rationale: "DHW sat above 4 C-weeks for five weeks.",
              },
            ],
            actions: ["Re-survey the same transect in February 2027."],
            uncertain_frames: [],
            model: "Muse Spark Open",
          },
        });
      }
      return Promise.resolve({ data: null });
    }),
  },
}));

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { UseEventStreamResult } from "../live/useEventStream";

const mocks = vi.hoisted(() => ({
  surveyId: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3",
  useEventStream: vi.fn(),
  survey: null as unknown,
  frames: null as unknown,
}));

vi.mock("../live/useEventStream", () => ({
  useEventStream: (id: string | undefined) => mocks.useEventStream(id),
}));

vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>();
  return {
    ...actual,
    Link: ({ to, children, ...props }: any) => (
      <a href={typeof to === "string" ? to : "#"} {...props}>
        {children}
      </a>
    ),
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
    mocks.survey = null;
    mocks.frames = null;
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

    // The header names the dive, not its database id
    expect(screen.queryByText(/srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3/i)).not.toBeInTheDocument();

    // Pipeline stages
    expect(screen.getAllByText("Frames").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Segment").length).toBeGreaterThan(0);

    // Frames section
    expect(screen.getAllByRole("heading", { name: "Frames" }).length).toBeGreaterThan(0);

    // Trace section
    expect(screen.getAllByRole("heading", { name: "Trace" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Heat stress").length).toBeGreaterThan(0);

    // Findings section
    expect(screen.getAllByRole("heading", { name: "Findings" }).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Bleaching detected across transect frames./i).length,
    ).toBeGreaterThan(0);
  });
  it("replaces frames panel with CaseFile when reportReady is true", async () => {
    mocks.useEventStream.mockReturnValue({
      state: {
        surveyId: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3",
        lastSeq: 42,
        frames: [
          {
            id: "frm_06",
            thumbUrl: "/media/frames/06.jpg",
            maskUrl: "/media/masks/06.png",
            cover: {
              live_coral: 0.26,
              bleached_coral: 0.38,
              algae: 0.12,
              rubble: 0.14,
              sand: 0.08,
              other: 0.02,
            },
          },
        ],
        toolCalls: [],
        findings: [
          {
            statement: "Bleaching detected across transect frames.",
            evidence: [{ kind: "frame", id: "frm_06" }],
          },
        ],
        investigationId: "inv_01JA7Z6M0B2D4F6H8K0N2Q4S6V",
        reportReady: true,
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

    // CaseFile replaces FrameGrid
    expect(
      await screen.findByText(/Thermal stress drove most of the bleaching/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Hypotheses" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Actions" })).toBeInTheDocument();

    // The case file owns the findings once it is ready; Trace does not repeat them.
    expect(screen.getAllByText("Bleaching detected across transect frames.")).toHaveLength(1);
  });

  it("names the stage a failed run stopped at and offers a fresh upload", () => {
    mocks.useEventStream.mockReturnValue({
      state: {
        surveyId: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3",
        lastSeq: 4,
        frames: [{ id: "frm_01", thumbUrl: "/media/frames/01.jpg" }],
        toolCalls: [],
        findings: [],
        investigationId: null,
        reportReady: false,
        failed: "SAM 3 timed out on frame 03",
      },
      status: "connected",
      reconnectSeq: null,
    } as UseEventStreamResult);

    render(
      <QueryClientProvider client={queryClient}>
        <SurveyRouteComponent />
      </QueryClientProvider>,
    );

    expect(screen.getByText("Stopped at Frames")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("The run stopped: SAM 3 timed out on frame 03");
    expect(screen.getByRole("link", { name: "Upload the clip again" })).toHaveAttribute("href", "/upload");
    expect(screen.getByText("The agent did not start.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Elapsed time")).not.toBeInTheDocument();
  });
  it("shows an imported record's stored frames and says it was never investigated", async () => {
    const cover = { live_coral: 0.31, bleached_coral: 0.22, algae: 0.1, rubble: 0.15, sand: 0.2, other: 0.02 };
    mocks.survey = {
      id: mocks.surveyId,
      site_id: "site_haw_41",
      dive_date: "2016-07-12",
      status: "done",
      source: "historical",
      video_path: null,
      cover,
      failure_reason: null,
      created_at: "2016-07-12T08:00:00Z",
    };
    mocks.frames = [
      {
        frame: {
          id: "frm_a",
          survey_id: mocks.surveyId,
          t_sec: 1,
          image_path: `blobs/${mocks.surveyId}/frames/frm_a.jpg`,
          quality: { blur: 0.1, color_cast: 0.1, turbidity: 0.1, passed: true, reason: null },
        },
        segmentation: {
          id: "seg_a",
          frame_id: "frm_a",
          backend: "sam3",
          mask_path: `blobs/${mocks.surveyId}/masks/frm_a.png`,
          cover,
          latency_ms: 900,
        },
        assessment: null,
      },
    ];
    // An imported record streams segmented events only: covers, no thumbnails.
    mocks.useEventStream.mockReturnValue({
      state: {
        surveyId: mocks.surveyId,
        lastSeq: 1,
        frames: [{ id: "frm_a", thumbUrl: "", cover }],
        toolCalls: [],
        findings: [],
        investigationId: null,
        reportReady: false,
        failed: null,
      },
      status: "closed",
      reconnectSeq: null,
    } as UseEventStreamResult);

    render(
      <QueryClientProvider client={queryClient}>
        <SurveyRouteComponent />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Imported survey · segmented only, no investigation")).toBeInTheDocument();
    expect(await screen.findByAltText("Frame 01")).toHaveAttribute(
      "src",
      `/media/${mocks.surveyId}/thumbs/frm_a.jpg`,
    );
    expect(screen.queryByRole("heading", { name: "Trace" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Awaiting tool calls/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Elapsed time")).not.toBeInTheDocument();
  });
});
