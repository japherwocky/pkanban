<script>
  import { api } from './api.js';
  import Modal from './Modal.svelte';
  import ShareModal from './ShareModal.svelte';
  import Comments from './Comments.svelte';
  import { dndzone } from 'svelte-dnd-action';
  import { createBoardDnd } from './boardDnd.js';

  let { board, onBack, availableTeams = [], onShare, onRename, initialCardId = null } = $props();

  let columns = $state([]);
  let loading = $state(false);
  let showCreateCardModal = $state(false);
  let selectedColumnId = $state(null);
  let newCardTitle = $state('');
  let newCardDescription = $state('');
  let createLoading = $state(false);
  let showEditCardModal = $state(false);
  let editingCard = $state(null);
  let editTitle = $state('');
  let editDescription = $state('');
  let editLoading = $state(false);
  let showCreateColumnModal = $state(false);
  let newColumnName = $state('');
  let createColumnLoading = $state(false);
  let showShareModal = $state(false);
  let showRenameBoardModal = $state(false);
  let renameBoardName = $state('');
  let renameLoading = $state(false);

  // Get current user's id from token
  let currentUserId = $state(null);
  try {
    const token = localStorage.getItem('token');
    if (token) {
      const tokenData = JSON.parse(atob(token.split('.')[1]));
      currentUserId = tokenData.sub;
    }
  } catch (e) {
    console.error('Failed to decode token:', e);
  }

  function isBoardOwner() {
    return board?.owner_id && String(board.owner_id) === String(currentUserId);
  }

  async function loadBoard() {
    loading = true;
    try {
      const data = await api.boards.get(board.id);
      columns = data.columns || [];
    } catch (e) {
      console.error('Failed to load board:', e);
    } finally {
      loading = false;
    }
  }

  async function createCard() {
    if (!newCardTitle.trim() || !selectedColumnId) return;
    createLoading = true;
    try {
      // Find the column to get current card count for position
      const column = columns.find(c => c.id === selectedColumnId);
      const position = column ? column.cards.length : 0;

      const card = await api.cards.create(
        selectedColumnId,
        newCardTitle.trim(),
        position,
        newCardDescription.trim() || null
      );
      columns = columns.map(col => {
        if (col.id === selectedColumnId) {
          return { ...col, cards: [...col.cards, card] };
        }
        return col;
      });
      newCardTitle = '';
      newCardDescription = '';
      showCreateCardModal = false;
    } catch (e) {
      alert('Failed to create card: ' + e.message);
    } finally {
      createLoading = false;
    }
  }

  async function deleteCard(columnId, cardId, e) {
    e.stopPropagation();
    if (!confirm('Delete this card?')) return;
    try {
      await api.cards.delete(cardId);
      columns = columns.map(col => {
        if (col.id === columnId) {
          return { ...col, cards: col.cards.filter(c => c.id !== cardId) };
        }
        return col;
      });
    } catch (e) {
      alert('Failed to delete card: ' + e.message);
    }
  }

  function openRenameBoard() {
    renameBoardName = board.name;
    showRenameBoardModal = true;
  }

  async function saveRenameBoard() {
    const name = renameBoardName.trim();
    if (!name || name === board.name) {
      showRenameBoardModal = false;
      return;
    }
    renameLoading = true;
    try {
      await onRename(name);
      showRenameBoardModal = false;
    } catch (e) {
      alert('Failed to rename board: ' + e.message);
    } finally {
      renameLoading = false;
    }
  }

  function openCreateCard(columnId) {
    selectedColumnId = columnId;
    newCardTitle = '';
    newCardDescription = '';
    showCreateCardModal = true;
  }

  function cardUrl(cardId) {
    return `/boards/${board.id}/card/${cardId}`;
  }

  function openEditCard(card, { updateUrl = true } = {}) {
    editingCard = card;
    editTitle = card.title || '';
    editDescription = card.description || '';
    showEditCardModal = true;
    if (updateUrl) {
      history.replaceState(history.state, '', cardUrl(card.id));
    }
  }

  function closeEditCard() {
    showEditCardModal = false;
    editingCard = null;
    history.replaceState(history.state, '', `/boards/${board.id}`);
  }

  // Deep-link support: open the card named in the URL once the board has loaded.
  let didOpenInitialCard = $state(false);
  $effect(() => {
    if (didOpenInitialCard || !initialCardId || columns.length === 0) return;
    didOpenInitialCard = true;
    const card = columns.flatMap(col => col.cards).find(c => String(c.id) === String(initialCardId));
    if (card) {
      openEditCard(card, { updateUrl: false });
    }
  });

  async function saveCard() {
    if (!editTitle.trim() || !editingCard) return;
    editLoading = true;
    try {
      await api.cards.update(editingCard.id, editTitle.trim(), editDescription.trim() || null, null, null);
      columns = columns.map(col => ({
        ...col,
        cards: col.cards.map(c =>
          c.id === editingCard.id
            ? { ...c, title: editTitle.trim(), description: editDescription.trim() }
            : c
        )
      }));
      closeEditCard();
    } catch (e) {
      alert('Failed to update card: ' + e.message);
    } finally {
      editLoading = false;
    }
  }

  function handleCommentsUpdate(cardId, updatedComments) {
    // Update the comments in the local state
    columns = columns.map(col => ({
      ...col,
      cards: col.cards.map(card =>
        card.id === cardId
          ? { ...card, comments: updatedComments }
          : card
      )
    }));
    
    // Also update the editing card if it's the same card
    if (editingCard && editingCard.id === cardId) {
      editingCard = { ...editingCard, comments: updatedComments };
    }
  }

  async function createColumn() {
    if (!newColumnName.trim()) return;
    createColumnLoading = true;
    try {
      const column = await api.columns.create(board.id, newColumnName.trim(), columns.length);
      columns = [...columns, { ...column, cards: [] }];
      newColumnName = '';
      showCreateColumnModal = false;
    } catch (e) {
      alert('Failed to create column: ' + e.message);
    } finally {
      createColumnLoading = false;
    }
  }

  async function deleteColumn(columnId, columnName) {
    if (!confirm(`Delete column "${columnName}" and all its cards?`)) return;
    try {
      await api.columns.delete(columnId);
      columns = columns.filter(col => col.id !== columnId);
    } catch (e) {
      alert('Failed to delete column: ' + e.message);
    }
  }

  // Drag-and-drop lives in boardDnd.js so its cross-column and rollback
  // behaviour can be tested without driving a real drag. See boardDnd.test.js.
  const dnd = createBoardDnd({
    getColumns: () => columns,
    setColumns: (next) => { columns = next; },
    api,
    reload: loadBoard,
  });

  // Sync columns with board changes
  $effect(() => {
    if (board?.columns) {
      columns = [...board.columns];
    }
  });

  function formatDate(dateStr) {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  }
</script>

<div class="board-view">
  <header>
    <div class="header-left">
      <button class="back-btn" onclick={onBack}>
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M12 4L6 10L12 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Back
      </button>
      {#if isBoardOwner()}
        <button class="board-title-btn" onclick={openRenameBoard} title="Rename board">
          <h1>{board.name}</h1>
          <svg class="rename-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M11.5 2.5L13.5 4.5L5 13H3V11L11.5 2.5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
        </button>
      {:else}
        <h1>{board.name}</h1>
      {/if}
    </div>
    <div class="header-actions">
      {#if isBoardOwner()}
        {#if availableTeams.length > 0}
          <button class="share-btn" onclick={() => showShareModal = true}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 3C8.44772 3 8 3.44772 8 4V8H4C3.44772 8 3 8.44772 3 9V10C3 10.6569 4.34315 12 6 12H8V14C8 14.5523 8.44772 15 9 15H9.5C10.0523 15 10.5 14.5523 10.5 14V12H12C13.6569 12 15 10.6569 15 9V8H10.5V4C10.5 3.44772 10.0523 3 9.5 3H9ZM4.5 9C4.5 8.72386 4.72386 8.5 5 8.5H6.5V9H4.5V9ZM12 9V9.5H13.5V9C13.5 8.72386 13.2761 8.5 13 8.5H12V9Z" stroke="currentColor" stroke-width="1.5"/>
            </svg>
            Share
          </button>
        {:else}
          <button class="share-btn disabled" title="Create an organization to share boards">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 3C8.44772 3 8 3.44772 8 4V8H4C3.44772 8 3 8.44772 3 9V10C3 10.6569 4.34315 12 6 12H8V14C8 14.5523 8.44772 15 9 15H9.5C10.0523 15 10.5 14.5523 10.5 14V12H12C13.6569 12 15 10.6569 15 9V8H10.5V4C10.5 3.44772 10.0523 3 9.5 3H9ZM4.5 9C4.5 8.72386 4.72386 8.5 5 8.5H6.5V9H4.5V9ZM12 9V9.5H13.5V9C13.5 8.72386 13.2761 8.5 13 8.5H12V9Z" stroke="currentColor" stroke-width="1.5"/>
            </svg>
            Share
          </button>
        {/if}
      {/if}
      <span class="card-count">{columns.reduce((sum, col) => sum + col.cards.length, 0)} cards</span>
    </div>
  </header>

  {#if loading}
    <div class="loading">Loading board...</div>
  {:else}
    <div class="columns-container"
      use:dndzone={{ items: columns, flipDurationMs: 200 }}
      onconsider={dnd.considerColumns}
      onfinalize={dnd.finalizeColumns}
    >
      {#each columns as column (column.id)}
        <div
          class="column"
          draggable="true"
        >
          <div class="column-header">
            <h3>{column.name}</h3>
            <div class="column-actions">
              <span class="card-count">{column.cards.length}</span>
              {#if isBoardOwner()}
                <button class="column-delete-btn" onclick={() => deleteColumn(column.id, column.name)} title="Delete column">×</button>
              {/if}
            </div>
          </div>
          <div class="column-content">
            {#if column.cards.length > 0}
              <div
                class="cards-list"
                use:dndzone={{ items: column.cards, flipDurationMs: 200 }}
                onconsider={(e) => dnd.considerCards(column.id, e)}
                onfinalize={(e) => dnd.finalizeCards(column.id, e)}
              >
                {#each column.cards as card (card.id)}
                  <div
                    class="card"
                    draggable="true"
                    onclick={() => openEditCard(card)}
                    onkeydown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        openEditCard(card);
                      }
                    }}
                    role="button"
                    tabindex="0"
                    aria-label={card.description ? `Edit card: ${card.title}. ${card.description}` : `Edit card: ${card.title}`}
                  >
                    <div class="card-header">
                      <span class="card-title"><span class="card-id">#{card.id}</span> {card.title}</span>
                      <button class="delete-btn" onclick={(e) => deleteCard(column.id, card.id, e)}>×</button>
                    </div>
                    {#if card.description}
                      <p class="card-description">{card.description}</p>
                    {/if}
                    <div class="card-meta">
                      {#if card.created_at}
                        <span>{formatDate(card.created_at)}</span>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {:else}
              <div class="empty-column">No cards</div>
            {/if}
          </div>
          <button class="add-card-btn" onclick={() => openCreateCard(column.id)}>
            <span>+</span> Add card
          </button>
        </div>
      {/each}
      <button class="add-column-btn" onclick={() => { newColumnName = ''; showCreateColumnModal = true; }}>
        <span>+</span> Add Column
      </button>
    </div>
  {/if}

    {#if showRenameBoardModal}
      <Modal open={showRenameBoardModal} onClose={() => showRenameBoardModal = false} title="Rename Board">
        {#snippet children()}
          <form onsubmit={(e) => { e.preventDefault(); saveRenameBoard(); }}>
            <!-- svelte-ignore a11y_autofocus -->
            <input
              bind:value={renameBoardName}
              placeholder="Board name"
              autofocus
              required
            />
            <div class="modal-actions">
              <button type="button" class="cancel-btn" onclick={() => showRenameBoardModal = false}>Cancel</button>
              <button type="submit" class="create-btn" disabled={renameLoading}>
                {renameLoading ? 'Saving...' : 'Save'}
              </button>
            </div>
          </form>
        {/snippet}
      </Modal>
    {/if}

    {#if showCreateCardModal}
      <Modal open={showCreateCardModal} onClose={() => showCreateCardModal = false} title="Add Card" wide>
        {#snippet children()}
          <form onsubmit={(e) => { e.preventDefault(); createCard(); }}>
            <input
              bind:value={newCardTitle}
              placeholder="Card title"
              required
            />
            <div class="grow-wrap" data-replicated-value={newCardDescription}>
              <textarea
                bind:value={newCardDescription}
                placeholder="Description (optional)"
              ></textarea>
            </div>
            <div class="modal-actions">
              <button type="button" class="cancel-btn" onclick={() => showCreateCardModal = false}>Cancel</button>
              <button type="submit" class="create-btn" disabled={createLoading}>
                {createLoading ? 'Adding...' : 'Add Card'}
              </button>
            </div>
          </form>
        {/snippet}
      </Modal>
    {/if}

    {#if showEditCardModal}
      <Modal open={showEditCardModal} onClose={closeEditCard} title="Edit Card" titleBadge={`#${editingCard?.id}`} wide>
        {#snippet children()}
          <form onsubmit={(e) => { e.preventDefault(); saveCard(); }}>
            <input
              bind:value={editTitle}
              placeholder="Card title"
              required
            />
            <div class="grow-wrap" data-replicated-value={editDescription}>
              <textarea
                bind:value={editDescription}
                placeholder="Description (optional)"
              ></textarea>
            </div>
            <div class="modal-actions">
              <button type="button" class="cancel-btn" onclick={closeEditCard}>Cancel</button>
              <button type="submit" class="create-btn" disabled={editLoading}>
                {editLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
          
          {#if editingCard}
            <Comments 
              card={editingCard} 
              onCommentsUpdate={handleCommentsUpdate}
            />
          {/if}
        {/snippet}
      </Modal>
    {/if}

    {#if showCreateColumnModal}
      <Modal open={showCreateColumnModal} onClose={() => showCreateColumnModal = false} title="Add Column">
        {#snippet children()}
          <form onsubmit={(e) => { e.preventDefault(); createColumn(); }}>
            <input
              bind:value={newColumnName}
              placeholder="Column name"
              required
            />
            <div class="modal-actions">
              <button type="button" class="cancel-btn" onclick={() => showCreateColumnModal = false}>Cancel</button>
              <button type="submit" class="create-btn" disabled={createColumnLoading}>
                {createColumnLoading ? 'Adding...' : 'Add Column'}
              </button>
            </div>
          </form>
        {/snippet}
      </Modal>
    {/if}

    {#if showShareModal}
      <ShareModal
        open={showShareModal}
        onClose={() => showShareModal = false}
        {board}
        availableTeams={availableTeams}
        onShare={onShare}
      />
    {/if}
  </div>

  <style>
  .board-view {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4) var(--space-6);
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .back-btn {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
    font-size: var(--text-sm);
  }

  .back-btn:hover {
    background: var(--color-muted);
  }

  header h1 {
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--color-foreground);
    margin: 0;
  }

  .board-title-btn {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    margin-left: -0.5rem;
    background: none;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    color: var(--color-foreground);
    transition: background var(--transition-fast);
  }

  .board-title-btn:hover {
    background: var(--color-muted);
  }

  .rename-icon {
    opacity: 0;
    color: var(--color-muted-foreground);
    transition: opacity var(--transition-fast);
  }

  .board-title-btn:hover .rename-icon,
  .board-title-btn:focus-visible .rename-icon {
    opacity: 1;
  }

  .card-count {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
  }

  .share-btn {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
    font-size: var(--text-sm);
  }

  .share-btn:hover {
    background: var(--color-muted);
    border-color: var(--color-primary);
  }

  .share-btn.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .share-btn.disabled:hover {
    background: transparent;
    border-color: var(--color-border);
  }

  .loading {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-muted-foreground);
  }

  .columns-container {
    flex: 1;
    display: flex;
    gap: var(--space-4);
    padding: var(--space-6);
    overflow-x: auto;
    min-height: 0;
  }

  .column {
    flex: 0 0 300px;
    display: flex;
    flex-direction: column;
    background: var(--color-muted);
    border-radius: var(--radius-xl);
    max-height: 100%;
  }

  .column-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4);
    border-bottom: 1px solid var(--color-border);
  }

  .column-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .column-delete-btn {
    padding: 0.125rem 0.375rem;
    font-size: var(--text-base);
    line-height: 1;
    background: transparent;
    color: var(--color-muted-foreground);
    border: none;
    opacity: 0;
    transition: opacity var(--transition-fast);
  }

  .column:hover .column-delete-btn {
    opacity: 1;
  }

  .column-delete-btn:hover {
    color: var(--color-destructive);
    background: transparent;
  }

  .column-header h3 {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-foreground);
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .column-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-3);
    min-height: 100px;
  }

  .cards-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-height: 50px;
  }

  .card {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-3);
    cursor: grab;
    transition: border-color var(--transition-fast);
  }

  .card:hover {
    border-color: var(--color-primary);
  }

  .card:active {
    cursor: grabbing;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: var(--space-2);
  }

  .card-title {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-foreground);
    word-break: break-word;
  }

  .card-id {
    font-size: var(--text-sm);
    font-weight: 400;
    color: var(--color-muted-foreground);
  }

  .delete-btn {
    padding: 0.125rem 0.375rem;
    font-size: var(--text-base);
    line-height: 1;
    background: transparent;
    color: var(--color-muted-foreground);
    border: none;
    opacity: 0;
    transition: opacity var(--transition-fast);
  }

  .card:hover .delete-btn {
    opacity: 1;
  }

  .delete-btn:hover {
    color: var(--color-destructive);
    background: transparent;
  }

  .card-description {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: var(--space-2) 0 0 0;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    overflow: hidden;
    word-break: break-word;
  }

  .card-meta {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
    margin-top: var(--space-2);
  }

  .empty-column {
    text-align: center;
    padding: var(--space-8) var(--space-4);
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
  }

  .add-card-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-3);
    background: transparent;
    color: var(--color-muted-foreground);
    border: none;
    border-top: 1px solid var(--color-border);
    font-size: var(--text-sm);
    transition: background-color var(--transition-fast), color var(--transition-fast);
  }

  .add-card-btn:hover {
    background: var(--color-muted);
    color: var(--color-foreground);
  }

  .add-card-btn span {
    font-size: var(--text-xl);
    font-weight: 300;
  }

  .add-column-btn {
    flex: 0 0 300px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-4);
    background: transparent;
    color: var(--color-muted-foreground);
    border: 2px dashed var(--color-border);
    border-radius: var(--radius-xl);
    font-size: var(--text-sm);
    font-weight: 500;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
    height: fit-content;
  }

  .add-column-btn:hover {
    border-color: var(--color-primary);
    color: var(--color-primary);
    background: var(--color-card);
  }

  .add-column-btn span {
    font-size: var(--text-2xl);
    font-weight: 300;
  }

  input {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    border-radius: var(--radius-lg);
    border: 1px solid var(--color-border);
    background: var(--color-card);
    color: var(--color-foreground);
  }

  input:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary);
  }

  /* CSS-only autosizing textarea. The invisible ::after replica and the
     textarea occupy the same grid cell, so the cell -- and the textarea --
     grow to fit the content instead of the textarea scrolling internally.
     No JS: the replica's content comes from data-replicated-value, which
     Svelte keeps in sync with the bound value on every keystroke. */
  .grow-wrap {
    display: grid;
  }

  .grow-wrap::after {
    content: attr(data-replicated-value) ' ';
    white-space: pre-wrap;
    visibility: hidden;
  }

  .grow-wrap > textarea,
  .grow-wrap::after {
    grid-area: 1 / 1 / 2 / 2;
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    font-family: inherit;
    border-radius: var(--radius-lg);
    min-height: 80px;
  }

  textarea {
    border: 1px solid var(--color-border);
    background: var(--color-card);
    color: var(--color-foreground);
    /* Grows via the grid cell above instead; a resize handle or an internal
       scrollbar would fight that -- and disabling scroll here, not just
       hiding it, is what lets a wheel over the field scroll the modal. */
    resize: none;
    overflow: hidden;
  }

  textarea:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary);
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    margin-top: var(--space-2);
  }

  button {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    font-weight: 500;
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast), box-shadow var(--transition-fast);
  }

  .cancel-btn {
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
  }

  .cancel-btn:hover {
    background: var(--color-muted);
  }

  .create-btn {
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: none;
  }

  .create-btn:hover {
    opacity: 0.9;
  }

  .create-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
