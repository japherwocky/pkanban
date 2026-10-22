import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import Invite from './Invite.svelte';

const navigate = vi.fn();
vi.mock('svelte-routing', () => ({ navigate: (...args) => navigate(...args) }));

const get = vi.fn();
const accept = vi.fn();
vi.mock('../lib/api.js', () => ({
  api: { invites: { get: (...a) => get(...a), accept: (...a) => accept(...a) } },
}));

const base = {
  id: 1,
  email: 'curtis@example.com',
  status: 'pending',
  created_by_username: 'japhy',
  organization_name: null,
};

describe('Invite page', () => {
  beforeEach(() => {
    navigate.mockClear();
    localStorage.setItem('token', 'h.e30.s');
  });

  it('names the board, and what the level allows, for a board invite', async () => {
    get.mockResolvedValue({
      ...base,
      team_name: 'heckinquest: curtis',
      board_id: 7,
      board_name: 'heckinquest',
      permission: 'read',
    });
    render(Invite, { props: { params: { token: 't' } } });
    expect(await screen.findByText('heckinquest')).toBeInTheDocument();
    expect(screen.getByText("You'll be able to read it.")).toBeInTheDocument();
    expect(screen.queryByText(/heckinquest: curtis/)).toBeNull();
  });

  it('lands on the board after accepting', async () => {
    get.mockResolvedValue({ ...base, team_name: 't', board_id: 7, board_name: 'b', permission: 'write' });
    accept.mockResolvedValue({ ok: true, team_id: 3, board_id: 7 });
    render(Invite, { props: { params: { token: 't' } } });
    await fireEvent.click(await screen.findByRole('button', { name: 'Accept Invite' }));
    expect(navigate).toHaveBeenCalledWith('/boards/7');
  });

  it('describes a team with no organization without printing null', async () => {
    get.mockResolvedValue({ ...base, team_name: 'Core' });
    render(Invite, { props: { params: { token: 't' } } });
    expect(await screen.findByText(/A team\. You'll get the boards shared with it\./)).toBeInTheDocument();
    expect(screen.queryByText(/null/)).toBeNull();
  });
});
