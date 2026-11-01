import type { ReactElement } from "react";
import TextShimmer from "./arc/text-shimmer/text-shimmer";

export interface PipelineStep {
  id: string;
  label: string;
}

export const DEFAULT_PIPELINE_STEPS: PipelineStep[] = [
  { id: "upload", label: "Upload" },
  { id: "frames", label: "Frames" },
  { id: "segment", label: "Segment" },
  { id: "assess", label: "Assess" },
  { id: "investigate", label: "Investigate" },
  { id: "report", label: "Report" },
];

export interface PipelineStepsProps {
  currentStage: number;
  reportReady: boolean;
  failed?: string | null;
  className?: string;
}

export function PipelineSteps({
  currentStage,
  reportReady,
  failed,
  className = "",
}: PipelineStepsProps): ReactElement {
  const activeLabel = DEFAULT_PIPELINE_STEPS[currentStage]?.label ?? "Processing";

  return (
    <div className={className}>
      {/* Mobile status banner */}
      <p role="status" className="sm:hidden font-mono text-mono-sm text-ink pb-2">
        {reportReady ? "Case file ready" : `Stage ${currentStage + 1} of 6: ${activeLabel}`}
      </p>

      {/* Desktop steps grid */}
      <div
        role="region"
        aria-label="Pipeline stages"
        className="hidden sm:grid grid-cols-6 gap-2 font-mono text-mono-eyebrow uppercase tracking-wider"
      >
      {DEFAULT_PIPELINE_STEPS.map((step, idx) => {
        const isPast = reportReady || idx < currentStage;
        const isCurrent = !reportReady && idx === currentStage && !failed;
        const isFailed = Boolean(failed) && idx === currentStage;
        const stepNum = String(idx + 1).padStart(2, "0");

        let statusClass = "text-mute border-b border-rule";
        if (isPast) {
          statusClass = "text-ink border-b border-ink font-medium";
        } else if (isCurrent) {
          statusClass = "text-key-red border-b-2 border-key-red font-medium";
        } else if (isFailed) {
          statusClass = "text-key-red border-b-2 border-key-red font-medium";
        }

        return (
          <div key={step.id} className={`pb-1.5 transition-colors ${statusClass}`}>
            <span>{stepNum} </span>
            {isCurrent ? (
              <span className="inline-block">
                <TextShimmer active>{step.label}</TextShimmer>
              </span>
            ) : (
              <span>{step.label}</span>
            )}
          </div>
        );
      })}
      </div>
    </div>
  );
}

