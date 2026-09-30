<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from '../lib/api.js';

  // A board this full is worth a warning before it becomes a 402.
  const NEAR = 0.8;

  let usage = $state(null);
  let loading = $state(true);
  let error = $state(null);

  onMount(async () => {
    try {
      usage = await api.me.usage();
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  const limited = $derived(
    usage !== null && usage.billing_enabled && usage.max_boards !== null
  );

  const nearBoards = $derived(
    limited
      ? usage.boards.filter((b) => b.cards >= usage.max_cards_per_board * NEAR)
      : []
  );

  function percent(used, max) {
    return Math.min(100, Math.round((used / max) * 100));
  }
</script>

<div class="plan-page">
  <div class="page-header">
    <h2>Plan</h2>
    <p class="description">What your plan includes, and how much of it you are using.</p>
  </div>

  {#if loading}
    <div class="loading">Loading plan...</div>
  {:else if error}
    <div class="notice" role="alert">Could not load your plan: {error}</div>
  {:else}
    <section class="card">
      <div class="row">
        <span class="label">Current plan</span>
        <span class="badge" class:pro={usage.plan === 'pro'}>{usage.plan}</span>
      </div>

      {#if !usage.billing_enabled}
        <p class="muted">This server does not enforce plan limits.</p>
      {:else if !limited}
        <p class="muted">Unlimited boards and cards.</p>
      {/if}
    </section>

    {#if limited}
      <section class="card">
        <div class="row">
          <span class="label">Boards you own</span>
          <span class="figure">{usage.boards_owned} / {usage.max_boards}</span>
        </div>
        <div
          class="meter"
          class:full={usage.boards_owned >= usage.max_boards}
          role="progressbar"
          aria-label="Boards owned"
          aria-valuenow={usage.boards_owned}
          aria-valuemin="0"
          aria-valuemax={usage.max_boards}
        >
          <div class="fill" style="width: {percent(usage.boards_owned, usage.max_boards)}%"></div>
        </div>
        <p class="muted">
          Only boards you own count. Boards shared with you are free for you to use.
        </p>
      </section>

      <section class="card">
        <div class="row">
          <span class="label">Cards per board</span>
          <span class="figure">up to {usage.max_cards_per_board}</span>
        </div>
        {#if nearBoards.length === 0}
          <p class="muted">None of your boards are close to the limit.</p>
        {:else}
          <ul class="boards">
            {#each nearBoards as board (board.id)}
              {@const full = board.cards >= usage.max_cards_per_board}
              <li>
                <div class="row">
                  <a
                    href={`/boards/${board.id}`}
                    onclick={(e) => { e.preventDefault(); navigate(`/boards/${board.id}`); }}
                  >{board.name}</a>
                  <span class="figure" class:warn={full}>
                    {board.cards} / {usage.max_cards_per_board}{full ? ' (full)' : ''}
                  </span>
                </div>
                <div
                  class="meter"
                  class:full
                  role="progressbar"
                  aria-label={`Cards on ${board.name}`}
                  aria-valuenow={board.cards}
                  aria-valuemin="0"
                  aria-valuemax={usage.max_cards_per_board}
                >
                  <div class="fill" style="width: {percent(board.cards, usage.max_cards_per_board)}%"></div>
                </div>
              </li>
            {/each}
          </ul>
        {/if}
        <p class="muted">Every card counts, Done included.</p>
      </section>
    {/if}
  {/if}
</div>

<style>
  .plan-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .page-header h2 {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-1) 0;
  }

  .description,
  .muted {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0;
  }

  .loading {
    text-align: center;
    padding: var(--space-12);
    color: var(--color-muted-foreground);
  }

  .notice {
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    color: var(--color-destructive);
  }

  .card {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-5);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
  }

  .row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--space-4);
  }

  .label {
    font-weight: 700;
    color: var(--color-foreground);
  }

  .figure {
    font-family: var(--font-mono, monospace);
    color: var(--color-foreground);
  }

  .figure.warn {
    color: var(--color-destructive);
  }

  .badge {
    padding: var(--space-1) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    font-size: var(--text-sm);
    text-transform: capitalize;
    color: var(--color-muted-foreground);
  }

  .badge.pro {
    border-color: var(--color-primary);
    color: var(--color-primary);
  }

  .meter {
    height: 8px;
    background: var(--color-muted);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }

  .fill {
    height: 100%;
    background: var(--color-primary);
  }

  .meter.full .fill {
    background: var(--color-destructive);
  }

  .boards {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .boards li {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
</style>
