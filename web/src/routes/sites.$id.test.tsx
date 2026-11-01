import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Route } from "./sites.$id";
import type { components } from "../api/schema";

vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>();
  return {
    ...actual,
    Link: ({ to, children, ...props }: any) => (
      <a href={typeof to === "string" ? to : "#"} {...props}>
        {children}
      </a>
    ),
  };
});

type SiteDetail = components["schemas"]["SiteDetail"];

const mockSiteDetail: SiteDetail = {
  site: {
    id: "site_lizard_island",
    name: "Lizard Island",
    location: { lat: -14.668, lon: 145.461 },
    mpa_id: "mpa_lizard_island_reef",
    created_at: "2019-08-19T08:00:00Z",
  },
  surveys: [
    {
      id: "srv_03",
      site_id: "site_lizard_island",
      dive_date: "2026-10-21",
      status: "done",
      source: "upload",
      video_path: "/media/clips/lizard.mp4",
      cover: {
        live_coral: 0.37,
        bleached_coral: 0.17,
        algae: 0.09,
        rubble: 0.14,
        sand: 0.21,
        other: 0.02,
      },
      failure_reason: null,
      created_at: "2026-10-21T08:00:00Z",
    },
    {
      id: "srv_01",
      site_id: "site_lizard_island",
      dive_date: "2021-11-03",
      status: "done",
      source: "historical",
      video_path: null,
      cover: {
        live_coral: 0.484,
        bleached_coral: 0.05,
        algae: 0.08,
        rubble: 0.11,
        sand: 0.26,
        other: 0.02,
      },
      failure_reason: null,
      created_at: "2021-11-03T08:00:00Z",
    },
  ],
};

let mockData: SiteDetail | null | undefined = mockSiteDetail;
let mockFrames: unknown[] | null = null;
let mockInvestigation: unknown = null;

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  api: {
    GET: vi.fn((path: string) => {
      if (path.includes("/api/sites/")) {
        if (mockData === undefined) {
          return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
        }
        return Promise.resolve({ data: mockData });
      }
      if (path.endsWith("/frames")) return Promise.resolve({ data: mockFrames });
      if (path.endsWith("/investigation")) return Promise.resolve({ data: mockInvestigation });
      return Promise.resolve({ data: null });
    }),
  },
}));

describe("SiteTimelineRoute", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    mockData = mockSiteDetail;
    mockFrames = null;
    mockInvestigation = null;
    vi.spyOn(Route, "useParams").mockReturnValue({ id: "site_lizard_island" });
  });

  it("renders header with site name, coordinates and MPA badge", async () => {
    const Component = (Route as any).options.component;
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    // Site name in display size
    expect(await screen.findByRole("heading", { name: "Lizard Island" })).toBeInTheDocument();

    // Coordinates
    expect(screen.getByText(/14.6680°\s+S\s+145.4610°\s+E/i)).toBeInTheDocument();

    // MPA chip
    expect(screen.getByText("MPA protected")).toBeInTheDocument();

    // One readout line of key figures
    expect(screen.getByLabelText("Site key figures")).toHaveTextContent(
      /\d+% live coral [+−]\d+\.\d pp since \d{4} · \d+ surveys/,
    );

    // Cover over time and Surveys
    expect(screen.getByRole("heading", { name: "Cover over time" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Surveys" })).toBeInTheDocument();

    // Surveys table contains Case file links
    const caseFileLinks = screen.getAllByRole("link", { name: /Case file/i });
    expect(caseFileLinks.length).toBeGreaterThan(0);
  });

  it("sorts the surveys table by live cover", async () => {
    const Component = (Route as any).options.component;
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    const table = await screen.findByRole("table", { name: "Recorded site surveys" });
    const order = () =>
      within(table)
        .getAllByRole("row")
        .slice(1)
        .map((row) => within(row).getAllByRole("cell")[1]?.textContent);
    const header = within(table).getByRole("columnheader", { name: /Live cover/ });
    const sort = within(header).getByRole("button");

    fireEvent.click(sort);
    const first = header.getAttribute("aria-sort");
    const firstOrder = order();
    fireEvent.click(sort);
    const secondOrder = order();

    expect(first === "ascending" ? firstOrder : secondOrder).toEqual(["37%", "48%"]);
    expect(first === "ascending" ? secondOrder : firstOrder).toEqual(["48%", "37%"]);
  });

  it("leaves a survey without cover out of the key figures", async () => {
    mockData = {
      site: mockSiteDetail.site,
      surveys: [
        {
          ...mockSiteDetail.surveys[0]!,
          id: "srv_04",
          dive_date: "2026-10-30",
          status: "running",
          cover: null,
        },
        ...mockSiteDetail.surveys,
      ],
    };

    const Component = (Route as any).options.component;
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    expect(await screen.findByLabelText("Site key figures")).toHaveTextContent(
      /37% live coral −11\.4 pp since 2021 · 3 surveys · latest dive 2026-10-21/,
    );
  });

  it("measures the change against the previous dive, not the first", async () => {
    mockData = {
      site: mockSiteDetail.site,
      surveys: [
        ...mockSiteDetail.surveys,
        {
          ...mockSiteDetail.surveys[1]!,
          id: "srv_00",
          dive_date: "2013-08-03",
          cover: { ...mockSiteDetail.surveys[1]!.cover!, live_coral: 0.05 },
        },
      ],
    };

    const Component = (Route as any).options.component;
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    expect(await screen.findByLabelText("Site key figures")).toHaveTextContent(
      /37% live coral −11\.4 pp since 2021 · 3 surveys/,
    );
  });

  it("renders empty state when site has no surveys", async () => {
    mockData = {
      site: mockSiteDetail.site,
      surveys: [],
    };

    const Component = (Route as any).options.component;
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText(/No surveys at this site yet. Upload a dive to start its record./i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Upload/i })).toBeInTheDocument();
  });

  it("says the record did not load when the API fails, not that the site is empty", async () => {
    mockData = undefined;

    const Component = (Route as any).options.component;
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(/The site record did not load/);
    expect(screen.queryByText(/No surveys at this site yet/)).not.toBeInTheDocument();
  });

  it("lays out the latest dive's frames and slim case file beside the site record", async () => {
    mockFrames = [
      {
        frame: {
          id: "frm_a",
          survey_id: "srv_03",
          t_sec: 1,
          image_path: "blobs/srv_03/frames/frm_a.jpg",
          quality: { blur: 0.1, color_cast: 0.1, turbidity: 0.1, passed: true, reason: null },
        },
        segmentation: {
          id: "seg_a",
          frame_id: "frm_a",
          backend: "sam3",
          mask_path: "blobs/srv_03/masks/frm_a.png",
          cover: mockSiteDetail.surveys[0]!.cover,
          latency_ms: 900,
        },
        assessment: null,
      },
    ];
    mockInvestigation = {
      id: "inv_1",
      survey_id: "srv_03",
      findings: [{ statement: "Bleaching is widespread on the slope.", evidence: [{ kind: "frame", id: "frm_a" }] }],
      hypotheses: [
        { cause: "heat_stress", confidence: 0.62, supporting: [], contradicting: [], rationale: "Hot summer." },
        { cause: "cyclone", confidence: 0.15, supporting: [], contradicting: [], rationale: "Wave impact." },
      ],
      verdict: "Thermal stress drove most of the bleaching. Marine heatwaves exceeded 8 degree heating weeks.",
      actions: ["Re-survey in February."],
      uncertain_frames: [],
      model: "Muse Spark Open",
    };

    const Component = (Route as any).options.component;
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Evidence: 1 frame from the 2026 dive" }),
    ).toBeInTheDocument();
    const lit = screen.getByRole("button", { name: "Open Frame 01" });
    expect(lit).toHaveAttribute("data-lit", "true");
    expect(screen.getByAltText("Frame 01")).toHaveAttribute("src", "/media/srv_03/thumbs/frm_a.jpg");

    // Right column shows only first sentence, top hypothesis, and Open full case file
    expect(await screen.findByText("Thermal stress drove most of the bleaching.")).toBeInTheDocument();
    expect(screen.queryByText("Marine heatwaves exceeded 8 degree heating weeks.")).not.toBeInTheDocument();
    expect(screen.getByText("Heat stress")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.queryByText("Cyclone")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open full case file" })).toBeInTheDocument();

    // No findings, other hypotheses, or actions headings
    expect(screen.queryByRole("heading", { name: "Findings" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Actions" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Hypotheses" })).not.toBeInTheDocument();

    // No "Cover by dive" in left column
    expect(screen.queryByRole("heading", { name: "Cover by dive" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Cover classes")).not.toBeInTheDocument();
  });

  it("shows empty state in right column when latest dive has no investigation yet", async () => {
    mockFrames = [];
    mockInvestigation = null;

    const Component = (Route as any).options.component;
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText("No case file for the 2026 dive"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("The agent has not investigated this dive yet."),
    ).toBeInTheDocument();
  });
});
