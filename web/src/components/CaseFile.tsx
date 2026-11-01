import { useQueries } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { FrameView, ToolCallView } from "../live/reducer";
import {
  causeLabel,
  citationKey,
  evidenceLabel,
  humanize,
  isRuledOut,
  modelName,
  splitFirstSentence,
} from "../format";
import { EYEBROW, SECTION_HEADING } from "./marks";

type Investigation = components["schemas"]["Investigation"];
type ToolResult = components["schemas"]["ToolResult"];
export type EvidenceRef = components["schemas"]["EvidenceRef"];
export type EvidenceItem = EvidenceRef;

export interface CaseFileProps {
  investigation: Investigation;
  onOpenEvidence: (evidence: EvidenceRef) => void;
  frames?: FrameView[];
  toolCalls?: ToolCallView[];
  /** A proven alert to show under the verdict. */
  alert?: string | null;
  /** Legacy prop preserved for compatibility */
  showLeadFrame?: boolean;
}

export interface EvidenceChipProps {
  evidence: EvidenceRef;
  label: string;
  keyLabel?: string;
  onOpen: (evidence: EvidenceRef) => void;
}

/** The red mono citation button used by the case file and the trace. */
export function EvidenceChip({
  evidence,
  label,
  keyLabel,
  onOpen,
}: EvidenceChipProps): ReactElement {
  const displayKey = keyLabel ?? label;
  return (
    <button
      type="button"
      aria-label={`Open evidence: ${label}`}
      onClick={() => onOpen(evidence)}
      className="inline-flex cursor-pointer items-baseline font-mono font-semibold text-key-red hover:underline focus:outline-none focus:ring-2 focus:ring-ink"
    >
      <span>{displayKey}</span>
    </button>
  );
}

export function toolNamesByResultId(toolCalls: ToolCallView[]): Record<string, string> {
  const byId: Record<string, string> = {};
  for (const call of toolCalls) {
    if (call.toolResultId) byId[call.toolResultId] = call.tool;
  }
  return byId;
}

type HeatPoint = { alert_level?: number; dhw?: number };

export function useCitedToolResults(investigation: Investigation | undefined): {
  toolCalls: ToolCallView[];
  alert: string | null;
} {
  const ids = new Set<string>();
  const refs = [
    ...(investigation?.findings ?? []).flatMap((finding) => finding.evidence),
    ...(investigation?.hypotheses ?? []).flatMap((hyp) => [
      ...hyp.supporting,
      ...hyp.contradicting,
    ]),
  ];
  for (const ev of refs) {
    if (ev.kind === "tool_result" && ev.id) ids.add(ev.id);
  }
  const results = useQueries({
    queries: [...ids].map((id) => ({
      queryKey: ["tool-result", id],
      queryFn: async (): Promise<ToolResult | null> => {
        const { data } = await api.GET("/api/tool-results/{tool_result_id}", {
          params: { path: { tool_result_id: id } },
        });
        return data ?? null;
      },
      staleTime: Infinity,
    })),
  });

  const toolCalls: ToolCallView[] = [];
  let alert: string | null = null;
  for (const query of results) {
    const result = query.data;
    if (!result) continue;
    toolCalls.push({
      callId: result.id,
      tool: result.tool,
      params: result.params,
      status: "returned",
      toolResultId: result.id,
    });
    if (result.tool !== "heat_stress" || alert) continue;
    const series = (result.data as { series?: HeatPoint[] }).series ?? [];
    const level = Math.max(0, ...series.map((point) => point.alert_level ?? 0));
    const peak = (result.data as { max_dhw?: number }).max_dhw;
    if (level >= 1) {
      alert = `Bleaching alert level ${level}${peak === undefined ? "" : ` · peak ${peak} °C-weeks`}`;
    }
  }
  return { toolCalls, alert };
}

export function CaseFile({
  investigation,
  onOpenEvidence,
  frames = [],
  toolCalls = [],
  alert = null,
}: CaseFileProps): ReactElement {
  const [headline, verdictRest] = splitFirstSentence(investigation.verdict);
  const frameIds = frames.map((f) => f.id);
  const toolResultIds = toolCalls.map((t) => t.toolResultId ?? t.callId);
  const toolByResultId = toolNamesByResultId(toolCalls);

  const getLabel = (ev: EvidenceRef) => evidenceLabel(ev, frameIds, toolByResultId);
  const getKey = (ev: EvidenceRef) => citationKey(ev, frameIds, toolResultIds);

  const renderChips = (refs: EvidenceRef[]) =>
    refs.map((ev) => (
      <EvidenceChip
        key={`chip-${ev.kind}-${ev.id}`}
        evidence={ev}
        label={getLabel(ev)}
        keyLabel={getKey(ev)}
        onOpen={onOpenEvidence}
      />
    ));

  // Partition hypotheses into active and ruled out
  const activeHypotheses = investigation.hypotheses.filter((h) => !isRuledOut(h));
  const ruledOutHypotheses = investigation.hypotheses.filter((h) => isRuledOut(h));

  return (
    <article aria-label="Case file" className="space-y-6 text-ink">
      {/* Proof Header */}
      <section aria-label="Verdict" className="space-y-3">
        <div className={EYEBROW}>CASE FILE · REPORT READY</div>
        <h2 className="font-sans text-verdict font-semibold tracking-tight text-ink">
          {headline}
        </h2>
        {verdictRest ? (
          <p className="font-sans text-body text-ink/90 leading-relaxed">{verdictRest}</p>
        ) : null}
        {alert ? (
          <p className="font-mono text-mono-base font-semibold text-key-red">{alert}</p>
        ) : null}
        <p className="font-mono text-mono-sm text-mute">
          Written by {modelName(investigation.model)}
        </p>
      </section>

      {/* Hypotheses on fixed size ramp */}
      <section aria-labelledby="hypotheses-heading" className="space-y-3 border-t border-ink pt-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 id="hypotheses-heading" className={SECTION_HEADING}>
            Hypotheses
          </h3>
          <p className="font-mono text-mono-sm text-mute">Each cause is scored on its own</p>
        </div>

        <div className="divide-y divide-rule border-b border-rule">
          {activeHypotheses.map((hyp, idx) => {
            const percent = Math.round(hyp.confidence * 100);
            const sizeClass =
              idx === 0
                ? "text-hyp-1"
                : idx === 1
                  ? "text-hyp-2"
                  : "text-hyp-3";

            return (
              <div
                key={hyp.cause}
                className="grid grid-cols-[80px_1fr] items-baseline gap-4 py-3 sm:grid-cols-[96px_1fr]"
              >
                <span
                  className={`font-sans font-semibold tracking-tight text-ink tabular-nums ${sizeClass}`}
                >
                  {percent}%
                </span>
                <div className="space-y-1">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="font-sans text-body font-medium text-ink">
                      {causeLabel(hyp.cause)}
                    </span>
                    {hyp.supporting.length > 0 ? (
                      <span className="inline-flex gap-1.5">{renderChips(hyp.supporting)}</span>
                    ) : null}
                  </div>
                  <p className="font-mono text-mono-sm text-mute">{hyp.rationale}</p>
                  {hyp.contradicting.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-1.5 text-mono-sm font-mono text-mute">
                      <span>Weighed against</span>
                      {renderChips(hyp.contradicting)}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}

          {ruledOutHypotheses.map((hyp) => (
            <div
              key={hyp.cause}
              className="grid grid-cols-[80px_1fr] items-baseline gap-4 py-3 sm:grid-cols-[96px_1fr]"
            >
              <span className="font-mono text-mono-base font-medium text-mute">ruled out</span>
              <div className="space-y-1">
                <div className="flex flex-wrap items-baseline gap-2">
                  <s className="font-sans text-body text-mute decoration-rule">
                    {causeLabel(hyp.cause)}
                  </s>
                  {hyp.supporting.length > 0 ? (
                    <span className="inline-flex gap-1.5">{renderChips(hyp.supporting)}</span>
                  ) : null}
                </div>
                <p className="font-mono text-mono-sm text-mute">{hyp.rationale}</p>
                {hyp.contradicting.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5 text-mono-sm font-mono text-mute">
                    <span>Weighed against</span>
                    {renderChips(hyp.contradicting)}
                  </div>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Tool Trace (T01-T05) */}
      {toolCalls.length > 0 ? (
        <section aria-label="Tool trace" className="space-y-2 font-mono text-mono-base">
          <div className="divide-y divide-rule border-y border-rule">
            {toolCalls.map((call, idx) => {
              const toolResultId = call.toolResultId ?? call.callId;
              const tKey = `T${String(idx + 1).padStart(2, "0")}`;
              const toolEvidence: EvidenceRef = {
                kind: "tool_result",
                id: toolResultId,
              };

              let dataSummary = "";
              if (call.tool === "heat_stress") {
                const maxDhw = (call.params as { max_dhw?: number })?.max_dhw;
                dataSummary = maxDhw !== undefined ? `DHW ${maxDhw}` : "";
              }

              return (
                <div
                  key={call.callId}
                  className="grid grid-cols-[40px_1fr_auto] items-center gap-3 py-1.5"
                >
                  <EvidenceChip
                    evidence={toolEvidence}
                    label={humanize(call.tool)}
                    keyLabel={tKey}
                    onOpen={onOpenEvidence}
                  />
                  <span className="truncate text-ink">{call.tool}</span>
                  <span className="text-mute">{dataSummary}</span>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {/* Findings */}
      <section aria-labelledby="findings-heading" className="space-y-3">
        <h3 id="findings-heading" className={SECTION_HEADING}>
          Findings
        </h3>
        <ol className="divide-y divide-rule border-y border-rule">
          {investigation.findings.map((finding) => {
            const cited = finding.evidence.length > 0;
            return (
              <li key={finding.statement} className="py-2.5 space-y-1.5">
                <p className="font-sans text-body text-ink">{finding.statement}</p>
                {cited ? (
                  <div className="flex flex-wrap gap-2">{renderChips(finding.evidence)}</div>
                ) : (
                  <p className="font-mono text-mono-sm text-mute">No evidence cited yet</p>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      {/* Actions */}
      <section aria-labelledby="actions-heading" className="space-y-3">
        <h3 id="actions-heading" className={SECTION_HEADING}>
          Actions
        </h3>
        <ol className="divide-y divide-rule border-y border-rule">
          {investigation.actions.map((act, idx) => (
            <li key={act} className="flex items-start gap-3 py-2.5">
              <span className="w-5 shrink-0 font-mono text-mono-base font-semibold text-ink">
                {idx + 1}
              </span>
              <span className="font-sans text-body text-ink">{act}</span>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}
