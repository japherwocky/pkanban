<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import Modal from '../lib/Modal.svelte';

  let organizations = $state([]);
  let organizationsLoading = $state(false);
  let users = $state([]);
  let showCreateOrgModal = $state(false);
  let showEditOrgModal = $state(false);
  let selectedOrg = $state(null);
  let newOrgName = $state('');
  let newOrgOwnerId = $state('');
  let editOrgName = $state('');
  let editOrgOwnerId = $state('');

  onMount(async () => {
    await Promise.all([loadOrganizations(), loadUsers()]);
  });

  async function loadOrganizations() {
    organizationsLoading = true;
    try {
      organizations = await api.admin.organizations.list();
    } catch (e) {
      console.error('Failed to load organizations:', e);
      alert('Failed to load organizations: ' + e.message);
    } finally {
      organizationsLoading = false;
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

  async function createOrganization() {
    if (!newOrgName.trim() || !newOrgOwnerId) return;

    try {
      await api.admin.organizations.create({
        name: newOrgName.trim(),
        owner_id: parseInt(newOrgOwnerId),
      });
      newOrgName = '';
      newOrgOwnerId = '';
      showCreateOrgModal = false;
      await loadOrganizations();
    } catch (e) {
      alert('Failed to create organization: ' + e.message);
    }
  }

  function openEditOrg(org) {
    selectedOrg = org;
    editOrgName = org.name;
    editOrgOwnerId = org.owner_id.toString();
    showEditOrgModal = true;
  }

  async function updateOrganization() {
    if (!selectedOrg) return;

    try {
      await api.admin.organizations.update(selectedOrg.id, {
        name: editOrgName.trim(),
        owner_id: parseInt(editOrgOwnerId),
      });
      showEditOrgModal = false;
      selectedOrg = null;
      await loadOrganizations();
    } catch (e) {
      alert('Failed to update organization: ' + e.message);
    }
  }

  async function deleteOrganization(orgId) {
    if (!confirm('Are you sure you want to delete this organization? This will delete all teams, boards, cards, and members. This action cannot be undone.')) return;

    try {
      await api.admin.organizations.delete(orgId);
      organizations = organizations.filter(o => o.id !== orgId);
    } catch (e) {
      alert('Failed to delete organization: ' + e.message);
    }
  }
</script>

<div class="tab-header">
  <h2>Organizations</h2>
  <button class="create-btn" onclick={() => showCreateOrgModal = true}>New Organization</button>
</div>

{#if organizationsLoading}
  <div class="loading">Loading organizations...</div>
{:else if organizations.length === 0}
  <div class="empty-state">No organizations found</div>
{:else}
  <div class="organizations-grid">
    {#each organizations as org (org.id)}
      <div class="org-card">
        <div class="org-info">
          <h3>{org.name}</h3>
          <p class="slug">@{org.slug}</p>
        </div>
        <div class="org-stats">
          <div class="stat">
            <span class="stat-value">{org.member_count}</span>
            <span class="stat-label">Members</span>
          </div>
          <div class="stat">
            <span class="stat-value">{org.team_count}</span>
            <span class="stat-label">Teams</span>
          </div>
        </div>
        <div class="org-meta">
          <span class="owner-badge">Owner: {org.owner_username}</span>
        </div>
        <div class="org-actions">
          <button class="action-btn" onclick={() => openEditOrg(org)}>Edit</button>
          <button class="action-btn delete" onclick={() => deleteOrganization(org.id)}>Delete</button>
        </div>
      </div>
    {/each}
  </div>
{/if}

{#if showCreateOrgModal}
  <Modal open={showCreateOrgModal} onClose={() => showCreateOrgModal = false} title="Create New Organization">
    {#snippet children()}
      <form onsubmit={(e) => { e.preventDefault(); createOrganization(); }}>
        <label>
          Name
          <input
            type="text"
            bind:value={newOrgName}
            placeholder="Enter organization name"
            required
          />
        </label>
        <label>
          Owner
          <select bind:value={newOrgOwnerId} required>
            <option value="">Select owner...</option>
            {#each users as user}
              <option value={user.id}>{user.username}</option>
            {/each}
          </select>
        </label>
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showCreateOrgModal = false}>Cancel</button>
          <button type="submit" class="create-btn">Create Organization</button>
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

{#if showEditOrgModal}
  <Modal open={showEditOrgModal} onClose={() => showEditOrgModal = false} title={selectedOrg?.name ? `Edit Organization: ${selectedOrg.name}` : 'Edit Organization'}>
    {#snippet children()}
      <form onsubmit={(e) => { e.preventDefault(); updateOrganization(); }}>
        <label>
          Name
          <input
            type="text"
            bind:value={editOrgName}
            placeholder="Enter organization name"
            required
          />
        </label>
        <label>
          Owner
          <select bind:value={editOrgOwnerId} required>
            <option value="">Select owner...</option>
            {#each users as user}
              <option value={user.id}>{user.username}</option>
            {/each}
          </select>
        </label>
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showEditOrgModal = false}>Cancel</button>
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

  .organizations-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: var(--space-4);
  }

  .org-card {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--space-5);
  }

  .org-info h3 {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-1) 0;
  }

  .org-info .slug {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0;
    font-family: monospace;
  }

  .org-stats {
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

  .org-meta {
    margin: var(--space-3) 0;
  }

  .owner-badge {
    display: inline-block;
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    font-weight: 700;
    background: var(--color-muted);
    color: var(--color-foreground);
    border-radius: var(--radius-md);
  }

  .org-actions {
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
