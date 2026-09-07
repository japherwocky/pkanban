<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from '../lib/api.js';
  import Modal from '../lib/Modal.svelte';

  let organizations = $state([]);
  let organizationsLoading = $state(false);
  let showCreateModal = $state(false);
  let newOrgName = $state('');
  let createLoading = $state(false);

  onMount(async () => {
    await loadOrganizations();
  });

  async function loadOrganizations() {
    organizationsLoading = true;
    try {
      organizations = await api.organizations.list();
    } catch (e) {
      console.error('Failed to load organizations:', e);
    } finally {
      organizationsLoading = false;
    }
  }

  async function createOrganization() {
    if (!newOrgName.trim()) return;
    createLoading = true;
    try {
      const org = await api.organizations.create(newOrgName.trim());
      organizations = [...organizations, org];
      newOrgName = '';
      showCreateModal = false;
    } catch (e) {
      alert('Failed to create organization: ' + e.message);
    } finally {
      createLoading = false;
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
    <div class="header-left">
      <button class="back-btn" onclick={() => navigate('/boards')}>
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M12 4L6 10L12 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Back to Boards
      </button>
      <h1>Organizations</h1>
    </div>
  </header>

  {#if organizationsLoading}
    <div class="loading">Loading organizations...</div>
  {:else if organizations.length === 0}
    <div class="empty-state">
      <p>No organizations yet</p>
      <button class="create-btn" onclick={() => showCreateModal = true}>Create your first organization</button>
    </div>
  {:else}
    <div class="organizations-grid">
      {#each organizations as org (org.id)}
        <button class="org-card" onclick={() => navigate(`/organizations/${org.id}`)} type="button">
          <h3>{org.name}</h3>
          <div class="org-slug">@{org.slug}</div>
          <div class="org-meta">Created {formatDate(org.created_at)}</div>
        </button>
      {/each}
      <button class="org-card create-card" onclick={() => showCreateModal = true}>
        <span class="plus">+</span>
        <span>New Organization</span>
      </button>
    </div>
  {/if}
</div>

{#if showCreateModal}
  <Modal open={showCreateModal} onClose={() => showCreateModal = false} title="Create New Organization">
    {#snippet children()}
      <form onsubmit={(e) => { e.preventDefault(); createOrganization(); }}>
        <input
          bind:value={newOrgName}
          placeholder="Organization name"
          required
        />
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showCreateModal = false}>Cancel</button>
          <button type="submit" class="create-btn" disabled={createLoading}>
            {createLoading ? 'Creating...' : 'Create Organization'}
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
    padding-bottom: var(--space-4);
    border-bottom: 1px solid var(--color-border);
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
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-primary);
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

  .organizations-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-4);
  }

  .org-card {
    display: flex;
    flex-direction: column;
    padding: var(--space-6);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    cursor: pointer;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
    text-align: left;
    min-height: 140px;
  }

  .org-card:hover {
    border-color: var(--color-primary);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .org-card h3 {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-2) 0;
  }

  .org-slug {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin-bottom: var(--space-2);
    font-family: monospace;
  }

  .org-meta {
    margin-top: auto;
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
  }

  .create-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    min-height: 140px;
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
