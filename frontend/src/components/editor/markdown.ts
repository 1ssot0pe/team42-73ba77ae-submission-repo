/**
 * Minimal markdown model for the protocol editor. Pure functions, no DOM.
 *
 * Supported block types: heading 1 ("# "), heading 2 ("## "), paragraph and bullet ("- ").
 * Every non-blank line is one block. Anything else (tables, numbered lists, bold, "### ") is kept
 * verbatim as paragraph text, so nothing is ever dropped.
 *
 * `gap` records a blank line before the block, so the source's own line structure survives:
 * serialise(parse(md)) === normalise(md), which only trims trailing whitespace at the ends,
 * turns CRLF into LF and collapses runs of blank lines into one.
 */

export type BlockType = "h1" | "h2" | "p" | "li";

export interface Block {
  type: BlockType;
  text: string;
  /** A blank line precedes this block in the markdown. */
  gap: boolean;
}

const PREFIX: Record<BlockType, string> = { h1: "# ", h2: "## ", p: "", li: "- " };

/** Detect a block marker at the start of a line. Returns the type and the text after the marker. */
export function marker(line: string): { type: BlockType; rest: string } | null {
  if (line.startsWith("## ")) return { type: "h2", rest: line.slice(3) };
  if (line.startsWith("# ")) return { type: "h1", rest: line.slice(2) };
  if (line.startsWith("- ")) return { type: "li", rest: line.slice(2) };
  return null;
}

export function parse(md: string): Block[] {
  const out: Block[] = [];
  let gap = false;
  for (const line of (md ?? "").split(/\r\n|\r|\n/)) {
    if (!line.trim()) {
      gap = out.length > 0;
      continue;
    }
    const m = marker(line);
    // A bare marker ("## " with nothing after it) has no content of its own: keep it as text.
    out.push(m && m.rest.trim() ? { type: m.type, text: m.rest, gap } : { type: "p", text: line, gap });
    gap = false;
  }
  return out;
}

export function serialise(blocks: Block[]): string {
  const lines: string[] = [];
  let pendingGap = false;
  for (const b of blocks) {
    const text = b.text.replace(/[\r\n]+/g, " ");
    if (!text.trim()) {
      // Empty blocks carry no content; keep their blank line for the next block.
      pendingGap = pendingGap || (b.gap && lines.length > 0);
      continue;
    }
    if ((b.gap || pendingGap) && lines.length > 0) lines.push("");
    lines.push(PREFIX[b.type] + text);
    pendingGap = false;
  }
  return lines.join("\n");
}

/** The canonical form of a markdown string for the supported block types. */
export function normalise(md: string): string {
  return (md ?? "")
    .split(/\r\n|\r|\n/)
    .map((l) => (l.trim() ? l : ""))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/^\n+/, "")
    .replace(/\n+$/, "");
}

/**
 * Take the first "# " heading out of a template so the title lives only in the name field.
 * Returns the heading text (or null) and the body without that line.
 */
export function takeTitle(md: string): { title: string | null; body: string } {
  const lines = (md ?? "").split(/\r\n|\r|\n/);
  const i = lines.findIndex((l) => /^# \S/.test(l));
  if (i < 0) return { title: null, body: md ?? "" };
  const title = lines[i].slice(2).trim();
  const rest = [...lines.slice(0, i), ...lines.slice(i + 1)];
  // Drop the blank line(s) that only separated the heading from its neighbours.
  while (rest.length && !rest[0].trim()) rest.shift();
  return { title, body: rest.join("\n") };
}

/** If the draft opens with "# <name>" (case-insensitive, trimmed), remove that line. Otherwise null. */
export function stripLeadingTitle(md: string, name: string): string | null {
  const lines = (md ?? "").split(/\r\n|\r|\n/);
  const i = lines.findIndex((l) => l.trim() !== "");
  if (i < 0) return null;
  const first = lines[i];
  if (!/^# /.test(first)) return null;
  if (first.slice(2).trim().toLowerCase() !== name.trim().toLowerCase()) return null;
  const rest = lines.slice(i + 1);
  while (rest.length && !rest[0].trim()) rest.shift();
  return rest.join("\n");
}
