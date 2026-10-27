import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useEventStream } from "./useEventStream";
import type { components } from "../api/schema";

type Event = components["schemas"]["Event"];

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  listeners: Record<string, ((event: MessageEvent) => void)[]> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: (event: MessageEvent) => void) {
    if (!this.listeners[type]) return;
    this.listeners[type] = this.listeners[type].filter((l) => l !== listener);
  }

  emit(type: string, data: Event) {
    const messageEvent = { data: JSON.stringify(data) } as MessageEvent;
    if (this.onmessage) this.onmessage(messageEvent);
    if (this.listeners[type]) {
      for (const listener of this.listeners[type]) {
        listener(messageEvent);
      }
    }
  }

  simulateOpen() {
    if (this.onopen) this.onopen();
  }

  simulateError() {
    if (this.onerror) this.onerror();
  }

  close() {
    this.closed = true;
  }
}

describe("useEventStream", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("connects to the event endpoint and dispatches events to state", () => {
    const { result } = renderHook(() => useEventStream("srv_test1"));
    expect(MockEventSource.instances.length).toBe(1);
    const es = MockEventSource.instances[0]!;
    expect(es.url).toBe("/api/surveys/srv_test1/events");

    act(() => {
      es.simulateOpen();
    });
    expect(result.current.status).toBe("connected");

    const event1: Event = {
      type: "frame_scored",
      seq: 1,
      ts: "2026-10-21T06:14:22Z",
      survey_id: "srv_test1",
      frame_id: "frm_01",
      thumb_url: "/media/frames/01.jpg",
      quality: { blur: 0.1, color_cast: 0.1, turbidity: 0.2, passed: true, reason: null },
    };

    act(() => {
      es.emit("frame_scored", event1);
    });

    expect(result.current.state.lastSeq).toBe(1);
    expect(result.current.state.frames.length).toBe(1);
    expect(result.current.state.frames[0]?.id).toBe("frm_01");
    expect(result.current.state.frames[0]?.thumbUrl).toBe("/media/frames/01.jpg");
  });

  it("handles disconnection and reconnect without duplicate items", () => {
    const { result } = renderHook(() => useEventStream("srv_test2"));
    const es = MockEventSource.instances[0]!;
    act(() => {
      es.simulateOpen();
      es.emit("tool_called", {
        type: "tool_called",
        seq: 1,
        ts: "2026-10-21T06:14:22Z",
        survey_id: "srv_test2",
        call_id: "call_01",
        tool: "heat_stress",
        params: { site_id: "site_test" },
      });
    });

    expect(result.current.state.toolCalls.length).toBe(1);

    // Simulate error/disconnect
    act(() => {
      es.simulateError();
    });
    expect(result.current.status).toBe("reconnecting");
    expect(result.current.reconnectSeq).toBe(1);

    // Replay event seq 1 should not duplicate
    act(() => {
      es.emit("tool_called", {
        type: "tool_called",
        seq: 1,
        ts: "2026-10-21T06:14:22Z",
        survey_id: "srv_test2",
        call_id: "call_01",
        tool: "heat_stress",
        params: { site_id: "site_test" },
      });
    });
    expect(result.current.state.toolCalls.length).toBe(1);

    // Event seq 2 is added
    act(() => {
      es.emit("tool_returned", {
        type: "tool_returned",
        seq: 2,
        ts: "2026-10-21T06:14:23Z",
        survey_id: "srv_test2",
        call_id: "call_01",
        tool_result_id: "tr_01",
        summary: "DHW peak 4.2",
      });
    });
    expect(result.current.state.toolCalls[0]?.status).toBe("returned");
    expect(result.current.state.toolCalls[0]?.summary).toBe("DHW peak 4.2");
  });
});
