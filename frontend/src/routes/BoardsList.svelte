<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import ThemeToggle from '../lib/ThemeToggle.svelte';
  import Logo from '../lib/Logo.svelte';
  import { api } from '../lib/api.js';
  import Modal from '../lib/Modal.svelte';

  let boards = $state([]);
  let boardsLoading = $state(false);
  let showCreateModal = $state(false);
  let newBoardName = $state('');
  let createLoading = $state(false);
  let teamsMap = $state({}); // Map team_id -> team object
  let isAdmin = $state(false);

  onMount(async () => {
    await Promise.all([loadBoards(), loadTeams(), loadAdminStatus()]);
  });

  function logout() {
    localStorage.removeItem('token');
    navigate('/login');
  }

  async function loadBoards() {
    boardsLoading = true;
    try {
      boards = await api.boards.list();
    } catch (e) {
      console.error('Failed to load boards:', e);
    } finally {
      boardsLoading = false;
    }
  }

  async function loadTeams() {
    try {
      const teams = [];
      const orgs = await api.organizations.list();

      for (const org of orgs) {
        const orgTeams = await api.organizations.teams.list(org.id);
        for (const team of orgTeams) {
          teams[team.id] = team;
        }
      }

      teamsMap = teams;
    } catch (e) {
      console.error('Failed to load teams:', e);
    }
  }

  async function loadAdminStatus() {
    try {
      const status = await api.admin.status();
      isAdmin = status.is_admin;
    } catch (e) {
      console.error('Failed to load admin status:', e);
      isAdmin = false;
    }
  }

  function getTeamName(teamId) {
    return teamsMap[teamId]?.name || null;
  }

  async function createBoard() {
    if (!newBoardName.trim()) return;
    createLoading = true;
    try {
      const board = await api.boards.create(newBoardName.trim());
      boards = [...boards, board];
      newBoardName = '';
      showCreateModal = false;
    } catch (e) {
      alert('Failed to create board: ' + e.message);
    } finally {
      createLoading = false;
    }
  }

  async function deleteBoard(id, e) {
    e.stopPropagation();
    if (!confirm('Delete this board?')) return;
    try {
      await api.boards.delete(id);
      boards = boards.filter(b => b.id !== id);
    } catch (e) {
      alert('Failed to delete board: ' + e.message);
    }
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }
</script>

<div class="app">
<header>
    <a href="/" class="logo-link">
      <Logo />
    </a>
    <div class="header-actions">
      <button class="nav-btn" onclick={() => navigate('/organizations')}>Organizations</button>
      {#if isAdmin}
        <button class="nav-btn admin-btn" onclick={() => navigate('/admin')}>Admin</button>
      {/if}
      <ThemeToggle />
      <button class="logout-btn" onclick={logout}>Logout</button>
    </div>
  </header>

  {#if boardsLoading}
    <div class="loading">Loading boards...</div>
  {:else if boards.length === 0}
    <div class="empty-state">
      <p>No boards yet</p>
      <button class="create-btn" onclick={() => showCreateModal = true}>Create your first board</button>
    </div>
  {:else}
    <div class="boards-grid">
      {#each boards as board (board.id)}
        <div class="board-card" class:shared={board.shared_team_id}>
          <button class="card-content" onclick={() => navigate(`/boards/${board.id}`)}>
            <div class="board-header">
              <h3>{board.name}</h3>
            </div>
            <div class="board-meta">
              <span>Created {formatDate(board.created_at)}</span>
              {#if board.shared_team_id}
                <span class="shared-badge">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 2C6.44772 2 6 2.44772 6 3V5H4C3.44772 5 3 5.44772 3 6V7C3 7.55228 4.44772 9 6 9H6V10C6 10.5523 6.44772 11 7 11H7.5C8.05228 11 8.5 10.5523 8.5 10V9H10C11.5523 9 13 7.55228 13 6V5H8.5V3C8.5 2.44772 8.05228 2 7.5 2H7ZM4.5 6C4.5 5.72386 4.72386 5.5 5 5.5H6.5V6H4.5V6ZM10 6V6.5H11.5V6C11.5 5.72386 11.2761 5.5 11 5.5H10V6Z" stroke="currentColor" stroke-width="1"/>
                  </svg>
                  {getTeamName(board.shared_team_id)}
                </span>
              {/if}
            </div>
          </button>
          <button class="delete-btn" onclick={(e) => deleteBoard(board.id, e)} title="Delete board">×</button>
        </div>
      {/each}
      <button class="board-card create-card" onclick={() => showCreateModal = true}>
        <span class="plus">+</span>
        <span>New Board</span>
      </button>
    </div>
  {/if}
</div>

{#if showCreateModal}
  <Modal open={showCreateModal} onClose={() => showCreateModal = false} title="Create New Board">
    {#snippet children()}
      <form onsubmit={(e) => { e.preventDefault(); createBoard(); }}>
        <input
          bind:value={newBoardName}
          placeholder="Board name"
          required
        />
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showCreateModal = false}>Cancel</button>
          <button type="submit" class="create-btn" disabled={createLoading}>
            {createLoading ? 'Creating...' : 'Create Board'}
          </button>
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

<style>
  .app {
    padding: var(--space-6);
    max-width: 1200px;
    margin: 0 auto;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-8);
    border: 2px solid var(--color-border);
    padding: var(--space-4) var(--space-6);
  }

  .logo-link {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    text-decoration: none;
    color: inherit;
  }

  .logo-link:hover {
    opacity: 0.8;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .nav-btn {
    padding: var(--space-2) var(--space-4);
    background: transparent;
    color: var(--color-foreground);
    border: 2px solid var(--color-border);
    text-decoration: none;
    font-size: var(--text-sm);
  }

  .nav-btn:hover {
    background: var(--color-muted);
  }

  .nav-btn.admin-btn {
    color: var(--color-destructive);
    border-color: var(--color-destructive);
  }

  .nav-btn.admin-btn:hover {
    background: var(--color-destructive);
    color: var(--color-destructive-foreground);
  }

  .logout-btn {
    padding: var(--space-2) var(--space-4);
    background: var(--color-muted);
    color: var(--color-foreground);
    border: 2px solid var(--color-border);
  }

  .logout-btn:hover {
    background: var(--color-border);
  }

  .loading {
    text-align: center;
    padding: var(--space-12);
    color: var(--color-muted-foreground);
  }

  .empty-state {
    text-align: center;
    padding: var(--space-16) var(--space-8);
    color: var(--color-muted-foreground);
  }

  .empty-state p {
    margin-bottom: var(--space-6);
    font-size: var(--text-lg);
  }

  .boards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-4);
  }

  .board-card {
    display: flex;
    flex-direction: row;
    padding: 0;
    background: var(--color-card);
    border: 2px solid var(--color-border);
    cursor: pointer;
    transition: border-color var(--transition-fast);
    text-align: left;
    position: relative;
  }

  .board-card:hover {
    border-color: var(--color-primary);
  }

  .board-card.shared {
    border-left: 4px solid var(--color-primary);
  }

  .card-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: var(--space-5);
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
  }

  .card-content:hover {
    background: var(--color-muted);
  }

  .board-header {
    display: flex;
    justify-content: flex-start;
    align-items: flex-start;
    margin-bottom: var(--space-2);
  }

  .board-header h3 {
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--color-foreground);
    margin: 0;
  }

  .delete-btn {
    position: absolute;
    top: 0.75rem;
    right: 0.75rem;
    padding: 0.125rem 0.375rem;
    font-size: var(--text-base);
    line-height: 1;
    background: transparent;
    color: var(--color-muted-foreground);
    border: none;
    opacity: 0;
    transition: opacity var(--transition-fast);
    cursor: pointer;
    z-index: 1;
  }

  .board-card:hover .delete-btn {
    opacity: 1;
  }

  .delete-btn:hover {
    color: var(--color-destructive);
    background: transparent;
  }

  .board-meta {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .shared-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    color: var(--color-primary);
    font-size: var(--text-xs);
    font-weight: 500;
  }

  .create-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    min-height: 120px;
    border: 2px dashed var(--color-border);
    background: transparent;
    color: var(--color-muted-foreground);
  }

  .create-card:hover {
    border-color: var(--color-primary);
    color: var(--color-primary);
    background: var(--color-card);
  }

  .create-card .plus {
    font-size: var(--text-3xl);
    font-weight: 300;
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

  input {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    border-radius: var(--radius-lg);
    border: 1px solid var(--color-border);
    background: var(--color-card);
    color: var(--color-foreground);
    transition: border-color var(--transition-fast);
    width: 100%;
  }

  input:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary);
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
