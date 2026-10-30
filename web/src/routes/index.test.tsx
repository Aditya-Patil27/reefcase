vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>();
  return {
    ...actual,
    Link: ({ to, children, ...props }: any) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
  };
});

vi.mock("react-map-gl/maplibre", () => ({
  default: ({ children, onClick }: any) => <div data-testid="maplibre-map" onClick={onClick}>{children}</div>,
  Marker: ({ children, onClick }: any) => <div data-testid="map-marker" onClick={onClick}>{children}</div>,
  Popup: ({ children }: any) => <div data-testid="map-popup">{children}</div>,
  Source: ({ children }: any) => <div>{children}</div>,
  Layer: () => null,
}));

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Route } from "./index";

const mockSites = [
  {
    id: "site_lizard_island",
    name: "Lizard Island",
    location: { lat: -14.668, lon: 145.461 },
    mpa_id: "mpa_lizard_island_reef",
    latest_cover: {
      live_coral: 0.37,
      bleached_coral: 0.15,
      algae: 0.1,
      rubble: 0.2,
      sand: 0.16,
      other: 0.02,
    },
    latest_dive_date: "2026-10-21",
    trend: "declining" as const,
  },
  {
    id: "site_swaraj_dweep",
    name: "Swaraj Dweep, Andaman",
    location: { lat: 11.98, lon: 93.01 },
    mpa_id: "mpa_mahatma_gandhi_marine",
    latest_cover: {
      live_coral: 0.41,
      bleached_coral: 0.04,
      algae: 0.07,
      rubble: 0.12,
      sand: 0.34,
      other: 0.02,
    },
    latest_dive_date: "2026-03-04",
    trend: "improving" as const,
  },
];

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  api: {
    GET: vi.fn((path: string) => {
      if (path === "/api/sites") {
        return Promise.resolve({ data: mockSites });
      }
      return Promise.resolve({ data: { type: "FeatureCollection", features: [] } });
    }),
  },
}));

describe("MapRoute", () => {
  let queryClient: QueryClient;
  const Component = (Route as any).options.component;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  it("renders the Sites list and Layers controls", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    // Section headings
    expect(screen.getByRole("heading", { name: "Sites" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Layers" })).toBeInTheDocument();

    // Sites in list
    await waitFor(() => {
      expect(screen.getByText("Lizard Island")).toBeInTheDocument();
      expect(screen.getByText("Swaraj Dweep, Andaman")).toBeInTheDocument();
    });

    // Layer switch labels
    expect(screen.getByText("MPA boundaries")).toBeInTheDocument();
    expect(screen.getByText("Reef extent")).toBeInTheDocument();
    expect(screen.getByText("Vessel activity")).toBeInTheDocument();
  });

  it("selects a site when clicking row in left panel and shows its popover details", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <Component />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Lizard Island")).toBeInTheDocument();
    });

    const lizardRow = screen.getByText("Lizard Island").closest("[role='listitem']");
    expect(lizardRow).not.toBeNull();
    fireEvent.click(lizardRow!);

    // Popover contains site details and a link to the site page
    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: "Lizard Island" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Open site" })).toHaveAttribute("href", "/sites/$id");
    });
  });
});
