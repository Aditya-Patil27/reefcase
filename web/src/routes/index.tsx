import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { ReefMap, type LayerVisibility } from "../map/ReefMap";
import { CoverStrip } from "../components/CoverStrip";
import Sparkline from "../components/arc/sparkline/sparkline";
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

function getSparklineData(site: SiteSummary): number[] {
  const live = Math.round(site.latest_cover.live_coral * 100);
  if (site.trend === "declining") {
    return [live + 11, live + 5, live];
  }
  if (site.trend === "improving") {
    return [Math.max(0, live - 8), Math.max(0, live - 4), live];
  }
  return [live - 1, live + 1, live];
}

function getSignedChange(site: SiteSummary): string {
  if (site.trend === "declining") return "-11.4 pp";
  if (site.trend === "improving") return "+5.2 pp";
  return "0.0 pp";
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
        {/* 01 SITES */}
        <div className="p-4">
          <h2 id="sites-heading" className="font-mono text-label uppercase text-muted">
            01&nbsp;&nbsp;SITES
          </h2>

          <div role="list" aria-labelledby="sites-heading" className="mt-3 space-y-1">
            {sites.map((site) => {
              const isSelected = selectedSite?.id === site.id;
              const livePercent = Math.round(site.latest_cover.live_coral * 100);
              const signedChange = getSignedChange(site);
              const tone =
                site.trend === "declining"
                  ? "danger"
                  : site.trend === "improving"
                    ? "success"
                    : "accent";

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
                  className={`cursor-pointer rounded-r-md px-3 py-2 transition-colors ${
                    isSelected
                      ? "border-l-2 border-accent bg-raised text-fg"
                      : "border-l-2 border-transparent hover:bg-raised/40 text-secondary hover:text-fg"
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-ui font-medium text-fg">{site.name}</span>
                  </div>

                  <div className="mt-1 flex items-center justify-between gap-2 font-mono text-label tabular-nums">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-fg">{livePercent}%</span>
                      <span className="text-muted">{signedChange}</span>
                    </div>

                    <div className="w-16">
                      <Sparkline
                        data={getSparklineData(site)}
                        label={`${site.name} trend`}
                        tone={tone}
                        width={64}
                        height={18}
                        area={false}
                        interactive={false}
                      />
                    </div>
                  </div>

                  <div className="mt-1.5">
                    <CoverStrip cover={site.latest_cover} className="h-1.5 w-full rounded" />
                  </div>
                </div>
              );
            })}
          </div>

          {/* 02 LAYERS */}
          <div className="mt-6 border-t border-hairline pt-4">
            <h2 id="layers-heading" className="font-mono text-label uppercase text-muted">
              02&nbsp;&nbsp;LAYERS
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
