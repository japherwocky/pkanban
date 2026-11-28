<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from './api.js';
  import { highlightSegments } from './searchSnippet.js';

  // `query` is bindable so the page can hide what the results replace.
  //
  // `boardId` is the board the box sits on, if any: the search starts there
  // and offers every board as the other choice. `floating` hangs the results
  // under the field instead of pushing the page down, for a box in a header.
  // `onopen(result)` lets the page open a card it already has on screen; it
  // returns true when it did, and anything else falls through to the link.
  let { query = $bindable(''), boardId = null, floating = false, onopen = null } = $props();

  let results = $state([]);
  let searching = $state(false);
  let error = $state(null);
  // Only read when there is a board to be scoped to.
  let scope = $state('board');
  // A floating panel covers the page under it, so it can be put away without
  // losing the query. Results in the page are always shown.
  let expanded = $state(true);
  let root;
  let input;
  let timer;
  let inflight = null;

  let onBoard = $derived(boardId != null && scope === 'board');
  let placeholder = $derived(
    boardId == null
      ? 'Search cards on every board  ( / )'
      : onBoard
        ? 'Search this board  ( / )'
        : 'Search every board  ( / )',
  );

  // Short: the server answers in about a millisecond, so this is only here to
  // avoid a request per keystroke from someone typing quickly.
  const DEBOUNCE_MS = 150;

  function oninput() {
    clearTimeout(timer);
    inflight?.abort();
    expanded = true;
    if (!query.trim()) {
      results = [];
      error = null;
      searching = false;
      return;
    }
    searching = true;
    timer = setTimeout(run, DEBOUNCE_MS);
  }

  async function run() {
    // Aborted rather than ignored, so an answer to "arch" can never land
    // after the answer to "archive" and replace it.
    const controller = new AbortController();
    inflight = controller;
    try {
      results = await api.cards.search(query, {
        boardId: onBoard ? boardId : null,
        signal: controller.signal,
      });
      error = null;
    } catch (e) {
      if (e.name === 'AbortError') return;
      error = e.message;
      results = [];
    } finally {
      if (inflight === controller) {
        inflight = null;
        searching = false;
      }
    }
  }

  function clear() {
    query = '';
    oninput();
    input?.focus();
  }

  function onkeydown(e) {
    if (e.key === 'Escape' && query) {
      e.preventDefault();
      clear();
    }
  }

  // Straight away, not debounced: it is one click, not typing.
  function setScope(next) {
    if (scope === next) return;
    scope = next;
    clearTimeout(timer);
    inflight?.abort();
    if (query.trim()) {
      searching = true;
      run();
    }
    input?.focus();
  }

  function cardHref(result) {
    return `/boards/${result.board_id}/card/${result.id}`;
  }

  // A real link, so it can be opened in a new tab; a plain click stays in the
  // app instead of reloading it.
  function open(e, result) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    if (floating) expanded = false;
    if (onopen?.(result) === true) return;
    navigate(cardHref(result));
  }

  // Tabbing out of a floating panel puts it away. A click is left to
  // onOutsidePointer: it has no relatedTarget when it lands on plain text,
  // inside the panel or not.
  function onfocusout(e) {
    if (floating && e.relatedTarget && !root.contains(e.relatedTarget)) expanded = false;
  }

  onMount(() => {
    // "/" jumps to the search box, unless it is being typed somewhere else
    // or a dialog is open over the page.
    function onGlobalKey(e) {
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
      const target = e.target;
      if (target.closest?.('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return;
      e.preventDefault();
      input?.focus();
    }
    function onOutsidePointer(e) {
      if (floating && !root.contains(e.target)) expanded = false;
    }
    window.addEventListener('keydown', onGlobalKey);
    window.addEventListener('pointerdown', onOutsidePointer);
    return () => {
      window.removeEventListener('keydown', onGlobalKey);
      window.removeEventListener('pointerdown', onOutsidePointer);
      clearTimeout(timer);
      inflight?.abort();
    };
  });
</script>

<div class="card-search" class:floating bind:this={root} {onfocusout}>
  <div class="field">
    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path stroke="currentColor" stroke-linecap="round" stroke-width="2" d="m21 21-4.35-4.35M17 10.5a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0Z"/>
    </svg>
    <input
      bind:this={input}
      bind:value={query}
      {oninput}
      {onkeydown}
      onfocus={() => (expanded = true)}
      type="search"
      {placeholder}
      aria-label="Search cards"
      autocomplete="off"
      spellcheck="false"
    />
    {#if query}
      <button type="button" class="clear" onclick={clear} aria-label="Clear search">×</button>
    {/if}
  </div>

  {#if query.trim() && (expanded || !floating)}
    <div class="results" aria-live="polite" aria-busy={searching}>
      {#if boardId != null}
        <div class="scope" role="group" aria-label="Where to search">
          <button type="button" aria-pressed={scope === 'board'} onclick={() => setScope('board')}>This board</button>
          <button type="button" aria-pressed={scope === 'all'} onclick={() => setScope('all')}>All boards</button>
        </div>
      {/if}
      {#if error}
        <p class="status error">{error}</p>
      {:else if results.length === 0}
        <p class="status">{searching ? 'Searching…' : 'No matching cards'}</p>
      {:else}
        <ul>
          {#each results as result (result.id)}
            <li>
              <a href={cardHref(result)} onclick={(e) => open(e, result)}>
                <span class="title-line">
                  <span class="card-id">#{result.id}</span>
                  <span class="title">{result.title}</span>
                  {#if result.archived_at}<span class="archived-badge">Archived</span>{/if}
                </span>
                <!-- On this board, the board's name is the page's own heading. -->
                <span class="where">{onBoard ? result.column_name : `${result.board_name} / ${result.column_name}`}</span>
                {#if result.snippet}
                  <span class="snippet">
                    {#each highlightSegments(result.snippet) as segment, i (i)}
                      {#if segment.match}<mark>{segment.text}</mark>{:else}{segment.text}{/if}
                    {/each}
                  </span>
                {/if}
              </a>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}
</div>

<style>
  .card-search {
    margin-bottom: var(--space-6);
  }

  .field {
    position: relative;
    display: flex;
    align-items: center;
  }

  .icon {
    position: absolute;
    left: var(--space-4);
    color: var(--color-muted-foreground);
    pointer-events: none;
  }

  input {
    width: 100%;
    padding: var(--space-3) var(--space-10) var(--space-3) var(--space-10);
    font-size: var(--text-base);
    border: 2px solid var(--color-border);
    background: var(--color-card);
    color: var(--color-foreground);
    transition: border-color var(--transition-fast);
  }

  /* The browser's own clear button would sit beside ours. */
  input::-webkit-search-cancel-button {
    appearance: none;
  }

  input:focus {
    outline: none;
    border-color: var(--color-primary);
  }

  .clear {
    position: absolute;
    right: var(--space-2);
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-lg);
    line-height: 1;
    background: transparent;
    border: none;
    color: var(--color-muted-foreground);
    cursor: pointer;
  }

  .clear:hover {
    color: var(--color-foreground);
  }

  .results {
    margin-top: var(--space-3);
  }

  .status {
    padding: var(--space-6) 0;
    text-align: center;
    color: var(--color-muted-foreground);
  }

  .status.error {
    color: var(--color-destructive);
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    border: 2px solid var(--color-border);
    background: var(--color-card);
  }

  li + li {
    border-top: 1px solid var(--color-border);
  }

  a {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-3) var(--space-4);
    color: inherit;
    text-decoration: none;
  }

  a:hover,
  a:focus-visible {
    background: var(--color-muted);
    outline: none;
  }

  .title-line {
    display: flex;
    gap: var(--space-2);
    align-items: baseline;
    min-width: 0;
  }

  .card-id {
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  .title {
    font-weight: 600;
    overflow-wrap: anywhere;
  }

  .where {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
  }

  .snippet {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    overflow-wrap: anywhere;
  }

  .archived-badge {
    flex-shrink: 0;
    padding: 0 var(--space-2);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--color-muted-foreground);
    border: 1px solid var(--color-border);
  }

  .scope {
    display: flex;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
  }

  .scope button {
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-xs);
    font-weight: 600;
    background: transparent;
    color: var(--color-muted-foreground);
    border: 1px solid var(--color-border);
    cursor: pointer;
  }

  .scope button:hover {
    color: var(--color-foreground);
  }

  .scope button[aria-pressed='true'] {
    color: var(--color-foreground);
    border-color: var(--color-primary);
  }

  /* In a header: a field the size of the buttons beside it, and results that
     hang under it over the page. */
  .floating {
    position: relative;
    flex: 0 1 16rem;
    min-width: 12rem;
    margin-bottom: 0;
  }

  .floating input {
    padding: var(--space-2) var(--space-8) var(--space-2) var(--space-8);
    font-size: var(--text-sm);
    border-width: 1px;
  }

  .floating .icon {
    left: var(--space-2);
  }

  .floating .clear {
    right: var(--space-1);
  }

  /* Under the modal (z-index 50), over the columns. Left-anchored and wider
     than the field: the header's other buttons sit to the field's right, so
     that is where the room is. */
  .floating .results {
    position: absolute;
    top: 100%;
    left: 0;
    z-index: 20;
    width: min(26rem, calc(100vw - 2 * var(--space-6)));
    max-height: min(70vh, 32rem);
    overflow-y: auto;
    margin-top: var(--space-2);
    padding: var(--space-3);
    background: var(--color-background);
    border: 1px solid var(--color-border);
    box-shadow: var(--shadow-lg);
  }

  .floating .status {
    padding: var(--space-4) 0;
  }

  .floating ul {
    border-width: 1px;
  }

  /* On a phone the header's actions wrap under the title, so the field takes
     the whole line and the results are exactly as wide as it is. */
  @media (max-width: 640px) {
    .floating {
      flex-basis: 100%;
    }

    .floating .results {
      right: 0;
      width: auto;
    }
  }

  mark {
    background: transparent;
    color: var(--color-foreground);
    font-weight: 700;
    text-decoration: underline;
    text-decoration-color: var(--color-primary);
    text-decoration-thickness: 2px;
    text-underline-offset: 2px;
  }
</style>
