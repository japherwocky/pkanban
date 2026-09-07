<script>
  import { link } from 'svelte-routing';
  import TerminalSimulator from './TerminalSimulator.svelte';
  import KanbanDemo from './KanbanDemo.svelte';

  let copied = $state(false);
  let copyResetTimer;

  function copyInstallCommand() {
    navigator.clipboard.writeText('pip install pkanban');
    copied = true;
    clearTimeout(copyResetTimer);
    copyResetTimer = setTimeout(() => (copied = false), 2000);
  }
</script>

<section class="hero-section">
  <div class="hero-content">
    <div class="text-content">
      <h1 class="headline">If your agent can print to stdout, it can use pkanban.</h1>
      <p class="subhead">No SDKs, no wrappers, no dependency hell.</p>

      <div class="hero-actions">
        <a href="/signup" use:link class="signup-button">Create your account</a>

        <button class="install-button" onclick={copyInstallCommand}>
          <code class="button-command">pip install pkanban</code>
          <span class="button-copy">{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
    </div>

    <div class="demo-container">
      <div class="demo-grid">
        <div class="demo-terminal">
          <TerminalSimulator />
        </div>
        <div class="demo-board">
          <KanbanDemo />
        </div>
      </div>
    </div>
  </div>
</section>

<style>
  .hero-section {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-16) var(--space-6);
    background-color: var(--color-background);
    position: relative;
    overflow: hidden;
  }

  .hero-section::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image:
      linear-gradient(to right, var(--color-border) 1px, transparent 1px),
      linear-gradient(to bottom, var(--color-border) 1px, transparent 1px);
    background-size: 72px 72px;
    opacity: 0.35;
    /* Fade the grid out before it reaches the copy, so it stays texture
       rather than becoming a thing you read. */
    mask-image: radial-gradient(ellipse 70% 60% at 50% 0%, #000 0%, transparent 75%);
    pointer-events: none;
  }

  .hero-content {
    max-width: 1200px;
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: var(--space-12);
    position: relative;
    z-index: 1;
  }

  .text-content {
    text-align: center;
    max-width: 800px;
    margin: 0 auto;
  }

  .headline {
    font-size: var(--text-4xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-5) 0;
    line-height: var(--leading-tight);
    letter-spacing: var(--tracking-tight);
    text-wrap: balance;
  }

  .subhead {
    font-size: var(--text-lg);
    color: var(--color-muted-foreground);
    margin: 0 0 var(--space-8) 0;
    line-height: var(--leading-relaxed);
    text-wrap: pretty;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
  }

  .hero-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: var(--space-4);
  }

  .signup-button {
    display: inline-flex;
    align-items: center;
    padding: var(--space-3) var(--space-6);
    border-radius: var(--radius-md);
    background-color: var(--color-primary);
    color: var(--color-primary-foreground);
    font-size: var(--text-sm);
    font-weight: 700;
    text-decoration: none;
    border: 1px solid var(--color-primary);
    transition: background-color var(--transition-fast), border-color var(--transition-fast);
  }

  .signup-button:hover {
    background-color: color-mix(in srgb, var(--color-primary) 86%, var(--color-foreground));
    border-color: color-mix(in srgb, var(--color-primary) 86%, var(--color-foreground));
  }

  .signup-button:focus-visible {
    outline: none;
    box-shadow: var(--ring);
  }

  .install-button {
    display: inline-flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-5);
    background-color: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: border-color var(--transition-fast), background-color var(--transition-fast);
    font-family: var(--font-mono);
  }

  .install-button:hover {
    border-color: var(--color-primary);
    background-color: var(--color-muted);
  }

  .button-command {
    font-size: var(--text-sm);
    color: var(--color-foreground);
    font-weight: 500;
    background: transparent;
    padding: 0;
  }

  .button-copy {
    font-size: var(--text-xs);
    color: var(--color-muted-foreground);
    padding: var(--space-1) var(--space-2);
    background-color: color-mix(in srgb, var(--color-foreground) 6%, transparent);
    border-radius: var(--radius-sm);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
    transition: color var(--transition-fast), background-color var(--transition-fast);
  }

  .install-button:hover .button-copy {
    color: var(--color-foreground);
    background: color-mix(in srgb, var(--color-foreground) 10%, transparent);
  }

  .demo-container {
    width: 100%;
  }

  .demo-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-6);
    min-height: 400px;
  }

  .demo-terminal,
  .demo-board {
    position: relative;
  }

  @media (max-width: 1024px) {
    .demo-grid {
      grid-template-columns: 1fr;
      gap: var(--space-4);
      min-height: 700px;
    }
  }

  @media (max-width: 640px) {
    .hero-section {
      padding: var(--space-10) var(--space-4);
    }

    .hero-actions {
      flex-direction: column;
      align-items: stretch;
      gap: var(--space-3);
    }

    .signup-button {
      width: 100%;
      justify-content: center;
      padding: 13px 20px;
    }

    .install-button {
      width: 100%;
      justify-content: center;
      padding: var(--space-3) var(--space-5);
    }

    .button-command {
      font-size: var(--text-sm);
    }

    .demo-grid {
      min-height: 600px;
    }
  }
</style>
