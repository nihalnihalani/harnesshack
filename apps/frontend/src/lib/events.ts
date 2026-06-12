// Typed-event wire shape — exactly what apps/api/main.py publishes on GET /events.
// CLAIM INTEGRITY: every value rendered by the UI comes out of these payloads;
// nothing on screen is hardcoded demo data.

export type SherpaEvent = {
  ts: string;
  incident_id: string;
  event_type: string;
  payload: Record<string, unknown>;
};

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type IncidentState = "INVESTIGATING" | "MITIGATING" | "RESOLVED";

// --- narrow helpers (payloads are untrusted JSON; never guess a value) ----

export function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export type CausalEdge = {
  cause_service: string;
  effect_service: string;
  lag_seconds: number;
};

export function causalEdges(payload: Record<string, unknown>): CausalEdge[] {
  if (!Array.isArray(payload.edges)) return [];
  const edges: CausalEdge[] = [];
  for (const raw of payload.edges) {
    const edge = asRecord(raw);
    if (!edge) continue;
    const cause = asString(edge.cause_service);
    const effect = asString(edge.effect_service);
    const lag = asNumber(edge.lag_seconds);
    if (cause && effect && lag !== null) {
      edges.push({ cause_service: cause, effect_service: effect, lag_seconds: lag });
    }
  }
  return edges;
}

/** "250" seconds -> "4m 10s" — formatting only, the number is from the event. */
export function formatLag(lagSeconds: number): string {
  const minutes = Math.floor(lagSeconds / 60);
  const seconds = lagSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

export function formatClock(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  return date.toISOString().slice(11, 19);
}

/** Derive the current incident state purely from received events. */
export function deriveState(events: SherpaEvent[]): IncidentState | null {
  let state: IncidentState | null = null;
  for (const event of events) {
    if (event.event_type === "incident.opened" || event.event_type === "alert.received") {
      state = state ?? "INVESTIGATING";
    }
    if (event.event_type === "state.transition") {
      const to = asString(event.payload.to);
      if (to === "INVESTIGATING" || to === "MITIGATING" || to === "RESOLVED") {
        state = to;
      }
    }
  }
  return state;
}

/** The incident currently on screen = the most recently opened incident. */
export function currentIncidentId(events: SherpaEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const type = events[i].event_type;
    if (type === "alert.received" || type === "incident.opened") {
      return events[i].incident_id;
    }
  }
  return events.length > 0 ? events[events.length - 1].incident_id : null;
}
