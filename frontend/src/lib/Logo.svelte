<script>
  // The pearachute logo: a pear under a parachute canopy, seen from above --
  // the "p" in pkanban. Same artwork as pearachute.com, cleaned up and cropped
  // to the disc (the original sits in the middle of a 200x200 canvas, which
  // rendered at half size here). One source of truth: src/assets/logo.svg is
  // also the favicon (see index.html).
  //
  // It's a self-contained disc with its own ink outline, so unlike the old
  // single-color mark it needs no currentColor and reads on both themes.
  let { size = 28, showWordmark = true } = $props();
  import logoUrl from '../assets/logo.svg';
</script>

<span class="logo-mark" style="--logo-size: {size}px">
  <img src={logoUrl} width={size} height={size} alt="" />
  {#if showWordmark}
    <span class="wordmark">pkanban</span>
  {/if}
</span>

<style>
  .logo-mark {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }

  .logo-mark img {
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
