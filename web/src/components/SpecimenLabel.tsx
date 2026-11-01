import type { ReactElement } from "react";
import type { FrameView } from "../live/reducer";
import { catalogueNumber, humanize, modelName } from "../format";

export interface SpecimenLabelProps {
  siteName?: string;
  diveDate?: string;
  frameIndex: number;
  frame: FrameView;
  lat?: number;
  lon?: number;
  segBackend?: string;
  className?: string;
}

export function SpecimenLabel({
  siteName = "SITE",
  diveDate = "",
  frameIndex,
  frame,
  lat,
  lon,
  segBackend,
  className = "",
}: SpecimenLabelProps): ReactElement {
  const cat = catalogueNumber(siteName, diveDate, frameIndex);
  // Split catalogue number to highlight F{nn} in red
  const match = cat.match(/^(RC-[A-Z0-9]+-\d{4}-)(F\d{2})$/);
  const catPrefix = match ? match[1] : `RC-${siteName}-F`;
  const catFrame = match ? match[2] : `F${String(frameIndex).padStart(2, "0")}`;

  // Line 2: lat/lon and dive date
  const coords =
    lat !== undefined && lon !== undefined
      ? `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? "N" : "S"} ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? "E" : "W"}`
      : null;
  const line2Parts = [coords, diveDate].filter(Boolean);
  const line2 = line2Parts.length > 0 ? line2Parts.join(" · ") : null;

  // Line 3: morphology and bleaching severity from assessment
  const assessment = frame.assessment;
  let line3: string | null = null;
  if (assessment && typeof assessment === "object") {
    const parts: string[] = [];
    if (assessment.morphology && assessment.morphology.length > 0) {
      parts.push(assessment.morphology.map((m) => humanize(m)).join(", "));
    }
    if (assessment.bleaching_severity !== undefined && assessment.bleaching_severity !== null) {
      parts.push(`severity ${assessment.bleaching_severity}`);
    }
    if (parts.length > 0) {
      line3 = parts.join(", ");
    }
  }

  // Line 4: det. {segmentation backend} / {assessment model}
  const segModel = segBackend ? (segBackend.toLowerCase() === "student" ? "ReefStudent" : "SAM 3") : null;
  const assessModel =
    assessment && typeof assessment === "object" && assessment.model
      ? modelName(assessment.model)
      : null;
  const detParts = [segModel, assessModel].filter(Boolean);
  const line4 = detParts.length > 0 ? `det. ${detParts.join(" / ")}` : null;

  return (
    <div
      className={`absolute left-3.5 bottom-3.5 z-10 w-[330px] max-w-[calc(100%-1.75rem)] bg-label-cream p-2.5 font-mono text-mono-sm text-label-ink select-text ${className}`}
    >
      <b className="block text-body font-semibold tracking-wide">
        <span>{catPrefix}</span>
        <em className="not-italic text-key-red">{catFrame}</em>
      </b>
      {line2 ? <div className="text-mono-sm text-label-ink/80">{line2}</div> : null}
      {line3 ? <div className="text-mono-sm text-label-ink/80">{line3}</div> : null}
      {line4 ? <div className="text-mono-sm text-label-ink/80">{line4}</div> : null}
    </div>
  );
}

