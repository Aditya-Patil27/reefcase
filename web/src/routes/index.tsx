import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { humanize } from "../format";
import { ReefMap, type LayerVisibility } from "../map/ReefMap";
import { CoverStrip } from "../components/CoverStrip";
import { Switch } from "../components/arc/switch/switch";

type SiteSummary = components["schemas"]["SiteSummary"];

export const Route = createFileRoute("/")({
  component: MapRoute,
});

async function fetchSites(): Promise<SiteSummary[]> {
  const { data } = await api.GET("/api/sites");
  return data ?? [];
}

async function fetchGeo(layer: "mpa" | "reef" | "vessels"): Promise<unknown> {
  const { data } = await api.GET("/api/geo/{layer}", {
    params: { path: { layer } },
  });
  return data;
}

function MapRoute() {
  const sitesQuery = useQuery({ queryKey: ["sites"], queryFn: fetchSites });
  const mpaQuery = useQuery({ queryKey: ["geo", "mpa"], queryFn: () => fetchGeo("mpa") });
  const reefQuery = useQuery({ queryKey: ["geo", "reef"], queryFn: () => fetchGeo("reef") });
  const vesselQuery = useQuery({ queryKey: ["geo", "vessel"], queryFn: () => fetchGeo("vessels") });

  const [selectedSite, setSelectedSite] = useState<SiteSummary | null>(null);
  const [layers, setLayers] = useState<LayerVisibility>({
    mpa: true,
    reef: true,
    vessel: true,
  });

  const sites = sitesQuery.data ?? [];

  return (
    <div className="relative flex h-[calc(100vh-48px-32px)] flex-col-reverse md:flex-row bg-bg text-fg overflow-hidden">
      {/* Left panel: 320px desktop, bottom sheet at 40% vh on mobile */}
      <aside
        aria-label="Sites and layers"
        className="z-10 flex h-[40vh] w-full shrink-0 flex-col border-t border-hairline bg-surface/95 md:h-full md:w-80 md:border-r md:border-t-0 overflow-y-auto"
      >
        <div className="p-4">
          <h2 id="sites-heading" className="font-mono text-label uppercase text-muted">
            SITES
          </h2>

          <div role="list" aria-labelledby="sites-heading" className="mt-3 space-y-1">
            {sites.map((site) => {
              const isSelected = selectedSite?.id === site.id;
              const livePercent = Math.round(site.latest_cover.live_coral * 100);

              return (
                <div
                  key={site.id}
                  role="listitem"
                  onClick={() => setSelectedSite(site)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedSite(site);
                    }
                  }}
                  tabIndex={0}
                  aria-current={isSelected ? "true" : undefined}
                  className={`cursor-pointer rounded-sm px-3 py-2 transition-colors ${
                    isSelected ? "bg-raised text-fg" : "text-secondary hover:bg-raised/40 hover:text-fg"
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-ui font-medium text-fg">{site.name}</span>
                  </div>

                  <div className="mt-1 flex items-baseline justify-between gap-2 font-mono text-label tabular-nums">
                    <span className="font-semibold text-fg">{livePercent}% live</span>
                    <span className="text-muted">{humanize(site.trend)}</span>
                  </div>

                  <div className="mt-1.5">
                    <CoverStrip cover={site.latest_cover} className="h-1.5 w-full rounded" />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-6 border-t border-hairline pt-4">
            <h2 id="layers-heading" className="font-mono text-label uppercase text-muted">
              LAYERS
            </h2>

            <div className="mt-3 space-y-3 font-mono text-label">
              <div className="flex items-center justify-between">
                <label htmlFor="mpa-switch" className="cursor-pointer text-body text-secondary hover:text-fg">
                  MPA boundaries
                </label>
                <Switch
                  id="mpa-switch"
                  aria-label="MPA boundaries"
                  checked={layers.mpa}
                  onCheckedChange={(checked) =>
                    setLayers((prev) => ({ ...prev, mpa: checked }))
                  }
                />
              </div>

              <div className="flex items-center justify-between">
                <label htmlFor="reef-switch" className="cursor-pointer text-body text-secondary hover:text-fg">
                  Reef extent
                </label>
                <Switch
                  id="reef-switch"
                  aria-label="Reef extent"
                  checked={layers.reef}
                  onCheckedChange={(checked) =>
                    setLayers((prev) => ({ ...prev, reef: checked }))
                  }
                />
              </div>

              <div className="flex items-center justify-between">
                <label htmlFor="vessel-switch" className="cursor-pointer text-body text-secondary hover:text-fg">
                  Vessel activity
                </label>
                <Switch
                  id="vessel-switch"
                  aria-label="Vessel activity"
                  checked={layers.vessel}
                  onCheckedChange={(checked) =>
                    setLayers((prev) => ({ ...prev, vessel: checked }))
                  }
                />
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main map view: visible above bottom sheet at 390px, fills area to right on desktop */}
      <div className="relative flex-1 h-[60vh] md:h-full">
        <ReefMap
          sites={sites}
          selectedSite={selectedSite}
          onSelectSite={setSelectedSite}
          layers={layers}
          geoData={{
            mpa: mpaQuery.data,
            reef: reefQuery.data,
            vessel: vesselQuery.data,
          }}
        />
      </div>
    </div>
  );
}
