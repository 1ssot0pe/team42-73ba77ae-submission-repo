/**
 * A lightweight block editor for protocol markdown: heading 1, heading 2, paragraph and bullet.
 *
 * One contentEditable root whose children are rendered imperatively from a block model (React renders
 * no children into it, so it never fights the browser for the DOM). Ordinary typing is left to the
 * browser and read back from the DOM on input, so the block you are typing in is not re-rendered and
 * the caret stays put. Structural edits (Enter, Backspace at the start, Delete at the end, paste,
 * edits across blocks, "# " / "## " / "- " shortcuts) go through the model, then the DOM is
 * re-rendered and the caret restored. Read-only mode renders the same blocks with React.
 */
import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import { marker, parse, serialise, type Block, type BlockType } from "./markdown";
import "../../styles/editor.css";

interface Props {
  value: string;
  onChange?: (md: string) => void;
  readOnly?: boolean;
  placeholder?: string;
  ariaLabel?: string;
  className?: string;
}

interface Caret { block: number; offset: number }

const TAGS: Record<BlockType, string> = { h1: "H1", h2: "H2", p: "P", li: "LI" };

const empty = (): Block => ({ type: "p", text: "", gap: false });
const clean = (s: string) => s.replace(/\u200b/g, "").replace(/[\u00a0\r\n\t]/g, " ");

/* ---------- DOM <-> model */

function render(root: HTMLElement, blocks: Block[]) {
  const frag = document.createDocumentFragment();
  let list: HTMLUListElement | null = null;
  for (const b of blocks) {
    const el = document.createElement(TAGS[b.type]);
    if (b.gap) el.dataset.gap = "1";
    if (b.text) el.textContent = b.text;
    else el.appendChild(document.createElement("br"));
    if (b.type === "li") {
      if (!list) { list = document.createElement("ul"); frag.appendChild(list); }
      list.appendChild(el);
    } else {
      list = null;
      frag.appendChild(el);
    }
  }
  root.replaceChildren(frag);
}

/** Block elements in document order (list items flattened). */
function blockEls(root: HTMLElement): HTMLElement[] {
  const out: HTMLElement[] = [];
  root.childNodes.forEach((n) => {
    if (!(n instanceof HTMLElement)) return;
    if (n.tagName === "UL" || n.tagName === "OL") {
      n.childNodes.forEach((c) => { if (c instanceof HTMLElement) out.push(c); });
    } else out.push(n);
  });
  return out;
}

/** Read blocks back from the DOM. `canonical` is false when the browser left markup we do not render. */
function read(root: HTMLElement): { blocks: Block[]; canonical: boolean } {
  const blocks: Block[] = [];
  let canonical = true;
  const leaf = (el: HTMLElement) => {
    const kids = Array.from(el.childNodes);
    const text = clean(el.textContent ?? "");
    const ok = text
      ? kids.every((k) => k.nodeType === Node.TEXT_NODE)
      : kids.length === 1 && kids[0].nodeName === "BR";
    if (!ok) canonical = false;
    return text;
  };
  root.childNodes.forEach((n) => {
    if (n.nodeType === Node.TEXT_NODE) {
      canonical = false;
      const t = clean(n.textContent ?? "");
      if (t) blocks.push({ type: "p", text: t, gap: false });
      return;
    }
    if (!(n instanceof HTMLElement)) { canonical = false; return; }
    const gap = n.dataset.gap === "1";
    switch (n.tagName) {
      case "H1": blocks.push({ type: "h1", text: leaf(n), gap }); break;
      case "H2": blocks.push({ type: "h2", text: leaf(n), gap }); break;
      case "P": blocks.push({ type: "p", text: leaf(n), gap }); break;
      case "UL": case "OL": {
        if (n.tagName === "OL" || n.childNodes.length === 0) canonical = false;
        n.childNodes.forEach((c) => {
          if (c instanceof HTMLElement && c.tagName === "LI") {
            blocks.push({ type: "li", text: leaf(c), gap: c.dataset.gap === "1" });
          } else {
            canonical = false;
            const t = clean(c.textContent ?? "");
            if (t) blocks.push({ type: "li", text: t, gap: false });
          }
        });
        break;
      }
      case "BR": canonical = false; break;
      default: {
        canonical = false;
        const t = clean(n.textContent ?? "");
        blocks.push({ type: "p", text: t, gap });
      }
    }
  });
  if (blocks.length === 0) { blocks.push(empty()); canonical = false; }
  return { blocks, canonical };
}

function blockIndexOf(root: HTMLElement, node: Node | null): number {
  const els = blockEls(root);
  let n: Node | null = node;
  while (n && n !== root) {
    const i = els.indexOf(n as HTMLElement);
    if (i >= 0) return i;
    n = n.parentNode;
  }
  return -1;
}

function pointOf(root: HTMLElement, node: Node, offset: number): Caret | null {
  if (!root.contains(node)) return null;
  const els = blockEls(root);
  let block = blockIndexOf(root, node);
  if (block < 0) {
    // Caret sits on the root itself (between blocks): snap to the nearest block.
    if (node === root) {
      const child = root.childNodes[offset] ?? null;
      block = child ? blockIndexOf(root, child.firstChild ?? child) : els.length - 1;
      if (block < 0) block = Math.max(0, els.length - 1);
      return { block, offset: 0 };
    }
    return null;
  }
  const r = document.createRange();
  r.selectNodeContents(els[block]);
  try { r.setEnd(node, offset); } catch { return { block, offset: 0 }; }
  return { block, offset: clean(r.toString()).length };
}

function getSel(root: HTMLElement): { start: Caret; end: Caret } | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return null;
  const r = sel.getRangeAt(0);
  const start = pointOf(root, r.startContainer, r.startOffset);
  const end = pointOf(root, r.endContainer, r.endOffset);
  if (!start || !end) return null;
  return { start, end };
}

function setCaret(root: HTMLElement, c: Caret) {
  const els = blockEls(root);
  const el = els[Math.min(Math.max(c.block, 0), els.length - 1)];
  if (!el) return;
  const sel = window.getSelection();
  if (!sel) return;
  let left = c.offset;
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode() as Text | null;
  let target: [Node, number] = [el, 0];
  while (node) {
    const len = node.data.length;
    if (left <= len) { target = [node, left]; break; }
    left -= len;
    target = [node, len];
    node = walker.nextNode() as Text | null;
  }
  const r = document.createRange();
  r.setStart(target[0], target[1]);
  r.collapse(true);
  sel.removeAllRanges();
  sel.addRange(r);
}

/* ---------- model edits (pure on a copy) */

function deleteRange(blocks: Block[], s: Caret, e: Caret): Block[] {
  const out = blocks.map((b) => ({ ...b }));
  const a = out[s.block], b = out[e.block];
  if (!a || !b) return out;
  a.text = a.text.slice(0, s.offset) + b.text.slice(e.offset);
  out.splice(s.block + 1, e.block - s.block);
  return out;
}

function insertText(blocks: Block[], at: Caret, text: string): { blocks: Block[]; caret: Caret } {
  const out = blocks.map((b) => ({ ...b }));
  const lines = text.replace(/\r\n|\r/g, "\n").split("\n");
  const cur = out[at.block];
  const head = cur.text.slice(0, at.offset);
  const tail = cur.text.slice(at.offset);
  if (lines.length === 1) {
    cur.text = head + clean(lines[0]);
    const offset = cur.text.length;
    cur.text += tail;
    return { blocks: out, caret: { block: at.block, offset } };
  }
  const pasted = parse(text);
  if (pasted.length === 0) return { blocks: out, caret: at };
  // Text that opens with a line break starts on a new block rather than joining the current one.
  if (cur.text && /^[ \t]*\n/.test(text.replace(/\r\n|\r/g, "\n"))) pasted.unshift(empty());
  const [first, ...rest] = pasted;
  if (!cur.text && cur.type === "p") { cur.type = first.type; cur.text = first.text; }
  else cur.text = head + first.text;
  const added = rest.map((b) => ({ ...b, text: clean(b.text) }));
  out.splice(at.block + 1, 0, ...added);
  const lastIdx = at.block + added.length;
  const last = out[lastIdx];
  const offset = (added.length ? last.text : cur.text).length;
  last.text += tail;
  return { blocks: out, caret: { block: lastIdx, offset } };
}

function splitBlock(blocks: Block[], at: Caret): { blocks: Block[]; caret: Caret } {
  const out = blocks.map((b) => ({ ...b }));
  const cur = out[at.block];
  // Enter in an empty bullet ends the list.
  if (cur.type === "li" && !cur.text) {
    cur.type = "p";
    return { blocks: out, caret: at };
  }
  // Enter at the start of a non-empty block pushes it down.
  if (at.offset === 0 && cur.text) {
    out.splice(at.block, 0, { type: cur.type === "li" ? "li" : "p", text: "", gap: cur.gap });
    cur.gap = false;
    return { blocks: out, caret: { block: at.block + 1, offset: 0 } };
  }
  const right = cur.text.slice(at.offset);
  cur.text = cur.text.slice(0, at.offset);
  const type: BlockType = cur.type === "li" ? "li" : "p";
  out.splice(at.block + 1, 0, { type, text: right, gap: false });
  return { blocks: out, caret: { block: at.block + 1, offset: 0 } };
}

function backspaceAtStart(blocks: Block[], at: Caret): { blocks: Block[]; caret: Caret } | null {
  const out = blocks.map((b) => ({ ...b }));
  const cur = out[at.block];
  if (cur.type !== "p") { cur.type = "p"; return { blocks: out, caret: at }; }
  if (at.block === 0) return null;
  const prev = out[at.block - 1];
  const offset = prev.text.length;
  prev.text += cur.text;
  out.splice(at.block, 1);
  return { blocks: out, caret: { block: at.block - 1, offset } };
}

function deleteAtEnd(blocks: Block[], at: Caret): { blocks: Block[]; caret: Caret } | null {
  if (at.block >= blocks.length - 1) return null;
  const out = blocks.map((b) => ({ ...b }));
  out[at.block].text += out[at.block + 1].text;
  out.splice(at.block + 1, 1);
  return { blocks: out, caret: at };
}

/* ---------- component */

export function BlockEditor({ value, onChange, readOnly, placeholder, ariaLabel, className }: Props) {
  if (readOnly) return <BlockView value={value} className={className} ariaLabel={ariaLabel} />;
  return <EditableBlocks value={value} onChange={onChange} placeholder={placeholder} ariaLabel={ariaLabel} className={className} />;
}

function EditableBlocks({ value, onChange, placeholder, ariaLabel, className }: Omit<Props, "readOnly">) {
  const root = useRef<HTMLDivElement>(null);
  const blocks = useRef<Block[]>([]);
  const emitted = useRef<string | null>(null);
  const composing = useRef(false);
  const change = useRef(onChange);
  change.current = onChange;

  const markEmpty = () => {
    const el = root.current;
    if (!el) return;
    const b = blocks.current;
    const isEmpty = b.length === 1 && b[0].type === "p" && !b[0].text;
    if (isEmpty) el.dataset.empty = "true";
    else delete el.dataset.empty;
  };

  const commit = () => {
    const md = serialise(blocks.current);
    markEmpty();
    if (md !== emitted.current) {
      emitted.current = md;
      change.current?.(md);
    }
  };

  const apply = (next: Block[], caret: Caret | null) => {
    const el = root.current;
    if (!el) return;
    blocks.current = next.length ? next : [empty()];
    render(el, blocks.current);
    if (caret) setCaret(el, caret);
    commit();
  };

  // Load from props when the value changes from outside (first mount, switching project).
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    if (value === emitted.current) return;
    const parsed = parse(value);
    blocks.current = parsed.length ? parsed : [empty()];
    emitted.current = value;
    render(el, blocks.current);
    markEmpty();
  }, [value]);

  useEffect(() => {
    const el = root.current;
    if (!el) return;

    const onBeforeInput = (e: InputEvent) => {
      if (composing.current || e.isComposing) return;
      const sel = getSel(el);
      if (!sel) return;
      const { start, end } = sel;
      const collapsed = start.block === end.block && start.offset === end.offset;
      const multi = start.block !== end.block;
      const t = e.inputType;
      const fresh = read(el).blocks;

      if (t === "insertParagraph" || t === "insertLineBreak") {
        e.preventDefault();
        const base = collapsed ? fresh : deleteRange(fresh, start, end);
        const r = splitBlock(base, start);
        apply(r.blocks, r.caret);
        return;
      }
      if (t === "insertFromPaste" || t === "insertFromDrop") {
        const text = e.dataTransfer?.getData("text/plain") ?? e.data ?? "";
        if (!text) return;
        e.preventDefault();
        const base = collapsed ? fresh : deleteRange(fresh, start, end);
        const r = insertText(base, start, text);
        apply(r.blocks, r.caret);
        return;
      }
      if (t.startsWith("delete")) {
        if (multi) {
          e.preventDefault();
          apply(deleteRange(fresh, start, end), start);
          return;
        }
        if (!collapsed) return;
        if (t === "deleteContentBackward" && start.offset === 0) {
          e.preventDefault();
          const r = backspaceAtStart(fresh, start);
          if (r) apply(r.blocks, r.caret);
          return;
        }
        if (t === "deleteContentForward" && start.offset === (fresh[start.block]?.text.length ?? 0)) {
          e.preventDefault();
          const r = deleteAtEnd(fresh, start);
          if (r) apply(r.blocks, r.caret);
        }
        return;
      }
      if (multi && t === "insertText" && e.data) {
        e.preventDefault();
        const r = insertText(deleteRange(fresh, start, end), start, e.data);
        apply(r.blocks, r.caret);
      }
    };

    const onInput = () => {
      if (composing.current) return;
      const { blocks: next, canonical } = read(el);
      const sel = getSel(el);
      const caret = sel ? sel.end : null;
      // Markdown shortcuts: "# ", "## " or "- " typed at the start of a block.
      if (caret) {
        const b = next[caret.block];
        const m = b ? marker(b.text) : null;
        if (b && m && m.type !== b.type && caret.offset >= b.text.length - m.rest.length) {
          const cut = b.text.length - m.rest.length;
          b.type = m.type;
          b.text = m.rest;
          if (m.type !== "li" && caret.block > 0) b.gap = true;
          apply(next, { block: caret.block, offset: Math.max(0, caret.offset - cut) });
          return;
        }
      }
      if (!canonical) { apply(next, caret); return; }
      blocks.current = next;
      commit();
    };

    const onPaste = (e: ClipboardEvent) => {
      const text = e.clipboardData?.getData("text/plain");
      e.preventDefault();
      if (!text) return;
      const sel = getSel(el);
      if (!sel) return;
      const fresh = read(el).blocks;
      const base = sel.start.block === sel.end.block && sel.start.offset === sel.end.offset
        ? fresh : deleteRange(fresh, sel.start, sel.end);
      const r = insertText(base, sel.start, text);
      apply(r.blocks, r.caret);
    };

    const onDrop = (e: DragEvent) => { e.preventDefault(); };
    const onCompStart = () => { composing.current = true; };
    const onCompEnd = () => { composing.current = false; onInput(); };

    el.addEventListener("beforeinput", onBeforeInput);
    el.addEventListener("input", onInput);
    el.addEventListener("paste", onPaste);
    el.addEventListener("drop", onDrop);
    el.addEventListener("compositionstart", onCompStart);
    el.addEventListener("compositionend", onCompEnd);
    return () => {
      el.removeEventListener("beforeinput", onBeforeInput);
      el.removeEventListener("input", onInput);
      el.removeEventListener("paste", onPaste);
      el.removeEventListener("drop", onDrop);
      el.removeEventListener("compositionstart", onCompStart);
      el.removeEventListener("compositionend", onCompEnd);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      ref={root}
      className={`ed${className ? ` ${className}` : ""}`}
      contentEditable
      suppressContentEditableWarning
      role="textbox"
      aria-multiline="true"
      aria-label={ariaLabel}
      data-placeholder={placeholder}
      spellCheck
    />
  );
}

/** Read-only, formatted rendering of the same markdown. */
export function BlockView({ value, className, ariaLabel }: { value: string; className?: string; ariaLabel?: string }) {
  const blocks = parse(value);
  const out: ReactNode[] = [];
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    const gap = b.gap ? "1" : undefined;
    if (b.type === "li") {
      const items: ReactNode[] = [];
      while (i < blocks.length && blocks[i].type === "li") {
        items.push(<li key={i} data-gap={blocks[i].gap ? "1" : undefined}>{blocks[i].text}</li>);
        i++;
      }
      i--;
      out.push(<ul key={`ul-${i}`}>{items}</ul>);
    } else if (b.type === "h1") out.push(<h1 key={i} data-gap={gap}>{b.text}</h1>);
    else if (b.type === "h2") out.push(<h2 key={i} data-gap={gap}>{b.text}</h2>);
    else out.push(<p key={i} data-gap={gap}>{b.text}</p>);
  }
  return (
    <div className={`ed ed--read${className ? ` ${className}` : ""}`} aria-label={ariaLabel} role="document">
      {out.length ? out : <p className="ed__none">Nothing written yet.</p>}
    </div>
  );
}
