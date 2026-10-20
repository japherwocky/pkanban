<script>
  import Logo from '../lib/Logo.svelte';

  let hoveredBox = $state(null);
  let mouseX = $state(0);
  let mouseY = $state(0);

  // Compatibility, not partnership. These are AI tools the reader already
  // uses, named in plain text so they recognize one -- pkanban has no
  // integration code for any of them.
  //
  // No logos, still. Checked 2026-10-20: Anthropic, OpenAI, Google and the
  // Linux Foundation (Goose) all want a logo approved first, and OpenAI's
  // brand page says an app's branding should carry none of theirs. A name,
  // used accurately, is fine. So each name gets one of our own icons, for how
  // pkanban reaches it, and the strip still looks like the logo row everyone
  // expects. (This list used to be "Bash script", "Cron job" and the like;
  // true, but invisible to the people the page is now for. See MARKETING.md
  // section 2.)
  //
  // Every entry is an app where pkanban works today: the agents by running
  // its commands, and the Claude and ChatGPT chat apps through the MCP
  // connector (/connect/claude, /docs/mcp).
  //
  //   chat      a chat app, through the connector
  //   terminal  an agent that runs commands in a terminal
  //   editor    an agent that lives in a code editor
  const agents = [
    { name: 'Claude', kind: 'chat' },
    { name: 'ChatGPT', kind: 'chat' },
    { name: 'Claude Code', kind: 'terminal' },
    { name: 'Codex', kind: 'terminal' },
    { name: 'opencode', kind: 'terminal' },
    { name: 'Cursor', kind: 'editor' },
    { name: 'Gemini CLI', kind: 'terminal' },
    { name: 'GitHub Copilot', kind: 'editor' },
    { name: 'Cline', kind: 'editor' },
    { name: 'Goose', kind: 'terminal' },
  ];

  function handleMouseMove(event, boxId) {
    if (hoveredBox === boxId) {
      const rect = event.currentTarget.getBoundingClientRect();
      mouseX = ((event.clientX - rect.left) / rect.width) * 100;
      mouseY = ((event.clientY - rect.top) / rect.height) * 100;
    }
  }
</script>

{#snippet agentIcon(kind)}
  <svg class="logo-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    {#if kind === 'chat'}
      <path d="M5 4.5h14a1.5 1.5 0 011.5 1.5v9a1.5 1.5 0 01-1.5 1.5h-8l-4.5 3.5v-3.5H5A1.5 1.5 0 013.5 15V6A1.5 1.5 0 015 4.5z"/>
      <path d="M8 9.5h8"/>
      <path d="M8 12.5h5"/>
    {:else if kind === 'terminal'}
      <rect x="3" y="4.5" width="18" height="15" rx="1.5"/>
      <path d="M7 9.5l3 2.5-3 2.5"/>
      <path d="M12.5 15h4.5"/>
    {:else}
      <rect x="3" y="4.5" width="18" height="15" rx="1.5"/>
      <path d="M3 8.5h18"/>
      <path d="M10 11.5l-2.5 2.5 2.5 2.5"/>
      <path d="M14 11.5l2.5 2.5-2.5 2.5"/>
    {/if}
  </svg>
{/snippet}

<section class="features-section">
  <div class="features-header">
    <h2>Engineered for Autonomy</h2>
    <p>Every design decision optimized for AI agents and their human overseers.</p>
  </div>

  <div class="bento-grid">
    <!-- Box 1: Zero-Config Handshake (Large) -->
    <div
      class="bento-box box-large"
      class:hovered={hoveredBox === 1}
      onmouseenter={() => hoveredBox = 1}
      onmouseleave={() => hoveredBox = null}
      onmousemove={(e) => handleMouseMove(e, 1)}
      role="group"
      aria-label="Zero-Config Handshake feature"
    >
      <div class="box-content">
        <div class="box-header">
          <span class="box-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <rect x="5" y="11" width="14" height="9" rx="2"/>
              <path d="M8 11V7a4 4 0 018 0v4"/>
              <circle cx="12" cy="15" r="1.25" fill="currentColor" stroke="none"/>
            </svg>
          </span>
          <h3>Zero-Config Handshake</h3>
        </div>
        <p class="box-description">Your agent asks to sign in, you click Approve. No password ever touches the terminal.</p>

        <div class="code-panel">
          <div class="code-line">
            <span class="code-comment"># Agent: ask to sign in</span>
          </div>
          <div class="code-line">
            <span class="code-prompt">$</span> pkanban login <span class="code-string">--no-wait</span>
          </div>
          <div class="code-line code-indent">
            <span class="code-comment"># Prints a link: /device?code=BCDF-GHJK</span>
          </div>
          <div class="code-line" style="margin-top: 8px;">
            <span class="code-comment"># Human: open the link, click Approve</span>
          </div>
          <div class="code-line" style="margin-top: 8px;">
            <span class="code-comment"># Agent: finish, then just run commands</span>
          </div>
          <div class="code-line">
            <span class="code-prompt">$</span> pkanban login
          </div>
          <div class="code-line">
            <span class="code-prompt">$</span> pkanban board list
          </div>
          <div class="code-line code-indent">
            <span class="code-comment"># Signed in from now on, with a key you can revoke</span>
          </div>
        </div>
      </div>

      <div class="glow-spot" style="left: {mouseX}%; top: {mouseY}%"></div>
    </div>

    <!-- Box 2: LLM-Optimized Structure (Tall) -->
    <div
      class="bento-box box-tall"
      class:hovered={hoveredBox === 2}
      onmouseenter={() => hoveredBox = 2}
      onmouseleave={() => hoveredBox = null}
      onmousemove={(e) => handleMouseMove(e, 2)}
      role="group"
      aria-label="LLM-Optimized Structure feature"
    >
      <div class="box-content">
        <div class="box-header">
          <span class="box-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="5.5" r="2.25"/>
              <circle cx="6" cy="18.5" r="2.25"/>
              <circle cx="18" cy="18.5" r="2.25"/>
              <path d="M12 7.75v3.5M12 11.25L6.6 16.6M12 11.25l5.4 5.35"/>
            </svg>
          </span>
          <h3>LLM-Optimized Structure</h3>
        </div>
        <p class="box-description">A hierarchy designed for context windows, not just human eyes.</p>

        <div class="structure-display">
          <div class="json-tree">
            <div class="json-line"><span class="json-brace">{'{'}</span></div>
            <div class="json-line code-indent"><span class="json-key">"id"</span>: <span class="json-number">1</span>,</div>
            <div class="json-line code-indent"><span class="json-key">"name"</span>: <span class="json-string">"Sprint-24"</span>,</div>
            <div class="json-line code-indent"><span class="json-key">"columns"</span>: [</div>
            <div class="json-line code-indent-2"><span class="json-brace">{'{'}</span></div>
            <div class="json-line code-indent-3"><span class="json-key">"id"</span>: <span class="json-number">1</span>,</div>
            <div class="json-line code-indent-3"><span class="json-key">"name"</span>: <span class="json-string">"Todo"</span>,</div>
            <div class="json-line code-indent-3"><span class="json-key">"position"</span>: <span class="json-number">0</span>,</div>
            <div class="json-line code-indent-3"><span class="json-key">"cards"</span>: [</div>
            <div class="json-line code-indent-4"><span class="json-brace">{'{'}</span> <span class="json-key">"id"</span>: <span class="json-number">1</span>, <span class="json-key">"title"</span>: <span class="json-string">"Fix bug"</span> ... <span class="json-brace">{'}'}</span></div>
            <div class="json-line code-indent-3"><span class="json-brace">]</span></div>
            <div class="json-line code-indent-2"><span class="json-brace">{'}'}</span></div>
            <div class="json-line code-indent"><span class="json-brace">]</span>,</div>
            <div class="json-line code-indent"><span class="json-key">"owner_id"</span>: <span class="json-number">1</span></div>
            <div class="json-line"><span class="json-brace">{'}'}</span></div>
          </div>

          <div class="robot-scanner" class:scanning={hoveredBox === 2}>
            <svg viewBox="0 0 100 100" class="robot-icon">
              <rect x="20" y="30" width="60" height="40" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
              <rect x="35" y="15" width="30" height="20" rx="3" fill="none" stroke="currentColor" stroke-width="2"/>
              <circle cx="50" cy="50" r="8" fill="none" stroke="currentColor" stroke-width="2"/>
              <line x1="50" y1="50" x2="50" y2="70" stroke="currentColor" stroke-width="2" class="scanner-beam"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="glow-spot" style="left: {mouseX}%; top: {mouseY}%"></div>
    </div>

    <!-- Box 3: Works where your Agents live (Wide). No hover effect: the
         strip is already moving, and the lift, glow and blue on top of it
         were too much. -->
    <div
      class="bento-box box-wide box-static"
      role="group"
      aria-label="Works with the AI you already use"
    >
      <div class="box-content">
        <div class="box-header">
          <span class="box-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9.5 14.5l5-5"/>
              <path d="M10.8 6.2l1-1a3.3 3.3 0 014.7 4.7l-1 1"/>
              <path d="M13.2 17.8l-1 1a3.3 3.3 0 01-4.7-4.7l1-1"/>
            </svg>
          </span>
          <h3>Works with the AI you already use</h3>
        </div>
        <p class="box-description">If your AI can run a command, it can use pkanban, with nothing to install on its side. If it can't, as in the Claude and ChatGPT apps, add pkanban as a connector.</p>

        <!-- Two identical groups, the track sliding left by exactly one of them,
             so the loop has no seam. The copy is hidden from screen readers:
             they get the list once, as a list. -->
        <div class="logo-marquee">
          <div class="logo-track">
            {#each [false, true] as copy (copy)}
              <ul class="logo-group" aria-hidden={copy ? 'true' : undefined}>
                {#each agents as agent (agent.name)}
                  <li class="logo-item">
                    {@render agentIcon(agent.kind)}
                    <span class="logo-text">{agent.name}</span>
                  </li>
                {/each}
                <!-- The pear is ours, so it is the one real logo in the row, in the
                     row's own color like the icons beside it. -->
                <li class="logo-item logo-item-pear">
                  <Logo size={18} showWordmark={false} mono />
                  <span class="logo-text">Anything that can run a command, you included</span>
                </li>
              </ul>
            {/each}
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<style>
  .features-section {
    max-width: 1200px;
    width: 100%;
    margin: var(--space-16) auto;
    padding: 0 var(--space-6);
  }

  .features-header {
    text-align: center;
    margin-bottom: var(--space-12);
  }

  .features-header h2 {
    font-size: var(--text-3xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-4) 0;
  }

  .features-header p {
    font-size: var(--text-lg);
    color: var(--color-muted-foreground);
    margin: 0;
  }

  .bento-grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    grid-template-rows: auto auto;
    gap: var(--space-5);
  }

  .bento-box {
    position: relative;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--space-6);
    overflow: hidden;
    transition: border-color var(--transition-slow), box-shadow var(--transition-slow), transform var(--transition-slow);
    cursor: pointer;
  }

  .bento-box:hover {
    border-color: var(--color-primary);
    transform: translateY(-4px);
    box-shadow: 0 20px 40px color-mix(in srgb, var(--color-primary) 10%, transparent);
  }

  .bento-box.hovered {
    border-color: var(--color-primary);
  }

  .bento-box.box-static {
    cursor: default;
  }

  .bento-box.box-static:hover {
    border-color: var(--color-border);
    transform: none;
    box-shadow: none;
  }

  .glow-spot {
    position: absolute;
    width: 200px;
    height: 200px;
    background-color: color-mix(in srgb, var(--color-primary) 7%, transparent);
    pointer-events: none;
    transform: translate(-50%, -50%);
    transition: opacity var(--transition-normal);
    opacity: 0;
  }

  .bento-box.hovered .glow-spot {
    opacity: 1;
  }

  .box-content {
    position: relative;
    z-index: 1;
  }

  .box-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .box-icon {
    display: inline-flex;
    color: var(--color-primary);
  }

  .box-icon svg {
    width: 24px;
    height: 24px;
  }

  .box-header h3 {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0;
  }

  .box-description {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    margin: 0 0 var(--space-6) 0;
    line-height: 1.6;
  }

  /* Box Large */
  .box-large {
    grid-column: span 8;
    grid-row: span 1;
  }

  /* Box Tall */
  .box-tall {
    grid-column: span 4;
    grid-row: span 2;
  }

  /* Box Wide */
  .box-wide {
    grid-column: span 8;
    grid-row: span 1;
  }

  /* Code Panel Styles */
  .code-panel {
    background: var(--color-code-bg);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.6;
  }

  .code-line {
    color: var(--color-muted-foreground);
  }

  .code-indent {
    padding-left: var(--space-6);
  }

  .code-indent-2 {
    padding-left: var(--space-12);
  }

  .code-indent-3 {
    padding-left: 72px;
  }

  .code-indent-4 {
    padding-left: var(--space-24);
  }

  .code-string { color: var(--color-success); }
  .code-comment { color: var(--color-muted-foreground); opacity: 0.7; }
  .code-prompt { color: var(--color-success); font-weight: 700; margin-right: var(--space-2); }

  /* JSON Tree Styles */
  .structure-display {
    display: flex;
    gap: var(--space-5);
    align-items: flex-start;
  }

  .json-tree {
    flex: 1;
    background: var(--color-code-bg);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    font-family: var(--font-mono);
    /* Matches .code-panel's size, not a smaller one: this block exists to
       prove the data model is legible, and Ubuntu Mono is weak enough at
       --text-xs (12px) that it undercut its own point. */
    font-size: var(--text-sm);
    line-height: 1.8;
  }

  .json-line { color: var(--color-muted-foreground); }
  .json-brace { color: var(--color-muted-foreground); }
  .json-key { color: var(--syntax-type); }
  .json-string { color: var(--color-success); }
  .json-number { color: var(--syntax-number); }

  .robot-scanner {
    width: 60px;
    height: 60px;
    color: var(--color-muted-foreground);
    transition: color var(--transition-slow);
  }

  .robot-scanner.scanning {
    color: var(--color-primary);
  }

  .robot-icon {
    width: 100%;
    height: 100%;
  }

  .scanner-beam {
    opacity: 0;
    transition: opacity var(--transition-slow);
  }

  .robot-scanner.scanning .scanner-beam {
    opacity: 1;
    animation: scan 1s ease-in-out infinite;
  }

  @keyframes scan {
    0%, 100% { transform: translateY(0); opacity: 0.5; }
    50% { transform: translateY(20px); opacity: 1; }
  }

  /* Logo Marquee Styles */
  .logo-marquee {
    overflow: hidden;
    padding: var(--space-4) 0;
    /* Names fade in and out at the edges instead of being cut off. */
    mask-image: linear-gradient(to right, transparent, black 8%, black 92%, transparent);
  }

  /* Always moving, and still under the pointer so a name can be read. It used
     to move only while hovered, which nobody would guess to do. */
  .logo-track {
    display: flex;
    width: max-content;
    animation: scroll 40s linear infinite;
  }

  .logo-marquee:hover .logo-track {
    animation-play-state: paused;
  }

  /* The spacing is padding on each group, not a gap between them, so one
     group plus its spacing is exactly half the track and -50% lands the
     second group where the first began. With a gap the loop jumped. */
  .logo-group {
    display: flex;
    gap: var(--space-8);
    padding: 0 var(--space-8) 0 0;
    margin: 0;
    list-style: none;
  }

  @keyframes scroll {
    from { transform: translateX(0); }
    to { transform: translateX(-50%); }
  }

  /* Still, and every name visible: wrapped, once. */
  @media (prefers-reduced-motion: reduce) {
    .logo-marquee {
      mask-image: none;
    }

    .logo-track {
      width: auto;
      animation: none;
    }

    .logo-group {
      flex-wrap: wrap;
      justify-content: center;
      gap: var(--space-3);
      padding: 0;
    }

    .logo-group[aria-hidden='true'] {
      display: none;
    }
  }

  .logo-item {
    flex-shrink: 0;
    padding: var(--space-3) var(--space-6);
    background: color-mix(in srgb, var(--color-foreground) 3%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-foreground) 6%, transparent);
    border-radius: var(--radius-lg);
    color: var(--color-muted-foreground);
    font-weight: 500;
    font-size: var(--text-sm);
    transition: background-color var(--transition-slow), border-color var(--transition-slow), color var(--transition-slow);
  }

  .logo-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .logo-icon {
    flex-shrink: 0;
    width: 18px;
    height: 18px;
  }

  .logo-text {
    white-space: nowrap;
  }

  /* Responsive */
  @media (max-width: 1024px) {
    .box-large,
    .box-wide {
      grid-column: span 12;
    }

    .box-tall {
      grid-column: span 12;
      grid-row: span 1;
    }

    .structure-display {
      flex-direction: column;
      align-items: center;
    }
  }

  @media (max-width: 640px) {
    .features-section {
      padding: 0 var(--space-4);
    }

    .features-header h2 {
      font-size: var(--text-2xl);
    }

    .features-header p {
      font-size: var(--text-base);
    }

    .bento-grid {
      gap: var(--space-4);
    }

    .bento-box {
      padding: var(--space-5);
    }

    .box-header h3 {
      font-size: var(--text-lg);
    }

    .code-panel,
    .json-tree {
      font-size: var(--text-xs);
    }
  }
</style>
