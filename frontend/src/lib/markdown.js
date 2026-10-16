// Card descriptions and comments are Markdown (Dev #980): the CLI, the MCP
// tools and every agent writing to a board treat them that way.
//
// Card text is written by anyone who can see the board, agents included, so
// what this renders goes into the page as HTML only after DOMPurify has been
// over it. marked does no sanitising of its own: a `javascript:` link or an
// `onerror` attribute would otherwise run as script for everyone who opens
// the card.

import { Marked } from 'marked';
import DOMPurify from 'dompurify';

const escapeHtml = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// Its own instance: Docs.svelte configures the global `marked` (Prism, and
// heading ids that could collide with the page's own).
const cardMarked = new Marked({
  gfm: true,
  // A single newline is a line break, as it is in the textarea it was typed in.
  breaks: true,
  renderer: {
    // HTML typed into a card is shown as typed. Cards mention tags in prose
    // ("a real <title>"), and rendering them would make that text vanish.
    html({ text, block }) {
      return block ? `<p>${escapeHtml(text.trim())}</p>\n` : escapeHtml(text);
    },
    // An image becomes a link to it. Loading it would tell a stranger's
    // server the IP of everyone who opens the card.
    image({ href, text }) {
      return `<a href="${escapeHtml(href)}">${escapeHtml(text || href)}</a>`;
    },
  },
});

const purify = DOMPurify(window);

// Links leave the app, in a new tab, without handing over the page.
purify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A' && node.hasAttribute('href')) {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer nofollow');
  }
});

// Exactly what marked emits for card text, and nothing else. An allowlist,
// not DOMPurify's defaults, which let through forms and <style>.
const SANITIZE = {
  ALLOWED_TAGS: [
    'p', 'br', 'strong', 'em', 'del', 'code', 'pre', 'blockquote', 'hr',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'input', 'a',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
  ],
  ALLOWED_ATTR: ['href', 'title', 'class', 'start', 'align', 'type', 'checked', 'disabled'],
};

/** Card Markdown as sanitised HTML, ready for {@html}. */
export function renderMarkdown(text) {
  if (!text) return '';
  return purify.sanitize(cardMarked.parse(text, { async: false }), SANITIZE);
}

/**
 * Card Markdown as one line of plain text, for the preview on a board tile.
 * Rendered Markdown in a three-line clamp looks broken, and raw Markdown
 * reads as noise; this keeps the words and drops the syntax. Returns text,
 * not HTML, so it goes into the page escaped as usual.
 */
export function markdownToText(text) {
  if (!text) return '';
  return blocks(cardMarked.lexer(text)).replace(/\s+/g, ' ').trim();
}

function blocks(tokens) {
  return tokens.map(block).join(' ');
}

function block(token) {
  switch (token.type) {
    case 'space':
    case 'hr':
    case 'def':
    case 'checkbox':
      return '';
    case 'code':
    case 'html':
      return token.text;
    case 'blockquote':
      return blocks(token.tokens);
    case 'list':
      return token.items.map((item) => blocks(item.tokens)).join(' ');
    case 'table':
      return [...token.header, ...token.rows.flat()].map((cell) => inline(cell.tokens)).join(' ');
    default:
      return token.tokens ? inline(token.tokens) : (token.text ?? '');
  }
}

function inline(tokens) {
  return tokens
    .map((token) => {
      switch (token.type) {
        case 'br':
          return ' ';
        case 'checkbox':
          return '';
        case 'codespan':
        case 'image':
        case 'html':
        case 'escape':
          return token.text;
        default:
          return token.tokens ? inline(token.tokens) : (token.text ?? '');
      }
    })
    .join('');
}
