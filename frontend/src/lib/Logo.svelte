<script>
  // The pteranodon mark -- see the "Design the pteranodon mark" card on the
  // Dev board (Brand & Marketing column) for how the silhouette was chosen.
  // One source of truth: this used to be a copy-pasted generic kanban glyph
  // in both Header.svelte and Footer.svelte, which said "kanban" and had
  // nothing to do with the brand. currentColor so it inherits the theme,
  // same stroke-free filled-silhouette treatment as favicon.svg/og-image.png
  // so the mark reads identically everywhere it appears.
  let { size = 28, showWordmark = true } = $props();
</script>

<span class="logo-mark" style="--logo-size: {size}px">
  <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
    <path
      d="M 2,30 L 14,18 L 26,26 L 30,10 L 24,2 L 36,12 L 52,8 L 42,20 L 40,26 L 54,20 L 62,32 L 46,32 L 38,44 L 32,56 L 28,42 L 16,30 Z"
      fill="currentColor"
    />
  </svg>
  {#if showWordmark}
    <span class="wordmark">pkanban</span>
  {/if}
</span>

<style>
  .logo-mark {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--color-primary);
  }

  .logo-mark svg {
    flex-shrink: 0;
    width: var(--logo-size);
    height: var(--logo-size);
  }

  .wordmark {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--color-foreground);
    letter-spacing: var(--tracking-tight);
  }
</style>
