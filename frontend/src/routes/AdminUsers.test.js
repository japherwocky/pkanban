import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/svelte';

const list = vi.fn();
const update = vi.fn();
vi.mock('../lib/api.js', () => ({
  api: { admin: { users: { list: (...a) => list(...a), update: (...a) => update(...a) } } },
}));

import AdminUsers from './AdminUsers.svelte';

const USERS = [
  { id: 1, username: 'alice', email: 'a@example.com', admin: true, plan: 'free', has_stripe_customer: false },
  { id: 2, username: 'bob', email: null, admin: false, plan: 'pro', has_stripe_customer: true },
];

beforeEach(() => {
  list.mockReset();
  update.mockReset();
  list.mockResolvedValue(USERS);
  update.mockResolvedValue({});
});

async function openEdit(name) {
  const card = (await screen.findByRole('heading', { name })).closest('.user-card');
  await fireEvent.click(within(card).getByRole('button', { name: 'Edit' }));
  return screen.findByRole('dialog');
}

describe('AdminUsers plan control', () => {
  it('marks Pro accounts in the list and nobody else', async () => {
    render(AdminUsers);
    const bob = (await screen.findByRole('heading', { name: 'bob' })).closest('.user-card');
    const alice = screen.getByRole('heading', { name: 'alice' }).closest('.user-card');

    expect(within(bob).getByText('Pro')).toBeInTheDocument();
    expect(within(alice).queryByText('Pro')).toBeNull();
  });

  it('opens the editor on the account\'s current plan', async () => {
    render(AdminUsers);
    const dialog = await openEdit('bob');
    expect(within(dialog).getByLabelText('Plan')).toHaveValue('pro');
  });

  it('sends the chosen plan with the rest of the user', async () => {
    render(AdminUsers);
    const dialog = await openEdit('alice');

    await fireEvent.change(within(dialog).getByLabelText('Plan'), { target: { value: 'pro' } });
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Save Changes' }));

    expect(update).toHaveBeenCalledWith(1, {
      username: 'alice',
      email: 'a@example.com',
      admin: true,
      plan: 'pro',
    });
  });

  it('leaves the plan out when the admin did not touch it', async () => {
    // The list may be minutes old and a webhook may have changed the plan
    // since; echoing the stale value would put it back.
    render(AdminUsers);
    const dialog = await openEdit('alice');

    await fireEvent.input(within(dialog).getByLabelText('Email (optional)'), {
      target: { value: 'fixed@example.com' },
    });
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Save Changes' }));

    expect(update).toHaveBeenCalledWith(1, {
      username: 'alice',
      email: 'fixed@example.com',
      admin: true,
    });
  });

  it('warns that Stripe will reset a manual change on a Stripe-backed account', async () => {
    render(AdminUsers);
    const dialog = await openEdit('bob');
    expect(within(dialog).queryByRole('note')).toBeNull();

    await fireEvent.change(within(dialog).getByLabelText('Plan'), { target: { value: 'free' } });

    expect(within(dialog).getByRole('note')).toHaveTextContent(/stripe stays the source of truth/i);
  });

  it('does not warn about Stripe for an account Stripe has never heard of', async () => {
    render(AdminUsers);
    const dialog = await openEdit('alice');

    await fireEvent.change(within(dialog).getByLabelText('Plan'), { target: { value: 'pro' } });

    expect(within(dialog).queryByRole('note')).toBeNull();
  });
});
