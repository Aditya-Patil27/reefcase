import type { components } from "../api/schema";

type Cover = components["schemas"]["Cover"];
type SegClass = components["schemas"]["SegClass"];

type Segment = { segClass: SegClass; label: string; colour: string };

/** One entry per SegClass, in architecture §4.2 declaration order. */
const SEGMENTS: readonly Segment[] = [
  { segClass: "live_coral", label: "live coral", colour: "bg-reef-live" },
  { segClass: "bleached_coral", label: "bleached coral", colour: "bg-reef-bleached" },
  { segClass: "algae", label: "algae", colour: "bg-reef-algae" },
  { segClass: "rubble", label: "rubble", colour: "bg-reef-rubble" },
  { segClass: "sand", label: "sand", colour: "bg-reef-sand" },
  { segClass: "other", label: "other", colour: "bg-reef-other" },
];

function widthPercent(fraction: number): number {
  return Math.round(fraction * 100000) / 1000;
}

function formatPercent(fraction: number): string {
  const value = Math.round(fraction * 1000) / 10;
  return Number.isInteger(value) ? `${value}` : value.toFixed(1);
}

function capitalize(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

/**
 * The stacked cover bar (4px unless sized by the caller): one segment per SegClass, sized by its fraction.
 * Reused wherever a cover value appears; bone-white bleaching always carries an outline.
 */
export function CoverStrip({ cover, className }: { cover: Cover; className?: string }) {
  const fractions = SEGMENTS.map((segment) => cover[segment.segClass] ?? 0);
  const label = SEGMENTS.map((segment, index) => {
    const name = index === 0 ? capitalize(segment.label) : segment.label;
    return `${name} ${formatPercent(fractions[index] ?? 0)}%`;
  }).join(", ");

  return (
    <div
      role="img"
      aria-label={label}
      className={["flex h-1 w-full overflow-hidden", className].filter(Boolean).join(" ")}
    >
      {SEGMENTS.map((segment, index) => (
        <span
          key={segment.segClass}
          data-segment={segment.segClass}
          className={`${segment.colour} h-full shrink-0 ${segment.segClass === "bleached_coral" ? "shadow-[inset_0_0_0_1px_var(--border)]" : ""}`}
          style={{ width: `${widthPercent(fractions[index] ?? 0)}%` }}
        />
      ))}
    </div>
  );
}
