import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/svelte';
import BoardView from './BoardView.svelte';

vi.mock('./api.js', () => ({
  api: {
    boards: { get: vi.fn().mockResolvedValue({ columns: [] }) },
    cards: { reorder: vi.fn(), update: vi.fn(), create: vi.fn(), delete: vi.fn() },
    columns: { reorder: vi.fn(), create: vi.fn(), delete: vi.fn() },
  },
}));

const board = {
  id: 1,
  name: 'Test Board',
  owner_id: 1,
  columns: [
    { id: 10, name: 'Todo', cards: [{ id: 1, title: 'alpha' }, { id: 2, title: 'beta' }] },
    { id: 20, name: 'Done', cards: [{ id: 3, title: 'gamma' }] },
  ],
};

const renderBoard = () => render(BoardView, {
  props: { board, onBack: () => {}, availableTeams: [], onShare: () => {}, onRename: () => {} },
});

describe('BoardView drag-and-drop wiring', () => {
  // svelte-dnd-action is a Svelte *action*: it only runs when applied with
  // `use:dndzone={...}`. Written as a plain `dndzone={...}` attribute it type-
  // checks, compiles, renders and deploys -- and does nothing at all, leaving
  // a board whose cards simply cannot be dragged. That is how it shipped, and
  // no amount of testing the reorder logic would have caught it, because the
  // logic was never reached. These assertions check the action is live.

  it('renders no literal dndzone attribute', () => {
    const { container } = renderBoard();
    expect(container.querySelector('[dndzone]')).toBeNull();
  });

  it('initialises every card list as a drop zone', () => {
    const { container } = renderBoard();
    const lists = container.querySelectorAll('.cards-list');
    expect(lists.length).toBeGreaterThan(0);
    for (const list of lists) {
      // the action stamps these on the zones it manages
      expect(list.getAttribute('role')).toBe('list');
      expect(list.getAttribute('aria-describedby')).toBeTruthy();
    }
  });

  // The zone used to sit inside {#if cards.length > 0}. Dragging a column's
  // last card out unmounted it mid-drag, and its stale finalize put the card
  // back, so the UI showed it in both columns until a reload.
  it('keeps a drop zone on an empty column', () => {
    const { container } = render(BoardView, {
      props: {
        board: { ...board, columns: [...board.columns, { id: 30, name: 'Empty', cards: [] }] },
        onBack: () => {}, availableTeams: [], onShare: () => {}, onRename: () => {},
      },
    });
    const lists = container.querySelectorAll('.cards-list');
    expect(lists.length).toBe(3);
    expect(lists[2].getAttribute('role')).toBe('list');
    expect(container.querySelector('.empty-column')).toBeInTheDocument();
  });

  it('initialises the column container as a drop zone', () => {
    const { container } = renderBoard();
    const columns = container.querySelector('.columns-container');
    expect(columns.getAttribute('role')).toBe('list');
  });

  it('still renders the cards it was given', () => {
    const { getByText } = renderBoard();
    expect(getByText('alpha')).toBeInTheDocument();
    expect(getByText('gamma')).toBeInTheDocument();
  });
});
