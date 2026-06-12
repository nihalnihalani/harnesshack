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

  const waitingForFirstToken =
    (requested || state === "RESOLVED") &&
    derived.text.length === 0 &&
    !derived.blocked &&
    !derived.skipped &&
    !derived.failed;

  const elapsedMs = derived.complete ? asNumber(derived.complete.elapsed_ms) : null;
  const model = derived.complete ? asString(derived.complete.model) : null;

  return (
    <section className="flex min-h-0 flex-col rounded-lg border border-slate-800 bg-slate-950/60">
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <span className="text-xs uppercase tracking-widest text-slate-400">
          Postmortem — generated from the event log
        </span>
        <button
          type="button"
          onClick={resolve}
          disabled={!incidentId || state !== "MITIGATING" || requested}
          className="rounded border border-emerald-500/70 bg-emerald-500/15 px-4 py-1.5 text-sm font-bold text-emerald-200 hover:bg-emerald-500/30 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {state === "RESOLVED" ? "Resolved" : requested ? "Resolving…" : "Incident Resolved"}
        </button>
      </header>

      <div className="min-h-[14rem] flex-1 overflow-y-auto px-4 py-3">
        {postError && <p className="mb-2 text-sm text-red-400">{postError}</p>}

        {derived.blocked && (
          <div className="rounded border border-red-600/70 bg-red-600/10 p-3 text-sm text-red-300">
            <strong>BLOCKED BY GUARDRAIL.</strong> GLiGuard refused the complete
            postmortem text before any token was released
            {Array.isArray(derived.blocked.categories) &&
            derived.blocked.categories.length > 0
              ? ` (categories: ${(derived.blocked.categories as unknown[]).join(", ")})`
              : ""}
            . Nothing was streamed.
          </div>
        )}
        {derived.skipped && (
          <div className="rounded border border-amber-500/70 bg-amber-500/10 p-3 text-sm text-amber-300">
            <strong>Skipped — not configured.</strong> {derived.skipped}
          </div>
        )}
        {derived.failed && (
          <div className="rounded border border-red-500/70 bg-red-500/10 p-3 text-sm text-red-300">
            <strong>Postmortem generation failed.</strong> {derived.failed}
          </div>
        )}

        {waitingForFirstToken && (
          <div aria-label="Generating postmortem" className="space-y-2">
            <Skeleton count={1} height="1.4rem" width="55%" />
            <Skeleton count={4} height="0.9rem" />
            <Skeleton count={1} height="1.4rem" width="40%" />
            <Skeleton count={3} height="0.9rem" />
          </div>
        )}

        {derived.text.length > 0 && (
          <div className="postmortem-stream text-slate-200">
            <MarkDownRenderer variant="clear" textMarkdown={derived.text} />
            {!derived.complete && (
              <span aria-hidden className="streaming-caret">
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
            <p className="text-sm italic text-slate-500">
              Click &ldquo;Incident Resolved&rdquo; and the postmortem streams
              from the typed event log — the agent reads its own notes, it does
              not reconstruct.
            </p>
          )}
      </div>

      {derived.complete && (
        <footer className="border-t border-slate-800 px-4 py-2 text-xs text-slate-400">
          completed in{" "}
          <span className="font-mono font-bold text-emerald-300">
            {elapsedMs !== null ? `${(elapsedMs / 1000).toFixed(1)}s` : "—"}
          </span>{" "}
          (measured){model ? ` · ${model}` : ""} · GLiGuard-screened before
          streaming
        </footer>
      )}
    </section>
  );
}
