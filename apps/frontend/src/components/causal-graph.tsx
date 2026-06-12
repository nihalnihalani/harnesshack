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
const NODE_RADIUS = 14;

export function CausalGraph({ edges, sql, affectedServices }: Props) {
  const [showSql, setShowSql] = useState(false);

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
        x: 70 + (index * (WIDTH - 140)) / Math.max(count - 1, 1),
        y: index % 2 === 0 ? 70 : 130,
      });
    });
    return map;
  }, [services]);

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-950/60">
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <span className="text-xs uppercase tracking-widest text-slate-400">
          Causal chain — ClickHouse LAG/LEAD
        </span>
        {sql && (
          <button
            type="button"
            onClick={() => setShowSql((value) => !value)}
            className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-300 hover:border-sky-500 hover:text-sky-300"
          >
            {showSql ? "hide SQL" : "show SQL"}
          </button>
        )}
      </header>

      {services.length === 0 ? (
        <p className="p-4 text-sm text-slate-500">
          Awaiting causal.chains_detected event — the graph renders only
          detected edges, never an illustration.
        </p>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${WIDTH} 200`}
            className="h-auto w-full"
            role="img"
            aria-label="Service causal graph"
          >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
              </marker>
            </defs>
            {edges.map((edge) => {
              const from = positions.get(edge.cause_service);
              const to = positions.get(edge.effect_service);
              if (!from || !to) return null;
              const midX = (from.x + to.x) / 2;
              const midY = (from.y + to.y) / 2 - 14;
              return (
                <g
                  key={`${edge.cause_service}->${edge.effect_service}`}
                  className="cursor-pointer"
                  onClick={() => setShowSql(true)}
                >
                  <line
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke="#f59e0b"
                    strokeWidth="2"
                    strokeDasharray="7 5"
                    markerEnd="url(#arrow)"
                    className="causal-edge"
                  />
                  <text
                    x={midX}
                    y={midY}
                    textAnchor="middle"
                    className="fill-amber-300 text-[12px] font-semibold"
                  >
                    precedes by {formatLag(edge.lag_seconds)}
                  </text>
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
                  className="cursor-pointer"
                  onClick={() => sql && setShowSql(true)}
                >
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={NODE_RADIUS}
                    className={
                      isEffect
                        ? "fill-red-500/30 stroke-red-400 causal-pulse"
                        : isCause
                          ? "fill-amber-500/30 stroke-amber-400"
                          : "fill-slate-700/50 stroke-slate-500"
                    }
                    strokeWidth="2"
                  />
                  <text
                    x={pos.x}
                    y={pos.y + NODE_RADIUS + 16}
                    textAnchor="middle"
                    className="fill-slate-300 text-[12px]"
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
              className="absolute inset-x-2 bottom-2 max-h-64 overflow-auto rounded-lg border border-slate-700 bg-slate-950/95 p-2 text-xs shadow-xl"
            >
              <div className="mb-1 flex items-center justify-between px-1">
                <span className="text-slate-400">
                  The exact SQL this query executed (from the event payload):
                </span>
                <button
                  type="button"
                  onClick={() => setShowSql(false)}
                  className="text-slate-400 hover:text-slate-200"
                >
                  close ✕
                </button>
              </div>
              <CodeBlock language="sql" codeString={sql} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
