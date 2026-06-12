"use client";

// F2 static fallback (demo fallback table: "OpenUI SSE stream stalls ->
// hidden static postmortem div revealed on F2"). The artifact is the cached
// output of a REAL completed run served by GET /fallback/postmortem; a 404
// means no real run has happened yet and the feature is DISABLED — there is
// no placeholder content on any path.

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/events";

type FallbackState =
  | { kind: "hidden" }
  | { kind: "visible"; html: string }
  | { kind: "disabled"; detail: string };

export function FallbackPostmortem() {
  const [state, setState] = useState<FallbackState>({ kind: "hidden" });

  useEffect(() => {
    const onKeyDown = async (event: KeyboardEvent) => {
      if (event.key !== "F2") return;
      event.preventDefault();
      setState((current) => {
        if (current.kind === "visible") return { kind: "hidden" };
        return current;
      });
      if (state.kind === "visible") return; // toggled off above
      try {
        const response = await fetch(`${API_BASE}/fallback/postmortem`);
        if (response.status === 404) {
          setState({
            kind: "disabled",
            detail:
              "F2 fallback disabled — no cached real run exists yet (honest 404; the artifact is only written after a live postmortem succeeds).",
          });
          return;
        }
        if (!response.ok) {
          setState({ kind: "disabled", detail: `fallback fetch failed (${response.status})` });
          return;
        }
        setState({ kind: "visible", html: await response.text() });
      } catch (exc) {
        setState({
          kind: "disabled",
          detail: `fallback fetch failed: ${exc instanceof Error ? exc.message : String(exc)}`,
        });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // state.kind is read inside the handler for toggle behavior:
  }, [state.kind]);

  useEffect(() => {
    if (state.kind !== "disabled") return;
    const timer = setTimeout(() => setState({ kind: "hidden" }), 6000);
    return () => clearTimeout(timer);
  }, [state]);

  if (state.kind === "hidden") return null;

  if (state.kind === "disabled") {
    return (
      <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded border border-amber-500/70 bg-slate-950 px-4 py-2 text-sm text-amber-300 shadow-xl">
        {state.detail}
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/95 p-6">
      <div className="mx-auto flex h-full max-w-4xl flex-col rounded-lg border border-slate-700 bg-slate-950">
        <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2 text-xs text-slate-400">
          <span>
            F2 STATIC FALLBACK — cached output of a real completed run (live
            stream unavailable)
          </span>
          <button
            type="button"
            onClick={() => setState({ kind: "hidden" })}
            className="text-slate-400 hover:text-slate-200"
          >
            close (F2) ✕
          </button>
        </header>
        <iframe
          title="Cached real postmortem run"
          srcDoc={state.html}
          className="h-full w-full flex-1 rounded-b-lg bg-transparent"
        />
      </div>
    </div>
  );
}
