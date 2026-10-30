import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";

type Health = components["schemas"]["Health"];

type Credit = { source: string; licence: string; obligation: string };

/** Every attribution in architecture §9.9, plus the basemap. */
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
  // A down or degraded API is not a proven alert: the dot empties instead of turning red.
  const dot =
    status === "ok"
      ? "bg-strobe"
      : status === "pending"
        ? "bg-deep-ink"
        : status === "degraded"
          ? "border-[1.5px] border-strobe"
          : "border-[1.5px] border-deep-ink";
  const readout = health.isPending
    ? "checking models"
    : health.isError
      ? "API unreachable"
      : health.data.detail;

  return (
    <p role="status" className="flex min-w-0 items-center gap-2 text-label text-deep-ink">
      <span aria-hidden="true" className={`size-2 shrink-0 ${dot}`} />
      <span className="truncate">{readout}</span>
    </p>
  );
}

function DataCredits() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  // Escape and a click outside close it, like any other popover.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    function onPointer(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative shrink-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="py-1 text-label font-semibold text-secondary underline decoration-border hover:text-fg hover:decoration-fg"
      >
        Data credits
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label="Data credits"
          className="absolute bottom-full left-0 z-20 mb-2 w-80 max-w-[calc(100vw-2rem)] border border-border bg-raised p-4 text-label text-secondary shadow-floating"
        >
          <ul className="grid gap-3">
            {CREDITS.map((credit) => (
              <li key={credit.source}>
                <span className="font-semibold text-fg">{credit.source}</span>{" "}
                <span className="text-muted">· {credit.licence}</span>
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
 * The active link carries a 2px strobe underline, set from the `data-status` attribute the router
 * adds, so the inactive transparent border can never win the cascade.
 */
const navLinkClass =
  "flex h-14 items-center border-b-2 border-b-transparent text-ui text-deep-ink hover:text-on-accent data-[status=active]:border-b-strobe data-[status=active]:font-semibold data-[status=active]:text-on-accent";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <header className="flex h-14 shrink-0 items-center gap-6 bg-deep px-4 text-on-accent sm:gap-10 sm:px-7">
        <Link to="/" className="text-title font-extrabold tracking-tight text-on-accent">
          ReefCase
        </Link>
        <nav aria-label="Primary" className="flex items-center gap-5 sm:gap-7">
          <Link to="/" activeOptions={{ exact: true }} className={navLinkClass}>
            Map
          </Link>
          <Link to="/upload" className={navLinkClass}>
            <span className="sm:hidden">Upload</span>
            <span className="hidden sm:inline">Upload a dive</span>
          </Link>
        </nav>
        <div className="ml-auto min-w-0">
          <HealthReadout />
        </div>
      </header>
      <main className="flex min-h-0 flex-1 flex-col">{children}</main>
      <footer className="flex shrink-0 items-center justify-between gap-4 border-t border-hairline px-4 py-2 text-label text-muted sm:px-7">
        <DataCredits />
        <p className="min-w-0 truncate">Open-weight models · SAM 3 · Muse Spark Open</p>
      </footer>
    </div>
  );
}
