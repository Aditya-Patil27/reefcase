import { useState } from "react";
import { Check } from "lucide-react";
import type { ToolCallView } from "../live/reducer";
import type { EventStreamStatus } from "../live/useEventStream";
import type { components } from "../api/schema";
import Alert from "./arc/alert/alert";
import TextShimmer from "./arc/text-shimmer/text-shimmer";
import { EvidenceChip, toolNamesByResultId } from "./CaseFile";
import { evidenceLabel, humanize } from "../format";

type Finding = components["schemas"]["Finding"];

export interface TracePanelProps {
  toolCalls: ToolCallView[];
  findings: Finding[];
  status?: EventStreamStatus;
  reconnectSeq?: number | null;
  /** Frame ids in arrival order, for human chip labels. */
  frameIds?: string[];
  className?: string;
  onSelectEvidence?: (kind: "frame" | "tool_result", id: string) => void;
}

const TOOL_SOURCES: Record<string, { label: string; url: string }> = {
  heat_stress: { label: "NOAA Coral Reef Watch", url: "https://coralreefwatch.noaa.gov" },
  vessel_activity: { label: "Global Fishing Watch", url: "https://globalfishingwatch.org" },
  mpa_boundary: { label: "Protected Planet WDPA", url: "https://protectedplanet.net" },
  reef_map: { label: "Allen Coral Atlas", url: "https://allencoralatlas.org" },
  site_history: { label: "ReefCase History Store", url: "#" },
};

function formatToolIndex(index: number): string {
  return String(index + 1).padStart(2, "0");
}

function formatParamSummary(params: Record<string, unknown>): string {
  const parts: string[] = [];
  if (params.lat !== undefined && params.lon !== undefined) {
    parts.push(`lat ${params.lat} lon ${params.lon}`);
  }
  if (params.radius_km !== undefined) {
    parts.push(`r=${params.radius_km}km`);
  }
  if (params.start && params.end) {
    parts.push(`${params.start} → ${params.end}`);
  }
  if (parts.length === 0) {
    for (const [key, val] of Object.entries(params)) {
      if (typeof val === "string" || typeof val === "number") {
        parts.push(`${key}=${val}`);
      }
    }
  }
  return parts.join(" · ");
}

export function TracePanel({
  toolCalls,
  findings,
  status,
  reconnectSeq,
  frameIds = [],
  className = "",
  onSelectEvidence,
}: TracePanelProps) {
  const [expandedCalls, setExpandedCalls] = useState<Record<string, boolean>>({});
  const toolByResultId = toolNamesByResultId(toolCalls);

  function toggleCall(callId: string) {
    setExpandedCalls((prev) => ({ ...prev, [callId]: !prev[callId] }));
  }

  return (
    <aside aria-labelledby="trace-heading" className={`space-y-6 ${className}`}>
      {status === "reconnecting" && reconnectSeq ? (
        <Alert
          tone="warning"
          title={`Reconnecting… resuming from event ${reconnectSeq}`}
        />
      ) : null}

      <div>
        <h2 id="trace-heading" className="font-mono text-label uppercase text-muted">
          TRACE
        </h2>

        <div className="mt-3 divide-y divide-dashed divide-hairline border-y border-dashed border-hairline">
          {toolCalls.length === 0 ? (
            <p className="py-3 text-body text-muted">Awaiting tool calls from investigator agent…</p>
          ) : (
            toolCalls.map((call, index) => {
              const idxStr = formatToolIndex(index);
              const summary = formatParamSummary(call.params);
              const isExpanded = !!expandedCalls[call.callId];
              const sourceInfo = TOOL_SOURCES[call.tool];

              return (
                <div key={call.callId} className="py-2.5">
                  <button
                    type="button"
                    onClick={() => toggleCall(call.callId)}
                    className="flex w-full items-center justify-between text-left hover:opacity-90"
                    aria-expanded={isExpanded}
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="font-mono text-label text-muted tabular-nums">{idxStr}</span>
                      <span className="text-ui font-medium text-fg">{humanize(call.tool)}</span>
                      <span className="truncate font-mono text-label text-muted">{summary}</span>
                    </div>

                    <div className="shrink-0 pl-2">
                      {call.status === "running" ? (
                        <span className="font-mono text-label text-accent">
                          <TextShimmer active>running</TextShimmer>
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 font-mono text-label text-secondary">
                          <Check size={16} strokeWidth={1.5} className="text-secondary" />
                          <span>done</span>
                        </span>
                      )}
                    </div>
                  </button>

                  {isExpanded && call.summary ? (
                    <div className="mt-2 pl-6 font-mono text-body text-secondary">
                      <p>{call.summary}</p>
                      {sourceInfo ? (
                        <p className="mt-1 text-label text-muted">
                          Source:{" "}
                          <a
                            href={sourceInfo.url}
                            target="_blank"
                            rel="noreferrer"
                            className="underline hover:text-accent"
                          >
                            {sourceInfo.label}
                          </a>
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
      </div>

      {findings.length > 0 ? (
        <div>
          <h3 className="font-mono text-label uppercase text-muted">FINDINGS</h3>
          <ul className="mt-3 divide-y divide-hairline border-y border-hairline">
            {findings.map((f, i) => (
              <li key={i} className="py-3">
                <p className="text-body text-fg">{f.statement}</p>
                {f.evidence && f.evidence.length > 0 ? (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {f.evidence.map((ev) => (
                      <EvidenceChip
                        key={`${ev.kind}-${ev.id}`}
                        evidence={ev}
                        label={evidenceLabel(ev, frameIds, toolByResultId)}
                        onOpen={(e) => onSelectEvidence?.(e.kind as "frame" | "tool_result", e.id)}
                      />
                    ))}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </aside>
  );
}
