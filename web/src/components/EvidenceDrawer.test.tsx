import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EvidenceDrawer } from "./EvidenceDrawer";

const mockToolResult = {
  id: "tr_01JA7",
  tool: "heat_stress",
  params: { site_id: "site_lizard_island" },
  data: {
    max_dhw: 6.8,
    series: [
      { date: "2026-08-01", dhw: 0.4, sst_anomaly: 0.2, alert_level: 0 },
      { date: "2026-09-14", dhw: 6.8, sst_anomaly: 1.6, alert_level: 1 },
    ],
  },
  source_url: "https://coralreefwatch.noaa.gov/product/vs/gauges/lizard_island.php",
  retrieved_at: "2026-10-21T09:14:02Z",
};

// The real vessel_activity shape (src/reefcase/tools/vessels.py).
const vesselToolResult = {
  id: "tr_vessels",
  tool: "vessel_activity",
  params: { lat: 20.268, lon: -155.86, radius_km: 10, days: 30 },
  data: {
    sar_detections: {
      total: 14,
      unmatched_to_ais: { count: 4, points: [{ lat: 20.27, lon: -155.85 }] },
    },
    fishing_hours: 31.4,
  },
  source_url: "https://gateway.api.globalfishingwatch.org/v3/4wings/report",
  retrieved_at: "2026-10-21T09:14:02Z",
};

const toolResults: Record<string, unknown> = {
  [mockToolResult.id]: mockToolResult,
  [vesselToolResult.id]: vesselToolResult,
};

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  api: {
    GET: vi.fn((path: string, init?: { params?: { path?: { tool_result_id?: string } } }) => {
      if (path.includes("/api/tool-results/")) {
        const id = init?.params?.path?.tool_result_id ?? "";
        return Promise.resolve({ data: toolResults[id] ?? null });
      }
      return Promise.resolve({ data: null });
    }),
  },
}));

describe("EvidenceDrawer", () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  it("renders frame evidence with mask toggle and assessment", () => {
    const mockFrame = {
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
      assessment: {
        id: "fa_06",
        frame_id: "frm_06",
        model: "muse_spark_open",
        bleaching_severity: 3,
        morphology: ["branching"],
        damage: ["none" as const],
        notes: "Branching colonies show advanced bleaching.",
      },
    };

    render(
      <QueryClientProvider client={queryClient}>
        <EvidenceDrawer
          evidence={{ kind: "frame", id: "frm_06" }}
          open={true}
          onOpenChange={vi.fn()}
          frames={[mockFrame]}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Frame 01")).toBeInTheDocument();
    expect(screen.getByText("Both")).toBeInTheDocument();
    expect(
      screen.getByText(/Branching colonies show advanced bleaching./i),
    ).toBeInTheDocument();
  });

  it("renders tool evidence with tool name, params, and source URL", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <EvidenceDrawer
          evidence={{ kind: "tool_result", id: "tr_01JA7" }}
          open={true}
          onOpenChange={vi.fn()}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(await screen.findByText("Heat stress")).toBeInTheDocument();
    expect(
      await screen.findByText(
        "https://coralreefwatch.noaa.gov/product/vs/gauges/lizard_island.php",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Parameters" })).toBeInTheDocument();
  });

  it("summarises vessel activity from the real tool shape", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <EvidenceDrawer
          evidence={{ kind: "tool_result", id: "tr_vessels" }}
          open={true}
          onOpenChange={vi.fn()}
        />
      </QueryClientProvider>,
    );

    const unmatched = await screen.findByText("Not broadcasting AIS");
    expect(unmatched.nextElementSibling).toHaveTextContent("4");
    expect(screen.getByText("All detections within 10 km").nextElementSibling).toHaveTextContent("14");
  });
});
