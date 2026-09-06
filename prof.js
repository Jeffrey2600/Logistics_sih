const { chromium } = require('playwright');
(async () => {
  const proxy = process.env.HTTPS_PROXY;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium',
    proxy: proxy ? { server: proxy, bypass: 'localhost,127.0.0.1' } : undefined });
  const p = await b.newPage();
  await p.goto('http://localhost:8111/', { waitUntil: 'domcontentloaded' });
  const timing = await p.evaluate(async () => {
    const t0 = performance.now();
    const r = await fetch('/network/places'); const { places } = await r.json();
    const tFetch = performance.now() - t0;

    const opts = places.map(x => [x.id, `${x.name} — ${x.state}`]);
    let t = performance.now();
    const sel = document.createElement('select');
    sel.innerHTML = opts.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
    document.body.appendChild(sel);
    const tSelect = performance.now() - t;

    t = performance.now();
    const div = document.createElement('div');
    for (const [v] of opts) { const btn = document.createElement('button'); btn.textContent = v; div.appendChild(btn); }
    document.body.appendChild(div);
    const tChips = performance.now() - t;

    return { places: places.length, fetchMs: Math.round(tFetch),
             oneSelectMs: Math.round(tSelect), chipRowMs: Math.round(tChips) };
  });
  console.log(JSON.stringify(timing, null, 1));
  await b.close();
})();
