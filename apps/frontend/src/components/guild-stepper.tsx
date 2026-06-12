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

// Beautiful custom inline SVG icons for each state
function StateIcon({ step, done, current }: { step: IncidentState; done: boolean; current: boolean }) {
  const iconClass = `h-4 w-4 ${done ? "text-emerald-400" : current ? "text-cyan-400" : "text-slate-600"}`;
  
  if (step === "INVESTIGATING") {
    return (
      <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    );
  }
  if (step === "MITIGATING") {
    return (
      <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
      </svg>
    );
  }
  // RESOLVED
  return (
    <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  );
}

export function GuildStepper({ state }: { state: IncidentState | null }) {
  const activeIndex = state === null ? -1 : STATES.indexOf(state);
  return (
    <ol aria-label="Guild incident state" className="flex items-center gap-1.5 sm:gap-3 bg-slate-950/40 p-1 rounded-full border border-slate-800/80 max-w-full overflow-x-auto">
      {STATES.map((step, index) => {
        const done = activeIndex > index || (state === "RESOLVED" && index === 2);
        const current = activeIndex === index;
        return (
          <li key={step} className="flex items-center gap-1.5 sm:gap-2">
            <span
              className={`flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider font-mono transition-all duration-300 border ${
                done
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400 shadow-[inset_0_1px_1px_rgba(255,255,255,0.05),0_0_8px_rgba(16,185,129,0.05)]"
                  : current
                    ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-300 shadow-[inset_0_1px_1px_rgba(255,255,255,0.05),0_0_12px_rgba(34,211,238,0.08)]"
                    : "border-slate-800/80 bg-slate-900/30 text-slate-500"
              }`}
            >
              <StateIcon step={step} done={done} current={current} />
              <span className="hidden sm:inline">{LABELS[step]}</span>
              <span className="sm:hidden text-[10px]">{LABELS[step].slice(0, 4)}..</span>
            </span>
            {index < STATES.length - 1 && (
              <span aria-hidden className={`text-xs ${activeIndex > index ? "text-emerald-500/50" : "text-slate-800"}`}>
                ➔
              </span>
            )}
          </li>
        );
      })}
      {state === null && (
        <li className="text-[10px] px-3 font-bold font-mono text-slate-500 animate-pulse uppercase">
          Awaiting initialization...
        </li>
      )}
    </ol>
  );
}
