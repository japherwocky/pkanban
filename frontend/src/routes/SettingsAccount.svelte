<script>
  import { api } from '../lib/api.js';

  let current = $state('');
  let next = $state('');
  let confirm = $state('');
  let busy = $state(false);
  let error = $state(null);
  let done = $state(false);

  async function submit(e) {
    e.preventDefault();
    error = null;
    done = false;
    if (next !== confirm) {
      error = 'The new passwords do not match.';
      return;
    }
    busy = true;
    try {
      await api.me.changePassword(current, next);
      current = next = confirm = '';
      done = true;
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="account-page">
  <div class="page-header">
    <h2>Account</h2>
    <p class="description">Change the password you sign in with.</p>
  </div>

  <form class="card" onsubmit={submit}>
    <label>
      Current password
      <input type="password" autocomplete="current-password" bind:value={current} required />
    </label>
    <label>
      New password
      <input type="password" autocomplete="new-password" maxlength="72" bind:value={next} required />
    </label>
    <label>
      Confirm new password
      <input type="password" autocomplete="new-password" maxlength="72" bind:value={confirm} required />
    </label>

    {#if error}
      <p class="warn-text" role="alert">{error}</p>
    {/if}
    {#if done}
      <p class="muted" role="status">Password changed.</p>
    {/if}

    <div>
      <button class="primary" type="submit" disabled={busy || !current || !next || !confirm}>
        {busy ? 'Saving...' : 'Change password'}
      </button>
    </div>
  </form>
</div>

<style>
  .account-page {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .page-header h2 {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-1) 0;
  }

  .description,
  .muted {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0;
  }

  .warn-text {
    font-size: var(--text-sm);
    color: var(--color-destructive);
    margin: 0;
  }

  .card {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    max-width: 420px;
    padding: var(--space-5);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
  }

  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-foreground);
  }

  input {
    padding: var(--space-2) var(--space-3);
    background: var(--color-card);
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font: inherit;
  }

  input:focus {
    outline: none;
    border-color: var(--color-primary);
  }

  button {
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-lg);
    font-size: var(--text-sm);
    font-weight: 500;
    cursor: pointer;
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .primary {
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: 1px solid var(--color-primary);
  }
</style>
