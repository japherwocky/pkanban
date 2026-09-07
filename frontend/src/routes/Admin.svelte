<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from '../lib/api.js';
  import ThemeToggle from '../lib/ThemeToggle.svelte';
  import AdminUsers from './AdminUsers.svelte';
  import AdminOrganizations from './AdminOrganizations.svelte';
  import AdminTeams from './AdminTeams.svelte';
  import AdminBoards from './AdminBoards.svelte';

  const { params } = $props();

  let isAdmin = $state(false);
  let adminCheckLoading = $state(true);

  // Get current section from route, default to 'users'
  let currentSection = $derived(params.section || 'users');

  onMount(async () => {
    await checkAdminStatus();
    if (!isAdmin) {
      navigate('/');
      return;
    }
  });

  async function checkAdminStatus() {
    try {
      const status = await api.admin.status();
      isAdmin = status.is_admin;
    } catch (e) {
      console.error('Admin check failed:', e);
      isAdmin = false;
    } finally {
      adminCheckLoading = false;
    }
  }

  function logout() {
    localStorage.removeItem('token');
    navigate('/login');
  }

  function navigateTo(section) {
    navigate(`/admin/${section}`);
  }
</script>

{#if adminCheckLoading}
  <div class="loading">Checking admin permissions...</div>
{:else if !isAdmin}
  <div class="not-admin">
    <h2>Access Denied</h2>
    <p>You don't have admin permissions to access this page.</p>
    <button onclick={() => navigate('/')}>Go to Dashboard</button>
  </div>
{:else}
  <div class="admin-app">
    <header>
      <h1>Admin Dashboard</h1>
      <div class="header-actions">
        <button class="nav-btn" onclick={() => navigate('/')}>Back to App</button>
        <ThemeToggle />
        <button class="logout-btn" onclick={logout}>Logout</button>
      </div>
    </header>

    <div class="admin-layout">
      <aside class="sidebar">
        <nav>
          <button
            class:active={currentSection === 'users'}
            onclick={() => navigateTo('users')}
          >
            Users
          </button>
          <button
            class:active={currentSection === 'organizations'}
            onclick={() => navigateTo('organizations')}
          >
            Organizations
          </button>
          <button
            class:active={currentSection === 'teams'}
            onclick={() => navigateTo('teams')}
          >
            Teams
          </button>
          <button
            class:active={currentSection === 'boards'}
            onclick={() => navigateTo('boards')}
          >
            Boards
          </button>
        </nav>
      </aside>

      <main class="content">
        {#if currentSection === 'users'}
          <AdminUsers />
        {:else if currentSection === 'organizations'}
          <AdminOrganizations />
        {:else if currentSection === 'teams'}
          <AdminTeams />
        {:else if currentSection === 'boards'}
          <AdminBoards />
        {:else}
          <div class="coming-soon">
            <h2>{currentSection.charAt(0).toUpperCase() + currentSection.slice(1)}</h2>
            <p>This section is coming soon</p>
          </div>
        {/if}
      </main>
    </div>
  </div>
{/if}

<style>
  .loading, .not-admin, .coming-soon {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-16) var(--space-8);
    text-align: center;
    color: var(--color-muted-foreground);
  }

  .not-admin h2 {
    color: var(--color-destructive);
    margin-bottom: var(--space-2);
  }

  .admin-app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4) var(--space-6);
    border-bottom: 1px solid var(--color-border);
    background: var(--color-card);
  }

  header h1 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-destructive);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .nav-btn {
    padding: var(--space-2) var(--space-4);
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
    font-size: var(--text-sm);
  }

  .nav-btn:hover {
    background: var(--color-muted);
  }

  .logout-btn {
    padding: var(--space-2) var(--space-4);
    background: var(--color-muted);
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
  }

  .logout-btn:hover {
    background: var(--color-border);
  }

  .admin-layout {
    display: flex;
    flex: 1;
  }

  .sidebar {
    width: 240px;
    background: var(--color-muted);
    border-right: 1px solid var(--color-border);
    padding: var(--space-4) 0;
  }

  .sidebar nav {
    display: flex;
    flex-direction: column;
  }

  .sidebar button {
    width: 100%;
    padding: var(--space-3) var(--space-6);
    text-align: left;
    background: transparent;
    border: none;
    color: var(--color-foreground);
    font-size: var(--text-base);
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast);
  }

  .sidebar button:hover:not(:disabled) {
    background: var(--color-card);
  }

  .sidebar button.active {
    background: var(--color-card);
    color: var(--color-primary);
    font-weight: 700;
    border-left: 3px solid var(--color-primary);
  }

  .sidebar button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .content {
    flex: 1;
    padding: var(--space-8);
  }

  button {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    font-weight: 500;
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast), box-shadow var(--transition-fast);
  }

  .coming-soon h2 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin-bottom: var(--space-2);
  }
</style>
