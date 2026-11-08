/**
 * BottleneckCard and BottleneckCards (design.md 8.19). Every module page opens with its bottlenecks.
 * BottleneckCard props: bottleneck (one entry from data/bottlenecks.json).
 * BottleneckCards props: module (module id such as "predose", "dosing", "postdose"; omit for all);
 *   ids (optional list of bottleneck ids to show instead, in that order); limit (default 3).
 *   Fetches /api/bottlenecks once per page load and filters by module.
 */
import { useEffect, useState } from "react";
import { api } from "../../api";
import type { Bottleneck } from "../../types";

let cache: Promise<Bottleneck[]> | null = null;
/** Cached fetch of /api/bottlenecks (one request per page load). */
export function loadBottlenecks(): Promise<Bottleneck[]> {
  if (!cache) {
    cache = api.bottlenecks().then((f) => f.bottlenecks ?? []).catch((e) => {
      cache = null;
      throw e;
    });
  }
  return cache;
}

export function BottleneckCard({ bottleneck: b }: { bottleneck: Bottleneck }) {
  return (
    <article className="bottleneck">
      <div className="eyebrow">Bottleneck</div>
      <h3 className="bottleneck__title">{b.title}</h3>
      <p className="bottleneck__number">{b.number}</p>
      <p className="bottleneck__source">
        {b.url ? <a className="link-smoke" href={b.url} target="_blank" rel="noopener noreferrer">{b.source}</a> : b.source}
      </p>
      <div className="stack stack--tight">
        <div className="eyebrow">How we move it</div>
        <p className="bottleneck__how">{b.how_we_tackle}</p>
      </div>
      {b.metric ? <p className="bottleneck__metric">Metric: {b.metric}</p> : null}
    </article>
  );
}

export interface BottleneckCardsProps {
  module?: string;
  ids?: string[];
  limit?: number;
}

export function BottleneckCards({ module, ids, limit = 3 }: BottleneckCardsProps) {
  const [all, setAll] = useState<Bottleneck[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    loadBottlenecks().then((b) => live && setAll(b)).catch(() => live && setFailed(true));
    return () => { live = false; };
  }, []);

  if (failed) return <p className="t-body-sm c-smoke">Bottlenecks could not be loaded. Check that the API is running.</p>;
  if (!all) return null;
  const shown = ids
    ? ids.map((id) => all.find((b) => b.id === id)).filter((b): b is Bottleneck => Boolean(b))
    : all.filter((b) => !module || b.module === module).slice(0, limit);
  if (shown.length === 0) return null;
  return (
    <div className="bottlenecks">
      {shown.map((b) => <BottleneckCard key={b.id} bottleneck={b} />)}
    </div>
  );
}
