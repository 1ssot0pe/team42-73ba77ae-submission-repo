/**
 * AgentNetwork (design.md 8.10). SVG on a taupe sheet: master in the centre, pre-dosing, dosing, post-dosing and
 * approvals around it. Edges are ink hairlines whose width grows with log(count) of messages (both directions
 * summed, the split in the tooltip). Faint dashed spokes show routes with no traffic yet. STUB modules are drawn
 * with a dashed outline and a STUB label. Props: edges (MessageEdge[] | null), moduleStatus (state.module_status).
 */
import { useRef } from "react";
import type { MessageEdge } from "../../types";
import { SpecimenTag, moduleLabel } from "../shared";
import { useElementSize } from "./useElementSize";

type NodeId = "master" | "predose" | "dosing" | "postdose" | "approvals";
const NODES: NodeId[] = ["master", "predose", "dosing", "postdose", "approvals"];
const R = 26;

function layout(w: number, h: number): Record<NodeId, { x: number; y: number }> {
  const side = w < 560 ? 0.17 : 0.2;
  return {
    master: { x: w / 2, y: h * 0.46 },
    predose: { x: w * side, y: h * 0.24 },
    approvals: { x: w * side, y: h * 0.7 },
    dosing: { x: w * (1 - side), y: h * 0.24 },
    postdose: { x: w * (1 - side), y: h * 0.7 },
  };
}

export interface AgentNetworkProps {
  edges: MessageEdge[] | null;
  moduleStatus: Record<string, string>;
}

export function AgentNetwork({ edges, moduleStatus }: AgentNetworkProps) {
  const box = useRef<HTMLDivElement>(null);
  const { width } = useElementSize(box);
  const w = Math.max(280, width || 720);
  const h = w < 560 ? 250 : 230;
  const pos = layout(w, h);

  // merge A->B and B->A into one undirected link
  const links = new Map<string, { a: NodeId; b: NodeId; total: number; parts: string[] }>();
  for (const e of edges ?? []) {
    const a = e.from as NodeId;
    const b = e.to as NodeId;
    if (!NODES.includes(a) || !NODES.includes(b) || a === b) continue;
    const key = [a, b].sort().join("|");
    const cur = links.get(key) ?? { a, b, total: 0, parts: [] };
    cur.total += e.count;
    cur.parts.push(`${moduleLabel(a)} to ${moduleLabel(b)}: ${e.count}`);
    links.set(key, cur);
  }
  const spokes = (["predose", "dosing", "postdose", "approvals"] as NodeId[])
    .filter((n) => !links.has(["master", n].sort().join("|")));
  const total = [...links.values()].reduce((s, l) => s + l.total, 0);

  return (
    <section className="mc-net" aria-label="Agent network">
      <div className="mc-net__head">
        <div className="stack stack--tight">
          <h2 className="t-title">Agent network</h2>
          <p className="t-body-sm c-smoke">
            Messages between the master agent and the module teams. Line width grows with the log of the count.
          </p>
        </div>
        <div className="row">
          <span className="mc-net__total"><span className="num">{total}</span> messages</span>
          <SpecimenTag />
        </div>
      </div>
      <div className="mc-net__canvas" ref={box}>
        <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img"
          aria-label={`Agent network: ${[...links.values()].map((l) => l.parts.join(", ")).join("; ") || "no messages yet"}`}>
          {spokes.map((n) => (
            <line key={`s-${n}`} className="mc-net__spoke" x1={pos.master.x} y1={pos.master.y} x2={pos[n].x} y2={pos[n].y} />
          ))}
          {[...links.values()].map((l) => {
            const p = pos[l.a];
            const q = pos[l.b];
            const sw = 1 + Math.log(l.total) * 1.25;
            const mx = (p.x + q.x) / 2;
            const my = (p.y + q.y) / 2;
            return (
              <g key={`${l.a}-${l.b}`}>
                <title>{l.parts.join("; ")}</title>
                <line className="mc-net__edge" x1={p.x} y1={p.y} x2={q.x} y2={q.y} strokeWidth={sw} />
                <text className="mc-net__count" x={mx} y={my} dy="0.35em" textAnchor="middle">{l.total}</text>
              </g>
            );
          })}
          {NODES.map((n) => {
            const { x, y } = pos[n];
            const stub = moduleStatus[n] === "stub";
            return (
              <g key={n} className={`mc-net__node${stub ? " mc-net__node--stub" : ""}`}>
                <circle className="mc-net__disc" cx={x} cy={y} r={R} />
                <circle className="mc-net__core" cx={x} cy={y} r={3} />
                <text className="mc-net__label" x={x} y={y + R + 15} textAnchor="middle">{moduleLabel(n)}</text>
                {stub ? <text className="mc-net__stub" x={x} y={y + R + 29} textAnchor="middle">STUB</text> : null}
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}
