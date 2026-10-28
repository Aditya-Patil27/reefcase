import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { handlers, MOCK_SURVEY_ID } from "./handlers";

const server = setupServer(...handlers);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const origin = "http://localhost";

describe("mock handlers", () => {
  it("serves the provider status", async () => {
    const response = await fetch(`${origin}/api/health`);
    expect(response.status).toBe(200);
    const body = (await response.json()) as { status: string; detail: string };
    expect(body.status).toBe("ok");
    expect(body.detail).toBe("models ok");
  });

  it("serves the eight real reef sites with their coordinates", async () => {
    const response = await fetch(`${origin}/api/sites`);
    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      name: string;
      location: { lat: number; lon: number };
      latest_cover: Record<string, number>;
    }[];

    expect(body).toHaveLength(8);
    expect(body.map((site) => site.name)).toEqual([
      "Lizard Island",
      "Heron Island",
      "Swaraj Dweep, Andaman",
      "Kavaratti, Lakshadweep",
      "Krusadai Island, Gulf of Mannar",
      "Netrani Island",
      "Cape Kri, Raja Ampat",
      "Tubbataha",
    ]);

    const lizard = body[0];
    expect(lizard?.location).toEqual({ lat: -14.668, lon: 145.461 });
    expect(lizard?.latest_cover.live_coral).toBeCloseTo(0.37, 5);
    for (const site of body) {
      const total = Object.values(site.latest_cover).reduce((sum, value) => sum + value, 0);
      expect(total).toBeCloseTo(1, 6);
    }
  });

  it("serves the survey event stream as SSE frames", async () => {
    const response = await fetch(`${origin}/api/surveys/${MOCK_SURVEY_ID}/events`);
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/event-stream");

    const body = await response.text();
    expect(body.match(/^id: /gm)).toHaveLength(41);
    expect(body).toContain("event: report_ready");
    expect(body).toContain(`"survey_id":"${MOCK_SURVEY_ID}"`);
    expect(body.split("\n\n").filter(Boolean)).toHaveLength(41);
    // The mock paces events so the demo streams visibly; reading all 41 takes ~6s.
  }, 20_000);

  it("serves frames, the investigation and a tool result", async () => {
    const frames = await fetch(`${origin}/api/surveys/${MOCK_SURVEY_ID}/frames`);
    expect(frames.status).toBe(200);
    const frameBody = (await frames.json()) as { segmentation: unknown; assessment: unknown }[];
    expect(frameBody).toHaveLength(8);
    expect(frameBody.every((row) => row.segmentation !== null && row.assessment !== null)).toBe(true);

    const investigation = await fetch(`${origin}/api/surveys/${MOCK_SURVEY_ID}/investigation`);
    expect(investigation.status).toBe(200);
    const report = (await investigation.json()) as { id: string; verdict: string };
    expect(report.id).toMatch(/^inv_/);

    const result = await fetch(`${origin}/api/tool-results/tr_01JA7Z5K1B3D5F7H9K1N3Q5S7V`);
    expect(result.status).toBe(200);
    const tool = (await result.json()) as { tool: string; data: { max_dhw: number } };
    expect(tool.tool).toBe("heat_stress");
    expect(tool.data.max_dhw).toBeCloseTo(6.8, 5);
  });

  it("accepts an upload and returns the queued survey", async () => {
    const body = new FormData();
    body.set("video", new Blob(["clip"]), "transect.mp4");
    body.set("lat", "-14.668");
    body.set("lon", "145.461");
    body.set("dive_date", "2026-10-21");

    const response = await fetch(`${origin}/api/surveys`, { method: "POST", body });
    expect(response.status).toBe(201);
    const created = (await response.json()) as { id: string };
    expect(created.id).toBe(MOCK_SURVEY_ID);
  });

  it("rejects an upload with no clip in FastAPI's validation shape", async () => {
    const body = new FormData();
    body.set("lat", "-14.668");
    body.set("lon", "145.461");
    body.set("dive_date", "2026-10-21");

    const response = await fetch(`${origin}/api/surveys`, { method: "POST", body });
    expect(response.status).toBe(422);
    const detail = (await response.json()) as {
      detail: { loc: string[]; msg: string; type: string }[];
    };
    expect(detail.detail).toEqual([
      { loc: ["body", "video"], msg: expect.any(String), type: expect.any(String) },
    ]);
  });

  it("rejects a latitude outside the globe", async () => {
    const body = new FormData();
    body.set("video", new Blob(["clip"]), "transect.mp4");
    body.set("lat", "91");
    body.set("lon", "145.461");
    body.set("dive_date", "2026-10-21");

    const response = await fetch(`${origin}/api/surveys`, { method: "POST", body });
    expect(response.status).toBe(422);
    const detail = (await response.json()) as {
      detail: { loc: string[]; msg: string; type: string }[];
    };
    expect(detail.detail).toEqual([
      { loc: ["body", "lat"], msg: expect.any(String), type: expect.any(String) },
    ]);
  });

  it("rejects a dive date that is not an ISO day", async () => {
    const body = new FormData();
    body.set("video", new Blob(["clip"]), "transect.mp4");
    body.set("lat", "-14.668");
    body.set("lon", "145.461");
    body.set("dive_date", "21/10/2026");

    const response = await fetch(`${origin}/api/surveys`, { method: "POST", body });
    expect(response.status).toBe(422);
    const detail = (await response.json()) as { detail: { loc: string[] }[] };
    expect(detail.detail.map((issue) => issue.loc)).toEqual([["body", "dive_date"]]);
  });

  it("returns 404 for an API path without a handler", async () => {
    const response = await fetch(`${origin}/api/not-a-route`);
    expect(response.status).toBe(404);
  });
});
