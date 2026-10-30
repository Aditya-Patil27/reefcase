/**
 * Class strings for the Strobe world's repeated marks (DESIGN.md), so every route draws a chip,
 * a rule or a button the same way. Square corners, rules instead of cards, one action colour.
 */

/** A section heading: sentence case, bold, no kicker above it. */
export const SECTION_HEADING = "text-ui font-bold text-fg";

/** A citation or reference chip: a 1.5px deep-water rule around bold label text. */
export const CHIP =
  "inline-flex items-center gap-1.5 border-[1.5px] border-deep px-2 py-0.5 text-label font-bold text-fg";

/** The only red on screen: a proven alert, such as a Coral Reef Watch alert level. */
export const CHIP_ALERT =
  "inline-flex items-center gap-1.5 border-[1.5px] border-danger bg-danger px-2 py-0.5 text-label font-bold text-on-accent";

/** A claim the agent has cited: a solid 3px rule on its left edge. */
export const RULE_CITED = "border-l-[3px] border-deep pl-3.5";

/** A claim still being checked: the same rule, dashed and quieter. */
export const RULE_PENDING = "border-l-[3px] border-dashed border-muted pl-3.5 text-secondary";

/** The one primary action per view: deep water, white text, square. */
export const BUTTON_PRIMARY =
  "inline-flex items-center justify-center gap-2 bg-deep px-4 py-3 text-ui font-bold text-on-accent no-underline transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50";

/** A secondary action: the same shape, outlined. */
export const BUTTON_SECONDARY =
  "inline-flex items-center justify-center gap-2 border-[1.5px] border-deep px-4 py-[10.5px] text-ui font-bold text-fg no-underline transition-colors hover:bg-accent-subtle disabled:cursor-not-allowed disabled:opacity-50";

/** A quiet inline link inside running text or a table. */
export const TEXT_LINK = "font-semibold text-fg underline decoration-border hover:decoration-fg";

/** The ring an opened, strobe-lit frame wears. */
export const LIT_RING = "shadow-[0_0_0_3px_var(--strobe),0_0_0_4px_var(--deep)]";
