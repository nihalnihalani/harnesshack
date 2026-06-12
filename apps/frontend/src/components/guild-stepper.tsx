"use client";

// Guild state stepper [Investigating / Mitigating / Resolved] — driven ONLY
// by state.transition / incident.opened events off the SSE stream.

import type { IncidentState } from "@/lib/events";

const STATES: IncidentState[] = ["INVESTIGATING", "MITIGATING", "RESOLVED"];
const LABELS: Record<IncidentState, string> = {
  INVESTIGATING: "Investigating",
  MITIGATING: "Mitigating",
  RESOLVED: "Resolved",
};

export function GuildStepper({ state }: { state: IncidentState | null }) {
  const activeIndex = state === null ? -1 : STATES.indexOf(state);
  return (
    <ol aria-label="Guild incident state" className="flex items-center gap-2">
      {STATES.map((step, index) => {
        const done = activeIndex > index || (state === "RESOLVED" && index === 2);
        const current = activeIndex === index;
        return (
          <li key={step} className="flex items-center gap-2">
            <span
              className={`flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium transition-colors ${
                done
                  ? "border-emerald-500/70 bg-emerald-500/15 text-emerald-300"
                  : current
                    ? "border-sky-400/80 bg-sky-400/15 text-sky-200"
                    : "border-slate-700 bg-slate-900 text-slate-500"
              }`}
            >
              <span aria-hidden className="text-xs">
                {done ? "✓" : current ? "●" : "○"}
              </span>
              {LABELS[step]}
            </span>
            {index < STATES.length - 1 && (
              <span aria-hidden className="text-slate-600">
                →
              </span>
            )}
          </li>
        );
      })}
      {state === null && (
        <li className="text-xs text-slate-500">awaiting incident.opened event</li>
      )}
    </ol>
  );
}
