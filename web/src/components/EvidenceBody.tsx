import { useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, ArrowLeft } from "lucide-react";
import SegmentedControl from "./arc/segmented-control/segmented-control";
import { JsonViewer } from "./arc/json-viewer/json-viewer";
import { LineChart } from "./arc/line-chart/line-chart";
import { CoverStrip } from "./CoverStrip";
import { SpecimenLabel } from "./SpecimenLabel";
import { api, dataOrNull } from "../api/client";
import type { components } from "../api/schema";
import type { FrameView } from "../live/reducer";
import { frameLabel, humanize } from "../format";
import { REEF_PALETTE, SEG_CLASS_ORDER, toRgbaString } from "../styles/palette";

type EvidenceRef = components["schemas"]["EvidenceRef"];
type ToolResult = components["schemas"]["ToolResult"];
type Cover = components["schemas"]["Cover"];

const BLEACHING_THRESHOLD_DHW = 4;

export interface EvidenceBodyProps {
  evidence: EvidenceRef | null;
  frames?: FrameView[];
  surveyCover?: Cover | null;
  siteName?: string;
  diveDate?: string;
  lat?: number;
  lon?: number;
  segBackend?: string;
  mode?: "stage" | "drawer";
  onBackToFrame?: () => void;
  className?: string;
}

async function fetchToolResult(id: string): Promise<ToolResult | null> {
  return dataOrNull(
    await api.GET("/api/tool-results/{tool_result_id}", {
      params: { path: { tool_result_id: id } },
    }),
  );
}

export function EvidenceBody({
  evidence,
  frames = [],
  surveyCover,
  siteName = "SITE",
  diveDate = "",
  lat,
  lon,
  segBackend,
  mode = "stage",
  onBackToFrame,
  className = "",
}: EvidenceBodyProps): ReactElement {
  const [maskMode, setMaskMode] = useState<"frame" | "mask" | "both">("both");

  const toolQuery = useQuery({
    queryKey: ["tool_result", evidence?.id],
    queryFn: () => (evidence?.id ? fetchToolResult(evidence.id) : null),
    enabled: evidence?.kind === "tool_result" && Boolean(evidence.id),
  });

  const toolResult = toolQuery.data;
  const frameIds = frames.map((f) => f.id);
  const frameIndex =
    evidence?.kind === "frame" ? frames.findIndex((f) => f.id === evidence.id) : -1;
  const frame = frameIndex >= 0 ? frames[frameIndex] : frames[0];
  const frameAlt = frame ? (frameLabel(frameIds, frame.id)) : "Frame";

  const heatData = (toolResult?.data as { series?: Array<{ date: string; dhw: number; sst_anomaly: number }> })
    ?.series;

  const chartData = heatData
    ? heatData.map((d) => ({
        key: d.date,
        label: d.date,
        axisLabel: d.date.slice(5),
        values: {
          dhw: d.dhw,
          threshold: BLEACHING_THRESHOLD_DHW,
        },
      }))
    : [];

  // When evidence is a frame
  if (evidence?.kind === "frame" || (!evidence && frame)) {
    if (!frame) {
      return (
        <div className={`flex items-center justify-center p-12 text-stage-mute font-mono ${className}`}>
          Waiting for frames
        </div>
      );
    }

    const currentLivePercent = Math.round((frame.cover?.live_coral ?? 0) * 100);
    const sortedFrames = [...frames].sort(
      (a, b) => (b.cover?.live_coral ?? 0) - (a.cover?.live_coral ?? 0),
    );
    const rank = sortedFrames.findIndex((f) => f.id === frame.id) + 1;
    const rankText =
      rank === 1
        ? `highest of ${frames.length}`
        : rank === frames.length && frames.length > 1
          ? `lowest of ${frames.length}`
          : `#${rank} of ${frames.length}`;

    const meanLive =
      surveyCover?.live_coral ??
      (frames.length > 0
        ? frames.reduce((acc, f) => acc + (f.cover?.live_coral ?? 0), 0) / frames.length
        : 0);
    const meanPercent = (meanLive * 100).toFixed(1);

    if (mode === "stage") {
      return (
        <div
          className={`grid h-[590px] grid-cols-1 gap-5 bg-stage-bg p-5 text-stage-fg @container lg:grid-cols-[560px_1fr] ${className}`}
        >
          {/* Frame viewer with specimen label */}
          <div className="relative flex flex-col justify-between overflow-hidden bg-stage-rule">
            <div className="relative size-full overflow-hidden">
              {maskMode !== "mask" && (frame.imageUrl || frame.thumbUrl) ? (
                <img
                  src={frame.imageUrl || frame.thumbUrl}
                  alt={`${frameAlt} stage`}
                  className="size-full object-contain"
                />
              ) : null}
              {maskMode !== "frame" && frame.maskUrl ? (
                <img
                  src={frame.maskUrl}
                  alt={`${frameAlt} stage mask`}
                  className={`absolute inset-0 size-full object-contain ${
                    maskMode === "both" ? "opacity-55" : ""
                  }`}
                />
              ) : null}

              {/* Specimen Label on bottom-left corner */}
              <SpecimenLabel
                siteName={siteName}
                diveDate={diveDate}
                frameIndex={frameIndex >= 0 ? frameIndex + 1 : 1}
                frame={frame}
                lat={lat}
                lon={lon}
                segBackend={segBackend}
              />
            </div>

            {/* SegmentedControl in top-right */}
            <div className="absolute top-3 right-3 z-20">
              <SegmentedControl
                value={maskMode}
                onValueChange={(v) => setMaskMode(v as "frame" | "mask" | "both")}
                label="Display mode"
                options={[
                  { value: "frame", label: "Frame" },
                  { value: "mask", label: "Mask" },
                  { value: "both", label: "Both" },
                ]}
              />
            </div>
          </div>

          {/* Side panel */}
          <div className="flex flex-col justify-between overflow-y-auto space-y-6 text-stage-fg">
            <div>
              <h4 className="font-mono text-mono-eyebrow uppercase tracking-wider text-stage-mute mb-2">
                Live coral, this frame ({frameAlt})
              </h4>
              <div className="font-sans text-figure-lg font-semibold tracking-tight text-stage-fg-bright">
                {frame.cover ? `${currentLivePercent}%` : "—"}
                <small className="block font-sans text-mono-sm font-normal text-stage-mute tracking-normal mt-1.5">
                  {rankText} · survey mean {meanPercent}%
                </small>
              </div>
            </div>

            {frame.cover ? (
              <div>
                <h4 className="font-mono text-mono-eyebrow uppercase tracking-wider text-stage-mute mb-2">
                  Cover
                </h4>
                <div className="grid grid-cols-[12px_1fr_auto] items-center gap-x-2.5 gap-y-1.5 text-body">
                  {SEG_CLASS_ORDER.map((cls) => {
                    const frac = frame.cover ? frame.cover[cls] ?? 0 : 0;
                    const pct = Math.round(frac * 100);
                    const color = toRgbaString(REEF_PALETTE[cls]);
                    return (
                      <span key={cls} className="contents">
                        <i
                          style={{ backgroundColor: color }}
                          className="size-3 inline-block shrink-0"
                          aria-hidden="true"
                        />
                        <span className="text-stage-fg capitalize">{cls.replace(/_/g, " ")}</span>
                        <span className="font-mono text-mono-base text-stage-fg-bright tabular-nums">
                          {pct}%
                        </span>
                      </span>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {frame.assessment ? (
              <div>
                <h4 className="font-mono text-mono-eyebrow uppercase tracking-wider text-stage-mute mb-2">
                  Assessment
                </h4>
                <div className="space-y-1 font-sans text-mono-sm text-stage-fg">
                  {frame.assessment.notes ? (
                    <p className="text-stage-fg-bright">{frame.assessment.notes}</p>
                  ) : null}
                  {frame.assessment.bleaching_severity !== undefined ? (
                    <p className="text-stage-mute">
                      Severity:{" "}
                      <span className="text-stage-fg font-medium">
                        {frame.assessment.bleaching_severity}
                      </span>
                    </p>
                  ) : null}
                  {frame.assessment.morphology?.length ? (
                    <p className="text-stage-mute">
                      Morphology:{" "}
                      <span className="text-stage-fg">
                        {frame.assessment.morphology.map((m) => humanize(m)).join(", ")}
                      </span>
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      );
    }

    // Drawer mode
    return (
      <div className={`space-y-5 ${className}`}>
        <div className="relative aspect-video w-full overflow-hidden bg-stage-rule">
          {maskMode !== "mask" && (frame.imageUrl || frame.thumbUrl) ? (
            <img
              src={frame.imageUrl || frame.thumbUrl}
              alt={frameAlt}
              className="size-full object-contain"
            />
          ) : null}
          {maskMode !== "frame" && frame.maskUrl ? (
            <img
              src={frame.maskUrl}
              alt={`${frameAlt} mask`}
              className={`absolute inset-0 size-full object-contain ${
                maskMode === "both" ? "opacity-55" : ""
              }`}
            />
          ) : null}
        </div>

        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-mono-sm text-mute">Show</span>
          <SegmentedControl
            value={maskMode}
            onValueChange={(v) => setMaskMode(v as "frame" | "mask" | "both")}
            label="Display mode"
            options={[
              { value: "frame", label: "Frame" },
              { value: "mask", label: "Mask" },
              { value: "both", label: "Both" },
            ]}
          />
        </div>

        {frame.cover ? (
          <div className="space-y-2 border-y border-rule py-3">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-mono-sm text-mute">Benthic cover</span>
              <span className="font-mono text-mono-base font-semibold text-ink">
                {currentLivePercent}% live coral
              </span>
            </div>
            <CoverStrip cover={frame.cover} className="h-2 w-full" />
          </div>
        ) : null}

        {frame.assessment ? (
          <div className="space-y-2">
            <h3 className="font-sans text-ui font-semibold text-ink">Assessment</h3>
            <div className="space-y-1 text-body">
              {frame.assessment.notes ? <p className="text-ink">{frame.assessment.notes}</p> : null}
              {frame.assessment.bleaching_severity !== undefined ? (
                <p className="text-mute">
                  Severity:{" "}
                  <span className="font-semibold text-ink">
                    {humanize(String(frame.assessment.bleaching_severity))}
                  </span>
                </p>
              ) : null}
              {frame.assessment.morphology?.length ? (
                <p className="text-mute">
                  Morphology:{" "}
                  <span className="text-ink">
                    {frame.assessment.morphology.map((m) => humanize(m)).join(", ")}
                  </span>
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  // When evidence is a tool result
  return (
    <div
      className={
        mode === "stage"
          ? `h-[590px] overflow-y-auto bg-stage-bg p-6 text-stage-fg space-y-6 ${className}`
          : `space-y-6 ${className}`
      }
    >
      {onBackToFrame ? (
        <div className="flex items-center justify-between border-b border-stage-rule pb-3">
          <button
            type="button"
            onClick={onBackToFrame}
            className="inline-flex items-center gap-1.5 font-mono text-mono-sm text-stage-mute hover:text-stage-fg-bright cursor-pointer focus:outline-none focus:ring-1 focus:ring-stage-fg"
          >
            <ArrowLeft size={14} aria-hidden="true" />
            <span>Back to frame</span>
          </button>
          <span className="font-mono text-mono-sm text-stage-mute">
            {toolResult?.retrieved_at ? `Retrieved ${toolResult.retrieved_at.slice(0, 10)}` : ""}
          </span>
        </div>
      ) : null}

      {toolQuery.isPending ? (
        <p className="font-mono text-mono-base text-stage-mute">Loading tool result…</p>
      ) : null}

      {toolQuery.isError ? (
        <p className="font-mono text-mono-base text-stage-mute">This tool result could not be loaded.</p>
      ) : null}

      {toolResult ? (
        <div className="space-y-6">
          <div>
            <span className="block font-mono text-mono-eyebrow uppercase tracking-wider text-stage-mute mb-1">
              Source
            </span>
            <a
              href={toolResult.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-mono text-mono-sm text-stage-fg hover:underline break-all"
            >
              <span>{toolResult.source_url}</span>
              <ExternalLink size={12} aria-hidden="true" className="shrink-0" />
            </a>
          </div>

          {toolResult.tool === "heat_stress" && chartData.length > 0 ? (
            <div className="space-y-2">
              <h3 className="font-sans text-ui font-semibold text-stage-fg-bright">
                Heat stress over time
              </h3>
              <div className="border-y border-stage-rule py-3">
                <LineChart
                  data={chartData}
                  series={[
                    {
                      label: "DHW (°C-weeks)",
                      key: "dhw",
                      color: "var(--color-heat-3)",
                      area: false,
                    },
                    {
                      label: `Bleaching threshold, ${BLEACHING_THRESHOLD_DHW} °C-weeks`,
                      key: "threshold",
                      color: "var(--color-fg)",
                      dashed: true,
                      area: false,
                    },
                  ]}
                  label="Degree Heating Weeks"
                  unit=" C-w"
                  height={180}
                  curve="smooth"
                />
              </div>
            </div>
          ) : null}

          {toolResult.tool === "vessel_activity" &&
          (toolResult.data as { sar_detections?: { unmatched_to_ais?: { count?: number }; total?: number } })
            ?.sar_detections ? (
            <div className="space-y-2">
              <h3 className="font-sans text-ui font-semibold text-stage-fg-bright">
                Radar vessel detections
              </h3>
              <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 border-y border-stage-rule py-3 text-body font-mono">
                <dt className="text-stage-mute">Not broadcasting AIS</dt>
                <dd className="font-semibold text-stage-fg-bright">
                  {(toolResult.data as any).sar_detections.unmatched_to_ais?.count ?? 0}
                </dd>
                <dt className="text-stage-mute">All detections within 10 km</dt>
                <dd className="font-semibold text-stage-fg-bright">
                  {(toolResult.data as any).sar_detections.total ?? 0}
                </dd>
              </dl>
            </div>
          ) : null}

          <div className="space-y-2">
            <h3 className="font-sans text-ui font-semibold text-stage-fg-bright">Parameters</h3>
            <div className="border-y border-stage-rule py-2">
              <JsonViewer data={toolResult.params} />
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="font-sans text-ui font-semibold text-stage-fg-bright">Result data</h3>
            <div className="border-y border-stage-rule py-2">
              <JsonViewer data={toolResult.data} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

