import type { components } from "../api/schema";

type Event = components["schemas"]["Event"];
type Cover = components["schemas"]["Cover"];
type QualityScore = components["schemas"]["QualityScore"];
type FrameAssessment = components["schemas"]["FrameAssessment"];
type Finding = components["schemas"]["Finding"];
type FrameDetail = components["schemas"]["FrameDetail"];

/** A frame as the live view shows it: ordered by arrival, enriched as events land. */
export type FrameView = {
  id: string;
  /** A small copy for the grid; empty until the frame is scored. */
  thumbUrl: string;
  /** The full-size frame, for the drawer and the case file. */
  imageUrl?: string;
  quality?: QualityScore;
  cover?: Cover;
  maskUrl?: string;
  assessment?: FrameAssessment;
};

/**
 * Frame URLs from the ids, the way /media serves them. Not from the event's thumb_url, so a
 * survey recorded before thumbnails existed still gets them.
 */
function frameUrls(surveyId: string, frameId: string): Pick<FrameView, "thumbUrl" | "imageUrl"> {
  return {
    thumbUrl: `/media/${surveyId}/thumbs/${frameId}.jpg`,
    imageUrl: `/media/${surveyId}/frames/${frameId}.jpg`,
  };
}

/** A stored frame as the views show it. Frame and mask URLs come from the ids, the way the media mount serves them. */
export function toFrameView(surveyId: string, detail: FrameDetail): FrameView {
  return {
    id: detail.frame.id,
    ...frameUrls(surveyId, detail.frame.id),
    quality: detail.frame.quality,
    cover: detail.segmentation?.cover,
    maskUrl: detail.segmentation ? `/media/${surveyId}/masks/${detail.frame.id}.png` : undefined,
    assessment: detail.assessment ?? undefined,
  };
}

/** One tool call in the trace panel. */
export type ToolCallView = {
  callId: string;
  tool: string;
  params: Record<string, unknown>;
  status: "running" | "returned";
  toolResultId?: string;
  summary?: string;
};

export type LiveState = {
  surveyId: string | null;
  lastSeq: number;
  frames: FrameView[];
  toolCalls: ToolCallView[];
  findings: Finding[];
  investigationId: string | null;
  reportReady: boolean;
  failed: string | null;
};

export const initialLiveState: LiveState = {
  surveyId: null,
  lastSeq: 0,
  frames: [],
  toolCalls: [],
  findings: [],
  investigationId: null,
  reportReady: false,
  failed: null,
};

export type LiveAction = { type: "event"; event: Event } | { type: "reset"; surveyId: string };

/**
 * Folds one server-sent event into the live view state.
 *
 * Pure: every branch returns a new object, and an event that is stale (seq already
 * seen) or belongs to another survey returns the state reference unchanged, so
 * reconnect replays never duplicate a frame, a tool call or a finding.
 */
export function liveReducer(state: LiveState, action: LiveAction): LiveState {
  if (action.type === "reset") {
    return { ...initialLiveState, surveyId: action.surveyId };
  }

  const event = action.event;
  if (state.surveyId !== null && event.survey_id !== state.surveyId) return state;
  if (event.seq <= state.lastSeq) return state;

  const base: LiveState = {
    ...state,
    surveyId: state.surveyId ?? event.survey_id,
    lastSeq: event.seq,
  };

  switch (event.type) {
    case "survey_started":
    case "frames_extracted":
    case "disagreement":
      return base;

    case "frame_scored":
      return {
        ...base,
        frames: upsertFrame(base.frames, event.frame_id, (frame) => ({
          ...frame,
          ...frameUrls(event.survey_id, event.frame_id),
          quality: event.quality,
        })),
      };

    case "segmented":
      return {
        ...base,
        frames: upsertFrame(base.frames, event.frame_id, (frame) => ({
          ...frame,
          cover: event.cover,
          maskUrl: event.mask_url,
        })),
      };

    case "assessed":
      return {
        ...base,
        frames: upsertFrame(base.frames, event.assessment.frame_id, (frame) => ({
          ...frame,
          assessment: event.assessment,
        })),
      };

    case "tool_called":
      return {
        ...base,
        toolCalls: appendCall(base.toolCalls, {
          callId: event.call_id,
          tool: event.tool,
          params: event.params,
          status: "running",
        }),
      };

    case "tool_returned": {
      // A return without its call cannot be placed in the trace; the stream always
      // emits the pair, so only a truncated tail reaches this branch.
      if (!base.toolCalls.some((call) => call.callId === event.call_id)) return base;
      return {
        ...base,
        toolCalls: base.toolCalls.map((call) =>
          call.callId === event.call_id
            ? {
                ...call,
                status: "returned",
                toolResultId: event.tool_result_id,
                summary: event.summary,
              }
            : call,
        ),
      };
    }

    case "finding":
      return { ...base, findings: [...base.findings, event.finding] };

    case "report_ready":
      return {
        ...base,
        investigationId: event.investigation_id,
        reportReady: true,
      };

    case "survey_failed":
      return { ...base, failed: event.reason };

    default: {
      // Compile-time exhaustiveness check; an event type added to the API later
      // leaves the live state untouched rather than corrupting it.
      const exhaustive: never = event;
      void exhaustive;
      return state;
    }
  }
}

function upsertFrame(
  frames: readonly FrameView[],
  id: string,
  update: (frame: FrameView) => FrameView,
): FrameView[] {
  let seen = false;
  const next = frames.map((frame) => {
    if (frame.id !== id) return frame;
    seen = true;
    return update(frame);
  });
  if (!seen) next.push(update({ id, thumbUrl: "" }));
  return next;
}

function appendCall(calls: readonly ToolCallView[], call: ToolCallView): ToolCallView[] {
  if (calls.some((existing) => existing.callId === call.callId)) return [...calls];
  return [...calls, call];
}
