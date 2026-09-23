// Lightweight structural parser for AI-generated ad text (chat_generate_ad's
// AD_CHAT_SYSTEM prompt produces **Section :** headers, "- " bullet lists,
// and plain paragraphs with occasional inline **bold**/*italic*). Renders
// section headers distinctly from body text instead of leaking raw "**".

export type InlineToken = { text: string; bold?: boolean; italic?: boolean };

const INLINE_RE = /\*\*(.+?)\*\*|\*(.+?)\*/g;

export function parseInline(line: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  INLINE_RE.lastIndex = 0;
  while ((m = INLINE_RE.exec(line))) {
    if (m.index > last) tokens.push({ text: line.slice(last, m.index) });
    if (m[1] !== undefined) tokens.push({ text: m[1], bold: true });
    else tokens.push({ text: m[2] ?? "", italic: true });
    last = INLINE_RE.lastIndex;
  }
  if (last < line.length) tokens.push({ text: line.slice(last) });
  return tokens;
}

export function renderInline(line: string): React.ReactNode {
  return parseInline(line).map((tok, i) => {
    if (tok.bold) return <strong key={i}>{tok.text}</strong>;
    if (tok.italic) return <em key={i}>{tok.text}</em>;
    return <span key={i}>{tok.text}</span>;
  });
}

export type AdContentBlock =
  | { type: "header"; text: string }
  | { type: "bullets"; items: string[] }
  | { type: "paragraph"; text: string };

const HEADER_RE = /^\*\*(.+?)\*\*:?\s*$/;
const BULLET_RE = /^[-*]\s+(.+)/;

export function parseAdContent(raw: string): AdContentBlock[] {
  const blocks: AdContentBlock[] = [];
  let bulletBuf: string[] = [];

  function flushBullets() {
    if (bulletBuf.length) {
      blocks.push({ type: "bullets", items: bulletBuf });
      bulletBuf = [];
    }
  }

  for (const rawLine of raw.split("\n")) {
    const line = rawLine.trim();
    if (!line) { flushBullets(); continue; }

    const headerMatch = line.match(HEADER_RE);
    if (headerMatch) {
      flushBullets();
      blocks.push({ type: "header", text: headerMatch[1].replace(/:$/, "").trim() });
      continue;
    }

    const bulletMatch = line.match(BULLET_RE);
    if (bulletMatch) {
      bulletBuf.push(bulletMatch[1]);
      continue;
    }

    flushBullets();
    blocks.push({ type: "paragraph", text: line });
  }
  flushBullets();
  return blocks;
}
