<script>
  import { link } from 'svelte-routing';
  import ParachuteScene from './ParachuteScene.svelte';

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

      <!-- The sentence above needs an AI that can run commands. A chat window
           can't, so the reader who would try it there gets the route that
           works for them. See MARKETING.md section 2. -->
      <p class="chat-route">
        Using Claude in the chat window instead?
        <a href="/connect/claude" use:link>Add pkanban as a connector</a>.
      </p>
    </div>

    <!-- The story in one shot: work lands on the board, carried down by a
         pear, and makes its way to Done. This replaced a terminal typing CLI
         commands beside a flat board; with the MCP connector, the terminal
         is no longer the way most people will meet pkanban. -->
    <div class="hero-stage">
      <div class="hero-scene">
        <ParachuteScene height="clamp(340px, 50vw, 560px)" />
      </div>
      <!-- The end card. Outside .hero-scene, whose edge fade would otherwise
           fade the text with it. -->
      <div class="scene-caption">
        <p class="scene-eyebrow">pkanban</p>
        <h2>Your AI moves the cards.</h2>
        <p class="scene-sub">It adds them as it finds the work and moves them as it goes. You watch the board.</p>
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

  .chat-route {
    margin: var(--space-6) 0 0 0;
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
  }

  .chat-route a {
    color: var(--color-primary);
    text-decoration: underline;
    text-underline-offset: 2px;
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

  /* A fixed height (set on the scene), so nothing in the shot can resize
     the hero: the old demo grew and shrank with its content and shifted the
     whole page every few seconds. The edges fade into the page, so the scene
     reads as part of it rather than as a video in a box. */
  .hero-stage {
    position: relative;
  }

  .hero-scene {
    width: 100%;
    /* Chutes fade in from above instead of being clipped by the top edge. */
    mask-image:
      linear-gradient(to bottom, transparent 0, #000 16%, #000 84%, transparent 100%),
      linear-gradient(to right, transparent 0, #000 6%, #000 94%, transparent 100%);
    mask-composite: intersect;
  }

  /* Over the scene's lower left, like a commercial's end card. A soft wash of
     the page color behind it keeps it legible when a card passes beneath. */
  .scene-caption {
    position: absolute;
    left: 0;
    bottom: 0;
    max-width: min(34rem, 60%);
    padding: var(--space-10) var(--space-10) var(--space-6) var(--space-2);
    background: radial-gradient(ellipse at 20% 80%, var(--color-background) 30%, transparent 72%);
    pointer-events: none;
  }

  .scene-caption h2 {
    margin: 0;
    font-size: clamp(2rem, 4.6vw, 4rem);
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
    color: var(--color-foreground);
    text-wrap: balance;
  }

  .scene-eyebrow {
    margin: 0 0 var(--space-3);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--color-primary);
  }

  .scene-sub {
    margin: var(--space-4) 0 0;
    max-width: 40ch;
    font-size: var(--text-lg);
    color: var(--color-muted-foreground);
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

    /* A phone's scene is too short to carry text over it: the caption
       follows it instead. */
    .scene-caption {
      position: static;
      max-width: none;
      padding: var(--space-4) 0 0;
      background: none;
    }
  }
</style>
