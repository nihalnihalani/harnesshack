"use client";

// CausalGraph (demo beat 0:42-0:55): service nodes + an animated edge labeled
// "precedes by Xm Ys". Everything rendered here comes from the
// causal.chains_detected event payload — including the ACTUAL SQL string the
// ClickHouse query executed (payload.sql, shipped by the agent), shown in a
// popover on click. No data -> an honest waiting state, never a fake graph.

import { useMemo, useState } from "react";
import { CodeBlock } from "@openuidev/react-ui";
import { type CausalEdge, formatLag } from "@/lib/events";

type Props = {
  edges: CausalEdge[];
  sql: string | null;
  affectedServices: string[]; // from extraction.completed payload
};

const WIDTH = 560;
const NODE_RADIUS = 18;

export function CausalGraph({ edges, sql, affectedServices }: Props) {
  const [showSql, setShowSql] = useState(false);
  const [copied, setCopied] = useState(false);

  const services = useMemo(() => {
    const ordered: string[] = [];
    const push = (name: string) => {
      if (!ordered.includes(name)) ordered.push(name);
    };
    for (const edge of edges) {
      push(edge.cause_service);
      push(edge.effect_service);
    }
    for (const name of affectedServices) push(name);
    return ordered;
  }, [edges, affectedServices]);

  const positions = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    const count = Math.max(services.length, 1);
    services.forEach((name, index) => {
      map.set(name, {
        x: 80 + (index * (WIDTH - 160)) / Math.max(count - 1, 1),
        y: index % 2 === 0 ? 65 : 125,
      });
    });
    return map;
  }, [services]);

  const copySqlToClipboard = async () => {
    if (!sql) return;
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy SQL: ", err);
    }
  };

  return (
    <section className="glass-panel rounded-xl overflow-hidden shadow-2xl relative">
      {/* Top micro gloss line */}
      <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-amber-500/20 to-transparent" />
      
      <header className="flex items-center justify-between border-b border-slate-900/60 bg-slate-950/30 px-4 py-3">
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span className="text-xs font-black uppercase tracking-widest text-slate-400 font-mono">
            CAUSAL CHAIN ANALYTICS (ClickHouse LEAD/LAG)
          </span>
        </div>
        {sql && (
          <button
            type="button"
            onClick={() => setShowSql((value) => !value)}
            className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-bold font-mono transition-all duration-200 ${
              showSql
                ? "border-amber-500/40 bg-amber-500/10 text-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.1)]"
                : "border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700 hover:text-slate-200"
            }`}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            {showSql ? "HIDE SQL" : "SHOW SQL"}
          </button>
        )}
      </header>

      {services.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-8 text-center min-h-[12rem] bg-slate-950/10">
          <svg className="h-10 w-10 text-slate-700 mb-2.5 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M7 12l3-3 3 3 4-4M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
          <p className="text-xs font-bold font-mono tracking-wider text-slate-500 uppercase">
            Awaiting causal.chains_detected event
          </p>
          <p className="mt-1 max-w-sm text-xs text-slate-600 font-medium">
            The graph renders only measured, mathematically correlated causal loops from lead/lag analysis.
          </p>
        </div>
      ) : (
        <div className="relative p-4 bg-gradient-to-b from-slate-950/20 to-slate-950/40">
          <svg
            viewBox={`0 0 ${WIDTH} 185`}
            className="h-auto w-full select-none"
            role="img"
            aria-label="Service causal graph"
          >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="17"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#f59e0b" />
              </marker>
              {/* Glowing gradients for node fills */}
              <radialGradient id="cause-grad" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="rgba(245, 158, 11, 0.45)" />
                <stop offset="100%" stopColor="rgba(245, 158, 11, 0.1)" />
              </radialGradient>
              <radialGradient id="effect-grad" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="rgba(239, 68, 68, 0.45)" />
                <stop offset="100%" stopColor="rgba(239, 68, 68, 0.1)" />
              </radialGradient>
              <radialGradient id="normal-grad" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="rgba(148, 163, 184, 0.2)" />
                <stop offset="100%" stopColor="rgba(30, 41, 59, 0.05)" />
              </radialGradient>
            </defs>
            {edges.map((edge) => {
              const from = positions.get(edge.cause_service);
              const to = positions.get(edge.effect_service);
              if (!from || !to) return null;
              const midX = (from.x + to.x) / 2;
              const midY = (from.y + to.y) / 2 - 12;
              return (
                <g
                  key={`${edge.cause_service}->${edge.effect_service}`}
                  className="cursor-pointer group"
                  onClick={() => setShowSql(true)}
                >
                  <line
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke="#f59e0b"
                    strokeWidth="2.5"
                    strokeDasharray="6 4"
                    markerEnd="url(#arrow)"
                    className="causal-edge transition-all group-hover:stroke-amber-400"
                  />
                  {/* Subtle blur backing line for glow */}
                  <line
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke="#f59e0b"
                    strokeWidth="6"
                    className="opacity-0 group-hover:opacity-15 blur-sm transition-opacity"
                  />
                  <g className="filter drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)]">
                    <rect
                      x={midX - 70}
                      y={midY - 11}
                      width="140"
                      height="18"
                      rx="4"
                      fill="#0f172a"
                      stroke="#f59e0b"
                      strokeWidth="1"
                      className="opacity-95"
                    />
                    <text
                      x={midX}
                      y={midY + 2}
                      textAnchor="middle"
                      className="fill-amber-300 text-[10px] font-bold font-mono tracking-wide uppercase"
                    >
                      precedes by {formatLag(edge.lag_seconds)}
                    </text>
                  </g>
                </g>
              );
            })}
            {services.map((name) => {
              const pos = positions.get(name);
              if (!pos) return null;
              const isCause = edges.some((edge) => edge.cause_service === name);
              const isEffect = edges.some((edge) => edge.effect_service === name);
              return (
                <g
                  key={name}
                  className="cursor-pointer group"
                  onClick={() => sql && setShowSql(true)}
                >
                  {/* Glowing halo ring on hover */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={NODE_RADIUS + 4}
                    fill="none"
                    stroke={isEffect ? "#f87171" : isCause ? "#fbbf24" : "#94a3b8"}
                    strokeWidth="1.5"
                    className="opacity-0 group-hover:opacity-40 transition-opacity"
                  />
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={NODE_RADIUS}
                    fill={isEffect ? "url(#effect-grad)" : isCause ? "url(#cause-grad)" : "url(#normal-grad)"}
                    stroke={isEffect ? "#f87171" : isCause ? "#fbbf24" : "#475569"}
                    className={
                      isEffect
                        ? "causal-pulse stroke-red-500"
                        : isCause
                          ? "causal-pulse-cause stroke-amber-500"
                          : "stroke-slate-600"
                    }
                    strokeWidth="2"
                  />
                  {/* Small core element */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r="4"
                    fill={isEffect ? "#ef4444" : isCause ? "#f59e0b" : "#475569"}
                  />
                  <text
                    x={pos.x}
                    y={pos.y + NODE_RADIUS + 16}
                    textAnchor="middle"
                    className="fill-slate-200 text-[11px] font-bold font-mono uppercase tracking-wide group-hover:fill-sky-300 transition-colors"
                  >
                    {name}
                  </text>
                </g>
              );
            })}
          </svg>

          {showSql && sql && (
            <div
              role="dialog"
              aria-label="Causal query SQL"
              className="absolute inset-x-3 bottom-3 max-h-72 overflow-hidden rounded-xl border border-slate-800/80 bg-slate-950/95 shadow-2xl flex flex-col"
            >
              <div className="flex items-center justify-between border-b border-slate-900/80 bg-slate-900/40 px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-cyan-500 animate-pulse" />
                  <span className="text-[11px] font-bold font-mono tracking-wider text-slate-400 uppercase">
                    Clickhouse LEAD/LAG Correlation query SQL
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={copySqlToClipboard}
                    className="rounded border border-slate-800 bg-slate-900/60 px-2 py-1 text-[10px] font-bold font-mono text-slate-400 hover:border-slate-700 hover:text-slate-200 transition-colors"
                  >
                    {copied ? "COPIED ✓" : "COPY SQL"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowSql(false)}
                    className="rounded border border-slate-800 bg-slate-900/60 px-2 py-1 text-[10px] font-bold font-mono text-slate-400 hover:border-slate-700 hover:text-slate-200 transition-colors"
                  >
                    CLOSE ✕
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-auto p-3 text-xs font-mono bg-[#03060f]">
                <CodeBlock language="sql" codeString={sql} />
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
