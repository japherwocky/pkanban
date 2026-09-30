import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';

vi.mock('svelte-routing', () => ({ navigate: vi.fn() }));

const usage = vi.fn();
const checkout = vi.fn();
const portal = vi.fn();
vi.mock('../lib/api.js', () => ({
  api: {
    me: { usage: (...a) => usage(...a) },
    billing: { checkout: (...a) => checkout(...a), portal: (...a) => portal(...a) },
  },
}));

import SettingsPlan from './SettingsPlan.svelte';

const FREE = {
  plan: 'free',
  billing_enabled: true,
  max_boards: 5,
  max_cards_per_board: 100,
  boards_owned: 3,
  boards: [
    { id: 1, name: 'Dev', cards: 97 },
    { id: 2, name: 'Side project', cards: 12 },
  ],
};

// Braces matter: a function returned from beforeEach is run as a teardown hook,
// and this would hand vitest the mock itself to call after every test.
// jsdom cannot navigate, so location is replaced wholesale, as api.test.js does.
let location;
function stubLocation(search = '') {
  location = { pathname: '/settings/plan', search, assign: vi.fn() };
  Object.defineProperty(window, 'location', {
    value: location, writable: true, configurable: true,
  });
}

beforeEach(() => {
  usage.mockReset();
  checkout.mockReset();
  portal.mockReset();
  stubLocation();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('SettingsPlan', () => {
  it('shows the plan and boards owned against the limit', async () => {
    usage.mockResolvedValue(FREE);
    render(SettingsPlan);

    expect(await screen.findByText('3 / 5')).toBeInTheDocument();
    expect(screen.getByText('free')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Boards owned' })).toHaveAttribute('aria-valuenow', '3');
  });

  it('warns only about boards near the card limit', async () => {
    usage.mockResolvedValue(FREE);
    render(SettingsPlan);

    expect(await screen.findByText('97 / 100')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dev' })).toHaveAttribute('href', '/boards/1');
    expect(screen.queryByText('Side project')).toBeNull();
  });

  it('marks a board that is full', async () => {
    usage.mockResolvedValue({ ...FREE, boards: [{ id: 1, name: 'Dev', cards: 100 }] });
    render(SettingsPlan);

    expect(await screen.findByText(/100 \/ 100 \(full\)/)).toBeInTheDocument();
  });

  it('says so when no board is near the limit', async () => {
    usage.mockResolvedValue({ ...FREE, boards: [{ id: 2, name: 'Side project', cards: 12 }] });
    render(SettingsPlan);

    expect(await screen.findByText(/none of your boards are close/i)).toBeInTheDocument();
  });

  it('shows a pro plan as unlimited, with no meters', async () => {
    usage.mockResolvedValue({ ...FREE, plan: 'pro', max_boards: null, max_cards_per_board: null });
    render(SettingsPlan);

    expect(await screen.findByText(/unlimited boards and cards/i)).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('says the server is not enforcing limits when billing is off', async () => {
    usage.mockResolvedValue({ ...FREE, billing_enabled: false, max_boards: null, max_cards_per_board: null });
    render(SettingsPlan);

    expect(await screen.findByText(/does not enforce plan limits/i)).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('reports a failure to load instead of a blank page', async () => {
    usage.mockRejectedValue(new Error('Request failed'));
    render(SettingsPlan);

    expect(await screen.findByRole('alert')).toHaveTextContent('Request failed');
  });
});

describe('SettingsPlan - subscribing', () => {
  const STRIPE_FREE = { ...FREE, upgrade_available: true, manage_available: false };
  const STRIPE_PRO = {
    ...FREE, plan: 'pro', max_boards: null, max_cards_per_board: null,
    upgrade_available: false, manage_available: true,
    current_period_end: '2026-11-30T00:00:00+00:00', subscription_status: 'active',
  };

  it('offers an upgrade to a free user and sends them to Stripe Checkout', async () => {
    usage.mockResolvedValue(STRIPE_FREE);
    checkout.mockResolvedValue({ url: 'https://checkout.stripe.test/pay' });
    render(SettingsPlan);

    await fireEvent.click(await screen.findByRole('button', { name: 'Upgrade to Pro' }));

    await vi.waitFor(() =>
      expect(location.assign).toHaveBeenCalledWith('https://checkout.stripe.test/pay')
    );
    expect(screen.queryByRole('button', { name: 'Manage subscription' })).toBeNull();
  });

  it('offers no upgrade when the server has no payments set up', async () => {
    usage.mockResolvedValue(FREE);
    render(SettingsPlan);

    await screen.findByText('3 / 5');
    expect(screen.queryByRole('button', { name: 'Upgrade to Pro' })).toBeNull();
  });

  it('shows the error and lets the user retry when checkout cannot start', async () => {
    usage.mockResolvedValue(STRIPE_FREE);
    checkout.mockRejectedValue(new Error('Could not reach the payment provider. Try again shortly.'));
    render(SettingsPlan);

    await fireEvent.click(await screen.findByRole('button', { name: 'Upgrade to Pro' }));

    expect(await screen.findByText(/could not reach the payment provider/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' })).toBeEnabled();
    expect(location.assign).not.toHaveBeenCalled();
  });

  it('gives a pro user the portal and when the period ends, not an upgrade', async () => {
    usage.mockResolvedValue(STRIPE_PRO);
    portal.mockResolvedValue({ url: 'https://billing.stripe.test/portal' });
    render(SettingsPlan);

    // Rendered in the viewer's own timezone, so the expectation is built the
    // same way rather than hard-coding a date that is only right in some zones.
    const expected = new Date(STRIPE_PRO.current_period_end).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
    expect(await screen.findByText(`Current period ends ${expected}.`)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Upgrade to Pro' })).toBeNull();

    await fireEvent.click(screen.getByRole('button', { name: 'Manage subscription' }));
    await vi.waitFor(() =>
      expect(location.assign).toHaveBeenCalledWith('https://billing.stripe.test/portal')
    );
  });

  it('warns a user whose payment failed, and keeps them on the portal path', async () => {
    usage.mockResolvedValue({ ...STRIPE_PRO, subscription_status: 'past_due' });
    render(SettingsPlan);

    expect(await screen.findByText(/last payment failed/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Manage subscription' })).toBeInTheDocument();
  });

  it('says so after a cancelled checkout, and that nothing was charged', async () => {
    stubLocation('?checkout=cancelled');
    usage.mockResolvedValue(STRIPE_FREE);
    render(SettingsPlan);

    expect(await screen.findByText(/not been charged/i)).toBeInTheDocument();
  });
});

describe('SettingsPlan - returning from Stripe', () => {
  const PAID = { ...FREE, plan: 'pro', max_boards: null, max_cards_per_board: null };

  beforeEach(() => {
    stubLocation('?checkout=success');
    // Only setTimeout: the poll waits on it, and testing-library's own polling
    // must keep working.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  });

  it('does not take the redirect as proof: it waits, then shows Pro once the webhook has landed', async () => {
    usage
      .mockResolvedValueOnce(FREE)   // first look: the webhook has not arrived
      .mockResolvedValue(PAID);      // by the next poll it has
    render(SettingsPlan);

    expect(await screen.findByText(/waiting for stripe to confirm/i)).toBeInTheDocument();
    expect(screen.getByText('free')).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(2000);

    expect(await screen.findByText(/you are on pro/i)).toBeInTheDocument();
    expect(screen.queryByText(/waiting for stripe/i)).toBeNull();
  });

  it('offers no second Upgrade while the payment is still being confirmed', async () => {
    // Someone who has just paid and sees "Upgrade to Pro" may well pay again,
    // and the server cannot refuse: the plan it checks is the one not updated.
    usage.mockResolvedValue({ ...FREE, upgrade_available: true, manage_available: false });
    render(SettingsPlan);

    await screen.findByText(/waiting for stripe to confirm/i);
    expect(screen.queryByRole('button', { name: 'Upgrade to Pro' })).toBeNull();

    await vi.advanceTimersByTimeAsync(2000 * 12);
    await screen.findByText(/has not updated yet/i);
    expect(screen.queryByRole('button', { name: 'Upgrade to Pro' })).toBeNull();
  });

  it('does not wait at all when the plan is already pro', async () => {
    usage.mockResolvedValue(PAID);
    render(SettingsPlan);

    expect(await screen.findByText(/you are on pro/i)).toBeInTheDocument();
    expect(usage).toHaveBeenCalledTimes(1);
  });

  it('stops waiting after a while and says what to do', async () => {
    usage.mockResolvedValue(FREE);
    render(SettingsPlan);

    await screen.findByText(/waiting for stripe to confirm/i);
    await vi.advanceTimersByTimeAsync(2000 * 12);

    expect(await screen.findByText(/has not updated yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/waiting for stripe/i)).toBeNull();
  });
});
