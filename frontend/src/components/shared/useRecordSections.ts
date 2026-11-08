/**
 * useRecordSections(trialId, sections): record sections for charts that derive values the view does not send
 * (docs/visuals-spec.md 4.4). Wraps api.record, refetches on useTrial().tick, and caches one promise per
 * (trialId, tick, sections) so several charts on one page share a single fetch.
 */
import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { useTrial } from "../../trial";
import type { RecordSectionName, RecordSections } from "../../types";

type Result<K extends RecordSectionName> = Partial<Pick<RecordSections, K>>;

const cache = new Map<string, Promise<unknown>>();
const MAX_CACHE = 24;

function load<K extends RecordSectionName>(trialId: string, tick: number, sections: K[]): Promise<Result<K>> {
  const key = `${trialId}|${tick}|${sections.join(",")}`;
  let p = cache.get(key) as Promise<Result<K>> | undefined;
  if (!p) {
    p = api.record(trialId, sections);
    // A failed fetch is not cached, so the next render can retry.
    p.catch(() => cache.delete(key));
    cache.set(key, p);
    while (cache.size > MAX_CACHE) {
      const first = cache.keys().next().value;
      if (first === undefined) break;
      cache.delete(first);
    }
  }
  return p;
}

export function useRecordSections<K extends RecordSectionName>(
  trialId: string,
  sections: K[],
): { data: Result<K> | null; loading: boolean; error: string | null } {
  const { tick } = useTrial();
  // Sorted, de-duplicated key so ["alerts","blinding_metrics"] and its reverse share a fetch.
  const sectionKey = useMemo(() => [...new Set(sections)].sort().join(","), [sections]);
  const [state, setState] = useState<{ key: string; data: Result<K> | null; error: string | null }>({
    key: "", data: null, error: null,
  });
  const reqKey = `${trialId}|${tick}|${sectionKey}`;

  useEffect(() => {
    if (!trialId || !sectionKey) return;
    let alive = true;
    load(trialId, tick, sectionKey.split(",") as K[])
      .then((data) => { if (alive) setState({ key: reqKey, data, error: null }); })
      .catch((e: unknown) => {
        if (alive) setState((s) => ({ key: reqKey, data: s.data, error: e instanceof Error ? e.message : String(e) }));
      });
    return () => { alive = false; };
  }, [trialId, tick, sectionKey, reqKey]);

  // Keep showing the previous data for this trial while a refetch after a tick is in flight, so charts do not
  // flash empty.
  const loading = !!trialId && state.key !== reqKey;
  // Never show another trial's data (or another section set's).
  const sameSource = state.key.startsWith(`${trialId}|`) && state.key.endsWith(`|${sectionKey}`);
  return { data: sameSource ? state.data : null, loading, error: state.key === reqKey ? state.error : null };
}
