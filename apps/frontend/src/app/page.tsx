"use client";

import { useEffect, useRef, useState } from "react";

// Raw typed event as streamed by GET /events (apps/api/main.py).
type SherpaEvent = {
  ts: string;
  incident_id: string;
  event_type: string;
  payload: Record<string, unknown>;
};

type ConnectionStatus = "connecting" | "connected" | "disconnected — retrying";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/**
 * Phase 1 placeholder UI: a raw typed-event list wired to the real SSE
 * stream. The OpenUI timeline / causal graph / postmortem panel components
 * deepen in Phase 6 — the wiring below is what they will consume.
 */
export default function Home() {
  const [events, setEvents] = useState<SherpaEvent[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const source = new EventSource(`${API_BASE}/events`);
    sourceRef.current = source;
    source.onopen = () => setStatus("connected");
    source.onerror = () => setStatus("disconnected — retrying");
    source.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as SherpaEvent;
        setEvents((previous) => [...previous, event]);
      } catch {
        // Non-JSON frames (keepalives) are ignored.
      }
    };
    return () => source.close();
  }, []);

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-10 font-mono">
      <h1 className="text-2xl font-bold">IncidentSherpa — typed event stream</h1>
      <p className="mt-1 text-sm opacity-70">
        SSE: {API_BASE}/events — <span data-testid="status">{status}</span>
      </p>

      <ul className="mt-6 space-y-2" data-testid="event-list">
        {events.length === 0 && (
          <li className="text-sm opacity-60">
            No events yet. POST an alert to {API_BASE}/trigger to see it land here.
          </li>
        )}
        {events.map((event, index) => (
          <li
            key={`${event.incident_id}-${event.ts}-${index}`}
            className="rounded border border-neutral-700 p-3 text-sm"
          >
            <div className="flex justify-between gap-4">
              <span className="font-semibold">{event.event_type}</span>
              <span className="opacity-70">{event.ts}</span>
            </div>
            <div className="opacity-80">incident: {event.incident_id}</div>
            <pre className="mt-1 overflow-x-auto text-xs opacity-70">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          </li>
        ))}
      </ul>
    </main>
  );
}
