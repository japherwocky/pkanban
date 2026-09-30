import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen, fireEvent, within } from '@testing-library/svelte';

const navigate = vi.fn();
// `link` is a Svelte action: it is called with the element and returns nothing
// that matters here. Terms.svelte uses it.
vi.mock('svelte-routing', () => ({ navigate: (...a) => navigate(...a), link: () => ({}) }));

import Pricing from './Pricing.svelte';
import Terms from './Terms.svelte';
import Privacy from './Privacy.svelte';
import Header from '../lib/Header.svelte';
import Footer from '../lib/Footer.svelte';

beforeEach(() => {
  navigate.mockClear();
  localStorage.clear();
});

// The server enforces these. A page that promises different numbers is worse
// than no page, so read them from the source of truth rather than retyping them.
function serverLimit(name) {
  // vitest runs with the frontend package as its cwd (see vite.config.js).
  const source = readFileSync(join(process.cwd(), '..', 'backend', 'billing.py'), 'utf8');
  const match = source.match(new RegExp(`^${name}\\s*=\\s*(\\d+)`, 'm'));
  if (!match) throw new Error(`${name} not found in backend/billing.py`);
  return Number(match[1]);
}

function serverString(name) {
  const source = readFileSync(join(process.cwd(), '..', 'backend', 'billing.py'), 'utf8');
  const match = source.match(new RegExp(`^${name}\\s*=\\s*"([^"]+)"`, 'm'));
  if (!match) throw new Error(`${name} not found in backend/billing.py`);
  return match[1];
}

const rowOf = (name) => screen.getByRole('row', { name: new RegExp(name, 'i') });

describe('Pricing - the numbers', () => {
  it('quotes the limits the server actually enforces', () => {
    render(Pricing);

    expect(within(rowOf('Boards you own')).getAllByRole('cell')[0]).toHaveTextContent(
      String(serverLimit('FREE_MAX_BOARDS'))
    );
    expect(within(rowOf('Cards per board')).getAllByRole('cell')[0]).toHaveTextContent(
      String(serverLimit('FREE_MAX_CARDS_PER_BOARD'))
    );
  });

  it('advertises the price `manage.py billing-check` holds the Stripe Price to', () => {
    // billing-check fails if the configured Price differs from these, so the
    // page, the preflight and the bill all answer to one number.
    expect(serverString('PRO_PRICE_INTERVAL')).toBe('month');
    render(Pricing);

    const cents = serverLimit('PRO_PRICE_CENTS');
    expect(within(rowOf('Price')).getAllByRole('cell')[1]).toHaveTextContent(`$${cents / 100}/mo`);
  });

  it('shows Free at $0 and Pro unlimited on both limits', () => {
    render(Pricing);

    const price = within(rowOf('Price')).getAllByRole('cell');
    expect(price[0]).toHaveTextContent('$0');
    expect(within(rowOf('Boards you own')).getAllByRole('cell')[1]).toHaveTextContent('Unlimited');
    expect(within(rowOf('Cards per board')).getAllByRole('cell')[1]).toHaveTextContent('Unlimited');
  });

  it('is a real table: plans are column headers, each limit a row header', () => {
    render(Pricing);

    expect(screen.getByRole('columnheader', { name: 'Free' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Pro' })).toBeInTheDocument();
    expect(screen.getByRole('rowheader', { name: 'Boards you own' })).toBeInTheDocument();
  });
});

describe('Pricing - what it tells people', () => {
  it('says the limits count what you own, and that shared boards are free to use', () => {
    render(Pricing);
    expect(screen.getByText(/limits are on what you own/i)).toBeInTheDocument();
    expect(screen.getByText(/shared with you doesn't/i)).toBeInTheDocument();
  });

  it('says every card counts, Done included', () => {
    render(Pricing);
    expect(screen.getByText(/including the ones\s+in Done/i)).toBeInTheDocument();
  });

  it('says going over never deletes anything', () => {
    render(Pricing);
    expect(screen.getByText(/nothing is deleted for you/i)).toBeInTheDocument();
  });

  it('mentions that self-hosting is MIT and unlimited, with a link to the source', () => {
    render(Pricing);
    expect(screen.getByText(/MIT licensed/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /source on github/i })).toHaveAttribute(
      'href',
      'https://github.com/japherwocky/pkanban'
    );
  });

  it('no longer says pricing is still being finalized', () => {
    render(Pricing);
    expect(screen.queryByText(/still finalizing/i)).toBeNull();
  });
});

describe('Pricing - the call to action', () => {
  it('sends a logged-out visitor to sign up, and says where to upgrade afterwards', async () => {
    render(Pricing);

    await fireEvent.click(screen.getByRole('button', { name: 'Sign up free' }));

    expect(navigate).toHaveBeenCalledWith('/signup');
    expect(screen.getByText(/upgrade from settings/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Upgrade to Pro' })).toBeNull();
  });

  it('sends a logged-in user straight to the Plan page', async () => {
    localStorage.setItem('token', 'x');
    render(Pricing);

    await fireEvent.click(screen.getByRole('button', { name: 'Upgrade to Pro' }));

    expect(navigate).toHaveBeenCalledWith('/settings/plan');
    expect(screen.queryByRole('button', { name: 'Sign up free' })).toBeNull();
  });
});

describe('Pricing is reachable', () => {
  it('has a Pricing entry in the desktop header nav', async () => {
    render(Header);

    await fireEvent.click(screen.getByRole('button', { name: 'Pricing' }));

    expect(navigate).toHaveBeenCalledWith('/pricing');
  });

  it('has a Pricing entry in the mobile menu too', async () => {
    render(Header);
    expect(screen.getAllByRole('button', { name: 'Pricing' })).toHaveLength(1);

    await fireEvent.click(screen.getByRole('button', { name: 'Toggle menu' }));
    const entries = screen.getAllByRole('button', { name: 'Pricing' });
    expect(entries).toHaveLength(2);

    await fireEvent.click(entries[1]);
    expect(navigate).toHaveBeenCalledWith('/pricing');
  });

  it('has a Pricing entry in the footer', async () => {
    render(Footer);

    await fireEvent.click(screen.getByRole('button', { name: 'Pricing' }));

    expect(navigate).toHaveBeenCalledWith('/pricing');
  });
});

describe('The legal pages cover paid plans', () => {
  it('Terms covers billing, cancellation, what happens at the end, refunds and price changes', () => {
    render(Terms);

    for (const heading of [
      'Plans and Billing',
      'Cancellation',
      'When Pro Ends or a Limit Is Passed',
      'Refunds',
      'Price Changes',
    ]) {
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    }
  });

  it('Terms promises nothing is deleted when Pro ends', () => {
    render(Terms);
    expect(screen.getByText(/nothing is deleted/i)).toBeInTheDocument();
  });

  it('Privacy says Stripe handles payment and that we never see the card number', () => {
    render(Privacy);

    expect(screen.getByRole('heading', { name: 'Payments' })).toBeInTheDocument();
    expect(screen.getByText(/handled by Stripe/i)).toBeInTheDocument();
    expect(screen.getByText(/never see or keep your card number/i)).toBeInTheDocument();
  });
});
