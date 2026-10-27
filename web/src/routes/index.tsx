import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { api } from "../api/client";
import type { components } from "../api/schema";

type SiteSummary = components["schemas"]["SiteSummary"];

export const Route = createFileRoute("/")({
  component: MapRoute,
});

async function fetchSites(): Promise<SiteSummary[]> {
  const { data } = await api.GET("/api/sites");
  return data ?? [];
}

/** Placeholder for the reef map (6.4): a section label and one line of real copy. */
function MapRoute() {
  const sites = useQuery({ queryKey: ["sites"], queryFn: fetchSites });
  const count = sites.data?.length;

  return (
    <section aria-labelledby="sites-heading" className="p-4">
      <h1 id="sites-heading" className="font-mono text-label uppercase text-muted">
        01&nbsp;&nbsp;SITES
      </h1>
      <p className="mt-2 text-body text-secondary">
        {count === undefined
          ? "Reading the site register."
          : `${count} sites in the demo region, from Lizard Island to Tubbataha.`}
      </p>
    </section>
  );
}
