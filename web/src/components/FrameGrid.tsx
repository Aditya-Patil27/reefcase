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

function formatIndex(index: number): string {
  return String(index + 1).padStart(2, "0");
}

function formatTimestamp(index: number): string {
  const seconds = index * 2;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function FrameGrid({ frames, className = "" }: FrameGridProps) {
  const [mode, setMode] = useState<ViewMode>("both");

  return (
    <section aria-labelledby="frames-heading" className={`space-y-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="frames-heading" className="font-mono text-label uppercase text-muted">
          01&nbsp;&nbsp;FRAMES
        </h2>
        <SegmentedControl
          options={VIEW_OPTIONS}
          value={mode}
          onValueChange={(val) => setMode(val as ViewMode)}
          label="Display mode"
        />
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {frames.map((frame, index) => {
          const idxStr = formatIndex(index);
          const timeStr = formatTimestamp(index);
          const isPending = !frame.thumbUrl;

          return (
            <div
              key={frame.id}
              className="flex flex-col justify-between overflow-hidden rounded-md border border-hairline bg-surface p-1.5"
            >
              <div className="mb-1 flex items-center justify-between font-mono text-label text-muted tabular-nums">
                <span>{`FR ${idxStr}`}</span>
                <span>{timeStr}</span>
              </div>

              {isPending ? (
                <div data-skeleton="true" className="aspect-video w-full overflow-hidden rounded-md">
                  <Skeleton className="size-full" />
                </div>
              ) : (
                <div className="relative aspect-video w-full overflow-hidden rounded-md bg-sunken">
                  {mode === "frame" && (
                    <img
                      src={frame.thumbUrl}
                      alt={`Frame ${idxStr}`}
                      className="size-full object-cover"
                    />
                  )}
                  {mode === "mask" && (
                    <img
                      src={frame.maskUrl || frame.thumbUrl}
                      alt={`Mask ${idxStr}`}
                      className="size-full object-cover opacity-55"
                    />
                  )}
                  {mode === "both" && (
                    <>
                      <img
                        src={frame.thumbUrl}
                        alt={`Frame ${idxStr}`}
                        className="size-full object-cover"
                      />
                      {frame.maskUrl ? (
                        <img
                          src={frame.maskUrl}
                          alt={`Mask ${idxStr}`}
                          className="absolute inset-0 size-full object-cover opacity-55"
                        />
                      ) : null}
                    </>
                  )}
                </div>
              )}

              <div className="mt-1.5 min-h-1 w-full">
                {frame.cover ? (
                  <CoverStrip cover={frame.cover} />
                ) : (
                  <div className="h-1 w-full bg-hairline" />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
