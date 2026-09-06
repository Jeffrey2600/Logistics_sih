const { chromium } = require('playwright');
(async () => {
  const proxy = process.env.HTTPS_PROXY;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined });
  const p = await b.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  p.on('console', m => { if (m.type()==='error') errs.push('CONSOLE: ' + m.text().slice(0,200)); });
  await p.goto('http://localhost:8121/', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(6000);
  console.log(errs.length ? [...new Set(errs)].slice(0,8).join('\n') : 'no errors');
  console.log('routeResult html length:', await p.evaluate(() => document.getElementById('routeResult').innerHTML.length));
  console.log('routeResult:', (await p.evaluate(() => document.getElementById('routeResult').textContent)).slice(0,200));
  await b.close();
})();
