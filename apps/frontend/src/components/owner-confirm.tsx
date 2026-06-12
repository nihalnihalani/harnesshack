"use client";

// "Suggested owner: <name> — Confirm?" (demo beat 0:30-0:38).
// The suggestion comes from the ownership.suggested event (parsed from the
// CITED Senso doc by the agent — null means honestly unparseable). The
// Confirm button POSTs /incidents/{id}/confirm-owner; the confirmed state
// renders only after the owner_confirmed event arrives back over SSE —
// the UI never pretends a confirmation the log doesn't have.

import { useState } from "react";
import { API_BASE, asString, type SherpaEvent } from "@/lib/events";

type Props = {
  incidentId: string | null;
  events: SherpaEvent[];
};

export function OwnerConfirm({ incidentId, events }: Props) {
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const suggestion = [...events]
    .reverse()
    .find((event) => event.event_type === "ownership.suggested");
  const confirmation = [...events]
    .reverse()
    .find((event) => event.event_type === "owner_confirmed");

  const owner = suggestion ? asString(suggestion.payload.suggested_owner) : null;
  const citation = suggestion ? asString(suggestion.payload.citation) : null;
  const note = suggestion ? asString(suggestion.payload.note) : null;

  const confirm = async () => {
    if (!incidentId || !owner) return;
    setPosting(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE}/incidents/${encodeURIComponent(incidentId)}/confirm-owner`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ owner, confirmed_by: "human" }),
        },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setError(
          `confirm failed (${response.status}): ${body?.detail ?? response.statusText}`,
        );
      }
      // Success state renders when the owner_confirmed event arrives on SSE.
    } catch (exc) {
      setError(`confirm failed: ${exc instanceof Error ? exc.message : String(exc)}`);
    } finally {
      setPosting(false);
    }
  };

  return (
    <section
      aria-label="Owner suggestion"
      className="glass-panel rounded-xl px-5 py-4 shadow-xl relative overflow-hidden"
    >
      {/* Top accent line */}
      <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent" />

      <div className="flex items-center gap-2 mb-3">
        <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
        <span className="text-xs font-black uppercase tracking-widest text-slate-400 font-mono">
          OWNERSHIP & ESCALATION
        </span>
      </div>

      {!suggestion ? (
        <div className="flex items-center gap-2 py-1">
          <span className="h-2 w-2 rounded-full bg-slate-800 animate-pulse" />
          <p className="text-xs font-medium font-mono text-slate-500 uppercase tracking-wider">
            Awaiting ownership.suggested event...
          </p>
        </div>
      ) : confirmation ? (
        <div className="flex items-center gap-3 bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
            <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <div className="text-[10px] font-black font-mono text-emerald-500 uppercase tracking-widest leading-none">
              AUTHORITY APPROVED
            </div>
            <p className="mt-1 text-sm font-semibold text-slate-100">
              {asString(confirmation.payload.owner) ?? owner}{" "}
              <span className="text-xs text-slate-400 font-normal">
                escalated by {asString(confirmation.payload.confirmed_by) ?? "human"}
              </span>
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/40 border border-slate-800/60 rounded-xl p-3.5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <div>
                <div className="text-[9px] font-black font-mono text-sky-400 uppercase tracking-widest leading-none">
                  SUGGESTED INCIDENT COMMANDER
                </div>
                <div className="mt-1 text-base font-extrabold text-slate-100">
                  {owner ?? "(name not parseable from cited doc)"}
                </div>
              </div>
            </div>
            {owner && (
              <button
                type="button"
                onClick={confirm}
                disabled={posting || !incidentId}
                className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500 bg-sky-500/15 px-4.5 py-2 text-xs font-extrabold font-mono uppercase tracking-wider text-sky-300 hover:bg-sky-500/35 transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_12px_rgba(14,165,233,0.1)] hover:shadow-[0_0_16px_rgba(14,165,233,0.2)] hover:-translate-y-0.5"
              >
                {posting ? (
                  <>
                    <span className="h-3 w-3 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
                    CONFIRMING…
                  </>
                ) : (
                  <>
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    CONFIRM APPOINTMENT
                  </>
                )}
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-400 border-t border-slate-900/60 pt-2.5 px-1">
            <span className="font-semibold text-slate-300">{note ?? "Suggested owner — awaiting confirmation"}</span>
            {citation && (
              <>
                <span className="text-slate-600">•</span>
                <span className="inline-flex items-center gap-1 font-mono text-[10px] text-slate-500 bg-slate-900 border border-slate-800/80 px-2 py-0.5 rounded-md uppercase">
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                  Cited: {citation}
                </span>
              </>
            )}
          </div>
        </div>
      )}
      {error && <p className="mt-2.5 text-xs font-bold font-mono text-red-400 bg-red-500/5 border border-red-500/20 px-3 py-1.5 rounded-lg">{error}</p>}
    </section>
  );
}
