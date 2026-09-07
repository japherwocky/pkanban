<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import SignupCTA from '../components/SignupCTA.svelte';
  import Logo from '../lib/Logo.svelte';
  import { api } from '../lib/api.js';

  // Must match UNVERIFIED_EMAIL_DETAIL in backend/api.py.
  const UNVERIFIED_DETAIL = 'Email not verified';

  let username = $state('');
  let password = $state('');
  let error = $state(null);
  let unverified = $state(false);
  let resendEmail = $state('');
  let resendNote = $state(null);
  let resending = $state(false);

  onMount(() => {
    const token = localStorage.getItem('token');
    const redirectPath = localStorage.getItem('redirectPath') || '/boards';
    if (token) {
      localStorage.removeItem('redirectPath');
      navigate(redirectPath);
    }
  });

  async function login() {
    error = null;
    unverified = false;
    resendNote = null;
    try {
      const res = await fetch('/api/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify({ username }));
        const redirectPath = localStorage.getItem('redirectPath') || '/boards';
        localStorage.removeItem('redirectPath');
        navigate(redirectPath);
        return;
      }
      // The body distinguishes "wrong password" from "correct password, but
      // you never clicked the verification link" -- the second is recoverable
      // and deserves a resend button rather than a dead end.
      const body = await res.json().catch(() => ({}));
      if (res.status === 403 && body.detail === UNVERIFIED_DETAIL) {
        unverified = true;
        error = 'Verify your email address before logging in.';
      } else {
        error = body.detail || 'Login failed';
      }
    } catch (e) {
      error = 'Login failed: ' + e.message;
    }
  }

  async function resend() {
    resending = true;
    resendNote = null;
    try {
      const result = await api.auth.resendVerification(resendEmail);
      resendNote = result.message;
    } catch (e) {
      resendNote = e.message;
    } finally {
      resending = false;
    }
  }
</script>

<div class="login-container">
  <div class="login">
    <Logo size={36} />
    <form onsubmit={(e) => { e.preventDefault(); login(); }}>
      <input bind:value={username} placeholder="Username" required autocomplete="username" />
      <input type="password" bind:value={password} placeholder="Password" required autocomplete="current-password" />
      {#if error}
        <p class="error">{error}</p>
      {/if}
      <button type="submit">Login</button>
    </form>

    {#if unverified}
      <!-- Asks for the address rather than showing it: the server will not
           tell an unauthenticated caller which email an account uses. -->
      <div class="resend">
        <p class="hint">Enter your email and we'll send a new verification link.</p>
        <input type="email" bind:value={resendEmail} placeholder="Email" autocomplete="email" />
        <button class="secondary" onclick={resend} disabled={resending || !resendEmail}>
          {resending ? 'Sending...' : 'Resend verification email'}
        </button>
        {#if resendNote}
          <p class="hint">{resendNote}</p>
        {/if}
      </div>
    {/if}

    <SignupCTA
      marginTop="2rem"
      maxWidth="400px"
      borderRadius="12px"
      padding="1.5rem"
      h2FontSize="1.5rem"
      descFontSize="0.9375rem"
      subtextFontSize="0.8125rem"
      compactPadding="1rem"
      compactH2FontSize="1.25rem"
      compactDescFontSize="0.875rem"
      showLoginLink={false}
    />
  </div>
</div>

<style>
  .login-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-8) var(--space-4);
  }

  .login {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    width: 100%;
  }

  .login form {
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
  }

  .login button[type="submit"] {
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: none;
  }

  .login button[type="submit"]:hover {
    opacity: 0.9;
  }

  .error {
    color: var(--color-destructive);
    font-size: var(--text-sm);
    margin: 0;
  }

  .resend {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    width: 100%;
    max-width: 320px;
    text-align: center;
  }

  .resend button.secondary {
    background: transparent;
    color: var(--color-foreground);
    border: 1px solid var(--color-border);
  }

  .resend button.secondary:hover:not(:disabled) {
    background: var(--color-accent);
  }

  .resend button.secondary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .hint {
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
    margin: 0;
  }
</style>
