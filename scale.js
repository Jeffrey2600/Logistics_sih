const { chromium } = require('playwright');
(async () => {
  const proxy = process.env.HTTPS_PROXY;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  p.on('console', m => { if (m.type()==='error') errs.push('CONSOLE: '+m.text().slice(0,120)); });

  let t = Date.now();
  await p.goto('http://localhost:8123/', { waitUntil: 'networkidle', timeout: 120000 });
  await p.waitForTimeout(4000);
  console.log(`route tab ready: ${((Date.now()-t)/1000).toFixed(1)}s`);
  await p.screenshot({ path: 'shots/scale-01-route.png' });

  for (const [tab, name] of [['risk','scale-02-risk'],['access','scale-03-access']]) {
    t = Date.now();
    await p.click(`nav button[data-tab="${tab}"]`);
    // wait until the sidebar table has rendered
    try {
      await p.waitForFunction(
        (sel) => document.querySelector(sel)?.querySelectorAll('tbody tr').length > 0,
        tab === 'risk' ? '#riskResult' : '#accessResult', { timeout: 90000 });
      console.log(`${tab} tab rendered: ${((Date.now()-t)/1000).toFixed(1)}s`);
    } catch (e) { console.log(`${tab} tab TIMED OUT after 90s`); }
    await p.waitForTimeout(3000);
    await p.screenshot({ path: `shots/${name}.png` });
  }
  console.log(errs.length ? '--- errors ---\n' + [...new Set(errs)].slice(0,6).join('\n') : 'no page errors');
  await b.close();
})();
