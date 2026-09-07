<script>
  export let title = '';
  export let description = '';
</script>

<div class="page">
  <div class="page-container">
    <h1>{title}</h1>
    {#if description}
      <p class="description">{description}</p>
    {/if}

    <slot />
  </div>
</div>

<style>
  .page {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-12) var(--space-6);
  }

  .page-container {
    max-width: 700px;
    width: 100%;
  }

  h1 {
    font-size: var(--text-3xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin: 0 0 var(--space-4) 0;
    text-align: center;
  }

  .description {
    font-size: var(--text-lg);
    color: var(--color-muted-foreground);
    line-height: 1.6;
    margin: 0 0 var(--space-8) 0;
    text-align: center;
  }

  @media (max-width: 640px) {
    .page {
      padding: var(--space-8) var(--space-4);
    }
  }
</style>
