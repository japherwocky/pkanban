<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from '../lib/api.js';

  let username = $state('');
  let email = $state('');
  let password = $state('');
  let submitting = $state(false);
  let error = $state(null);
  let sentTo = $state(null);
  let resending = $state(false);
  let resendNote = $state(null);

  onMount(() => {
    // Already signed in -- nothing to sign up for.
    if (localStorage.getItem('token')) {
      const redirectPath = localStorage.getItem('redirectPath') || '/boards';
      localStorage.removeItem('redirectPath');
      navigate(redirectPath);
      return;
    }

    // Arrived from an invite addressed to a particular address. Accepting
    // requires holding that address, so start the form on it.
    const invited = localStorage.getItem('inviteEmail');
    if (invited) {
      email = invited;
      localStorage.removeItem('inviteEmail');
    }
  });

  async function signup() {
    submitting = true;
    error = null;
    try {
      const result = await api.auth.signup(username, email, password);
      sentTo = result.email;
    } catch (e) {
      error = e.message;
    } finally {
      submitting = false;
    }
  }

  async function resend() {
    resending = true;
    resendNote = null;
    try {
      const result = await api.auth.resendVerification(sentTo);
      resendNote = result.message;
    } catch (e) {
      resendNote = e.message;
    } finally {
      resending = false;
    }
  }
</script>

<div class="signup-container">
  <div class="signup">
    {#if sentTo}
      <h1>Check your email</h1>
      <p class="sent">
        We sent a verification link to <strong>{sentTo}</strong>.
        Click it to finish setting up your account.
      </p>
      <p class="hint">The link expires in 24 hours.</p>
      <button class="secondary" onclick={resend} disabled={resending}>
        {resending ? 'Sending...' : 'Resend the email'}
      </button>
      {#if resendNote}
        <p class="hint">{resendNote}</p>
      {/if}
    {:else}
      <h1>Create your account</h1>
      <form onsubmit={(e) => { e.preventDefault(); signup(); }}>
        <input bind:value={username} placeholder="Username" required autocomplete="username" />
        <input bind:value={email} type="email" placeholder="Email" required autocomplete="email" />
        <input bind:value={password} type="password" placeholder="Password" required autocomplete="new-password" />
        {#if error}
          <p class="error">{error}</p>
        {/if}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Creating account...' : 'Sign up'}
        </button>
      </form>
      <p class="alt">Already have an account? <a href="/login">Log in</a></p>
    {/if}
  </div>
</div>

<style>
  .signup-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-8) var(--space-4);
  }

  .signup {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    width: 100%;
    max-width: 400px;
    text-align: center;
  }

  .signup h1 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-primary);
  }

  .signup form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    width: 100%;
    max-width: 320px;
  }

  input {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    border-radius: var(--radius-lg);
    border: 1px solid var(--color-border);
    background: var(--color-card);
    color: var(--color-foreground);
    transition: border-color var(--transition-fast);
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
    border: none;
  }

  .signup button[type="submit"] {
    background: var(--color-primary);
    color: var(--color-primary-foreground);
  }

  .signup button[type="submit"]:hover:not(:disabled) {
    opacity: 0.9;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  button.secondary {
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
  }

  button.secondary:hover:not(:disabled) {
    background: var(--color-accent);
  }

  .error {
    color: var(--color-destructive);
    font-size: var(--text-sm);
    margin: 0;
    text-align: left;
  }

  .sent {
    color: var(--color-foreground);
    line-height: 1.6;
    margin: 0;
  }

  .hint {
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
    margin: 0;
  }

  .alt {
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
    margin: 0;
  }

  .alt a {
    color: var(--color-primary);
    text-decoration: none;
  }

  .alt a:hover {
    text-decoration: underline;
  }
</style>
