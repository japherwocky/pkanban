<script>
  import PageLayout from '../lib/PageLayout.svelte';
  import SignupCTA from '../components/SignupCTA.svelte';
</script>

<PageLayout
  title="About pkanban"
  description="Building the kanban tool we wanted for orchestrating human and AI agent workflows."
>
  <div class="about-content">
    <p class="mascot-note">
      🦖 Meet our mascot: a pteranodon. She's been reviewing pull requests since the Cretaceous and hasn't found a reason to stop.
    </p>

    <section>
      <h2>Our Mission</h2>
      <p>
        Most task management tools are built for humans. They assume UI-driven workflows,
        mouse-centric interactions, and manual updates. But AI agents think differently.
        (And honestly, some of us humans prefer the keyboard too.)
      </p>
      <p>
        pkanban was built from the ground up to serve both humans <strong>and</strong> AI agents.
        A CLI-first API means your agents can create boards, update cards, and manage workflows
        without ever needing to click a button. Pixel-free productivity — that's the dream.
      </p>
    </section>

    <section>
      <h2>Why "pkanban"?</h2>
      <p>
        The "p" stands for <strong>Pearachute</strong> — our domain and freelance brand.
        And like "pterodactyl" or "ptarmigan," it's <strong>silent</strong>.
      </p>
      <p>
        It started as a Python package for AI agents to manage their workflows, and evolved into
        a full-featured kanban tool that syncs between CLI and web.
      </p>
    </section>

    <section>
      <h2>Built For</h2>
      <div class="built-for-grid">
        <div class="built-for-card">
          <h3>🤖 AI-Powered Teams</h3>
          <p>Building workflows that orchestrate humans and agents together</p>
        </div>
        <div class="built-for-card">
          <h3>⌨️ CLI Devs</h3>
          <p>Developers who prefer the terminal</p>
        </div>
        <div class="built-for-card">
          <h3>⚙️ Automation Pipelines</h3>
          <p>Task tracking for CI/CD and agent workflows without the drag</p>
        </div>
        <div class="built-for-card">
          <h3>🚀 Simplicity Seekers</h3>
          <p>Fast, focused kanban boards without the enterprise bloat</p>
        </div>
      </div>
    </section>

    <SignupCTA
      marginTop="2.5rem"
      borderRadius="12px"
      padding="2rem"
      h2FontSize="1.5rem"
      descFontSize="1rem"
      subtextFontSize="0.8125rem"
      compactPadding="1rem"
      compactH2FontSize="1.25rem"
      compactDescFontSize="0.875rem"
    />
  </div>
</PageLayout>

<style>
  .mascot-note {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    font-style: italic;
    margin-bottom: var(--space-8);
    padding: var(--space-3) var(--space-4);
    background: var(--color-muted);
    border-radius: var(--radius-lg);
    border-left: 3px solid var(--color-primary);
  }

  .about-content {
    text-align: left;
  }

  section {
    margin-bottom: var(--space-8);
  }

  h2 {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-muted-foreground);
    margin: 0 0 var(--space-6) 0;
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-variant: small-caps;
  }

  p {
    color: var(--color-muted-foreground);
    font-size: var(--text-base);
    line-height: 1.7;
    margin: 0 0 var(--space-4) 0;
  }

  ul {
    margin: 0;
    padding-left: var(--space-5);
    color: var(--color-muted-foreground);
  }

  li {
    font-size: var(--text-base);
    line-height: 1.7;
    margin-bottom: var(--space-2);
  }

  .built-for-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: var(--space-4);
  }

  .built-for-card {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--space-5);
    transition: border-color var(--transition-normal), box-shadow var(--transition-normal), transform var(--transition-normal);
  }

  .built-for-card:hover {
    border-color: var(--color-primary);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .built-for-card h3 {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-foreground);
    margin: 0 0 var(--space-2) 0;
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .built-for-card p {
    font-size: var(--text-sm);
    color: var(--color-muted-foreground);
    line-height: 1.6;
    margin: 0;
  }

  @media (max-width: 640px) {
    section {
      margin-bottom: var(--space-6);
    }

    h2 {
      font-size: var(--text-sm);
    }
  }
</style>
