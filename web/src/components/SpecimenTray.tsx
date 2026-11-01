import { useRef, type KeyboardEvent, type ReactElement } from "react";
import type { FrameView } from "../live/reducer";
import { frameLabel } from "../format";

export interface SpecimenTrayProps {
  frames: FrameView[];
  selectedFrameId?: string;
  citedFrameIds?: Set<string>;
  onSelectFrame: (frameId: string) => void;
  className?: string;
}

export function SpecimenTray({
  frames,
  selectedFrameId,
  citedFrameIds = new Set(),
  onSelectFrame,
  className = "",
}: SpecimenTrayProps): ReactElement {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const frameIds = frames.map((f) => f.id);

  function handleKeyDown(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (e.key === "ArrowLeft" && index > 0) {
      e.preventDefault();
      const prev = frames[index - 1];
      if (prev) {
        onSelectFrame(prev.id);
        const btn = containerRef.current?.querySelectorAll<HTMLButtonElement>("button")[index - 1];
        btn?.focus();
      }
    } else if (e.key === "ArrowRight" && index < frames.length - 1) {
      e.preventDefault();
      const next = frames[index + 1];
      if (next) {
        onSelectFrame(next.id);
        const btn = containerRef.current?.querySelectorAll<HTMLButtonElement>("button")[index + 1];
        btn?.focus();
      }
    }
  }

  if (frames.length === 0) {
    return <div className={`h-16 ${className}`} />;
  }

  return (
    <div className={`space-y-1.5 ${className}`}>
      <div
        ref={containerRef}
        role="region"
        aria-label="Frame specimen tray"
        className="flex w-full gap-1 overflow-x-auto pb-1"
        style={{ scrollbarWidth: "thin" }}
      >
        {frames.map((frame, idx) => {
          const isSelected = frame.id === selectedFrameId;
          const isCited = citedFrameIds.has(frame.id);
          const livePercent = Math.round((frame.cover?.live_coral ?? 0) * 100);
          const label = frameLabel(frameIds, frame.id);

          return (
            <div
              key={frame.id}
              className="flex min-w-[36px] flex-1 flex-col items-center gap-1"
            >
              {/* 2px ink tick above cited tiles */}
              <div
                className={`h-0.5 w-full ${isCited ? "bg-ink" : "bg-transparent"}`}
                aria-hidden="true"
              />
              <button
                type="button"
                aria-label={`Open ${label}`}
                aria-pressed={isSelected}
                data-lit={isSelected}
                onClick={() => onSelectFrame(frame.id)}
                onKeyDown={(e) => handleKeyDown(e, idx)}
                className={`group relative aspect-video h-12 w-full overflow-hidden bg-stage-rule transition-opacity focus:outline-none focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:ring-offset-bg ${
                  isSelected
                    ? "outline-2 outline-key-red outline-offset-1 z-10"
                    : "hover:opacity-90"
                }`}
              >
                {frame.thumbUrl ? (
                  <img
                    src={frame.thumbUrl}
                    alt={label}
                    className="size-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="size-full bg-stage-rule" />
                )}
              </button>
              <span
                className={`font-mono text-mono-num tabular-nums text-center whitespace-nowrap ${
                  isSelected ? "font-semibold text-key-red" : "text-mute"
                }`}
              >
                <span className="sr-only">{label}, live coral </span>
                <span>{frame.cover ? `${livePercent}%` : "—"}</span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

