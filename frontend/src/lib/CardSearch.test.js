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
});
