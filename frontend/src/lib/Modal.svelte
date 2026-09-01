<script>

  let { open = false, onClose, title = 'Dialog', titleBadge = '', wide = false, children } = $props();

  let modalRef = $state();
  let previousActiveElement = null;

  // Handle keyboard navigation
  function handleKeydown(e) {
    if (!open) return;

    // ESC to close
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
      return;
    }

    // Tab trapping - keep focus within modal
    if (e.key === 'Tab') {
      const focusableElements = modalRef.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        // Shift + Tab
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        // Tab
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    }
  }

  // Handle backdrop click
  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  // Focus management
  $effect(() => {
    if (open) {
      // Save previous focused element
      previousActiveElement = document.activeElement;

      // Focus first focusable element in modal
      setTimeout(() => {
        const focusableElements = modalRef?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements && focusableElements.length > 0) {
          focusableElements[0].focus();
        }
      }, 0);

      // Add keyboard event listener
      document.addEventListener('keydown', handleKeydown);

      // Prevent body scroll
      document.body.style.overflow = 'hidden';
    } else {
      // Restore focus to previous element
      if (previousActiveElement) {
        setTimeout(() => previousActiveElement.focus(), 0);
      }

      // Remove keyboard event listener
      document.removeEventListener('keydown', handleKeydown);

      // Restore body scroll
      document.body.style.overflow = '';
    }

    return () => {
      document.removeEventListener('keydown', handleKeydown);
      document.body.style.overflow = '';
    };
  });
</script>

{#if open}
  <div
    class="modal-overlay"
    role="presentation"
    onclick={handleBackdropClick}
  >
    <div
      class="modal"
      class:wide
      bind:this={modalRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <!-- The heading aria-labelledby has always pointed at. The badge's leading
           space is interpolated rather than literal because svelte trims literal
           whitespace at an {#if} boundary, which would render "Edit Card#42". -->
      <h2 id="modal-title">
        {title}{#if titleBadge}<span class="title-badge">{` ${titleBadge}`}</span>{/if}
      </h2>
      {@render children()}
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    /* No align-items/justify-content: centering comes from .modal's auto
       margins below. align-items: center clips a modal taller than the
       viewport instead of scrolling to it -- overflow above the centered
       point becomes unreachable, since a fixed, centered flex item isn't
       part of anything scrollable. auto margins center the same way when
       there's room, and fall back to flush-top-scrollable when there isn't. */
    overflow-y: auto;
    padding: var(--space-4);
    z-index: 50;
  }

  .modal {
    margin: auto;
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--space-6);
    width: 100%;
    max-width: 400px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
  }

  #modal-title {
    margin: 0 0 var(--space-5) 0;
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--color-foreground);
  }

  .title-badge {
    font-size: var(--text-base);
    font-weight: 400;
    color: var(--color-muted-foreground);
  }

  @media (min-width: 768px) {
    .modal.wide {
      max-width: 720px;
    }
  }

  :global(.modal form) {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
</style>
