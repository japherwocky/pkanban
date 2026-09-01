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
      const teams = [];
      const orgs = await api.organizations.list();

      for (const org of orgs) {
        const orgTeams = await api.organizations.teams.list(org.id);
        for (const team of orgTeams) {
          teams.push({
            id: team.id,
            name: team.name,
            organization: org.name
          });
        }
      }

      return { teams, orgs };
    } catch (e) {
      console.error('Failed to load share targets:', e);
      return { teams: [], orgs: [] };
    }
  }

  function goBack() {
    navigate('/boards');
  }

  async function handleShare(teamId, isPublicToOrg, organizationId = null) {
    await api.boards.share(board.id, teamId, isPublicToOrg, organizationId);
    // Reload board to get updated shared_team_id and is_public_to_org
    board = await api.boards.get(board.id);
  }

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
  <BoardView board={board} onBack={goBack} availableTeams={availableTeams} availableOrgs={availableOrgs} onShare={handleShare} onRename={handleRename} initialCardId={params.cardId} />
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
