// Drive the Stickers surface in a real browser, all three ways in.
//
//   node tests/stickers.mjs [baseURL]
//
// **A separate file from `tests/frontend.mjs` on purpose.** That file is maintained by
// whoever owns the site generators and two agents editing one test file clobber each
// other; `tests/tuner_failpaths.mjs` set the precedent. Same harness, same system Chrome,
// no browser download.
//
// Every assertion here exists because of something that either went wrong or could go
// wrong silently:
//
//   - the surface was built and **never mounted into `backend/api.py`**, so every route
//     404'd while the page looked finished. The first assertion below is that one.
//   - a sticker can decode perfectly and be a solid opaque square, so alpha is measured
//     rather than inferred from the image loading.
//   - a control offered for a capability the box does not have is the fake-activity-light
//     failure `.claude/CLAUDE.md` forbids, so the gating is asserted against /state.
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
const failed = [];
page.on('response', r => { if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`); });
page.on('pageerror', e => failed.push(`jserror: ${e.message}`));

// Stickers are prepended, so the newest is the first child. **Every per-sticker assertion
// must be scoped to it.** A bare `.sg-card` selector matches every card in the sheet, and
// the first version of this file asserted the spoken sticker's alpha against the *previous*
// card's image -- passing for the wrong reason on one run and failing on the next.
const NEWEST = '.sg-card:first-child';

// A 1x1 red PNG is enough to prove the upload path carries bytes end to end. The alpha
// assertions use a real photograph via the API tests; this is about the browser half.
const TINY_PNG =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

// Read channel four of what the <img> actually shows, by drawing it to a canvas. An image
// that loads is not the same as an image with transparency, and the whole surface is an
// argument about the second one.
const alphaOf = (sel) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el || !el.naturalWidth) return null;
  const c = document.createElement('canvas');
  c.width = el.naturalWidth; c.height = el.naturalHeight;
  const g = c.getContext('2d');
  g.drawImage(el, 0, 0);
  const d = g.getImageData(0, 0, c.width, c.height).data;
  let clear = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] === 0) clear++;
  return { w: c.width, h: c.height, transparent: clear / (d.length / 4) };
}, sel);

try {
  // ---- the surface is actually mounted -------------------------------------
  //
  // This is the assertion that would have caught the real defect: the page shipped and
  // was live while `backend/api.py` contained no reference to the surface at all.
  // The page is loaded first so the fetch below is same-origin -- exactly how a visitor
  // reaches the API, and the only configuration the real frontend works in.
  await page.goto(BASE + '/sigils.html', { waitUntil: 'networkidle' });
  const st = await page.evaluate(async () => {
    const r = await fetch('/api/sigils/state');
    return { status: r.status, body: r.ok ? await r.json() : null };
  });
  record('the sticker surface is mounted in the API', st.status === 200,
         `GET /api/sigils/state -> ${st.status}`);
  if (st.status !== 200) throw new Error('surface not mounted; nothing else can be asserted');
  record('three ways in are reported',
         ['text', 'image', 'audio'].every(k => k in st.body.inputs),
         JSON.stringify(st.body.inputs));

  // ---- the three controls exist and match what the box can do --------------
  const modes = await page.$$eval('#sg-modes .sg-mode', els => els.map(e => ({
    m: e.dataset.m, disabled: e.disabled, label: e.textContent.trim(),
  })));
  record('three input modes are offered', modes.length === 3,
         modes.map(m => m.label).join(' | '));
  for (const key of ['text', 'image', 'audio']) {
    const btn = modes.find(m => m.m === key);
    // Gating asserted in both directions. A mode enabled while /state says it cannot run
    // is a dishonest control; a mode disabled while /state says it can is a regression
    // that would quietly remove a feature.
    record(`the ${key} control matches /state`,
           !!btn && btn.disabled === !st.body.inputs[key],
           `enabled=${!btn?.disabled} state=${st.body.inputs[key]}`);
  }

  // ---- typed path ----------------------------------------------------------
  await page.click('#sg-modes .sg-mode[data-m="text"]');
  await page.fill('#prompt', 'a raven perched, wings folded');
  await page.click('#send');
  await page.waitForSelector(NEWEST + ' img[src*="/api/gen/"]', { timeout: 300000 });
  await page.waitForFunction(s => {
    const el = document.querySelector(s);
    return el && el.complete && el.naturalWidth > 0;
  }, NEWEST + ' img[src*="/api/gen/"]', { timeout: 120000 });
  const typed = await alphaOf(NEWEST + ' img[src*="/api/gen/"]');
  record('a typed sticker decodes', !!typed && typed.w > 0, JSON.stringify(typed));
  // A solid square decodes perfectly and is worthless. This is the assertion that tells
  // the two apart without a human looking at it.
  record('a typed sticker has real transparency', !!typed && typed.transparent > 0.05,
         `${Math.round((typed?.transparent ?? 0) * 1000) / 10}% clear`);
  const typedMatte = await page.$$eval(NEWEST + ' dt', els =>
    els.map(e => e.textContent.trim()));
  record('the typed path reports which matte ran', typedMatte.includes('matte'),
         typedMatte.join(','));
  record('the typed path reports the field it actually painted',
         typedMatte.includes('field found'), typedMatte.join(','));

  // ---- uploaded picture, cut out -------------------------------------------
  if (st.body.inputs.image) {
    await page.click('#sg-modes .sg-mode[data-m="image"]');
    // The field-colour control must disappear for a cut-out: no field is painted, so
    // offering to choose one would be offering a setting that does nothing.
    await page.click('#sg-imgmode .sg-field[data-v="cutout"]');
    record('a cut-out hides the field-colour control',
           await page.$eval('#sg-fieldblock', e => e.hidden), 'sg-fieldblock hidden');
    record('a cut-out hides the strength slider',
           await page.$eval('#sg-strengthctl', e => e.hidden), 'sg-strengthctl hidden');

    await page.click('#sg-imgmode .sg-field[data-v="redraw"]');
    record('a re-draw shows the strength slider',
           !(await page.$eval('#sg-strengthctl', e => e.hidden)), 'sg-strengthctl shown');
    // The measured ceiling has to reach the actual input element, not just the prose.
    const cap = await page.$eval('#sg-strength', e => parseFloat(e.max));
    record('the strength slider carries the measured ceiling',
           cap === st.body.image.max_strength, `max=${cap} state=${st.body.image.max_strength}`);

    await page.click('#sg-imgmode .sg-field[data-v="cutout"]');
    // setInputFiles needs a real file; build one from the data URI in the page context
    // instead, which also exercises the FileReader path the visitor uses.
    await page.evaluate(async (b64) => {
      const bin = atob(b64);
      const arr = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
      const dt = new DataTransfer();
      dt.items.add(new File([arr], 'probe.png', { type: 'image/png' }));
      const input = document.querySelector('#sg-imgfile');
      input.files = dt.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }, TINY_PNG);
    await page.waitForFunction(() => !document.querySelector('#sg-thumb').hidden,
                               { timeout: 10000 });
    record('an uploaded picture previews before it is sent', true, 'thumbnail shown');

    const before = await page.$$eval('.sg-card', els => els.length);
    await page.click('#send');
    await page.waitForFunction(n => document.querySelectorAll('.sg-card').length > n,
                               before, { timeout: 30000 });
    await page.waitForFunction(() => {
      const el = document.querySelector('.sg-card');
      return el && !el.textContent.includes('working');
    }, { timeout: 300000 });
    const cutText = await page.$eval(NEWEST, e => e.textContent);
    // A 1x1 image cannot produce a meaningful cut, so this asserts the round trip and
    // the honesty of the readings rather than the quality of the matte.
    record('the cut-out path completes in the browser',
           !cutText.includes('That did not work'), cutText.slice(0, 120));
    // No GPU is taken on this path, so no render time may be printed. A "0 s render"
    // here would be reporting a measurement of something that never ran.
    const cutKeys = await page.$$eval(NEWEST + ' dt', els => els.map(e => e.textContent.trim()));
    record('a cut-out prints no render time', !cutKeys.includes('render'),
           cutKeys.join(','));
    record('a cut-out names the matte that ran', cutKeys.includes('matte'),
           cutKeys.join(','));
  }

  // ---- spoken path ---------------------------------------------------------
  if (st.body.inputs.audio) {
    await page.click('#sg-modes .sg-mode[data-m="audio"]');
    record('the record control is offered when the transcriber is installed',
           await page.$eval('#sg-recbtn', e => !e.disabled), 'enabled');
    // The indicator must be driven by MediaRecorder's own state, so before any recording
    // it must be off. A dot that is lit at rest is the decorative-status-light failure.
    record('the recording indicator is dark before anything is recorded',
           !(await page.$eval('#sg-dot', e => e.classList.contains('sg-on'))), 'sg-dot off');

    // Feed the real 11 s sample through the file picker rather than the microphone --
    // Chrome's fake device would test the harness, not the surface.
    {
      await page.setInputFiles('#sg-audfile', join(REPO, 'contrib/whisper.cpp/samples/jfk.wav'));
      await page.waitForFunction(
        () => document.querySelector('#sg-heard').textContent.includes('KiB'),
        { timeout: 10000 });
      const before = await page.$$eval('.sg-card', els => els.length);
      await page.click('#send');
      await page.waitForFunction(n => document.querySelectorAll('.sg-card').length > n,
                                 before, { timeout: 30000 });
      await page.waitForSelector(NEWEST + ' img[src*="/api/gen/"]', { timeout: 300000 });
      await page.waitForFunction(s => {
        const el = document.querySelector(s);
        return el && el.complete && el.naturalWidth > 0;
      }, NEWEST + ' img[src*="/api/gen/"]', { timeout: 120000 });
      const spoken = await alphaOf(NEWEST + ' img[src*="/api/gen/"]');
      record('a spoken sticker decodes and has transparency',
             !!spoken && spoken.transparent > 0.02, JSON.stringify(spoken));
      const heard = await page.$eval(NEWEST + ' .sg-heard', e => e.textContent).catch(() => '');
      // The transcript is shown so a visitor can tell a mishearing from a bad render.
      // Those have different fixes, and without the transcript both look identical.
      record('the transcript is shown verbatim with the sticker',
             heard.toLowerCase().includes('country'), heard.slice(0, 90));
      const spokenKeys = await page.$$eval(NEWEST + ' dt', els =>
        els.map(e => e.textContent.trim()));
      record('transcribe time is reported apart from render time',
             spokenKeys.includes('transcribed') && spokenKeys.includes('render'),
             spokenKeys.join(','));
    }
  }

  // ---- layout --------------------------------------------------------------
  //
  // Read computed styles rather than reasoning about the cascade: three bugs on this site
  // have come from generic class names colliding across components.
  await page.setViewportSize({ width: 390, height: 900 });
  await page.waitForTimeout(200);
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  record('nothing overflows the viewport at 390px', overflow <= 1, `${overflow}px over`);
  // An ellipsis on a reading is data loss with extra steps, and the rule is repo-wide.
  const clipped = await page.evaluate(() =>
    [...document.querySelectorAll('.sg-readings dd, .sg-file, .sg-heard, .sg-why')]
      .filter(e => getComputedStyle(e).textOverflow === 'ellipsis').length);
  record('no reading is truncated with an ellipsis', clipped === 0, `${clipped} clipped`);
} catch (e) {
  record('run completed', false, e.message);
} finally {
  await page.screenshot({ path: `${SHOTS}/stickers.png`, fullPage: false }).catch(() => {});
  await browser.close();
}

if (failed.length) console.log('\nfailed requests / js errors:\n  ' + failed.join('\n  '));
const bad = results.filter(r => !r.ok).length;
console.log(`\n${results.length - bad}/${results.length} passed`);
process.exit(bad ? 1 : 0);
