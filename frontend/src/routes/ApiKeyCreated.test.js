import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen } from '@testing-library/svelte';
import ApiKeyCreated from './ApiKeyCreated.svelte';

const KEY = 'pkanban_Ab3xYz12secretsecretsecretsecret';

describe('a new API key never touches the URL', () => {
  // It used to travel as /settings/api-keys/created?key=...; the page then
  // cleared the query string, but navigate() had already pushed that URL,
  // which put the raw key in browser history and whatever syncs it.

  beforeEach(() => {
    history.replaceState(null, '', '/');
  });

  it('SettingsApiKeys passes the key in history state, not a query string', () => {
    const source = readFileSync(join(__dirname, 'SettingsApiKeys.svelte'), 'utf8');
    expect(source).not.toMatch(/created\?key=/);
    expect(source).toMatch(/state:\s*\{\s*apiKey:/);
  });

  it('shows the key from history state', () => {
    history.pushState({ apiKey: KEY, keyName: 'CI', key: '1' }, '', '/settings/api-keys/created');
    render(ApiKeyCreated);
    expect(screen.getAllByText(KEY, { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getByText('CI')).toBeInTheDocument();
    expect(window.location.search).toBe('');
  });

  it('clears the key from history state once shown', () => {
    history.pushState({ apiKey: KEY, keyName: 'CI', key: '1' }, '', '/settings/api-keys/created');
    render(ApiKeyCreated);
    expect(history.state).toEqual({ key: '1' });
    expect(JSON.stringify(history.state)).not.toContain(KEY);
  });

  it('ignores a key in the query string', () => {
    history.pushState(null, '', `/settings/api-keys/created?key=${KEY}`);
    render(ApiKeyCreated);
    expect(screen.getByText(/No key found/)).toBeInTheDocument();
  });
});
