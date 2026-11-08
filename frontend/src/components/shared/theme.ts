/**
 * Theme preference: "auto" follows the system, "light" (Bench) or "dark" (Darkroom) set
 * data-theme on <html> so tokens.css's manual override wins. Stored in localStorage (try/catch).
 */
export type ThemePref = "auto" | "light" | "dark";
const KEY = "unblind.theme";

export function getThemePref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "auto";
  } catch {
    return "auto";
  }
}

export function applyTheme(pref: ThemePref): void {
  const el = document.documentElement;
  if (pref === "auto") el.removeAttribute("data-theme");
  else el.setAttribute("data-theme", pref);
  try {
    if (pref === "auto") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, pref);
  } catch {
    /* storage blocked */
  }
}
