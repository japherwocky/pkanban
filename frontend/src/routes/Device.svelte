<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from '../lib/api.js';

  // `pkanban login` (no username) sends people here with ?code=XXXX-XXXX.
  // Approving hands that terminal an API key, so the page's job is to make
  // sure the person knows which terminal they are letting in.
  let code = $state(new URLSearchParams(window.location.search).get('code') || '');
  let typedCode = $state('');
  let login = $state(null);
  let loading = $state(false);
  let error = $state(null);
  let deciding = $state(false);
  const signedIn = !!localStorage.getItem('token');

  onMount(() => {
    if (code && signedIn) load();
  });

  async function load() {
    loading = true;
    error = null;
    try {
      login = await api.deviceLogin.get(code);
    } catch (e) {
      error = e.message;
      login = null;
    } finally {
      loading = false;
    }
  }

  function submitCode(event) {
    event.preventDefault();
    code = typedCode.trim();
    if (!code) return;
    history.replaceState(null, '', `/device?code=${encodeURIComponent(code)}`);
    load();
  }

  async function decide(approve) {
    deciding = true;
    error = null;
    try {
      login = approve
        ? await api.deviceLogin.approve(code)
        : await api.deviceLogin.deny(code);
    } catch (e) {
      error = e.message;
    } finally {
      deciding = false;
    }
  }

  function goTo(path) {
    localStorage.setItem('redirectPath', window.location.pathname + window.location.search);
    navigate(path);
  }

  function minutesAgo(when) {
    const minutes = Math.round((Date.now() - new Date(when).getTime()) / 60000);
    if (minutes < 1) return 'just now';
    return minutes === 1 ? '1 minute ago' : `${minutes} minutes ago`;
  }
</script>

<div class="device-container">
  <div class="device-card">
    {#if !signedIn}
      <h1>Sign in to continue</h1>
      <p class="muted">
        A terminal is asking to sign in to pkanban{code ? ` with the code ${code}` : ''}.
        Sign in first, and you'll come back here to approve it.
      </p>
      <div class="actions">
        <button class="primary" onclick={() => goTo('/login')}>Sign in</button>
        <button class="secondary" onclick={() => goTo('/signup')}>Create an account</button>
      </div>
    {:else if !code || (error && !login)}
      <h1>Connect a terminal</h1>
      <p class="muted">Enter the code that <code>pkanban login</code> printed.</p>
      {#if error}
        <p class="error-text" role="alert">{error}</p>
      {/if}
      <form class="code-form" onsubmit={submitCode}>
        <label class="sr-only" for="device-code">Code</label>
        <input
          id="device-code"
          bind:value={typedCode}
          placeholder="XXXX-XXXX"
          autocomplete="off"
          autocapitalize="characters"
          spellcheck="false"
        />
        <button class="primary" type="submit">Continue</button>
      </form>
    {:else if loading || !login}
      <div class="muted">Looking up the code...</div>
    {:else if login.status === 'pending'}
      <h1>Let this terminal into your account?</h1>
      <div class="code">{login.user_code}</div>
      <p class="muted">Check this matches the code in your terminal.</p>
      <dl class="details">
        <dt>Computer</dt>
        <dd>{login.client_name}</dd>
        <dt>Requested</dt>
        <dd>{minutesAgo(login.created_at)}{login.requester_ip ? ` from ${login.requester_ip}` : ''}</dd>
      </dl>
      <p class="warning">
        Only approve if you, or an AI agent working for you, just ran
        <code>pkanban login</code>. It gets full access to your boards, as an
        API key you can revoke any time under Settings &gt; API keys.
      </p>
      {#if error}
        <p class="error-text" role="alert">{error}</p>
      {/if}
      <div class="actions">
        <button class="primary" onclick={() => decide(true)} disabled={deciding}>
          {deciding ? 'Working...' : 'Approve'}
        </button>
        <button class="secondary" onclick={() => decide(false)} disabled={deciding}>Deny</button>
      </div>
    {:else if login.status === 'approved' || login.status === 'claimed'}
      <h1>Terminal connected</h1>
      <p class="muted">
        {login.client_name} is signed in. You can close this tab; the terminal
        carries on by itself.
      </p>
      <a href="/boards" class="link">Go to your boards</a>
    {:else if login.status === 'denied'}
      <h1>Login denied</h1>
      <p class="muted">That terminal was not let in. Nothing was shared with it.</p>
    {:else}
      <h1>This code has expired</h1>
      <p class="muted">Codes last ten minutes. Run <code>pkanban login</code> again for a new one.</p>
    {/if}
  </div>
</div>

<style>
  .device-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-8) var(--space-4);
  }

  .device-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-5);
    width: 100%;
    max-width: 440px;
    padding: var(--space-8);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    text-align: center;
  }

  h1 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0;
  }

  p {
    margin: 0;
    line-height: 1.6;
  }

  .muted {
    color: var(--color-muted-foreground);
  }

  code {
    font-family: var(--font-mono);
    font-size: 0.95em;
  }

  .code {
    font-family: var(--font-mono);
    font-size: var(--text-3xl);
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--color-primary);
  }

  .details {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--space-2) var(--space-4);
    width: 100%;
    margin: 0;
    text-align: left;
    font-size: var(--text-sm);
  }

  .details dt {
    color: var(--color-muted-foreground);
  }

  .details dd {
    margin: 0;
    color: var(--color-foreground);
    overflow-wrap: anywhere;
  }

  .warning {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    text-align: left;
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .error-text {
    color: var(--color-destructive);
    font-size: var(--text-sm);
  }

  .code-form {
    display: flex;
    gap: var(--space-2);
    width: 100%;
  }

  .code-form input {
    flex: 1;
    min-width: 0;
    padding: var(--space-3) var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-foreground);
    background: var(--color-background);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .actions {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    width: 100%;
  }

  button {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-base);
    font-weight: 500;
    border-radius: var(--radius-lg);
    cursor: pointer;
    border: none;
    transition: opacity var(--transition-fast), background-color var(--transition-fast);
  }

  button.primary {
    background: var(--color-primary);
    color: var(--color-primary-foreground);
  }

  button.primary:hover:not(:disabled) {
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

  .link {
    color: var(--color-primary);
    text-decoration: none;
  }

  .link:hover {
    text-decoration: underline;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }
</style>
