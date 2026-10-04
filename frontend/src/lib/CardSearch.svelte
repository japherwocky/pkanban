<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from './api.js';
  import { highlightSegments } from './searchSnippet.js';

  // `query` is bindable so the page can hide what the results replace.
  let { query = $bindable('') } = $props();

  let results = $state([]);
  let searching = $state(false);
  let error = $state(null);
  let input;
  let timer;
  let inflight = null;

  // Short: the server answers in about a millisecond, so this is only here to
  // avoid a request per keystroke from someone typing quickly.
  const DEBOUNCE_MS = 150;

  function oninput() {
    clearTimeout(timer);
    inflight?.abort();
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
      results = await api.cards.search(query, { signal: controller.signal });
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

  function cardHref(result) {
    return `/boards/${result.board_id}/card/${result.id}`;
  }

  // A real link, so it can be opened in a new tab; a plain click stays in the
  // app instead of reloading it.
  function open(e, result) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    navigate(cardHref(result));
  }

  // "/" jumps to the search box, unless it is being typed somewhere else.
  onMount(() => {
    function onGlobalKey(e) {
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
      const target = e.target;
      if (target.closest?.('input, textarea, select, [contenteditable="true"]')) return;
      e.preventDefault();
      input?.focus();
    }
    window.addEventListener('keydown', onGlobalKey);
    return () => {
      window.removeEventListener('keydown', onGlobalKey);
      clearTimeout(timer);
      inflight?.abort();
    };
  });
</script>

<div class="card-search">
  <div class="field">
    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path stroke="currentColor" stroke-linecap="round" stroke-width="2" d="m21 21-4.35-4.35M17 10.5a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0Z"/>
    </svg>
    <input
      bind:this={input}
      bind:value={query}
      {oninput}
      {onkeydown}
      type="search"
      placeholder="Search cards on every board  ( / )"
      aria-label="Search cards"
      autocomplete="off"
      spellcheck="false"
    />
    {#if query}
      <button type="button" class="clear" onclick={clear} aria-label="Clear search">×</button>
    {/if}
  </div>

  {#if query.trim()}
    <div class="results" aria-live="polite" aria-busy={searching}>
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
                </span>
                <span class="where">{result.board_name} / {result.column_name}</span>
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
