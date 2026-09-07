<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import Modal from '../lib/Modal.svelte';

  let boards = $state([]);
  let boardsLoading = $state(false);
  let users = $state([]);
  let showCreateBoardModal = $state(false);
  let showEditBoardModal = $state(false);
  let selectedBoard = $state(null);
  let newBoardName = $state('');
  let newBoardOwnerId = $state('');
  let editBoardName = $state('');

  onMount(async () => {
    await Promise.all([loadBoards(), loadUsers()]);
  });

  async function loadBoards() {
    boardsLoading = true;
    try {
      boards = await api.admin.boards.list();
    } catch (e) {
      console.error('Failed to load boards:', e);
      alert('Failed to load boards: ' + e.message);
    } finally {
      boardsLoading = false;
    }
  }

  async function loadUsers() {
    try {
      users = await api.admin.users.list();
    } catch (e) {
      console.error('Failed to load users:', e);
    }
  }

  function getUsernameById(userId) {
    const user = users.find(u => u.id === userId);
    return user?.username || 'Unknown';
  }

  async function createBoard() {
    if (!newBoardName.trim() || !newBoardOwnerId) return;

    try {
      await api.admin.boards.create({
        name: newBoardName.trim(),
        owner_id: parseInt(newBoardOwnerId),
      });
      newBoardName = '';
      newBoardOwnerId = '';
      showCreateBoardModal = false;
      await loadBoards();
    } catch (e) {
      alert('Failed to create board: ' + e.message);
    }
  }

  function openEditBoard(board) {
    selectedBoard = board;
    editBoardName = board.name;
    showEditBoardModal = true;
  }

  async function updateBoard() {
    if (!selectedBoard) return;

    try {
      await api.admin.boards.update(selectedBoard.id, {
        name: editBoardName.trim(),
      });
      showEditBoardModal = false;
      selectedBoard = null;
      await loadBoards();
    } catch (e) {
      alert('Failed to update board: ' + e.message);
    }
  }

  async function deleteBoard(boardId) {
    if (!confirm('Are you sure you want to delete this board? This will delete all columns and cards. This action cannot be undone.')) return;

    try {
      await api.admin.boards.delete(boardId);
      boards = boards.filter(b => b.id !== boardId);
    } catch (e) {
      alert('Failed to delete board: ' + e.message);
    }
  }

  function getSharingInfo(board) {
    if (board.is_public_to_org) {
      return '<span class="badge public-badge">Public to Org</span>';
    }
    if (board.shared_team_name) {
      return `<span class="badge shared-badge">Shared: ${board.shared_team_name}</span>`;
    }
    return '<span class="badge private-badge">Private</span>';
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }
</script>

<div class="tab-header">
  <h2>Boards</h2>
  <button class="create-btn" onclick={() => showCreateBoardModal = true}>New Board</button>
</div>

{#if boardsLoading}
  <div class="loading">Loading boards...</div>
{:else if boards.length === 0}
  <div class="empty-state">No boards found</div>
{:else}
  <div class="boards-grid">
    {#each boards as board (board.id)}
      <div class="board-card">
        <div class="board-info">
          <h3>{board.name}</h3>
          <p class="owner-badge">Owner: {board.owner_username}</p>
        </div>
        <div class="board-stats">
          <div class="stat">
            <span class="stat-value">{board.column_count}</span>
            <span class="stat-label">Columns</span>
          </div>
          <div class="stat">
            <span class="stat-value">{board.card_count}</span>
            <span class="stat-label">Cards</span>
          </div>
        </div>
        <div class="board-meta">
          <div class="sharing-info">
            {@html getSharingInfo(board)}
          </div>
          <div class="created-date">
            Created {formatDate(board.created_at)}
          </div>
        </div>
        <div class="board-actions">
          <button class="action-btn" onclick={() => openEditBoard(board)}>Edit</button>
          <button class="action-btn delete" onclick={() => deleteBoard(board.id)}>Delete</button>
        </div>
      </div>
    {/each}
  </div>
{/if}

{#if showCreateBoardModal}
  <Modal open={showCreateBoardModal} onClose={() => showCreateBoardModal = false} title="Create New Board">
    {#snippet children()}
      <form onsubmit={(e) => { e.preventDefault(); createBoard(); }}>
        <label>
          Name
          <input
            type="text"
            bind:value={newBoardName}
            placeholder="Enter board name"
            required
          />
        </label>
        <label>
          Owner
          <select bind:value={newBoardOwnerId} required>
            <option value="">Select owner...</option>
            {#each users as user}
              <option value={user.id}>{user.username}</option>
            {/each}
          </select>
        </label>
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showCreateBoardModal = false}>Cancel</button>
          <button type="submit" class="create-btn">Create Board</button>
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

{#if showEditBoardModal}
  <Modal open={showEditBoardModal} onClose={() => showEditBoardModal = false} title={selectedBoard?.name ? `Edit Board: ${selectedBoard.name}` : 'Edit Board'}>
    {#snippet children()}
      <form onsubmit={(e) => { e.preventDefault(); updateBoard(); }}>
        <label>
          Name
          <input
            type="text"
            bind:value={editBoardName}
            placeholder="Enter board name"
            required
          />
        </label>
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showEditBoardModal = false}>Cancel</button>
          <button type="submit" class="create-btn">Save Changes</button>
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

<style>
  .loading, .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-16) var(--space-8);
    text-align: center;
    color: var(--color-muted-foreground);
  }

  .tab-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-8);
  }

  .tab-header h2 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0;
  }

  .create-btn {
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: none;
  }

  .create-btn:hover {
    opacity: 0.9;
  }

  .boards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: var(--space-4);
  }

  .board-card {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--space-5);
  }

  .board-info h3 {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-1) 0;
  }

  .board-info .owner-badge {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0;
  }

  .board-stats {
    display: flex;
    gap: var(--space-6);
    margin: var(--space-4) 0;
  }

  .stat {
    display: flex;
    flex-direction: column;
  }

  .stat-value {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-primary);
  }

  .stat-label {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .board-meta {
    margin: var(--space-3) 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .sharing-info {
    display: flex;
    gap: var(--space-2);
  }

  .badge {
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    font-weight: 700;
    border-radius: var(--radius-md);
  }

  .public-badge {
    background: var(--color-primary);
    color: var(--color-primary-foreground);
  }

  .shared-badge {
    background: var(--color-muted);
    color: var(--color-foreground);
  }

  .private-badge {
    background: var(--color-border);
    color: var(--color-muted-foreground);
  }

  .created-date {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
  }

  .board-actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-4);
  }

  .action-btn {
    flex: 1;
    padding: var(--space-2);
    font-size: var(--text-sm);
    background: var(--color-muted);
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .action-btn:hover {
    background: var(--color-border);
  }

  .action-btn.delete {
    color: var(--color-destructive);
    border-color: var(--color-destructive);
  }

  .action-btn.delete:hover {
    background: var(--color-destructive);
    color: var(--color-destructive-foreground);
  }

  form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-foreground);
  }

  select, input {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    border-radius: var(--radius-lg);
    border: 1px solid var(--color-border);
    background: var(--color-card);
    color: var(--color-foreground);
    transition: border-color var(--transition-fast);
    width: 100%;
  }

  select:focus, input:focus {
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

  .cancel-btn {
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
  }

  .cancel-btn:hover {
    background: var(--color-muted);
  }

  button {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    font-weight: 500;
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast), box-shadow var(--transition-fast);
  }
</style>
