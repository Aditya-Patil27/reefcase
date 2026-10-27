import { http, HttpResponse } from "msw";
import type { components } from "../api/schema";
import events from "./events.json";

type Event = components["schemas"]["Event"];
type SiteSummary = components["schemas"]["SiteSummary"];
type Survey = components["schemas"]["Survey"];
type FrameDetail = components["schemas"]["FrameDetail"];
type ToolResult = components["schemas"]["ToolResult"];
type Investigation = components["schemas"]["Investigation"];
type Health = components["schemas"]["Health"];

/** The mock survey: Lizard Island, dive date 2026-10-21 (docs/agents/ui.md). */
export const MOCK_SURVEY_ID = "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3";
export const MOCK_SITE_ID = "site_lizard_island";

const eventList = events as unknown as Event[];

const lizardCover = {
  live_coral: 0.37,
  bleached_coral: 0.17,
  algae: 0.09,
  rubble: 0.14,
  sand: 0.21,
  other: 0.02,
};

export const sites: SiteSummary[] = [
  {
    id: MOCK_SITE_ID,
    name: "Lizard Island",
    location: { lat: -14.668, lon: 145.461 },
    mpa_id: "mpa_lizard_island_reef",
    latest_cover: lizardCover,
    latest_dive_date: "2026-10-21",
    trend: "declining",
  },
  {
    id: "site_heron_island",
    name: "Heron Island",
    location: { lat: -23.442, lon: 151.914 },
    mpa_id: "mpa_capricorn_bunker",
    latest_cover: {
      live_coral: 0.26,
      bleached_coral: 0.11,
      algae: 0.12,
      rubble: 0.18,
      sand: 0.31,
      other: 0.02,
    },
    latest_dive_date: "2026-09-18",
    trend: "declining",
  },
  {
    id: "site_swaraj_dweep",
    name: "Swaraj Dweep, Andaman",
    location: { lat: 11.98, lon: 93.01 },
    mpa_id: "mpa_mahatma_gandhi_marine",
    latest_cover: {
      live_coral: 0.41,
      bleached_coral: 0.04,
      algae: 0.07,
      rubble: 0.12,
      sand: 0.34,
      other: 0.02,
    },
    latest_dive_date: "2026-03-04",
    trend: "improving",
  },
  {
    id: "site_kavaratti",
    name: "Kavaratti, Lakshadweep",
    location: { lat: 10.563, lon: 72.642 },
    mpa_id: null,
    latest_cover: {
      live_coral: 0.19,
      bleached_coral: 0.06,
      algae: 0.16,
      rubble: 0.21,
      sand: 0.36,
      other: 0.02,
    },
    latest_dive_date: "2026-02-11",
    trend: "stable",
  },
  {
    id: "site_krusadai_island",
    name: "Krusadai Island, Gulf of Mannar",
    location: { lat: 9.247, lon: 79.212 },
    mpa_id: "mpa_gulf_of_mannar",
    latest_cover: {
      live_coral: 0.23,
      bleached_coral: 0.05,
      algae: 0.14,
      rubble: 0.19,
      sand: 0.37,
      other: 0.02,
    },
    latest_dive_date: "2025-12-09",
    trend: "stable",
  },
  {
    id: "site_netrani_island",
    name: "Netrani Island",
    location: { lat: 14.016, lon: 74.33 },
    mpa_id: null,
    latest_cover: {
      live_coral: 0.38,
      bleached_coral: 0.03,
      algae: 0.08,
      rubble: 0.13,
      sand: 0.36,
      other: 0.02,
    },
    latest_dive_date: "2026-01-27",
    trend: "improving",
  },
  {
    id: "site_cape_kri",
    name: "Cape Kri, Raja Ampat",
    location: { lat: -0.556, lon: 130.69 },
    mpa_id: "mpa_raja_ampat",
    latest_cover: {
      live_coral: 0.45,
      bleached_coral: 0.02,
      algae: 0.05,
      rubble: 0.1,
      sand: 0.36,
      other: 0.02,
    },
    latest_dive_date: "2026-04-16",
    trend: "improving",
  },
  {
    id: "site_tubbataha",
    name: "Tubbataha",
    location: { lat: 8.95, lon: 119.87 },
    mpa_id: "mpa_tubbataha_reefs",
    latest_cover: {
      live_coral: 0.31,
      bleached_coral: 0.04,
      algae: 0.09,
      rubble: 0.15,
      sand: 0.39,
      other: 0.02,
    },
    latest_dive_date: "2026-05-02",
    trend: "stable",
  },
];

export const survey: Survey = {
  id: MOCK_SURVEY_ID,
  site_id: MOCK_SITE_ID,
  dive_date: "2026-10-21",
  status: "done",
  source: "upload",
  video_path: `/media/${MOCK_SURVEY_ID}/video.mp4`,
  cover: lizardCover,
  failure_reason: null,
  created_at: "2026-10-21T09:14:00Z",
};

const lizardHistory: Survey[] = [
  survey,
  {
    id: "srv_01J9Q2W8T4Y6C0B2D4F6H8K0M2",
    site_id: MOCK_SITE_ID,
    dive_date: "2024-03-12",
    status: "done",
    source: "historical",
    video_path: null,
    cover: {
      live_coral: 0.48,
      bleached_coral: 0.05,
      algae: 0.08,
      rubble: 0.11,
      sand: 0.26,
      other: 0.02,
    },
    failure_reason: null,
    created_at: "2024-03-12T08:00:00Z",
  },
  {
    id: "srv_01J4P7V2R8X0N6M4K2J0H8G6F4",
    site_id: MOCK_SITE_ID,
    dive_date: "2021-11-03",
    status: "done",
    source: "historical",
    video_path: null,
    cover: {
      live_coral: 0.51,
      bleached_coral: 0.03,
      algae: 0.07,
      rubble: 0.1,
      sand: 0.27,
      other: 0.02,
    },
    failure_reason: null,
    created_at: "2021-11-03T08:00:00Z",
  },
  {
    id: "srv_01J0M5T8Q2W4E6R8Y0U2I4O6P8",
    site_id: MOCK_SITE_ID,
    dive_date: "2019-08-19",
    status: "done",
    source: "historical",
    video_path: null,
    cover: {
      live_coral: 0.54,
      bleached_coral: 0.02,
      algae: 0.06,
      rubble: 0.09,
      sand: 0.27,
      other: 0.02,
    },
    failure_reason: null,
    created_at: "2019-08-19T08:00:00Z",
  },
];

function firstEvent<T extends Event["type"]>(type: T, match: (event: Extract<Event, { type: T }>) => boolean) {
  return eventList.find(
    (event): event is Extract<Event, { type: T }> =>
      event.type === type && match(event as Extract<Event, { type: T }>),
  );
}

function frameDetail(frameId: string, index: number): FrameDetail {
  const scored = firstEvent("frame_scored", (event) => event.frame_id === frameId);
  if (!scored) throw new Error(`No frame_scored event for ${frameId}.`);
  const segmented = firstEvent("segmented", (event) => event.frame_id === frameId);
  const assessed = firstEvent("assessed", (event) => event.assessment.frame_id === frameId);

  return {
    frame: {
      id: frameId,
      survey_id: MOCK_SURVEY_ID,
      t_sec: Number((index * 6.4).toFixed(1)),
      image_path: scored.thumb_url,
      quality: scored.quality,
    },
    segmentation: segmented
      ? {
          id: `seg_${frameId.slice(4)}`,
          frame_id: frameId,
          backend: segmented.backend,
          mask_path: segmented.mask_url,
          cover: segmented.cover,
          latency_ms: 1180 + index * 43,
        }
      : null,
    assessment: assessed ? assessed.assessment : null,
  };
}

const frameIds = eventList.flatMap((event) =>
  event.type === "frame_scored" ? [event.frame_id] : [],
);

export const frames: FrameDetail[] = frameIds.map(frameDetail);

const toolData: Record<string, Record<string, unknown>> = {
  heat_stress: {
    max_dhw: 6.8,
    series: [
      { date: "2026-08-01", dhw: 0.4, sst_anomaly: 0.2, alert_level: 0 },
      { date: "2026-08-22", dhw: 1.9, sst_anomaly: 0.8, alert_level: 0 },
      { date: "2026-09-05", dhw: 3.4, sst_anomaly: 1.1, alert_level: 1 },
      { date: "2026-09-14", dhw: 6.8, sst_anomaly: 1.6, alert_level: 1 },
      { date: "2026-09-28", dhw: 6.1, sst_anomaly: 1.4, alert_level: 1 },
      { date: "2026-10-07", dhw: 4.6, sst_anomaly: 0.9, alert_level: 1 },
      { date: "2026-10-14", dhw: 2.8, sst_anomaly: 0.5, alert_level: 0 },
      { date: "2026-10-21", dhw: 1.2, sst_anomaly: 0.2, alert_level: 0 },
    ],
  },
  vessel_activity: {
    sar_detections: {
      count: 14,
      unmatched_to_ais: 4,
      points: [
        { lat: -14.612, lon: 145.503, date: "2026-09-08" },
        { lat: -14.704, lon: 145.421, date: "2026-09-19" },
        { lat: -14.651, lon: 145.522, date: "2026-10-02" },
        { lat: -14.598, lon: 145.447, date: "2026-10-13" },
      ],
    },
    fishing_hours: 31.4,
  },
  reef_map: {
    geomorphic_zone: "Reef slope",
    benthic_class: "Coral/Algae",
    reef_area_km2_within_1km: 1.8,
  },
  mpa_boundary: {
    inside_mpa: true,
    mpa_name: "Lizard Island Reef",
    no_take: true,
    designation: "IUCN category Ia",
  },
  site_history: {
    surveys: [
      { date: "2019-08-19", live_coral: 0.54 },
      { date: "2021-11-03", live_coral: 0.51 },
      { date: "2024-03-12", live_coral: 0.48 },
      { date: "2026-10-21", live_coral: 0.37 },
    ],
  },
};

const toolSource: Record<string, string> = {
  heat_stress: "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/dhw_5km.html",
  vessel_activity: "https://globalfishingwatch.org/our-apis/documentation/docs/v3/4wings/report",
  reef_map: "https://doi.org/10.5281/zenodo.3833242",
  mpa_boundary: "https://www.protectedplanet.net/",
  site_history: "https://reefcase.local/sites/site_lizard_island",
};

function buildToolResults(): ToolResult[] {
  const calls = new Map<string, Extract<Event, { type: "tool_called" }>>();
  const results: ToolResult[] = [];

  for (const event of eventList) {
    if (event.type === "tool_called") {
      calls.set(event.call_id, event);
      continue;
    }
    if (event.type !== "tool_returned") continue;
    const call = calls.get(event.call_id);
    if (!call) continue;
    results.push({
      id: event.tool_result_id,
      tool: call.tool,
      params: call.params,
      data: toolData[call.tool] ?? {},
      source_url: toolSource[call.tool] ?? "https://reefcase.local/",
      retrieved_at: event.ts,
    });
  }

  return results;
}

export const toolResults: ToolResult[] = buildToolResults();

export const investigation: Investigation = {
  id: "inv_01JA7Z6M0B2D4F6H8K0N2Q4S6V",
  survey_id: MOCK_SURVEY_ID,
  findings: eventList.flatMap((event) => (event.type === "finding" ? [event.finding] : [])),
  hypotheses: [
    {
      cause: "heat_stress",
      confidence: 0.62,
      supporting: [
        { kind: "tool_result", id: toolResults[0]?.id ?? "" },
        { kind: "frame", id: frameIds[5] ?? "" },
      ],
      contradicting: [{ kind: "tool_result", id: toolResults[3]?.id ?? "" }],
      rationale:
        "DHW sat above 4 C-weeks for five weeks and the whitest colonies are the shallow branching ones.",
    },
    {
      cause: "fishing_pressure",
      confidence: 0.24,
      supporting: [
        { kind: "tool_result", id: toolResults[1]?.id ?? "" },
        { kind: "frame", id: frameIds[3] ?? "" },
      ],
      contradicting: [{ kind: "tool_result", id: toolResults[3]?.id ?? "" }],
      rationale:
        "Four unmatched detections inside the no-take boundary, but their tracks stay off the transect.",
    },
  ],
  verdict:
    "Thermal stress drove most of the bleaching; vessel pressure is a secondary, localised signal.",
  actions: [
    "Re-survey the same transect in February 2027.",
    "Ask the reef authority for the September vessel tracks near the no-take line.",
  ],
  uncertain_frames: [frameIds[3] ?? ""],
  model: "Muse Spark Open",
};

const health: Health = {
  status: "ok",
  detail: "models ok",
  providers: {
    segmenter: "sam3",
    assessor: "Muse Spark Open",
    investigator: "Muse Spark Open",
  },
};

const sseBody = eventList
  .map((event) => `id: ${event.seq}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`)
  .join("");

/** 8×8 dark frame, valid PNG, stands in for thumbnails, masks and clips. */
const PIXEL_PNG = Uint8Array.from(
  atob(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEUlEQVR42mMQkVHCihiGlgQA/7EUgft8CDcAAAAASUVORK5CYII=",
  ),
  (char) => char.charCodeAt(0),
);

function notFound(detail: string) {
  return HttpResponse.json({ detail }, { status: 404 });
}

function geoLayer(layer: string) {
  if (layer === "mpa") {
    return {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { name: "Lizard Island Reef", no_take: true },
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [145.42, -14.72],
                [145.51, -14.72],
                [145.51, -14.62],
                [145.42, -14.62],
                [145.42, -14.72],
              ],
            ],
          },
        },
      ],
    };
  }
  if (layer === "reef") {
    return {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { benthic_class: "Coral/Algae" },
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [145.44, -14.69],
                [145.47, -14.69],
                [145.47, -14.65],
                [145.44, -14.65],
                [145.44, -14.69],
              ],
            ],
          },
        },
      ],
    };
  }
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { unmatched_to_ais: true, date: "2026-09-08" },
        geometry: { type: "Point", coordinates: [145.503, -14.612] },
      },
    ],
  };
}

export const handlers = [
  http.get("/api/health", () => HttpResponse.json(health)),

  http.post("/api/surveys", () => HttpResponse.json(survey, { status: 201 })),

  http.get("/api/surveys/:survey_id/events", () => {
    return new HttpResponse(sseBody, {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-store" },
    });
  }),

  http.get("/api/surveys/:survey_id/investigation", () => HttpResponse.json(investigation)),

  http.get("/api/surveys/:survey_id/frames", () => HttpResponse.json(frames)),

  http.get("/api/surveys/:survey_id", ({ params }) => {
    if (params.survey_id !== MOCK_SURVEY_ID) return notFound("No such survey.");
    return HttpResponse.json(survey);
  }),

  http.get("/api/sites", () => HttpResponse.json(sites)),

  http.get("/api/sites/:site_id", ({ params }) => {
    const site = sites.find((candidate) => candidate.id === params.site_id);
    if (!site) return notFound("No such site.");
    return HttpResponse.json({
      site: {
        id: site.id,
        name: site.name,
        location: site.location,
        mpa_id: site.mpa_id,
        created_at: "2019-08-19T08:00:00Z",
      },
      surveys: site.id === MOCK_SITE_ID ? lizardHistory : [survey],
    });
  }),

  http.get("/api/tool-results/:tool_result_id", ({ params }) => {
    const result = toolResults.find((candidate) => candidate.id === params.tool_result_id);
    if (!result) return notFound("No such tool result.");
    return HttpResponse.json(result);
  }),

  http.get("/api/geo/:layer", ({ params }) => HttpResponse.json(geoLayer(String(params.layer)))),

  http.get("/media/*", () => new HttpResponse(PIXEL_PNG, { headers: { "Content-Type": "image/png" } })),

  // A path with no handler returns 404 rather than a network error, so a missing
  // fixture is visible in the UI and in the tests.
  http.all("/api/*", () => notFound("No mock handler for this path.")),
];
