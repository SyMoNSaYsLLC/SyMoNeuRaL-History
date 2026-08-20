// Drive the real pages in a real browser.
//
// curl proves the endpoints answer. It proves nothing about the JavaScript that has to
// render them -- which is how a render that succeeded server-side still showed up as a
// broken <img> on the live site. Everything here asserts on what the DOM actually shows.
//
//   node tests/frontend.mjs [baseURL]
//
// Uses the system Chrome (channel: 'chrome') so no browser download is needed.

// Playwright lives in the llama.cpp web UI's node_modules, installed when that UI was
// built. Resolved relative to this file so the repo can be cloned anywhere.
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = dirname(dirname(fileURLToPath(import.meta.url)));
const { chromium } = createRequire(import.meta.url)(
  join(REPO, 'contrib/llama.cpp/tools/ui/node_modules/playwright'));

const BASE = process.argv[2] || 'http://127.0.0.1:8800';
// The tabbed front page is addressed as /index.html throughout, because `/` now redirects
// to /overview. Loading BASE for a rack or control-board assertion would land on the
// masthead and quietly assert nothing.

const SHOTS = process.env.SHOT_DIR || '/tmp/symoneural-shots';
const results = [];
const record = (name, ok, detail) => {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  -- ' + detail : ''}`);
};

const browser = await chromium.launch({ channel: 'chrome', args: ['--no-sandbox'] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();

// Anything the page requests and does not get is a real defect: a broken image on a page
// whose argument is that its numbers are real is worse than a slow one.
const failed = [];
page.on('response', r => { if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`); });
page.on('pageerror', e => failed.push(`jserror: ${e.message}`));

// The front page shows one panel at a time above the gate in symoneural.css, and the panel
// it opens on is the masthead. Anything asserting on the rack or the control board has to
// open that tab first -- exactly as a visitor does. Below the gate every section is already
// visible and the click is a no-op, so this is safe to call unconditionally.
const openTab = async (p, id) => {
  await p.evaluate(i => {
    const b = document.querySelector(`.ns-tab[data-panel="${i}"]`);
    if (b) b.click();
  }, id);
  await p.waitForTimeout(150);
};

try {
  // ---- rack ----------------------------------------------------------------
  await page.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
  await openTab(page, 'rack');
  await page.waitForSelector('.unit', { timeout: 15000 });
  const units = await page.$$eval('.unit', els => els.map(e => ({
    name: e.querySelector('.uname b')?.textContent?.trim(),
    bus:  e.querySelector('.ubus')?.textContent?.trim(),
    state: e.getAttribute('data-state'),
  })));
  record('rack renders units from /api/status', units.length >= 5, `${units.length} units`);
  record('bus plate carries a real reading',
         // ASIC and NET are buses too. The plate used to be `bus === 'cpu' ? 'CPU' : 'GPU'`,
         // so an ASIC surface printed "GPU" -- the wrong hardware, on the one plate the page
         // asks you to trust. '--' stays allowed: it is what console.js prints for a bus it
         // does not recognise, which is the honest answer to an unknown value.
         units.every(u => ['GPU', 'CPU', 'ASIC', 'NET', '--'].includes(u.bus)),
         units.map(u => `${u.name}=${u.bus}`).join(', '));
  // Renamed again 2026-08-17: the old label was our prefix bolted onto the expansion of a
  // generic technique, and it wrapped to five lines in the compact GPU panel. What this
  // assertion guards is unchanged -- that the training bay carries a real PRODUCT name in
  // the SyMoNeuRaL series, not a technique description.
  record('train unit carries a product name',
         units.some(u => u.name === 'SyMoNeuRaL Reinforce'));
  // No rack name may be a prefix of another, which is a stricter rule than "no duplicates"
  // and it is the stricter one that was needed here.
  //
  // The miner shipped as two rows: "SyMoNeuRaL Miner", OFFLINE on the ASIC bus with no rig
  // attached, and "SyMoNeuRaL Miner GPU", READY and the only one that has ever hashed. Two
  // distinct strings, so a duplicate check passes them both -- and Garrett still read the
  // pair as one surface that was half broken, because the clean product name sat on the
  // dead row while the working one wore a qualifier. That is the defect: not a collision,
  // but a name that reads as the general case of the name beside it. They are now one row.
  {
    const names = units.map(u => u.name).filter(Boolean);
    const bad = [];
    names.forEach(a => names.forEach(b => {
      if (a !== b && b.startsWith(a)) bad.push(`"${a}" is a prefix of "${b}"`);
    }));
    record('no rack name is a prefix of another', bad.length === 0,
           bad.length ? bad.join('; ') : `${names.length} names, none a prefix of another`);
  }

  // ---- one unit per surface ------------------------------------------------
  // Garrett: "you need to migrate tuner and guide to be 1". Tuner and Guide were two units
  // with the SAME href, /tuner.html, so the rack showed one page twice and disagreed with
  // itself about how many things this box runs. They are now one unit.
  //
  // The assertion is on the INVARIANT rather than on a count. `units.length === 11` would go
  // red every time a genuine surface is added, which is the kind of assertion people delete
  // instead of reading. What was actually broken is narrower and survives the rack growing:
  // no two tiles may claim the same page AND the same bus, because then they are one thing
  // shown twice. Tuner and Guide were exactly that -- both `cpu`, both /tuner.html.
  //
  // Sharing a page is fine on its own, which is why this is not the blunter check: Coder and
  // Project both link to /documentation.html because neither has a page yet and that beats
  // linking to a 404. A rule that failed that would be measuring the wrong thing.
  //
  // This comment used to cite the two Miner units -- ASIC and GPU, different hardware, one
  // page -- as the second example. They were merged into a single `miner` row on 2026-08-17
  // (the two halves now ride in its `sub` array), so that example no longer exists. The rule
  // is unchanged and still correct; only the illustration was stale.
  const tiles = await page.$$eval('#units .unit', els => els.map(e => ({
    href: e.getAttribute('href'),
    bus: e.querySelector('.ubus')?.textContent?.trim() || '',
  })));
  const keys = tiles.filter(t => t.href && t.href !== '/documentation.html')
                    .map(t => `${t.href} [${t.bus}]`);
  const dupes = [...new Set(keys.filter((k, i) => keys.indexOf(k) !== i))];
  record('no two rack units are the same page on the same bus', dupes.length === 0,
         dupes.length ? `duplicated: ${dupes.join(', ')}` : `${keys.length} distinct`);
  record('the tuner unit carries the guide too',
         units.some(u => /Tuner/.test(u.name || '') && /Guide/.test(u.name || '')),
         units.map(u => u.name).filter(n => /Tuner|Guide/.test(n)).join(' | ') || 'no tuner unit');

  // the rack must lead the page now
  const order = await page.evaluate(() => {
    const r = document.querySelector('#rack'), c = document.querySelector('#console');
    return r && c ? (r.compareDocumentPosition(c) & Node.DOCUMENT_POSITION_FOLLOWING) > 0 : false;
  });
  record('rack precedes the control board', order);

  // ---- phone reflow: nothing may overlap -----------------------------------
  await page.setViewportSize({ width: 390, height: 900 });
  await page.waitForTimeout(400);
  const overlap = await page.evaluate(() => {
    const bad = [];
    document.querySelectorAll('.unit').forEach(u => {
      const n = u.querySelector('.uname'), s = u.querySelector('.ustate');
      if (!n || !s) return;
      const a = n.getBoundingClientRect(), b = s.getBoundingClientRect();
      const hit = a.right > b.left + 1 && a.left < b.right - 1 &&
                  a.bottom > b.top + 1 && a.top < b.bottom - 1;
      if (hit) bad.push(n.textContent.trim().slice(0, 30));
    });
    return bad;
  });
  record('no overlap at 390px', overlap.length === 0, overlap.join(', ') || 'clean');
  await page.setViewportSize({ width: 1440, height: 1000 });

  // ---- nothing may run off the right edge at 390px --------------------------
  // The header nav did exactly this: the <button> dropdowns are not <a>, so the rule
  // that hides the nav links on a phone never touched them, and the nav ran 122px past
  // a 390px viewport with the CTA entirely off screen.
  await page.setViewportSize({ width: 390, height: 900 });
  await page.waitForTimeout(300);
  const spill = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const bad = [];
    document.querySelectorAll('header .bar > *, header nav > *, .cards > *').forEach(e => {
      const r = e.getBoundingClientRect();
      if (r.width && r.right > vw + 1) bad.push(`${e.className || e.tagName} -> ${Math.round(r.right)} > ${vw}`);
    });
    if (document.documentElement.scrollWidth > vw + 1) bad.push(`page scrolls to ${document.documentElement.scrollWidth}`);
    return bad;
  });
  record('nothing spills past the right edge at 390px', spill.length === 0,
         spill.join('; ') || 'clean');
  await page.setViewportSize({ width: 1440, height: 1000 });

  // ---- the header holds its nav in the tablet band --------------------------
  // Why this exists, and why the 390px check above could never have caught it. That one
  // runs on /index.html, whose nav is five links plus the CTA; the four prompt surfaces and
  // the operator pages carry SIX plus the CTA -- they add "Live stack". The hide rule at
  // symoneural.css:123 is `max-width:780px`, and it was sized against the FIVE-link nav, so
  // at 781px the longer nav became visible and immediately overflowed: measured 66px past
  // `header .bar`'s right edge at 781px, 47px at 800px, 27px at 820px, clear only at 860px,
  // with the wordmark squeezed 138px -> 108px across the whole band because flex shrinks
  // `.logo` before it gives up on the nav. It was live on the site.
  //
  // Asserting on the six-link nav, at 781px because that is one pixel inside the hide rule
  // and therefore the worst case by construction. Two separate things are checked: that no
  // nav item extends past the bar, and that the wordmark keeps its natural width -- the
  // second is what tells you the nav is being given room rather than taking it from the
  // brand.
  for (const bandW of [781, 800, 860]) {
    const probe = await ctx.newPage();
    await probe.setViewportSize({ width: bandW, height: 900 });
    await probe.goto(new URL('/chat.html', BASE).href, { waitUntil: 'networkidle' });
    await probe.waitForTimeout(250);
    const band = await probe.evaluate(() => {
      const bar = document.querySelector('header .bar');
      const nav = document.querySelector('header nav');
      const logo = document.querySelector('header .logo');
      const barR = bar.getBoundingClientRect().right;
      const items = [...nav.children].filter(e => e.getBoundingClientRect().width > 0);
      const past = Math.max(0, ...items.map(e => Math.round(e.getBoundingClientRect().right - barR)));
      return { past, links: items.length, logoW: Math.round(logo.getBoundingClientRect().width),
               spillX: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth) };
    });
    await probe.close();
    // 130px is the wordmark's natural width at this size (measured 138px); anything much
    // under it means flex has started eating the brand to pay for the nav.
    record(`the header holds a six-link nav at ${bandW}px`,
           band.past === 0 && band.spillX === 0 && band.links >= 7 && band.logoW >= 130,
           `${band.links} items, ${band.past}px past the bar, logo ${band.logoW}px, page spill ${band.spillX}`);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });

  // The gutter renders live in the masthead, which is the `hero` panel. Open it -- the
  // three assertions below all reach for `a.gart`, and a hidden element has no box.
  await openTab(page, 'hero');

  // ---- the renders open large enough to read their watermark ---------------
  // Each render carries a watermark naming the model, seed and wall-clock -- the claim the
  // whole band makes. At 38-59px it is unreadable, and `.band-art` had pointer-events:none,
  // which silently disabled every descendant: the hover caption never appeared either.
  const lb = await page.evaluate(async () => {
    const a = document.querySelector('a.gart, a.art');
    if (!a) return { ok: false, why: 'no clickable render on the front page' };
    if (getComputedStyle(a).pointerEvents === 'none') return { ok: false, why: 'pointer-events:none' };
    a.click();
    await new Promise(r => setTimeout(r, 300));
    const box = document.querySelector('.lightbox.on');
    if (!box) return { ok: false, why: 'lightbox did not open' };
    const img = box.querySelector('img');
    await new Promise(r => img.complete ? r() : img.addEventListener('load', r, { once: true }));
    const w = img.getBoundingClientRect().width;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await new Promise(r => setTimeout(r, 200));
    return { ok: img.naturalWidth >= 768 && w >= 400 && !document.querySelector('.lightbox.on'),
             why: `natural ${img.naturalWidth}px, shown ${Math.round(w)}px, closed on Escape` };
  });
  record('a render opens large enough to read its watermark', lb.ok, lb.why);

  // ---- the watermark's claim is readable without opening anything ----------
  // The strip burned into the PNG is 3.5x downscaled in a gutter, so it cannot be read in
  // place at any size that does not eat the picture. The same facts are printed as text in
  // .gprov, and this asserts what the DOM *shows*: the line is on screen, is not clipped,
  // and still carries the two things that are obligations rather than decoration -- the
  // seed (the reproducibility claim) and the model name (an Apache-2.0 attribution
  // condition, which is why every ellipsis rule was removed from this stylesheet).
  const prov = await page.evaluate(() => {
    const el = document.querySelector('.gart .gprov');
    if (!el) return { ok: false, why: 'no .gprov under any gutter render' };
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const t = el.textContent;
    const clipped = cs.textOverflow === 'ellipsis' || el.scrollWidth > el.clientWidth + 1;
    return {
      ok: r.width > 0 && r.height > 0 && parseFloat(cs.fontSize) >= 10 &&
          cs.visibility !== 'hidden' && cs.display !== 'none' &&
          !clipped && /seed \d/.test(t) && /SymonImage/.test(t) && /RTX/.test(t),
      why: `"${t.trim()}" at ${cs.fontSize}, ${Math.round(r.width)}px wide` +
           (clipped ? ' -- CLIPPED' : ', not clipped'),
    };
  });
  record('the watermark is readable as text without opening the render', prov.ok, prov.why);

  // ---- the lightbox's provenance claim tracks the file, not the page ------
  // It says "the strip along the bottom is printed into the file". Only build_gallery.py
  // burns a strip; a render from /api/gen has none. Asserting it unconditionally would put
  // a false provenance claim on the one feature whose entire purpose is provenance, so the
  // claim is derived from the file's own shape -- the bar makes it taller than it is wide.
  // A square stand-in stands for an API render here; the real thing is 768x768 too.
  const claim = await page.evaluate(async () => {
    const a = document.querySelector('a.gart, a.art');
    if (!a) return { ok: false, why: 'no lightbox-able render' };
    const href = a.getAttribute('href');
    const read = async () => {
      a.click();
      const im = document.querySelector('.lightbox img');
      await new Promise(r => im.complete ? r() : im.addEventListener('load', r, { once: true }));
      await new Promise(r => setTimeout(r, 120));
      const t = document.querySelector('.lb-meta').textContent;
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      await new Promise(r => setTimeout(r, 80));
      return { t, w: im.naturalWidth, h: im.naturalHeight };
    };
    const tall = await read();
    // a 2x2 square PNG: same shape as an unstamped API render, no network needed
    a.setAttribute('href', 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAAB'
      + 'ytg0kAAAAEklEQVR42mP8z8BQz0AEYBxVSF+FABJADveWkH6oAAAAAElFTkSuQmCC');
    const square = await read();
    a.setAttribute('href', href);
    const said = s => s.includes('printed into the file');
    return {
      ok: said(tall.t) && !said(square.t) && /seconds, start to finish/.test(square.t),
      why: `${tall.w}x${tall.h} claims the strip: ${said(tall.t)}; `
         + `${square.w}x${square.h} claims it: ${said(square.t)} (must be false, timing kept)`,
    };
  });
  record('the lightbox only claims a burned-in strip when there is one', claim.ok, claim.why);

  // ---- the miner page reads both of its units -----------------------------
  // TWO rack units point at /miner.html -- `asicminer` and `gpuminer` -- and for a while
  // the page only spoke about the first, so the surface that actually hashes on this box
  // had no page at all.
  //
  // These assertions are on VALUES, not markup, because a card that renders perfectly and
  // receives nothing is indistinguishable from a working one in a screenshot. Each was
  // watched going red before being kept, against a copy of the site with the bug put back:
  // cutting both status paths turns the first two red on `chip="not present"`; removing the
  // shared GPU panel's VRAM row turns the third red on `vram=""` while the temperature
  // beside it still reads; and writing a plausible `53.01 MH/s` into a gated row -- the
  // dishonest-gauge case this whole site argues against -- turns the fourth red.
  {
    const probe = await ctx.newPage();
    const perrs = [];
    probe.on('pageerror', e => perrs.push(e.message));
    await probe.goto(BASE + '/miner.html', { waitUntil: 'networkidle' });
    // Wait for a reading to arrive, not for a timeout to expire.
    await probe.waitForFunction(
      () => !/^reading/.test(document.getElementById('mg-detail')?.textContent || 'reading'),
      { timeout: 20000 }).catch(() => {});

    const mg = await probe.evaluate(async () => {
      const t = id => (document.getElementById(id)?.textContent || '').trim();
      // The same public endpoint the page reads, so the assertion compares the DOM against
      // the API rather than against a string written into this test.
      const api = await fetch('/api/status').then(r => r.json()).catch(() => null);
      // The two mining halves are one rack row with a `sub` array, so look in both places.
      // Top level first, exactly as the page does: an API that has not restarted yet still
      // publishes `gpuminer` as a unit of its own, and this assertion must pass against
      // both shapes or it fails on the deploy gap rather than on a real defect.
      const all = (api && api.units) || [];
      const u = all.find(x => x.id === 'gpuminer')
             || all.flatMap(x => x.sub || []).find(x => x.id === 'gpuminer');
      return {
        unit: t('mg-unit'), detail: t('mg-detail'), chip: t('mgstate'),
        dot: document.getElementById('mgdot')?.className || '',
        apiState: u && u.state, apiDetail: u && u.detail,
        tel: ['mg-hr', 'mg-pool', 'mg-lock', 'mg-up'].map(t),
        vram: t('m-vram'), temp: t('m-temp'), holder: t('m-holder'),
        asicChip: t('mnstate'),
        gpuHead: t('mghead'), asicHead: t('mnhead'),
      };
    });

    const STATES = ['ready', 'busy', 'queued', 'offline'];
    record('the miner page shows the gpuminer unit\'s own reading',
           !!mg.apiState && mg.chip === mg.apiState && mg.detail === mg.apiDetail &&
           mg.unit.includes('gpuminer') && STATES.includes(mg.apiState) &&
           mg.detail.length > 0,
           `chip="${mg.chip}" api="${mg.apiState}" detail="${mg.detail.slice(0, 70)}"`);
    // The dot is not decoration: green only when the surface is usable, amber while it holds
    // or waits for the card, grey when it is offline.
    const wantDot = (mg.apiState === 'busy' || mg.apiState === 'queued') ? 'busy'
                  : (mg.apiState === 'ready' ? 'on' : '');
    record('the miner card\'s LED tracks the unit state', mg.dot === wantDot,
           `state ${mg.apiState} -> class "${mg.dot}" (want "${wantDot}")`);
    // The shared GPU panel, on a page that has no prompt. It arrives through console.js's
    // existing socket, so this also proves the page did not grow a second data path.
    record('the miner page\'s GPU panel carries live card readings',
           /\d/.test(mg.vram) && /\d/.test(mg.temp) && mg.holder.length > 0,
           `vram="${mg.vram}" temp="${mg.temp}" holding="${mg.holder}"`);
    // Withheld, not faked. Every gated row must say a token is missing rather than show a
    // number, and it must not show a stale one either.
    record('operator telemetry is withheld rather than faked',
           mg.tel.every(v => /token required/.test(v)), mg.tel.join(' | '));
    // One page, two units, two different pieces of hardware. If a future edit merges them,
    // one of the two states has to become a lie -- the GPU miner is configured here and the
    // ASIC panel has no hardware attached.
    //
    // Asserted on the heads being DIFFERENT and the ASIC one naming ASIC, rather than on the
    // GPU one matching a literal: the GPU unit is now just "SyMoNeuRaL Miner" (it is the
    // miner on this box), so a test pinned to the old "Miner GPU" string would fail the
    // rename while the page was perfectly correct -- and pinning it to the new string would
    // pass even if BOTH heads said it.
    record('the miner page keeps its GPU and ASIC units distinct',
           /Miner/.test(mg.gpuHead) && !/ASIC/.test(mg.gpuHead) &&
           /ASIC/.test(mg.asicHead) && mg.gpuHead !== mg.asicHead &&
           STATES.includes(mg.asicChip) && perrs.length === 0,
           `gpu head "${mg.gpuHead.slice(0, 34)}" chip "${mg.chip}", ` +
           `asic head "${mg.asicHead.slice(0, 34)}" chip "${mg.asicChip}"` +
           (perrs.length ? `, JS ERROR: ${perrs[0]}` : ''));

    // Nothing on this page may be clipped, and it must not scroll sideways on a phone. The
    // readings and the reason a reading is absent are the content; an ellipsis on either is
    // data loss with extra steps.
    await probe.setViewportSize({ width: 390, height: 900 });
    await probe.waitForTimeout(250);
    const clip = await probe.evaluate(() => {
      const bad = [];
      document.querySelectorAll('.mg-facts dd, .mg-facts dt, .mg-warn, .mg-lede')
        .forEach(e => {
          const cs = getComputedStyle(e);
          if (cs.textOverflow === 'ellipsis') bad.push(`ellipsis on ${e.id || e.className}`);
          if (e.scrollWidth > e.clientWidth + 1)
            bad.push(`${e.id || e.className} clipped ${e.scrollWidth}>${e.clientWidth}`);
        });
      const vw = document.documentElement.clientWidth;
      if (document.documentElement.scrollWidth > vw + 1)
        bad.push(`page scrolls to ${document.documentElement.scrollWidth} at ${vw}`);
      return bad;
    });
    record('the miner page clips nothing at 390px', clip.length === 0,
           clip.join('; ') || 'clean');
    await probe.close();
  }
  // ---- the gateway page shows the API's own words, and does not light an LED ----
  // docs/specs/gateway-completion.md item 6. Before this, the suite touched gateway.html
  // only in the script-error sweep below -- so the licensing surface could have reported
  // anything at all, or nothing, and every test still passed.
  //
  // It reads /api/status, NOT /api/gateway/state. That route answers 503 while the surface
  // is switched off, which is its correct behaviour and production's current state, so an
  // assertion bound to it would go red on a healthy system -- HANDOVER §3.0d is a list of
  // five verification steps that did exactly that. /api/status carries the gateway unit in
  // every configuration.
  //
  // The comparison is verbatim on purpose. The whole design of this surface is that the
  // detail line is free-text carrying the truth the four state strings cannot express
  // (backend/apps/gateway/__init__.py, "Do not invent a fifth state string"). A page that
  // paraphrased it -- or that fell back to a friendly default when the fetch failed -- would
  // be inventing a reading, which is the one thing this rack exists to not do.
  await page.goto(BASE + '/gateway.html', { waitUntil: 'networkidle' });
  await page.waitForFunction(
    () => !/Reading the surface state/.test(
      document.getElementById('gwdetail')?.textContent || 'Reading the surface state'),
    { timeout: 15000 }).catch(() => {});
  const gw = await page.evaluate(async () => {
    const s = await fetch('/api/status', { headers: { Accept: 'application/json' } })
      .then(r => r.ok ? r.json() : null).catch(() => null);
    const unit = s && (s.units || []).find(u => u.id === 'gateway');
    const led = document.querySelector('#gwhead s');
    return {
      shown: document.getElementById('gwstate')?.textContent?.trim(),
      detail: document.getElementById('gwdetail')?.textContent?.trim(),
      apiState: unit?.state, apiDetail: (unit?.detail || '').trim(),
      // The LED is a bare <s> with no class. symoneural.css renders that as an unlit grey
      // dot; any class the JS added would light it. Reading the computed colour rather than
      // the class list is the lesson from three cascade bugs in this stylesheet -- and an
      // unearned green light on a licensing surface is precisely the decorative indicator
      // .claude/CLAUDE.md forbids.
      ledClass: led ? led.className : null,
      ledColor: led ? getComputedStyle(led).backgroundColor : null,
    };
  });
  record('the gateway page prints the API\'s own state and detail, verbatim',
         !!gw.apiState && gw.shown === gw.apiState &&
         gw.detail.length > 0 && gw.detail === gw.apiDetail,
         `page "${gw.shown}" / api "${gw.apiState}" · detail ${gw.detail === gw.apiDetail
           ? `matches (${gw.detail.length} chars)` : `DIFFERS: "${gw.detail}"`}`);
  record('the gateway status dot is unlit while the surface is offline',
         gw.apiState !== 'offline' || !gw.ledClass,
         `state=${gw.apiState} led class=${JSON.stringify(gw.ledClass)} bg=${gw.ledColor}`);

  // ---- no page throws a script error ------------------------------------
  // This exists because a generator shipped BROKEN JAVASCRIPT to production and the suite
  // passed 22/22 anyway. tuner.html's script had an unterminated string literal -- a `\\n`
  // written into a non-raw Python string in build_pages.py became a real newline inside a
  // JS literal -- so the entire page's behaviour was dead while every assertion about its
  // markup, CSS and endpoints still passed. Counting passes is not the same as the page
  // working, and only a parse check catches that.
  const broken = [];
  for (const pg of ['', 'chat.html', 'image.html', 'ravencalc.html', 'remix.html',
                    'miner.html', 'gateway.html', 'tuner.html', 'build.html',
                    'documentation.html', 'training.html', 'account.html',
                    // The watch page is ~700 lines of inline JS and the most recent thing here,
                    // so it is the likeliest to arrive broken. This visits it COLD -- no handoff
                    // in localStorage -- which is the branch a visitor who types the URL gets,
                    // and the one no other test covers.
                    'tuner-watch.html']) {
    const probe = await ctx.newPage();
    const errs = [];
    probe.on('pageerror', e => errs.push(`${pg || '/'}: ${e.message}`));
    await probe.goto(new URL('/' + pg, BASE).href, { waitUntil: 'networkidle' }).catch(() => {});
    await probe.close();
    broken.push(...errs);
  }
  record('no page throws a script error', broken.length === 0,
         broken.length ? broken.join(' | ').slice(0, 160) : 'all 13 pages clean');

  // ---- the front page folds, and the panel it folds into is readable ------
  // THE PREVIOUS VERSION OF THIS ASSERTION PASSED WHILE THE PAGE WAS BROKEN. It checked
  // that the document does not scroll and that no section was dropped. Both were true, and
  // the layout still shipped with the rack rendered into a 330px window at 1440x900 and a
  // 48px one at 1280x800 -- the scrollbar had simply moved inside the panel, which is worse
  // than scrolling, not better. "The document does not scroll" is not the property a
  // visitor experiences.
  //
  // So the panel height is now the assertion, as a share of the viewport. A floor of 45%
  // is what separates "a pane that scrolls a bit", which is what claude.ai and ESPN do,
  // from a slit. The viewports are picked at the GATE BOUNDARIES, because that is where a
  // layout gate breaks: 1301x740 is one pixel inside it and 1300x900 one pixel outside,
  // and 1280x800 is the exact case that shipped broken.
  const PANELS = ['hero', 'rack', 'console', 'more'];
  const ns = {};
  for (const [w, h, key] of [[1440, 900, 'in'], [1301, 740, 'corner'],
                             [1300, 900, 'out'], [1280, 800, 'slit']]) {
    const probe = await ctx.newPage();
    await probe.setViewportSize({ width: w, height: h });
    await probe.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
    await probe.waitForTimeout(250);
    ns[key] = await probe.evaluate(async (ids) => {
      const d = document.documentElement, out = { worst: 101, worstId: null };
      // BEFORE any click: what does a visitor actually land on? Every other front-page
      // assertion now opens the tab it needs, which means none of them would notice if the
      // landing view broke -- the mirror image of the vacuous check this file just lost.
      // The masthead must be the open panel and the rest closed.
      // COMPUTED DISPLAY, never `.hidden`. The `hidden` property reports the attribute,
      // and an author rule that sets `display` beats the UA stylesheet's display:none --
      // which is exactly how the masthead shipped rendering above every panel while
      // reporting hidden:true, and how this assertion passed while it did.
      const shown = i => { const e = document.getElementById(i);
        return e && getComputedStyle(e).display !== 'none'; };
      out.lands = ids.filter(shown).join(',');
      const ghosts = new Set();
      for (const i of ids) {                       // measure each panel while IT is the open one
        const b = document.querySelector(`.ns-tab[data-panel="${i}"]`);
        if (b) b.click();
        await new Promise(r => setTimeout(r, 120));
        const e = document.getElementById(i);
        if (!e) continue;
        const share = Math.round(100 * e.clientHeight / innerHeight);
        if (share < out.worst) { out.worst = share; out.worstId = i; }
        // While `i` is open, NO other panel may take vertical space. This is the check the
        // whole layout rests on and the one that was missing: the masthead was taking 172px
        // above whichever panel was open, which is where the second scrollbar came from.
        if (d.classList.contains('ns')) {
          ids.filter(o => o !== i && shown(o)
                     && document.getElementById(o).getBoundingClientRect().height > 0)
             .forEach(o => ghosts.add(`${o} visible while ${i} open`));
        }
      }
      out.ghosts = [...ghosts].join('; ');
      out.ns = d.classList.contains('ns');
      out.scrolls = d.scrollHeight > d.clientHeight + 1;
      out.visible = ids.filter(shown).length;
      return out;
    }, PANELS);
    await probe.close();
  }
  // In-gate the landing view is the masthead alone; out-of-gate nothing is hidden at all.
  const folded = k => ns[k].ns && !ns[k].scrolls && ns[k].visible === 1 && ns[k].worst >= 45
                      && ns[k].lands === 'hero' && !ns[k].ghosts;
  const plain = k => !ns[k].ns && ns[k].scrolls && ns[k].visible === PANELS.length
                     && ns[k].lands === PANELS.join(',');
  record('the front page folds into a panel big enough to read',
         folded('in') && folded('corner') && plain('out') && plain('slit'),
         Object.entries(ns).map(([k, v]) =>
           `${k}: ns=${v.ns} scroll=${v.scrolls} lands on [${v.lands}] min panel ${v.worst}% (${v.worstId})`
           + (v.ghosts ? ` GHOSTS: ${v.ghosts}` : '')
         ).join(' | '));

  // ---- the bare domain goes to /overview ----------------------------------
  // Checked WITHOUT following, so the status code is visible: a 301 here would be a bug,
  // because browsers cache it indefinitely and it could not be walked back. Also asserts
  // the tabbed page is still reachable at /index.html rather than orphaned -- it is the
  // page tools/build_split.py reads to build the other four.
  const rootRedir = await ctx.request.get(new URL('/', BASE).href, { maxRedirects: 0 });
  const idx = await ctx.request.get(new URL('/index.html', BASE).href);
  record('the bare domain redirects to /overview, temporarily',
         rootRedir.status() === 302
           && (rootRedir.headers()['location'] || '').endsWith('/overview')
           && idx.status() === 200,
         `/ -> ${rootRedir.status()} ${rootRedir.headers()['location']}; `
         + `/index.html = ${idx.status()}`);

  // ---- one page per section, at its own URL -------------------------------
  // tools/build_split.py writes these and backend/api.py routes them. Three properties,
  // and the third is the one that would rot silently: each page must carry ONLY its own
  // section (a stale generator run leaves a control board welded to every page -- that
  // happened, because `<section id="console" style=...>` did not match a pattern expecting
  // `">`), the clean URL must actually be served, and the section must fit its viewport
  // with no internal scroll at the size Garrett actually uses.
  // Two viewports, and the second is the one that constrains the design: 1301x740 is the
  // tightest the gate allows (584px of panel), so it is where the rack's height budget is
  // actually decided. Checking only a roomy window would let a regression sit unnoticed
  // until someone resized -- which is how Live stack came to overflow by 49-77px between
  // 1301 and 1366 while every measurement taken at 1440 and above looked fine.
  const SPLIT = [];
  for (const [w, h] of [[1855, 745], [1301, 740]]) {
    for (const [slug, keep] of [['overview', 'hero'], ['livestack', 'rack'],
                                ['controlboard', 'console'], ['receipts', 'more']]) {
      SPLIT.push([slug, keep, w, h]);
    }
  }
  const split = [];
  for (const [slug, keep, vw, vh] of SPLIT) {
    const probe = await ctx.newPage();
    await probe.setViewportSize({ width: vw, height: vh });
    const resp = await probe.goto(new URL('/' + slug, BASE).href, { waitUntil: 'networkidle' });
    const m = await probe.evaluate((k) => {
      const ids = ['hero', 'rack', 'console', 'more'];
      const present = ids.filter(i => document.getElementById(i));
      const e = document.getElementById(k);
      return { present, has: !!e,
               fits: e ? e.scrollHeight <= e.clientHeight + 1 : false,
               content: e ? e.scrollHeight : 0, panel: e ? e.clientHeight : 0 };
    }, keep);
    split.push({ slug: `${slug}@${vw}x${vh}`, status: resp ? resp.status() : 0, ...m });
    await probe.close();
  }
  record('each section has its own URL, carrying only itself, fitting one screen',
         split.every(s => s.status === 200 && s.has && s.present.length === 1 && s.fits),
         split.map(s => `${s.slug}=${s.status} [${s.present}] ${s.content}/${s.panel}`).join('  '));

  // ---- the dense sections scale too, and still fit ------------------------
  // Garrett, on a 1080p monitor: "i notice diffrence in control board and receipts but not
  // live stack and overview." He was right about Live stack. The rack and the board sit
  // behind a `max-height` gate that reset all seven type tokens to their base sizes on a
  // short window, so on ~970px of content height those two sections got NONE of the site's
  // enlargement -- measured, 25% of Live stack's text elements changed size and 19% of the
  // board's, against 100% everywhere else. A flat pin was too blunt: 1.20x is the measured
  // ceiling that still fits (1.30x overflows by 2px at 1855x745 and 20px at 1990x970).
  //
  // Two properties, and BOTH are needed -- either alone is satisfied by the bug. That the
  // type grew is what Garrett asked for; that it still fits one screen is what he asked for
  // earlier and must not be traded away to get it. 1990x970 is the viewport that exposed
  // this, so it is the one asserted, and it is NOT covered by the split check above.
  const dense = [];
  for (const [slug, id] of [['livestack', 'rack'], ['controlboard', 'console']]) {
    const probe = await ctx.newPage();
    await probe.setViewportSize({ width: 1990, height: 970 });
    await probe.goto(new URL('/' + slug, BASE).href, { waitUntil: 'networkidle' });
    await probe.waitForTimeout(1200);   // these sections take live readings and grow at load
    const m = await probe.evaluate((k) => {
      const e = document.getElementById(k);
      if (!e) return { missing: true };
      // getComputedStyle hands back a custom property as its raw `clamp(...)` TEXT -- it does
      // not resolve it, so parseFloat gives NaN. Make the browser resolve it by asking for the
      // computed font-size of a throwaway element that inherits the section's tokens.
      const resolve = (tok) => {
        const s = document.createElement('span');
        s.style.cssText = `position:absolute;visibility:hidden;font-size:var(${tok})`;
        e.appendChild(s);
        const px = parseFloat(getComputedStyle(s).fontSize);
        s.remove();
        return Math.round(px * 100) / 100;
      };
      const t3 = resolve('--t3'), t7 = resolve('--t7');
      return { missing: false, t3, t7,
               fits: e.scrollHeight <= e.clientHeight + 1,
               over: e.scrollHeight - e.clientHeight };
    }, id);
    dense.push({ slug, ...m });
    await probe.close();
  }
  // Bases are 20px (--t3) and 10.5px (--t7); above them means the section is scaling at all.
  record('the rack and the board scale with the site and still fit one screen',
         dense.every(d => !d.missing && d.t3 > 20.5 && d.t7 > 10.8 && d.fits),
         dense.map(d => `${d.slug}@1990x970 --t3=${d.t3}px --t7=${d.t7}px over=${d.over}px`).join('  '));

  // ---- the GPU panel beside a prompt carries a real reading ---------------
  // The rule this exists for: no decorative indicators. A panel that renders its layout but
  // never receives data is exactly the fake gauge the site argues against, and it looks
  // identical to a working one in a screenshot. So this asserts on the VALUES, not the
  // markup -- em-dash placeholders and a 0% bar fail.
  await page.goto(new URL('/image.html', BASE).href, { waitUntil: 'networkidle' });
  const gpanel = await page.evaluate(async () => {
    const el = document.querySelector('.gpu-panel');
    if (!el) return { ok: false, why: 'no .gpu-panel on a surface page' };
    // console.js fills these over the websocket it already opens for the rack.
    await new Promise(r => {
      const t0 = Date.now();
      (function poll() {
        const v = document.getElementById('m-vram');
        if ((v && v.textContent && v.textContent !== '\u2014') || Date.now() - t0 > 20000) return r();
        setTimeout(poll, 300);
      })();
    });
    const txt = id => (document.getElementById(id)?.textContent || '').trim();
    const vram = txt('m-vram'), temp = txt('m-temp');
    const units = document.querySelectorAll('.gpu-stack .unit').length;
    return {
      ok: /[0-9]/.test(vram) && /[0-9]/.test(temp) && units >= 5,
      why: `vram="${vram}" temp="${temp}" stack=${units} units link="${txt('con-link')}"`,
    };
  });
  record('the GPU panel beside a prompt shows a real reading', gpanel.ok, gpanel.why);
  await page.goto(BASE + '/index.html', { waitUntil: 'networkidle' });

  // ---- the tuner form is styled, and posts to routes that exist ----------
  // Two bugs shipped together on this page. The `tn-` CSS was never written, so the form
  // rendered as raw unstyled HTML; and the JS posted to /api/tuner/channels, which no
  // router serves, so it fell through to the static mount at "/" and came back 405 Method
  // Not Allowed -- a confusing way to be told the URL is wrong. This asserts the styling
  // exists AND that every endpoint the page names is really served.
  await page.goto(new URL('/tuner.html', BASE).href, { waitUntil: 'networkidle' });
  const tuner = await page.evaluate(async () => {
    const tab = document.querySelector('.tn-tab');
    const inp = document.querySelector('.tn-fields input');
    if (!tab || !inp) return { ok: false, why: 'tuner form markup missing' };
    const styled = parseFloat(getComputedStyle(tab).borderRadius) > 0
                && parseFloat(getComputedStyle(inp).paddingLeft) > 0;
    // The endpoints are READ OUT OF THE PAGE'S OWN SCRIPT, not hardcoded here. An earlier
    // version of this test listed the two correct paths and probed the API directly --
    // which passed happily while the page went on posting to a path that did not exist,
    // so it did not catch the bug it was written for. What matters is that whatever the
    // page actually calls is routed.
    const src = [...document.querySelectorAll('script')].map(s => s.textContent).join('\n');
    const paths = [...new Set([...src.matchAll(/['"](\/api\/tuner\/[a-z\/]+)['"]/g)].map(m => m[1]))];
    if (!paths.length) return { ok: false, why: 'the page names no /api/tuner endpoint' };
    const codes = {};
    let routed = true;
    for (const name of paths) {
      // A path ending in `/` is a PREFIX the page appends an id to -- `/session/<id>`,
      // which the player polls to find out WHY a stream did not start. POSTing to the
      // bare prefix probes a route nobody ever meant to exist and reports 405 for a
      // perfectly healthy page, which is the "check that fails on healthy input" this
      // suite is supposed to be the opposite of. Probe it the way the page uses it --
      // GET, with an id on the end -- and tell "routed, no such session" apart from
      // "no such route" by the body: FastAPI's own miss says "Not Found", ours says
      // what is actually missing.
      if (name.endsWith('/')) {
        const r = await fetch(name + '__probe__');
        const j = await r.json().catch(() => ({}));
        const isRouted = typeof j.detail === 'string' && j.detail !== 'Not Found';
        codes[name] = (isRouted ? 'routed' : 'NOT ROUTED') + `(GET ${r.status})`;
        if (!isRouted) routed = false;
        continue;
      }
      const r = await fetch(name, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: '{}' });
      codes[name] = r.status;
      if (r.status === 404 || r.status === 405) routed = false;
    }
    return { ok: styled && routed,
             why: `styled=${styled}, ` + Object.entries(codes)
                   .map(([k, v]) => `${k.replace('/api/tuner', '')}=${v}`).join(' ') };
  });
  record('the tuner form is styled and its endpoints are routed', tuner.ok, tuner.why);
  await page.goto(BASE + '/index.html', { waitUntil: 'networkidle' });

  // ---- .card is not redefined out from under the rest of the site ---------
  // `.card` was defined twice: the general card near the top of the stylesheet, and the
  // homepage receipts grid written as a bare `.card` further down, which therefore won
  // everywhere. Eleven cards on documentation.html were silently wearing the receipts
  // styling. This asserts the two components stay distinguishable, which is the property
  // that broke -- not the specific values.
  await page.goto(new URL('/documentation.html', BASE).href, { waitUntil: 'networkidle' });
  const genCards = await page.evaluate(() => {
    const out = { outside: null, n: 0 };
    for (const el of document.querySelectorAll('.card')) {
      if (el.closest('.cards')) continue;
      const cs = getComputedStyle(el);
      out.n++;
      out.outside = out.outside || { display: cs.display, padding: cs.padding };
    }
    return out;
  });
  record('a .card outside the receipts grid keeps its own styling',
         genCards.n > 0 && genCards.outside?.display === 'block',
         genCards.n ? `${genCards.n} general cards, display:${genCards.outside.display} `
                    + `padding:${genCards.outside.padding}` : 'no general .card found');
  await page.goto(BASE + '/index.html', { waitUntil: 'networkidle' });

  // ---- the receipts grid, and the order page it feeds ----------------------
  const cards = await page.$$eval('#more .card', els => els.map(e => ({
    tag: e.querySelector('.ctag')?.textContent.trim(),
    title: e.querySelector('b')?.textContent.trim(),
    href: e.getAttribute('href'),
  })));
  record('receipts render as cards', cards.length >= 8 &&
         cards.every(c => c.tag && c.title && c.href), `${cards.length} cards`);

  // Every "Have one built" route must land on a real page. The order section was moved
  // off the front page; a dangling link would take the one lead-generation click nowhere.
  const buildLinks = await page.$$eval('a[href="/build.html"]', els => els.length);
  const buildRes = await page.request.get(BASE + '/build.html');
  const buildTxt = await buildRes.text();
  record('the order page exists and is linked', buildRes.status() === 200 &&
         buildLinks >= 2 && buildTxt.includes('Tell us what you want to run'),
         `${buildLinks} links -> ${buildRes.status()}`);

  // ---- the band is four renders in a row, and the constellation moved -------
  // Both halves matter. On the front page the constellation's absolutely-positioned
  // renders collapsed into a vertical column in narrow gutters, which is what a visitor
  // actually saw; it now lives on /build.html where there is room. If .sky ever reappears
  // on the front page, or the row ever stops being a row, this fails.
  // The front page opened with a hero, then a 930px band restating the argument, and the
  // rack -- the machine reading its own sensors while you watch -- began ~1,300px down.
  // The requirement is pitch, hero and rack all reachable on a first look at 100% zoom.
  // This asserts the shape that delivers it rather than a pixel count, which would break
  // on any copy edit: pitch and hero on one row, and four renders in the gutters costing
  // no vertical space.
  //
  // The old version also required `rack.top < innerHeight`. THAT CLAUSE HAD GONE VACUOUS:
  // once the rack became a tab panel it is hidden on load, and a hidden element reports
  // top 0, so the check passed for free and would have kept passing had the rack been
  // deleted outright. "Within one viewport" is not the property any more -- "one click
  // away, and the click works without scrolling the page" is. So it is measured that way,
  // and the guard is that the rack must have a real box AFTER its tab is opened.
  const fold = await page.evaluate(() => {
    const box = s => { const e = document.querySelector(s); return e && e.getBoundingClientRect(); };
    const hero = box('.mh-hero'), pitch = box('.mh-pitch');
    if (!hero || !pitch) return { why: 'masthead missing' };
    return {
      sideBySide: Math.abs(hero.top - pitch.top) < hero.height,   // same row, not stacked
      arts: document.querySelectorAll('.gart').length,
      sky: !!document.querySelector('.sky'),
    };
  });
  await openTab(page, 'rack');
  const reach = await page.evaluate(() => {
    const r = document.querySelector('.rack');
    const d = document.documentElement;
    return { h: r ? Math.round(r.getBoundingClientRect().height) : 0,
             top: r ? Math.round(r.getBoundingClientRect().top) : -1,
             vh: innerHeight, pageScrolled: d.scrollTop > 1 };
  });
  await openTab(page, 'hero');
  record('pitch, hero and rack fit one look',
         fold.sideBySide && fold.arts === 4 && !fold.sky
           && reach.h > 200 && reach.top < reach.vh && !reach.pageScrolled,
         fold.why || `${fold.arts} gutter renders; one click opens a ${reach.h}px rack at `
         + `${reach.top}px of ${reach.vh}px without scrolling the page`
         + (fold.sky ? ', but .sky is still on the front page' : ''));

  record('the constellation moved to the order page',
         buildTxt.includes('class="sky"') && (buildTxt.match(/class="art"/g) || []).length >= 19,
         `${(buildTxt.match(/class="art"/g) || []).length} renders on /build.html`);

  // ---- the header is links, not JavaScript menus ---------------------------
  // The two dropdowns painted underneath the hero: the menu was z-index:60 inside a header
  // that is itself a z-index:20 stacking context, so 60 only ever competed with the header's
  // own children. Both opened onto a single destination, so they are plain links now.
  const nav = await page.evaluate(() => ({
    menus: document.querySelectorAll('.navitem, .menu, nav button').length,
    links: [...document.querySelectorAll('header nav a')].map(a => a.getAttribute('href')),
  }));
  record('the header has no dropdowns left', nav.menus === 0,
         nav.menus ? `${nav.menus} menu element(s) remain` : nav.links.join(' '));

  // ---- stale CSS can never be served for new markup ------------------------
  const unstamped = await page.$$eval(
    'link[rel=stylesheet][href^="/"], script[src^="/"]',
    els => els.map(e => e.getAttribute('href') || e.getAttribute('src'))
             .filter(u => !/\?v=[0-9a-f]{6,}$/.test(u)));
  record('every local asset is cache-busted', unstamped.length === 0,
         unstamped.join(', ') || 'all stamped');

  // ---- the fleet table states its assumption, and loses nothing -------------
  // Two separate risks, both worth a permanent guard.
  //
  // The honesty one first: every money column in that table is projected off an occupancy
  // assumption, and docs/specs/symon-ml-review.md §5 exists because a pitch once quoted
  // "~$5,800/month" whose arithmetic only closed at 59.9% occupancy that the document never
  // stated. The generator prints the rate into the caption from a named constant. If someone
  // later edits the copy and drops it, the table silently becomes the thing that review
  // criticised -- so assert the caption still carries a percentage.
  //
  // The layout one second: it is a 7-column table, and the fluid scale takes cells to
  // 18.75px at 2560px. CLAUDE.md forbids truncation outright -- the rack was cutting an
  // Apache-2.0 attribution down to "...7B-Ins..." -- so check at the widest viewport that no
  // cell is clipping and that the page itself never scrolls sideways. `.tw` scrolling
  // internally is fine and expected; the body scrolling is not.
  await page.setViewportSize({ width: 2560, height: 1440 });
  await page.goto(BASE + '/documentation.html', { waitUntil: 'networkidle' });
  const fleet = await page.evaluate(() => {
    const tws = [...document.querySelectorAll('#cost .tw')];
    if (!tws.length) return { missing: true };
    const t = tws[tws.length - 1].querySelector('table');
    const clipped = [...t.querySelectorAll('th,td,span')].filter(e => {
      const s = getComputedStyle(e);
      return s.textOverflow === 'ellipsis' ||
             (s.whiteSpace === 'nowrap' && e.scrollWidth > e.clientWidth + 1);
    }).map(e => e.textContent.trim().slice(0, 40));
    return {
      caption: (t.querySelector('caption') || {}).textContent?.trim() || '',
      cols: t.querySelectorAll('thead th').length,
      rows: t.querySelectorAll('tbody tr').length,
      clipped,
      bodyScrolls: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    };
  });
  record('the fleet table states its occupancy assumption',
         !fleet.missing && /\d+\s*%/.test(fleet.caption),
         fleet.missing ? 'no table found in #cost' : fleet.caption);
  record('the fleet table loses no text at 2560px',
         !fleet.missing && fleet.clipped.length === 0 && !fleet.bodyScrolls,
         fleet.missing ? 'no table' :
           `${fleet.cols} cols x ${fleet.rows} rows, ` +
           (fleet.clipped.length ? `CLIPPED: ${fleet.clipped.join(' | ')}` : 'nothing clipped') +
           `, body h-scroll ${fleet.bodyScrolls}`);
  await page.setViewportSize({ width: 1440, height: 1000 });

  // ---- Symon Say News: the bar along the bottom ----------------------------
  // The ticker is built entirely in JavaScript -- no markup for it exists in any of the 23
  // HTML files -- so this suite is the only place it can be tested at all. Three properties,
  // and the first one is what makes the other two meaningful on any box:
  //
  // THE ASSERTION IS AGAINST THE SERVER'S OWN ANSWER, not against a hard-coded expectation.
  // The news surface is off by default (SYMONEURAL_NEWS_ENABLED unset), and with it off the
  // correct rendering is NOTHING AT ALL -- no bar, no placeholder, no empty strip. So the
  // endpoint is asked first and the expected DOM follows from it. Written the other way this
  // check would fail on every box where the switch is off, which is most of them, and it
  // would fail for the one reason that is not a defect.
  const newsState = await page.evaluate(async () => {
    try {
      const r = await fetch('/api/news/ticker', { cache: 'no-store' });
      if (!r.ok) return { reachable: false, status: r.status };
      const d = await r.json();
      return { reachable: true, enabled: !!d.enabled, count: d.count,
               stale: !!d.stale, newest: d.newest_age_s,
               allHttps: (d.items || []).every(i => String(i.url).startsWith('https://')) };
    } catch (e) { return { reachable: false, status: 0 }; }
  });
  const wantBar = newsState.reachable && newsState.enabled && newsState.count > 0;
  {
    // 1300x900 is out of the fold gate, so this is the fixed-position branch: the bar sits
    // on the viewport while the document scrolls behind it. Scrolled to the very end, the
    // footer must still be ABOVE the bar -- the body padding-bottom is what buys that, and
    // without it the site's own credit line would spend its life underneath the ticker.
    const probe = await ctx.newPage();
    await probe.setViewportSize({ width: 1300, height: 900 });
    await probe.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
    await probe.waitForTimeout(900);
    await probe.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await probe.waitForTimeout(300);
    const m = await probe.evaluate(() => {
      const bar = document.getElementById('symonsaynews');
      if (!bar) return { bar: false, snon: document.documentElement.classList.contains('sn-on') };
      const r = bar.getBoundingClientRect();
      const f = document.querySelector('footer').getBoundingClientRect();
      const run = bar.querySelector('.sn-run');
      const items = [...bar.querySelectorAll('.sn-lane:not([aria-hidden]) .sn-item')];
      return {
        bar: true, snon: document.documentElement.classList.contains('sn-on'),
        pos: getComputedStyle(bar).position, items: items.length,
        https: items.every(a => a.href.startsWith('https://')),
        blank: items.some(a => !a.querySelector('.sn-head').textContent.trim()),
        // A lane duplicated for the seamless wrap, and only for that: two lanes, the second
        // hidden from the accessibility tree and out of the tab order.
        lanes: bar.querySelectorAll('.sn-lane').length,
        dupeHidden: bar.querySelectorAll('.sn-lane[aria-hidden="true"]').length === 1,
        // A measured duration, not the initial 0s: an unmeasured crawl is a still bar.
        secs: parseFloat(getComputedStyle(run).animationDuration) || 0,
        lamp: !!bar.querySelector('.sn-lamp'), old: bar.classList.contains('sn-old'),
        clear: Math.round(r.top - f.bottom), pad: getComputedStyle(document.body).paddingBottom,
      };
    });
    await probe.close();
    record('the news bar renders exactly when the news surface has headlines',
           wantBar
             ? (m.bar && m.snon && m.items === newsState.count && m.https && !m.blank
                && m.lanes === 2 && m.dupeHidden && m.secs > 0 && newsState.allHttps)
             : (!m.bar && !m.snon),
           wantBar ? `${m.items}/${newsState.count} headlines, ${m.secs}s crawl, ${m.pos}`
                   : `surface ${newsState.reachable ? (newsState.enabled ? 'on but empty' : 'off')
                                                    : 'unreachable(' + newsState.status + ')'}`
                     + ` -> no bar (${!m.bar})`);
    // The lamp is a claim: it says these headlines are current. It may only be lit when the
    // server said the newest one is under six hours old. CLAUDE.md's rule about decorative
    // indicators applies to a pulsing green dot over yesterday's news exactly as it does to
    // a fake GPU reading.
    const fresh = wantBar && !newsState.stale && typeof newsState.newest === 'number'
                  && newsState.newest <= 21600;
    record('the news bar claims to be live only when its newest headline is',
           !wantBar || (m.lamp === fresh && m.old === !fresh),
           !wantBar ? 'no bar to check'
                    : `newest=${newsState.newest}s stale=${newsState.stale}`
                      + ` -> lamp=${m.lamp} sn-old=${m.old}`);
    record('the news bar leaves the footer readable at the end of a scroll',
           !wantBar || (m.pos === 'fixed' && m.clear >= 0),
           !wantBar ? 'no bar to check' : `${m.pos}, body pad ${m.pad}, ${m.clear}px clear`);
  }
  {
    // Both age branches, driven by a FABRICATED payload rather than by whatever the feeds
    // happen to be carrying today. The three checks above assert the real integration, and
    // they are the ones that would catch a broken endpoint -- but they can only ever exercise
    // one branch of the label, because the live bar is nearly always fresh. Mutation-testing
    // showed exactly that: gutting the age check in ui.js so the lamp is ALWAYS lit left all
    // 47 assertions passing, because "always lit" and "correctly lit" agree on fresh data.
    //
    // So the endpoint is intercepted and answered with two synthetic ages. Nothing here
    // reaches a publisher, and the numbers are chosen to sit on either side of ui.js's
    // six-hour line.
    const ITEMS = [
      { title: 'A synthetic headline, served by tests/frontend.mjs', url: 'https://example.com/a',
        source: 'Test', topic: 'releases', at: 1, score: 1 },
      { title: 'A second synthetic headline', url: 'https://example.com/b',
        source: 'Test', topic: 'models', at: 1, score: 0.9 },
    ];
    for (const [name, newest, stale, wantLamp, wantSays] of
         [['fresh (15 min old)', 900, false, true, ''],
          ['stale (5 days old)', 5 * 86400, true, false, '5d old']]) {
      const probe = await ctx.newPage();
      await probe.route('**/api/news/ticker', r => r.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ enabled: true, items: ITEMS, count: ITEMS.length, at: 1,
                               age_s: 30, stale, newest_at: 1, newest_age_s: newest,
                               interval_s: 900, sources: [], error: null }),
      }));
      await probe.setViewportSize({ width: 1300, height: 900 });
      await probe.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
      await probe.waitForTimeout(700);
      const m = await probe.evaluate(() => {
        const bar = document.getElementById('symonsaynews');
        if (!bar) return { bar: false };
        return { bar: true, lamp: !!bar.querySelector('.sn-lamp'),
                 old: bar.classList.contains('sn-old'),
                 brand: bar.querySelector('.sn-brand').textContent.trim(),
                 age: (bar.querySelector('.sn-age') || {}).textContent || '',
                 items: bar.querySelectorAll('.sn-lane:not([aria-hidden]) .sn-item').length };
      });
      await probe.close();
      record(`the news bar labels a bar of ${name} correctly`,
             m.bar && m.items === ITEMS.length && m.lamp === wantLamp && m.old === !wantLamp
             && m.age.trim() === wantSays && m.brand.indexOf('Symon Say News') >= 0,
             m.bar ? `brand="${m.brand}" lamp=${m.lamp} sn-old=${m.old}` : 'no bar rendered');
    }
  }
  {
    // Reduced motion: the crawl stops and the duplicate lane goes, but every headline must
    // still be REACHABLE -- the window becomes a scrollable strip. Removing the motion is
    // the request; removing the news with it would not be.
    const rm = await browser.newContext({ viewport: { width: 1300, height: 900 },
                                          reducedMotion: 'reduce' });
    const probe = await rm.newPage();
    await probe.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
    await probe.waitForTimeout(900);
    const m = await probe.evaluate(() => {
      const bar = document.getElementById('symonsaynews');
      if (!bar) return { bar: false };
      const win = bar.querySelector('.sn-window');
      return { bar: true,
               name: getComputedStyle(bar.querySelector('.sn-run')).animationName,
               shown: [...bar.querySelectorAll('.sn-lane')]
                        .filter(l => getComputedStyle(l).display !== 'none').length,
               reachable: win.scrollWidth > win.clientWidth,
               scrollable: getComputedStyle(win).overflowX };
    });
    await rm.close();
    record('the news bar stops for reduced motion without losing a headline',
           !wantBar || (m.bar && m.name === 'none' && m.shown === 1
                        && m.reachable && m.scrollable === 'auto'),
           !wantBar ? 'no bar to check'
                    : `animation=${m.name}, ${m.shown} lane shown, overflow-x=${m.scrollable}`);
  }

  // ---- calc ----------------------------------------------------------------
  await page.goto(BASE + '/ravencalc.html', { waitUntil: 'networkidle' });
  const calcBox = await page.$('input[type=text], textarea');
  if (calcBox) {
    await calcBox.fill('integrate(x**2, x)');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(4000);
    const txt = await page.evaluate(() => document.body.innerText);
    record('ravencalc renders an exact result', /x\*\*3\/3|x\^{3}|frac/.test(txt),
           txt.match(/x\*\*3\/3/)?.[0] || 'see page');
  } else {
    record('ravencalc input found', false, 'no input on /ravencalc.html');
  }

  // ---- image: the one that was broken --------------------------------------
  await page.goto(BASE + '/image.html', { waitUntil: 'networkidle' });
  const promptBox = await page.$('input[type=text], textarea');
  record('image prompt box present', !!promptBox);
  if (promptBox) {
    await promptBox.fill('a single green LED on a dark rack panel');
    // Must be specific. 'button:has-text("Generate"), button' matched the header's
    // Documentation dropdown once the nav gained <button> elements -- a selector list
    // returns the first element in DOM order matching *either* branch, so the fallback
    // silently won and the test clicked open a menu and waited 4 minutes for an image.
    const btn = page.locator('#app button, main button, form button, button')
                    .filter({ hasText: /generate/i }).first();
    await btn.click();
    // a cold FLUX load plus a render; chat gets evicted first
    await page.waitForSelector('img[src*="/api/gen/"]', { timeout: 240000 });
    // naturalWidth is 0 while the bytes are still in flight as well as when the
    // request 404s, so waiting for decode is what makes the next assertion mean
    // "the visitor sees an image" rather than "an <img> tag exists".
    await page.waitForFunction(() => {
      const el = document.querySelector('img[src*="/api/gen/"]');
      return el && el.complete;
    }, { timeout: 60000 });
    const img = await page.$eval('img[src*="/api/gen/"]', el => ({
      src: el.getAttribute('src'),
      w: el.naturalWidth, h: el.naturalHeight,
    }));
    // naturalWidth is 0 for a broken image -- this is the assertion that would have
    // caught the 404 that shipped.
    record('generated image actually loads', img.w > 0 && img.h > 0,
           `${img.src} -> ${img.w}x${img.h}`);
    record('render is served from the API, not the webroot',
           img.src.startsWith('/api/gen/'), img.src);
  }
} catch (e) {
  record('run completed', false, e.message);
} finally {
  await page.screenshot({ path: `${SHOTS}/final.png`, fullPage: false }).catch(() => {});
  await browser.close();
}

if (failed.length) console.log('\nfailed requests / js errors:\n  ' + failed.join('\n  '));
const bad = results.filter(r => !r.ok).length;
console.log(`\n${results.length - bad}/${results.length} passed`);
process.exit(bad ? 1 : 0);
