<script>
  import { link } from 'svelte-routing';

  // Sizing knobs. Every page that renders this wants a slightly different
  // scale -- the landing page gets the full-size version, Login gets a
  // compact one under the form -- so the dimensions come in as props rather
  // than being forked into per-page copies of the markup.
  let {
    marginTop = 'var(--space-16)',
    // Off on the login page, where "already have an account?" is noise --
    // they are looking at the login form.
    showLoginLink = true,
    maxWidth = null,
    borderRadius = 'var(--radius-lg)',
    padding = 'var(--space-12)',
    h2FontSize = 'var(--text-2xl)',
    descFontSize = 'var(--text-lg)',
    subtextFontSize = 'var(--text-sm)',
    mobilePadding = 'var(--space-6)',
    mobileH2FontSize = 'var(--text-xl)',
    mobileDescFontSize = 'var(--text-base)',
    compactPadding = 'var(--space-4)',
    compactH2FontSize = 'var(--text-xl)',
    compactDescFontSize = 'var(--text-sm)'
  } = $props();
</script>

<div
  class="signup-cta"
  style="
    --margin-top: {marginTop};
    --max-width: {maxWidth ?? 'none'};
    --border-radius: {borderRadius};
    --padding: {padding};
    --h2-font-size: {h2FontSize};
    --desc-font-size: {descFontSize};
    --subtext-font-size: {subtextFontSize};
    --mobile-padding: {mobilePadding};
    --mobile-h2-font-size: {mobileH2FontSize};
    --mobile-desc-font-size: {mobileDescFontSize};
    --compact-padding: {compactPadding};
    --compact-h2-font-size: {compactH2FontSize};
    --compact-desc-font-size: {compactDescFontSize};
  "
>
  <div class="cta-background"></div>
  <div class="cta-content">
    <h2>Initialize Your Workspace</h2>
    <p class="cta-description">
      Create an account and start orchestrating agents in minutes.
    </p>

    <a href="/signup" use:link class="cta-button">
      <span class="button-prompt">$</span>
      <span class="button-text">create_account</span>
    </a>

    <p class="cta-subtext">
      {#if showLoginLink}
        Free to start. Already have an account?
        <a href="/login" use:link class="inline-link">Log in</a>.
      {:else}
        Free to start.
      {/if}
    </p>
  </div>
</div>

<style>
  .signup-cta {
    position: relative;
    margin: var(--margin-top, 4rem) auto 0 auto;
    width: 100%;
    max-width: var(--max-width, none);
    overflow: hidden;
    border-radius: var(--border-radius, var(--radius-lg));
    border: 1px solid var(--color-border);
  }

  .cta-background {
    position: absolute;
    inset: 0;
    background-color: var(--color-surface);
  }

  .cta-content {
    position: relative;
    z-index: 1;
    text-align: center;
    padding: var(--padding, 3rem);
  }

  .signup-cta h2 {
    font-size: var(--h2-font-size, var(--text-2xl));
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-3) 0;
  }

  .cta-description {
    color: var(--color-muted-foreground);
    font-size: var(--desc-font-size, var(--text-lg));
    margin: 0 0 var(--space-8) 0;
    line-height: var(--leading-relaxed);
  }

  .cta-button {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    background-color: var(--color-primary);
    border: 1px solid var(--color-primary);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-6);
    margin-bottom: var(--space-6);
    cursor: pointer;
    text-decoration: none;
    transition: background-color var(--transition-fast), border-color var(--transition-fast);
  }

  .cta-button:hover {
    background-color: color-mix(in srgb, var(--color-primary) 86%, var(--color-foreground));
    border-color: color-mix(in srgb, var(--color-primary) 86%, var(--color-foreground));
  }

  .cta-button:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 40%, transparent);
  }

  .button-prompt,
  .button-text {
    color: var(--color-primary-foreground);
    font-family: var(--font-mono);
    font-weight: 500;
    white-space: nowrap;
  }

  .button-prompt {
    font-size: var(--text-sm);
    opacity: 0.8;
  }

  .button-text {
    font-size: var(--text-sm);
  }

  .cta-subtext {
    color: var(--color-muted-foreground);
    font-size: var(--subtext-font-size, 0.875rem);
    margin: 0;
  }

  .inline-link {
    color: var(--color-primary);
    text-decoration: none;
  }

  .inline-link:hover {
    text-decoration: underline;
  }

  @media (max-width: 640px) {
    .cta-content {
      padding: var(--mobile-padding, 1.5rem);
    }

    .signup-cta h2 {
      font-size: var(--mobile-h2-font-size, 1.5rem);
    }

    .cta-description {
      font-size: var(--mobile-desc-font-size, 1rem);
    }

    .cta-button {
      width: 100%;
      justify-content: center;
    }
  }

  @media (max-width: 480px) {
    .cta-content {
      padding: var(--compact-padding, 1rem);
    }

    .signup-cta h2 {
      font-size: var(--compact-h2-font-size, 1.25rem);
    }

    .cta-description {
      font-size: var(--compact-desc-font-size, 0.875rem);
    }
  }
</style>
