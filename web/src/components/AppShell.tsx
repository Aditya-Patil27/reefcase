import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";

type Health = components["schemas"]["Health"];

type Credit = { source: string; licence: string; obligation: string };

/** Every attribution in architecture §9.9, plus the basemap (docs/agents/ui.md). */
const CREDITS: readonly Credit[] = [
  {
    source: "Global Fishing Watch",
    licence: "CC BY-NC 4.0",
    obligation: "Powered by Global Fishing Watch. Non-commercial use only.",
  },
  {
    source: "NOAA Coral Reef Watch, NCRMP",
    licence: "US Government work",
    obligation: "Cite NOAA Coral Reef Watch and PIFSC ESD.",
  },
  {
    source: "Allen Coral Atlas",
    licence: "CC BY 4.0",
    obligation: "Cite doi:10.5281/zenodo.3833242.",
  },
  {
    source: "Protected Planet, WDPA",
    licence: "Non-commercial",
    obligation: "Cite UNEP-WCMC and IUCN.",
  },
  {
    source: "Coralscapes",
    licence: "Apache-2.0",
    obligation: "Cite the Coralscapes paper.",
  },
  {
    source: "Ifremer clips",
    licence: "CC BY 4.0",
    obligation: "Credit Ifremer.",
  },
  {
    source: "SAM 3",
    licence: "SAM License",
    obligation: "Acknowledge SAM. Include the licence when redistributing.",
  },
  {
    source: "Muse Spark Open, Glimmer-Reef",
    licence: "Muse Model License",
    obligation: "Built with Muse Spark Open. Ship the licence and Usage Policy.",
  },
  {
    source: "CARTO, OpenStreetMap",
    licence: "Basemap",
    obligation: "Credit CARTO and OpenStreetMap contributors.",
  },
];

function HealthReadout() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async (): Promise<Health> => {
      const { data, response } = await api.GET("/api/health");
      if (!data) throw new Error(`Health check returned ${response.status}.`);
      return data;
    },
    retry: 5,
    retryDelay: (attempt) => Math.min(500 * 2 ** attempt, 2000),
  });

  const status = health.isPending ? "pending" : health.isError ? "error" : health.data.status;
  const dot =
    status === "ok"
      ? "bg-success"
      : status === "degraded"
        ? "bg-warning"
        : status === "pending"
          ? "bg-muted"
          : "bg-danger";
  const readout = health.isPending
    ? "checking providers"
    : health.isError
      ? "API unreachable"
      : health.data.detail;

  return (
    <p role="status" className="flex items-center gap-2 font-mono text-label text-secondary">
      <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${dot}`} />
      <span>{readout}</span>
    </p>
  );
}

function DataCredits() {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="rounded-md px-1 py-0.5 text-label text-secondary hover:text-fg"
      >
        Data credits
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label="Data credits"
          className="absolute bottom-full left-0 z-10 mb-2 w-72 rounded-lg border border-hairline bg-raised p-4 text-label text-secondary shadow-floating"
        >
          <ul className="space-y-2">
            {CREDITS.map((credit) => (
              <li key={credit.source}>
                <span className="text-fg">{credit.source}</span>{" "}
                <span className="font-mono text-muted">{credit.licence}</span>
                <span className="block text-muted">{credit.obligation}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/**
 * The active link is `text-fg` with a 2px accent underline. Both come from the
 * `data-status` attribute the router sets, so the inactive transparent border can
 * never win the cascade against the active colour.
 */
const navLinkClass =
  "border-b-2 border-b-transparent px-1 py-3 text-ui text-secondary hover:text-fg data-[status=active]:border-b-accent data-[status=active]:text-fg";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-hairline px-4">
        <div className="flex items-center gap-6">
          <Link to="/" className="text-ui font-semibold text-fg">
            ReefCase
          </Link>
          <nav aria-label="Primary" className="flex items-center gap-4">
            <Link to="/" activeOptions={{ exact: true }} className={navLinkClass}>
              Map
            </Link>
            <Link to="/upload" className={navLinkClass}>
              Upload
            </Link>
          </nav>
        </div>
        <HealthReadout />
      </header>
      <main className="flex-1">{children}</main>
      <footer className="flex h-8 shrink-0 items-center justify-between gap-4 border-t border-hairline px-4 text-label text-muted">
        <DataCredits />
        <p className="min-w-0 truncate font-mono">Open-weight models · SAM 3 · Muse Spark Open</p>
      </footer>
    </div>
  );
}
