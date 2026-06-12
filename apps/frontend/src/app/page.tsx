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
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-4 px-4 py-4 scanline-none">
      <header className="glass-panel flex flex-wrap items-center justify-between gap-4 rounded-xl px-5 py-4 shadow-2xl relative overflow-hidden">
        {/* Glowing glass accent line */}
        <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/30 to-transparent" />
        
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/15">
              <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <div>
              <h1 className="bg-gradient-to-r from-cyan-400 via-sky-400 to-blue-500 bg-clip-text text-lg font-black tracking-wider text-transparent uppercase font-sans">
                IncidentSherpa
              </h1>
              <div className="text-[9px] uppercase tracking-widest text-slate-500 font-bold font-mono leading-none mt-0.5">
                OPS COMMAND CENTER
              </div>
            </div>
          </div>

          <div className="hidden sm:block h-6 w-[1px] bg-slate-800" />

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 font-mono">
              SESSION:
            </span>
            {incidentId ? (
              <span className="inline-flex items-center rounded-md border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-0.5 text-xs font-bold font-mono text-cyan-400 shadow-sm shadow-cyan-500/5">
                {incidentId}
              </span>
            ) : (
              <span className="inline-flex items-center rounded-md border border-slate-800 bg-slate-900/40 px-2.5 py-0.5 text-xs font-bold font-mono text-slate-500">
                AWAITING_INCIDENT
              </span>
            )}
          </div>
        </div>

        <GuildStepper state={state} />

        <div className="flex items-center gap-3">
          <span
            data-testid="status"
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-bold ${
              status.kind === "connected"
                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.04)]"
                : "border-amber-500/20 bg-amber-500/10 text-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.04)]"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${status.kind === "connected" ? "bg-emerald-500 live-dot" : "bg-amber-500"}`} />
            <span className="font-mono text-[10px] tracking-wide">
              {status.kind === "connected"
                ? "SSE CONNECTED"
                : status.kind === "connecting"
                  ? "CONNECTING…"
                  : `RECONNECT (ATTEMPT ${status.attempt}, RETRY IN ${Math.round(status.nextRetryMs / 1000)}s)`}
            </span>
          </span>
        </div>
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
