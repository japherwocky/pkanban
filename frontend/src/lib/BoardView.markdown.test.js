import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/svelte';

vi.mock('svelte-routing', () => ({ navigate: vi.fn() }));

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

const DESCRIPTION = '# Plan\n\n**Ship it** with `npm ci`.\n\n- [x] tests\n- [ ] deploy';

const board = () => ({
  id: 1,
  name: 'Board',
  owner_id: 1,
  columns: [
    {
      id: 10,
      name: 'Todo',
      archived_count: 0,
      cards: [
        { id: 1, title: 'alpha', description: DESCRIPTION, archived_at: null, comments: [] },
        { id: 2, title: 'beta', description: null, archived_at: null, comments: [] },
      ],
    },
  ],
});

function renderBoard() {
  return render(BoardView, {
    props: { board: board(), onBack: () => {}, availableTeams: [], onShare: () => {}, onRename: () => {} },
  });
}

// By the tile's own title: an open card's dialog title says the same words,
// and svelte-dnd-action replaces the tile's button role with its own.
const tile = (title) =>
  [...document.querySelectorAll('.card')].find((el) =>
    el.querySelector('.card-title').textContent.trim().endsWith(title),
  );

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', `h.${btoa(JSON.stringify({ sub: '1' }))}.s`);
});

describe('a card tile', () => {
  it('previews the description as plain words, without the Markdown', () => {
    renderBoard();
    const preview = tile('alpha').querySelector('.card-description');
    expect(preview.textContent).toBe('Plan Ship it with npm ci. tests deploy');
    expect(preview.querySelector('*')).toBeNull();
    // Screen readers get the same words, not the syntax.
    expect(tile('alpha').getAttribute('aria-label')).toBe('Open card: alpha. Plan Ship it with npm ci. tests deploy');
  });
});

describe('an open card', () => {
  it('shows the description rendered, titled with the card', async () => {
    renderBoard();
    await fireEvent.click(tile('alpha'));

    const dialog = screen.getByRole('dialog', { name: /^alpha\s*#1$/ });
    expect(within(dialog).getByRole('heading', { name: 'Plan' })).toBeInTheDocument();
    expect(within(dialog).getByText('Ship it').tagName).toBe('STRONG');
    expect(within(dialog).getAllByRole('checkbox')).toHaveLength(2);
    expect(within(dialog).queryByRole('textbox', { name: 'Description' })).toBeNull();
  });

  it('edits the raw Markdown, saves, and shows it rendered again', async () => {
    api.cards.update.mockResolvedValue({});
    renderBoard();
    await fireEvent.click(tile('alpha'));
    await fireEvent.click(screen.getByRole('button', { name: 'Edit' }));

    const textarea = screen.getByRole('textbox', { name: 'Description' });
    expect(textarea.value).toBe(DESCRIPTION);
    await fireEvent.input(textarea, { target: { value: 'Now *just* this.' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

    expect(api.cards.update).toHaveBeenCalledWith(1, 'alpha', 'Now *just* this.', null, null);
    const dialog = await screen.findByRole('dialog', { name: /^alpha\s*#1$/ });
    expect(within(dialog).getByText('just').tagName).toBe('EM');
    expect(tile('alpha').querySelector('.card-description').textContent).toBe('Now just this.');
  });

  it('cancelling an edit keeps the card as it was', async () => {
    renderBoard();
    await fireEvent.click(tile('alpha'));
    await fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
    await fireEvent.input(screen.getByRole('textbox', { name: 'Description' }), { target: { value: 'scrap' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(api.cards.update).not.toHaveBeenCalled();
    const dialog = screen.getByRole('dialog', { name: /^alpha\s*#1$/ });
    expect(within(dialog).getByRole('heading', { name: 'Plan' })).toBeInTheDocument();
  });

  it('offers to add a description to a card without one', async () => {
    renderBoard();
    await fireEvent.click(tile('beta'));
    await fireEvent.click(screen.getByRole('button', { name: 'Add a description' }));

    expect(screen.getByRole('textbox', { name: 'Description' }).value).toBe('');
    expect(screen.getByRole('textbox', { name: 'Title' }).value).toBe('beta');
  });

  it('never runs script written into a card', async () => {
    const hostile = board();
    hostile.columns[0].cards[0].description =
      '<img src=x onerror="window.__pwned = 1"> [x](javascript:window.__pwned=1)';
    render(BoardView, {
      props: { board: hostile, onBack: () => {}, availableTeams: [], onShare: () => {}, onRename: () => {} },
    });
    await fireEvent.click(tile('alpha'));

    const dialog = screen.getByRole('dialog', { name: /^alpha\s*#1$/ });
    expect(dialog.querySelector('img')).toBeNull();
    expect(dialog.querySelector('a[href^="javascript"]')).toBeNull();
    expect(dialog.textContent).toContain('<img src=x onerror="window.__pwned = 1">');
  });
});
