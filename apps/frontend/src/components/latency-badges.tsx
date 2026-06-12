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
      detail: "schema-conditioned extraction",
      measuredMs: pioneerMs,
      blockedNote: null,
    },
    {
      label: "Airbyte Context Store",
      detail: "live semantic query",
      measuredMs: airbyteMs,
      blockedNote: airbyteBlocked
        ? `skipped — not configured (${airbyteBlocked})`
        : null,
    },
    {
      label: "Senso retrieval",
      detail: "cited runbook / ownership",
      measuredMs: sensoMs,
      blockedNote: null,
    },
  ];
}

export function LatencyBadges({ events }: { events: SherpaEvent[] }) {
  const badges = deriveBadges(events);
  return (
    <section
      aria-label="Measured latencies"
      className="grid grid-cols-1 gap-2 sm:grid-cols-3"
    >
      {badges.map((badge) => (
        <div
          key={badge.label}
          className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2"
        >
          <div className="text-xs font-semibold text-slate-200">{badge.label}</div>
          <div className="text-[11px] text-slate-500">{badge.detail}</div>
          {badge.measuredMs !== null ? (
            <div className="mt-1 font-mono text-lg font-bold text-emerald-300">
              {badge.measuredMs.toFixed(1)} ms
              <span className="ml-1 align-middle text-[10px] font-normal text-slate-500">
                measured
              </span>
            </div>
          ) : badge.blockedNote ? (
            <div className="mt-1 text-xs font-semibold text-amber-400">
              {badge.blockedNote}
            </div>
          ) : (
            <div className="mt-1 text-xs italic text-slate-500">
              awaiting measurement
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
