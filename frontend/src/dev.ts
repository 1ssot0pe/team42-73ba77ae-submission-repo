/**
 * Developer toggle. When on, the nav overflow menu shows the trial ID, Gemini on or off and
 * real or stub module status. Hidden by default (design-v2.md Developer details).
 * useDeveloper() returns [on, setOn]. The value lives in localStorage (try/catch) and every
 * hook instance stays in sync through a window event, plus the storage event across tabs.
 */
import { useCallback, useEffect, useState } from "react";

const KEY = "parallax.developer";
const EVENT = "parallax:developer";

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function setDeveloper(on: boolean): void {
  try {
    if (on) localStorage.setItem(KEY, "1");
    else localStorage.removeItem(KEY);
  } catch {
    /* storage blocked: the event below still syncs this tab */
  }
  window.dispatchEvent(new CustomEvent<boolean>(EVENT, { detail: on }));
}

export function useDeveloper(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState<boolean>(read);
  useEffect(() => {
    const onLocal = (e: Event) => setOn(Boolean((e as CustomEvent<boolean>).detail));
    const onStorage = (e: StorageEvent) => { if (e.key === KEY) setOn(read()); };
    window.addEventListener(EVENT, onLocal);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(EVENT, onLocal);
      window.removeEventListener("storage", onStorage);
    };
  }, []);
  const set = useCallback((v: boolean) => setDeveloper(v), []);
  return [on, set];
}
