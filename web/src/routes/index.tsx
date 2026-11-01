import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { api, dataOrNull } from "../api/client";
import type { components } from "../api/schema";
import { humanize } from "../format";
import { ReefMap, type LayerVisibility } from "../map/ReefMap";
import { CoverStrip } from "../components/CoverStrip";
import { Switch } from "../components/arc/switch/switch";
import { SECTION_HEADING } from "../components/marks";

type SiteSummary = components["schemas"]["SiteSummary"];

export const Route = createFileRoute("/")({
  component: MapRoute,
});

async function fetchSites(): Promise<SiteSummary[]> {
  return dataOrNull(await api.GET("/api/sites")) ?? [];
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
    // The shell's 56px bar and 35px footer sit outside the map's height.
    <div className="relative flex h-[calc(100dvh-96px)] flex-col-reverse overflow-hidden bg-bg text-ink md:flex-row">
      <aside
        aria-label="Sites and layers"
        className="z-10 flex h-[40vh] w-full shrink-0 flex-col overflow-y-auto border-t border-rule bg-bg md:h-full md:w-80 md:border-t-0 md:border-r"
      >
        <div className="px-4 py-5 sm:px-5">
          <h2 id="sites-heading" className={SECTION_HEADING}>
            Sites
          </h2>
          {sitesQuery.isPending ? (
            <p className="mt-3 font-mono text-mono-sm text-mute">Loading sites…</p>
          ) : sitesQuery.isError ? (
            <p role="alert" className="mt-3 font-sans text-body text-ink">
              Sites did not load. Check the API and reload the page.
            </p>
          ) : sites.length === 0 ? (
            <p className="mt-3 font-sans text-body text-mute">
              No sites yet. Upload a dive to put the first one on the map.
            </p>
          ) : null}

          <div role="list" aria-labelledby="sites-heading" className="mt-3 divide-y divide-rule border-y border-rule">
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
                  className={`-mx-2 cursor-pointer border-l-2 px-2 py-3 transition-colors ${
                    isSelected
                      ? "border-key-red bg-bg"
                      : "border-transparent hover:bg-rule/30"
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="min-w-0 truncate font-sans text-ui font-semibold text-ink">{site.name}</span>
                    <span className="shrink-0 font-mono text-mono-base font-semibold text-ink whitespace-nowrap">{livePercent}% live</span>
                  </div>

                  <p className="mt-0.5 font-mono text-mono-sm text-mute">
                    {humanize(site.trend)} · latest dive {site.latest_dive_date}
                  </p>

                  <div className="mt-1.5">
                    <CoverStrip cover={site.latest_cover} className="h-2 w-full" />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-7">
            <h2 id="layers-heading" className={SECTION_HEADING}>
              Layers
            </h2>

            <div className="mt-3 space-y-3">
              <div className="flex items-center justify-between">
                <label htmlFor="mpa-switch" className="cursor-pointer font-sans text-ui text-mute hover:text-ink">
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
                <label htmlFor="reef-switch" className="cursor-pointer font-sans text-ui text-mute hover:text-ink">
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
                <label htmlFor="vessel-switch" className="cursor-pointer font-sans text-ui text-mute hover:text-ink">
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

      <div className="relative h-[60vh] flex-1 md:h-full">
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
