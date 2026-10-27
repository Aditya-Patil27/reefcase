import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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

let mockData: SiteDetail | null = mockSiteDetail;

vi.mock("../api/client", () => ({
  api: {
    GET: vi.fn((path: string) => {
      if (path.includes("/api/sites/")) {
        return Promise.resolve({ data: mockData });
      }
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

    // Coordinates in mono
    expect(screen.getByText(/14.6680°\s+S\s+145.4610°\s+E/i)).toBeInTheDocument();

    // MPA badge
    expect(screen.getByText(/MPA/i)).toBeInTheDocument();

    // 4 metric cards
    expect(screen.getByText("Live cover now")).toBeInTheDocument();
    expect(screen.getByText("Change")).toBeInTheDocument();
    expect(screen.getByText("Surveys")).toBeInTheDocument();
    expect(screen.getByText("Latest heat stress")).toBeInTheDocument();

    // 01 COVER OVER TIME and 02 SURVEYS
    expect(screen.getByRole("heading", { name: /01\s+COVER OVER TIME/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /02\s+SURVEYS/i })).toBeInTheDocument();

    // Surveys table contains Case file links
    const caseFileLinks = screen.getAllByRole("link", { name: /Case file/i });
    expect(caseFileLinks.length).toBeGreaterThan(0);
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
});
