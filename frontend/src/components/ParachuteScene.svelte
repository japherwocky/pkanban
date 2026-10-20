<script>
  // Cards parachuting onto a kanban board, in 3D. The scene itself is
  // lib/parachutes/scene.js; this mounts it and keeps it polite:
  //
  //   - three.js is imported here, on mount, so it is its own chunk and only
  //     pages that show the scene download it;
  //   - colors come from the theme tokens and follow a theme switch;
  //   - it stops drawing when scrolled out of view or the tab is hidden;
  //   - with reduced motion it draws one still frame and never animates;
  //   - without WebGL it renders nothing, and the page around it is unchanged.
  //
  // It takes the size its container gives it. `height` is a CSS length.
  import { onMount } from 'svelte';

  let { height = '520px', label = 'Cards drifting down onto a kanban board under little parachutes, then moving from Todo to Done.' } = $props();

  let container = $state();
  let canvas = $state();
  let probe = $state();
  let failed = $state(false);

  const TOKENS = {
    background: '--color-background',
    surface: '--color-surface',
    card: '--color-card',
    ink: '--color-foreground',
    muted: '--color-muted-foreground',
    primary: '--color-primary',
    accent: '--color-accent',
    border: '--color-border',
  };

  // Resolved through a hidden probe element rather than read off the custom
  // properties, which can hold var() or color-mix() that three cannot parse.
  function readPalette() {
    const palette = {};
    for (const [name, token] of Object.entries(TOKENS)) {
      probe.style.color = `var(${token})`;
      palette[name] = getComputedStyle(probe).color;
    }
    return palette;
  }

  onMount(() => {
    let scene;
    let disposed = false;
    let visible = false;
    const cleanups = [];
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

    const run = () => {
      if (!scene) return;
      if (visible && !document.hidden) scene.play();
      else scene.pause();
    };

    (async () => {
      const { createParachuteScene } = await import('../lib/parachutes/scene.js');
      // The card faces are drawn on canvases in Ubuntu; draw them in it.
      await document.fonts?.ready;
      if (disposed) return;
      try {
        scene = createParachuteScene(canvas, { palette: readPalette(), reducedMotion });
      } catch (error) {
        console.warn('Parachute scene unavailable:', error);
        failed = true;
        return;
      }

      const resize = new ResizeObserver(() => scene.resize(container.clientWidth, container.clientHeight));
      resize.observe(container);
      cleanups.push(() => resize.disconnect());

      const view = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        run();
      });
      view.observe(container);
      cleanups.push(() => view.disconnect());

      document.addEventListener('visibilitychange', run);
      cleanups.push(() => document.removeEventListener('visibilitychange', run));

      // theme.js switches themes by toggling a class on <html>.
      const theme = new MutationObserver(() => scene.setPalette(readPalette()));
      theme.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
      cleanups.push(() => theme.disconnect());

      const onPointer = (event) => {
        const rect = container.getBoundingClientRect();
        scene.setPointer(
          ((event.clientX - rect.left) / rect.width) * 2 - 1,
          -(((event.clientY - rect.top) / rect.height) * 2 - 1),
        );
      };
      const onLeave = () => scene.setPointer(0, 0);
      container.addEventListener('pointermove', onPointer);
      container.addEventListener('pointerleave', onLeave);
      cleanups.push(() => {
        container.removeEventListener('pointermove', onPointer);
        container.removeEventListener('pointerleave', onLeave);
      });
    })();

    return () => {
      disposed = true;
      cleanups.forEach((fn) => fn());
      scene?.dispose();
    };
  });
</script>

{#if !failed}
  <div class="parachute-scene" bind:this={container} style="height: {height}" role="img" aria-label={label}>
    <canvas bind:this={canvas}></canvas>
    <span class="probe" bind:this={probe} aria-hidden="true"></span>
  </div>
{/if}

<style>
  .parachute-scene {
    position: relative;
    width: 100%;
    overflow: hidden;
    background: var(--color-background);
  }

  .probe {
    display: none;
  }

  canvas {
    display: block;
    width: 100%;
    height: 100%;
  }
</style>
