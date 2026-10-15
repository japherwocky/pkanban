import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';

const get = vi.fn();
const approve = vi.fn();
const deny = vi.fn();
vi.mock('../lib/api.js', () => ({
  api: {
    oauthRequest: {
      get: (...a) => get(...a),
      approve: (...a) => approve(...a),
      deny: (...a) => deny(...a),
    },
  },
}));

import Consent from './Consent.svelte';

const PENDING = {
  client_name: 'Claude',
  redirect_host: 'claude.ai',
  status: 'pending',
  created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 600000).toISOString(),
};

function at(search, { signedIn = true } = {}) {
  history.replaceState(null, '', `/oauth/consent${search}`);
  if (signedIn) localStorage.setItem('token', 'session-token');
}

beforeEach(() => {
  get.mockReset();
  approve.mockReset();
  deny.mockReset();
});

describe('the OAuth consent page', () => {
  it('names the app as a claim and leads with where the browser goes', async () => {
    at('?request=r1');
    get.mockResolvedValue(PENDING);
    render(Consent, { leave: vi.fn() });

    expect(await screen.findByText('Claude')).toBeInTheDocument();
    expect(screen.getByText('An app calling itself')).toBeInTheDocument();
    expect(screen.getAllByText('claude.ai').length).toBeGreaterThan(0);
    expect(get).toHaveBeenCalledWith('r1');
  });

  it('approving sends the browser exactly where the server said', async () => {
    at('?request=r1');
    get.mockResolvedValue(PENDING);
    const redirect = 'https://claude.ai/api/mcp/auth_callback?code=abc&state=xyz';
    approve.mockResolvedValue({ ...PENDING, status: 'approved', redirect_to: redirect });
    const leave = vi.fn();
    render(Consent, { leave });

    await fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    expect(approve).toHaveBeenCalledWith('r1');
    expect(leave).toHaveBeenCalledWith(redirect);
    expect(await screen.findByText('Sending you back to claude.ai...')).toBeInTheDocument();
  });

  it('denying sends the browser back too, so the app hears about it', async () => {
    at('?request=r1');
    get.mockResolvedValue(PENDING);
    const redirect = 'https://claude.ai/api/mcp/auth_callback?error=access_denied&state=xyz';
    deny.mockResolvedValue({ ...PENDING, status: 'denied', redirect_to: redirect });
    const leave = vi.fn();
    render(Consent, { leave });

    await fireEvent.click(await screen.findByRole('button', { name: 'Deny' }));
    expect(leave).toHaveBeenCalledWith(redirect);
    expect(await screen.findByText('Not connected')).toBeInTheDocument();
  });

  it('stays put and says why when approving fails', async () => {
    at('?request=r1');
    get.mockResolvedValue(PENDING);
    approve.mockRejectedValue(new Error('This sign-in request was already decided.'));
    const leave = vi.fn();
    render(Consent, { leave });

    await fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('already decided');
    expect(leave).not.toHaveBeenCalled();
  });

  it('asks a signed-out visitor to sign in and remembers the request', async () => {
    at('?request=r1', { signedIn: false });
    render(Consent, { leave: vi.fn() });

    expect(screen.getByText('Sign in to continue')).toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(localStorage.getItem('redirectPath')).toBe('/oauth/consent?request=r1');
  });

  it('says so when the link has no request', () => {
    at('');
    render(Consent, { leave: vi.fn() });
    expect(screen.getByText('Nothing to approve')).toBeInTheDocument();
  });

  it('shows the server error for an unknown request', async () => {
    at('?request=gone');
    get.mockRejectedValue(new Error('No sign-in request with that id.'));
    render(Consent, { leave: vi.fn() });
    expect(await screen.findByRole('alert')).toHaveTextContent('No sign-in request');
  });

  it.each([
    ['expired', 'This request has expired'],
    ['denied', 'Not connected'],
    ['used', 'Already approved'],
  ])('a %s request offers no buttons', async (status, heading) => {
    at('?request=r1');
    get.mockResolvedValue({ ...PENDING, status });
    render(Consent, { leave: vi.fn() });
    expect(await screen.findByText(heading)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
  });
});
