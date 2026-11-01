import type { ReactElement } from "react";
import { Link } from "@tanstack/react-router";
import type { components } from "../api/schema";
import { TEXT_LINK } from "./marks";

type Survey = components["schemas"]["Survey"];

export interface CoverChartProps {
  surveys: Survey[];
  className?: string;
}

const CATEGORIES = [
  { key: "live_coral", label: "Live coral", color: "bg-reef-live" },
  // Bleached coral is near-white, so it carries a 1px rule like CoverStrip and the site legend.
  { key: "bleached_coral", label: "Bleached coral", color: "bg-reef-bleached shadow-[inset_0_0_0_1px_var(--border)]" },
  { key: "algae", label: "Algae", color: "bg-reef-algae" },
  { key: "rubble", label: "Rubble", color: "bg-reef-rubble" },
  { key: "sand", label: "Sand", color: "bg-reef-sand" },
  { key: "other", label: "Rock and unclassified", color: "bg-reef-other" },
] as const;

export function CoverChart({ surveys, className }: CoverChartProps): ReactElement {
  // Sort chronological ascending
  const sorted = [...surveys].sort((a, b) => a.dive_date.localeCompare(b.dive_date));

  return (
    <figure
      aria-label="Reef cover over time"
      className={["border-y border-hairline py-4 sm:py-6 space-y-6 max-w-full overflow-hidden", className]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Legend */}
      <div
        role="group"
        aria-label="Cover categories"
        className="flex flex-wrap items-center gap-3 sm:gap-4 text-label text-secondary"
      >
        {CATEGORIES.map((cat) => (
          <div key={cat.key} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={`size-3 ${cat.color} shrink-0`} />
            <span>{cat.label}</span>
          </div>
        ))}
      </div>

      {/* Chart grid. The plot band (top-8, h-44) is exactly where every bar sits: a 24px
          readout plus an 8px gap above it, so the axis and gridlines line up with the bars. The
          chart is only as wide as its bars (min 360px), so one dive is not one bar in a void. */}
      <div className="overflow-x-auto max-w-full pb-2">
        <div className="relative inline-block min-w-[360px] pr-6 align-top">
        <div className="absolute left-0 right-0 top-8 h-44 pointer-events-none select-none">
          {[100, 75, 50, 25, 0].map((tick) => (
            <div
              key={tick}
              className="absolute left-0 right-0 flex h-0 items-center"
              style={{ top: `${100 - tick}%` }}
            >
              <span className="w-10 text-label text-muted">{tick}%</span>
              <div
                className={`flex-1 border-b border-hairline ${tick === 0 ? "" : "border-dashed"}`}
              />
            </div>
          ))}
        </div>

        {/* Stacked bars */}
        <div className="relative ml-12 flex items-start gap-6 sm:gap-8 z-10">
          {sorted.map((survey) => {
            const cover = survey.cover;
            if (!cover) return null;

            const livePct = Math.round(cover.live_coral * 100);

            return (
              <div
                key={survey.id}
                className="flex flex-col items-center gap-2 group w-20"
              >
                {/* Live coral readout on top */}
                <span className="h-6 text-ui leading-6 font-bold text-fg">
                  {livePct}%
                </span>

                {/* Stacked bar: h-44 is the 0 to 100% plot band */}
                <div
                  className="h-44 w-12 overflow-hidden flex flex-col-reverse bg-sunken"
                  aria-label={`Dive ${survey.dive_date}: ${livePct}% live coral`}
                >
                  {CATEGORIES.map((cat) => {
                    const frac = cover[cat.key] ?? 0;
                    const heightPct = Math.round(frac * 100);
                    if (heightPct <= 0) return null;
                    return (
                      <div
                        key={cat.key}
                        style={{ height: `${heightPct}%` }}
                        className={`${cat.color} w-full shrink-0 transition-opacity duration-150 group-hover:opacity-90`}
                        title={`${cat.label}: ${heightPct}%`}
                      />
                    );
                  })}
                </div>

                {/* X-axis date */}
                <div className="text-center space-y-1 pt-2">
                  <span className="block text-label text-secondary whitespace-nowrap">
                    {survey.dive_date}
                  </span>
                  <Link
                    to="/surveys/$id"
                    params={{ id: survey.id }}
                    className={`text-label ${TEXT_LINK}`}
                  >
                    Case file
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      </div>
    </figure>
  );
}
