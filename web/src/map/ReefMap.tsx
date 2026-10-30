import { useEffect, useRef, useState, type ReactElement } from "react";
import Map, {
  Marker,
  Source,
  Layer,
  Popup,
  type MapRef,
} from "react-map-gl/maplibre";
import { Link } from "@tanstack/react-router";
import { X } from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { config } from "../config";
import type { components } from "../api/schema";
import { formatCoordinates } from "../components/SitePicker";
import { CoverStrip } from "../components/CoverStrip";
import { BUTTON_PRIMARY, LIT_RING } from "../components/strobe";
import {
  mpaFillLayer,
  mpaLineLayer,
  reefFillLayer,
  vesselCircleLayer,
} from "./layers";

type SiteSummary = components["schemas"]["SiteSummary"];

/** Pins grow with live cover: 14px at none, 22px at 60% and above. */
function pinSize(live: number): number {
  return Math.round(14 + Math.min(live / 0.6, 1) * 8);
}

export interface LayerVisibility {
  mpa: boolean;
  reef: boolean;
  vessel: boolean;
}

export interface ReefMapProps {
  sites: SiteSummary[];
  selectedSite: SiteSummary | null;
  onSelectSite: (site: SiteSummary | null) => void;
  layers: LayerVisibility;
  geoData: {
    mpa: unknown;
    reef: unknown;
    vessel: unknown;
  };
}

export function ReefMap({
  sites,
  selectedSite,
  onSelectSite,
  layers,
  geoData,
}: ReefMapProps): ReactElement {
  // A state ref: maplibre loads lazily, so the map can arrive after the sites do.
  const [map, setMap] = useState<MapRef | null>(null);

  // Open on every site at once, then leave the view to the reader.
  const fitted = useRef(false);
  useEffect(() => {
    if (fitted.current || !map || sites.length === 0) return;
    fitted.current = true;
    const lons = sites.map((site) => site.location.lon);
    const lats = sites.map((site) => site.location.lat);
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: 64, maxZoom: 6, duration: 0 },
    );
  }, [map, sites]);

  // Pan to selected site when selection changes
  useEffect(() => {
    if (selectedSite && map) {
      map.flyTo({
        center: [selectedSite.location.lon, selectedSite.location.lat],
        duration: 1000,
      });
    }
  }, [map, selectedSite]);

  return (
    <div
      role="region"
      aria-label="Reef overview map"
      className="relative h-full w-full overflow-hidden bg-bg"
    >
      <Map
        ref={setMap}
        initialViewState={{ longitude: 145.461, latitude: -14.668, zoom: 6 }}
        mapStyle={config.BASEMAP_STYLE}
        style={{ width: "100%", height: "100%" }}
        dragRotate={false}
        workerUrl={workerUrl}
        onClick={() => onSelectSite(null)}
      >
        {/* MPA boundary layer */}
        {layers.mpa && geoData.mpa ? (
          <Source id="mpa-source" type="geojson" data={geoData.mpa as any}>
            <Layer {...mpaFillLayer} />
            <Layer {...mpaLineLayer} />
          </Source>
        ) : null}

        {/* Reef extent layer */}
        {layers.reef && geoData.reef ? (
          <Source id="reef-source" type="geojson" data={geoData.reef as any}>
            <Layer {...reefFillLayer} />
          </Source>
        ) : null}

        {/* Vessel activity layer */}
        {layers.vessel && geoData.vessel ? (
          <Source id="vessel-source" type="geojson" data={geoData.vessel as any}>
            <Layer {...vesselCircleLayer} />
          </Source>
        ) : null}

        {/* Site markers */}
        {sites.map((site) => {
          const isSelected = selectedSite?.id === site.id;
          const size = pinSize(site.latest_cover.live_coral);
          return (
            <Marker
              key={site.id}
              longitude={site.location.lon}
              latitude={site.location.lat}
              anchor="center"
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                onSelectSite(site);
              }}
            >
              {/* Tailwind needs the hover and focus variants of LIT_RING spelled out to generate them. */}
              <button
                type="button"
                aria-label={site.name}
                aria-pressed={isSelected}
                style={{ width: size, height: size }}
                className={`block border-2 border-raised bg-deep transition-shadow hover:shadow-[0_0_0_3px_var(--strobe),0_0_0_4px_var(--deep)] focus-visible:shadow-[0_0_0_3px_var(--strobe),0_0_0_4px_var(--deep)] focus-visible:outline-none ${
                  isSelected ? LIT_RING : ""
                }`}
              />
            </Marker>
          );
        })}

        {/* Site popover */}
        {selectedSite ? (
          <Popup
            longitude={selectedSite.location.lon}
            latitude={selectedSite.location.lat}
            anchor="bottom"
            offset={14}
            closeButton={false}
            closeOnClick={false}
            onClose={() => onSelectSite(null)}
          >
            <div
              role="dialog"
              aria-label={selectedSite.name}
              className="w-[280px] border border-border bg-raised p-4 text-fg shadow-floating"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-title font-bold text-fg">{selectedSite.name}</h3>
                  <p className="text-label text-secondary">
                    {formatCoordinates(selectedSite.location)}
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Close"
                  onClick={() => onSelectSite(null)}
                  className="p-1 text-secondary hover:bg-accent-subtle hover:text-fg"
                >
                  <X size={16} aria-hidden="true" />
                </button>
              </div>

              <p className="mt-3 flex items-baseline justify-between gap-2">
                <span className="flex items-baseline gap-1.5">
                  <span className="text-figure font-bold text-fg">
                    {Math.round(selectedSite.latest_cover.live_coral * 100)}%
                  </span>
                  <span className="text-ui font-semibold text-fg">live coral</span>
                </span>
                <span className="text-label text-secondary">{selectedSite.latest_dive_date}</span>
              </p>

              <CoverStrip cover={selectedSite.latest_cover} className="mt-2 h-2.5 w-full" />

              <Link
                to="/sites/$id"
                params={{ id: selectedSite.id }}
                className={`${BUTTON_PRIMARY} mt-4 w-full`}
              >
                Open site
              </Link>
            </div>
          </Popup>
        ) : null}
      </Map>
    </div>
  );
}
