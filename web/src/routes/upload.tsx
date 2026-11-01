import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, dataOrNull } from "../api/client";
import type { components } from "../api/schema";
import {
  formatBytes,
  formatDuration,
  uploadSurvey,
  type FieldError,
  type FieldName,
  type UploadProgress,
} from "../api/upload";
import { DatePicker } from "../components/arc/date-picker/date-picker";
import { FileDropzone } from "../components/arc/file-dropzone/file-dropzone";
import { Input } from "../components/arc/input/input";
import { NumberField } from "../components/arc/number-field/number-field";
import { SitePicker, clampDiveSite, formatLatitude, formatLongitude } from "../components/SitePicker";
import { BUTTON_PRIMARY } from "../components/marks";
import { useCrumb } from "../components/crumb";

export const Route = createFileRoute("/upload")({
  component: UploadRoute,
});

type SiteSummary = components["schemas"]["SiteSummary"];

/** Lizard Island, the mock site in docs/agents/ui.md: a real reef for the pin until the sites load. */
const INITIAL_SITE = { lat: -14.668, lon: 145.461 };

/** The site dived most recently, which is where the next clip most likely comes from. */
function latestSite(sites: SiteSummary[] | undefined): SiteSummary | undefined {
  return sites?.reduce<SiteSummary | undefined>(
    (latest, site) => (!latest || site.latest_dive_date > latest.latest_dive_date ? site : latest),
    undefined,
  );
}

/** DOM order, so focus lands on the first invalid field a reader would meet. */
const FIELD_ORDER: readonly FieldName[] = ["video", "lat", "lon", "site_name", "dive_date"];

type FormErrors = Partial<Record<FieldName, string>>;

/** A local day as the `YYYY-MM-DD` the API takes, without a UTC shift. */
function toIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** The checks the form can make itself, in the same shape a 422 arrives in. */
function validate(input: {
  clip: File | null;
  lat: number;
  lon: number;
  diveDate: Date | undefined;
}): FieldError[] {
  const found: FieldError[] = [];
  if (!input.clip) found.push({ field: "video", message: "Choose the dive clip to investigate." });
  if (!(input.lat >= -90 && input.lat <= 90)) {
    found.push({ field: "lat", message: "Latitude must be between 90° S and 90° N." });
  }
  if (!(input.lon >= -180 && input.lon <= 180)) {
    found.push({ field: "lon", message: "Longitude must be between 180° W and 180° E." });
  }
  if (!input.diveDate) found.push({ field: "dive_date", message: "Choose the date of the dive." });
  return found;
}

/** The control to focus for a field: the Arc control's own input, else the field's group. */
function focusField(field: FieldName): void {
  const target =
    document.getElementById(`upload-${field}-input`) ?? document.getElementById(`upload-${field}`);
  target?.focus();
}

/**
 * One labelled field. Arc's number-field, date-picker and dropzone take no error prop, so the
 * group around the control carries `aria-invalid` and owns the message it points at; the
 * `site_name` input renders its own error instead.
 */
function Field(props: { name: FieldName; label: string; error?: string; children: ReactNode }) {
  const { name, label, error, children } = props;
  const errorId = `upload-${name}-error`;

  return (
    <div
      id={`upload-${name}`}
      tabIndex={-1}
      role="group"
      aria-label={label}
      aria-invalid={error ? true : undefined}
      aria-describedby={error ? errorId : undefined}
      className={`grid min-w-0 gap-1.5 outline-none ${error ? "border-l-2 border-key-red pl-3" : ""}`}
    >
      {children}
      {error ? (
        <p id={errorId} className="font-mono text-mono-sm font-semibold text-key-red">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Progress bar and its readout in mono. */
function UploadBar({ progress }: { progress: UploadProgress }) {
  const percent =
    progress.total > 0 ? Math.min(100, Math.round((progress.loaded / progress.total) * 100)) : 0;
  // "18.3 / 43.6 MB": the unit belongs to the total, so the loaded figure loses its own.
  const loaded = formatBytes(progress.loaded).replace(/ (?:MB|KB|B)$/, "");

  return (
    <div className="grid gap-1">
      <div
        role="progressbar"
        aria-label="Upload progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="h-2 w-full overflow-hidden bg-rule"
      >
        <span
          aria-hidden="true"
          className="block h-full origin-left bg-ink motion-safe:transition-transform motion-safe:duration-200"
          style={{ transform: `scaleX(${percent / 100})` }}
        />
      </div>
      <p className="font-mono text-mono-sm font-semibold text-ink">
        {`Uploading ${percent}% · ${loaded} / ${formatBytes(progress.total)}`}
      </p>
    </div>
  );
}

function UploadRoute() {
  const navigate = useNavigate();
  useCrumb("UPLOAD");

  const [clip, setClip] = useState<File | null>(null);
  const [clipUrl, setClipUrl] = useState<string | null>(null);
  const [duration, setDuration] = useState(Number.NaN);
  const clipUrlRef = useRef<string | null>(null);
  const [site, setSite] = useState(INITIAL_SITE);
  const pinPlaced = useRef(false);
  const sitesQuery = useQuery({
    queryKey: ["sites"],
    queryFn: async () => dataOrNull(await api.GET("/api/sites")) ?? [],
  });
  const startSite = latestSite(sitesQuery.data);
  // The pin starts on the latest site once the sites load, unless the diver has already placed it.
  // The map remounts in the same update, so its camera opens on the moved pin, not the default.
  const [mapKey, setMapKey] = useState("initial");
  useEffect(() => {
    if (startSite && !pinPlaced.current) {
      setSite({ lat: startSite.location.lat, lon: startSite.location.lon });
      setMapKey(startSite.id);
    }
  }, [startSite]);
  const [siteName, setSiteName] = useState("");
  const [diveDate, setDiveDate] = useState<Date | undefined>(() => new Date());
  const [errors, setErrors] = useState<FormErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [inFlight, setInFlight] = useState(false);

  // The clip's own URL feeds a hidden <video>, which reports the length once the header is read.
  // It is made and revoked in the event that picks the clip, so no effect has to set state.
  useEffect(() => {
    return () => {
      if (clipUrlRef.current) URL.revokeObjectURL(clipUrlRef.current);
    };
  }, []);

  function chooseClip(files: File[]): void {
    const file = files[0] ?? null;
    if (clipUrlRef.current) URL.revokeObjectURL(clipUrlRef.current);
    clipUrlRef.current = null;
    setClip(file);
    setClipUrl(null);
    setDuration(Number.NaN);
    if (file) {
      const url = URL.createObjectURL(file);
      clipUrlRef.current = url;
      setClipUrl(url);
    }
    clearError("video");
  }

  function clearError(field: FieldName): void {
    setErrors((current) => {
      if (!current[field]) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  function movePin(next: { lat: number; lon: number }): void {
    pinPlaced.current = true;
    setSite(clampDiveSite(next));
    clearError("lat");
    clearError("lon");
  }

  function showErrors(fieldErrors: FieldError[], fallback?: string): void {
    const fields: FormErrors = {};
    const formLevel: string[] = [];
    for (const error of fieldErrors) {
      if (error.field) fields[error.field] = error.message;
      else formLevel.push(error.message);
    }
    setErrors(fields);
    setFormError(
      formLevel.length > 0
        ? formLevel.join(" ")
        : fieldErrors.length === 0
          ? (fallback ?? null)
          : null,
    );
    const first = FIELD_ORDER.find((field) => fields[field]);
    if (first) focusField(first);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (inFlight) return;
    setFormError(null);

    const local = validate({ clip, lat: site.lat, lon: site.lon, diveDate });
    if (local.length > 0) {
      showErrors(local);
      return;
    }
    if (!clip || !diveDate) return;

    setErrors({});
    setProgress({ loaded: 0, total: clip.size });
    setInFlight(true);

    const outcome = await uploadSurvey(
      {
        video: clip,
        lat: site.lat,
        lon: site.lon,
        diveDate: toIsoDate(diveDate),
        siteName,
      },
      { onProgress: setProgress },
    );

    setInFlight(false);
    if (outcome.ok) {
      await navigate({ to: "/surveys/$id", params: { id: outcome.survey.id } });
      return;
    }
    showErrors(outcome.fieldErrors, outcome.message);
  }

  const durationText = formatDuration(duration);

  return (
    <div className="min-h-[calc(100vh-91px)] bg-ground py-10 px-4 sm:px-6">
      <form
        className="mx-auto max-w-[720px] divide-y divide-rule"
        onSubmit={handleSubmit}
        noValidate
      >
        {/* Section 01: Clip */}
        <section aria-labelledby="clip-heading" className="pb-8 space-y-4">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-mono-eyebrow uppercase tracking-wider text-mute">01</span>
            <h1 id="clip-heading" className="font-sans text-title font-bold text-ink">
              Clip
            </h1>
          </div>
          <p className="font-sans text-body text-mute">
            One diver clip from one dive. SAM 3 reads its frames; the agent writes the case file.
          </p>
          <Field name="video" label="Dive clip" error={errors.video}>
            <div className="[&_[data-slot=dropzone]]:border [&_[data-slot=dropzone]]:border-dashed [&_[data-slot=dropzone]]:border-ink [&_[data-slot=dropzone]]:bg-transparent [&_[data-slot=dropzone]]:rounded-none">
              <FileDropzone
                accept="video/*"
                multiple={false}
                maxFiles={1}
                label="Choose a dive clip"
                description="Drop a clip here or choose one from your device"
                note="One clip per survey"
                onFilesChange={(files) => {
                  chooseClip(files);
                }}
              />
            </div>
            {clip ? <p className="font-mono text-mono-sm text-mute">{`Length ${durationText}`}</p> : null}
            {clipUrl ? (
              <video
                className="hidden"
                src={clipUrl}
                preload="metadata"
                aria-hidden="true"
                onLoadedMetadata={(event) => {
                  const { duration: seconds } = event.currentTarget;
                  setDuration(Number.isFinite(seconds) ? seconds : Number.NaN);
                }}
              />
            ) : null}
          </Field>
        </section>

        {/* Section 02: Site */}
        <section aria-labelledby="site-heading" className="py-8 space-y-4">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-mono-eyebrow uppercase tracking-wider text-mute">02</span>
            <h2 id="site-heading" className="font-sans text-title font-bold text-ink">
              Site
            </h2>
          </div>
          <p className="font-sans text-body text-mute">
            Drop the pin where you dived. A pin within 500 m of a known site joins its record.
          </p>
          {/* Keyed on the start site: the map's camera opens on the pin only when it mounts. */}
          <SitePicker key={mapKey} value={site} onChange={movePin} />
          <div className="grid grid-cols-2 gap-3">
            <Field name="lat" label="Latitude" error={errors.lat}>
              <NumberField
                id="upload-lat-input"
                label="Latitude"
                value={site.lat}
                min={-90}
                max={90}
                step={0.0001}
                largeStep={1}
                formatOptions={{ minimumFractionDigits: 4, maximumFractionDigits: 4, useGrouping: false }}
                onValueChange={(lat) => {
                  pinPlaced.current = true;
                  setSite((current) => ({ ...current, lat }));
                  clearError("lat");
                }}
              />
              <p className="font-mono text-mono-sm text-mute">{formatLatitude(site.lat)}</p>
            </Field>
            <Field name="lon" label="Longitude" error={errors.lon}>
              <NumberField
                id="upload-lon-input"
                label="Longitude"
                value={site.lon}
                min={-180}
                max={180}
                step={0.0001}
                largeStep={1}
                formatOptions={{ minimumFractionDigits: 4, maximumFractionDigits: 4, useGrouping: false }}
                onValueChange={(lon) => {
                  pinPlaced.current = true;
                  setSite((current) => ({ ...current, lon }));
                  clearError("lon");
                }}
              />
              <p className="font-mono text-mono-sm text-mute">{formatLongitude(site.lon)}</p>
            </Field>
          </div>
          <Input
            id="upload-site_name-input"
            label="Site name"
            description="Optional"
            placeholder="Lizard Island"
            value={siteName}
            error={errors.site_name}
            onChange={(event) => {
              setSiteName(event.target.value);
              clearError("site_name");
            }}
          />
        </section>

        {/* Section 03: Dive */}
        <section aria-labelledby="dive-heading" className="py-8 space-y-4">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-mono-eyebrow uppercase tracking-wider text-mute">03</span>
            <h2 id="dive-heading" className="font-sans text-title font-bold text-ink">
              Dive
            </h2>
          </div>
          <Field name="dive_date" label="Dive date" error={errors.dive_date}>
            <DatePicker
              id="upload-dive_date-input"
              label="Dive date"
              value={diveDate}
              showToday
              onChange={(date) => {
                setDiveDate(date);
                clearError("dive_date");
              }}
            />
          </Field>
        </section>

        {/* Form actions */}
        <div className="pt-8 space-y-3">
          {formError ? (
            <p role="alert" className="font-sans text-body font-bold text-ink">
              {formError}
            </p>
          ) : null}
          {inFlight && progress ? (
            <UploadBar progress={progress} />
          ) : (
            <button type="submit" disabled={inFlight} className={`${BUTTON_PRIMARY} w-full py-3 text-ui`}>
              Start investigation
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
