// Post-deploy smoke check: load the live site in a real browser and assert the
// things unit tests cannot see -- what the bundler emitted, what nginx routed,
// what the browser actually fetched (card #163). Exits 1 on any failure.
//
//   node scripts/smoke_check.cjs [base-url]
//
// Needs the `playwright` package and a chromium (`npx playwright install
// chromium`); deploy-production.yml installs both.
const { chromium } = require('playwright');

const BASE = (process.argv[2] || 'https://pkanban.pearachute.com').replace(/\/$/, '');
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`);
  if (!ok) failures.push(what);
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  const consoleErrors = [];
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));
  page.on('pageerror', (e) => consoleErrors.push(String(e)));
  page.on('requestfailed', (r) => consoleErrors.push(`request failed: ${r.url()}`));

  // The app mounted: a bundle that failed to parse leaves #app empty.
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  const mounted = await page.evaluate(() => document.querySelector('#app')?.childElementCount > 0);
  check(mounted, 'app mounted (#app has children)');

  // The stylesheet linked and defines the theme.
  const bg = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--color-background').trim()
  );
  check(bg !== '', 'built CSS defines --color-background');

  // Web fonts loaded: an @import dropped by the bundler leaves every page in
  // the system fallback with no error anywhere.
  await page.evaluate(() => document.fonts.ready);
  const loaded = await page.evaluate(() =>
    [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family.replace(/"/g, ''))
  );
  check(loaded.includes('Ubuntu'), `Ubuntu web font loaded (loaded: ${loaded.join(', ') || 'none'})`);

  // A docs SPA route resolves to the app, not an nginx 404 or directory listing.
  const docs = await page.goto(BASE + '/docs/quickstart', { waitUntil: 'networkidle' });
  const docsMounted = await page.evaluate(() => document.querySelector('#app')?.childElementCount > 0);
  check(docs.status() === 200 && docsMounted, `/docs/quickstart serves the app (HTTP ${docs.status()})`);

  // ...while the markdown behind it is real markdown, not index.html.
  const md = await page.request.get(BASE + '/docs/quickstart.md');
  const body = await md.text();
  check(md.status() === 200 && !/^\s*<!doctype html/i.test(body), '/docs/quickstart.md returns markdown');

  check(consoleErrors.length === 0, `no console errors${consoleErrors.length ? ': ' + consoleErrors.join(' | ') : ''}`);

  await browser.close();
  if (failures.length) {
    console.error(`\n${failures.length} smoke check(s) failed`);
    process.exit(1);
  }
  console.log('\nsmoke check passed');
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
