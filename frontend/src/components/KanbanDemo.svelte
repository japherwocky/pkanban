<script>
  import { onMount, onDestroy } from 'svelte';
  import { getDemoState } from '$lib/demoApi';

  // Initial cards - will be replaced by state from demoApi
  let columns = $state([
    { id: 1, name: 'Todo', cards: [] },
    { id: 2, name: 'In Progress', cards: [] },
    { id: 3, name: 'Done', cards: [] }
  ]);

  let animatedCard = $state(null);
  let previousCardState = $state(null);
  let isAnimating = $state(false);

  function updateColumnsFromState(state) {
    if (!state || !state.board) return;

    const newColumns = state.board.columns.map(col => ({
      id: col.id,
      name: col.name,
      cards: col.cards.map(card => ({
        id: card.id,
        title: card.title,
        description: card.description,
        isNew: card.isNew,
        justMoved: card.justMoved
      }))
    }));

    // Detect changes for animations
    detectChanges(columns, newColumns);
    columns = newColumns;
  }

  function detectChanges(oldCols, newCols) {
    if (!oldCols || oldCols.length === 0) {
      // First load - just set state without animation
      return;
    }

    // Check for new cards
    for (const newCol of newCols) {
      const oldCol = oldCols.find(c => c.id === newCol.id);
      for (const newCard of newCol.cards) {
        const oldCard = oldCol?.cards.find(c => c.id === newCard.id);
        if (!oldCard) {
          // New card added
          animatedCard = { ...newCard, columnId: newCol.id, isNew: true };
          setTimeout(() => {
            animatedCard = null;
          }, 300);
          return; // Handle one change at a time
        }
      }
    }

    // Check for moved cards
    for (const newCol of newCols) {
      const oldCol = oldCols.find(c => c.id === newCol.id);
      for (const newCard of newCol.cards) {
        const oldCard = oldCol?.cards.find(c => c.id === newCard.id);
        if (oldCard && oldCol.id !== newCol.id) {
          // Card moved between columns
          animatedCard = { ...newCard, columnId: newCol.id, justMoved: true };
          setTimeout(() => {
            animatedCard = null;
          }, 600);
          return;
        }
      }
    }

    // Check for description updates
    for (const newCol of newCols) {
      const oldCol = oldCols.find(c => c.id === newCol.id);
      for (const newCard of newCol.cards) {
        const oldCard = oldCol?.cards.find(c => c.id === newCard.id);
        if (oldCard && oldCard.description !== newCard.description && newCard.description) {
          // Description added
          animatedCard = { ...newCard, columnId: newCol.id, descriptionUpdated: true };
          setTimeout(() => {
            animatedCard = null;
          }, 500);
          return;
        }
      }
    }
  }

  function handleStateUpdate(event) {
    const { state } = event.detail;
    updateColumnsFromState(state);
  }

  onMount(() => {
    window.addEventListener('demo-state-update', handleStateUpdate);
    // Initialize with demo state
    updateColumnsFromState(getDemoState());
  });

  onDestroy(() => {
    window.removeEventListener('demo-state-update', handleStateUpdate);
  });

  function getCardsByStatus(status) {
    const col = columns.find(c => c.name === status);
    return col ? col.cards : [];
  }

  function getColumnCount(status) {
    return getCardsByStatus(status).length;
  }
</script>

<div class="kanban-board">
  <div class="column">
    <div class="column-header">
      <span class="column-dot todo"></span>
      <span class="column-title">Todo</span>
      <span class="column-count">{getColumnCount('Todo')}</span>
    </div>
    <div class="column-content">
      {#each getCardsByStatus('Todo') as card (card.id)}
        <div
          class="card"
          class:animated={animatedCard?.id === card.id}
          class:move-target={animatedCard?.id === card.id && animatedCard?.columnId === 1}
          class:description-updated={animatedCard?.id === card.id && card.description}
        >
          <div class="card-content">
            <span class="card-id">#{card.id}</span>
            <p class="card-title">{card.title}</p>
            {#if card.description}
              <p class="card-description">{card.description}</p>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>

  <div class="column">
    <div class="column-header">
      <span class="column-dot in-progress"></span>
      <span class="column-title">In Progress</span>
      <span class="column-count">{getColumnCount('In Progress')}</span>
    </div>
    <div class="column-content">
      {#each getCardsByStatus('In Progress') as card (card.id)}
        <div
          class="card"
          class:animated={animatedCard?.id === card.id}
          class:move-source={animatedCard?.id === card.id && animatedCard?.columnId !== 2}
          class:description-updated={animatedCard?.id === card.id && card.description}
        >
          <div class="card-content">
            <span class="card-id">#{card.id}</span>
            <p class="card-title">{card.title}</p>
            {#if card.description}
              <p class="card-description">{card.description}</p>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>

  <div class="column">
    <div class="column-header">
      <span class="column-dot done"></span>
      <span class="column-title">Done</span>
      <span class="column-count">{getColumnCount('Done')}</span>
    </div>
    <div class="column-content">
      {#each getCardsByStatus('Done') as card (card.id)}
        <div class="card done-card">
          <div class="card-content">
            <span class="card-id">#{card.id}</span>
            <p class="card-title">{card.title}</p>
            {#if card.description}
              <p class="card-description">{card.description}</p>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .kanban-board {
    display: flex;
    gap: var(--space-4);
    height: 100%;
    padding: var(--space-5);
    background: var(--color-surface);
    border-radius: var(--radius-xl);
    border: 1px solid var(--color-border);
  }

  .column {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .column-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-1);
    margin-bottom: var(--space-3);
  }

  .column-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .column-dot.todo {
    background: var(--color-muted-foreground);
  }

  .column-dot.in-progress {
    background: var(--color-warning);
    box-shadow: 0 0 8px var(--color-warning);
  }

  .column-dot.done {
    background: var(--color-success);
    box-shadow: 0 0 8px var(--color-success);
  }

  /* Light mode status dots - more vibrant */
  :global(.light) .column-dot.in-progress {
    background: var(--color-warning);
    box-shadow: 0 0 6px color-mix(in srgb, var(--color-warning) 50%, transparent);
  }

  :global(.light) .column-dot.done {
    background: var(--color-success);
    box-shadow: 0 0 6px color-mix(in srgb, var(--color-success) 50%, transparent);
  }

  .column-title {
    font-size: var(--text-sm);
    font-weight: 700;
    color: var(--color-foreground);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    opacity: 0.7;
  }

  .column-count {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
    background: color-mix(in srgb, var(--color-foreground) 5%, transparent);
    padding: 2px 8px;
    border-radius: var(--radius-xl);
  }

  .column-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
  }

  .card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 14px;
    transition: border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
    backdrop-filter: blur(8px);
  }

  .card:hover {
    border-color: var(--color-primary);
    transform: translateY(-2px);
    box-shadow: 0 8px 25px color-mix(in srgb, var(--color-primary) 10%, transparent);
  }

  .card.animated {
    animation: cardAppear 0.3s ease-out;
  }

  .card.move-source {
    animation: cardMoveOut 0.5s ease-in-out forwards;
  }

  .card.move-target {
    animation: cardMoveIn 0.5s ease-in-out forwards;
  }

  .card.description-updated {
    animation: descriptionFlash 0.5s ease-out;
  }

  .card.done-card {
    opacity: 0.6;
  }

  .card-content {
    margin-bottom: var(--space-3);
  }

  .card-id {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
    font-family: var(--font-mono);
  }

  .card-title {
    font-size: var(--text-sm);
    color: var(--color-foreground);
    font-weight: 500;
    margin: 6px 0 0 0;
    line-height: 1.4;
  }

  .card-description {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
    margin: var(--space-2) 0 0 0;
    line-height: 1.4;
    font-style: italic;
  }





  @keyframes cardAppear {
    from {
      opacity: 0;
      transform: translateY(20px) scale(0.95);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  @keyframes cardMoveOut {
    from {
      opacity: 1;
      transform: translateX(0);
    }
    to {
      opacity: 0;
      transform: translateX(100px);
    }
  }

  @keyframes cardMoveIn {
    from {
      opacity: 0;
      transform: translateX(-100px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  @keyframes descriptionFlash {
    from {
      background: color-mix(in srgb, var(--color-primary) 20%, transparent);
    }
    to {
      background: var(--color-surface);
    }
  }

  @media (max-width: 768px) {
    .kanban-board {
      flex-direction: column;
      gap: var(--space-3);
      padding: var(--space-4);
    }

    .column {
      min-height: 100px;
    }

    .card {
      padding: var(--space-3);
    }

    .card-title {
      font-size: var(--text-sm);
    }
  }
</style>
