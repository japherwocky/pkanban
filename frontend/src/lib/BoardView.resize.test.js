import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import { COLUMN_WIDTHS_KEY } from './columnWidths.js';

vi.mock('svelte-routing', () => ({ navigate: vi.fn() }));

const api = vi.hoisted(() => ({
  boards: { get: vi.fn() },
  cards: { reorder: vi.fn(), update: vi.fn(), create: vi.fn(), delete: vi.fn() },
  columns: { reorder: vi.fn(), create: vi.fn(), delete: vi.fn() },
}));
vi.mock('./api.js', () => ({ api }));

import BoardView from './BoardView.svelte';

const board = (extra = {}) => ({
  id: 1,
  name: 'Board',
  owner_id: 1,
  columns: [
    { id: 10, name: 'Todo', cards: [{ id: 1, title: 'alpha' }] },
    { id: 20, name: 'Done', cards: [] },
  ],
  ...extra,
});

const renderBoard = (props = {}) => render(BoardView, {
  props: { board: board(), onBack: () => {}, availableTeams: [], onRename: () => {}, ...props },
});

const handle = (name = 'Todo') => screen.getByRole('separator', { name: `Resize column ${name}` });
const columnOf = (el) => el.closest('.column');
const widthOf = (name = 'Todo') => columnOf(handle(name)).style.flexBasis;
const stored = () => JSON.parse(localStorage.getItem(COLUMN_WIDTHS_KEY) ?? '{}');

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', `h.${btoa(JSON.stringify({ sub: '1' }))}.s`);
});

describe('resizing a column', () => {
  it('starts every column at the default width', () => {
    renderBoard();
    expect(widthOf('Todo')).toBe('300px');
    expect(widthOf('Done')).toBe('300px');
    expect(handle()).toHaveAttribute('aria-valuenow', '300');
  });

  it('opens at the width saved on this device', () => {
    localStorage.setItem(COLUMN_WIDTHS_KEY, JSON.stringify({ 20: 480 }));
    renderBoard();
    expect(widthOf('Todo')).toBe('300px');
    expect(widthOf('Done')).toBe('480px');
  });

  it('follows a drag of the handle, and saves where it lands', async () => {
    renderBoard();
    await fireEvent.pointerDown(handle(), { pointerId: 1, button: 0, clientX: 100 });
    await fireEvent.pointerMove(handle(), { pointerId: 1, clientX: 160 });
    expect(widthOf()).toBe('360px');
    expect(stored()).toEqual({});

    await fireEvent.pointerMove(handle(), { pointerId: 1, clientX: 220 });
    await fireEvent.pointerUp(handle(), { pointerId: 1, clientX: 220 });
    expect(widthOf()).toBe('420px');
    expect(stored()).toEqual({ 10: 420 });
    expect(widthOf('Done')).toBe('300px');
  });

  it('stops at the limits', async () => {
    renderBoard();
    await fireEvent.pointerDown(handle(), { pointerId: 1, button: 0, clientX: 500 });
    await fireEvent.pointerMove(handle(), { pointerId: 1, clientX: 0 });
    expect(widthOf()).toBe('200px');
    await fireEvent.pointerMove(handle(), { pointerId: 1, clientX: 5000 });
    expect(widthOf()).toBe('800px');
  });

  it('takes arrow keys, Shift for bigger steps', async () => {
    renderBoard();
    await fireEvent.keyDown(handle(), { key: 'ArrowRight' });
    expect(widthOf()).toBe('320px');
    await fireEvent.keyDown(handle(), { key: 'ArrowRight', shiftKey: true });
    expect(widthOf()).toBe('420px');
    await fireEvent.keyDown(handle(), { key: 'ArrowLeft' });
    expect(widthOf()).toBe('400px');
    expect(stored()).toEqual({ 10: 400 });
  });

  it('goes back to the default on a double-click', async () => {
    localStorage.setItem(COLUMN_WIDTHS_KEY, JSON.stringify({ 10: 500 }));
    renderBoard();
    await fireEvent.dblClick(handle());
    expect(widthOf()).toBe('300px');
    expect(stored()).toEqual({});
  });

  // It is a view setting, kept in the browser: nothing for the server to refuse.
  it('is open to a read-only viewer', async () => {
    renderBoard({ board: board({ permission: 'read', owner_id: 2 }) });
    await fireEvent.keyDown(handle(), { key: 'ArrowRight' });
    expect(widthOf()).toBe('320px');
  });

  it('forgets the width of a deleted column', async () => {
    localStorage.setItem(COLUMN_WIDTHS_KEY, JSON.stringify({ 10: 500, 20: 400 }));
    api.columns.delete.mockResolvedValue({});
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderBoard();
    await fireEvent.click(columnOf(handle('Todo')).querySelector('.column-delete-btn'));
    await vi.waitFor(() => expect(stored()).toEqual({ 20: 400 }));
  });

  // svelte-dnd-action picks a column up from a native mousedown, touchstart,
  // or Enter/Space keydown on it. If any of those got past the handle, grabbing
  // it would drag the whole column away instead of resizing it.
  it('never lets the column drag see the handle', () => {
    renderBoard();
    const column = columnOf(handle());
    const reached = vi.fn();
    for (const type of ['mousedown', 'touchstart', 'keydown']) column.addEventListener(type, reached);

    fireEvent.mouseDown(handle(), { button: 0 });
    fireEvent.touchStart(handle(), { touches: [{ clientX: 0, clientY: 0 }] });
    fireEvent.keyDown(handle(), { key: 'Enter' });
    fireEvent.keyDown(handle(), { key: ' ' });
    expect(reached).not.toHaveBeenCalled();

    // and the column's own header, which is how a column is picked up, still can
    fireEvent.mouseDown(screen.getByRole('heading', { name: 'Todo' }), { button: 0 });
    expect(reached).toHaveBeenCalled();
  });
});
