"use client";

// Scrolling typed-event Timeline (demo beat 0:00-0:08). Every row is a real
// event off the SSE stream. SKIPPED_NOT_CONFIGURED / DEGRADED /
// BLOCKED_BY_GUARDRAIL rows are styled loudly — honesty is a feature.

import { useEffect, useRef } from "react";
import {
  asRecord,
  asString,
  formatClock,
  type SherpaEvent,
} from "@/lib/events";

const SEVERITY_STYLES: Record<string, string> = {
  P0: "bg-red-500/20 text-red-300 border-red-500/60",
  P1: "bg-orange-500/20 text-orange-300 border-orange-500/60",
  P2: "bg-yellow-500/20 text-yellow-200 border-yellow-500/60",
  P3: "bg-sky-500/20 text-sky-300 border-sky-500/60",
};

type RowTone = "normal" | "skipped" | "degraded" | "blocked" | "error" | "milestone";

function toneFor(eventType: string): RowTone {
  if (eventType === "SKIPPED_NOT_CONFIGURED") return "skipped";
  if (eventType === "DEGRADED") return "degraded";
  if (eventType === "BLOCKED_BY_GUARDRAIL") return "blocked";
  if (eventType === "agent.error" || eventType === "postmortem_error") return "error";
  if (eventType === "state.transition" || eventType === "postmortem_complete") {
    return "milestone";
  }
  return "normal";
}

const TONE_STYLES: Record<RowTone, string> = {
  normal: "border-slate-700/70 bg-slate-900/40",
  skipped:
    "border-amber-500/70 bg-amber-500/10 shadow-[inset_3px_0_0_0_theme(colors.amber.500)]",
  degraded:
    "border-orange-600/70 bg-orange-600/10 shadow-[inset_3px_0_0_0_theme(colors.orange.600)]",
  blocked:
    "border-red-600/80 bg-red-600/10 shadow-[inset_3px_0_0_0_theme(colors.red.600)]",
  error:
    "border-red-500/70 bg-red-500/10 shadow-[inset_3px_0_0_0_theme(colors.red.500)]",
  milestone: "border-emerald-600/60 bg-emerald-600/10",
};

const TONE_LABELS: Partial<Record<RowTone, string>> = {
  skipped: "SKIPPED — NOT CONFIGURED",
  degraded: "DEGRADED",
  blocked: "BLOCKED BY GUARDRAIL",
  error: "ERROR",
};

function serviceOf(event: SherpaEvent): string | null {
  const direct = asString(event.payload.service);
  if (direct) return direct;
  const alert = asRecord(event.payload.alert);
  return alert ? asString(alert.service) : null;
}

function summaryOf(event: SherpaEvent): string | null {
  const p = event.payload;
  switch (event.event_type) {
    case "extraction.completed":
      return `GLiNER2 schema-conditioned extraction — severity ${asString(p.severity) ?? "?"}`;
    case "causal.chains_detected":
      return "ClickHouse causal LAG/LEAD query complete";
    case "runbook.retrieved":
      return `Senso runbook (cited): ${asString(p.citation) ?? ""}`;
    case "ownership.suggested":
      return `${asString(p.note) ?? "Suggested owner"}: ${asString(p.suggested_owner) ?? "(see cited doc)"}`;
    case "owner_confirmed":
      return `Owner confirmed by ${asString(p.confirmed_by) ?? "human"}: ${asString(p.owner) ?? ""}`;
    case "runbook.step_selected":
      return asString(p.step) ?? asString(p.note) ?? null;
    case "state.transition":
      return `${asString(p.from) ?? "?"} → ${asString(p.to) ?? "?"}`;
    case "SKIPPED_NOT_CONFIGURED":
    case "DEGRADED":
    case "agent.error":
    case "postmortem_error":
      return asString(p.error) ?? null;
    default:
      return null;
  }
}

export function Timeline({ events }: { events: SherpaEvent[] }) {
  const endRef = useRef<HTMLDivElement | null>(null);
  // postmortem tokens stream to the PostmortemPanel, not the timeline.
  const rows = events.filter((event) => event.event_type !== "postmortem_token");

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [rows.length]);

  return (
    <section
      aria-label="Typed event timeline"
      className="flex h-full min-h-0 flex-col rounded-lg border border-slate-800 bg-slate-950/60"
    >
      <header className="border-b border-slate-800 px-4 py-2 text-xs uppercase tracking-widest text-slate-400">
        Typed event log
      </header>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3" data-testid="timeline">
        {rows.length === 0 && (
          <p className="p-2 text-sm text-slate-500">
            No events yet. POST an alert to /trigger — every agent action lands
            here as a typed event.
          </p>
        )}
        {rows.map((event, index) => {
          const tone = toneFor(event.event_type);
          const severity = asString(event.payload.severity);
          const service = serviceOf(event);
          const summary = summaryOf(event);
          return (
            <article
              key={`${event.ts}-${event.event_type}-${index}`}
              className={`rounded border px-3 py-2 text-sm ${TONE_STYLES[tone]}`}
            >
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <time className="tabular-nums text-slate-400">{formatClock(event.ts)}</time>
                <span className="font-semibold text-slate-100">{event.event_type}</span>
                {service && (
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-300">
                    {service}
                  </span>
                )}
                {severity && (
                  <span
                    className={`rounded border px-1.5 py-0.5 text-xs font-bold ${
                      SEVERITY_STYLES[severity] ?? "border-slate-600 text-slate-300"
                    }`}
                  >
                    {severity}
                  </span>
                )}
                {TONE_LABELS[tone] && (
                  <span className="ml-auto text-xs font-bold tracking-wider">
                    {TONE_LABELS[tone]}
                  </span>
                )}
              </div>
              {summary && <p className="mt-1 text-slate-300">{summary}</p>}
            </article>
          );
        })}
        <div ref={endRef} />
      </div>
    </section>
  );
}
