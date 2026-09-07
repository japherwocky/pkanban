<script>
  import { navigate } from 'svelte-routing';
  import Logo from '../lib/Logo.svelte';
</script>

<div class="not-found">
  <Logo size={40} />
  <h1>404</h1>
  <p>Page not found</p>
  <button onclick={() => navigate('/boards')}>Go to Boards</button>
</div>

<style>
  .not-found {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    gap: var(--space-4);
    text-align: center;
  }

  .not-found h1 {
    font-size: var(--text-4xl);
    font-weight: 700;
    color: var(--color-primary);
    margin: 0;
  }

  .not-found p {
    font-size: var(--text-lg);
    color: var(--color-muted-foreground);
    margin: 0;
  }

  button {
    padding: var(--space-3) var(--space-6);
    font-size: var(--text-base);
    font-weight: 500;
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast), box-shadow var(--transition-fast);
    background: var(--color-primary);
    color: var(--color-primary-foreground);
    border: none;
  }

  button:hover {
    opacity: 0.9;
  }
</style>
