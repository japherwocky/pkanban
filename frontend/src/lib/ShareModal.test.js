import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import ShareModal from './ShareModal.svelte';

const board = {
  id: 7,
  name: 'heckinquest',
  is_public_to_org: false,
  organization_id: null,
  org_permission: 'write',
  teams: [
    { id: 1, name: 'Core', organization_name: 'Acme', permission: 'write' },
    { id: 2, name: 'Curtis', organization_name: null, permission: 'read' },
  ],
};

const available = [
  { id: 1, name: 'Core', organization_name: 'Acme' },
  { id: 2, name: 'Curtis', organization_name: null },
  { id: 3, name: 'Design', organization_name: 'Acme' },
];

function renderModal(props = {}) {
  const handlers = {
    onSetTeam: vi.fn().mockResolvedValue(),
    onRemoveTeam: vi.fn().mockResolvedValue(),
    onShareOrg: vi.fn().mockResolvedValue(),
  };
  render(ShareModal, {
    props: { open: true, onClose: () => {}, board, availableTeams: available, availableOrgs: [], ...handlers, ...props },
  });
  return handlers;
}

describe('ShareModal', () => {
  it('lists every team with its level, and a team with no org by name alone', () => {
    renderModal();
    expect(screen.getByText('Core (Acme)')).toBeInTheDocument();
    expect(screen.getByText('Curtis')).toBeInTheDocument();
    expect(screen.getByLabelText('Access for Core').value).toBe('write');
    expect(screen.getByLabelText('Access for Curtis').value).toBe('read');
  });

  it('changes a level in place', async () => {
    const { onSetTeam } = renderModal();
    await fireEvent.change(screen.getByLabelText('Access for Curtis'), { target: { value: 'admin' } });
    expect(onSetTeam).toHaveBeenCalledWith(2, 'admin');
  });

  it('removes a team', async () => {
    const { onRemoveTeam } = renderModal();
    await fireEvent.click(screen.getByLabelText('Remove Core'));
    expect(onRemoveTeam).toHaveBeenCalledWith(1);
  });

  it('offers only the teams not already on the board, and adds at the chosen level', async () => {
    const { onSetTeam } = renderModal();
    const picker = screen.getByLabelText('Team to add');
    const offered = [...picker.options].map((o) => o.textContent);
    expect(offered).toEqual(['Add a team…', 'Design (Acme)']);

    await fireEvent.change(picker, { target: { value: picker.options[1].value } });
    await fireEvent.change(screen.getByLabelText('Access for the new team'), { target: { value: 'read' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    expect(onSetTeam).toHaveBeenCalledWith(3, 'read');
  });

  it('shows the server refusal instead of swallowing it', async () => {
    renderModal({ onRemoveTeam: vi.fn().mockRejectedValue(new Error('Sharing a board needs admin on it')) });
    await fireEvent.click(screen.getByLabelText('Remove Core'));
    expect(await screen.findByRole('alert')).toHaveTextContent('needs admin');
  });

  it('shares with the organization at a level', async () => {
    const { onShareOrg } = renderModal({ availableOrgs: [{ id: 9, name: 'Acme' }] });
    await fireEvent.click(screen.getByLabelText('Public to organization'));
    await fireEvent.change(screen.getByLabelText('Access for the organization'), { target: { value: 'read' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Save organization access' }));
    expect(onShareOrg).toHaveBeenCalledWith(true, 9, 'read');
  });
});
