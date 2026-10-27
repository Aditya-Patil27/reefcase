import { afterEach, describe, expect, it, vi } from "vitest";
import type { components } from "./schema";
import {
  formatBytes,
  formatDuration,
  uploadSurvey,
  type UploadInput,
  type UploadProgress,
} from "./upload";
import { config } from "../config";

type Survey = components["schemas"]["Survey"];

const survey: Survey = {
  id: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3",
  site_id: "site_lizard_island",
  dive_date: "2026-10-21",
  status: "queued",
  source: "upload",
  video_path: null,
  cover: null,
  failure_reason: null,
  created_at: "2026-10-21T09:14:00Z",
};

const input: UploadInput = {
  video: new File(["clip"], "transect.mp4", { type: "video/mp4" }),
  lat: -14.668,
  lon: 145.461,
  diveDate: "2026-10-21",
  siteName: "Lizard Island",
};

type ProgressEventLike = { lengthComputable: boolean; loaded: number; total: number };

/** The transport uses XMLHttpRequest for upload progress, so the test drives a fake one. */
class FakeXHR {
  static last: FakeXHR | null = null;

  method = "";
  url = "";
  body: FormData | null = null;
  status = 0;
  responseText = "";
  upload: { onprogress: ((event: ProgressEventLike) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;

  open(method: string, url: string): void {
    this.method = method;
    this.url = url;
  }

  send(body: FormData): void {
    this.body = body;
    FakeXHR.last = this;
  }
}

function respond(xhr: FakeXHR, status: number, body: unknown): void {
  xhr.status = status;
  xhr.responseText = JSON.stringify(body);
  xhr.onload?.();
}

describe("uploadSurvey", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.useRealTimers();
    FakeXHR.last = null;
  });

  it("posts the clip and its site as multipart form data", () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);

    void uploadSurvey(input, {});

    const xhr = FakeXHR.last;
    expect(xhr).not.toBeNull();
    expect(xhr?.method).toBe("POST");
    expect(xhr?.url).toBe(`${config.API_URL}/api/surveys`);

    const body = xhr!.body!;
    const clip = body.get("video");
    expect(clip).toBeInstanceOf(File);
    expect((clip as File).name).toBe("transect.mp4");
    expect(body.get("lat")).toBe("-14.668");
    expect(body.get("lon")).toBe("145.461");
    expect(body.get("dive_date")).toBe("2026-10-21");
    expect(body.get("site_name")).toBe("Lizard Island");
  });

  it("omits the site name when it is blank", () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);

    void uploadSurvey({ ...input, siteName: "   " }, {});

    expect(FakeXHR.last?.body?.get("site_name")).toBeNull();
  });

  it("reports upload progress from the request", () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const progress: UploadProgress[] = [];

    void uploadSurvey(input, { onProgress: (next) => progress.push(next) });
    FakeXHR.last?.upload.onprogress?.({
      lengthComputable: true,
      loaded: 18_300_000,
      total: 43_600_000,
    });

    expect(progress).toEqual([{ loaded: 18_300_000, total: 43_600_000 }]);
  });

  it("resolves with the created survey on 201", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);

    const pending = uploadSurvey(input, {});
    respond(FakeXHR.last!, 201, survey);

    await expect(pending).resolves.toEqual({ ok: true, survey });
  });

  it("maps a 422 body to the field it names", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);

    const pending = uploadSurvey(input, {});
    respond(FakeXHR.last!, 422, {
      detail: [
        { loc: ["body", "lat"], msg: "Input should be less than or equal to 90", type: "less_than_equal" },
        { loc: ["body"], msg: "The clip could not be read.", type: "value_error" },
      ],
    });

    const outcome = await pending;
    expect(outcome.ok).toBe(false);
    if (outcome.ok) return;
    expect(outcome.status).toBe(422);
    expect(outcome.fieldErrors).toEqual([
      { field: "lat", message: "Input should be less than or equal to 90" },
      { field: "", message: "The clip could not be read." },
    ]);
    expect(outcome.message.length).toBeGreaterThan(0);
  });

  it("names the status when the API refuses for another reason", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);

    const pending = uploadSurvey(input, {});
    respond(FakeXHR.last!, 503, { detail: "Pipeline is down." });

    const outcome = await pending;
    expect(outcome).toEqual({
      ok: false,
      status: 503,
      fieldErrors: [],
      message: expect.stringContaining("503"),
    });
  });

  it("reports an unreachable API", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);

    const pending = uploadSurvey(input, {});
    FakeXHR.last?.onerror?.();

    await expect(pending).resolves.toEqual({
      ok: false,
      status: null,
      fieldErrors: [],
      message: "Couldn't reach the ReefCase API. Check the connection and try again.",
    });
  });

  it("reports a timeout as unreachable", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);

    const pending = uploadSurvey(input, {});
    FakeXHR.last?.ontimeout?.();

    await expect(pending).resolves.toMatchObject({
      ok: false,
      status: null,
      message: "Couldn't reach the ReefCase API. Check the connection and try again.",
    });
  });

  it("animates progress in mock mode, where the service worker fires no upload events", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    vi.useFakeTimers();
    vi.resetModules();
    vi.stubEnv("VITE_MOCK_API", "1");
    const mocked = await import("./upload");
    const progress: UploadProgress[] = [];

    const pending = mocked.uploadSurvey(input, { onProgress: (next) => progress.push(next) });
    vi.advanceTimersByTime(480);

    const last = progress.at(-1);
    expect(last?.total).toBe(input.video.size);
    expect(last?.loaded).toBeGreaterThan(0);
    expect(last!.loaded).toBeLessThan(input.video.size);

    respond(FakeXHR.last!, 201, survey);
    await expect(pending).resolves.toMatchObject({ ok: true });
    expect(progress.at(-1)).toEqual({ loaded: input.video.size, total: input.video.size });
  });
});

describe("the readout formatters", () => {
  it("formats a byte count in megabytes", () => {
    expect(formatBytes(43_600_000)).toBe("43.6 MB");
    expect(formatBytes(18_300_000)).toBe("18.3 MB");
  });

  it("formats a clip duration as minutes and seconds", () => {
    expect(formatDuration(62.4)).toBe("01:02");
    expect(formatDuration(0)).toBe("00:00");
  });
});
