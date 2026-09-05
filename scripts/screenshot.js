/**
 * Capture all four dashboard views to shots/.
 *
 *   node scripts/screenshot.js [baseUrl]
 *
 * Used to verify the dashboard actually renders, rather than assuming it does
 * because the files return 200. Three of the rendering bugs in this project's
 * history were only visible by driving a real browser: a MapLibre layer that
 * silently failed to be added, a glyph fetch that took a whole source's tile
 * parse down with it, and an error handler that swallowed both.
 *
 * Behind an HTTPS proxy, Chromium ignores the environment variable, so it is
 * passed explicitly - with localhost bypassed, or the dashboard itself becomes
 * unreachable.
 */
const { chromium } = require('playwright');

const BASE = process.argv[2] || 'http://localhost:8000';
const VIEWS = [
  ['route', '01-route'],
  ['risk', '02-risk'],
  ['access', '03-access'],
  ['siting', '04-siting'],
];

(async () => {
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined,
  });

  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  const problems = [];
  page.on('pageerror', (e) => problems.push('PAGEERROR: ' + e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') problems.push('CONSOLE: ' + m.text().slice(0, 160));
  });

  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(6000);

  for (const [tab, name] of VIEWS) {
    if (tab !== 'route') {
      await page.click(`nav button[data-tab="${tab}"]`);
      await page.waitForTimeout(4000);
      if (tab === 'siting') {
        await page.click('#siteBtn');
        await page.waitForTimeout(4000);
      }
    }
    await page.screenshot({ path: `shots/${name}.png` });
    console.log(`wrote shots/${name}.png`);
  }

  // A blank basemap is survivable and expected offline; a missing data layer is
  // not, so report what actually made it onto the map.
  const rendered = await page.evaluate(() => ({
    basemap: typeof basemapLoaded !== 'undefined' ? basemapLoaded : null,
    layers: map.getStyle().layers.map((l) => l.id).filter((id) => !id.startsWith('bg')),
  }));
  console.log('basemap loaded:', rendered.basemap);
  console.log('data layers:', rendered.layers.join(', '));

  if (problems.length) {
    console.log('--- page problems ---');
    console.log([...new Set(problems)].slice(0, 10).join('\n'));
  }
  await browser.close();
})();
