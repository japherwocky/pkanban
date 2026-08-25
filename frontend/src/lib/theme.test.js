import { describe, it, expect, vi } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { get } from 'svelte/store';

// Not import.meta.url: under jsdom that is an http:// URL, which fs cannot
// read. cwd is the vite project root (frontend/) when run via `npm test`, but
// fall back to the repo-root path so it also works from one level up.
const INDEX_HTML = [
  resolve(process.cwd(), 'index.html'),
  resolve(process.cwd(), 'frontend/index.html'),
].find(existsSync);

// The inline <script> in index.html decides the theme before first paint, so a
// reload does not flash white. index.html says it "must stay in sync with
// getInitialTheme() in src/lib/theme.js" -- two implementations of one rule,
// which is exactly the kind of pair that drifts silently. Rather than trust the
// comment, run both over the same inputs and require the same answer.
function inlineThemeGuard() {
  const html = readFileSync(INDEX_HTML, 'utf-8');
  const match = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!match) throw new Error('no inline <script> found in index.html');
  return new Function(match[1]);
}

async function freshTheme() {
  vi.resetModules();
  return await import('./theme.js');
}

const STORED_VALUES = [null, 'light', 'dark', 'system', 'not-a-theme', ''];

describe('theme.js agrees with the pre-paint guard in index.html', () => {
  it.each(STORED_VALUES)('resolves the same way for stored value %j', async (stored) => {
    const runGuard = inlineThemeGuard();

    const apply = (fn) => {
      document.documentElement.className = '';
      localStorage.clear();
      if (stored !== null) localStorage.setItem('pkanban-theme', stored);
      fn();
      return document.documentElement.classList.contains('dark');
    };

    const fromInlineGuard = apply(runGuard);

    const { theme } = await freshTheme();
    const fromModule = apply(() => theme.init());

    expect(fromModule).toBe(fromInlineGuard);
  });

  it('defaults to dark, which is what makes the guard worth having', async () => {
    const runGuard = inlineThemeGuard();
    document.documentElement.className = '';
    localStorage.clear();
    runGuard();
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('still applies dark when localStorage throws', () => {
    const runGuard = inlineThemeGuard();
    document.documentElement.className = '';
    const original = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() { throw new Error('storage disabled'); },
    });
    try {
      runGuard();
      expect(document.documentElement.classList.contains('dark')).toBe(true);
    } finally {
      Object.defineProperty(window, 'localStorage', {
        value: original, writable: true, configurable: true,
      });
    }
  });
});

describe('theme store', () => {
  it('starts from the stored theme', async () => {
    localStorage.setItem('pkanban-theme', 'light');
    const { theme } = await freshTheme();
    expect(get(theme)).toBe('light');
  });

  it('persists and applies setTheme', async () => {
    const { theme } = await freshTheme();
    theme.setTheme('light');

    expect(get(theme)).toBe('light');
    expect(localStorage.getItem('pkanban-theme')).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('ignores a theme it does not recognise', async () => {
    const { theme } = await freshTheme();
    theme.setTheme('dark');
    theme.setTheme('chartreuse');

    expect(get(theme)).toBe('dark');
    expect(localStorage.getItem('pkanban-theme')).toBe('dark');
  });

  it('cycles between light and dark', async () => {
    localStorage.setItem('pkanban-theme', 'dark');
    const { theme } = await freshTheme();

    theme.cycleTheme();
    expect(get(theme)).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);

    theme.cycleTheme();
    expect(get(theme)).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('labels every theme it can hold', async () => {
    const { getThemeLabel } = await freshTheme();
    expect(getThemeLabel('light')).toBe('Light');
    expect(getThemeLabel('dark')).toBe('Dark');
    expect(getThemeLabel(undefined)).toBe('Dark');
  });
});
