const { chromium } = require('playwright');
const P = 'http://localhost:8070/';
const results = [];
const check = (name, ok, detail) => results.push({ name, ok, detail });

(async () => {
  const proxy = process.env.HTTPS_PROXY;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto(P, { waitUntil: 'domcontentloaded' });
  await p.waitForSelector('#routeResult .stat b', { timeout: 120000 });

  const idle = async (sel) => {
    await p.waitForTimeout(250);
    await p.waitForFunction(s => !document.querySelector(s).disabled, sel, { timeout: 180000 });
    await p.waitForTimeout(250);
  };
  const summary = async () => (await p.textContent('#routeResult .stats')).replace(/\s+/g,' ').trim();

  const panel = await p.evaluate(() => {
    const el = document.getElementById('sidebar');
    return { bg: getComputedStyle(el).backgroundColor, width: el.offsetWidth };
  });
  check('left panel is light', panel.bg === 'rgb(255, 255, 255)', panel.bg);
  check('left panel widened', panel.width === 475, `${panel.width}px`);
  const tabs = await p.$$eval('nav button', e => e.map(x => x.dataset.tab));
  check('Where to build removed', !tabs.includes('siting'), tabs.join(','));
  check('Analysis tab present', tabs.includes('analysis'), tabs.join(','));
  check('road-closure control removed', (await p.$('#closure')) === null);

  await p.selectOption('#origin', 'KHM'); await p.selectOption('#destination', 'GAU');
  await p.click('#planBtn'); await idle('#planBtn');
  await p.selectOption('#priority','cheapest'); await idle('#planBtn');
  const cheap = await summary();
  await p.selectOption('#priority','fastest'); await idle('#planBtn');
  const fast = await summary();
  check('What matters most changes the plan', cheap !== fast, `${cheap.slice(0,38)} | ${fast.slice(0,38)}`);
  await p.selectOption('#priority','balanced'); await idle('#planBtn');
  await p.selectOption('#cargo','25'); await idle('#planBtn');
  const bulk = await summary();
  await p.selectOption('#cargo','3000'); await idle('#planBtn');
  const urgent = await summary();
  check('What are you shipping changes the plan', bulk !== urgent, `${bulk.slice(0,38)} | ${urgent.slice(0,38)}`);
  await p.selectOption('#cargo','150'); await idle('#planBtn');

  const alts = await p.$$eval('.alt', e => e.length);
  check('alternatives listed', alts > 0, `${alts}`);
  const flags = await p.evaluate(() => [...new Set(
    map.getSource('route')._data.features.map(f => f.properties.chosen))].length);
  check('all routes drawn, one highlighted', flags === 2, `distinct chosen flags=${flags}`);
  if (alts) {
    await p.click('.alt'); await p.waitForTimeout(1200);
    check('clicking an alternative highlights it',
          await p.$eval('.alt', e => e.classList.contains('chosen')));
  }
  await p.click('#advanced summary');
  await p.$eval('#wRisk', el => { el.value='1'; el.dispatchEvent(new Event('input')); });
  check('advanced slider label updates', (await p.textContent('#wRiskL')) === '1.00');
  await p.click('#advanced summary');

  await p.click('nav button[data-tab="risk"]');
  await p.waitForSelector('#riskResult tbody tr', { timeout: 180000 });
  const rows = async () => (await p.textContent('#riskResult tbody')).replace(/\s+/g,' ').trim().slice(0,100);
  await p.selectOption('#hazard','flood');
  await p.click('#riskApply'); await idle('#riskApply');
  const floodRows = await rows();
  check('Apply shows a confirmation', await p.$eval('#riskApplied', e => !e.hidden));
  await p.selectOption('#hazard','landslide');
  await p.click('#riskApply'); await idle('#riskApply');
  const slideRows = await rows();
  check('hazard filter changes results', slideRows !== floodRows, slideRows.slice(0,60));
  const shown = async () => (await p.textContent('#riskResult')).match(/Showing ([\d,]+)/)?.[1];
  const at5 = await shown();
  await p.$eval('#minLength', el => { el.value='20'; el.dispatchEvent(new Event('input')); });
  await p.click('#riskApply'); await idle('#riskApply');
  const at20 = await shown();
  check('length filter works', +at20.replace(/,/g,'') < +at5.replace(/,/g,''), `${at5} -> ${at20}`);

  await p.click('nav button[data-tab="access"]');
  await p.waitForSelector('#accessResult tbody tr', { timeout: 180000 });
  await p.selectOption('#accessMetric','hours_to_market');
  await p.click('#accessApply'); await idle('#accessApply');
  check('accessibility Apply confirms', await p.$eval('#accessApplied', e => !e.hidden));

  await p.click('nav button[data-tab="analysis"]');
  await p.waitForSelector('#analysisResult table.compare tbody tr', { timeout: 240000 });
  const optionRows = await p.$$eval('#analysisResult table.compare tbody tr', e => e.length);
  const verdict = (await p.textContent('#analysisResult .verdict')).replace(/\s+/g,' ').trim();
  check('analysis lists every option', optionRows >= 4, `${optionRows} rows`);
  check('analysis explains in prose', verdict.length > 120, verdict.slice(0,110));
  check('analysis marks a winner', (await p.$('#analysisResult tr.winner')) !== null);
  await p.screenshot({ path: 'shots/final-analysis.png' });

  console.log(JSON.stringify({ results, pageErrors: [...new Set(errs)] }, null, 1));
  await b.close();
})();
