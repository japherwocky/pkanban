<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import Modal from '../lib/Modal.svelte';

  let users = $state([]);
  let usersLoading = $state(false);
  let showCreateUserModal = $state(false);
  let showEditUserModal = $state(false);
  let selectedUser = $state(null);
  let newUserUsername = $state('');
  let newUserEmail = $state('');
  let newUserPassword = $state('');
  let newUserAdmin = $state(false);
  let editUserUsername = $state('');
  let editUserEmail = $state('');
  let editUserAdmin = $state(false);
  let resetPasswordForUser = $state(null);
  let resetPasswordNewPassword = $state('');
  let showResetPasswordModal = $state(false);

  onMount(async () => {
    await loadUsers();
  });

  async function loadUsers() {
    usersLoading = true;
    try {
      users = await api.admin.users.list();
    } catch (e) {
      console.error('Failed to load users:', e);
      alert('Failed to load users: ' + e.message);
    } finally {
      usersLoading = false;
    }
  }

  async function createUser() {
    if (!newUserUsername.trim() || !newUserPassword.trim()) return;

    try {
      await api.admin.users.create({
        username: newUserUsername.trim(),
        email: newUserEmail.trim() || null,
        password: newUserPassword,
        admin: newUserAdmin,
      });
      newUserUsername = '';
      newUserEmail = '';
      newUserPassword = '';
      newUserAdmin = false;
      showCreateUserModal = false;
      await loadUsers();
    } catch (e) {
      alert('Failed to create user: ' + e.message);
    }
  }

  function openEditUser(user) {
    selectedUser = user;
    editUserUsername = user.username;
    editUserEmail = user.email || '';
    editUserAdmin = user.admin || false;
    showEditUserModal = true;
  }

  async function updateUser() {
    if (!selectedUser) return;

    try {
      await api.admin.users.update(selectedUser.id, {
        username: editUserUsername.trim(),
        email: editUserEmail.trim() || null,
        admin: editUserAdmin,
      });
      showEditUserModal = false;
      selectedUser = null;
      await loadUsers();
    } catch (e) {
      alert('Failed to update user: ' + e.message);
    }
  }

  async function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) return;

    try {
      await api.admin.users.delete(userId);
      users = users.filter(u => u.id !== userId);
    } catch (e) {
      alert('Failed to delete user: ' + e.message);
    }
  }

  function openResetPassword(user) {
    resetPasswordForUser = user;
    resetPasswordNewPassword = '';
    showResetPasswordModal = true;
  }

  async function resetPassword() {
    if (!resetPasswordForUser || !resetPasswordNewPassword.trim()) return;

    try {
      await api.admin.users.resetPassword(resetPasswordForUser.id, {
        password: resetPasswordNewPassword,
      });
      showResetPasswordModal = false;
      resetPasswordForUser = null;
      resetPasswordNewPassword = '';
      alert('Password reset successfully');
    } catch (e) {
      alert('Failed to reset password: ' + e.message);
    }
  }
</script>

<div class="tab-header">
  <h2>Users</h2>
  <button class="create-btn" onclick={() => showCreateUserModal = true}>New User</button>
</div>

{#if usersLoading}
  <div class="loading">Loading users...</div>
{:else if users.length === 0}
  <div class="empty-state">No users found</div>
{:else}
  <div class="users-grid">
    {#each users as user (user.id)}
      <div class="user-card">
        <div class="user-info">
          <h3>{user.username}</h3>
          <p>{user.email || 'No email'}</p>
        </div>
        <div class="user-badges">
          {#if user.admin}
            <span class="badge admin-badge">Admin</span>
          {/if}
        </div>
        <div class="user-actions">
          <button class="action-btn" onclick={() => openEditUser(user)}>Edit</button>
          <button class="action-btn" onclick={() => openResetPassword(user)}>Reset Password</button>
          <button class="action-btn delete" onclick={() => deleteUser(user.id)}>Delete</button>
        </div>
      </div>
    {/each}
  </div>
{/if}

{#if showCreateUserModal}
  <Modal open={showCreateUserModal} onClose={() => showCreateUserModal = false} title="Create New User">
    {#snippet children()}
      <form onsubmit={(e) => { e.preventDefault(); createUser(); }}>
        <label>
          Username
          <input
            type="text"
            bind:value={newUserUsername}
            placeholder="Enter username"
            required
          />
        </label>
        <label>
          Email (optional)
          <input
            type="email"
            bind:value={newUserEmail}
            placeholder="Enter email"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            bind:value={newUserPassword}
            placeholder="Enter password"
            required
          />
        </label>
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={newUserAdmin} />
          <span>Admin user</span>
        </label>
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showCreateUserModal = false}>Cancel</button>
          <button type="submit" class="create-btn">Create User</button>
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

{#if showEditUserModal}
  <Modal open={showEditUserModal} onClose={() => showEditUserModal = false} title={selectedUser?.username ? `Edit User: ${selectedUser.username}` : 'Edit User'}>
    {#snippet children()}
      <form onsubmit={(e) => { e.preventDefault(); updateUser(); }}>
        <label>
          Username
          <input
            type="text"
            bind:value={editUserUsername}
            placeholder="Enter username"
            required
          />
        </label>
        <label>
          Email (optional)
          <input
            type="email"
            bind:value={editUserEmail}
            placeholder="Enter email"
          />
        </label>
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={editUserAdmin} />
          <span>Admin user</span>
        </label>
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showEditUserModal = false}>Cancel</button>
          <button type="submit" class="create-btn">Save Changes</button>
        </div>
      </form>
    {/snippet}
  </Modal>
{/if}

{#if showResetPasswordModal}
  <Modal open={showResetPasswordModal} onClose={() => showResetPasswordModal = false} title={resetPasswordForUser?.username ? `Reset Password for ${resetPasswordForUser.username}` : 'Reset Password'}>
    {#snippet children()}
      <form onsubmit={(e) => { e.preventDefault(); resetPassword(); }}>
        <label>
          New Password
          <input
            type="password"
            bind:value={resetPasswordNewPassword}
            placeholder="Enter new password"
            required
          />
        </label>
        <div class="modal-actions">
          <button type="button" class="cancel-btn" onclick={() => showResetPasswordModal = false}>Cancel</button>
          <button type="submit" class="create-btn">Reset Password</button>
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

  .users-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: var(--space-4);
  }

  .user-card {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--space-5);
  }

  .user-info h3 {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-1) 0;
  }

  .user-info p {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0;
  }

  .user-badges {
    margin: var(--space-3) 0;
    display: flex;
    gap: var(--space-2);
  }

  .badge {
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    font-weight: 700;
    border-radius: var(--radius-md);
  }

  .admin-badge {
    background: var(--color-destructive);
    color: var(--color-destructive-foreground);
  }

  .user-actions {
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

  label.checkbox-label {
    flex-direction: row;
    align-items: center;
    gap: var(--space-2);
    cursor: pointer;
  }

  label input[type="checkbox"] {
    width: auto;
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
