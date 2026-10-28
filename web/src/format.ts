import type { components } from "./api/schema";

type EvidenceRef = components["schemas"]["EvidenceRef"];

/** Percentage-point change with a true minus sign: "+5.2 pp", "−17.0 pp". */
export function formatSignedPp(pp: number): string {
  const rounded = Math.round(pp * 10) / 10;
  return `${rounded < 0 ? "−" : "+"}${Math.abs(rounded).toFixed(1)} pp`;
}

/** "heat_stress" → "Heat stress", "mpa_boundary" → "MPA boundary". */
export function humanize(snake: string): string {
  const words = snake.replace(/_/g, " ").replace(/\b(mpa|sar|ais|dhw|sst)\b/g, (w) => w.toUpperCase());
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** "Frame 06" from the frame's arrival order. */
export function frameLabel(frameIds: string[], id: string): string {
  const index = frameIds.indexOf(id);
  return index === -1 ? "Frame" : `Frame ${String(index + 1).padStart(2, "0")}`;
}

/** Human chip text for an evidence ref: the frame ordinal or the tool's name. */
export function evidenceLabel(
  ev: EvidenceRef,
  frameIds: string[],
  toolByResultId: Record<string, string>,
): string {
  if (ev.kind === "frame") return frameLabel(frameIds, ev.id);
  const tool = toolByResultId[ev.id];
  return tool ? humanize(tool) : "Tool result";
}
