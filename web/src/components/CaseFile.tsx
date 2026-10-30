import { useQueries } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { FrameView, ToolCallView } from "../live/reducer";
import { evidenceLabel, frameLabel, humanize } from "../format";
import { CHIP, CHIP_ALERT, LIT_RING, RULE_CITED, RULE_PENDING } from "./strobe";

type Investigation = components["schemas"]["Investigation"];
type ToolResult = components["schemas"]["ToolResult"];
export type EvidenceRef = components["schemas"]["EvidenceRef"];
export type EvidenceItem = EvidenceRef;

export interface CaseFileProps {
  investigation: Investigation;
  onOpenEvidence: (evidence: EvidenceRef) => void;
  frames?: FrameView[];
  toolCalls?: ToolCallView[];
  /** A proven alert to show under the verdict, the only red on the page. */
  alert?: string | null;
  /** Shows the most bleached frame beside the verdict; off where frames already sit nearby. */
  showLeadFrame?: boolean;
}

export interface EvidenceChipProps {
  evidence: EvidenceRef;
  label: string;
  onOpen: (evidence: EvidenceRef) => void;
}

/** The one evidence chip used by the case file and the trace. */
export function EvidenceChip({ evidence, label, onOpen }: EvidenceChipProps): ReactElement {
  return (
    <button
      type="button"
      aria-label={`Open evidence: ${label}`}
      onClick={() => onOpen(evidence)}
      className={`${CHIP} transition-colors hover:bg-strobe`}
    >
      {evidence.kind === "frame" ? (
        <span aria-hidden="true" className="size-2 bg-cast" />
      ) : null}
      <span>{label}</span>
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

/**
 * The tool results an investigation cites, fetched once each, for a case file shown outside its
 * live run: `toolCalls` names the chips, and `alert` is the Coral Reef Watch alert from the cited
 * heat_stress result, null until that shows alert level 1 or above.
 */
export function useCitedToolResults(investigation: Investigation | undefined): {
  toolCalls: ToolCallView[];
  alert: string | null;
} {
  const ids = new Set<string>();
  const refs = [
    ...(investigation?.findings ?? []).flatMap((finding) => finding.evidence),
    ...(investigation?.hypotheses ?? []).flatMap((hyp) => [...hyp.supporting, ...hyp.contradicting]),
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

const HEADING = "text-ui font-bold text-fg";

export function CaseFile({
  investigation,
  onOpenEvidence,
  frames = [],
  toolCalls = [],
  alert = null,
  showLeadFrame = true,
}: CaseFileProps): ReactElement {
  const topHypothesis = investigation.hypotheses[0];
  const frameIds = frames.map((f) => f.id);
  const toolByResultId = toolNamesByResultId(toolCalls);
  const label = (ev: EvidenceRef) => evidenceLabel(ev, frameIds, toolByResultId);
  const chips = (refs: EvidenceRef[], prefix: string) =>
    refs.map((ev) => (
      <EvidenceChip
        key={`${prefix}-${ev.kind}-${ev.id}`}
        evidence={ev}
        label={label(ev)}
        onOpen={onOpenEvidence}
      />
    ));

  // The frame that shows the verdict most plainly: the most bleached one.
  const worstFrame = frames.reduce<FrameView | undefined>(
    (worst, f) =>
      f.cover && f.cover.bleached_coral > (worst?.cover?.bleached_coral ?? -1) ? f : worst,
    undefined,
  );

  return (
    <article aria-label="Case file" className="@container space-y-8 text-fg">
      <section aria-label="Verdict" className="grid gap-5 @2xl:grid-cols-[1fr_minmax(0,18rem)]">
        <div className="space-y-3">
          {/* A one-line verdict reads as a headline; a model's paragraph-long one drops to title size. */}
          <h2
            className={
              investigation.verdict.length > 120
                ? "max-w-[60ch] text-title font-bold text-fg"
                : "text-display font-bold text-fg"
            }
          >
            {investigation.verdict}
          </h2>
          {alert ? (
            <p className="flex flex-wrap gap-2">
              <span className={CHIP_ALERT}>{alert}</span>
            </p>
          ) : null}
          {topHypothesis?.rationale ? (
            <p className="text-body text-secondary">{topHypothesis.rationale}</p>
          ) : null}
          <p className="text-label text-muted">Written by {investigation.model}</p>
        </div>

        {showLeadFrame && worstFrame?.thumbUrl && worstFrame.cover ? (
          <figure className="space-y-1.5">
            <button
              type="button"
              aria-label={`Open evidence: ${frameLabel(frameIds, worstFrame.id)}`}
              onClick={() => onOpenEvidence({ kind: "frame", id: worstFrame.id })}
              data-lit="true"
              className={`water-cast block aspect-[4/3] w-full cursor-zoom-in ${LIT_RING}`}
            >
              <img
                src={worstFrame.imageUrl ?? worstFrame.thumbUrl}
                alt=""
                className="size-full object-cover"
              />
              {worstFrame.maskUrl ? (
                <img
                  src={worstFrame.maskUrl}
                  alt=""
                  className="absolute inset-0 size-full object-cover opacity-55"
                />
              ) : null}
            </button>
            <figcaption className="flex justify-between text-label">
              <span className="font-bold text-fg">{frameLabel(frameIds, worstFrame.id)}</span>
              <span className="font-semibold text-fg">
                {Math.round(worstFrame.cover.bleached_coral * 100)}% bleached
              </span>
            </figcaption>
          </figure>
        ) : null}
      </section>

      <section aria-labelledby="hypotheses-heading" className="space-y-3">
        <h3 id="hypotheses-heading" className={HEADING}>
          Hypotheses
        </h3>
        <ul className="space-y-5">
          {investigation.hypotheses.map((hyp) => {
            const percent = Math.round(hyp.confidence * 100);
            return (
              <li key={hyp.cause} className="space-y-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-ui font-bold text-fg">{humanize(hyp.cause)}</span>
                  <span className="text-ui font-bold text-fg">{percent}%</span>
                </div>
                <div className="h-2 w-full bg-sunken">
                  <div className="h-full bg-deep" style={{ width: `${percent}%` }} />
                </div>
                <p className="text-body text-secondary">{hyp.rationale}</p>
                {hyp.supporting.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-label font-semibold text-secondary">Supported by</span>
                    {chips(hyp.supporting, "sup")}
                  </div>
                ) : null}
                {hyp.contradicting.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-label font-semibold text-secondary">Weighed against</span>
                    {chips(hyp.contradicting, "con")}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-labelledby="findings-heading" className="space-y-3">
        <h3 id="findings-heading" className={HEADING}>
          Findings
        </h3>
        <ol className="space-y-4">
          {investigation.findings.map((finding) => {
            const cited = finding.evidence.length > 0;
            return (
              <li key={finding.statement} className={`space-y-2 ${cited ? RULE_CITED : RULE_PENDING}`}>
                <p className="text-body">{finding.statement}</p>
                {cited ? (
                  <div className="flex flex-wrap gap-1.5">{chips(finding.evidence, "ev")}</div>
                ) : (
                  <p className="text-label">No evidence cited yet</p>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      <section aria-labelledby="actions-heading" className="space-y-3">
        <h3 id="actions-heading" className={HEADING}>
          Actions
        </h3>
        <ol className="divide-y divide-hairline border-y border-hairline">
          {investigation.actions.map((act, idx) => (
            <li key={act} className="flex items-start gap-3 py-3">
              <span className="w-5 shrink-0 text-ui font-bold text-fg">{idx + 1}</span>
              <span className="text-body text-fg">{act}</span>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}
