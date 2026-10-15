import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import Header from './Header.svelte';
import Footer from './Footer.svelte';

// Crawlers follow <a href> and nothing else. The header and footer used to
// navigate with <button onclick>, which left every page on the site unlinked
// as far as a search engine could tell.

function hrefs(container) {
  return [...container.querySelectorAll('a[href]')].map((a) => a.getAttribute('href'));
}

describe('site navigation is real links', () => {
  it('header', () => {
    const { container } = render(Header);
    expect(hrefs(container)).toEqual(expect.arrayContaining(['/', '/docs', '/pricing', '/about']));
  });

  it('footer', () => {
    const { container } = render(Footer);
    expect(hrefs(container)).toEqual(
      expect.arrayContaining(['/', '/docs', '/pricing', '/about', '/contact', '/privacy', '/terms']),
    );
  });
});
