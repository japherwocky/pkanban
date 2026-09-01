<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from '../lib/api.js';
  import Modal from '../lib/Modal.svelte';

  let { params } = $props();
  let organization = $state(null);
  let members = $state([]);
  let teams = $state([]);
  let invites = $state([]);
  let loading = $state(true);
  let activeTab = $state('members');

  // Modals
  let showAddMemberModal = $state(false);
  let showCreateTeamModal = $state(false);
  let showAddTeamMemberModal = $state(false);
  let showCreateInviteModal = $state(false);
  let selectedTeam = $state(null);
  let teamMembers = $state([]);
  let teamMembersLoading = $state(false);
  let newMemberUsername = $state('');
  let newTeamName = $state('');
  let newInviteEmail = $state('');
  let addMemberLoading = $state(false);
  let createTeamLoading = $state(false);
  let createInviteLoading = $state(false);
  let addTeamMemberLoading = $state(false);

  // Store current username for permission checks
  let currentUsername = $state('');

  onMount(async () => {

    // Get username from token (simple decode - in production use JWT decode)
    try {
      const token = localStorage.getItem('token');
      const tokenData = JSON.parse(atob(token.split('.')[1]));
      currentUsername = tokenData.username;
    } catch (e) {
      console.error('Failed to decode token:', e);
    }

    await loadOrganization();
  });

  async function loadOrganization() {
    loading = true;
    try {
      organization = await api.organizations.get(params.id);
      members = await api.organizations.members.list(params.id);
      teams = await api.organizations.teams.list(params.id);
      invites = await api.organizations.invites.list(params.id);
    } catch (e) {
      console.error('Failed to load organization:', e);
      alert('Failed to load organization');
      navigate('/organizations');
    } finally {
      loading = false;
    }
  }

  function isOwner() {
    return organization?.owner_id && members.find(m => m.user_id === organization.owner_id && m.username === currentUsername);
  }

  async function addMember() {
    if (!newMemberUsername.trim()) return;
    addMemberLoading = true;
    try {
      const member = await api.organizations.members.add(params.id, newMemberUsername.trim());
      members = [...members, member];
      newMemberUsername = '';
      showAddMemberModal = false;
    } catch (e) {
      alert('Failed to add member: ' + e.message);
    } finally {
      addMemberLoading = false;
    }
  }

  async function removeMember(userId, username) {
    if (!confirm(`Remove ${username} from organization?`)) return;
    try {
      await api.organizations.members.remove(params.id, userId);
      members = members.filter(m => m.user_id !== userId);
    } catch (e) {
      alert('Failed to remove member: ' + e.message);
    }
  }

  async function createTeam() {
    if (!newTeamName.trim()) return;
    createTeamLoading = true;
    try {
      const team = await api.organizations.teams.create(params.id, newTeamName.trim());
      teams = [...teams, team];
      newTeamName = '';
      showCreateTeamModal = false;
    } catch (e) {
      alert('Failed to create team: ' + e.message);
    } finally {
      createTeamLoading = false;
    }
  }

  async function deleteTeam(teamId, teamName) {
    if (!confirm(`Delete team "${teamName}"? This will unshare all boards.`)) return;
    try {
      await api.teams.delete(teamId);
      teams = teams.filter(t => t.id !== teamId);
    } catch (e) {
      alert('Failed to delete team: ' + e.message);
    }
  }

  async function openTeamMembers(team) {
    selectedTeam = team;
    teamMembersLoading = true;
    showAddTeamMemberModal = true;
    try {
      teamMembers = await api.teams.members.list(team.id);
    } catch (e) {
      console.error('Failed to load team members:', e);
    } finally {
      teamMembersLoading = false;
    }
  }

  function isTeamMember() {
    return teamMembers.find(m => m.username === currentUsername);
  }

  async function addTeamMember() {
    if (!newMemberUsername.trim() || !selectedTeam) return;
    addTeamMemberLoading = true;
    try {
      const member = await api.teams.members.add(selectedTeam.id, newMemberUsername.trim());
      teamMembers = [...teamMembers, member];
      newMemberUsername = '';
    } catch (e) {
      alert('Failed to add team member: ' + e.message);
    } finally {
      addTeamMemberLoading = false;
    }
  }

  async function removeTeamMember(userId, username) {
    if (!confirm(`Remove ${username} from team?`)) return;
    try {
      await api.teams.members.remove(selectedTeam.id, userId);
      teamMembers = teamMembers.filter(m => m.user_id !== userId);
    } catch (e) {
      alert('Failed to remove team member: ' + e.message);
    }
  }

  async function createInvite() {
    createInviteLoading = true;
    try {
      const result = await api.organizations.invites.create(params.id, newInviteEmail.trim() || null);
      invites = [...invites, result];
      newInviteEmail = '';
      showCreateInviteModal = false;
    } catch (e) {
      alert('Failed to create invite: ' + e.message);
    } finally {
      createInviteLoading = false;
    }
  }

  async function revokeInvite(inviteId, email) {
    if (!confirm(`Revoke invite for ${email || 'anonymous'}?`)) return;
    try {
      await api.organizations.invites.revoke(params.id, inviteId);
      invites = invites.filter(i => i.id !== inviteId);
    } catch (e) {
      alert('Failed to revoke invite: ' + e.message);
    }
  }

  function copyInviteLink(invite) {
    const link = `${window.location.origin}/invite/${invite.token}`;
    navigator.clipboard.writeText(link);
    alert('Invite link copied to clipboard!');
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
      <button class="back-btn" onclick={() => navigate('/organizations')}>
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M12 4L6 10L12 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Back
      </button>
      <div class="org-header">
        <h1>{organization?.name || 'Organization'}</h1>
        <span class="org-slug">@{organization?.slug}</span>
      </div>
    </div>
  </header>

  {#if loading}
    <div class="loading">Loading organization...</div>
  {:else}
    <div class="content">
      <div class="tabs">
        <button
          class="tab-btn"
          class:active={activeTab === 'members'}
          onclick={() => activeTab = 'members'}
        >
          Members ({members.length})
        </button>
        <button
          class="tab-btn"
          class:active={activeTab === 'teams'}
          onclick={() => activeTab = 'teams'}
        >
          Teams ({teams.length})
        </button>
        <button
          class="tab-btn"
          class:active={activeTab === 'invites'}
          onclick={() => activeTab = 'invites'}
        >
          Invites ({invites.length})
        </button>
      </div>

      {#if activeTab === 'members'}
        <div class="section">
          <div class="section-header">
            <h2>Members</h2>
            {#if isOwner()}
              <button class="add-btn" onclick={() => showAddMemberModal = true}>+ Add Member</button>
            {/if}
          </div>

          {#if members.length === 0}
            <div class="empty-state">No members yet</div>
          {:else}
            <div class="members-list">
              {#each members as member (member.id)}
                <div class="member-item">
                  <div class="member-info">
                    <span class="member-username">{member.username}</span>
                    {#if member.user_id === organization?.owner_id}
                      <span class="owner-badge">Owner</span>
                    {/if}
                  </div>
                  <div class="member-actions">
                    {#if isOwner() && member.user_id !== organization?.owner_id}
                      <button
                        class="remove-btn"
                        onclick={() => removeMember(member.user_id, member.username)}
                      >
                        Remove
                      </button>
                    {:else if member.username === currentUsername && member.user_id !== organization?.owner_id}
                      <button
                        class="leave-btn"
                        onclick={() => removeMember(member.user_id, member.username)}
                      >
                        Leave
                      </button>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {:else if activeTab === 'teams'}
        <div class="section">
          <div class="section-header">
            <h2>Teams</h2>
            <button class="add-btn" onclick={() => showCreateTeamModal = true}>+ Create Team</button>
          </div>

          {#if teams.length === 0}
            <div class="empty-state">No teams yet</div>
          {:else}
            <div class="teams-list">
              {#each teams as team (team.id)}
                <div class="team-item">
                  <div class="team-info">
                    <h3>{team.name}</h3>
                    <span class="team-meta">Created {formatDate(team.created_at)}</span>
                  </div>
                  <div class="team-actions">
                    <button class="members-btn" onclick={() => openTeamMembers(team)}>
                      Members
                    </button>
                    {#if isOwner()}
                      <button
                        class="delete-team-btn"
                        onclick={() => deleteTeam(team.id, team.name)}
                      >
                        Delete
                      </button>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {:else if activeTab === 'invites'}
        <div class="section">
          <div class="section-header">
            <h2>Invites</h2>
            {#if isOwner()}
              <button class="add-btn" onclick={() => showCreateInviteModal = true}>+ Create Invite</button>
            {/if}
          </div>

          {#if invites.length === 0}
            <div class="empty-state">No pending invites</div>
          {:else}
            <div class="invites-list">
              {#each invites as invite (invite.id)}
                <div class="invite-item">
                  <div class="invite-info">
                    <span class="invite-email">{invite.email || 'Anonymous'}</span>
                    <span class="invite-meta">Created {formatDate(invite.created_at)}</span>
                  </div>
                  <div class="invite-actions">
                    <!-- The server sends the token to the owner only, so a
                         member sees that an invite exists without being able
                         to pass it on. -->
                    {#if invite.token}
                      <button class="copy-btn" onclick={() => copyInviteLink(invite)}>
                        Copy Link
                      </button>
                    {/if}
                    {#if isOwner()}
                      <button
                        class="revoke-btn"
                        onclick={() => revokeInvite(invite.id, invite.email)}
                      >
                        Revoke
                      </button>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<!-- Add Member Modal -->
{#if showAddMemberModal}
  <Modal open={showAddMemberModal} onClose={() => showAddMemberModal = false} title="Add Member">
    {#snippet children()}
      <p class="modal-help">Enter the username of the person you want to add to this organization.</p>
      <form onsubmit={(e) => { e.preventDefault(); addMember(); }}>
        <input
          bind:value={newMemberUsername}
          placeholder="Username"
          required
        />
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showAddMemberModal = false}>Cancel</button>
          <button type="submit" class="create-btn" disabled={addMemberLoading}>
            {addMemberLoading ? 'Adding...' : 'Add Member'}
          </button>
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

<!-- Create Team Modal -->
{#if showCreateTeamModal}
  <Modal open={showCreateTeamModal} onClose={() => showCreateTeamModal = false} title="Create Team">
    {#snippet children()}
      <p class="modal-help">Teams allow you to share boards with a subset of organization members.</p>
      <form onsubmit={(e) => { e.preventDefault(); createTeam(); }}>
        <input
          bind:value={newTeamName}
          placeholder="Team name"
          required
        />
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showCreateTeamModal = false}>Cancel</button>
          <button type="submit" class="create-btn" disabled={createTeamLoading}>
            {createTeamLoading ? 'Creating...' : 'Create Team'}
          </button>
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

<!-- Team Members Modal -->
{#if showAddTeamMemberModal}
  <Modal open={showAddTeamMemberModal} onClose={() => showAddTeamMemberModal = false} title={selectedTeam?.name ? `Team Members: ${selectedTeam.name}` : 'Team Members'}>
    {#snippet children()}
      <div class="team-members-list">
        {#if teamMembersLoading}
          <div class="loading">Loading members...</div>
        {:else if teamMembers.length === 0}
          <div class="empty-state">No members yet</div>
        {:else}
          {#each teamMembers as member (member.id)}
            <div class="team-member-item">
              <div class="member-info">
                <span class="member-username">{member.username}</span>
              </div>
              <div class="member-actions">
                {#if member.username !== currentUsername && isTeamMember()}
                  <button
                    class="remove-btn"
                    onclick={() => removeTeamMember(member.user_id, member.username)}
                  >
                    Remove
                  </button>
                {:else if member.username === currentUsername}
                  <button
                    class="leave-btn"
                    onclick={() => removeTeamMember(member.user_id, member.username)}
                  >
                    Leave
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        {/if}
      </div>

      {#if isTeamMember()}
        <div class="add-member-section">
          <h3>Add Member</h3>
          <p class="modal-help">Enter the username of an organization member to add them to this team.</p>
          <form class="add-member-form" onsubmit={(e) => { e.preventDefault(); addTeamMember(); }}>
            <div class="input-group">
              <input
                bind:value={newMemberUsername}
                placeholder="Username"
                required
              />
              <button type="submit" class="create-btn" disabled={addTeamMemberLoading}>
                {addTeamMemberLoading ? 'Adding...' : 'Add'}
              </button>
            </div>
          </form>
        </div>
      {/if}

      <div class="modal-actions">
        <button type="button" class="cancel-btn" onclick={() => showAddTeamMemberModal = false}>Close</button>
      </div>
    {/snippet}
  </Modal>
{/if}

<!-- Create Invite Modal -->
{#if showCreateInviteModal}
  <Modal open={showCreateInviteModal} onClose={() => showCreateInviteModal = false} title="Create Invite">
    {#snippet children()}
      <p class="modal-help">Generate an invite link to share with someone. They'll be able to join this organization.</p>
      <form onsubmit={(e) => { e.preventDefault(); createInvite(); }}>
        <input
          bind:value={newInviteEmail}
          placeholder="Email (optional)"
          type="email"
        />
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showCreateInviteModal = false}>Cancel</button>
          <button type="submit" class="create-btn" disabled={createInviteLoading}>
            {createInviteLoading ? 'Creating...' : 'Create Invite'}
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

  .org-header {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .org-header h1 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-primary);
    margin: 0;
  }

  .org-slug {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    font-family: monospace;
  }

  .loading {
    text-align: center;
    padding: var(--space-12);
    color: var(--color-muted-foreground);
  }

  .content {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .tabs {
    display: flex;
    gap: var(--space-2);
    border-bottom: 1px solid var(--color-border);
  }

  .tab-btn {
    padding: var(--space-3) var(--space-6);
    background: transparent;
    color: var(--color-muted-foreground);
    border: none;
    border-bottom: 2px solid transparent;
    font-size: var(--text-base);
    cursor: pointer;
    transition: border-bottom-color var(--transition-fast), color var(--transition-fast);
  }

  .tab-btn:hover {
    color: var(--color-foreground);
  }

  .tab-btn.active {
    color: var(--color-primary);
    border-bottom-color: var(--color-primary);
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-4);
  }

  .section-header h2 {
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--color-foreground);
    margin: 0;
  }

  .empty-state {
    text-align: center;
    padding: var(--space-12);
    color: var(--color-muted-foreground);
  }

  .members-list, .teams-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .member-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4) var(--space-5);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .member-info {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .member-username {
    font-size: var(--text-base);
    font-weight: 500;
    color: var(--color-foreground);
  }

  .owner-badge {
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border-radius: var(--radius-md);
    font-weight: 600;
    text-transform: uppercase;
  }

  .member-actions {
    display: flex;
    gap: var(--space-2);
  }

  .team-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-5);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .team-info h3 {
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--color-foreground);
    margin: 0 0 var(--space-1) 0;
  }

  .team-meta {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
  }

  .team-actions {
    display: flex;
    gap: var(--space-2);
  }

  .members-btn {
    padding: var(--space-2) var(--space-4);
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
    font-size: var(--text-sm);
  }

  .members-btn:hover {
    background: var(--color-muted);
    border-color: var(--color-primary);
  }

  .add-btn {
    padding: var(--space-2) var(--space-4);
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: none;
    font-size: var(--text-sm);
  }

  .add-btn:hover {
    opacity: 0.9;
  }

  .remove-btn, .delete-team-btn {
    padding: var(--space-2) var(--space-4);
    background-color: var(--color-error);
    color: var(--color-error-foreground);
    border: none;
    font-size: var(--text-sm);
  }

  .remove-btn:hover, .delete-team-btn:hover {
    opacity: 0.9;
  }

  .leave-btn {
    padding: var(--space-2) var(--space-4);
    background: transparent;
    color: var(--color-muted-foreground);
    border: 1px solid var(--color-border);
    font-size: var(--text-sm);
  }

  .leave-btn:hover {
    background: var(--color-muted);
    color: var(--color-destructive);
  }

  .invites-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .invite-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4) var(--space-5);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .invite-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .invite-email {
    font-size: var(--text-base);
    font-weight: 500;
    color: var(--color-foreground);
  }

  .invite-meta {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
  }

  .invite-actions {
    display: flex;
    gap: var(--space-2);
  }

  .copy-btn {
    padding: var(--space-2) var(--space-4);
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
    font-size: var(--text-sm);
  }

  .copy-btn:hover {
    background: var(--color-muted);
    border-color: var(--color-primary);
  }

  .revoke-btn {
    padding: var(--space-2) var(--space-4);
    background-color: var(--color-error);
    color: var(--color-error-foreground);
    border: none;
    font-size: var(--text-sm);
  }

  .revoke-btn:hover {
    opacity: 0.9;
  }

  .team-members-list {
    max-height: 400px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-bottom: var(--space-6);
  }

  .team-member-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-3) var(--space-4);
    background: var(--color-muted);
    border-radius: var(--radius-md);
  }

  .add-member-section {
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-6);
    margin-bottom: var(--space-6);
  }

  .add-member-section h3 {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-foreground);
    margin: 0 0 var(--space-2) 0;
  }

  .add-member-form {
    margin-top: var(--space-4);
  }

  .input-group {
    display: flex;
    gap: var(--space-3);
  }

  .input-group input {
    flex: 1;
  }

  .modal-help {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0 0 var(--space-4) 0;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    margin-top: var(--space-6);
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

  input, select {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    border-radius: var(--radius-lg);
    border: 1px solid var(--color-border);
    background: var(--color-card);
    color: var(--color-foreground);
    transition: border-color var(--transition-fast);
    width: 100%;
  }

  input:focus, select:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary);
  }

  button {
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast), box-shadow var(--transition-fast);
  }
</style>
