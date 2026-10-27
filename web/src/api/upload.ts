import { config } from "../config";
import type { components, paths } from "./schema";

type Survey = components["schemas"]["Survey"];

/** The multipart request body, derived from the generated schema rather than hand-written. */
type CreateSurveyBody = paths["/api/surveys"]["post"]["requestBody"]["content"]["multipart/form-data"];
/** FastAPI's inline validation body, also derived from the generated schema. */
type ValidationErrorBody = paths["/api/surveys"]["post"]["responses"][422]["content"]["application/json"];

/** The fields this form owns; FastAPI may also report another name, or "" for a body-level error. */
export type FieldName = "video" | "lat" | "lon" | "dive_date" | "site_name" | string;

export type UploadInput = {
  video: File;
  lat: number;
  lon: number;
  diveDate: string;
  siteName?: string;
};

export type UploadProgress = { loaded: number; total: number };

export type FieldError = { field: FieldName; message: string };

export type UploadOutcome =
  | { ok: true; survey: Survey }
  | { ok: false; status: number | null; fieldErrors: FieldError[]; message: string };

const UNREACHABLE = "Couldn't reach the ReefCase API. Check the connection and try again.";

function appendField(form: FormData, name: keyof CreateSurveyBody & string, value: string): void {
  form.append(name, value);
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function isSurvey(value: unknown): value is Survey {
  return typeof value === "object" && value !== null && typeof (value as { id?: unknown }).id === "string";
}

/**
 * POSTs one clip and its site as multipart form data. `fetch` reports no upload progress,
 * so this call uses XMLHttpRequest (architecture §7 decision 3).
 */
export function uploadSurvey(
  input: UploadInput,
  options: { onProgress?: (progress: UploadProgress) => void } = {},
): Promise<UploadOutcome> {
  const form = new FormData();
  form.append("video", input.video, input.video.name);
  appendField(form, "lat", String(input.lat));
  appendField(form, "lon", String(input.lon));
  appendField(form, "dive_date", input.diveDate);
  const siteName = input.siteName?.trim();
  if (siteName) appendField(form, "site_name", siteName);

  return new Promise<UploadOutcome>((resolve) => {
    const xhr = new XMLHttpRequest();
    const clipSize = input.video.size;
    let mockTimer: ReturnType<typeof setInterval> | undefined;

    const settle = (outcome: UploadOutcome) => {
      clearInterval(mockTimer);
      resolve(outcome);
    };

    // Mock only: MSW's service worker never fires upload progress events
    // (mswjs.io/guides/recipes/xmlhttprequest-progress-events), so the canned demo climbs
    // to 92% of the clip on its own. Real mode is driven only by xhr.upload.onprogress.
    if (config.MOCK_API) {
      const total = clipSize;
      const ceiling = Math.floor(total * 0.92);
      const step = Math.max(1, Math.round(total * 0.08));
      let loaded = 0;
      mockTimer = setInterval(() => {
        loaded = Math.min(ceiling, loaded + step);
        options.onProgress?.({ loaded, total });
      }, 120);
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) options.onProgress?.({ loaded: event.loaded, total: event.total });
    };

    xhr.onload = () => {
      // Mock only: the demo bar lands on the whole clip as the request completes.
      if (config.MOCK_API) options.onProgress?.({ loaded: clipSize, total: clipSize });

      if (xhr.status === 201) {
        const body = parseJson(xhr.responseText);
        if (isSurvey(body)) {
          settle({ ok: true, survey: body });
          return;
        }
        settle({
          ok: false,
          status: 201,
          fieldErrors: [],
          message: "The ReefCase API accepted the clip but sent no survey back.",
        });
        return;
      }

      if (xhr.status === 422) {
        const body = parseJson(xhr.responseText) as ValidationErrorBody | null;
        const fieldErrors: FieldError[] = (body?.detail ?? []).map((entry) => ({
          // FastAPI leads with the location (`body`), so the field is the last element when
          // there is one; a body-level error (`loc: ["body"]`) belongs to the form itself.
          field: entry.loc.length > 1 ? (entry.loc.at(-1) ?? "") : "",
          message: entry.msg,
        }));
        settle({
          ok: false,
          status: 422,
          fieldErrors,
          message: "Some details of the dive need fixing before the survey can start.",
        });
        return;
      }

      settle({
        ok: false,
        status: xhr.status,
        fieldErrors: [],
        message: `The ReefCase API answered ${xhr.status}. The survey was not started.`,
      });
    };

    xhr.onerror = () => settle({ ok: false, status: null, fieldErrors: [], message: UNREACHABLE });
    xhr.ontimeout = () => settle({ ok: false, status: null, fieldErrors: [], message: UNREACHABLE });

    xhr.open("POST", `${config.API_URL}/api/surveys`);
    xhr.send(form);
  });
}

/** A byte count as a readout, in the decimal units the size text uses: 43600000 → "43.6 MB". */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  if (bytes >= 1_000) return `${Math.round(bytes / 1_000)} KB`;
  return `${Math.round(bytes)} B`;
}

/** A clip length as mm:ss: 62.4 → "01:02". `—` stands in for a clip whose metadata never loaded. */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  const whole = Math.floor(seconds);
  return `${String(Math.floor(whole / 60)).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`;
}
