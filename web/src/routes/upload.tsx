import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  formatBytes,
  formatDuration,
  uploadSurvey,
  type FieldError,
  type FieldName,
  type UploadProgress,
} from "../api/upload";
import { Button } from "../components/arc/button/button";
import { DatePicker } from "../components/arc/date-picker/date-picker";
import { FileDropzone } from "../components/arc/file-dropzone/file-dropzone";
import { Input } from "../components/arc/input/input";
import { NumberField } from "../components/arc/number-field/number-field";
import { SitePicker, clampDiveSite, formatLatitude, formatLongitude } from "../components/SitePicker";

export const Route = createFileRoute("/upload")({
  component: UploadRoute,
});

/** Lizard Island, the mock site in docs/agents/ui.md, so the pin starts on a real reef. */
const INITIAL_SITE = { lat: -14.668, lon: 145.461 };

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
      className="grid min-w-0 gap-1 outline-none"
    >
      {children}
      {error ? (
        <p id={errorId} className="text-body text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** A 2px accent bar and the mono readout. Arc's progress draws a 7px track, which this route may not restyle. */
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
        className="h-0.5 w-full overflow-hidden rounded-full bg-sunken"
      >
        <span
          aria-hidden="true"
          className="block h-full origin-left bg-accent motion-safe:transition-transform motion-safe:duration-200"
          style={{ transform: `scaleX(${percent / 100})` }}
        />
      </div>
      <p className="font-mono text-label text-muted tabular-nums">
        {`${percent}% · ${loaded} / ${formatBytes(progress.total)}`}
      </p>
    </div>
  );
}

function UploadRoute() {
  const navigate = useNavigate();
  const [clip, setClip] = useState<File | null>(null);
  const [clipUrl, setClipUrl] = useState<string | null>(null);
  const [duration, setDuration] = useState(Number.NaN);
  const clipUrlRef = useRef<string | null>(null);
  const [site, setSite] = useState(INITIAL_SITE);
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
    <form className="grid gap-4 p-4 lg:grid-cols-2" onSubmit={handleSubmit} noValidate>
      <section aria-labelledby="clip-heading" className="grid min-w-0 content-start gap-3">
        <h1 id="clip-heading" className="font-mono text-label uppercase text-muted">
          CLIP
        </h1>
        <Field name="video" label="Dive clip" error={errors.video}>
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
          {clip ? (
            <div className="mt-1 grid min-w-0 gap-1">
              <p className="truncate text-ui text-fg">{clip.name}</p>
              <p className="font-mono text-label text-muted tabular-nums">
                {`${formatBytes(clip.size)} · ${durationText}`}
              </p>
            </div>
          ) : null}
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

      <section aria-labelledby="site-heading" className="grid min-w-0 content-start gap-3">
        <h2 id="site-heading" className="font-mono text-label uppercase text-muted">
          SITE
        </h2>
        <SitePicker value={site} onChange={movePin} />
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
                setSite((current) => ({ ...current, lat }));
                clearError("lat");
              }}
            />
            <p className="font-mono text-label text-muted tabular-nums">{formatLatitude(site.lat)}</p>
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
                setSite((current) => ({ ...current, lon }));
                clearError("lon");
              }}
            />
            <p className="font-mono text-label text-muted tabular-nums">{formatLongitude(site.lon)}</p>
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

      <div className="grid min-w-0 gap-2 lg:col-span-2">
        {formError ? (
          <p role="alert" className="text-body text-danger">
            {formError}
          </p>
        ) : null}
        {inFlight && progress ? (
          <UploadBar progress={progress} />
        ) : (
          <Button
            type="submit"
            variant="primary"
            disabled={inFlight}
            className="w-full bg-accent! text-on-accent!"
          >
            Start investigation
          </Button>
        )}
      </div>
    </form>
  );
}
