<script>
  import { link } from 'svelte-routing';
  import TerminalSimulator from './TerminalSimulator.svelte';
  import KanbanDemo from './KanbanDemo.svelte';

  // What the visitor pastes into their AI. Not `pip install pkanban`: the
  // reader this page is for may never have opened a terminal, and doesn't
  // need to -- the agent installs pkanban itself, then asks them to sign in.
  // It points at /agents.md, setup written for the agent, so every agent
  // follows the same steps instead of guessing at them. https is implied for
  // the hosted site; anything else (a local or self-hosted server on plain
  // http) spells its scheme out.
  const SERVER =
    window.location.protocol === 'https:' ? window.location.host : window.location.origin;
  const AGENT_PROMPT = `Read ${SERVER}/agents.md and set up pkanban for me.`;

  let copied = $state(false);
  let copyResetTimer;

  function copyAgentPrompt() {
    navigator.clipboard.writeText(AGENT_PROMPT);
    copied = true;
    clearTimeout(copyResetTimer);
    copyResetTimer = setTimeout(() => (copied = false), 2000);
  }
</script>

<section class="hero-section">
  <div class="hero-content">
    <div class="text-content">
      <h1 class="headline">Give your AI a to-do list you can both see.</h1>
      <p class="subhead">
        Works with Claude Code, Codex, opencode, or any AI that can run commands.
        Setup is one sentence: paste the one below into your AI, and it'll install
        pkanban and ask you to sign in.
      </p>

      <div class="hero-actions">
        <a href="/signup" use:link class="signup-button">Create your account</a>

        <button
          class="prompt-button"
          onclick={copyAgentPrompt}
          aria-label="Copy a message to paste into your AI: {AGENT_PROMPT}"
        >
          <span class="prompt-text">“{AGENT_PROMPT}”</span>
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

  .prompt-button {
    display: inline-flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-5);
    background-color: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: border-color var(--transition-fast), background-color var(--transition-fast);
  }

  .prompt-button:hover {
    border-color: var(--color-primary);
    background-color: var(--color-muted);
  }

  .prompt-button:focus-visible {
    outline: none;
    box-shadow: var(--ring);
  }

  /* Body face, not mono: this is a sentence you say to your AI, not a
     command you type, and mono would read as "code" to the people it's for. */
  .prompt-text {
    font-size: var(--text-sm);
    color: var(--color-foreground);
    font-weight: 500;
    text-align: left;
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

  .prompt-button:hover .button-copy {
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

    .prompt-button {
      width: 100%;
      justify-content: space-between;
      padding: var(--space-3) var(--space-5);
    }

    .demo-grid {
      min-height: 600px;
    }
  }
</style>
