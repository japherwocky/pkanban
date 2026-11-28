import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';

const navigate = vi.fn();
vi.mock('svelte-routing', () => ({ navigate: (...args) => navigate(...args) }));

const api = vi.hoisted(() => ({
  boards: { get: vi.fn() },
  cards: {
    reorder: vi.fn(), update: vi.fn(), create: vi.fn(), delete: vi.fn(),
    archive: vi.fn(), unarchive: vi.fn(), search: vi.fn(),
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

// What /api/search answers with for a card on this board.
const hit = (card) => ({
  snippet: '', column_id: 10, column_name: 'Todo', board_id: 1, board_name: 'Board',
  archived_at: null, ...card,
});

const renderBoard = (props = {}) => render(BoardView, {
  props: { board: liveBoard(), onBack: () => {}, availableTeams: [], onRename: () => {}, ...props },
});

async function searchFor(text) {
  const input = screen.getByRole('searchbox', { name: 'Search cards' });
  input.value = text;
  await fireEvent.input(input);
}

beforeEach(() => {
  vi.clearAllMocks();
  api.comments.list.mockResolvedValue([]);
  localStorage.setItem('token', `h.${btoa(JSON.stringify({ sub: '1' }))}.s`);
  history.replaceState(null, '', '/boards/1');
});

describe('searching from a board', () => {
  it('searches this board and opens a result without leaving it', async () => {
    api.cards.search.mockResolvedValue([hit({ id: 2, title: 'beta' })]);
    renderBoard();

    await searchFor('beta');
    await fireEvent.click(await screen.findByRole('link', { name: /beta/ }));

    expect(api.cards.search).toHaveBeenCalledWith('beta', expect.objectContaining({ boardId: 1 }));
    expect(await screen.findByRole('dialog', { name: /^beta\s*#2$/ })).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
    expect(api.boards.get).not.toHaveBeenCalled();
    expect(location.pathname).toBe('/boards/1/card/2');
    // The results are out of the card's way.
    expect(screen.queryByRole('link', { name: /beta/ })).toBeNull();
  });

  it('opens a second result after the first: the deep link is not what opens them', async () => {
    api.cards.search.mockResolvedValue([hit({ id: 1, title: 'alpha' }), hit({ id: 2, title: 'beta' })]);
    renderBoard({ initialCardId: '1' });
    await fireEvent.click(await screen.findByRole('button', { name: 'Close' }));

    await searchFor('a');
    await fireEvent.click(await screen.findByRole('link', { name: /beta/ }));

    expect(await screen.findByRole('dialog', { name: /^beta\s*#2$/ })).toBeInTheDocument();
  });

  it('shows the archived cards to open an archived result', async () => {
    api.cards.search.mockResolvedValue([hit({ id: 3, title: 'gamma', archived_at: ARCHIVED_AT })]);
    api.boards.get.mockResolvedValue(withArchived());
    renderBoard();

    await searchFor('gamma');
    await fireEvent.click(await screen.findByRole('link', { name: /gamma/ }));

    await waitFor(() => expect(api.boards.get).toHaveBeenCalledWith(1, { includeArchived: true }));
    expect(await screen.findByRole('dialog', { name: /^gamma\s*#3$/ })).toBeInTheDocument();
    expect(screen.getByText('Hide archived')).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('reloads for a card added since the board was loaded', async () => {
    api.cards.search.mockResolvedValue([hit({ id: 4, title: 'delta' })]);
    const board = liveBoard();
    board.columns[0].cards.push({ id: 4, title: 'delta', archived_at: null, comments: [] });
    api.boards.get.mockResolvedValue(board);
    renderBoard();

    await searchFor('delta');
    await fireEvent.click(await screen.findByRole('link', { name: /delta/ }));

    await waitFor(() => expect(api.boards.get).toHaveBeenCalledWith(1, { includeArchived: false }));
    expect(await screen.findByRole('dialog', { name: /^delta\s*#4$/ })).toBeInTheDocument();
  });

  it('goes to the other board for a result that lives there', async () => {
    api.cards.search.mockResolvedValue([hit({ id: 50, title: 'elsewhere', board_id: 2, board_name: 'Ops' })]);
    renderBoard();

    await searchFor('elsewhere');
    await fireEvent.click(await screen.findByRole('button', { name: 'All boards' }));
    await fireEvent.click(await screen.findByRole('link', { name: /elsewhere/ }));

    expect(navigate).toHaveBeenCalledWith('/boards/2/card/50');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('is there for someone who can only read the board', () => {
    renderBoard({ board: { ...liveBoard(), owner_id: 2, permission: 'read' } });

    expect(screen.getByRole('searchbox', { name: 'Search cards' })).toBeInTheDocument();
  });
});
