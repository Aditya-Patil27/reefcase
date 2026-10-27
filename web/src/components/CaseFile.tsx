import type { ReactElement } from "react";
import type { components } from "../api/schema";

type Investigation = components["schemas"]["Investigation"];
export type EvidenceRef = components["schemas"]["EvidenceRef"];
export type EvidenceItem = EvidenceRef;

export interface CaseFileProps {
  investigation: Investigation;
  onOpenEvidence: (evidence: EvidenceRef) => void;
}

export function CaseFile({
  investigation,
  onOpenEvidence,
}: CaseFileProps): ReactElement {
  const topHypothesis = investigation.hypotheses[0];

  return (
    <article aria-label="Case file" className="space-y-8 text-fg">
      {/* 1. Verdict block */}
      <section
        aria-label="Verdict"
        className="border-l-[3px] border-l-heat-3 pl-4 py-1"
      >
        <h2 className="text-display font-semibold leading-tight text-fg">
          {investigation.verdict}
        </h2>
        {topHypothesis?.rationale ? (
          <p className="mt-2 text-body text-secondary">
            {topHypothesis.rationale}
          </p>
        ) : null}
      </section>

      {/* 2. 01 FINDINGS */}
      <section aria-labelledby="findings-heading" className="space-y-4">
        <h3
          id="findings-heading"
          className="font-mono text-label uppercase tracking-wider text-muted"
        >
          01&nbsp;&nbsp;FINDINGS
        </h3>

        <div className="space-y-3">
          {investigation.findings.map((finding, idx) => (
            <div
              key={finding.statement}
              className="rounded-lg border border-hairline bg-surface p-4"
            >
              <div className="flex items-start gap-3">
                <span className="font-mono text-label text-muted tabular-nums">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <div className="flex-1 space-y-2">
                  <p className="text-body text-fg leading-relaxed">
                    {finding.statement}
                  </p>

                  {/* Evidence chips */}
                  {finding.evidence.length > 0 ? (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {finding.evidence.map((ev) => (
                        <button
                          key={`${ev.kind}-${ev.id}`}
                          type="button"
                          aria-label={`Evidence ${ev.id}`}
                          onClick={() => onOpenEvidence(ev)}
                          className="flex items-center gap-1.5 rounded-md border border-hairline bg-sunken px-2 py-0.5 font-mono text-label text-secondary transition-colors hover:border-accent hover:text-fg"
                        >
                          {ev.kind === "frame" ? (
                            <span className="size-2 rounded-full bg-accent" />
                          ) : null}
                          <span>{ev.id}</span>
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 3. 02 HYPOTHESES */}
      <section aria-labelledby="hypotheses-heading" className="space-y-4">
        <h3
          id="hypotheses-heading"
          className="font-mono text-label uppercase tracking-wider text-muted"
        >
          02&nbsp;&nbsp;HYPOTHESES
        </h3>

        <div className="space-y-3">
          {investigation.hypotheses.map((hyp) => {
            const percent = Math.round(hyp.confidence * 100);
            return (
              <div
                key={hyp.cause}
                className="rounded-lg border border-hairline bg-surface p-4 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-body font-semibold text-fg">
                    {hyp.cause}
                  </span>
                  <span className="font-mono text-label font-bold text-accent tabular-nums">
                    {percent}%
                  </span>
                </div>

                {/* 4px confidence bar */}
                <div className="h-1 w-full overflow-hidden rounded-full bg-sunken">
                  <div
                    className="h-full bg-accent transition-all duration-500"
                    style={{ width: `${percent}%` }}
                  />
                </div>

                <p className="text-body text-secondary">{hyp.rationale}</p>

                {/* Supporting evidence chips */}
                {hyp.supporting.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="font-mono text-label text-muted">
                      Support:
                    </span>
                    {hyp.supporting.map((ev) => (
                      <button
                        key={`sup-${ev.kind}-${ev.id}`}
                        type="button"
                        aria-label={`Supporting evidence ${ev.id}`}
                        onClick={() => onOpenEvidence(ev)}
                        className="rounded-md border border-hairline bg-sunken px-2 py-0.5 font-mono text-label text-secondary transition-colors hover:border-accent hover:text-fg"
                      >
                        {ev.id}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>

      {/* 4. 03 ACTIONS */}
      <section aria-labelledby="actions-heading" className="space-y-4">
        <h3
          id="actions-heading"
          className="font-mono text-label uppercase tracking-wider text-muted"
        >
          03&nbsp;&nbsp;ACTIONS
        </h3>

        <ol className="space-y-2">
          {investigation.actions.map((act, idx) => (
            <li
              key={act}
              className="flex items-start gap-3 rounded-lg border border-hairline bg-surface p-3"
            >
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
