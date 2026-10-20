<script>
  // The pearachute logo: a pear under a parachute canopy, seen from above --
  // the "p" in pkanban. Same artwork as pearachute.com, cleaned up and cropped
  // to the disc (the original sits in the middle of a 200x200 canvas, which
  // rendered at half size here). One source of truth: src/assets/logo.svg is
  // also the favicon (see index.html).
  //
  // Full color by default: a self-contained disc with its own ink outline,
  // which reads on both themes as it is. `mono` draws the same pear in one
  // color instead -- the current text color, so it can be recolored like any
  // icon. That is logo-mono.svg, the ink alone, used as a mask over
  // currentColor rather than inlined, so it stays one file.
  let { size = 28, showWordmark = true, mono = false } = $props();
  import logoUrl from '../assets/logo.svg';
  import monoUrl from '../assets/logo-mono.svg';
</script>

<span class="logo-mark" style="--logo-size: {size}px">
  {#if mono}
    <span class="logo-mono" style="--logo-mono: url({monoUrl})" aria-hidden="true"></span>
  {:else}
    <img src={logoUrl} width={size} height={size} alt="" />
  {/if}
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

  .logo-mark img,
  .logo-mono {
    flex-shrink: 0;
    width: var(--logo-size);
    height: var(--logo-size);
  }

  .logo-mono {
    display: inline-block;
    background-color: currentColor;
    -webkit-mask: var(--logo-mono) center / contain no-repeat;
    mask: var(--logo-mono) center / contain no-repeat;
  }

  .wordmark {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--color-foreground);
    letter-spacing: var(--tracking-tight);
  }
</style>
