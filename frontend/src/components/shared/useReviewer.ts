/**
 * useReviewer(): [name, setName]. The reviewer's name, remembered in localStorage (via api.ts, try/catch)
 * and kept in sync across every approval slip on the page.
 */
import { useCallback, useEffect, useState } from "react";
import { getReviewer, setReviewer } from "../../api";

const EVENT = "unblind:reviewer";

export function useReviewer(): [string, (name: string) => void] {
  const [name, setName] = useState<string>(getReviewer);

  useEffect(() => {
    const on = (e: Event) => setName((e as CustomEvent<string>).detail);
    window.addEventListener(EVENT, on);
    return () => window.removeEventListener(EVENT, on);
  }, []);

  const update = useCallback((n: string) => {
    setReviewer(n);
    setName(n);
    window.dispatchEvent(new CustomEvent<string>(EVENT, { detail: n }));
  }, []);

  return [name, update];
}
