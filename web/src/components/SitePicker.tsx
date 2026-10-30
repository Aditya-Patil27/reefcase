import type { ReactElement } from "react";
import Map, { Marker } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { BasemapNotice, useBasemap } from "../map/basemap";

export type DiveSite = { lat: number; lon: number };

/** A pin is always somewhere on the globe, whatever a drag, a click or a typed value tried. */
export function clampDiveSite(value: DiveSite): DiveSite {
  return {
    lat: Math.min(90, Math.max(-90, value.lat)),
    lon: Math.min(180, Math.max(-180, value.lon)),
  };
}

/** −14.668 → "14.6680° S"; four decimals so a readout never changes width as the pin moves. */
export function formatLatitude(lat: number): string {
  return `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? "N" : "S"}`;
}

/** 145.461 → "145.4610° E". */
export function formatLongitude(lon: number): string {
  return `${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? "E" : "W"}`;
}

/** The pair on one readout line: "14.6680° S  145.4610° E". */
export function formatCoordinates(value: DiveSite): string {
  return `${formatLatitude(value.lat)}  ${formatLongitude(value.lon)}`;
}

/**
 * A 360px map with one draggable pin. The camera starts on the pin and is left alone after
 * that, so a drag or a typed coordinate never fights the view (initialViewState is uncontrolled).
 * maplibre-gl 6 no longer inlines its worker, so `workerUrl` points at the emitted worker chunk.
 */
export function SitePicker(props: {
  value: DiveSite;
  onChange: (next: DiveSite) => void;
}): ReactElement {
  const { value, onChange } = props;
  const basemap = useBasemap();

  return (
    <div
      role="group"
      aria-label="Dive site map"
      className="relative overflow-hidden border border-border bg-surface"
    >
      <Map
        key={basemap.key}
        {...basemap.mapProps}
        initialViewState={{ longitude: value.lon, latitude: value.lat, zoom: 10 }}
        style={{ width: "100%", height: 360 }}
        dragRotate={false}
        workerUrl={workerUrl}
        onClick={(event) =>
          onChange(clampDiveSite({ lat: event.lngLat.lat, lon: event.lngLat.lng }))
        }
      >
        <Marker
          longitude={value.lon}
          latitude={value.lat}
          draggable
          onDragEnd={(event) =>
            onChange(clampDiveSite({ lat: event.lngLat.lat, lon: event.lngLat.lng }))
          }
        >
          <span
            aria-hidden="true"
            className="block size-5 cursor-grab border-[3px] border-strobe bg-deep shadow-floating active:cursor-grabbing"
          />
        </Marker>
      </Map>
      {basemap.failed ? (
        <BasemapNotice onRetry={basemap.retry}>
          Click or drag to place the pin, or type the coordinates.
        </BasemapNotice>
      ) : null}
    </div>
  );
}
