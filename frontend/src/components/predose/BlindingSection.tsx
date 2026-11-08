/**
 * The co-designer's drafted "Blinding and expectancy" section (a paper document) and the protocol
 * version history ledger (v, day, why, changes).
 */
import type { ReactNode } from "react";
import { LedgerTable, formatDay } from "../shared";
import type { ProtocolVersion } from "../../types";

/** Tiny markdown: "## heading", "- bullet" and paragraphs. Enough for blinding_section_md. */
function renderMd(md: string): ReactNode[] {
  const out: ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      out.push(<ul key={`ul-${out.length}`} className="drafted__list">{bullets.map((b, i) => <li key={i}>{b}</li>)}</ul>);
      bullets = [];
    }
  };
  md.split("\n").forEach((raw) => {
    const ln = raw.trim();
    if (!ln) { flush(); return; }
    if (/^[-*] /.test(ln)) { bullets.push(ln.slice(2)); return; }
    flush();
    const h = /^(#{1,4})\s+(.*)$/.exec(ln);
    if (h) out.push(<h3 key={out.length} className="t-title">{h[2]}</h3>);
    else out.push(<p key={out.length} className="drafted__p">{ln}</p>);
  });
  flush();
  return out;
}

export function DraftedSection({ md }: { md: string | undefined }) {
  return (
    <section className="st-block drafted" aria-labelledby="drafted-title">
      <div className="stack stack--tight">
        <div className="st-label">Drafted by the co-designer</div>
        <h2 className="st-subtitle" id="drafted-title">Blinding section</h2>
      </div>
      {md ? <div className="drafted__body">{renderMd(md)}</div>
        : <p className="t-body-sm c-smoke">The drafted section appears after the first design review.</p>}
      <p className="t-caption c-ash">A draft for the protocol authors. It is not added to the protocol until someone saves it as a version.</p>
    </section>
  );
}

export function VersionHistory({ versions }: { versions: ProtocolVersion[] }) {
  const rows = versions.slice().reverse().map((v) => [
    <span className="num">v{v.version}</span>,
    <span className="num">{formatDay(v.day)}</span>,
    v.why,
    v.changes.length === 0 ? <span className="c-ash">none</span> : (
      <span className="vhist__changes">
        <span className="num">{v.changes.length} {v.changes.length === 1 ? "line" : "lines"}</span>
        <span className="vhist__first" title={v.changes.join("\n")}>{v.changes[0].replace(/^[+-]/, "")}</span>
      </span>
    ),
  ]);
  return (
    <LedgerTable title="Version history" columns={[{ label: "Version", mono: true }, { label: "Day", mono: true }, "Why", "Changes"]}
      rows={rows} empty="No versions yet." maxHeight={360} />
  );
}
