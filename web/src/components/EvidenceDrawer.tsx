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

  const frame =
    evidence?.kind === "frame"
      ? frames.find((f) => f.id === evidence.id) ?? {
          id: evidence.id,
          thumbUrl: "/media/frames/01.jpg",
          maskUrl: "/media/masks/01.png",
          cover: {
            live_coral: 0.35,
            bleached_coral: 0.15,
            algae: 0.1,
            rubble: 0.2,
            sand: 0.18,
            other: 0.02,
          },
          assessment: "Assessment not available for this frame.",
        }
      : null;

  const toolResult = toolQuery.data;

  const title =
    evidence?.kind === "frame"
      ? `Frame ${evidence.id}`
      : toolResult
        ? `Tool: ${toolResult.tool}`
        : "Evidence item";

  const description =
    evidence?.kind === "frame"
      ? "Transect frame assessment and segmentation"
      : toolResult
        ? `Retrieved ${toolResult.retrieved_at}`
        : "Investigation evidence inspection";

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

              {/* 16:9 visual */}
              <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-hairline bg-surface">
                {maskMode !== "mask" && frame.thumbUrl ? (
                  <img
                    src={frame.thumbUrl}
                    alt={`Frame ${frame.id}`}
                    className="absolute inset-0 h-full w-full object-cover"
                  />
                ) : null}
                {maskMode !== "frame" && frame.maskUrl ? (
                  <img
                    src={frame.maskUrl}
                    alt={`Mask ${frame.id}`}
                    className="absolute inset-0 h-full w-full object-cover opacity-60 mix-blend-screen"
                  />
                ) : null}
              </div>

              {/* Cover breakdown */}
              {frame.cover ? (
                <div className="space-y-2 rounded-lg border border-hairline bg-surface p-4">
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
                <div className="rounded-lg border border-hairline bg-surface p-4 space-y-2">
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
                          Morphology: <span className="text-fg">{(frame.assessment as any).morphology}</span>
                        </p>
                      ) : null}
                      {(frame.assessment as any).damage ? (
                        <p className="text-secondary">
                          Damage: <span className="text-danger">{(frame.assessment as any).damage}</span>
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
              {/* Source URL link */}
              <div className="rounded-lg border border-hairline bg-surface p-3">
                <span className="font-mono text-label text-muted">Source:</span>
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
                <div className="rounded-lg border border-hairline bg-surface p-2">
                  <JsonViewer data={toolResult.params} />
                </div>
              </div>

              {/* Visualization for heat stress */}
              {toolResult.tool === "heat_stress" && chartData.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="font-mono text-label uppercase text-muted">
                    HEAT STRESS TIMELINE
                  </h4>
                  <div className="rounded-lg border border-hairline bg-surface p-4">
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
                  <div className="rounded-lg border border-hairline bg-surface p-3 font-mono text-label space-y-1">
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
                <div className="rounded-lg border border-hairline bg-surface p-2">
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
