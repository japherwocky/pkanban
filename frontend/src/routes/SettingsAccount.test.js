import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';

const changePassword = vi.fn();
vi.mock('../lib/api.js', () => ({
  api: { me: { changePassword: (...a) => changePassword(...a) } },
}));

import SettingsAccount from './SettingsAccount.svelte';

beforeEach(() => {
  changePassword.mockReset();
});

async function fill(current, next, confirm) {
  await fireEvent.input(screen.getByLabelText('Current password'), { target: { value: current } });
  await fireEvent.input(screen.getByLabelText('New password'), { target: { value: next } });
  await fireEvent.input(screen.getByLabelText('Confirm new password'), { target: { value: confirm } });
}

describe('SettingsAccount', () => {
  it('sends current and new password, then confirms and clears the form', async () => {
    changePassword.mockResolvedValue({ ok: true });
    render(SettingsAccount);
    await fill('old-pass', 'new-pass', 'new-pass');
    await fireEvent.click(screen.getByRole('button', { name: 'Change password' }));

    expect(changePassword).toHaveBeenCalledWith('old-pass', 'new-pass');
    expect(await screen.findByText('Password changed.')).toBeInTheDocument();
    expect(screen.getByLabelText('Current password')).toHaveValue('');
  });

  it('does not call the API when the confirmation differs', async () => {
    render(SettingsAccount);
    await fill('old-pass', 'new-pass', 'typo');
    await fireEvent.click(screen.getByRole('button', { name: 'Change password' }));

    expect(changePassword).not.toHaveBeenCalled();
    expect(await screen.findByRole('alert')).toHaveTextContent('do not match');
  });

  it('shows the server error and keeps what was typed', async () => {
    changePassword.mockRejectedValue(new Error('Current password is incorrect'));
    render(SettingsAccount);
    await fill('wrong', 'new-pass', 'new-pass');
    await fireEvent.click(screen.getByRole('button', { name: 'Change password' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Current password is incorrect');
    expect(screen.getByLabelText('New password')).toHaveValue('new-pass');
  });
});
