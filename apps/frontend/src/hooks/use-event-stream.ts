"use client";

// SSE consumption with graceful reconnect (Phase 8 pull-forward): exponential
// backoff 1s -> 2s -> 4s ... capped at 30s, reset on a successful open. The
// browser's native EventSource retry is replaced by an explicit close +
// scheduled reconnect so the backoff (and its honest on-screen status) is
// under our control.

import { useEffect, useRef, useState } from "react";
import type { SherpaEvent } from "@/lib/events";

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export type StreamStatus =
  | { kind: "connecting" }
  | { kind: "connected" }
  | { kind: "reconnecting"; attempt: number; nextRetryMs: number };

export function useEventStream(url: string): {
  events: SherpaEvent[];
  status: StreamStatus;
} {
  const [events, setEvents] = useState<SherpaEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>({ kind: "connecting" });
  const attemptRef = useRef(0);

  useEffect(() => {
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      source = new EventSource(url);
      source.onopen = () => {
        attemptRef.current = 0;
        setStatus({ kind: "connected" });
      };
      source.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as SherpaEvent;
          if (event && typeof event.event_type === "string") {
            setEvents((previous) => [...previous, event]);
          }
        } catch {
          // Non-JSON frames (keepalive comments) are ignored.
        }
      };
      source.onerror = () => {
        source?.close();
        if (disposed) return;
        attemptRef.current += 1;
        const delay = Math.min(
          BASE_DELAY_MS * 2 ** (attemptRef.current - 1),
          MAX_DELAY_MS,
        );
        setStatus({
          kind: "reconnecting",
          attempt: attemptRef.current,
          nextRetryMs: delay,
        });
        timer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      source?.close();
    };
  }, [url]);

  return { events, status };
}
