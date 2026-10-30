import type { ReactElement } from "react";
import { Link } from "@tanstack/react-router";
import type { components } from "../api/schema";
import { TEXT_LINK } from "./strobe";

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

      {/* Chart grid */}
      <div className="overflow-x-auto max-w-full pb-2">
        <div className="relative min-w-[360px] flex items-end gap-6 sm:gap-12 pt-6 pb-2 min-h-[260px] border-b border-hairline">
        {/* Y-axis ticks */}
        <div className="absolute left-0 top-0 bottom-8 flex flex-col justify-between text-label text-muted select-none pointer-events-none">
          <span>100%</span>
          <span>75%</span>
          <span>50%</span>
          <span>25%</span>
          <span>0%</span>
        </div>

        {/* Horizontal gridlines */}
        <div className="absolute left-10 right-0 top-0 bottom-8 flex flex-col justify-between pointer-events-none">
          <div className="border-b border-dashed border-hairline w-full" />
          <div className="border-b border-dashed border-hairline w-full" />
          <div className="border-b border-dashed border-hairline w-full" />
          <div className="border-b border-dashed border-hairline w-full" />
          <div className="border-b border-hairline w-full" />
        </div>

        {/* Stacked bars */}
        <div className="ml-12 flex-1 flex items-end justify-around gap-4 z-10">
          {sorted.map((survey) => {
            const cover = survey.cover;
            if (!cover) return null;

            const livePct = Math.round(cover.live_coral * 100);

            return (
              <div
                key={survey.id}
                className="flex flex-col items-center gap-2 group w-20 max-w-[100px]"
              >
                {/* Live coral readout on top */}
                <span className="text-ui font-bold text-fg">
                  {livePct}%
                </span>

                {/* Stacked bar (height 180px) */}
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
                <div className="text-center space-y-1 pt-1">
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
