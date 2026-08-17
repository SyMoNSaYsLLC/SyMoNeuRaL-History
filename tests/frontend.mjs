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
         units.every(u => ['GPU', 'CPU', '--'].includes(u.bus)),
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
