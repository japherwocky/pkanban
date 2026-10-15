<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { api } from '../lib/api.js';

  // An app connecting to pkanban over MCP (Claude, ChatGPT...) sends people
  // here from /oauth/authorize with ?request=<id>. Approving hands that app an
  // API key, so the page's job is to make clear who is asking and where the
  // browser goes next -- the sign-in code travels with it. The app's name is
  // whatever it registered with, so it is shown as a claim. Where the code
  // goes is the one thing the app cannot fake, so that is what the page
  // leads with.
  //
  // `leave` hands the browser back to the app. A prop so a test can see where
  // it would go without jsdom attempting the navigation.
  let { leave = (url) => window.location.assign(url) } = $props();

  const requestId = new URLSearchParams(window.location.search).get('request') || '';
  const signedIn = !!localStorage.getItem('token');
  let grant = $state(null);
  let loading = $state(false);
  let error = $state(null);
  let deciding = $state(false);
  // 'approved' or 'denied' once the browser is on its way back to the app.
  let leaving = $state(null);

  onMount(() => {
    if (requestId && signedIn) load();
  });

  async function load() {
    loading = true;
    error = null;
    try {
      grant = await api.oauthRequest.get(requestId);
    } catch (e) {
      error = e.message;
      grant = null;
    } finally {
      loading = false;
    }
  }

  async function decide(approve) {
    deciding = true;
    error = null;
    try {
      const result = approve
        ? await api.oauthRequest.approve(requestId)
        : await api.oauthRequest.deny(requestId);
      grant = result;
      leaving = approve ? 'approved' : 'denied';
      // Exactly the URL the server built: it checked the scheme, and it
      // carries the code and state the app is waiting for.
      leave(result.redirect_to);
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

<div class="consent-container">
  <div class="consent-card">
    {#if !signedIn}
      <h1>Sign in to continue</h1>
      <p class="muted">
        An app is asking to connect to your pkanban account. Sign in first, and
        you'll come back here to approve it.
      </p>
      <div class="actions">
        <button class="primary" onclick={() => goTo('/login')}>Sign in</button>
        <button class="secondary" onclick={() => goTo('/signup')}>Create an account</button>
      </div>
    {:else if !requestId}
      <h1>Nothing to approve</h1>
      <p class="muted">
        This link is missing its sign-in request. Start connecting again from
        the app.
      </p>
    {:else if leaving}
      <h1>{leaving === 'approved' ? 'Connected' : 'Not connected'}</h1>
      <p class="muted">Sending you back to {grant.redirect_host}...</p>
    {:else if error && !grant}
      <h1>Can't find this request</h1>
      <p class="error-text" role="alert">{error}</p>
      <p class="muted">Start connecting again from the app.</p>
    {:else if loading || !grant}
      <div class="muted">Looking up the request...</div>
    {:else if grant.status === 'pending'}
      <h1>Connect an app to pkanban?</h1>
      <div class="claim">
        <span class="muted">An app calling itself</span>
        <span class="app-name">{grant.client_name}</span>
      </div>
      <dl class="details">
        <dt>Sends you back to</dt>
        <dd><strong>{grant.redirect_host}</strong></dd>
        <dt>Requested</dt>
        <dd>{minutesAgo(grant.created_at)}</dd>
      </dl>
      <p class="warning">
        Approving lets this app read and change every board you can see, as
        you. It gets an API key you can revoke any time under Settings &gt; API
        keys. Only approve if you just asked {grant.client_name} to connect to
        pkanban, and expect to land back on <strong>{grant.redirect_host}</strong>.
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
    {:else if grant.status === 'approved' || grant.status === 'used'}
      <h1>Already approved</h1>
      <p class="muted">
        {grant.client_name} is connected. You can close this tab. To disconnect
        it, revoke its key under Settings &gt; API keys.
      </p>
      <a href="/settings/api-keys" class="link">Go to API keys</a>
    {:else if grant.status === 'denied'}
      <h1>Not connected</h1>
      <p class="muted">This request was denied. Nothing was shared with the app.</p>
    {:else}
      <h1>This request has expired</h1>
      <p class="muted">Requests last ten minutes. Start connecting again from the app.</p>
    {/if}
  </div>
</div>

<style>
  .consent-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-8) var(--space-4);
  }

  .consent-card {
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

  .claim {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .app-name {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-primary);
    overflow-wrap: anywhere;
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

  .warning strong {
    color: var(--color-foreground);
  }

  .error-text {
    color: var(--color-destructive);
    font-size: var(--text-sm);
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
</style>
