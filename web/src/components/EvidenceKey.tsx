import type { ReactElement } from "react";
import type { components } from "../api/schema";
import { KEY } from "./marks";

type EvidenceRef = components["schemas"]["EvidenceRef"];

export interface EvidenceKeyProps {
  evidence: EvidenceRef;
  keyLabel: string;
  accessibleName: string;
  onSelect: (evidence: EvidenceRef) => void;
  className?: string;
}

export function EvidenceKey({
  evidence,
  keyLabel,
  accessibleName,
  onSelect,
  className = "",
}: EvidenceKeyProps): ReactElement {
  return (
    <button
      type="button"
      aria-label={`Open evidence: ${accessibleName}`}
      onClick={() => onSelect(evidence)}
      className={`${KEY} ${className}`}
    >
      {keyLabel}
    </button>
  );
}

