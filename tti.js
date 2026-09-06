const { chromium } = require('playwright');
(async () => {
  const proxy = process.env.HTTPS_PROXY;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined });
  const ctx = await b.newContext({ viewport: { width: 1500, height: 950 }, bypassCSP: true });
  const p = await ctx.newPage();
  await p.route('**/*', r => r.continue());   // no disk cache
  const t0 = Date.now();
  await p.goto('http://localhost:8114/', { waitUntil: 'domcontentloaded' });
  await p.waitForSelector('#routeResult .stat b', { timeout: 60000 });
  console.log(`time to first usable route: ${((Date.now()-t0)/1000).toFixed(1)}s`);
  console.log(JSON.stringify(await p.evaluate(() => ({
    originOptions: document.getElementById('origin').options.length,
    candidateListOptions: document.getElementById('candidateList')?.options.length ?? 'MISSING',
  }))));
  // Exercise the siting flow end to end.
  await p.click('nav button[data-tab="siting"]');
  await p.fill('#candidateSearch', 'Kohima');
  await p.waitForTimeout(400);
  await p.selectOption('#candidateList', { index: 0 });
  await p.click('#siteBtn');
  await p.waitForSelector('#sitingResult tbody tr', { timeout: 120000 });
  console.log('siting ran:', (await p.textContent('#sitingResult')).slice(0, 120).replace(/\s+/g,' '));
  await p.screenshot({ path: 'shots/siting-picker.png' });
  await b.close();
})();
