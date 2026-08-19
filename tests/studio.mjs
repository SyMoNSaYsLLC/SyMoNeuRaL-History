// Browser check for /studio: the Studio surface, end to end, in a real browser.
//
//   node tests/studio.mjs http://127.0.0.1:8875
//   SYM_STUDIO_TOKEN=<secret> node tests/studio.mjs http://127.0.0.1:8875
//
// **This is not part of `tests/frontend.mjs` and must not be folded into it.** That suite runs
// against any instance and asserts what every visitor sees; this one needs the surface switched
// on (`SYM_STUDIO_ENABLED=1` and a token in the API's environment) and it takes the GPU for a
// real render. Pointing it at the deployed service would queue a job on the live card.
//
// Start your own API on a spare port, as CLAUDE.md says, or you are testing what is deployed
// rather than what you wrote:
//
//   cd backend && SYM_STUDIO_ENABLED=1 SYM_STUDIO_TOKEN=devtest \
//       python3 -m uvicorn api:app --port 8875
//   bash scripts/comfyui.sh start
//
// The last two assertions are the ones worth having. A render succeeding server-side and still
// showing as a broken image for every visitor is a bug this repo has actually shipped -- curl
// proved the endpoint answered, which was never in doubt. So this decodes the image in the page
// and checks it came through `/api/studio/image` rather than from port 8188, which the browser
// cannot reach.
// Playwright lives in the llama.cpp web UI's node_modules, installed when that UI was built.
// Resolved relative to this file so the repo can be cloned anywhere -- same as frontend.mjs.
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const REPO = dirname(dirname(fileURLToPath(import.meta.url)));
const { chromium } = createRequire(import.meta.url)(
  join(REPO, 'contrib/llama.cpp/tools/ui/node_modules/playwright'));

const BASE = process.argv[2] || 'http://127.0.0.1:8875';
const TOKEN = process.env.SYM_STUDIO_TOKEN || 'devtest';
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
byTitle['Tools'] === '26' ? ok('26 tools reported') : no('tools', byTitle['Tools']);
byTitle['ComfyUI'] === 'up' ? ok('ComfyUI reads up') : no('comfyui', byTitle['ComfyUI']);
byTitle['GPU lease'] === 'not held' ? ok('lease reads not held at rest')
                                    : no('lease', byTitle['GPU lease']);

// --- tool table ---
const rows = await page.locator('#st-tools tr').count();
rows === 26 ? ok('the tool table has a row per tool') : no('tool rows', String(rows));
const writes = await page.locator('#st-tools .st-danger').count();
writes > 0 ? ok('writing tools are labelled', `${writes} flagged`) : no('no writes labelled');

// --- workflow select ---
const wf = await page.locator('#st-wf option').allTextContents();
wf.length >= 1 ? ok('workflow select populated', wf.join(', ')) : no('no workflows');

// --- the embedded editor ---
const src = await page.locator('#st-bench-frame').getAttribute('src');
src && src.startsWith('/studio/comfy/?token=') ? ok('bench iframe points at the proxy', src.split('=')[0] + '=…')
                                                : no('iframe src', String(src));
try {
  const frame = await (await page.locator('#st-bench-frame').elementHandle()).contentFrame();
  await frame.waitForSelector('canvas, .comfyui-menu, #graph-canvas', { timeout: 40000 });
  const title = await frame.title();
  ok('ComfyUI editor booted inside the iframe', `title=${JSON.stringify(title)}`);
  const nodes = await frame.evaluate(async () => {
    const r = await fetch('/studio/comfy/api/object_info');
    return Object.keys(await r.json()).length;
  });
  nodes > 800 ? ok('the editor reaches its own API through the proxy', `${nodes} node classes`)
              : no('object_info through proxy', String(nodes));
} catch (e) { no('ComfyUI editor in iframe', String(e).split('\n')[0]); }

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
  await page.waitForSelector('#st-shots img', { timeout: 300000 });
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
