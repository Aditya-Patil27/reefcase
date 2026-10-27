import type { LayerProps } from "react-map-gl/maplibre";
import type { components } from "../api/schema";
import {
  BORDER_STRONG_HEX,
  MPA_FILL_COLOR,
  REEF_FILL_COLOR,
  STROKE_DARK_HEX,
  TREND_DECLINING_COLOR,
  TREND_IMPROVING_COLOR,
  TREND_STABLE_COLOR,
  VESSEL_CIRCLE_COLOR,
} from "../styles/palette";

export type SiteTrend = components["schemas"]["SiteTrend"];

export function getTrendColor(trend: SiteTrend): string {
  switch (trend) {
    case "declining":
      return TREND_DECLINING_COLOR;
    case "stable":
      return TREND_STABLE_COLOR;
    case "improving":
      return TREND_IMPROVING_COLOR;
  }
}

export function getTrendClass(trend: SiteTrend): string {
  switch (trend) {
    case "declining":
      return "bg-heat-3";
    case "stable":
      return "bg-reef-sand";
    case "improving":
      return "bg-reef-live";
  }
}

/** MPA layer: dashed border-strong outline over accent-subtle fill */
export const mpaFillLayer: LayerProps = {
  id: "mpa-fill",
  type: "fill",
  paint: {
    "fill-color": MPA_FILL_COLOR,
    "fill-opacity": 0.14,
  },
};

export const mpaLineLayer: LayerProps = {
  id: "mpa-line",
  type: "line",
  paint: {
    "line-color": BORDER_STRONG_HEX,
    "line-width": 1.5,
    "line-dasharray": [2, 2],
  },
};

/** Reef extent: reef-live at 20% opacity */
export const reefFillLayer: LayerProps = {
  id: "reef-fill",
  type: "fill",
  paint: {
    "fill-color": REEF_FILL_COLOR,
    "fill-opacity": 0.2,
  },
};

/** Vessels: vessel dots */
export const vesselCircleLayer: LayerProps = {
  id: "vessel-circle",
  type: "circle",
  paint: {
    "circle-color": VESSEL_CIRCLE_COLOR,
    "circle-radius": 4,
    "circle-stroke-color": STROKE_DARK_HEX,
    "circle-stroke-width": 1,
  },
};
