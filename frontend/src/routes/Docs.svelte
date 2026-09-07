<script>
  import { onMount } from 'svelte';
  import { navigate } from 'svelte-routing';
  import { marked } from 'marked';
  import Prism from 'prismjs';
  import 'prismjs/themes/prism.css';
  import 'prismjs/components/prism-bash';
  import 'prismjs/components/prism-javascript';

  export let params = { section: 'docs' };

  let markdownContent = '';
  let htmlContent = '';
  let loading = true;
  let error = '';
  let activeSection = params.section || 'docs';

  const docsSections = [
    { id: 'docs', title: 'Documentation', path: '/docs' },
    { id: 'quickstart', title: 'Quick Start', path: '/docs/quickstart' },
    { id: 'reference', title: 'Command Reference', path: '/docs/reference' },
    { id: 'workflows', title: 'Common Workflows', path: '/docs/workflows' },
    { id: 'commands', title: 'All Commands', path: '/docs/commands' },
    { id: 'auth', title: 'Authentication', path: '/docs/auth' },
    { id: 'multi-tenant', title: 'Organizations & Teams', path: '/docs/multi-tenant' },
    { id: 'theme-system', title: 'Theme System', path: '/docs/theme-system' }
  ];

  // Configure marked options
  marked.setOptions({
    breaks: true,
    gfm: true,
    highlight: function(code, lang) {
      if (Prism.languages[lang]) {
        return Prism.highlight(code, Prism.languages[lang], lang);
      }
      return code;
    }
  });

  // Must stay in sync with anchor() in scripts/generate_cli_docs.py, which
  // emits the in-page links these ids are the targets for.
  function slugify(text) {
    return text
      .toLowerCase()
      .replace(/`/g, '')
      .replace(/[^a-z0-9 -]/g, '')
      .trim()
      .split(/\s+/)
      .join('-');
  }

  // marked doesn't emit heading ids, so in-page anchors are dead without this.
  marked.use({
    renderer: {
      heading({ tokens, depth }) {
        const content = this.parser.parseInline(tokens);
        const raw = tokens.map((t) => t.raw ?? '').join('');
        return `<h${depth} id="${slugify(raw)}">${content}</h${depth}>\n`;
      }
    }
  });

  onMount(async () => {
    await loadDocumentation(activeSection);
  });

  // Watch for section changes
  $: if (params.section !== activeSection) {
    activeSection = params.section || 'docs';
    loadDocumentation(activeSection);
  }

  function convertMarkdownLinks(markdown) {
    return markdown.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, href) => {
      if (href.startsWith('http') || href.startsWith('#')) {
        return match;
      }
      if (!href.startsWith('/')) {
        href = '/docs/' + href;
      }
      return `[${text}](${href})`;
    });
  }

  async function loadDocumentation(section) {
    loading = true;
    error = '';

    try {
      const response = await fetch(`/docs/${section}.md`);

      if (!response.ok) {
        throw new Error(`Documentation not found: ${section}`);
      }

      let rawMarkdown = await response.text();
      markdownContent = convertMarkdownLinks(rawMarkdown);
      htmlContent = marked(markdownContent);

      setTimeout(() => {
        Prism.highlightAll();
      }, 0);

    } catch (err) {
      error = `Failed to load documentation: ${err.message}`;
      htmlContent = `<h2 class="text-white text-2xl font-semibold mb-4">Documentation Not Found</h2><p class="text-slate-300">The requested documentation section does not exist.</p>`;
    }

    loading = false;
  }

  function handleSectionClick(sectionPath, sectionId) {
    navigate(sectionPath);
  }

  // Per-command pages (commands/board, commands/card, ...) keep the
  // "All Commands" nav entry highlighted.
  function isActive(sectionId) {
    return activeSection === sectionId
      || (sectionId === 'commands' && activeSection.startsWith('commands/'));
  }
</script>

<div class="docs-layout">
  <!-- Sidebar Navigation -->
  <aside class="docs-sidebar">
    <ul class="py-4 px-3 space-y-1">
      {#each docsSections as section}
        <li>
          <a
            href="{section.path}"
            class="block px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 docs-nav-link"
            class:active={isActive(section.id)}
            on:click={() => handleSectionClick(section.path, section.id)}
          >
            {section.title}
          </a>
        </li>
      {/each}
    </ul>
  </aside>

  <!-- Main Content -->
  <div class="docs-content">
    <!-- Glow effect behind title -->
    <div class="docs-title-wrapper">
      <div class="docs-title-content">
        <h1>Documentation</h1>
        <p class="docs-subtitle">Everything you need to build with pkanban</p>
      </div>
    </div>

    {#if loading}
      <div class="flex items-center justify-center min-h-[400px]">
        <div class="text-center">
          <div class="inline-flex items-center justify-center w-8 h-8 border-2 rounded-full animate-spin mb-4" style="border-color: var(--color-primary); border-top-color: transparent;"></div>
          <p style="color: var(--color-muted-foreground);">Loading documentation...</p>
        </div>
      </div>
    {:else if error}
      <div class="docs-callout docs-callout--danger">
        {error}
      </div>
    {:else}
      <!-- Terminal-style command blocks -->
      <div class="markdown-body space-y-6">
        {@html htmlContent}
      </div>
    {/if}
  </div>
</div>

<style>
  .docs-callout {
    padding: var(--space-4);
    border-radius: var(--radius-md);
    border-left: 3px solid transparent;
    font-size: var(--text-sm);
  }

  .docs-callout--danger {
    background-color: color-mix(in srgb, var(--color-error) 10%, transparent);
    border-color: var(--color-error);
    color: var(--color-error);
  }

  .docs-layout {
    display: flex;
    min-height: calc(100vh - 4rem);
    background-color: var(--color-background);
    color: var(--color-foreground);
  }

  .docs-sidebar {
    width: 16rem;
    flex-shrink: 0;
    height: calc(100vh - 4rem);
    position: sticky;
    top: 4rem;
    overflow-y: auto;
    background-color: var(--color-card);
    border-right: 1px solid var(--color-border);
  }

  .docs-content {
    flex: 1;
    padding: var(--space-8);
    max-width: 56rem;
    overflow-y: auto;
  }

  .docs-nav-link {
    color: var(--color-foreground);
  }

  .docs-nav-link:hover {
    background-color: rgba(255, 255, 255, 0.05);
  }

  .docs-nav-link.active {
    border-left: 2px solid var(--color-primary);
    color: var(--color-foreground);
    background-color: rgba(255, 255, 255, 0.05);
  }

  .docs-title-wrapper {
    position: relative;
    margin-bottom: var(--space-8);
  }

  .docs-title-content {
    position: relative;
    z-index: 1;
  }

  .docs-title-content h1 {
    font-size: var(--text-3xl);
    font-weight: 700;
    color: var(--color-foreground);
    margin-bottom: var(--space-3);
  }

  .docs-subtitle {
    font-size: var(--text-lg);
    color: var(--color-muted-foreground);
  }

  :global(.markdown-body h1) {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: white;
    margin-bottom: var(--space-6);
    margin-top: var(--space-8);
  }

  :global(.markdown-body h2) {
    font-size: var(--text-2xl);
    font-weight: 600;
    color: var(--color-foreground);
    margin-bottom: var(--space-4);
    margin-top: var(--space-10);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--color-border);
  }

  :global(.markdown-body h3) {
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--color-foreground);
    margin-bottom: var(--space-3);
    margin-top: var(--space-8);
  }

  :global(.markdown-body h4) {
    font-size: var(--text-lg);
    font-weight: 500;
    color: var(--color-foreground);
    margin-bottom: var(--space-2);
    margin-top: var(--space-6);
  }

  :global(.markdown-body p) {
    color: var(--color-muted-foreground);
    line-height: 1.625;
    margin-bottom: var(--space-4);
  }

  :global(.markdown-body a) {
    color: var(--color-primary);
    transition: color var(--transition-normal);
  }

  :global(.markdown-body a:hover) {
    color: var(--color-accent);
  }

  :global(.markdown-body ul) {
    list-style-type: disc;
    padding-left: var(--space-4);
    margin-bottom: var(--space-6);
    color: var(--color-muted-foreground);
  }

  :global(.markdown-body ol) {
    list-style-type: decimal;
    padding-left: var(--space-4);
    margin-bottom: var(--space-6);
    color: var(--color-muted-foreground);
  }

  :global(.markdown-body li) {
    line-height: 1.625;
  }

  :global(.markdown-body strong) {
    color: var(--color-foreground);
    font-weight: 600;
  }

  :global(.markdown-body code) {
    background-color: var(--color-code-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: 0.125rem 0.375rem;
    font-size: var(--text-sm);
    font-family: monospace;
    color: var(--color-success);
  }

  :global(.markdown-body pre) {
    background-color: var(--color-code-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    font-family: monospace;
    font-size: var(--text-sm);
    margin-bottom: var(--space-6);
    overflow-x: auto;
  }

  :global(.markdown-body pre code) {
    background-color: transparent;
    border: none;
    padding: 0;
    color: var(--color-code-fg);
  }

  /* Terminal-style command blocks */
  :global(.markdown-body pre:has(> code.shell)) {
    position: relative;
  }

  :global(.markdown-body code.shell) {
    color: var(--color-success);
  }

  /* Table styling */
  :global(.markdown-body table) {
    width: 100%;
    margin-bottom: var(--space-6);
    border-collapse: collapse;
  }

  :global(.markdown-body thead) {
    border-bottom: 1px solid var(--color-border);
  }

  :global(.markdown-body th) {
    text-align: left;
    font-size: var(--text-xs);
    text-transform: uppercase;
    color: var(--color-muted-foreground);
    font-weight: 500;
    padding: var(--space-3) var(--space-4);
  }

  :global(.markdown-body td) {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-muted-foreground);
  }

  :global(.markdown-body tbody tr:hover) {
    background-color: rgba(255, 255, 255, 0.05);
  }

  /* Blockquotes */
  :global(.markdown-body blockquote) {
    border-left: 4px solid var(--color-primary);
    padding-left: var(--space-4);
    padding-top: var(--space-2);
    padding-bottom: var(--space-2);
    margin-top: var(--space-6);
    margin-bottom: var(--space-6);
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    color: var(--color-muted-foreground);
  }

  /* Horizontal rules */
  :global(.markdown-body hr) {
    border-color: var(--color-border);
    margin-top: var(--space-8);
    margin-bottom: var(--space-8);
  }

  /* Inline code in tables */
  :global(.markdown-body td code) {
    font-size: var(--text-xs);
  }

  /* Responsive */
  @media (max-width: 768px) {
    .docs-layout {
      flex-direction: column;
    }

    .docs-sidebar {
      width: 100%;
      height: auto;
      position: relative;
      top: 0;
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }

    .docs-content {
      padding: var(--space-6);
    }

    .docs-title-content h1 {
      font-size: var(--text-2xl);
    }

    :global(.markdown-body h2) {
      font-size: var(--text-xl);
    }
  }
</style>