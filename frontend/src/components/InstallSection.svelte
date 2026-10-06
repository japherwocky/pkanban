<script>
  // For the reader who would rather install pkanban themselves than ask an
  // agent to: the same one-liners the docs give, for this server. The hero's
  // agent prompt stays the lead (MARKETING.md); this sits further down.
  const ORIGIN = window.location.origin;

  const TABS = [
    { id: 'unix', label: 'macOS / Linux', command: `curl -fsSL ${ORIGIN}/install.sh | sh` },
    { id: 'powershell', label: 'Windows PowerShell', command: `irm ${ORIGIN}/install.ps1 | iex` },
    {
      id: 'cmd',
      label: 'Windows CMD',
      command: `curl -fsSL ${ORIGIN}/install.cmd -o install.cmd && install.cmd && del install.cmd`,
    },
  ];

  // Start on the visitor's own platform; they can still switch.
  const isWindows = /Win/i.test(navigator.userAgent);
  let selected = $state(isWindows ? 'powershell' : 'unix');
  let copied = $state(false);
  let copyResetTimer;

  const current = $derived(TABS.find((tab) => tab.id === selected));

  function select(id) {
    selected = id;
    copied = false;
  }

  function onTabKey(event, index) {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const next = TABS[(index + step + TABS.length) % TABS.length];
    select(next.id);
    document.getElementById(`install-tab-${next.id}`)?.focus();
  }

  function copyCommand() {
    navigator.clipboard.writeText(current.command);
    copied = true;
    clearTimeout(copyResetTimer);
    copyResetTimer = setTimeout(() => (copied = false), 2000);
  }
</script>

<section class="install-section" aria-labelledby="install-heading">
  <h2 id="install-heading">Or install it yourself</h2>
  <p class="lede">
    One line, and no Python needed. Then run <code>pkanban login</code> and
    approve it in your browser.
  </p>

  <div class="install-box">
    <div class="tabs" role="tablist" aria-label="Your system">
      {#each TABS as tab, index (tab.id)}
        <button
          id="install-tab-{tab.id}"
          class="tab"
          role="tab"
          aria-selected={selected === tab.id}
          aria-controls="install-panel"
          tabindex={selected === tab.id ? 0 : -1}
          onclick={() => select(tab.id)}
          onkeydown={(e) => onTabKey(e, index)}
        >
          {tab.label}
        </button>
      {/each}
    </div>

    <div id="install-panel" class="command-row" role="tabpanel" aria-labelledby="install-tab-{selected}">
      <code class="command">{current.command}</code>
      <button class="copy" onclick={copyCommand} aria-label="Copy the install command">
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  </div>
</section>

<style>
  .install-section {
    width: 100%;
    max-width: 760px;
    margin: var(--space-16) auto 0;
    padding: 0 var(--space-6);
    text-align: center;
  }

  h2 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-3);
  }

  .lede {
    color: var(--color-muted-foreground);
    margin: 0 0 var(--space-6);
  }

  .lede code {
    font-family: var(--font-mono);
    font-size: 0.95em;
    color: var(--color-foreground);
  }

  .install-box {
    text-align: left;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }

  /* One row that scrolls on a phone, rather than tabs stacking into a list. */
  .tabs {
    display: flex;
    overflow-x: auto;
    scrollbar-width: none;
    border-bottom: 1px solid var(--color-border);
  }

  .tab {
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-muted-foreground);
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    white-space: nowrap;
    cursor: pointer;
    transition: color var(--transition-fast), border-color var(--transition-fast);
  }

  .tab:hover {
    color: var(--color-foreground);
  }

  .tab[aria-selected='true'] {
    color: var(--color-foreground);
    border-bottom-color: var(--color-primary);
  }

  .tab:focus-visible,
  .copy:focus-visible {
    outline: none;
    box-shadow: var(--ring);
  }

  .command-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-4);
  }

  .command {
    flex: 1;
    min-width: 0;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-foreground);
    overflow-wrap: anywhere;
  }

  .copy {
    flex-shrink: 0;
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
    padding: var(--space-1) var(--space-2);
    background-color: color-mix(in srgb, var(--color-foreground) 6%, transparent);
    border: none;
    border-radius: var(--radius-sm);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
    cursor: pointer;
  }

  .copy:hover {
    color: var(--color-foreground);
  }
</style>
