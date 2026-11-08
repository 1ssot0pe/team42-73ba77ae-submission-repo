/**
 * ViewCards: the notes from a module view model as a compact hairline list (design v2).
 * Tone is a small coloured dot plus a word, so colour is never the only signal.
 *   info -> neutral "Note", warn -> watch "Watch", good -> good "Good", bad -> alert "Alert".
 * Props: cards (normalised Card[]).
 */
import type { Tone } from "../shared";
import type { Card } from "./normalise";
import type { CardTone } from "../../types";

const TONE: Record<CardTone, { dot: Tone; word: string }> = {
  info: { dot: "neutral", word: "Note" },
  warn: { dot: "watch", word: "Watch" },
  good: { dot: "good", word: "Good" },
  bad: { dot: "alert", word: "Alert" },
};

export function ViewCards({ cards }: { cards: Card[] }) {
  return (
    <ul className="mnotes" role="list">
      {cards.map((c, i) => {
        const t = TONE[c.tone];
        return (
          <li key={`${c.title}-${i}`} className={`mnote mnote--${c.tone}`}>
            <span className="st-status mnote__status"><span className={`st-dot st-dot--${t.dot}`} aria-hidden="true" />{t.word}</span>
            <div className="mnote__main">
              {c.title ? <h3 className="mnote__title">{c.title}</h3> : null}
              {c.body ? <p className="mnote__body">{c.body}</p> : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
