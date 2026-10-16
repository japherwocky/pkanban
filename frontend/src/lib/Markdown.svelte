<script>
  // Card Markdown, rendered and sanitised by markdown.js. The only place card
  // text becomes HTML: anything else that shows it does so as plain text.
  import { renderMarkdown } from './markdown.js';

  let { text = '' } = $props();

  let html = $derived(renderMarkdown(text));
</script>

<!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitised by renderMarkdown -->
<div class="markdown">{@html html}</div>

<style>
  /* Sized for a card, not a document: headings step down from the modal's own
     title rather than competing with it. :global() because {@html} content
     is outside this component's scoped styles. */
  .markdown {
    color: var(--color-foreground);
    line-height: var(--leading-normal);
    overflow-wrap: anywhere;
  }

  .markdown :global(:is(p, ul, ol, pre, blockquote, table, h1, h2, h3, h4, h5, h6)) {
    margin: 0 0 var(--space-3) 0;
  }

  .markdown :global(> :last-child) {
    margin-bottom: 0;
  }

  .markdown :global(:is(h1, h2, h3, h4, h5, h6)) {
    font-weight: 700;
    line-height: var(--leading-tight);
    margin-top: var(--space-4);
  }

  .markdown :global(> :first-child) {
    margin-top: 0;
  }

  .markdown :global(h1) { font-size: var(--text-lg); }
  .markdown :global(h2) { font-size: var(--text-base); }
  .markdown :global(:is(h3, h4, h5, h6)) {
    font-size: var(--text-sm);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
    color: var(--color-muted-foreground);
  }

  /* Tailwind's preflight strips list markers; cards use them constantly. */
  .markdown :global(ul) { list-style: disc; padding-left: var(--space-5); }
  .markdown :global(ol) { list-style: decimal; padding-left: var(--space-5); }
  .markdown :global(li + li) { margin-top: var(--space-1); }
  .markdown :global(li > :is(ul, ol)) { margin: var(--space-1) 0 0 0; }
  .markdown :global(li:has(> input[type='checkbox'])) { list-style: none; margin-left: calc(-1 * var(--space-5)); }
  .markdown :global(input[type='checkbox']) { margin: 0 var(--space-2) 0 0; vertical-align: middle; }

  .markdown :global(a) {
    color: var(--color-primary);
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .markdown :global(code) {
    font-family: var(--font-mono);
    font-size: 0.9em;
    background: var(--color-code-bg);
    color: var(--color-code-fg);
    padding: 0.1em 0.35em;
    border-radius: var(--radius-sm);
  }

  .markdown :global(pre) {
    background: var(--color-code-bg);
    color: var(--color-code-fg);
    padding: var(--space-3);
    border-radius: var(--radius-md);
    overflow-x: auto;
  }

  .markdown :global(pre code) {
    background: none;
    padding: 0;
    font-size: var(--text-sm);
    overflow-wrap: normal;
  }

  .markdown :global(blockquote) {
    border-left: 3px solid var(--color-border-strong);
    padding-left: var(--space-3);
    color: var(--color-muted-foreground);
  }

  .markdown :global(hr) {
    border: none;
    border-top: 1px solid var(--color-border);
    margin: var(--space-4) 0;
  }

  /* display: block so a wide table scrolls inside the card instead of
     widening the modal. */
  .markdown :global(table) {
    display: block;
    overflow-x: auto;
    border-collapse: collapse;
    font-size: var(--text-sm);
  }

  .markdown :global(:is(th, td)) {
    border: 1px solid var(--color-border);
    padding: var(--space-1) var(--space-2);
    text-align: left;
  }

  .markdown :global(th) {
    background: var(--color-surface);
    font-weight: 700;
  }
</style>
