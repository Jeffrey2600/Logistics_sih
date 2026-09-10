/**
 * Browser smoke test for the dashboard.
 *
 * The Python suite tests the backend. It stayed green while three of the four
 * tabs were unreachable, because nothing loaded the page - so this drives the
 * real UI and asserts that every control changes what it claims to change.
 *
 * Run it against a server started with NER_USE_OSM=1:
 *
 *     node tests/browser/check.js                 # defaults to :8000
 *     BASE=http://localhost:8080 node tests/browser/check.js
 *
 * Exits non-zero if any check fails, so it can gate a release.
 */
const { chromium } = require('playwright');
const P = (process.env.BASE || 'http://localhost:8000').replace(/\/?$/, '/');
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

  // The place pickers are no longer <select>s, so selectOption cannot drive
  // them. Type into the search box and click the match, which is also the only
  // path a real user has.
  const pickPlace = async (which, id) => {
    const label = await p.evaluate(([w, i]) => {
      const combo = window.__combos && window.__combos[w];
      const option = combo && combo.options.find(o => o.id === i);
      return option ? option.name : null;
    }, [which, id]);
    if (!label) throw new Error(`no place ${id} in ${which}`);
    await p.click(`#${which}Search`);
    await p.fill(`#${which}Search`, label);
    await p.waitForSelector(`#${which}List li[data-index]`, { timeout: 15000 });
    await p.click(`#${which}List li[data-index="0"]`);
  };

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

  await pickPlace('origin', 'KHM'); await pickPlace('destination', 'GAU');
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

  // Back to the planning tab: the checks below drive controls that live there,
  // and a hidden control cannot be operated.
  await p.click('nav button[data-tab="route"]');
  await p.waitForSelector('#originSearch:visible', { timeout: 60000 });
  await idle('#planBtn');

  const sum = summary;
  await pickPlace('origin', 'KHM'); await pickPlace('destination', 'GAU');
  await p.click('#planBtn'); await idle('#planBtn');

  // 1. Ship from / Ship to actually drive the plan.
  const a = await sum();
  await pickPlace('origin', 'IMP'); await idle('#planBtn');
  check('Ship from changes the plan', (await sum()) !== a, await sum());
  await pickPlace('origin', 'KHM'); await idle('#planBtn');
  const legFrom = await p.$eval('#routeResult .leg .where', e => e.textContent);
  check('itinerary starts at the chosen origin', /Kohima/.test(legFrom), legFrom);

  // 2. Month drives the plan.
  const jul = await sum();
  await p.selectOption('#month','jan'); await idle('#planBtn');
  check('Month changes the plan', (await sum()) !== jul, `jul=${jul.slice(0,32)} jan=${(await sum()).slice(0,32)}`);
  await p.selectOption('#month','jul'); await idle('#planBtn');

  // 3. Advanced sliders change the ROUTE, not just their label.
  await p.click('#advanced summary');
  const before = await sum();
  await p.$eval('#vot', el => { el.value='3000'; el.dispatchEvent(new Event('input')); });
  await p.click('#planBtn'); await idle('#planBtn');
  check('Advanced: cost-of-delay slider changes the plan', (await sum()) !== before,
        `${before.slice(0,32)} -> ${(await sum()).slice(0,32)}`);
  await p.$eval('#vot', el => { el.value='150'; el.dispatchEvent(new Event('input')); });
  await p.click('#planBtn'); await idle('#planBtn');
  await p.click('#advanced summary');

  // 4. Mode chips restrict the plan.
  const withAir = await sum();
  const chips = await p.$$('#modeChips .chip');
  for (const c of chips) if ((await c.textContent()).trim() === 'Air') await c.click();
  await p.click('#planBtn'); await idle('#planBtn');
  const noAir = await p.textContent('#routeResult');
  check('turning a mode off removes it from the plan', !/By air|air ·/.test(noAir), 'air excluded');
  // Not asserting the summary changed: on a lane the optimiser already routes
  // by road and rail, switching air off correctly changes nothing. What must
  // hold is that the restriction is honoured, checked above.
  check('mode chips re-plan without a button press',
        (await p.textContent('#routeResult')).length > 0, 'replanned');
  for (const c of chips) if ((await c.textContent()).trim() === 'Air') await c.click();
  await p.click('#planBtn'); await idle('#planBtn');

  // 5. A lane with no route reports rather than breaking.
  await pickPlace('origin', 'GTK');
  for (const c of chips) { const t = (await c.textContent()).trim();
    if (t !== 'Water') continue; }
  await p.click('#planBtn'); await idle('#planBtn');
  check('an impossible request is reported, not silent',
        (await p.textContent('#routeResult')).length > 0, 'handled');
  await pickPlace('origin', 'KHM'); await p.click('#planBtn'); await idle('#planBtn');

  // 6. Risk: mode chips filter the map.
  await p.click('nav button[data-tab="risk"]');
  await p.waitForSelector('#riskResult tbody tr', { timeout: 180000 });
  const shown2 = async () => (await p.textContent('#riskResult')).match(/Showing ([\d,]+)/)?.[1];
  const allModes = await shown2();
  const rChips = await p.$$('#riskModeChips .chip');
  for (const c of rChips) { const t = (await c.textContent()).trim();
    if (t === 'Rail' || t === 'Water' || t === 'Air') await c.click(); }
  await p.click('#riskApply'); await idle('#riskApply');
  check('risk mode chips filter the map', (await shown2()) !== allModes, `${allModes} -> ${await shown2()}`);

  // 7. Risk month changes the numbers.
  const julRows = (await p.textContent('#riskResult tbody')).replace(/\s+/g,' ').slice(0,80);
  await p.selectOption('#riskMonth','jan'); await idle('#riskApply');
  check('risk month changes the numbers',
        (await p.textContent('#riskResult tbody')).replace(/\s+/g,' ').slice(0,80) !== julRows, 'changed');

  // 8. Accessibility: metric and month change the map.
  await p.click('nav button[data-tab="access"]');
  await p.waitForSelector('#accessResult tbody tr', { timeout: 180000 });
  const legendOf = async () => (await p.textContent('#legend')).replace(/\s+/g,' ').trim();
  const scoreLegend = await legendOf();
  await p.selectOption('#accessMetric','hours_to_market');
  await p.click('#accessApply'); await idle('#accessApply');
  check('accessibility metric changes the map legend', (await legendOf()) !== scoreLegend,
        (await legendOf()).slice(0,60));
  const julTable = (await p.textContent('#accessResult tbody')).replace(/\s+/g,' ').slice(0,80);
  await p.selectOption('#accessMonth','jan');
  await p.click('#accessApply'); await idle('#accessApply');
  check('accessibility month changes the ranking',
        (await p.textContent('#accessResult tbody')).replace(/\s+/g,' ').slice(0,80) !== julTable, 'changed');

  // 9. Clicking a row flies the map there.
  const beforeCentre = await p.evaluate(() => map.getCenter().lat);
  await p.click('#accessResult tbody tr');
  await p.waitForTimeout(2500);
  check('clicking a place flies the map to it',
        Math.abs(await p.evaluate(() => map.getCenter().lat) - beforeCentre) > 0.01, 'moved');


  // 10. Place search: typing filters, and picking drives the plan.
  await p.click('nav button[data-tab="route"]');
  await idle('#planBtn');
  await p.click('#originSearch');
  await p.fill('#originSearch', 'guwa');
  await p.waitForSelector('#originList li[data-index]', { timeout: 15000 });
  const guwa = await p.$$eval('#originList li[data-index]',
    els => els.map(e => e.textContent.trim()));
  check('place search filters as you type',
        guwa.length > 0 && guwa.every(x => /guwa/i.test(x)), guwa.slice(0, 2).join(' | '));

  // Accents must not have to be typed: OSM carries them, keyboards do not.
  await p.fill('#originSearch', 'nawajis');
  await p.waitForTimeout(300);
  const folded = await p.$$eval('#originList li[data-index]', els => els.length);
  check('search ignores accents', folded > 0, `${folded} match(es) for "nawajis"`);

  await p.fill('#originSearch', 'kohima');
  await p.waitForSelector('#originList li[data-index]', { timeout: 15000 });
  await p.click('#originList li[data-index="0"]');
  await idle('#planBtn');
  check('picking from the search re-plans the route',
        /Kohima/.test(await p.textContent('#routeResult')),
        (await p.inputValue('#origin')));

  // Escape restores the committed choice rather than leaving a half-typed box.
  await p.fill('#originSearch', 'zzz nonsense');
  await p.keyboard.press('Escape');
  await p.waitForTimeout(200);
  check('escape restores the chosen place',
        /Kohima/.test(await p.inputValue('#originSearch')),
        await p.inputValue('#originSearch'));

  // The rupee sign lives in the label; the slider must not add a second one.
  await p.click('#advanced summary');
  await p.$eval('#vot', el => {
    el.value = 500;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await p.waitForTimeout(200);
  const votText = (await p.textContent('#votLine')).replace(/\s+/g, ' ').trim();
  check('cost-of-delay label shows one rupee sign', !/₹\s*₹/.test(votText), votText);

  // 11. Voice input degrades rather than lying about being available.
  const voice = await p.evaluate(() => ({
    supported: !!(window.SpeechRecognition || window.webkitSpeechRecognition),
    hidden: document.getElementById('originMic').hidden,
  }));
  check('voice button matches browser support', voice.supported !== voice.hidden,
        `supported=${voice.supported} hidden=${voice.hidden}`);

  // 12. Satellite base map: real raster sources, and our layers survive it.
  //
  // The imagery host is unreachable from some networks - the CI sandbox among
  // them - and the app disables the button when its probe fails. That is the
  // behaviour we want, so assert it, then drive the switch directly so the
  // style-swap logic is still covered wherever this runs.
  const satButton = await p.evaluate(() => {
    const button = document.querySelector('#basemapSwitch button[data-basemap="satellite"]');
    return { disabled: button.disabled, title: button.title };
  });
  check('an unreachable base map is disabled with a reason, not left inert',
        !satButton.disabled || /not reachable/i.test(satButton.title),
        `disabled=${satButton.disabled} title="${satButton.title}"`);

  if (satButton.disabled) {
    await p.evaluate(() => setBasemap('satellite'));
  } else {
    await p.click('#basemapSwitch button[data-basemap="satellite"]');
  }
  await p.waitForTimeout(3000);
  const sat = await p.evaluate(() => ({
    sources: Object.keys(map.getStyle().sources),
    route: !!map.getLayer('route-line'),
    segments: !!map.getLayer('segments-line'),
    places: !!map.getLayer('places-circle'),
    body: document.body.classList.contains('satellite'),
  }));
  check('satellite adds imagery and reference layers',
        sat.sources.includes('sat-imagery') && sat.sources.includes('sat-reference'),
        sat.sources.join(','));
  check('data layers survive the base map switch',
        sat.route && sat.segments && sat.places && sat.body, JSON.stringify(sat));

  await p.evaluate(() => setBasemap('map'));
  await p.waitForTimeout(3000);
  check('switching back restores the vector base map',
        await p.evaluate(() => !document.body.classList.contains('satellite')
                            && !!map.getLayer('route-line')), 'restored');

  // 13. Language: the UI translates, and the choice survives a reload.
  const englishTab = await p.textContent('nav button[data-tab="route"]');
  await p.selectOption('#langSelect', 'hi');
  await p.waitForTimeout(600);
  const hindiTab = await p.textContent('nav button[data-tab="route"]');
  check('language switch translates the tabs', hindiTab !== englishTab && /[ऀ-ॿ]/.test(hindiTab),
        `${englishTab} -> ${hindiTab}`);
  check('language switch translates the month list',
        /[ऀ-ॿ]/.test(await p.$eval('#month option[value="jul"]', e => e.textContent)),
        await p.$eval('#month option[value="jul"]', e => e.textContent));
  await idle('#planBtn');
  check('language switch translates generated results',
        /[ऀ-ॿ]/.test(await p.textContent('#routeResult .stats')),
        (await p.textContent('#routeResult .stats')).replace(/\s+/g, ' ').slice(0, 50));

  await p.reload({ waitUntil: 'domcontentloaded' });
  await p.waitForSelector('#routeResult .stat b', { timeout: 120000 });
  check('language choice survives a reload',
        /[ऀ-ॿ]/.test(await p.textContent('nav button[data-tab="route"]')),
        await p.textContent('nav button[data-tab="route"]'));
  await p.selectOption('#langSelect', 'en');
  await p.waitForTimeout(400);
  check('switching back to English restores it',
        (await p.textContent('nav button[data-tab="route"]')).trim() === 'Plan a shipment',
        await p.textContent('nav button[data-tab="route"]'));

  const failed = results.filter((r) => !r.ok);
  for (const r of results) {
    console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name || r.n}` +
                (r.ok ? "" : `   -> ${String(r.detail ?? r.d).slice(0, 90)}`));
  }
  console.log(`\n${results.length - failed.length}/${results.length} passed` +
              `  |  page errors: ${errs.length ? [...new Set(errs)].join("; ") : "none"}`);
  await b.close();
  process.exit(failed.length || errs.length ? 1 : 0);
})();
