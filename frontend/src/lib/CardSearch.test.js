import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';

const navigate = vi.fn();
vi.mock('svelte-routing', () => ({ navigate: (...args) => navigate(...args) }));

const search = vi.fn();
vi.mock('./api.js', () => ({ api: { cards: { search: (...args) => search(...args) } } }));

import CardSearch from './CardSearch.svelte';

const archiving = {
  id: 781,
  title: 'Card archiving',
  snippet: 'archived cards still \x02count\x03 toward <b>the</b> limit',
  column_id: 4,
  column_name: 'Todo',
  board_id: 1,
  board_name: 'Dev',
};

function type(text) {
  const input = screen.getByRole('searchbox', { name: 'Search cards' });
  input.value = text;
  return fireEvent.input(input);
}

beforeEach(() => {
  navigate.mockClear();
  search.mockReset();
});

describe('CardSearch', () => {
  it('shows matching cards with the matched words marked', async () => {
    search.mockResolvedValue([archiving]);
    render(CardSearch);

    await type('count');

    const link = await screen.findByRole('link', { name: /Card archiving/ });
    expect(link.getAttribute('href')).toBe('/boards/1/card/781');
    expect(link.textContent).toContain('Dev / Todo');
    expect(link.querySelector('mark').textContent).toBe('count');
    // Card text is text: the <b> arrives as characters, not as an element.
    expect(link.querySelector('b')).toBeNull();
    expect(link.textContent).toContain('<b>the</b>');
    expect(search).toHaveBeenCalledWith('count', expect.anything());
  });

  it('marks archived results', async () => {
    search.mockResolvedValue([
      { ...archiving, archived_at: '2026-10-15T12:00:00Z' },
      { ...archiving, id: 782, title: 'Launch billing', archived_at: null },
    ]);
    render(CardSearch);

    await type('card');

    const archived = await screen.findByRole('link', { name: /Card archiving/ });
    const live = screen.getByRole('link', { name: /Launch billing/ });
    expect(archived.querySelector('.archived-badge').textContent).toBe('Archived');
    expect(live.querySelector('.archived-badge')).toBeNull();
  });

  it('says so when nothing matches', async () => {
    search.mockResolvedValue([]);
    render(CardSearch);

    await type('nothing');

    expect(await screen.findByText('No matching cards')).toBeTruthy();
  });

  it('a plain click navigates in the app', async () => {
    search.mockResolvedValue([archiving]);
    render(CardSearch);
    await type('count');

    await fireEvent.click(await screen.findByRole('link', { name: /Card archiving/ }));

    expect(navigate).toHaveBeenCalledWith('/boards/1/card/781');
  });

  it('only the last query is ever shown', async () => {
    let answerFirst;
    search.mockImplementationOnce(
      (q, { signal }) =>
        new Promise((resolve, reject) => {
          answerFirst = () => resolve([{ ...archiving, id: 1, title: 'Stale' }]);
          signal.addEventListener('abort', () =>
            reject(Object.assign(new Error('aborted'), { name: 'AbortError' })),
          );
        }),
    );
    search.mockResolvedValueOnce([archiving]);
    render(CardSearch);

    await type('arch');
    await waitFor(() => expect(search).toHaveBeenCalledTimes(1));
    await type('archive');
    await screen.findByRole('link', { name: /Card archiving/ });
    answerFirst();

    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText('Stale')).toBeNull();
  });

  it('Escape clears the query and the results', async () => {
    search.mockResolvedValue([archiving]);
    render(CardSearch);
    await type('count');
    await screen.findByRole('link', { name: /Card archiving/ });

    await fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Escape' });

    expect(screen.getByRole('searchbox').value).toBe('');
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('"/" focuses the search box from elsewhere on the page', async () => {
    render(CardSearch);

    await fireEvent.keyDown(document.body, { key: '/' });

    expect(document.activeElement).toBe(screen.getByRole('searchbox'));
  });

  it('"/" typed in an open dialog stays there', async () => {
    render(CardSearch);
    const dialog = document.createElement('div');
    dialog.setAttribute('role', 'dialog');
    dialog.innerHTML = '<button>Close</button>';
    document.body.append(dialog);

    await fireEvent.keyDown(dialog.querySelector('button'), { key: '/' });

    expect(document.activeElement).not.toBe(screen.getByRole('searchbox'));
    dialog.remove();
  });

  it('offers no choice of board when it is not on one', async () => {
    search.mockResolvedValue([archiving]);
    render(CardSearch);

    await type('count');
    await screen.findByRole('link', { name: /Card archiving/ });

    expect(screen.queryByRole('group', { name: 'Where to search' })).toBeNull();
    expect(search.mock.calls[0][1].boardId).toBeNull();
  });
});

describe('CardSearch on a board', () => {
  const onBoard = (props = {}) => render(CardSearch, { props: { boardId: 1, ...props } });

  it('searches that board first, and names only the column', async () => {
    search.mockResolvedValue([archiving]);
    onBoard();
    expect(screen.getByRole('searchbox').placeholder).toContain('Search this board');

    await type('count');

    const link = await screen.findByRole('link', { name: /Card archiving/ });
    expect(search).toHaveBeenCalledWith('count', expect.objectContaining({ boardId: 1 }));
    expect(link.querySelector('.where').textContent).toBe('Todo');
    expect(screen.getByRole('button', { name: 'This board' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('"All boards" searches again, everywhere, and says which board', async () => {
    search.mockResolvedValueOnce([]);
    search.mockResolvedValueOnce([{ ...archiving, board_id: 2, board_name: 'Ops' }]);
    onBoard();
    await type('count');
    await screen.findByText('No matching cards');

    await fireEvent.click(screen.getByRole('button', { name: 'All boards' }));

    const link = await screen.findByRole('link', { name: /Card archiving/ });
    expect(search).toHaveBeenLastCalledWith('count', expect.objectContaining({ boardId: null }));
    expect(link.querySelector('.where').textContent).toBe('Ops / Todo');
    expect(screen.getByRole('searchbox').placeholder).toContain('Search every board');
  });

  it('lets the page open a card itself, and follows the link when it declines', async () => {
    search.mockResolvedValue([archiving, { ...archiving, id: 900, title: 'Elsewhere', board_id: 2 }]);
    const onopen = vi.fn((result) => result.board_id === 1);
    onBoard({ onopen });
    await type('count');

    await fireEvent.click(await screen.findByRole('link', { name: /Card archiving/ }));
    expect(onopen).toHaveBeenCalledWith(expect.objectContaining({ id: 781 }));
    expect(navigate).not.toHaveBeenCalled();

    await fireEvent.click(screen.getByRole('link', { name: /Elsewhere/ }));
    expect(navigate).toHaveBeenCalledWith('/boards/2/card/900');
  });

  it('leaves a ctrl-click to the browser', async () => {
    search.mockResolvedValue([archiving]);
    const onopen = vi.fn(() => true);
    onBoard({ onopen });
    await type('count');

    await fireEvent.click(await screen.findByRole('link', { name: /Card archiving/ }), { ctrlKey: true });

    expect(onopen).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });
});

describe('CardSearch floating under a header', () => {
  const floating = (props = {}) => render(CardSearch, { props: { boardId: 1, floating: true, ...props } });

  it('puts the results away on a click elsewhere and brings them back on focus', async () => {
    search.mockResolvedValue([archiving]);
    floating();
    await type('count');
    await screen.findByRole('link', { name: /Card archiving/ });

    await fireEvent.pointerDown(document.body);
    expect(screen.queryByRole('link')).toBeNull();
    // The query is kept: the panel was in the way, not finished with.
    expect(screen.getByRole('searchbox').value).toBe('count');

    await fireEvent.focus(screen.getByRole('searchbox'));
    expect(screen.getByRole('link', { name: /Card archiving/ })).toBeTruthy();
  });

  it('stays open for a click inside it', async () => {
    search.mockResolvedValue([archiving]);
    floating();
    await type('count');
    const link = await screen.findByRole('link', { name: /Card archiving/ });

    await fireEvent.pointerDown(link.querySelector('.snippet'));

    expect(screen.getByRole('link', { name: /Card archiving/ })).toBeTruthy();
  });

  it('closes once a card is opened', async () => {
    search.mockResolvedValue([archiving]);
    floating({ onopen: () => true });
    await type('count');

    await fireEvent.click(await screen.findByRole('link', { name: /Card archiving/ }));

    expect(screen.queryByRole('link')).toBeNull();
  });

  it('results in the page are not put away by a click elsewhere', async () => {
    search.mockResolvedValue([archiving]);
    render(CardSearch);
    await type('count');
    await screen.findByRole('link', { name: /Card archiving/ });

    await fireEvent.pointerDown(document.body);

    expect(screen.getByRole('link', { name: /Card archiving/ })).toBeTruthy();
  });
});
