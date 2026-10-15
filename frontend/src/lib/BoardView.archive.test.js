import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';

const navigate = vi.fn();
vi.mock('svelte-routing', () => ({ navigate: (...args) => navigate(...args) }));

const api = vi.hoisted(() => ({
  boards: { get: vi.fn() },
  cards: {
    reorder: vi.fn(), update: vi.fn(), create: vi.fn(), delete: vi.fn(),
    archive: vi.fn(), unarchive: vi.fn(),
  },
  columns: { reorder: vi.fn(), create: vi.fn(), delete: vi.fn() },
  comments: { list: vi.fn().mockResolvedValue([]), create: vi.fn() },
}));
vi.mock('./api.js', () => ({ api }));

import BoardView from './BoardView.svelte';

const ARCHIVED_AT = '2026-10-15T12:00:00Z';

const liveBoard = () => ({
  id: 1,
  name: 'Board',
  owner_id: 1,
  columns: [
    {
      id: 10,
      name: 'Todo',
      archived_count: 1,
      cards: [
        { id: 1, title: 'alpha', archived_at: null, comments: [] },
        { id: 2, title: 'beta', archived_at: null, comments: [] },
      ],
    },
  ],
});

const withArchived = () => {
  const board = liveBoard();
  board.columns[0].cards.push({ id: 3, title: 'gamma', archived_at: ARCHIVED_AT, comments: [] });
  return board;
};

function renderBoard(props = {}) {
  return render(BoardView, {
    props: {
      board: liveBoard(),
      onBack: () => {}, availableTeams: [], onShare: () => {}, onRename: () => {},
      ...props,
    },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  api.comments.list.mockResolvedValue([]);
  localStorage.setItem('token', `h.${btoa(JSON.stringify({ sub: '1' }))}.s`);
});

describe('archiving a card', () => {
  it('takes it off the board and offers to show it', async () => {
    api.cards.archive.mockResolvedValue({ id: 2, archived_at: ARCHIVED_AT });
    renderBoard();
    expect(screen.getByText('Show archived (1)')).toBeInTheDocument();

    await fireEvent.click(screen.getByText('beta'));
    await fireEvent.click(await screen.findByRole('button', { name: 'Archive' }));

    expect(api.cards.archive).toHaveBeenCalledWith(2);
    await waitFor(() => expect(screen.queryByText('beta')).toBeNull());
    expect(screen.getByText('Show archived (2)')).toBeInTheDocument();
    expect(screen.getByText('1 cards')).toBeInTheDocument();
  });

  it('shows archived cards, marked, when asked', async () => {
    api.boards.get.mockResolvedValue(withArchived());
    renderBoard();

    await fireEvent.click(screen.getByText('Show archived (1)'));

    expect(api.boards.get).toHaveBeenCalledWith(1, { includeArchived: true });
    const gamma = (await screen.findByText('gamma')).closest('.card');
    expect(gamma.classList.contains('archived')).toBe(true);
    expect(gamma.textContent).toContain('Archived');
    expect(screen.getByText('Hide archived')).toBeInTheDocument();
    // The counts are of live cards, archived ones shown or not.
    expect(screen.getByText('2 cards')).toBeInTheDocument();
  });

  it('unarchives from the card itself', async () => {
    api.boards.get.mockResolvedValue(withArchived());
    api.cards.unarchive.mockResolvedValue({ id: 3, archived_at: null, position: 2 });
    renderBoard();
    await fireEvent.click(screen.getByText('Show archived (1)'));

    await fireEvent.click(await screen.findByText('gamma'));
    await fireEvent.click(await screen.findByRole('button', { name: 'Unarchive' }));

    expect(api.cards.unarchive).toHaveBeenCalledWith(3);
    await waitFor(() =>
      expect(screen.getByText('gamma').closest('.card').classList.contains('archived')).toBe(false),
    );
    expect(screen.getByText('3 cards')).toBeInTheDocument();
  });
});

describe('a link to an archived card', () => {
  it('loads the archived cards and opens it', async () => {
    api.boards.get.mockResolvedValue(withArchived());
    renderBoard({ initialCardId: '3' });

    await waitFor(() => expect(api.boards.get).toHaveBeenCalledWith(1, { includeArchived: true }));
    expect(await screen.findByRole('button', { name: 'Unarchive' })).toBeInTheDocument();
    expect(screen.getByDisplayValue('gamma')).toBeInTheDocument();
  });

  it('does not reload for a live card', async () => {
    renderBoard({ initialCardId: '1' });

    expect(await screen.findByDisplayValue('alpha')).toBeInTheDocument();
    expect(api.boards.get).not.toHaveBeenCalled();
  });
});

describe('deleting a column', () => {
  it('says how many archived cards go with it', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { container } = renderBoard();

    await fireEvent.click(container.querySelector('.column-delete-btn'));

    expect(confirm).toHaveBeenCalledWith('Delete column "Todo" and all its cards, including 1 archived?');
    confirm.mockRestore();
  });
});
