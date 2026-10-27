import { describe, expect, it } from "vitest";
import type { components } from "../api/schema";
import mockEvents from "../mocks/events.json";
import { initialLiveState, liveReducer, type LiveState } from "./reducer";

type Event = components["schemas"]["Event"];

const events = mockEvents as unknown as Event[];
const surveyId = "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3";

function fold(sequence: readonly Event[], state: LiveState = initialLiveState): LiveState {
  return sequence.reduce<LiveState>(
    (current, event) => liveReducer(current, { type: "event", event }),
    state,
  );
}

function coverTotal(cover: Record<string, number>): number {
  return Object.values(cover).reduce((sum, value) => sum + value, 0);
}

describe("liveReducer over the mock event sequence", () => {
  it("builds frames with covers and masks, tool calls with results, findings and a ready report", () => {
    const state = fold(events);

    expect(state.surveyId).toBe(surveyId);
    expect(state.lastSeq).toBe(41);
    expect(state.frames).toHaveLength(8);

    for (const frame of state.frames) {
      expect(frame.cover).toBeDefined();
      expect(Object.keys(frame.cover ?? {})).toHaveLength(6);
      expect(coverTotal(frame.cover ?? {})).toBeCloseTo(1, 6);
      expect(frame.maskUrl).toBeDefined();
      expect(frame.assessment).toBeDefined();
      expect(frame.thumbUrl).toContain("/media/");
    }

    expect(state.toolCalls).toHaveLength(5);
    for (const call of state.toolCalls) {
      expect(call.status).toBe("returned");
      expect(call.toolResultId).toBeDefined();
      expect(call.summary).toBeTruthy();
    }

    expect(state.findings).toHaveLength(3);
    for (const finding of state.findings) {
      expect(finding.evidence.length).toBeGreaterThan(0);
    }

    expect(state.reportReady).toBe(true);
    expect(state.investigationId).toMatch(/^inv_/);
    expect(state.failed).toBeNull();
  });

  it("keeps frames in arrival order and numbers them by their event order", () => {
    const state = fold(events);
    const scored = events.filter((event) => event.type === "frame_scored");
    expect(state.frames.map((frame) => frame.id)).toEqual(
      scored.map((event) => (event.type === "frame_scored" ? event.frame_id : "")),
    );
  });

  it("is idempotent when the whole sequence is replayed", () => {
    const once = fold(events);
    const twice = fold(events, once);
    expect(twice).toEqual(once);
    expect(twice.frames).toHaveLength(8);
    expect(twice.toolCalls).toHaveLength(5);
    expect(twice.findings).toHaveLength(3);
  });

  it("ignores an event whose seq is not newer", () => {
    const state = fold(events);
    const late = events[2] as Event;
    expect(liveReducer(state, { type: "event", event: late })).toBe(state);
  });

  it("ignores events from a different survey once the survey is set", () => {
    const state = fold(events);
    const foreign = { ...(events[0] as Event), survey_id: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P4", seq: 99 };
    expect(liveReducer(state, { type: "event", event: foreign as Event })).toBe(state);
  });

  it("leaves the state alone for an event type this build does not know", () => {
    const state = fold(events);
    const future = { ...(events[0] as Event), type: "frame_dropped", seq: 99 };
    const action = { type: "event", event: future as unknown as Event } as const;
    expect(liveReducer(state, action)).toBe(state);
  });

  it("records a survey failure", () => {
    const failed: Event = {
      type: "survey_failed",
      survey_id: surveyId,
      seq: 42,
      ts: "2026-10-21T09:20:00Z",
      reason: "The clip ended before the transect finished.",
    };
    const state = fold(events);
    const after = liveReducer(state, { type: "event", event: failed });
    expect(after.failed).toBe("The clip ended before the transect finished.");
    expect(after.lastSeq).toBe(42);
  });

  it("resets to a clean state for a new survey", () => {
    const state = liveReducer(fold(events), { type: "reset", surveyId: "srv_reset" });
    expect(state).toEqual({ ...initialLiveState, surveyId: "srv_reset" });
    expect(liveReducer(initialLiveState, { type: "reset", surveyId: "srv_reset" }).frames).toEqual([]);
  });

  it("never mutates the state it is given", () => {
    const state = fold(events);
    const snapshot = structuredClone(state);
    Object.freeze(state.frames);
    Object.freeze(state.toolCalls);
    Object.freeze(state.findings);

    const next = liveReducer(
      { ...state, lastSeq: 0 },
      { type: "event", event: events[2] as Event },
    );

    expect(next).not.toBe(state);
    expect(state).toEqual(snapshot);
  });
});
