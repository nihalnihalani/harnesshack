"use client";

// IncidentSherpa war-room view (demo-scripts.md, IncidentSherpa Rev 2.1).
// Every element on this page renders ONLY data received over SSE / API —
// no hardcoded demo values; latency badges render measured numbers or
// "awaiting measurement"; blocked/skipped/degraded states are styled loudly.

import { useMemo } from "react";
import { useEventStream } from "@/hooks/use-event-stream";
import {
  API_BASE,
  asString,
  causalEdges,
  currentIncidentId,
  deriveState,
  type SherpaEvent,
} from "@/lib/events";
import { CausalGraph } from "@/components/causal-graph";
import { FallbackPostmortem } from "@/components/fallback-postmortem";
import { GuildStepper } from "@/components/guild-stepper";
import { LatencyBadges } from "@/components/latency-badges";
import { OwnerConfirm } from "@/components/owner-confirm";
import { PostmortemPanel } from "@/components/postmortem-panel";
import { Timeline } from "@/components/timeline";

function latestCausal(events: SherpaEvent[]): {
  edges: ReturnType<typeof causalEdges>;
  sql: string | null;
} {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].event_type === "causal.chains_detected") {
      return {
        edges: causalEdges(events[i].payload),
        sql: asString(events[i].payload.sql),
      };
    }
  }
  return { edges: [], sql: null };
}

function affectedServicesOf(events: SherpaEvent[]): string[] {
  for (let i = events.length - 1; i >= 0; i--) {
    const event = events[i];
    if (event.event_type === "extraction.completed") {
      const raw = event.payload.affected_services;
      if (Array.isArray(raw)) {
        return raw.filter((item): item is string => typeof item === "string");
      }
    }
  }
  return [];
}

export default function Home() {
  const { events: allEvents, status } = useEventStream(`${API_BASE}/events`);

  const incidentId = currentIncidentId(allEvents);
  const events = useMemo(
    () =>
      incidentId === null
        ? allEvents
        : allEvents.filter((event) => event.incident_id === incidentId),
    [allEvents, incidentId],
  );

  const state = deriveState(events);
  const causal = latestCausal(events);

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-4 px-4 py-4">
      <header className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3">
        <div className="flex items-baseline gap-3">
          <h1 className="text-lg font-bold tracking-tight text-slate-100">
            IncidentSherpa
          </h1>
          <span className="text-sm text-slate-400">
            {incidentId ? (
              <>
                incident <span className="font-mono text-slate-200">{incidentId}</span>
              </>
            ) : (
              "no live incident"
            )}
          </span>
        </div>
        <GuildStepper state={state} />
        <span
          data-testid="status"
          className={`rounded-full border px-3 py-1 text-xs ${
            status.kind === "connected"
              ? "border-emerald-600/60 text-emerald-300"
              : "border-amber-600/60 text-amber-300"
          }`}
        >
          {status.kind === "connected"
            ? "● SSE connected"
            : status.kind === "connecting"
              ? "○ connecting…"
              : `○ reconnecting (attempt ${status.attempt}, retry in ${Math.round(
                  status.nextRetryMs / 1000,
                )}s)`}
        </span>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="min-h-[24rem] lg:col-span-2">
          <Timeline events={events} />
        </div>
        <div className="flex min-h-0 flex-col gap-4 lg:col-span-3">
          <CausalGraph
            edges={causal.edges}
            sql={causal.sql}
            affectedServices={affectedServicesOf(events)}
          />
          <LatencyBadges events={events} />
          <OwnerConfirm incidentId={incidentId} events={events} />
          <PostmortemPanel incidentId={incidentId} state={state} events={events} />
        </div>
      </div>

      <FallbackPostmortem />
    </main>
  );
}
