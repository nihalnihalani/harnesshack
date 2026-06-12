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
      className="rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3"
    >
      <div className="text-xs uppercase tracking-widest text-slate-400">
        Ownership
      </div>
      {!suggestion ? (
        <p className="mt-1 text-sm italic text-slate-500">
          awaiting ownership.suggested event
        </p>
      ) : confirmation ? (
        <p className="mt-1 text-sm text-emerald-300">
          ✓ Owner confirmed: {asString(confirmation.payload.owner) ?? owner} (by{" "}
          {asString(confirmation.payload.confirmed_by) ?? "human"})
        </p>
      ) : (
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <span className="text-sm text-slate-200">
            Suggested owner:{" "}
            <span className="font-bold text-sky-300">
              {owner ?? "(name not parseable from cited doc)"}
            </span>
          </span>
          {owner && (
            <button
              type="button"
              onClick={confirm}
              disabled={posting || !incidentId}
              className="rounded border border-sky-500/70 bg-sky-500/15 px-3 py-1 text-sm font-semibold text-sky-200 hover:bg-sky-500/30 disabled:opacity-50"
            >
              {posting ? "Confirming…" : "Confirm?"}
            </button>
          )}
        </div>
      )}
      {suggestion && !confirmation && (
        <p className="mt-1 text-[11px] text-slate-500">
          {note ?? "Suggested owner — awaiting confirmation"}
          {citation ? ` · cited: ${citation}` : ""}
        </p>
      )}
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </section>
  );
}
