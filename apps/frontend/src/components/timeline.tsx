"use client";

// Scrolling typed-event Timeline (demo beat 0:00-0:08). Every row is a real
// event off the SSE stream. SKIPPED_NOT_CONFIGURED / DEGRADED /
// BLOCKED_BY_GUARDRAIL rows are styled loudly — honesty is a feature.

import { useEffect, useRef, useState, useMemo } from "react";
import {
  asRecord,
  asString,
  formatClock,
  type SherpaEvent,
} from "@/lib/events";

const SEVERITY_STYLES: Record<string, string> = {
  P0: "bg-red-500/15 text-red-400 border-red-500/30",
  P1: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  P2: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  P3: "bg-sky-500/15 text-sky-400 border-sky-500/30",
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
  normal: "border-slate-800 bg-slate-900/10 hover:bg-slate-900/30",
  skipped:
    "border-amber-500/40 bg-amber-500/5 shadow-[inset_3.5px_0_0_0_theme(colors.amber.500)] hover:bg-amber-500/10",
  degraded:
    "border-orange-600/40 bg-orange-600/5 shadow-[inset_3.5px_0_0_0_theme(colors.orange.600)] hover:bg-orange-600/10",
  blocked:
    "border-red-600/50 bg-red-600/5 shadow-[inset_3.5px_0_0_0_theme(colors.red.600)] hover:bg-red-600/10",
  error:
    "border-red-500/40 bg-red-500/5 shadow-[inset_3.5px_0_0_0_theme(colors.red.500)] hover:bg-red-500/10",
  milestone: "border-emerald-500/40 bg-emerald-500/5 hover:bg-emerald-500/10 shadow-[inset_3.5px_0_0_0_theme(colors.emerald.500)]",
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
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedPayloads, setExpandedPayloads] = useState<Record<string, boolean>>({});

  // postmortem tokens stream to the PostmortemPanel, not the timeline.
  const rawRows = events.filter((event) => event.event_type !== "postmortem_token");

  // Filtering logic
  const filteredRows = useMemo(() => {
    return rawRows.filter((row) => {
      // 1. Severity filter
      if (filterSeverity !== "ALL") {
        const rowSev = asString(row.payload.severity);
        if (rowSev !== filterSeverity) return false;
      }

      // 2. Search query filter
      if (searchQuery.trim() !== "") {
        const q = searchQuery.toLowerCase();
        const typeMatch = row.event_type.toLowerCase().includes(q);
        const serviceMatch = (serviceOf(row) ?? "").toLowerCase().includes(q);
        const summaryMatch = (summaryOf(row) ?? "").toLowerCase().includes(q);
        return typeMatch || serviceMatch || summaryMatch;
      }

      return true;
    });
  }, [rawRows, filterSeverity, searchQuery]);

  useEffect(() => {
    // Only scroll if we are showing all events and new ones come in
    if (filterSeverity === "ALL" && searchQuery === "") {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [rawRows.length, filterSeverity, searchQuery]);

  const togglePayload = (key: string) => {
    setExpandedPayloads((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  return (
    <section
      aria-label="Typed event timeline"
      className="glass-panel flex h-full min-h-[30rem] flex-col rounded-xl overflow-hidden shadow-2xl relative"
    >
      {/* Top light bar */}
      <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-slate-500/25 to-transparent" />

      <header className="border-b border-slate-900/60 bg-slate-950/30 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h7" />
          </svg>
          <span className="text-xs font-black uppercase tracking-widest text-slate-400 font-mono">
            TYPED EVENT LOGSTREAM
          </span>
        </div>

        {/* Diagnostic counters */}
        <div className="text-[10px] font-bold font-mono text-slate-500 uppercase">
          {filteredRows.length === rawRows.length ? (
            <span>{rawRows.length} total events</span>
          ) : (
            <span className="text-cyan-400">{filteredRows.length} shown / {rawRows.length} total</span>
          )}
        </div>
      </header>

      {/* Control panel: search & severity filters */}
      <div className="border-b border-slate-900/40 bg-slate-950/15 p-3 flex flex-col sm:flex-row gap-2.5">
        <div className="relative flex-1">
          <span className="absolute inset-y-0 left-3 flex items-center text-slate-600">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </span>
          <input
            type="text"
            placeholder="Search logs by service, type or text..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-800 bg-slate-950/60 pl-8.5 pr-3 py-1.5 text-xs font-medium placeholder-slate-600 text-slate-200 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20 transition-all font-mono"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute inset-y-0 right-3 flex items-center text-slate-500 hover:text-slate-300"
            >
              ✕
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          <span className="text-[9px] font-bold font-mono text-slate-600 uppercase tracking-widest mr-1 hidden md:inline">SEVERITY:</span>
          {["ALL", "P0", "P1", "P2", "P3"].map((sev) => (
            <button
              key={sev}
              type="button"
              onClick={() => setFilterSeverity(sev)}
              className={`rounded px-2 py-1 text-[10px] font-bold font-mono transition-all cursor-pointer ${
                filterSeverity === sev
                  ? sev === "P0"
                    ? "bg-red-500/20 text-red-400 border border-red-500/30"
                    : sev === "P1"
                      ? "bg-orange-500/20 text-orange-400 border border-orange-500/30"
                      : "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                  : "border border-slate-800 bg-slate-950/40 text-slate-500 hover:border-slate-700 hover:text-slate-300"
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto p-4 custom-scrollbar" data-testid="timeline">
        {filteredRows.length === 0 && (
          <div className="flex flex-col items-center justify-center p-8 text-center min-h-[14rem]">
            <svg className="h-9 w-9 text-slate-700 mb-2 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-xs font-bold font-mono tracking-wider text-slate-500 uppercase">
              No matching events detected
            </p>
            <p className="mt-1 max-w-sm text-[11px] text-slate-600 font-medium">
              {searchQuery || filterSeverity !== "ALL"
                ? "Try resetting your active log filters and search query parameters."
                : "POST an alert payload to /trigger — the IncidentAgent worker will instantly populate this logstream."}
            </p>
          </div>
        )}
        
        {filteredRows.map((event, index) => {
          const tone = toneFor(event.event_type);
          const severity = asString(event.payload.severity);
          const service = serviceOf(event);
          const summary = summaryOf(event);
          const eventId = `${event.ts}-${event.event_type}-${index}`;
          const isExpanded = !!expandedPayloads[eventId];

          return (
            <article
              key={eventId}
              onClick={() => togglePayload(eventId)}
              className={`rounded-lg border px-3.5 py-2.5 text-sm transition-all duration-200 cursor-pointer ${TONE_STYLES[tone]} ${isExpanded ? "ring-1 ring-cyan-500/25 border-cyan-500/30" : ""}`}
            >
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 select-none">
                <time className="tabular-nums font-mono text-xs font-bold text-slate-500">{formatClock(event.ts)}</time>
                <span className="font-bold font-mono text-slate-200 tracking-wide uppercase text-[12px]">{event.event_type}</span>
                {service && (
                  <span className="rounded bg-slate-900 border border-slate-800/80 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-400">
                    {service}
                  </span>
                )}
                {severity && (
                  <span
                    className={`rounded border px-2 py-0.5 font-mono text-[10px] font-black ${
                      SEVERITY_STYLES[severity] ?? "border-slate-800 text-slate-400 bg-slate-900"
                    }`}
                  >
                    {severity}
                  </span>
                )}
                {TONE_LABELS[tone] && (
                  <span className={`ml-auto text-[10px] font-black tracking-wider uppercase ${
                    tone === "blocked" || tone === "error" ? "text-red-400" : "text-amber-400"
                  }`}>
                    {TONE_LABELS[tone]}
                  </span>
                )}
              </div>
              
              {summary && <p className="mt-1.5 text-slate-300 text-xs font-medium leading-relaxed">{summary}</p>}
              
              {/* Expandable JSON Payload view */}
              {isExpanded && (
                <div
                  onClick={(e) => e.stopPropagation()} // Prevent parent collapse toggle
                  className="mt-3.5 rounded-lg border border-slate-900 bg-slate-950 p-3 shadow-inner overflow-hidden flex flex-col"
                >
                  <div className="flex items-center justify-between border-b border-slate-900 pb-2 mb-2 select-none">
                    <div className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
                      <span className="text-[10px] font-black font-mono tracking-widest text-slate-500 uppercase">RAW EVENT WIRE DATA</span>
                    </div>
                    <button
                      onClick={() => togglePayload(eventId)}
                      className="text-[9px] font-bold font-mono text-slate-500 hover:text-slate-300 transition-colors"
                    >
                      COLLAPSE ✕
                    </button>
                  </div>
                  <pre className="text-[11px] font-mono text-slate-400 overflow-x-auto max-h-56 custom-scrollbar leading-5">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </div>
              )}
            </article>
          );
        })}
        <div ref={endRef} />
      </div>
    </section>
  );
}
