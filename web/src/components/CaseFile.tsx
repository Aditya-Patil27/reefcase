import type { ReactElement } from "react";
import type { components } from "../api/schema";
import type { FrameView, ToolCallView } from "../live/reducer";
import { evidenceLabel, frameLabel, humanize } from "../format";

type Investigation = components["schemas"]["Investigation"];
export type EvidenceRef = components["schemas"]["EvidenceRef"];
export type EvidenceItem = EvidenceRef;

export interface CaseFileProps {
  investigation: Investigation;
  onOpenEvidence: (evidence: EvidenceRef) => void;
  frames?: FrameView[];
  toolCalls?: ToolCallView[];
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
      className="inline-flex items-center gap-1.5 rounded-sm border border-hairline px-1.5 py-0.5 font-mono text-label text-secondary transition-colors hover:border-accent hover:text-fg"
    >
      {evidence.kind === "frame" ? (
        <span aria-hidden="true" className="size-1.5 rounded-full bg-accent" />
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

const HEADING = "font-mono text-label uppercase text-muted";

export function CaseFile({
  investigation,
  onOpenEvidence,
  frames = [],
  toolCalls = [],
}: CaseFileProps): ReactElement {
  const topHypothesis = investigation.hypotheses[0];
  const frameIds = frames.map((f) => f.id);
  const toolByResultId = toolNamesByResultId(toolCalls);
  const label = (ev: EvidenceRef) => evidenceLabel(ev, frameIds, toolByResultId);

  // The frame that shows the verdict most plainly: the most bleached one.
  const worstFrame = frames.reduce<FrameView | undefined>(
    (worst, f) =>
      f.cover && f.cover.bleached_coral > (worst?.cover?.bleached_coral ?? -1) ? f : worst,
    undefined,
  );

  return (
    <article aria-label="Case file" className="space-y-8 text-fg">
      <section aria-label="Verdict" className="grid gap-4 sm:grid-cols-[1fr_minmax(0,16rem)]">
        <div>
          <h2 className="text-display font-semibold leading-tight text-fg">
            {investigation.verdict}
          </h2>
          {topHypothesis?.rationale ? (
            <p className="mt-2 text-body text-secondary">{topHypothesis.rationale}</p>
          ) : null}
        </div>

        {worstFrame?.thumbUrl && worstFrame.cover ? (
          <figure className="space-y-1.5">
            <button
              type="button"
              aria-label={`Open evidence: ${frameLabel(frameIds, worstFrame.id)}`}
              onClick={() => onOpenEvidence({ kind: "frame", id: worstFrame.id })}
              className="relative block aspect-video w-full overflow-hidden rounded-sm bg-sunken"
            >
              <img src={worstFrame.thumbUrl} alt="" className="size-full object-cover" />
              {worstFrame.maskUrl ? (
                <img
                  src={worstFrame.maskUrl}
                  alt=""
                  className="absolute inset-0 size-full object-cover opacity-55"
                />
              ) : null}
            </button>
            <figcaption className="flex justify-between font-mono text-label tabular-nums">
              <span className="text-secondary">{frameLabel(frameIds, worstFrame.id)}</span>
              <span className="text-fg">
                {Math.round(worstFrame.cover.bleached_coral * 100)}% bleached
              </span>
            </figcaption>
          </figure>
        ) : null}
      </section>

      <section aria-labelledby="findings-heading" className="space-y-3">
        <h3 id="findings-heading" className={HEADING}>
          FINDINGS
        </h3>
        <ol className="divide-y divide-hairline border-y border-hairline">
          {investigation.findings.map((finding, idx) => (
            <li key={finding.statement} className="flex items-start gap-3 py-3">
              <span className="font-mono text-label text-muted tabular-nums">
                {String(idx + 1).padStart(2, "0")}
              </span>
              <div className="flex-1 space-y-2">
                <p className="text-body leading-relaxed text-fg">{finding.statement}</p>
                {finding.evidence.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {finding.evidence.map((ev) => (
                      <EvidenceChip
                        key={`${ev.kind}-${ev.id}`}
                        evidence={ev}
                        label={label(ev)}
                        onOpen={onOpenEvidence}
                      />
                    ))}
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="hypotheses-heading" className="space-y-3">
        <h3 id="hypotheses-heading" className={HEADING}>
          HYPOTHESES
        </h3>
        <ul className="divide-y divide-hairline border-y border-hairline">
          {investigation.hypotheses.map((hyp) => {
            const percent = Math.round(hyp.confidence * 100);
            return (
              <li key={hyp.cause} className="space-y-2 py-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-body font-semibold text-fg">{humanize(hyp.cause)}</span>
                  <span className="font-mono text-label font-semibold text-fg tabular-nums">
                    {percent}%
                  </span>
                </div>
                <div className="h-1 w-full overflow-hidden bg-sunken">
                  <div className="h-full bg-accent" style={{ width: `${percent}%` }} />
                </div>
                <p className="text-body text-secondary">{hyp.rationale}</p>
                {hyp.supporting.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-mono text-label text-muted">Supported by</span>
                    {hyp.supporting.map((ev) => (
                      <EvidenceChip
                        key={`sup-${ev.kind}-${ev.id}`}
                        evidence={ev}
                        label={label(ev)}
                        onOpen={onOpenEvidence}
                      />
                    ))}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-labelledby="actions-heading" className="space-y-3">
        <h3 id="actions-heading" className={HEADING}>
          ACTIONS
        </h3>
        <ol className="divide-y divide-hairline border-y border-hairline">
          {investigation.actions.map((act, idx) => (
            <li key={act} className="flex items-start gap-3 py-3">
              <span className="font-mono text-label text-muted tabular-nums">
                {String(idx + 1).padStart(2, "0")}
              </span>
              <span className="text-body text-fg">{act}</span>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}
