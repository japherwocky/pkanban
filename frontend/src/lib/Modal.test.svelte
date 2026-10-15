<script>
  // Modal takes its body as a `children` snippet, which cannot be passed
  // through @testing-library's plain props object -- this harness supplies one.
  import Modal from './Modal.svelte';

  let { open, onClose, title = undefined, titleBadge = undefined, wide = false, preferEdit = false } = $props();
</script>

<Modal {open} {onClose} {title} {titleBadge} {wide}>
  {#snippet children()}
    <p><a href="https://example.com">a link in the text</a></p>
    <form>
      <button type="button" data-autofocus={preferEdit || undefined}>Edit</button>
      <button type="submit">Save</button>
    </form>
  {/snippet}
</Modal>
