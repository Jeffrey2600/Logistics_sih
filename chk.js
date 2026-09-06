const { chromium } = require('playwright');
(async () => {
  const proxy = process.env.HTTPS_PROXY;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined });
  for (const port of [8002, 8001]) {
    const p = await b.newPage();
    const errs = [];
    p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
    await p.goto(`http://localhost:${port}/`, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(6000);
    const r = await p.evaluate(() => ({
      origin: document.getElementById('origin').options.length,
      dest: document.getElementById('destination').options.length,
      when: document.getElementById('month').options.length,
      firstOrigin: document.getElementById('origin').options[0]?.text || null,
      routeMsg: document.getElementById('routeResult').textContent.trim().slice(0, 90),
    }));
    console.log(`port ${port}:`, JSON.stringify(r), errs.length ? '\n  ' + errs[0] : '');
    await p.close();
  }
  await b.close();
})();
