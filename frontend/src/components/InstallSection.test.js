import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import InstallSection from './InstallSection.svelte';

let writeText;

beforeEach(() => {
  writeText = vi.fn();
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
});

describe('the install section', () => {
  it('starts on a command-line tab, with the login step after it', () => {
    render(InstallSection);
    expect(screen.getByRole('tab', { selected: true })).not.toHaveTextContent('Claude');
    expect(screen.getByText(/install\.(sh|ps1)/)).toBeInTheDocument();
    expect(screen.getByText('pkanban login')).toBeInTheDocument();
  });

  it('has a Claude tab with this server’s /mcp address to copy', async () => {
    render(InstallSection);
    await fireEvent.click(screen.getByRole('tab', { name: 'Claude' }));

    const address = `${window.location.origin}/mcp`;
    expect(screen.getByText(address)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Copy the connector address' }));
    expect(writeText).toHaveBeenCalledWith(address);
  });

  it('links the Claude tab to the walkthrough and the MCP docs', async () => {
    render(InstallSection);
    await fireEvent.click(screen.getByRole('tab', { name: 'Claude' }));

    expect(screen.getByRole('link', { name: 'Step by step' })).toHaveAttribute('href', '/connect/claude');
    expect(screen.getByRole('link', { name: 'ChatGPT and other apps' })).toHaveAttribute('href', '/docs/mcp');
    expect(screen.queryByText('pkanban login')).toBeNull();
  });
});
