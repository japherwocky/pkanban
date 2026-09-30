import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// apiFetch keeps module-level state (the redirect latch), so each test imports
// a fresh copy rather than leaking a tripped latch into the next one.
async function freshApi() {
  vi.resetModules();
  return await import('./api.js');
}

function stubLocation(pathname) {
  const loc = { pathname, href: pathname };
  Object.defineProperty(window, 'location', {
    value: loc, writable: true, configurable: true,
  });
  return loc;
}

function jsonResponse(body, { ok = true, status = 200, headers = {} } = {}) {
  return {
    ok,
    status,
    // apiFetch reads the renewal header on every response, so the stub needs a
    // Headers-shaped object even when a test does not care about headers.
    headers: { get: (name) => headers[name] ?? null },
    json: () => Promise.resolve(body),
  };
}

beforeEach(() => {
  localStorage.clear();
  stubLocation('/board/1');
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('apiFetch - request shape', () => {
  it('sends the bearer token when one is stored', async () => {
    localStorage.setItem('token', 'tok123');
    fetch.mockResolvedValue(jsonResponse({ ok: true }));
    const { apiFetch } = await freshApi();

    await apiFetch('/api/boards');

    const [url, opts] = fetch.mock.calls[0];
    expect(url).toBe('/api/boards');
    expect(opts.headers.Authorization).toBe('Bearer tok123');
    expect(opts.headers['Content-Type']).toBe('application/json');
  });

  it('omits Authorization entirely when there is no token', async () => {
    fetch.mockResolvedValue(jsonResponse({}));
    const { apiFetch } = await freshApi();

    await apiFetch('/api/beta-signup', { method: 'POST' });

    expect(fetch.mock.calls[0][1].headers).not.toHaveProperty('Authorization');
  });

  it('lets callers override headers', async () => {
    fetch.mockResolvedValue(jsonResponse({}));
    const { apiFetch } = await freshApi();

    await apiFetch('/api/x', { headers: { 'Content-Type': 'text/plain' } });

    expect(fetch.mock.calls[0][1].headers['Content-Type']).toBe('text/plain');
  });

  it('returns the parsed body on success', async () => {
    fetch.mockResolvedValue(jsonResponse({ id: 7, name: 'Dev' }));
    const { apiFetch } = await freshApi();

    await expect(apiFetch('/api/boards/7')).resolves.toEqual({ id: 7, name: 'Dev' });
  });
});

describe('apiFetch - errors', () => {
  it('throws with the server-supplied detail', async () => {
    fetch.mockResolvedValue(jsonResponse({ detail: 'Board not found' }, { ok: false, status: 404 }));
    const { apiFetch } = await freshApi();

    await expect(apiFetch('/api/boards/99')).rejects.toThrow('Board not found');
  });

  it('falls back to a generic message when the error body is not JSON', async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 500,
      headers: { get: () => null },
      json: () => Promise.reject(new Error('not json')),
    });
    const { apiFetch } = await freshApi();

    await expect(apiFetch('/api/boards')).rejects.toThrow('Request failed');
  });
});

describe('apiFetch - plan limits', () => {
  const body = {
    error: 'plan_limit', limit: 'boards', max: 5, current: 5,
    detail: 'The free plan allows 5 boards and you own 5.',
  };

  it('throws a PlanLimitError carrying the structured fields', async () => {
    fetch.mockResolvedValue(jsonResponse(body, { ok: false, status: 402 }));
    const { apiFetch, PlanLimitError } = await freshApi();

    const error = await apiFetch('/api/boards', { method: 'POST' }).catch((e) => e);

    expect(error).toBeInstanceOf(PlanLimitError);
    expect(error.code).toBe('plan_limit');
    expect([error.limit, error.max, error.current]).toEqual(['boards', 5, 5]);
  });

  it('keeps the server sentence as the message, for callers that just alert it', async () => {
    fetch.mockResolvedValue(jsonResponse(body, { ok: false, status: 402 }));
    const { apiFetch } = await freshApi();

    await expect(apiFetch('/api/boards', { method: 'POST' })).rejects.toThrow(
      'The free plan allows 5 boards and you own 5.'
    );
  });

  it('leaves a 402 that is not a plan limit as a plain error', async () => {
    fetch.mockResolvedValue(jsonResponse({ detail: 'Payment Required' }, { ok: false, status: 402 }));
    const { apiFetch, PlanLimitError } = await freshApi();

    const error = await apiFetch('/api/boards').catch((e) => e);

    expect(error).not.toBeInstanceOf(PlanLimitError);
    expect(error.message).toBe('Payment Required');
  });
});

describe('apiFetch - expired session handling', () => {
  it('clears credentials and redirects on a 401 for an authenticated request', async () => {
    localStorage.setItem('token', 'expired');
    localStorage.setItem('user', '{"id":1}');
    const loc = stubLocation('/board/1');
    fetch.mockResolvedValue(jsonResponse({ detail: 'Invalid token' }, { ok: false, status: 401 }));
    const { apiFetch } = await freshApi();

    await expect(apiFetch('/api/boards')).rejects.toThrow('Invalid token');

    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
    // so the user comes back to where they were after logging in again
    expect(localStorage.getItem('redirectPath')).toBe('/board/1');
    expect(loc.href).toBe('/login');
  });

  it('does not redirect on a 401 for an unauthenticated request', async () => {
    // a failed login is a 401 too, and must surface as a normal error
    const loc = stubLocation('/login');
    fetch.mockResolvedValue(jsonResponse({ detail: 'Bad credentials' }, { ok: false, status: 401 }));
    const { apiFetch } = await freshApi();

    await expect(apiFetch('/api/token', { method: 'POST' })).rejects.toThrow('Bad credentials');

    expect(loc.href).toBe('/login');
    expect(localStorage.getItem('redirectPath')).toBeNull();
  });

  it('does not stash a redirectPath when already on /login', async () => {
    localStorage.setItem('token', 'expired');
    stubLocation('/login');
    fetch.mockResolvedValue(jsonResponse({ detail: 'nope' }, { ok: false, status: 401 }));
    const { apiFetch } = await freshApi();

    await expect(apiFetch('/api/boards')).rejects.toThrow();

    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('redirectPath')).toBeNull();
  });

  it('redirects once when several in-flight requests 401 together', async () => {
    localStorage.setItem('token', 'expired');
    const loc = stubLocation('/board/1');
    fetch.mockResolvedValue(jsonResponse({ detail: 'Invalid token' }, { ok: false, status: 401 }));
    const { apiFetch } = await freshApi();

    const results = await Promise.allSettled([
      apiFetch('/api/boards'), apiFetch('/api/columns'), apiFetch('/api/cards'),
    ]);
    expect(results.every(r => r.status === 'rejected')).toBe(true);

    // the latch means the first one wins and the rest do not re-navigate
    expect(loc.href).toBe('/login');
    let assignments = 0;
    Object.defineProperty(loc, 'href', { set() { assignments++; }, get: () => '/login' });
    await Promise.allSettled([apiFetch('/api/boards')]);
    expect(assignments).toBe(0);
  });

  it('leaves a non-401 failure alone', async () => {
    localStorage.setItem('token', 'good');
    const loc = stubLocation('/board/1');
    fetch.mockResolvedValue(jsonResponse({ detail: 'Server error' }, { ok: false, status: 500 }));
    const { apiFetch } = await freshApi();

    await expect(apiFetch('/api/boards')).rejects.toThrow('Server error');

    expect(localStorage.getItem('token')).toBe('good');
    expect(loc.href).toBe('/board/1');
  });
});

describe('api surface', () => {
  it('routes a board fetch to the right endpoint', async () => {
    fetch.mockResolvedValue(jsonResponse({}));
    const { api } = await freshApi();

    await api.boards.get(42);

    expect(fetch.mock.calls[0][0]).toBe('/api/boards/42');
  });

  it('sends card reorder as a body of id/position pairs', async () => {
    fetch.mockResolvedValue(jsonResponse({}));
    const { api } = await freshApi();

    await api.cards.reorder([{ id: 1, position: 0 }, { id: 2, position: 1 }]);

    const [url, opts] = fetch.mock.calls[0];
    expect(url).toBe('/api/cards/reorder');
    expect(JSON.parse(opts.body)).toEqual({ cards: [{ id: 1, position: 0 }, { id: 2, position: 1 }] });
  });
});


describe('apiFetch - session renewal', () => {
  // Sessions used to die exactly 24h after login: the token's expiry is
  // absolute and nothing re-issued it. The server now returns a replacement on
  // X-Renewed-Token once the current one is close to expiring, and apiFetch is
  // the single place every request passes through to pick it up.

  it('stores a renewed token', async () => {
    localStorage.setItem('token', 'old-token');
    fetch.mockResolvedValue(
      jsonResponse({}, { headers: { 'X-Renewed-Token': 'new-token' } }),
    );
    const { apiFetch } = await freshApi();

    await apiFetch('/api/boards');

    expect(localStorage.getItem('token')).toBe('new-token');
  });

  it('sends the renewed token on the next request', async () => {
    localStorage.setItem('token', 'old-token');
    fetch.mockResolvedValueOnce(
      jsonResponse({}, { headers: { 'X-Renewed-Token': 'new-token' } }),
    );
    fetch.mockResolvedValueOnce(jsonResponse({}));
    const { apiFetch } = await freshApi();

    await apiFetch('/api/boards');
    await apiFetch('/api/boards');

    expect(fetch.mock.calls[1][1].headers.Authorization).toBe('Bearer new-token');
  });

  it('leaves the token alone when no renewal is offered', async () => {
    localStorage.setItem('token', 'old-token');
    fetch.mockResolvedValue(jsonResponse({}));
    const { apiFetch } = await freshApi();

    await apiFetch('/api/boards');

    expect(localStorage.getItem('token')).toBe('old-token');
  });

  it('picks up a renewal on a response that failed on its own merits', async () => {
    localStorage.setItem('token', 'old-token');
    fetch.mockResolvedValue(
      jsonResponse(
        { detail: 'Board not found' },
        { ok: false, status: 404, headers: { 'X-Renewed-Token': 'new-token' } },
      ),
    );
    const { apiFetch } = await freshApi();

    await expect(apiFetch('/api/boards/99')).rejects.toThrow('Board not found');
    expect(localStorage.getItem('token')).toBe('new-token');
  });

  it('does not store a renewal for a request it sent no token with', async () => {
    fetch.mockResolvedValue(
      jsonResponse({}, { headers: { 'X-Renewed-Token': 'new-token' } }),
    );
    const { apiFetch } = await freshApi();

    await apiFetch('/api/beta-signup', { method: 'POST' });

    expect(localStorage.getItem('token')).toBeNull();
  });
});
