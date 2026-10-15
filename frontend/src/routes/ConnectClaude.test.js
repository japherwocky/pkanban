import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import ConnectClaude from './ConnectClaude.svelte';

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

  it('offers sign-up only to someone signed out', () => {
    const { unmount } = render(ConnectClaude);
    expect(screen.getByRole('button', { name: 'Create your account' })).toBeInTheDocument();
    unmount();

    localStorage.setItem('token', 'session-token');
    render(ConnectClaude);
    expect(screen.queryByRole('button', { name: 'Create your account' })).toBeNull();
  });
});
