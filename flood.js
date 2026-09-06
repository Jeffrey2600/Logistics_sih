const { chromium } = require('playwright');
(async () => {
  const proxy = process.env.HTTPS_PROXY;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined });
  const p = await b.newPage({ viewport: { width: 1500, height: 980 } });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  await p.goto('http://localhost:8020/', { waitUntil: 'domcontentloaded' });
  await p.waitForSelector('#routeResult .stat b', { timeout: 120000 });
  await p.click('nav button[data-tab="risk"]');
  await p.waitForSelector('#riskResult tbody tr', { timeout: 120000 });
  for (const [hazard, name] of [['flood','h-flood'],['landslide','h-slide']]) {
    await p.selectOption('#hazard', hazard);
    await p.waitForTimeout(3500);
    await p.screenshot({ path: `shots/${name}.png` });
  }
  console.log(errs.length ? errs.join('\n') : 'no page errors');
  await b.close();
})();
