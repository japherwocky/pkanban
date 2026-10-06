import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/svelte';

const create = vi.fn();
const del = vi.fn();
vi.mock('./api.js', () => ({
  api: { comments: { create: (...a) => create(...a), delete: (...a) => del(...a), update: vi.fn() } },
}));

import Comments from './Comments.svelte';

// Comments reads the signed-in user id from the JWT payload's `sub`.
const tokenFor = (sub) => `x.${btoa(JSON.stringify({ sub }))}.y`;
const CARD = {
  id: 7,
  comments: [
    { id: 1, user_id: 'me', username: 'me', content: 'mine', created_at: '2026-01-01T00:00:00Z' },
    { id: 2, user_id: 'them', username: 'them', content: 'theirs', created_at: '2026-01-01T00:00:00Z' },
  ],
};

beforeEach(() => {
  create.mockReset();
  del.mockReset();
  localStorage.setItem('token', tokenFor('me'));
});
afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

const commentEl = (text) => screen.getByText(text).closest('.comment');

describe('Comments', () => {
  it('offers edit and delete on your own comments only', () => {
    render(Comments, { card: CARD });
    expect(within(commentEl('mine')).getByTitle('Delete comment')).toBeInTheDocument();
    expect(within(commentEl('theirs')).queryByTitle('Delete comment')).toBeNull();
  });

  it('adds a created comment to the list and tells the parent', async () => {
    const onCommentsUpdate = vi.fn();
    create.mockResolvedValue({ id: 3, user_id: 'me', username: 'me', content: 'hello', created_at: '2026-01-01T00:00:00Z' });
    render(Comments, { card: CARD, onCommentsUpdate });

    await fireEvent.input(screen.getByPlaceholderText('Add a comment...'), { target: { value: ' hello ' } });
    await fireEvent.click(screen.getByRole('button', { name: /comment/i }));

    expect(create).toHaveBeenCalledWith(7, 'hello');
    expect(await screen.findByText('hello')).toBeInTheDocument();
    expect(onCommentsUpdate).toHaveBeenCalledWith(7, expect.arrayContaining([expect.objectContaining({ id: 3 })]));
  });

  it('removes a comment only after the server accepted the delete', async () => {
    vi.stubGlobal('confirm', () => true);
    del.mockResolvedValue({});
    render(Comments, { card: CARD });
    await fireEvent.click(within(commentEl('mine')).getByTitle('Delete comment'));

    expect(del).toHaveBeenCalledWith(1);
    await vi.waitFor(() => expect(screen.queryByText('mine')).toBeNull());
  });

  it('keeps the comment when the delete fails', async () => {
    vi.stubGlobal('confirm', () => true);
    vi.stubGlobal('alert', vi.fn());
    del.mockRejectedValue(new Error('nope'));
    render(Comments, { card: CARD });
    await fireEvent.click(within(commentEl('mine')).getByTitle('Delete comment'));

    await vi.waitFor(() => expect(alert).toHaveBeenCalled());
    expect(screen.getByText('mine')).toBeInTheDocument();
  });

  it('shows the comments of a card swapped in later, not the previous one', async () => {
    const { rerender } = render(Comments, { card: CARD });
    await rerender({ card: { id: 8, comments: [] } });
    expect(screen.queryByText('mine')).toBeNull();
    expect(screen.getByText(/No comments yet/)).toBeInTheDocument();
  });
});
