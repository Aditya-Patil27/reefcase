import { useState } from "react";
import type { FrameView } from "../live/reducer";
import SegmentedControl from "./arc/segmented-control/segmented-control";
import { Skeleton } from "./arc/skeleton/skeleton";
import { CoverStrip } from "./CoverStrip";
import { LIT_RING } from "./strobe";

export type ViewMode = "frame" | "mask" | "both";

export interface FrameGridProps {
  frames: FrameView[];
  className?: string;
  /** The frame opened under the strobe: shown in true colour, twice the size. */
  litId?: string;
  /** Makes each frame a button that opens it as evidence. */
  onOpenFrame?: (id: string) => void;
  title?: string;
  /** One line under the heading saying where the frames came from. */
  description?: string;
}

const VIEW_OPTIONS = [
  { value: "frame", label: "Frame" },
  { value: "mask", label: "Mask" },
  { value: "both", label: "Both" },
];

export function FrameGrid({
  frames,
  className = "",
  litId,
  onOpenFrame,
  title = "Frames",
  description = "Frames sit in the water's cast until you open one. An opened frame shows in true colour with its SAM 3 mask.",
}: FrameGridProps) {
  const [mode, setMode] = useState<ViewMode>("both");

  return (
    <section aria-labelledby="frames-heading" className={`space-y-4 ${className}`}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-prose space-y-1">
          <h2 id="frames-heading" className="text-title font-bold text-fg">
            {title}
          </h2>
          <p className="text-body text-secondary">{description}</p>
        </div>
        <SegmentedControl
          options={VIEW_OPTIONS}
          value={mode}
          onValueChange={(val) => setMode(val as ViewMode)}
          label="Display mode"
        />
      </div>

      <div className="grid grid-flow-dense grid-cols-2 gap-3 lg:grid-cols-4">
        {frames.map((frame, index) => {
          const name = `Frame ${String(index + 1).padStart(2, "0")}`;
          const isPending = !frame.thumbUrl;
          const lit = frame.id === litId;
          const live = frame.cover ? `${Math.round(frame.cover.live_coral * 100)}% live` : null;

          const picture = (
            <>
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
              {lit ? (
                <span className="absolute top-2 left-2 z-10 bg-strobe px-1.5 py-0.5 text-label font-bold text-fg">
                  {name}
                </span>
              ) : null}
            </>
          );
          const tile = `water-cast block aspect-[4/3] w-full ${lit ? LIT_RING : ""}`;

          return (
            <figure
              key={frame.id}
              className={`space-y-1.5 ${lit ? "col-span-2 row-span-2" : ""}`}
            >
              {isPending ? (
                <div data-skeleton="true" className="aspect-[4/3] w-full overflow-hidden">
                  <Skeleton className="size-full" />
                </div>
              ) : onOpenFrame ? (
                <button
                  type="button"
                  aria-label={`Open ${name}`}
                  data-lit={lit}
                  onClick={() => onOpenFrame(frame.id)}
                  className={`${tile} cursor-zoom-in`}
                >
                  {picture}
                </button>
              ) : (
                <div data-lit={lit} className={tile}>
                  {picture}
                </div>
              )}

              <figcaption className="flex items-baseline justify-between gap-2 text-label">
                <span className={lit ? "font-bold text-fg" : "text-secondary"}>{name}</span>
                {live ? <span className="font-semibold text-fg">{live}</span> : null}
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
