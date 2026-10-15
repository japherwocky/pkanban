import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { titleFor, docTitle, resetTitles } from './pageTitle.js';

// The same cases are in backend/tests/test_pages.py: the browser and the
// server title a docs page by one rule.
const DOC_TITLE_CASES = [
  ['# Quick Start\n\nGet going.', 'Quick Start — pkanban docs'],
  ['# pkanban Documentation\n', 'pkanban Documentation'],
  ['intro\n# `pkanban card` *commands*\n', 'pkanban card commands'],
  ['# See [the reference](/docs/reference)\n', 'See the reference — pkanban docs'],
  ['no heading here\n## only a subheading\n', null],
];

describe('docTitle', () => {
  it.each(DOC_TITLE_CASES)('%j', (markdown, expected) => {
    expect(docTitle(markdown)).toBe(expected);
  });
});

describe('titleFor', () => {
  beforeEach(() => {
    resetTitles();
    document.title = 'pkanban — default';
  });

  afterEach(() => {
    document.getElementById('page-titles')?.remove();
  });

  function embed(titles) {
    const script = document.createElement('script');
    script.type = 'application/json';
    script.id = 'page-titles';
    script.textContent = JSON.stringify(titles);
    document.head.appendChild(script);
  }

  it('uses the title the server embedded for a public page', () => {
    embed({ default: 'Generic', pages: { '/pricing': 'Pricing — pkanban' } });
    expect(titleFor('/pricing')).toBe('Pricing — pkanban');
    expect(titleFor('/pricing/')).toBe('Pricing — pkanban');
  });

  it('falls back to the default for any other page', () => {
    embed({ default: 'Generic', pages: { '/pricing': 'Pricing — pkanban' } });
    expect(titleFor('/boards/3')).toBe('Generic');
  });

  it('keeps the loaded title when nothing was embedded (the dev server)', () => {
    expect(titleFor('/pricing')).toBe('pkanban — default');
  });
});
