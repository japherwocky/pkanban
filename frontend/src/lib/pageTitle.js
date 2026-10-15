// The tab title, kept right as people move around the app.
//
// The server writes each public page's title into its HTML (backend/pages.py)
// and embeds all of them as JSON in #page-titles, so in-app navigation can
// follow without any page repeating its own title. Docs pages are titled by
// their markdown's first heading, by the same rule the server uses.

let titles = null;

function load() {
  if (titles) return titles;
  titles = { default: document.title, pages: {} };
  const embedded = document.getElementById('page-titles');
  if (embedded) {
    try {
      titles = { ...titles, ...JSON.parse(embedded.textContent) };
    } catch {
      // A page without usable titles keeps whatever title it loaded with.
    }
  }
  return titles;
}

export function titleFor(pathname) {
  const { pages, default: fallback } = load();
  const path = pathname.replace(/\/+$/, '') || '/';
  return pages[path] ?? fallback;
}

// Must match doc_title() in backend/pages.py.
export function docTitle(markdown) {
  const line = markdown.split(/\r?\n/).find((l) => l.startsWith('# '));
  if (!line) return null;
  const heading = line
    .slice(2)
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[`*_]/g, '')
    .split(/\s+/)
    .filter(Boolean)
    .join(' ');
  return heading.toLowerCase().includes('pkanban') ? heading : `${heading} — pkanban docs`;
}

// For tests: forget what was read from the page.
export function resetTitles() {
  titles = null;
}
