import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useCrumb } from "./crumb";

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
  // 6px square dot per Specimen Proof contract
  const dot =
    status === "ok"
      ? "bg-ink"
      : status === "pending"
        ? "bg-mute"
        : status === "degraded"
          ? "border border-ink"
          : "border border-mute";
  const readout = health.isPending
    ? "checking models"
    : health.isError
      ? "API unreachable"
      : health.data.detail;

  return (
    <p role="status" className="flex min-w-0 items-center gap-2 font-mono text-mono-sm text-mute">
      <span aria-hidden="true" className={`size-1.5 shrink-0 ${dot}`} />
      <span className="truncate">{readout}</span>
    </p>
  );
}

function DataCredits() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

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
        className="py-1 font-mono text-mono-sm text-mute underline decoration-rule hover:text-ink hover:decoration-ink focus:outline-none focus:ring-1 focus:ring-ink"
      >
        Data credits
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label="Data credits"
          className="absolute bottom-full left-0 z-30 mb-2 w-80 max-w-[calc(100vw-2rem)] border border-rule bg-bg p-4 font-mono text-mono-sm text-mute shadow-none"
        >
          <ul className="grid gap-3">
            {CREDITS.map((credit) => (
              <li key={credit.source}>
                <span className="font-semibold text-ink">{credit.source}</span>{" "}
                <span className="text-mute">· {credit.licence}</span>
                <span className="block text-mute">{credit.obligation}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

const navLinkClass =
  "flex h-14 items-center border-b border-transparent text-mute hover:text-ink data-[status=active]:border-ink data-[status=active]:font-medium data-[status=active]:text-ink transition-colors";

export function AppShell({ children }: { children: ReactNode }) {
  const { crumb } = useCrumb();

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <header className="flex h-14 shrink-0 items-center gap-6 border-b border-rule bg-bg px-4 sm:px-10 text-ink">
        <Link to="/" className="font-sans text-title font-bold tracking-tight text-ink no-underline">
          ReefCase
        </Link>
        {crumb ? (
          <span className="hidden md:inline font-mono text-mono-sm text-mute truncate max-w-md">
            {crumb}
          </span>
        ) : null}

        <nav aria-label="Primary" className="ml-auto flex items-center gap-6 sm:gap-8 font-sans text-ui text-mute">
          <Link to="/" activeOptions={{ exact: true }} className={navLinkClass}>
            Map
          </Link>
          <Link to="/upload" className={navLinkClass}>
            <span className="sm:hidden">Upload</span>
            <span className="hidden sm:inline">Upload a dive</span>
          </Link>
        </nav>

        <div className="min-w-0 pl-2">
          <HealthReadout />
        </div>
      </header>

      <main className="flex min-h-0 flex-1 flex-col">{children}</main>

      <footer className="flex h-10 shrink-0 items-center justify-between gap-4 border-t border-rule bg-bg px-4 sm:px-10 font-mono text-mono-sm text-mute">
        <DataCredits />
        <p className="min-w-0 truncate font-mono text-mono-sm text-mute">
          Open-weight models · SAM 3 · Muse Spark Open
        </p>
      </footer>
    </div>
  );
}
