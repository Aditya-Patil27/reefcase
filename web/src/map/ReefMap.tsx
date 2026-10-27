import { useState, useRef, useEffect, type ReactElement } from "react";
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
import {
  getTrendClass,
  mpaFillLayer,
  mpaLineLayer,
  reefFillLayer,
  vesselCircleLayer,
} from "./layers";

type SiteSummary = components["schemas"]["SiteSummary"];

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
  const mapRef = useRef<MapRef | null>(null);
  const [viewState, setViewState] = useState({
    longitude: 145.461,
    latitude: -14.668,
    zoom: 6,
  });

  // Pan to selected site when selection changes
  useEffect(() => {
    if (selectedSite && mapRef.current) {
      mapRef.current.flyTo({
        center: [selectedSite.location.lon, selectedSite.location.lat],
        duration: 1000,
      });
    }
  }, [selectedSite]);

  return (
    <div
      role="region"
      aria-label="Reef overview map"
      className="relative h-full w-full overflow-hidden bg-bg"
    >
      <Map
        ref={mapRef}
        {...viewState}
        onMove={(evt) => setViewState(evt.viewState)}
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
              <button
                type="button"
                aria-label={site.name}
                className={`group relative flex size-5 items-center justify-center rounded-full transition-transform hover:scale-125 focus:scale-125 ${
                  isSelected ? "scale-125 ring-2 ring-reef-bleached" : ""
                }`}
              >
                <span
                  className={`size-3 rounded-full shadow-sm hover:ring-2 hover:ring-reef-bleached ${getTrendClass(
                    site.trend,
                  )}`}
                />
              </button>
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
              className="w-[280px] rounded-lg border border-hairline bg-surface p-4 text-fg shadow-floating"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-title font-semibold text-fg">{selectedSite.name}</h3>
                  <p className="font-mono text-label text-muted">
                    {formatCoordinates(selectedSite.location)}
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Close"
                  onClick={() => onSelectSite(null)}
                  className="rounded p-1 text-muted hover:text-fg"
                >
                  <X size={14} />
                </button>
              </div>

              <div className="mt-3 flex items-baseline justify-between">
                <span className="text-figure font-bold tabular-nums text-fg">
                  {Math.round(selectedSite.latest_cover.live_coral * 100)}%
                </span>
                <span className="font-mono text-label text-secondary">
                  {selectedSite.latest_dive_date}
                </span>
              </div>

              <div className="mt-2">
                <CoverStrip cover={selectedSite.latest_cover} className="h-2 w-full rounded" />
              </div>

              <div className="mt-4 flex flex-col gap-2 border-t border-hairline pt-3 font-mono text-label">
                <Link
                  to="/sites/$id"
                  params={{ id: selectedSite.id }}
                  className="flex items-center justify-between text-accent hover:underline"
                >
                  <span>Site timeline</span>
                  <span aria-hidden="true">&rarr;</span>
                </Link>
                <Link
                  to="/surveys/$id"
                  params={{ id: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3" }}
                  className="flex items-center justify-between text-secondary hover:text-fg"
                >
                  <span>Latest case file</span>
                  <span aria-hidden="true">&rarr;</span>
                </Link>
              </div>
            </div>
          </Popup>
        ) : null}
      </Map>
    </div>
  );
}
