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
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
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
  record('train unit is renamed',
         units.some(u => u.name === 'SyMoNeuRaL Quantized Low-Rank Adaptation Tool'));

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
          !clipped && /seed \d/.test(t) && /FLUX/.test(t) && /RTX/.test(t),
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
                    'documentation.html', 'training.html', 'account.html']) {
    const probe = await ctx.newPage();
    const errs = [];
    probe.on('pageerror', e => errs.push(`${pg || '/'}: ${e.message}`));
    await probe.goto(new URL('/' + pg, BASE).href, { waitUntil: 'networkidle' }).catch(() => {});
    await probe.close();
    broken.push(...errs);
  }
  record('no page throws a script error', broken.length === 0,
         broken.length ? broken.join(' | ').slice(0, 160) : 'all 12 pages clean');

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
    await probe.goto(BASE, { waitUntil: 'networkidle' });
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
  await page.goto(BASE, { waitUntil: 'networkidle' });

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
    for (const name of paths) {
      const r = await fetch(name, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: '{}' });
      codes[name] = r.status;
    }
    const routed = Object.values(codes).every(c => c !== 405 && c !== 404);
    return { ok: styled && routed,
             why: `styled=${styled}, ` + Object.entries(codes)
                   .map(([k, v]) => `${k.replace('/api/tuner', '')}=${v}`).join(' ') };
  });
  record('the tuner form is styled and its endpoints are routed', tuner.ok, tuner.why);
  await page.goto(BASE, { waitUntil: 'networkidle' });

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
  await page.goto(BASE, { waitUntil: 'networkidle' });

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
