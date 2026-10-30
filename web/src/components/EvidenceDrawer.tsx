import { useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Drawer, DrawerContent } from "./arc/drawer/drawer";
import { JsonViewer } from "./arc/json-viewer/json-viewer";
import { LineChart } from "./arc/line-chart/line-chart";
import SegmentedControl from "./arc/segmented-control/segmented-control";
import { CoverStrip } from "./CoverStrip";
import { api, dataOrNull } from "../api/client";
import type { components } from "../api/schema";
import type { FrameView } from "../live/reducer";
import { frameLabel, humanize } from "../format";
import { RULE_CITED, SECTION_HEADING as HEADING, TEXT_LINK } from "./strobe";

const LABEL = "text-label font-bold text-secondary";

export type EvidenceRef = components["schemas"]["EvidenceRef"];
export type EvidenceItem = EvidenceRef;
type ToolResult = components["schemas"]["ToolResult"];

/** Coral Reef Watch's Alert Level 1: significant bleaching is likely at 4 °C-weeks and above. */
const BLEACHING_THRESHOLD_DHW = 4;

export interface EvidenceDrawerProps {
  evidence: EvidenceRef | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  frames?: FrameView[];
}

async function fetchToolResult(id: string): Promise<ToolResult | null> {
  return dataOrNull(
    await api.GET("/api/tool-results/{tool_result_id}", {
      params: { path: { tool_result_id: id } },
    }),
  );
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
          threshold: BLEACHING_THRESHOLD_DHW,
        },
      }))
    : [];

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        title={title}
        description={description}
        side="right"
        className="evidence-drawer h-full w-full overflow-y-auto border-l border-hairline bg-raised p-6 text-fg sm:max-w-[480px]"
      >
        <div className="space-y-6 pt-4">
          {evidence?.kind === "frame" && !frame ? (
            <p className="text-body text-secondary">This frame is not loaded yet.</p>
          ) : null}

          {evidence?.kind === "frame" && frame ? (
            <div className="space-y-5">
              {/* Opened under the strobe: true colour, edge to edge across the drawer. */}
              <div className="-mx-6 bg-deep">
                <div data-lit="true" className="water-cast relative aspect-video w-full">
                  {maskMode !== "mask" && frame.thumbUrl ? (
                    <img
                      src={frame.thumbUrl}
                      alt={frameName}
                      className="absolute inset-0 size-full object-cover"
                    />
                  ) : null}
                  {maskMode !== "frame" && frame.maskUrl ? (
                    <img
                      src={frame.maskUrl}
                      alt={`${frameName} mask`}
                      className={`absolute inset-0 size-full object-cover ${maskMode === "both" ? "opacity-55" : ""}`}
                    />
                  ) : null}
                </div>
              </div>

              <div className="flex items-center justify-between gap-3">
                <span className={LABEL}>Show</span>
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
                <div className="space-y-2 border-y border-hairline py-3">
                  <div className="flex items-baseline justify-between">
                    <span className={LABEL}>Benthic cover</span>
                    <span className="text-ui font-bold text-fg">
                      {Math.round(frame.cover.live_coral * 100)}% live coral
                    </span>
                  </div>
                  <CoverStrip cover={frame.cover} className="h-2 w-full" />
                </div>
              ) : null}

              {frame.assessment ? (
                <div className="space-y-2">
                  <h3 className={HEADING}>Assessment</h3>
                  {typeof frame.assessment === "string" ? (
                    <p className="text-body text-fg">{frame.assessment}</p>
                  ) : (
                    <div className="space-y-1 text-body">
                      {(frame.assessment as any).notes ? (
                        <p className="text-fg">{(frame.assessment as any).notes}</p>
                      ) : null}
                      {(frame.assessment as any).bleaching_severity ? (
                        <p className="text-secondary">
                          Severity:{" "}
                          <span className="font-bold text-fg">
                            {humanize(String((frame.assessment as any).bleaching_severity))}
                          </span>
                        </p>
                      ) : null}
                      {(frame.assessment as any).morphology ? (
                        <p className="text-secondary">
                          Morphology:{" "}
                          <span className="text-fg">
                            {[(frame.assessment as any).morphology].flat().join(", ")}
                          </span>
                        </p>
                      ) : null}
                      {(frame.assessment as any).damage ? (
                        <p className="text-secondary">
                          Damage:{" "}
                          <span className="text-fg">
                            {[(frame.assessment as any).damage].flat().join(", ")}
                          </span>
                        </p>
                      ) : null}
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          ) : null}

          {evidence?.kind === "tool_result" && toolQuery.isPending ? (
            <p className="text-body text-secondary">Loading the tool result…</p>
          ) : null}

          {evidence?.kind === "tool_result" && toolQuery.isError ? (
            <p className="text-body text-secondary">This tool result could not be loaded.</p>
          ) : null}

          {evidence?.kind === "tool_result" && toolResult ? (
            <div className="space-y-6">
              <div className={`space-y-1 ${RULE_CITED}`}>
                <span className={`block ${LABEL}`}>Source</span>
                <a
                  href={toolResult.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className={`flex items-start gap-1.5 break-all text-label ${TEXT_LINK}`}
                >
                  <span>{toolResult.source_url}</span>
                  <ExternalLink size={12} aria-hidden="true" className="mt-0.5 shrink-0" />
                </a>
              </div>

              {toolResult.tool === "heat_stress" && chartData.length > 0 ? (
                <div className="space-y-2">
                  <h3 className={HEADING}>Heat stress over time</h3>
                  <div className="border-y border-hairline py-3">
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
                          color: "var(--color-deep)",
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
              (toolResult.data as any)?.sar_detections ? (
                <div className="space-y-2">
                  <h3 className={HEADING}>Radar vessel detections</h3>
                  <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 border-y border-hairline py-3 text-body">
                    <dt className="text-secondary">Not broadcasting AIS</dt>
                    <dd className="font-bold text-fg">
                      {(toolResult.data as any).sar_detections.unmatched_to_ais}
                    </dd>
                    <dt className="text-secondary">All detections within 10 km</dt>
                    <dd className="font-bold text-fg">
                      {(toolResult.data as any).sar_detections.count}
                    </dd>
                  </dl>
                </div>
              ) : null}

              <div className="space-y-2">
                <h3 className={HEADING}>Parameters</h3>
                <div className="border-y border-hairline py-2">
                  <JsonViewer data={toolResult.params} />
                </div>
              </div>

              <div className="space-y-2">
                <h3 className={HEADING}>Result data</h3>
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
