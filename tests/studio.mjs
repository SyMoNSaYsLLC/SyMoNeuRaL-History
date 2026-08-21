// Browser check for /studio: the Studio surface, end to end, in a real browser.
//
//   node tests/studio.mjs http://127.0.0.1:8875
//   SYMONEURAL_STUDIO_TOKEN=<secret> node tests/studio.mjs http://127.0.0.1:8875
//
// **This is not part of `tests/frontend.mjs` and must not be folded into it.** That suite runs
// against any instance and asserts what every visitor sees; this one needs the surface switched
// on (`SYMONEURAL_STUDIO_ENABLED=1` and a token in the API's environment) and it takes the GPU for a
// real render. Pointing it at the deployed service would queue a job on the live card.
//
// Start your own API on a spare port, as CLAUDE.md says, or you are testing what is deployed
// rather than what you wrote:
//
//   cd backend && SYMONEURAL_STUDIO_ENABLED=1 SYMONEURAL_STUDIO_TOKEN=devtest \
//       python3 -m uvicorn api:app --port 8875
//   bash scripts/symoneural-ui.sh start
//
// The last two assertions are the ones worth having. A render succeeding server-side and still
// showing as a broken image for every visitor is a bug this repo has actually shipped -- curl
// proved the endpoint answered, which was never in doubt. So this decodes the image in the page
// and checks it came through `/api/studio/image` rather than from port 8188, which the browser
// cannot reach.
import { chromium } from './browser.mjs';

const BASE = process.argv[2] || 'http://127.0.0.1:8875';
const TOKEN = process.env.SYMONEURAL_STUDIO_TOKEN || 'devtest';
let pass = 0, fail = 0;
const ok = (n, d = '') => { pass++; console.log(`PASS  ${n}${d ? '  -- ' + d : ''}`); };
const no = (n, d = '') => { fail++; console.log(`FAIL  ${n}${d ? '  -- ' + d : ''}`); };

const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
page.on('requestfailed', r => errors.push(`${r.failure()?.errorText} ${r.url()}`));

await page.addInitScript(t => sessionStorage.setItem('sym.studio.token', t), TOKEN);
await page.goto(`${BASE}/studio`, { waitUntil: 'networkidle' });

// --- gate + strip ---
const gateHidden = await page.locator('#st-gate').isHidden();
gateHidden ? ok('the gate is closed when a token is present') : no('gate still showing');

await page.waitForFunction(() => document.querySelectorAll('#st-strip .st-cell').length > 0,
                           null, { timeout: 10000 });
const cells = await page.$$eval('#st-strip .st-cell',
  ns => ns.map(n => [n.querySelector('h4').textContent, n.querySelector('p').textContent]));
console.log('      strip:', JSON.stringify(cells));
cells.length === 6 ? ok('the status strip has six cells') : no('strip cells', String(cells.length));
const byTitle = Object.fromEntries(cells);
byTitle['Surface'] === 'on' ? ok('surface reads on') : no('surface', byTitle['Surface']);
// 28, and the literal stays a literal: reading the expected count from the same API that
// produces it would assert nothing. It was 26 until `23f2f64` added `extract_spec` and
// `generate_native_code` (group `cleanroom`) and updated `test_studio.py`'s EXPECTED_TOOLS but
// not this file -- so this suite reported two failures for work that was correct. When you add
// a tool, this number and `test_studio.py` both move, in the same commit.
byTitle['Tools'] === '28' ? ok('28 tools reported') : no('tools', byTitle['Tools']);
// 'Render UI', not 'ComfyUI': the cell reads the `render_ui` key of /api/studio/status, which
// is an unauthenticated public payload and so is held to the same naming standard as the URL.
// The *prose* on the page still names ComfyUI on purpose -- see page.html's bench comment;
// that is attribution, not branding, and GPL-3.0 is the reason it stays.
byTitle['Render UI'] === 'up' ? ok('the render UI reads up') : no('render ui', byTitle['Render UI']);
byTitle['GPU lease'] === 'not held' ? ok('lease reads not held at rest')
                                    : no('lease', byTitle['GPU lease']);

// --- tool table ---
const rows = await page.locator('#st-tools tr').count();
rows === 28 ? ok('the tool table has a row per tool') : no('tool rows', String(rows));
const writes = await page.locator('#st-tools .st-danger').count();
writes > 0 ? ok('writing tools are labelled', `${writes} flagged`) : no('no writes labelled');

// --- workflow select ---
const wf = await page.locator('#st-wf option').allTextContents();
wf.length >= 1 ? ok('workflow select populated', wf.join(', ')) : no('no workflows');

// --- the embedded editor ---
const src = await page.locator('#st-bench-frame').getAttribute('src');
src && src.startsWith('/studio/editor/?token=') ? ok('bench iframe points at the proxy', src.split('=')[0] + '=…')
                                                : no('iframe src', String(src));
try {
  const frame = await (await page.locator('#st-bench-frame').elementHandle()).contentFrame();
  await frame.waitForSelector('canvas, .comfyui-menu, #graph-canvas', { timeout: 40000 });
  const title = await frame.title();
  ok('ComfyUI editor booted inside the iframe', `title=${JSON.stringify(title)}`);
  const nodes = await frame.evaluate(async () => {
    const r = await fetch('/studio/editor/api/object_info');
    return Object.keys(await r.json()).length;
  });
  nodes > 800 ? ok('the editor reaches its own API through the proxy', `${nodes} node classes`)
              : no('object_info through proxy', String(nodes));
} catch (e) { no('ComfyUI editor in iframe', String(e).split('\n')[0]); }

// --- the editor gets the window -------------------------------------------------------------
//
// These four exist because every check on this surface was green while the thing the surface is
// *for* was invisible. The bench used to be the fourth block down the page under
// `height:min(78vh,760px)`, which at 1440x1000 put its top at y>1000: entirely below the fold.
// An `exists` or a `grep` cannot ask that question, and neither can "is the iframe present" --
// it was present, sized, and pointed at a working proxy the whole time.
//
// Note what is asserted: not the frame's height, because 760px of 1000 is 76% and would have
// passed. It is the frame's area *inside the first viewport*, which was zero.
const geom = await page.evaluate(() => {
  const f = document.getElementById('st-bench-frame');
  const r = f.getBoundingClientRect();
  const kids = [...document.querySelectorAll('#studio > *')].map(e => e.id);
  return { top: r.top, h: r.height, vh: innerHeight,
           visible: Math.max(0, Math.min(innerHeight, r.top + r.height) - Math.max(0, r.top)),
           benchBeforeStrip: kids.indexOf('st-bench') < kids.indexOf('st-strip') };
});
const share = geom.visible / geom.vh;
share >= 0.4 ? ok('the editor is visible without scrolling',
                  `${Math.round(geom.visible)}px of ${geom.vh} = ${Math.round(share * 100)}%`)
             : no('editor below the fold',
                  `top=${Math.round(geom.top)} visible=${Math.round(geom.visible)}px of ${geom.vh}`);
geom.benchBeforeStrip ? ok('the bench comes before the status strip')
                      : no('the bench was pushed back down the page');

// Expand. The button must reach a genuinely fixed, viewport-filling frame -- and the iframe must
// still be the same document afterwards, which is why `st-wide` is a class toggle and not a
// `body.appendChild(bench)`: re-parenting an iframe reloads it and discards the operator's graph.
const before = await page.locator('#st-bench-frame').getAttribute('src');
await page.click('#st-expand');
await page.waitForTimeout(400);
const wide = await page.evaluate(() => {
  const f = document.getElementById('st-bench-frame').getBoundingClientRect();
  return { cover: f.height / innerHeight, w: f.width, vw: innerWidth,
           pos: getComputedStyle(document.getElementById('st-bench')).position,
           bodyOv: getComputedStyle(document.body).overflow,
           hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
           src: document.getElementById('st-bench-frame').getAttribute('src') };
});
(wide.pos === 'fixed' && wide.cover >= 0.85 && wide.bodyOv === 'hidden' && !wide.hscroll)
  ? ok('Expand fills the viewport', `${Math.round(wide.cover * 100)}% tall, ${wide.w}/${wide.vw} wide`)
  : no('Expand did not fill the viewport', JSON.stringify(wide));
wide.src === before ? ok('expanding did not remount the iframe')
                    : no('the iframe was remounted and the graph is gone');

// Escape must get out. A fixed panel covers the site header, so without this there is nothing
// left to click and the operator is trapped on a page with no way back.
await page.keyboard.press('Escape');
await page.waitForTimeout(400);
const back = await page.evaluate(() =>
  getComputedStyle(document.getElementById('st-bench')).position);
back === 'static' ? ok('Escape collapses the bench') : no('Escape left the bench fixed', back);

// --- no ellipsis anywhere on the rendered page ---
const clipped = await page.$$eval('#studio *', ns =>
  ns.filter(n => getComputedStyle(n).textOverflow === 'ellipsis').length);
clipped === 0 ? ok('nothing on the page truncates text') : no('elements with ellipsis', String(clipped));

// --- horizontal overflow at phone width ---
await page.setViewportSize({ width: 390, height: 900 });
const hscroll = await page.evaluate(() =>
  document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
hscroll ? no('the page scrolls sideways at 390px') : ok('no sideways scroll at 390px');
await page.setViewportSize({ width: 1440, height: 1000 });

// --- a real render, through the page's own form ---
await page.fill('#st-prompt', 'a raven perched on a foundry crucible, sparks, night');
const t0 = Date.now();
await page.click('#st-go');
try {
  /* Wait for the image to DECODE, not for the `<img>` to exist.
   *
   * This used to be `waitForSelector('#st-shots img')`, which returns the moment page.js sets
   * `src` -- before a byte of the PNG has arrived. `naturalWidth` is 0 until it decodes, so the
   * assertion below read 0x0 and called a perfectly good render a failure: a ~1 MB PNG over
   * loopback is fast but not free. Measured on the run that caught it, the endpoint answered
   * `200 image/png content-length: 996780` to curl at the same moment the browser reported 0x0.
   *
   * A racy version of this assertion is worse than not having it. It exists because a render
   * once succeeded server-side and still showed as a broken image to every visitor, so it must
   * go red for exactly that and for nothing else. `complete` alone would not do -- it is true
   * for a failed load too, which is the case this is here to catch. */
  await page.waitForFunction(() => {
    const i = document.querySelector('#st-shots img');
    return !!i && i.complete && i.naturalWidth > 0;
  }, { timeout: 300000 });
  const shot = await page.$eval('#st-shots img',
    i => ({ w: i.naturalWidth, h: i.naturalHeight, src: i.getAttribute('src'), alt: i.alt }));
  shot.w > 0 && shot.h > 0
    ? ok('the render decoded in the browser', `${shot.w}x${shot.h} ${shot.alt} in ${((Date.now()-t0)/1000).toFixed(1)}s`)
    : no('render did not decode', JSON.stringify(shot));
  shot.src.startsWith('/api/studio/image')
    ? ok('the image is proxied by the API, not fetched from :8188')
    : no('image src', shot.src);
} catch (e) {
  no('render', (await page.textContent('#st-render-note').catch(() => '')) || String(e).split('\n')[0]);
}
console.log('      note:', await page.textContent('#st-render-note').catch(() => ''));

// ComfyUI asks for a handful of optional files on boot -- a user stylesheet, a saved
// template list, two settings keys -- and 404s them itself when they have never been created.
// Chrome reports a 404 on a stylesheet or a fetch() as ERR_ABORTED, so they show up here
// looking like proxy failures. They are not: `curl` against 127.0.0.1:8188 returns 404 for
// the same paths. Labelled rather than filtered, because a filter would also hide a real
// abort on one of those paths.
const OPTIONAL = /user\.css|comfy\.templates\.json|api\/settings\//;
if (errors.length) console.log('\nfailed requests / js errors:\n  '
  + errors.map(e => OPTIONAL.test(e) ? e + '   [optional, 404 upstream too]' : e).join('\n  '));
console.log(`\n${pass}/${pass + fail} passed`);
await browser.close();
process.exit(fail ? 1 : 0);
