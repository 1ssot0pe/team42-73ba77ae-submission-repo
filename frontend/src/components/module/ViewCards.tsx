/**
 * ViewCards: the cards from a module view model as L1 notebook sheets. Tone maps to the Section 3 status tints,
 * and the tone is always spelled out as a word in a pill so colour is never the only signal.
 *   info -> neutral "Note", warn -> watch "Watch", good -> good "Good", bad -> alert "Alert".
 * Props: cards (normalised Card[]).
 */
import { StatusPill, type Tone } from "../shared";
import type { Card } from "./normalise";
import type { CardTone } from "../../types";

const TONE: Record<CardTone, { pill: Tone; word: string }> = {
  info: { pill: "neutral", word: "Note" },
  warn: { pill: "watch", word: "Watch" },
  good: { pill: "good", word: "Good" },
  bad: { pill: "alert", word: "Alert" },
};

export function ViewCards({ cards }: { cards: Card[] }) {
  return (
    <div className="mcards">
      {cards.map((c, i) => {
        const t = TONE[c.tone];
        return (
          <article key={`${c.title}-${i}`} className={`mcard mcard--${c.tone}`}>
            <div className="mcard__head">
              <StatusPill tone={t.pill}>{t.word}</StatusPill>
            </div>
            {c.title ? <h3 className="mcard__title">{c.title}</h3> : null}
            {c.body ? <p className="mcard__body">{c.body}</p> : null}
          </article>
        );
      })}
    </div>
  );
}
