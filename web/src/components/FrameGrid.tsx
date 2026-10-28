import { useState } from "react";
import type { FrameView } from "../live/reducer";
import SegmentedControl from "./arc/segmented-control/segmented-control";
import { Skeleton } from "./arc/skeleton/skeleton";
import { CoverStrip } from "./CoverStrip";

export type ViewMode = "frame" | "mask" | "both";

export interface FrameGridProps {
  frames: FrameView[];
  className?: string;
}

const VIEW_OPTIONS = [
  { value: "frame", label: "Frame" },
  { value: "mask", label: "Mask" },
  { value: "both", label: "Both" },
];

export function FrameGrid({ frames, className = "" }: FrameGridProps) {
  const [mode, setMode] = useState<ViewMode>("both");

  return (
    <section aria-labelledby="frames-heading" className={`space-y-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="frames-heading" className="font-mono text-label uppercase text-muted">
          FRAMES
        </h2>
        <SegmentedControl
          options={VIEW_OPTIONS}
          value={mode}
          onValueChange={(val) => setMode(val as ViewMode)}
          label="Display mode"
        />
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-5 lg:grid-cols-4">
        {frames.map((frame, index) => {
          const name = `Frame ${String(index + 1).padStart(2, "0")}`;
          const isPending = !frame.thumbUrl;

          return (
            <figure key={frame.id} className="space-y-1.5">
              {isPending ? (
                <div data-skeleton="true" className="aspect-video w-full overflow-hidden rounded-sm">
                  <Skeleton className="size-full" />
                </div>
              ) : (
                <div className="relative aspect-video w-full overflow-hidden rounded-sm bg-sunken">
                  {mode !== "mask" && (
                    <img src={frame.thumbUrl} alt={name} className="size-full object-cover" />
                  )}
                  {mode !== "frame" && frame.maskUrl ? (
                    <img
                      src={frame.maskUrl}
                      alt={`${name} mask`}
                      className={`absolute inset-0 size-full object-cover ${mode === "both" ? "opacity-55" : ""}`}
                    />
                  ) : null}
                </div>
              )}

              <figcaption className="flex items-baseline justify-between font-mono text-label tabular-nums">
                <span className="text-secondary">{name}</span>
                {frame.cover ? (
                  <span className="text-fg">{Math.round(frame.cover.live_coral * 100)}% live</span>
                ) : null}
              </figcaption>

              {frame.cover ? (
                <CoverStrip cover={frame.cover} />
              ) : (
                <div className="h-1 w-full bg-hairline" />
              )}
            </figure>
          );
        })}
      </div>
    </section>
  );
}
