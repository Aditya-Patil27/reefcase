/**
 * Class strings for the Specimen Proof world's repeated marks (Story 8.8).
 * Near-white ground, 1px rules, no cards, no radius, no shadows.
 * Velvet-black stage. Label red for citation keys and selected frame.
 */

/** A red mono citation key button: F09, T01. Evidence label is its accessible name. */
export const KEY =
  "font-mono font-semibold text-key-red inline-flex items-baseline hover:underline cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-ink";

/** A standard 1px rule. */
export const RULE = "border-t border-rule";

/** The one primary action per view: solid ink with white text, square corners. */
export const BUTTON_PRIMARY =
  "inline-flex items-center justify-center gap-2 bg-ink px-4 py-2.5 font-sans text-ui font-medium text-bg no-underline transition-colors hover:bg-mute disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink";

/** A secondary action: outlined with 1px rule, near-white ground, ink text. */
export const BUTTON_SECONDARY =
  "inline-flex items-center justify-center gap-2 border border-rule bg-bg px-4 py-2 font-sans text-ui font-medium text-ink no-underline transition-colors hover:border-ink disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink";

/** A quiet inline link inside running text or a table. */
export const TEXT_LINK =
  "font-medium text-ink underline decoration-rule hover:decoration-ink";

/** A section heading: sentence case, bold, no kicker above it. */
export const SECTION_HEADING = "font-sans text-ui font-semibold text-ink";

/** Eyebrow text in uppercase mono with letter spacing. */
export const EYEBROW =
  "font-mono text-mono-eyebrow font-medium uppercase tracking-wider text-mute";

/** Outline for the selected frame on the stage or in the tray: 2px red outline. */
export const STAGE_SELECTED = "outline-2 outline-key-red outline-offset-1";

/** A cited trace finding: an ink rule down its left edge. */
export const RULE_CITED = "border-l-2 border-ink pl-3.5";
/** A finding with no evidence yet: a dashed rule, muted text. */
export const RULE_PENDING = "border-l-2 border-dashed border-rule pl-3.5 text-mute";

