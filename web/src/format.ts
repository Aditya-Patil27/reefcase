import type { components } from "./api/schema";

type EvidenceRef = components["schemas"]["EvidenceRef"];
type Hypothesis = components["schemas"]["Hypothesis"];

/** RC-{SITE}-{YEAR}-F{nn}: site name non-alphanumeric stripped up to 6 chars, year, padded frame index */
export function catalogueNumber(siteName: string, diveDate: string, frameIndex: number): string {
  const cleanSite = siteName.replace(/[^a-zA-Z0-9]/g, "").toUpperCase().slice(0, 6) || "SITE";
  const year = diveDate ? diveDate.slice(0, 4) : new Date().getFullYear().toString();
  const framePad = String(frameIndex).padStart(2, "0");
  return `RC-${cleanSite}-${year}-F${framePad}`;
}

/** Confidence below 0.15 and at least one contradicting ref */
export function isRuledOut(hyp: Pick<Hypothesis, "confidence"> & { contradicting?: unknown[] }): boolean {
  return hyp.confidence < 0.15 && (hyp.contradicting?.length ?? 0) > 0;
}

/** Short citation key: F09, T01 */
export function citationKey(
  ev: EvidenceRef,
  frameIds: string[],
  toolResultIds: string[] = [],
): string {
  if (ev.kind === "frame") {
    const idx = frameIds.indexOf(ev.id);
    return idx === -1 ? "F--" : `F${String(idx + 1).padStart(2, "0")}`;
  }
  const tIdx = toolResultIds.indexOf(ev.id);
  return tIdx === -1 ? "T--" : `T${String(tIdx + 1).padStart(2, "0")}`;
}

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

/**
 * A hypothesis cause as a reader sees it. `unknown` is the agent's bucket for a cause none of its
 * tools measure (runoff, water quality), so it must not read as "we don't know".
 */
export function causeLabel(cause: string): string {
  return cause === "unknown" ? "Cause outside our data" : humanize(cause);
}

/** "meta-models/muse-spark-open-1026" → "Muse Spark Open": the name, not the deployment id. */
export function modelName(id: string): string {
  const name = (id.split("/").pop() ?? id).replace(/-\d+$/, "");
  return name
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** The first sentence, and whatever follows it. */
export function splitFirstSentence(text: string): [string, string] {
  const match = /^(.+?[.!?])\s+(\S[\s\S]*)$/.exec(text.trim());
  return match ? [match[1]!, match[2]!] : [text.trim(), ""];
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
