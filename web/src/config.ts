/**
 * Environment-driven settings. Defaults here are the only URLs the app knows;
 * everything else comes from Vite's env (architecture §7).
 */
const env = import.meta.env;

export const config = {
  /** Base URL for the API. Empty means same origin. */
  API_URL: env.VITE_API_URL ?? "",
  /** Serve every route from the MSW fixtures instead of a backend. */
  MOCK_API: env.VITE_MOCK_API === "1",
  /** MapLibre style for the reef map. */
  BASEMAP_STYLE:
    env.VITE_BASEMAP_STYLE ??
    "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
} as const;
