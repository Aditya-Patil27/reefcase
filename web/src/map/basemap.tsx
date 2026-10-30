import { useRef, useState, type ReactElement } from "react";
import type { ErrorEvent, StyleSpecification } from "react-map-gl/maplibre";
import { config } from "../config";
import { BUTTON_SECONDARY } from "../components/strobe";
import { SURFACE_HEX } from "../styles/palette";

/** Plain paper with nothing on it: pins and overlays still draw when the basemap can't load. */
const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "paper", type: "background", paint: { "background-color": SURFACE_HEX } }],
};

/**
 * The basemap a `<Map>` draws on. The style is fetched from a third party, so when it fails the
 * map falls back to plain paper and offers a retry instead of staying blank.
 * Spread `mapProps` onto the `<Map>`; `key` remounts it on retry.
 */
export function useBasemap() {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const loaded = useRef(false);

  return {
    key: attempt,
    failed,
    mapProps: {
      mapStyle: failed ? FALLBACK_STYLE : config.BASEMAP_STYLE,
      onLoad: () => {
        loaded.current = true;
      },
      onError: (event: ErrorEvent) => {
        // A tile names its source; an error with none before the first load is the style itself.
        if (!loaded.current && !("sourceId" in event)) setFailed(true);
      },
    },
    retry: () => {
      loaded.current = false;
      setFailed(false);
      setAttempt((n) => n + 1);
    },
  };
}

/** Says the basemap is missing, over the bottom of the map. */
export function BasemapNotice({
  onRetry,
  children,
}: {
  onRetry: () => void;
  children: string;
}): ReactElement {
  return (
    <div
      role="status"
      className="absolute inset-x-3 bottom-3 z-10 flex flex-wrap items-center justify-between gap-3 border border-border bg-raised px-4 py-3 shadow-floating sm:right-auto"
    >
      <p className="text-body text-fg">The basemap didn't load. {children}</p>
      <button type="button" onClick={onRetry} className={BUTTON_SECONDARY}>
        Retry
      </button>
    </div>
  );
}
