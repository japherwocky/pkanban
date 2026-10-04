// The server marks matched words in a search snippet with STX ... ETX
// (HIGHLIGHT_START/END in backend/search.py). Control characters rather than
// HTML: the snippet is card text, so it is rendered as text and never as
// markup, and the markers become <mark> elements built here instead.
export const HIGHLIGHT_START = '\x02';
export const HIGHLIGHT_END = '\x03';

/**
 * Split a snippet into runs of plain and matched text.
 *
 * Returns [{ text, match }], in order, with empty runs dropped. A marker the
 * server never closed highlights to the end of the snippet; a stray END is
 * dropped. Neither can come from FTS5, but a card's own text could contain
 * either character, and the worst it should do is mis-highlight.
 */
export function highlightSegments(snippet) {
  if (!snippet) return [];
  const segments = [];
  const parts = snippet.split(HIGHLIGHT_START);
  const push = (text, match) => {
    text = text.replaceAll(HIGHLIGHT_END, '');
    if (text) segments.push({ text, match });
  };

  push(parts[0], false);
  for (const part of parts.slice(1)) {
    const end = part.indexOf(HIGHLIGHT_END);
    if (end === -1) {
      push(part, true);
    } else {
      push(part.slice(0, end), true);
      push(part.slice(end + 1), false);
    }
  }
  return segments;
}
