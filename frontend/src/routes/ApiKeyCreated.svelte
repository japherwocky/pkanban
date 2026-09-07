<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';

  let apiKey = $state('');
  let keyName = $state('');
  let copied = $state(false);
  let mounted = $state(false);

  onMount(() => {
    // Get key from URL
    const params = new URLSearchParams(window.location.search);
    apiKey = params.get('key') || '';
    keyName = params.get('name') || 'API Key';
    mounted = true;

    // Clear URL to prevent re-exposure on refresh
    if (apiKey) {
      history.replaceState(null, '', window.location.pathname);
    }
  });

  async function copyKey() {
    if (!apiKey) return;

    try {
      await navigator.clipboard.writeText(apiKey);
      copied = true;
      setTimeout(() => {
        copied = false;
      }, 2000);
    } catch (e) {
      console.error('Failed to copy:', e);
    }
  }

  function done() {
    navigate('/settings/api-keys');
  }
</script>

<div class="key-created-page">
  <div class="success-icon">
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="24" cy="24" r="20"/>
      <path d="M16 24l6 6 12-12" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </div>

  <h2>API Key Created</h2>
  <p class="key-name-display">{keyName}</p>

  <div class="warning-banner">
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M10 6.67v5M10 14.67v.67"/>
      <circle cx="10" cy="10" r="8.33"/>
    </svg>
    <div>
      <strong>Copy this key now</strong>
      <p>You won't be able to see it again after leaving this page.</p>
    </div>
  </div>

  <div class="key-display">
    {#if mounted && apiKey}
      <code class="key-value">{apiKey}</code>
      <button class="copy-btn" onclick={copyKey} aria-label="Copy API key">
        {#if copied}
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M3.75 9l3.5 3.5 6.75-6.75" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Copied!
        {:else}
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="4" y="4" width="10" height="10" rx="1.5"/>
            <path d="M8.25 4v1.5a1.5 1.5 0 001.5 1.5h4"/>
          </svg>
          Copy
        {/if}
      </button>
    {:else}
      <p class="no-key">No key found. Please create a new API key.</p>
    {/if}
  </div>

  <div class="usage-section">
    <h3>Usage</h3>
    <p>Use this key to authenticate agents and CI pipelines:</p>
    <div class="code-example">
      <code>pkanban --api-key {apiKey || 'your-api-key'} board list</code>
    </div>
    <p class="header-note">Or set the <code>X-API-Key</code> header when making API requests:</p>
    <div class="code-example">
      <code>curl -H "X-API-Key: {apiKey || 'your-api-key'}" https://pkanban.pearachute.com/api/boards</code>
    </div>
  </div>

  <button class="done-btn" onclick={done}>
    {copied ? 'Done' : 'I\'ve copied the key'}
  </button>
</div>

<style>
  .key-created-page {
    max-width: 520px;
    margin: 0 auto;
    text-align: center;
    animation: fadeIn 0.3s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .success-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 80px;
    height: 80px;
    background: rgba(34, 197, 94, 0.1);
    border-radius: 50%;
    color: var(--color-success);
    margin-bottom: var(--space-6);
  }

  h2 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-2) 0;
  }

  .key-name-display {
    font-size: var(--text-base);
    color: var(--color-muted-foreground);
    margin: 0 0 var(--space-6) 0;
  }

  .warning-banner {
    display: flex;
    gap: 0.875rem;
    padding: var(--space-4);
    background: rgba(251, 191, 36, 0.1);
    border: 1px solid rgba(251, 191, 36, 0.3);
    border-radius: var(--radius-xl);
    text-align: left;
    margin-bottom: var(--space-6);
  }

  .warning-banner svg {
    flex-shrink: 0;
    color: var(--color-warning);
    margin-top: 0.125rem;
  }

  .warning-banner strong {
    display: block;
    font-size: var(--text-sm);
    font-weight: 700;
    color: var(--color-warning);
    margin-bottom: var(--space-1);
  }

  .warning-banner p {
    font-size: var(--text-sm);
    color: var(--color-warning);
    margin: 0;
    line-height: 1.4;
  }

  .key-display {
    display: flex;
    align-items: stretch;
    gap: var(--space-2);
    padding: var(--space-2);
    background: var(--color-code-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    margin-bottom: var(--space-8);
  }

  .key-value {
    flex: 1;
    padding: 0.875rem 1rem;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-code-fg);
    background: transparent;
    border: none;
    word-break: break-all;
    text-align: left;
    line-height: 1.5;
  }

  .copy-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.625rem 1rem;
    background: var(--color-muted);
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-foreground);
    cursor: pointer;
    transition: background-color var(--transition-fast);
    white-space: nowrap;
  }

  .copy-btn:hover {
    background: var(--color-border);
  }

  .no-key {
    flex: 1;
    padding: 0.875rem;
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0;
  }

  .usage-section {
    text-align: left;
    padding: var(--space-6);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    margin-bottom: var(--space-6);
  }

  .usage-section h3 {
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-2) 0;
  }

  .usage-section > p {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0 0 var(--space-3) 0;
  }

  .code-example {
    padding: var(--space-3) var(--space-4);
    background: var(--color-code-bg);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-4);
  }

  .code-example code {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-code-fg);
    word-break: break-all;
  }

  .header-note {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0 0 0.375rem 0;
  }

  .header-note code {
    padding: 0.125rem 0.375rem;
    background: var(--color-muted);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    color: var(--color-foreground);
  }

  .done-btn {
    width: 100%;
    padding: 0.875rem 1.5rem;
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: none;
    border-radius: var(--radius-xl);
    font-size: var(--text-base);
    font-weight: 700;
    cursor: pointer;
    transition: opacity var(--transition-fast);
  }

  .done-btn:hover {
    opacity: 0.9;
  }

  @media (max-width: 480px) {
    .key-display {
      flex-direction: column;
    }

    .copy-btn {
      justify-content: center;
    }
  }
</style>
