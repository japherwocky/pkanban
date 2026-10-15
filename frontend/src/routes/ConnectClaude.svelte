<script>
  import { navigate } from 'svelte-routing';
  import PageLayout from '../lib/PageLayout.svelte';

  // How to add pkanban to Claude as a connector (MCP, Dev #900). Written for
  // the reader MARKETING.md is for: someone who uses Claude in the chat
  // window and has never configured anything like this. The URL is this
  // server's own, so a self-hosted install shows its own address.
  //
  // Its <title> and description are the server's, in backend/pages.py.

  const ORIGIN = window.location.origin;
  const MCP_URL = `${ORIGIN}/mcp`;
  const CLAUDE_CODE_COMMAND = `claude mcp add --transport http pkanban ${MCP_URL}`;
  const AGENT_PROMPT = `Read ${ORIGIN}/agents.md and set up pkanban for me.`;

  const EXAMPLES = [
    'Make a board for the kitchen renovation with columns for Ideas, Quotes, Booked and Done.',
    "What's in progress on my Dev board?",
    'Add a card to To Do: call the plumber about the leak under the sink.',
    'Move the launch cards to Done and comment on each one with what shipped.',
  ];

  const loggedIn = typeof localStorage !== 'undefined' && !!localStorage.getItem('token');

  let copied = $state(null);
  let copyResetTimer;

  function copy(text, which) {
    navigator.clipboard.writeText(text);
    copied = which;
    clearTimeout(copyResetTimer);
    copyResetTimer = setTimeout(() => (copied = null), 2000);
  }
</script>

<PageLayout
  title="Connect pkanban to Claude"
  description="Give Claude a to-do list you can both see. It reads your boards, adds cards and moves them as it works, and you watch it happen on the board."
>
  <section aria-labelledby="steps-heading">
    <h2 id="steps-heading">Add it to Claude</h2>
    <ol class="steps">
      <li>
        In Claude, open <strong>Settings › Connectors</strong> and choose
        <strong>Add custom connector</strong>. Claude on the web and Claude
        Desktop share connectors, so you do this once.
      </li>
      <li>
        Name it <strong>pkanban</strong> and paste this URL. Leave the advanced
        settings empty.
        <div class="copy-box">
          <code>{MCP_URL}</code>
          <button class="copy" onclick={() => copy(MCP_URL, 'url')}>
            {copied === 'url' ? 'Copied' : 'Copy'}
          </button>
        </div>
      </li>
      <li>
        Click <strong>Add</strong>, then <strong>Connect</strong>. A pkanban
        page opens: sign in, or create an account, check that it says it is
        sending you back to <strong>claude.ai</strong>, and approve.
      </li>
      <li>
        Start a chat and ask. If Claude doesn't seem to know about pkanban,
        switch it on from the chat's <strong>+</strong> menu, under
        <strong>Connectors</strong>.
      </li>
    </ol>
    <p class="note">
      On a Team or Enterprise plan, an owner adds the connector for the
      organization first. Then each person connects their own pkanban account
      from Settings › Connectors.
    </p>
  </section>

  <section aria-labelledby="examples-heading">
    <h2 id="examples-heading">Then ask for things</h2>
    <ul class="examples">
      {#each EXAMPLES as example (example)}
        <li>{example}</li>
      {/each}
    </ul>
  </section>

  <section aria-labelledby="access-heading">
    <h2 id="access-heading">What Claude can do</h2>
    <p>
      It works as you: it sees the boards you can see, and your plan's limits
      apply. It can read cards and their comments, search them, create boards,
      columns and cards, edit and move cards, comment, and archive.
    </p>
    <p>
      It can't delete anything. Archiving stands in for that, and an archived
      card can be brought back. It doesn't touch your teams, sharing, API keys
      or plan.
    </p>
    <p>
      To disconnect it, revoke the key named <strong>Claude (connected app)</strong>
      under Settings › API keys, and remove the connector in Claude.
    </p>
  </section>

  <section aria-labelledby="code-heading">
    <h2 id="code-heading">Using Claude Code?</h2>
    <p>
      Claude Code can run pkanban's own commands, which is how most people use
      it there. Paste this into Claude Code:
    </p>
    <div class="copy-box">
      <code>{AGENT_PROMPT}</code>
      <button class="copy" onclick={() => copy(AGENT_PROMPT, 'prompt')}>
        {copied === 'prompt' ? 'Copied' : 'Copy'}
      </button>
    </div>
    <p>
      Or add the same connector there, then run <code>/mcp</code> in Claude Code,
      pick pkanban, and choose Authenticate:
    </p>
    <div class="copy-box">
      <code>{CLAUDE_CODE_COMMAND}</code>
      <button class="copy" onclick={() => copy(CLAUDE_CODE_COMMAND, 'command')}>
        {copied === 'command' ? 'Copied' : 'Copy'}
      </button>
    </div>
  </section>

  <section aria-labelledby="selfhost-heading">
    <h2 id="selfhost-heading">Running your own server?</h2>
    <p>
      Use its address with <code>/mcp</code> on the end. Claude connects from
      Anthropic's servers, so yours has to be reachable from the internet over
      HTTPS. Claude Code connects from your own computer and has no such limit.
    </p>
  </section>

  {#if !loggedIn}
    <div class="cta">
      <button class="primary" onclick={() => navigate('/signup')}>Create your account</button>
      <p class="note">Or create it on the way, when Claude sends you to sign in.</p>
    </div>
  {/if}
</PageLayout>

<style>
  section {
    margin-top: var(--space-10);
  }

  h2 {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-4) 0;
  }

  p {
    color: var(--color-muted-foreground);
    line-height: 1.7;
    margin: 0 0 var(--space-4) 0;
  }

  strong {
    color: var(--color-foreground);
    font-weight: 600;
  }

  code {
    font-family: var(--font-mono);
    font-size: 0.95em;
  }

  .steps {
    margin: 0;
    padding: 0;
    list-style: none;
    counter-reset: step;
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .steps li {
    counter-increment: step;
    position: relative;
    padding-left: var(--space-10);
    color: var(--color-muted-foreground);
    line-height: 1.7;
  }

  .steps li::before {
    content: counter(step);
    position: absolute;
    left: 0;
    top: 0;
    width: var(--space-8);
    height: var(--space-8);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono);
    font-weight: 700;
    color: var(--color-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .copy-box {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-top: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .copy-box code {
    flex: 1;
    min-width: 0;
    color: var(--color-foreground);
    overflow-wrap: anywhere;
  }

  .copy {
    flex-shrink: 0;
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-foreground);
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
  }

  .copy:hover {
    background: var(--color-accent);
  }

  .examples {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .examples li {
    padding: var(--space-3) var(--space-4);
    color: var(--color-foreground);
    border-left: 2px solid var(--color-primary);
    background: var(--color-card);
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
  }

  .note {
    font-size: var(--text-sm);
  }

  .steps + .note {
    margin-top: var(--space-6);
  }

  .cta {
    margin-top: var(--space-10);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
  }

  .cta .note {
    margin: 0;
  }

  button.primary {
    padding: var(--space-3) var(--space-6);
    font-size: var(--text-base);
    font-weight: 500;
    color: var(--color-primary-foreground);
    background: var(--color-primary);
    border: none;
    border-radius: var(--radius-lg);
    cursor: pointer;
  }

  button.primary:hover {
    opacity: 0.9;
  }
</style>
