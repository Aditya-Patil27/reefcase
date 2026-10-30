import type { LayerProps } from "react-map-gl/maplibre";
import {
  BORDER_STRONG_HEX,
  MPA_FILL_COLOR,
  REEF_FILL_COLOR,
  STROKE_DARK_HEX,
  VESSEL_CIRCLE_COLOR,
} from "../styles/palette";

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
