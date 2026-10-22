<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import BoardView from '../lib/BoardView.svelte';
  import { api } from '../lib/api.js';

  let { params } = $props();

  let board = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let availableTeams = $state([]);
  let availableOrgs = $state([]);

  onMount(async () => {

    try {
      loading = true;
      const [loadedBoard, shareTargets] = await Promise.all([
        api.boards.get(params.id),
        loadShareTargets()
      ]);
      board = loadedBoard;
      availableTeams = shareTargets.teams;
      availableOrgs = shareTargets.orgs;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  // Orgs as well as teams: a board can be shared with a whole organization,
  // and that is possible with no teams defined at all. Gating the share UI on
  // teams alone hid the option entirely for a brand new org.
  async function loadShareTargets() {
    try {
      // Teams the server will let this user share with: their own (with or
      // without an org) and every team in their orgs.
      const [teams, orgs] = await Promise.all([api.me.teams(), api.organizations.list()]);
      return { teams, orgs };
    } catch (e) {
      console.error('Failed to load share targets:', e);
      return { teams: [], orgs: [] };
    }
  }

  function goBack() {
    navigate('/boards');
  }

  // Each sharing change reloads the board, so the dialog shows what the
  // server now holds rather than what it was asked for.
  const sharing = {
    setTeam: async (teamId, permission) => {
      await api.boards.teams.set(board.id, teamId, permission);
      board = await api.boards.get(board.id);
    },
    removeTeam: async (teamId) => {
      await api.boards.teams.remove(board.id, teamId);
      board = await api.boards.get(board.id);
    },
    shareOrg: async (isPublicToOrg, organizationId, orgPermission) => {
      await api.boards.shareWithOrg(board.id, isPublicToOrg, organizationId, orgPermission);
      board = await api.boards.get(board.id);
    },
  };

  async function handleRename(name) {
    const updated = await api.boards.update(board.id, name);
    board = { ...board, name: updated.name };
  }
</script>

{#if loading}
  <div class="loading">Loading board...</div>
{:else if error}
  <div class="error">
    <p>{error}</p>
    <button onclick={goBack}>Back to Boards</button>
  </div>
 {:else if board}
  <BoardView board={board} onBack={goBack} availableTeams={availableTeams} availableOrgs={availableOrgs} {sharing} onRename={handleRename} initialCardId={params.cardId} />
 {/if}

<style>
  .loading, .error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    gap: var(--space-4);
    text-align: center;
  }

  .loading {
    color: var(--color-muted-foreground);
  }

  .error {
    padding: var(--space-8);
  }

  .error p {
    color: var(--color-destructive);
  }

  button {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    font-weight: 500;
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast), box-shadow var(--transition-fast);
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: none;
  }

  button:hover {
    opacity: 0.9;
  }
</style>
