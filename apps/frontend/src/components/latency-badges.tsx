"use client";

// Latency badges (Pioneer/GLiNER2, Airbyte Context Store, Senso).
// CLAIM INTEGRITY IS LAW: a number renders ONLY when a measured value arrived
// in an event payload. Otherwise the badge says "awaiting measurement" (or
// names the open blocker for an honest SKIPPED step). Never a made-up number.

import { asNumber, asString, type SherpaEvent } from "@/lib/events";

type Badge = {
  label: string;
  detail: string;
  measuredMs: number | null;
  blockedNote: string | null;
  type: "pioneer" | "airbyte" | "senso";
};

function deriveBadges(events: SherpaEvent[]): Badge[] {
  let pioneerMs: number | null = null;
  let airbyteMs: number | null = null;
  let airbyteBlocked: string | null = null;
  let sensoMs: number | null = null;

  for (const event of events) {
    const p = event.payload;
    if (event.event_type === "extraction.completed") {
      pioneerMs = asNumber(p.latency_ms) ?? pioneerMs;
    }
    if (event.event_type === "context.related_items") {
      airbyteMs = asNumber(p.latency_ms) ?? airbyteMs;
    }
    if (
      event.event_type === "SKIPPED_NOT_CONFIGURED" &&
      asString(p.step) === "airbyte_context_lookup"
    ) {
      airbyteBlocked = asString(p.blocker) ?? "blocked";
    }
    if (
      event.event_type === "runbook.retrieved" ||
      event.event_type === "ownership.suggested"
    ) {
      sensoMs = asNumber(p.latency_ms) ?? sensoMs;
    }
  }

  return [
    {
      label: "Pioneer / GLiNER2",
      detail: "schema extraction",
      measuredMs: pioneerMs,
      blockedNote: null,
      type: "pioneer",
    },
    {
      label: "Airbyte Context Store",
      detail: "live semantic query",
      measuredMs: airbyteMs,
      blockedNote: airbyteBlocked
        ? `skipped — not configured (${airbyteBlocked})`
        : null,
      type: "airbyte",
    },
    {
      label: "Senso retrieval",
      detail: "cited knowledge",
      measuredMs: sensoMs,
      blockedNote: null,
      type: "senso",
    },
  ];
}

// Custom SVG Icons for each badge type
function BadgeIcon({ type, active }: { type: Badge["type"]; active: boolean }) {
  const iconClass = `h-5 w-5 ${active ? "text-cyan-400" : "text-slate-600"}`;
  
  if (type === "pioneer") {
    return (
      <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
      </svg>
    );
  }
  if (type === "airbyte") {
    return (
      <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
      </svg>
    );
  }
  // senso
  return (
    <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
    </svg>
  );
}

export function LatencyBadges({ events }: { events: SherpaEvent[] }) {
  const badges = deriveBadges(events);
  return (
    <section
      aria-label="Measured latencies"
      className="grid grid-cols-1 gap-3 sm:grid-cols-3"
    >
      {badges.map((badge) => {
        const isMeasured = badge.measuredMs !== null;
        // Simple latency zone categorization for visual feedback (under 250ms is excellent)
        const isFast = isMeasured && (badge.measuredMs ?? 0) <= 250;
        
        return (
          <div
            key={badge.label}
            className="glass-panel glass-panel-hover rounded-xl p-4 flex flex-col justify-between shadow-lg relative overflow-hidden"
          >
            {/* Soft accent top colored edge on measurement arrival */}
            {isMeasured && (
              <div className={`absolute inset-x-0 top-0 h-[1.5px] ${isFast ? "bg-emerald-500/50" : "bg-amber-500/50"}`} />
            )}

            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-xs font-bold text-slate-200 tracking-wide">{badge.label}</div>
                <div className="text-[10px] font-bold font-mono text-slate-500 uppercase tracking-widest mt-0.5">{badge.detail}</div>
              </div>
              <BadgeIcon type={badge.type} active={isMeasured} />
            </div>

            <div className="mt-3.5">
              {badge.measuredMs !== null ? (
                <div className="flex items-baseline gap-1">
                  <span className={`font-mono text-xl font-black ${isFast ? "text-emerald-400" : "text-amber-400"}`}>
                    {badge.measuredMs.toFixed(1)}
                  </span>
                  <span className={`font-mono text-xs font-bold ${isFast ? "text-emerald-500" : "text-amber-500"}`}>
                    ms
                  </span>
                  <span className="ml-2 text-[10px] font-bold font-mono text-slate-500 uppercase tracking-wider">
                    MEASURED
                  </span>
                </div>
              ) : badge.blockedNote ? (
                <div className="text-xs font-bold font-mono text-amber-500 bg-amber-500/5 border border-amber-500/20 px-2 py-1 rounded-md uppercase tracking-wider">
                  {badge.blockedNote}
                </div>
              ) : (
                <div className="text-xs font-bold font-mono text-slate-500 italic animate-pulse uppercase tracking-wider">
                  awaiting telemetry...
                </div>
              )}

              {/* Small telemetry visual spark/zone bar */}
              <div className="mt-2.5 h-[3px] w-full rounded-full bg-slate-900 overflow-hidden relative">
                {badge.measuredMs !== null ? (
                  <div
                    style={{ width: `${Math.min((badge.measuredMs / 500) * 100, 100)}%` }}
                    className={`h-full rounded-full transition-all duration-500 ${isFast ? "bg-emerald-500" : "bg-amber-500"}`}
                  />
                ) : (
                  <div className="h-full w-1/3 rounded-full bg-slate-800 animate-shimmer" />
                )}
              </div>
            </div>
          </div>
        );
      })}
    </section>
  );
}
