const { chromium } = require('playwright');
(async () => {
  const proxy = process.env.HTTPS_PROXY;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined });
  const p = await b.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE: ' + m.text().slice(0,200)); });
  await p.goto('http://localhost:8060/', { waitUntil: 'domcontentloaded' });
  await p.waitForSelector('#routeResult .stat b', { timeout: 120000 });
  await p.click('nav button[data-tab="risk"]');
  await p.waitForTimeout(25000);
  console.log('errors:', errs.length ? [...new Set(errs)].join('\n') : 'none');
  console.log('riskResult:', (await p.textContent('#riskResult')).slice(0,200).replace(/\s+/g,' '));
  await b.close();
})();
