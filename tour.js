const { chromium } = require('playwright');
(async () => {
  const proxy = process.env.HTTPS_PROXY;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined });
  const p = await b.newPage({ viewport: { width: 1500, height: 980 } });
  await p.goto('http://localhost:8010/', { waitUntil: 'domcontentloaded' });
  await p.waitForSelector('#routeResult .stat b', { timeout: 90000 });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: 'shots/t1-plan.png' });

  // Open the advanced panel so every control is visible at least once.
  await p.click('#advanced summary');
  await p.waitForTimeout(500);
  await p.screenshot({ path: 'shots/t1b-advanced.png' });
  await p.click('#advanced summary');

  await p.click('nav button[data-tab="risk"]');
  await p.waitForSelector('#riskResult tbody tr', { timeout: 90000 });
  await p.waitForTimeout(2000);
  await p.screenshot({ path: 'shots/t2-risk.png' });

  await p.click('nav button[data-tab="access"]');
  await p.waitForSelector('#accessResult tbody tr', { timeout: 90000 });
  await p.waitForTimeout(2000);
  await p.screenshot({ path: 'shots/t3-cutoff.png' });

  await p.click('nav button[data-tab="siting"]');
  await p.waitForTimeout(600);
  await p.fill('#candidateSearch', 'Haflong');
  await p.waitForTimeout(400);
  await p.selectOption('#candidateList', { index: 0 });
  await p.fill('#candidateSearch', 'Kohima');
  await p.waitForTimeout(400);
  await p.selectOption('#candidateList', { index: 0 });
  await p.fill('#candidateSearch', 'Tawang');
  await p.waitForTimeout(400);
  await p.selectOption('#candidateList', { index: 0 });
  await p.click('#siteBtn');
  await p.waitForSelector('#sitingResult tbody tr', { timeout: 180000 });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: 'shots/t4-build.png' });
  console.log('captured');
  await b.close();
})();
