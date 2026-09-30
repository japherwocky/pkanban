import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';

vi.mock('svelte-routing', () => ({ navigate: vi.fn() }));

const usage = vi.fn();
vi.mock('../lib/api.js', () => ({ api: { me: { usage: (...a) => usage(...a) } } }));

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
beforeEach(() => {
  usage.mockReset();
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
