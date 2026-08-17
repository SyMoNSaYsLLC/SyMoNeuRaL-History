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

try {
  // ---- rack ----------------------------------------------------------------
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
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
  // on any copy edit: pitch and hero on one row, four renders in the gutters costing no
  // vertical space, and the rack starting inside one viewport of the top.
  const fold = await page.evaluate(() => {
    const box = s => { const e = document.querySelector(s); return e && e.getBoundingClientRect(); };
    const hero = box('.mh-hero'), pitch = box('.mh-pitch'), rack = box('.rack');
    if (!hero || !pitch || !rack) return { why: 'masthead or rack missing' };
    return {
      sideBySide: Math.abs(hero.top - pitch.top) < hero.height,   // same row, not stacked
      rackTop: Math.round(rack.top + window.scrollY),
      vh: window.innerHeight,
      arts: document.querySelectorAll('.gart').length,
      sky: !!document.querySelector('.sky'),
    };
  });
  record('pitch, hero and rack fit one look',
         fold.sideBySide && fold.arts === 4 && !fold.sky && fold.rackTop < fold.vh,
         fold.why || `rack at ${fold.rackTop}px of ${fold.vh}px, ${fold.arts} gutter renders` +
         (fold.sky ? ', but .sky is still on the front page' : ''));

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
