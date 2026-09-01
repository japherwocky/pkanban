<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from '../lib/api.js';

  let { params = {} } = $props();

  let invite = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let accepting = $state(false);

  onMount(async () => {
    try {
      invite = await api.invites.get(params.token);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  async function acceptInvite() {
    accepting = true;
    try {
      const result = await api.invites.accept(params.token);
      navigate(`/organizations/${result.organization_id}`);
    } catch (e) {
      alert(e.message);
    } finally {
      accepting = false;
    }
  }

  function goToLogin() {
    localStorage.setItem('redirectPath', `/invite/${params.token}`);
    navigate('/login');
  }

  function goToSignup() {
    localStorage.setItem('redirectPath', `/invite/${params.token}`);
    // An addressed invite can only be accepted by the address it was sent to,
    // so carry it into the signup form rather than letting someone register a
    // different one and hit a wall on the way back here.
    if (invite?.email) {
      localStorage.setItem('inviteEmail', invite.email);
    }
    navigate('/signup');
  }
</script>

<div class="invite-container">
  <div class="invite-card">
    {#if loading}
      <div class="loading">Validating invite...</div>
    {:else if error}
      <div class="error">
        <h1>Invalid Invite</h1>
        <p>{error}</p>
        <a href="/" class="back-link">Go to homepage</a>
      </div>
    {:else}
      <h1>You're Invited!</h1>
      <p class="invite-text">
        <strong>{invite.created_by_username}</strong> has invited you to join
        <span class="org-name">{invite.organization_name}</span>
      </p>
      {#if invite.email}
        <p class="invite-addressee">
          This invitation is for <strong>{invite.email}</strong>
        </p>
      {/if}

      <div class="actions">
        {#if localStorage.getItem('token')}
          <button class="primary" onclick={acceptInvite} disabled={accepting}>
            {accepting ? 'Joining...' : 'Accept Invite'}
          </button>
        {:else}
          <p class="auth-prompt">Sign in to accept this invitation</p>
          <button class="primary" onclick={goToLogin}>Login</button>
          <button class="secondary" onclick={goToSignup}>Create Account</button>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .invite-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-8) var(--space-4);
  }

  .invite-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-6);
    width: 100%;
    max-width: 400px;
    padding: var(--space-8);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    text-align: center;
  }

  h1 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-primary);
    margin: 0;
  }

  .invite-text {
    font-size: var(--text-base);
    color: var(--color-foreground);
    line-height: 1.6;
  }

  .org-name {
    color: var(--color-primary);
    font-weight: 600;
  }

  .invite-addressee {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: calc(-1 * var(--space-3)) 0 0;
  }

  .loading {
    color: var(--color-muted-foreground);
    font-size: var(--text-base);
  }

  .error h1 {
    color: var(--color-destructive);
  }

  .error p {
    color: var(--color-muted-foreground);
    margin: var(--space-2) 0;
  }

  .back-link {
    color: var(--color-primary);
    text-decoration: none;
  }

  .back-link:hover {
    text-decoration: underline;
  }

  .actions {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    width: 100%;
    margin-top: var(--space-4);
  }

  .auth-prompt {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0;
  }

  button {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    font-weight: 500;
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast), box-shadow var(--transition-fast);
    border: none;
  }

  button.primary {
    background: var(--color-primary);
    color: var(--color-primary-foreground);
  }

  button.primary:hover:not(:disabled) {
    opacity: 0.9;
  }

  button.primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  button.secondary {
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
  }

  button.secondary:hover {
    background: var(--color-accent);
  }
</style>
