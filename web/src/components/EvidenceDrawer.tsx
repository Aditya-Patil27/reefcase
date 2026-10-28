import { useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Drawer, DrawerContent } from "./arc/drawer/drawer";
import { JsonViewer } from "./arc/json-viewer/json-viewer";
import { LineChart } from "./arc/line-chart/line-chart";
import SegmentedControl from "./arc/segmented-control/segmented-control";
import { CoverStrip } from "./CoverStrip";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { FrameView } from "../live/reducer";
import { frameLabel, humanize } from "../format";

export type EvidenceRef = components["schemas"]["EvidenceRef"];
export type EvidenceItem = EvidenceRef;
type ToolResult = components["schemas"]["ToolResult"];

export interface EvidenceDrawerProps {
  evidence: EvidenceRef | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  frames?: FrameView[];
}

async function fetchToolResult(id: string): Promise<ToolResult | null> {
  const { data } = await api.GET("/api/tool-results/{tool_result_id}", {
    params: { path: { tool_result_id: id } },
  });
  return data ?? null;
}

export function EvidenceDrawer({
  evidence,
  open,
  onOpenChange,
  frames = [],
}: EvidenceDrawerProps): ReactElement {
  const [maskMode, setMaskMode] = useState<"frame" | "mask" | "both">("both");

  const toolQuery = useQuery({
    queryKey: ["tool_result", evidence?.id],
    queryFn: () => (evidence?.id ? fetchToolResult(evidence.id) : null),
    enabled: evidence?.kind === "tool_result" && Boolean(evidence.id),
  });

  const frameIds = frames.map((f) => f.id);
  const frame =
    evidence?.kind === "frame" ? frames.find((f) => f.id === evidence.id) ?? null : null;
  const frameName = evidence?.kind === "frame" ? frameLabel(frameIds, evidence.id) : "";

  const toolResult = toolQuery.data;

  const title =
    evidence?.kind === "frame"
      ? frameName
      : toolResult
        ? humanize(toolResult.tool)
        : "Evidence item";

  const description =
    evidence?.kind === "frame"
      ? "Transect frame and its segmentation mask"
      : toolResult
        ? `Retrieved ${toolResult.retrieved_at.slice(0, 16).replace("T", " ")} UTC`
        : "Investigation evidence";

  // Heat stress series data for line chart
  const heatData = (toolResult?.data as any)?.series as
    | Array<{ date: string; dhw: number; sst_anomaly: number }>
    | undefined;

  const chartData = heatData
    ? heatData.map((d) => ({
        key: d.date,
        label: d.date,
        axisLabel: d.date.slice(5),
        values: {
          dhw: d.dhw,
        },
      }))
    : [];

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        title={title}
        description={description}
        side="right"
        className="w-full sm:max-w-[480px] bg-raised border-l border-hairline p-6 text-fg overflow-y-auto h-full"
      >
        <div className="space-y-6 pt-4">
          {/* Frame Evidence View */}
          {evidence?.kind === "frame" && !frame ? (
            <p className="text-body text-secondary">This frame is not loaded yet.</p>
          ) : null}

          {evidence?.kind === "frame" && frame ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-mono text-label text-muted uppercase">
                  Overlay view
                </span>
                <SegmentedControl
                  value={maskMode}
                  onValueChange={(v) => setMaskMode(v as "frame" | "mask" | "both")}
                  options={[
                    { value: "frame", label: "Frame" },
                    { value: "mask", label: "Mask" },
                    { value: "both", label: "Both" },
                  ]}
                />
              </div>

              <div className="relative aspect-video w-full overflow-hidden rounded-sm bg-sunken">
                {maskMode !== "mask" && frame.thumbUrl ? (
                  <img
                    src={frame.thumbUrl}
                    alt={frameName}
                    className="absolute inset-0 h-full w-full object-cover"
                  />
                ) : null}
                {maskMode !== "frame" && frame.maskUrl ? (
                  <img
                    src={frame.maskUrl}
                    alt={`${frameName} mask`}
                    className={`absolute inset-0 h-full w-full object-cover ${maskMode === "both" ? "opacity-55" : ""}`}
                  />
                ) : null}
              </div>

              {/* Cover breakdown */}
              {frame.cover ? (
                <div className="space-y-2 border-y border-hairline py-3">
                  <div className="flex items-center justify-between font-mono text-label text-secondary">
                    <span>Benthic cover</span>
                    <span className="font-semibold text-fg">
                      {Math.round(frame.cover.live_coral * 100)}% live coral
                    </span>
                  </div>
                  <CoverStrip cover={frame.cover} className="h-2 w-full rounded" />
                </div>
              ) : null}

              {/* Assessment */}
              {frame.assessment ? (
                <div className="space-y-2">
                  <h4 className="font-mono text-label uppercase text-muted">
                    Assessment
                  </h4>
                  {typeof frame.assessment === "string" ? (
                    <p className="mt-1 text-body text-fg">{frame.assessment}</p>
                  ) : (
                    <div className="space-y-1 font-mono text-label">
                      {(frame.assessment as any).notes ? (
                        <p className="text-body font-sans text-fg">{(frame.assessment as any).notes}</p>
                      ) : null}
                      {(frame.assessment as any).bleaching_severity ? (
                        <p className="text-secondary">
                          Severity: <span className="text-warning font-semibold">{(frame.assessment as any).bleaching_severity}</span>
                        </p>
                      ) : null}
                      {(frame.assessment as any).morphology ? (
                        <p className="text-secondary">
                          Morphology: <span className="text-fg">{[(frame.assessment as any).morphology].flat().join(", ")}</span>
                        </p>
                      ) : null}
                      {(frame.assessment as any).damage ? (
                        <p className="text-secondary">
                          Damage: <span className="text-danger">{[(frame.assessment as any).damage].flat().join(", ")}</span>
                        </p>
                      ) : null}
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          ) : null}

          {/* Tool Result View */}
          {evidence?.kind === "tool_result" && toolResult ? (
            <div className="space-y-6">
              <div className="border-y border-hairline py-3">
                <span className="font-mono text-label uppercase text-muted">Source</span>
                <a
                  href={toolResult.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 flex items-center gap-1.5 font-mono text-label text-accent hover:underline break-all"
                >
                  <span>{toolResult.source_url}</span>
                  <ExternalLink size={12} className="shrink-0" />
                </a>
              </div>

              {/* Parameters */}
              <div className="space-y-2">
                <h4 className="font-mono text-label uppercase text-muted">
                  PARAMETERS
                </h4>
                <div className="border-y border-hairline py-2">
                  <JsonViewer data={toolResult.params} />
                </div>
              </div>

              {/* Visualization for heat stress */}
              {toolResult.tool === "heat_stress" && chartData.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="font-mono text-label uppercase text-muted">
                    HEAT STRESS TIMELINE
                  </h4>
                  <div className="border-y border-hairline py-3">
                    <LineChart
                      data={chartData}
                      series={[
                        {
                          label: "DHW (°C-weeks)",
                          key: "dhw",
                          color: "var(--color-heat-3)",
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

              {/* Detections summary for vessel activity */}
              {toolResult.tool === "vessel_activity" &&
              (toolResult.data as any)?.sar_detections ? (
                <div className="space-y-2">
                  <h4 className="font-mono text-label uppercase text-muted">
                    SAR DETECTIONS
                  </h4>
                  <div className="space-y-1 border-y border-hairline py-3 font-mono text-label">
                    <p className="text-secondary">
                      Unmatched to AIS:{" "}
                      <span className="text-danger font-semibold">
                        {(toolResult.data as any).sar_detections.unmatched_to_ais}
                      </span>
                    </p>
                    <p className="text-secondary">
                      Total detections inside 10km:{" "}
                      <span className="text-fg font-semibold">
                        {(toolResult.data as any).sar_detections.count}
                      </span>
                    </p>
                  </div>
                </div>
              ) : null}

              {/* Result Data */}
              <div className="space-y-2">
                <h4 className="font-mono text-label uppercase text-muted">
                  RESULT DATA
                </h4>
                <div className="border-y border-hairline py-2">
                  <JsonViewer data={toolResult.data} />
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
