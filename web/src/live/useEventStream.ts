import { useEffect, useReducer, useRef, useState } from "react";
import type { LiveState } from "./reducer";
import { initialLiveState, liveReducer } from "./reducer";
import type { components } from "../api/schema";
import { api } from "../api/client";
import { config } from "../config";

type Event = components["schemas"]["Event"];

export type EventStreamStatus = "connecting" | "connected" | "reconnecting" | "closed";

export interface UseEventStreamResult {
  state: LiveState;
  status: EventStreamStatus;
  reconnectSeq: number | null;
}

const EVENT_TYPES = [
  "survey_started",
  "frames_extracted",
  "frame_scored",
  "segmented",
  "assessed",
  "disagreement",
  "tool_called",
  "tool_returned",
  "finding",
  "report_ready",
  "survey_failed",
] as const;

export function useEventStream(surveyId: string | undefined): UseEventStreamResult {
  const [state, dispatch] = useReducer(liveReducer, initialLiveState);
  const [status, setStatus] = useState<EventStreamStatus>("connecting");
  const [reconnectSeq, setReconnectSeq] = useState<number | null>(null);
  const lastSeqRef = useRef(0);

  useEffect(() => {
    lastSeqRef.current = state.lastSeq;
  }, [state.lastSeq]);

  useEffect(() => {
    if (!surveyId) return;
    const id = surveyId;

    let eventSource: EventSource | null = null;
    let isCancelled = false;

    dispatch({ type: "reset", surveyId: id });

    function connect() {
      if (isCancelled) return;
      const url = `${config.API_URL}/api/surveys/${encodeURIComponent(id)}/events`;
      const es = new EventSource(url);
      eventSource = es;

      es.onopen = () => {
        if (isCancelled) return;
        setStatus("connected");
        setReconnectSeq(null);
      };

      const handleEvent = (raw: MessageEvent) => {
        if (isCancelled) return;
        let parsed: Event;
        try {
          parsed = JSON.parse(raw.data) as Event;
        } catch {
          return; // ignore malformed payloads
        }
        dispatch({ type: "event", event: parsed });
        // The server ends the stream after a terminal event; close first so
        // EventSource does not read that end as a dropped connection.
        if (parsed.type === "report_ready" || parsed.type === "survey_failed") {
          es.close();
          setStatus("closed");
          setReconnectSeq(null);
        }
      };

      es.onmessage = handleEvent;

      for (const t of EVENT_TYPES) {
        es.addEventListener(t, handleEvent);
      }

      es.onerror = () => {
        if (isCancelled) return;
        setStatus("reconnecting");
        setReconnectSeq(lastSeqRef.current);
        // The server also ends the stream of a survey that finished without a terminal
        // event (imported historical surveys stop after segmentation); stop there.
        void api
          .GET("/api/surveys/{survey_id}", { params: { path: { survey_id: id } } })
          .then(({ data }) => {
            if (isCancelled || es !== eventSource) return;
            if (data?.status === "done" || data?.status === "failed") {
              es.close();
              setStatus("closed");
              setReconnectSeq(null);
            }
          })
          .catch(() => {}); // a failed check leaves EventSource to retry
      };
    }

    connect();

    return () => {
      isCancelled = true;
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      setStatus("closed");
    };
  }, [surveyId]);

  return { state, status, reconnectSeq };
}
