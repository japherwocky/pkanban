<script>
  import {
    clampColumnWidth,
    COLUMN_WIDTH_STEP,
    DEFAULT_COLUMN_WIDTH,
    MAX_COLUMN_WIDTH,
    MIN_COLUMN_WIDTH,
  } from './columnWidths.js';

  // The strip on a column's right edge, in the gap before the next column.
  // Drag it, or focus it and use the arrow keys (Shift for bigger steps, Home
  // and End for the limits); a double-click puts the default back. onresize
  // fires as the width changes and oncommit once it settles, which is when
  // the board saves it.
  let { width, label, onresize, oncommit } = $props();

  let drag = $state(null);

  function set(next) {
    next = clampColumnWidth(next);
    onresize(next);
    oncommit(next);
  }

  // Every listener is native, on the handle itself. svelte-dnd-action picks a
  // column up from a native mousedown, touchstart or Enter/Space keydown
  // anywhere inside it, and Svelte delegates its own event attributes to the
  // root -- too late to stop any of those from reaching the column first.
  function handle(node) {
    function down(e) {
      if (e.button !== 0) return;
      // Also cancels the mousedown that would follow: no text selection, and
      // no column drag in browsers that never send one.
      e.preventDefault();
      node.setPointerCapture?.(e.pointerId);
      drag = { pointerId: e.pointerId, startX: e.clientX, startWidth: width, width };
    }

    function move(e) {
      if (e.pointerId !== drag?.pointerId) return;
      drag.width = clampColumnWidth(drag.startWidth + e.clientX - drag.startX);
      onresize(drag.width);
    }

    function up(e) {
      if (e.pointerId !== drag?.pointerId) return;
      const { width: final, startWidth } = drag;
      drag = null;
      if (final !== startWidth) oncommit(final);
    }

    function key(e) {
      e.stopPropagation();
      const step = e.shiftKey ? COLUMN_WIDTH_STEP * 5 : COLUMN_WIDTH_STEP;
      const next = {
        ArrowLeft: width - step,
        ArrowRight: width + step,
        Home: MIN_COLUMN_WIDTH,
        End: MAX_COLUMN_WIDTH,
      }[e.key];
      if (next === undefined) return;
      e.preventDefault();
      set(next);
    }

    const stop = (e) => e.stopPropagation();
    const listeners = [
      ['pointerdown', down],
      ['pointermove', move],
      ['pointerup', up],
      ['pointercancel', up],
      ['keydown', key],
      ['mousedown', stop],
      ['touchstart', stop],
    ];
    for (const [type, fn] of listeners) node.addEventListener(type, fn, { passive: type === 'touchstart' });
    return () => {
      for (const [type, fn] of listeners) node.removeEventListener(type, fn);
    };
  }
</script>

<!-- A focusable separator is ARIA's window splitter: it reports its value
     and takes arrow keys, which makes it a widget, not decoration. -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
  class="column-resize-handle"
  class:dragging={drag}
  role="separator"
  aria-orientation="vertical"
  aria-label={label}
  aria-valuenow={width}
  aria-valuemin={MIN_COLUMN_WIDTH}
  aria-valuemax={MAX_COLUMN_WIDTH}
  tabindex="0"
  title="Drag to resize, double-click to reset"
  ondblclick={() => set(DEFAULT_COLUMN_WIDTH)}
  {@attach handle}
></div>

<style>
  /* As wide as the gap between columns (.columns-container's gap), and
     sitting in it, so it never covers a column's own scrollbar. */
  .column-resize-handle {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 100%;
    width: var(--space-4);
    cursor: col-resize;
    touch-action: none;
    z-index: 1;
  }

  .column-resize-handle::after {
    content: '';
    position: absolute;
    top: var(--space-2);
    bottom: var(--space-2);
    left: 50%;
    width: 2px;
    transform: translateX(-50%);
    border-radius: 1px;
    background: transparent;
    transition: background-color var(--transition-fast);
  }

  /* Keyboard focus also gets the app's own :focus-visible ring. */
  .column-resize-handle:hover::after,
  .column-resize-handle:focus-visible::after,
  .column-resize-handle.dragging::after {
    background: var(--color-primary);
  }
</style>
