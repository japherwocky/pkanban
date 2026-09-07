<script>
  import { navigate } from 'svelte-routing';
  import Logo from './Logo.svelte';

  function goTo(path) {
    navigate(path);
  }
</script>

<footer class="footer">
  <div class="footer-container">
    <!-- Brand Column -->
    <div class="footer-brand">
      <button class="logo" onclick={() => goTo('/')}>
        <Logo />
      </button>
      <p class="tagline">A kanban tool for humans and AI agents.</p>
    </div>

    <!-- Links Columns -->
    <div class="footer-links">
      <div class="link-group">
        <h4>Product</h4>
        <button onclick={() => goTo('/docs')}>Documentation</button>
        <button onclick={() => goTo('/pricing')}>Pricing</button>
      </div>

      <div class="link-group">
        <h4>Company</h4>
        <button onclick={() => goTo('/about')}>About</button>
        <button onclick={() => goTo('/contact')}>Contact</button>
      </div>

      <div class="link-group">
        <h4>Legal</h4>
        <button onclick={() => goTo('/privacy')}>Privacy</button>
        <button onclick={() => goTo('/terms')}>Terms</button>
      </div>
    </div>
  </div>

  <!-- Bottom Bar -->
  <div class="footer-bottom">
    <p>&copy; {new Date().getFullYear()} pkanban. All rights reserved.</p>
    <div class="social-links">
      <a href="https://github.com/japherwocky/pkanban" target="_blank" rel="noopener" aria-label="GitHub">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
        </svg>
      </a>
    </div>
  </div>
</footer>

<style>
  .footer {
    background: var(--color-card);
    border-top: 1px solid var(--color-border);
    margin-top: auto;
  }

  .footer-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-12) var(--space-6) var(--space-8);
    display: grid;
    gap: var(--space-8);
  }

  .footer-brand {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .logo {
    display: flex;
    align-items: center;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    transition: opacity var(--transition-fast);
  }

  .logo:hover {
    opacity: 0.8;
  }

  .tagline {
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
    line-height: 1.6;
    margin: 0;
  }

  .footer-links {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-6);
  }

  .link-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .link-group h4 {
    color: var(--color-foreground);
    font-size: var(--text-sm);
    font-weight: 600;
    margin: 0;
  }

  .link-group button {
    background: none;
    border: none;
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
    cursor: pointer;
    padding: 0;
    text-align: left;
    transition: color var(--transition-fast);
  }

  .link-group button:hover {
    color: var(--color-foreground);
    text-decoration: underline;
  }

  .footer-bottom {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-6);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    border-top: 1px solid var(--color-border);
  }

  .footer-bottom p {
    color: var(--color-muted-foreground);
    font-size: var(--text-sm);
    margin: 0;
  }

  .social-links {
    display: flex;
    gap: var(--space-4);
  }

  .social-links a {
    color: var(--color-muted-foreground);
    transition: color var(--transition-fast);
  }

  .social-links a:hover {
    color: var(--color-foreground);
  }

  @media (min-width: 640px) {
    .footer-container {
      grid-template-columns: 1fr 2fr;
    }
  }

  @media (max-width: 639px) {
    .footer-links {
      grid-template-columns: repeat(2, 1fr);
    }

    .footer-bottom {
      flex-direction: column;
      text-align: center;
    }
  }
</style>
