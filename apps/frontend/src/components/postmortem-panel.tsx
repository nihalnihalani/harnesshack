"use client";

// PostmortemPanel — the wow moment (demo beat 0:08-0:30). Resolve button
// POSTs /incidents/{id}/resolve; the panel then shows a skeleton shimmer
// until the first postmortem_token event arrives, renders tokens as they
// stream, and footers the MEASURED elapsed_ms from postmortem_complete.
// Blocked / blocked-dependency outcomes render their honest event — the
// panel never shows text that didn't come off the bus.

import { useMemo, useState } from "react";
import { MarkDownRenderer, Skeleton } from "@openuidev/react-ui";
import {
  API_BASE,
  asNumber,
  asString,
  type IncidentState,
  type SherpaEvent,
} from "@/lib/events";

type Props = {
  incidentId: string | null;
  state: IncidentState | null;
  events: SherpaEvent[];
};

export function PostmortemPanel({ incidentId, state, events }: Props) {
  const [requested, setRequested] = useState(false);
  const [postError, setPostError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const derived = useMemo(() => {
    const tokens: { index: number; token: string }[] = [];
    let complete: Record<string, unknown> | null = null;
    let blocked: Record<string, unknown> | null = null;
    let skipped: string | null = null;
    let failed: string | null = null;
    for (const event of events) {
      const p = event.payload;
      if (event.event_type === "postmortem_token") {
        const token = asString(p.token) ?? "";
        tokens.push({ index: asNumber(p.index) ?? tokens.length, token });
      } else if (event.event_type === "postmortem_complete") {
        complete = p;
      } else if (
        event.event_type === "BLOCKED_BY_GUARDRAIL" &&
        asString(p.step) === "postmortem"
      ) {
        blocked = p;
      } else if (
        event.event_type === "SKIPPED_NOT_CONFIGURED" &&
        asString(p.step) === "postmortem_generation"
      ) {
        skipped = asString(p.error);
      } else if (event.event_type === "postmortem_error") {
        failed = asString(p.error);
      }
    }
    tokens.sort((a, b) => a.index - b.index);
    return { text: tokens.map((t) => t.token).join(""), complete, blocked, skipped, failed };
  }, [events]);

  const resolve = async () => {
    if (!incidentId) return;
    setRequested(true);
    setPostError(null);
    try {
      const response = await fetch(
        `${API_BASE}/incidents/${encodeURIComponent(incidentId)}/resolve`,
        { method: "POST" },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setPostError(
          `resolve failed (${response.status}): ${body?.detail ?? response.statusText}`,
        );
        setRequested(false);
      }
    } catch (exc) {
      setPostError(`resolve failed: ${exc instanceof Error ? exc.message : String(exc)}`);
      setRequested(false);
    }
  };

  const copyPostmortemToClipboard = async () => {
    if (!derived.text) return;
    try {
      await navigator.clipboard.writeText(derived.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy postmortem text: ", err);
    }
  };

  const waitingForFirstToken =
    (requested || state === "RESOLVED") &&
    derived.text.length === 0 &&
    !derived.blocked &&
    !derived.skipped &&
    !derived.failed;

  const elapsedMs = derived.complete ? asNumber(derived.complete.elapsed_ms) : null;
  const model = derived.complete ? asString(derived.complete.model) : null;

  // Pulse effect only when in MITIGATING state (meaning investigation is complete and team is ready to resolve)
  const isMitigating = state === "MITIGATING";

  return (
    <section className="glass-panel rounded-xl overflow-hidden shadow-2xl relative flex min-h-[16rem] flex-col">
      {/* Top micro shine accent */}
      <div className={`absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-transparent to-transparent ${
        derived.complete 
          ? "via-emerald-500/30" 
          : waitingForFirstToken 
            ? "via-cyan-500/30" 
            : "via-slate-500/10"
      }`} />

      <header className="flex items-center justify-between border-b border-slate-900/60 bg-slate-950/30 px-4 py-3">
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span className="text-xs font-black uppercase tracking-widest text-slate-400 font-mono">
            STENO INCIDENT POSTMORTEM
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Demo cue: only while the incident is actually resolvable. */}
          {isMitigating && !requested && (
            <span className="demo-cue hidden sm:inline-flex items-center gap-1 text-[11px] font-black font-mono uppercase tracking-widest text-emerald-400">
              Click to resolve
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </span>
          )}

          {derived.text.length > 0 && (
            <button
              type="button"
              onClick={copyPostmortemToClipboard}
              className={`inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-bold font-mono rounded border transition-all duration-200 ${
                copied
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                  : "border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700 hover:text-slate-200"
              }`}
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              {copied ? "COPIED ✓" : "COPY REPORT"}
            </button>
          )}

          <button
            type="button"
            onClick={resolve}
            disabled={!incidentId || state !== "MITIGATING" || requested}
            className={`inline-flex items-center gap-2 rounded-lg border px-6 py-3 text-sm sm:text-base font-black font-mono uppercase tracking-wider transition-all duration-300 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 ${
              state === "RESOLVED"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : requested
                  ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-400"
                  : isMitigating
                    ? "border-2 border-emerald-400 bg-emerald-500/20 text-emerald-100 hover:bg-emerald-500/40 demo-action-glow hover:-translate-y-0.5"
                    : "border-slate-800 bg-slate-900/30 text-slate-500"
            }`}
          >
            {state === "RESOLVED" ? (
              <>
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                RESOLVED
              </>
            ) : requested ? (
              <>
                <span className="h-4 w-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                RESOLVING…
              </>
            ) : (
              <>
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                RESOLVE INCIDENT
              </>
            )}
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-5 py-4 custom-scrollbar bg-slate-950/5">
        {postError && <p className="mb-3.5 text-xs font-bold font-mono text-red-400 bg-red-500/5 border border-red-500/20 px-3.5 py-2 rounded-lg">{postError}</p>}

        {derived.blocked && (
          <div className="rounded-lg border border-red-600/30 bg-red-600/5 p-4 text-xs font-medium text-red-400 shadow-sm leading-relaxed">
            <strong className="font-extrabold uppercase font-mono tracking-wider mr-1">BLOCKED BY GUARDRAIL.</strong>
            GLiGuard security screeners refused the complete postmortem draft text because it violated privacy rules before any token was released
            {Array.isArray(derived.blocked.categories) &&
            derived.blocked.categories.length > 0
              ? ` (categories: ${(derived.blocked.categories as unknown[]).join(", ")})`
              : ""}
            . Nothing was streamed to the bus.
          </div>
        )}
        {derived.skipped && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-xs font-medium text-amber-400 leading-relaxed">
            <strong className="font-extrabold uppercase font-mono tracking-wider mr-1">Skipped — not configured.</strong>
            {derived.skipped}
          </div>
        )}
        {derived.failed && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-xs font-medium text-red-400 leading-relaxed">
            <strong className="font-extrabold uppercase font-mono tracking-wider mr-1">Postmortem generation failed.</strong>
            {derived.failed}
          </div>
        )}

        {waitingForFirstToken && (
          <div aria-label="Generating postmortem report" className="space-y-3.5 py-2">
            <div className="flex items-center gap-2 mb-4">
              <span className="h-3 w-3 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-[10px] font-black font-mono tracking-widest text-cyan-400 uppercase">DRAFTING POSTMORTEM REPORT VIA CLAUDE...</span>
            </div>
            <Skeleton count={1} height="1.4rem" width="55%" />
            <Skeleton count={4} height="0.9rem" />
            <Skeleton count={1} height="1.4rem" width="40%" />
            <Skeleton count={3} height="0.9rem" />
          </div>
        )}

        {derived.text.length > 0 && (
          <div className="postmortem-stream text-slate-200 markdown-body">
            <MarkDownRenderer variant="clear" textMarkdown={derived.text} />
            {!derived.complete && (
              <span aria-hidden className="streaming-caret ml-1 select-none">
                ▍
              </span>
            )}
          </div>
        )}

        {!requested &&
          state !== "RESOLVED" &&
          derived.text.length === 0 &&
          !derived.blocked &&
          !derived.skipped &&
          !derived.failed && (
            <div className="flex flex-col items-center justify-center p-6 text-center min-h-[10rem]">
              <svg className="h-10 w-10 text-slate-700 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              <p className="text-xs font-bold font-mono tracking-wider text-slate-500 uppercase">
                Ready for resolution
              </p>
              <p className="mt-1.5 max-w-sm text-[11px] text-slate-600 font-medium leading-normal">
                Click &ldquo;Resolve Incident&rdquo; to trigger immediate, automated postmortem streaming compiled directly from the structured event trail.
              </p>
            </div>
          )}
      </div>

      {derived.complete && (
        <footer className="border-t border-slate-900/60 bg-slate-950/20 px-4 py-2.5 text-[10px] font-bold font-mono text-slate-500 uppercase tracking-wider flex flex-wrap items-center justify-between gap-2 select-none">
          <div>
            COMPLETED IN{" "}
            <span className="font-extrabold text-emerald-400">
              {elapsedMs !== null ? `${(elapsedMs / 1000).toFixed(1)}s` : "—"}
            </span>{" "}
            (MEASURED) · GLIGUARD-SCREENED
          </div>
          {model && (
            <div className="bg-slate-900 border border-slate-800 px-2 py-0.5 rounded text-[9px] text-slate-400 font-extrabold uppercase">
              {model}
            </div>
          )}
        </footer>
      )}
    </section>
  );
}
