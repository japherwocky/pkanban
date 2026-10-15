import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen, fireEvent } from '@testing-library/svelte';
import ConnectClaude from './ConnectClaude.svelte';

const SOURCE = readFileSync(join(__dirname, 'ConnectClaude.svelte'), 'utf8');

// The value of a Python string constant in backend/pages.py, adjacent string
// literals joined: what the server puts in this page's <head>.
function pagesEntry(field) {
  const pages = readFileSync(join(process.cwd(), '..', 'backend', 'pages.py'), 'utf8');
  const block = pages.slice(pages.indexOf('"/connect/claude"'));
  const match = block.match(new RegExp(`"${field}":\\s*\\(?((?:\\s*"[^"]*")+)`));
  if (!match) throw new Error(`${field} not found for /connect/claude in backend/pages.py`);
  return [...match[1].matchAll(/"([^"]*)"/g)].map((m) => m[1]).join('');
}

function pageConstant(name) {
  const match = SOURCE.match(new RegExp(`const ${name} =\\s*'([^']*)'`));
  if (!match) throw new Error(`${name} not found in ConnectClaude.svelte`);
  return match[1];
}

beforeEach(() => {
  history.replaceState(null, '', '/connect/claude');
});

describe('the Connect to Claude page', () => {
  it('shows this server’s own /mcp URL and copies it', async () => {
    const writeText = vi.fn();
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    render(ConnectClaude);

    const url = `${window.location.origin}/mcp`;
    expect(screen.getByText(url)).toBeInTheDocument();
    await fireEvent.click(screen.getAllByRole('button', { name: 'Copy' })[0]);
    expect(writeText).toHaveBeenCalledWith(url);
    expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
  });

  it('sets the same title and description the server sends', () => {
    render(ConnectClaude);
    expect(document.title).toBe(pagesEntry('title'));
    expect(pageConstant('TITLE')).toBe(pagesEntry('title'));
    expect(pageConstant('DESCRIPTION')).toBe(pagesEntry('description'));
  });

  it('offers sign-up only to someone signed out', () => {
    const { unmount } = render(ConnectClaude);
    expect(screen.getByRole('button', { name: 'Create your account' })).toBeInTheDocument();
    unmount();

    localStorage.setItem('token', 'session-token');
    render(ConnectClaude);
    expect(screen.queryByRole('button', { name: 'Create your account' })).toBeNull();
  });
});
