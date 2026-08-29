// Functional smoke for the application surfaces that do not already own a dedicated
// end-to-end suite.
//
//   node tests/applications_smoke.mjs
//
// This is self-contained: it serves site/ from a throwaway loopback origin and intercepts
// the application APIs with deterministic responses.  Dedicated suites still own real
// media decode, Project persistence, Accounts, Streamer, Studio, Sigils and Chat.  The
// sequential runner in run_ui_verification.mjs combines those suites with this one.
//
// A mocked success here is not a backend verdict.  It proves the browser-side behaviour:
// controls dispatch once, response state reaches the DOM, failures stay legible, and the
// hand-maintained pages execute their modules after the shell refactor.

import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { dirname, extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from './browser.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const SITE = join(ROOT, 'site');
const PORT = Number(process.argv[2] || 8993);
const BASE = `http://127.0.0.1:${PORT}`;

const CLEAN = new Map([
  ['/', 'overview.html'],
  ['/overview', 'overview.html'],
  ['/livestack', 'livestack.html'],
  ['/controlboard', 'controlboard.html'],
  ['/receipts', 'receipts.html'],
  ['/studio', 'studio.html'],
  ['/exp', 'exp.html'],
  ['/livestack/coder', 'coder.html'],
  ['/livestack/live', 'live.html'],
]);
const TYPES = new Map([
  ['.html', 'text/html; charset=utf-8'], ['.css', 'text/css; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'], ['.mjs', 'text/javascript; charset=utf-8'],
  ['.png', 'image/png'], ['.jpg', 'image/jpeg'], ['.jpeg', 'image/jpeg'],
  ['.svg', 'image/svg+xml'], ['.ico', 'image/x-icon'],
]);

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, BASE);
    let rel = CLEAN.get(url.pathname) || url.pathname.replace(/^\/+/, '');
    if (!rel || rel.endsWith('/')) rel += 'index.html';
    const file = normalize(join(SITE, rel));
    if (!file.startsWith(SITE + '/')) throw new Error('path outside site');
    const body = await readFile(file);
    res.writeHead(200, { 'content-type': TYPES.get(extname(file)) || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    res.end('not found');
  }
});
await new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(PORT, '127.0.0.1', resolve);
});

let pass = 0, fail = 0;
const calls = new Map();
const record = (name, ok, detail = '') => {
  ok ? pass++ : fail++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  -- ' + detail : ''}`);
};
const called = path => calls.get(path) || 0;

const browser = await chromium.launch({ channel: 'chrome', args: ['--no-sandbox'] });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(() => {
  sessionStorage.setItem('sym.asic.token', 'fixture-token');
  sessionStorage.setItem('sym.miner.token', 'fixture-token');
});
const page = await context.newPage();
let errors = [];
page.on('pageerror', e => errors.push(String(e)));

const json = (route, body, status = 200) => route.fulfill({
  status, contentType: 'application/json', body: JSON.stringify(body),
});

await page.route('**/api/**', async route => {
  const req = route.request();
  const url = new URL(req.url());
  const path = url.pathname;
  calls.set(path, called(path) + 1);
  let body = {};
  try { body = req.postDataJSON() || {}; } catch {}

  if (path === '/api/news/ticker') return json(route, { enabled: false, items: [] });
  if (path === '/api/status') return json(route, {
    units: [{ id: 'miner', state: 'ready', detail: 'fixture rack row', sub: [
      { id: 'asicminer', state: 'ready', detail: 'firmware inventory ready' },
      { id: 'gpuminer', state: 'ready', detail: 'benchmark surface ready' },
      { id: 'gateway', state: 'ready', detail: 'license checks are available' },
    ] }],
  });
  if (path === '/api/remix') return json(route, {
    tracks: [
      { title: 'First Track', artist: 'Fixture Artist', why: 'opens the sequence' },
      { title: 'Second Track', artist: 'Fixture Artist', why: 'closes the sequence' },
    ], seconds: 0.02, note: 'browser fixture',
  });
  if (path === '/api/asicminer/firmware') return json(route, { packages: [{
    id: 'fixture.tar.gz', vendor: 'antminer', name: 'Fixture Antminer',
    kind: 'browser', bytes: 1048576,
  }] });
  if (path === '/api/asicminer/emulator') {
    if (body.action === 'status') return json(route, { running: true, package: 'Fixture Antminer' });
    return json(route, { ok: true, package: 'Fixture Antminer', pid: 4242,
                         note: 'fixture boot complete', web: 'http://127.0.0.1:8080' });
  }
  if (path === '/api/asicminer/scan') return json(route, {
    swept: 1, responded: 1, port: 80,
    rigs: [{ identified: true, host: '192.168.1.2', vendor: 'fixture', model: 'one' }],
  });
  if (path === '/api/gpuminer/status') return json(route, {
    running: true, hashrate_mh_s: 42, hashrate_source: 'fixture telemetry',
    hashrate_age_s: 1, benchmark: true, pool: false, holds_gpu_lock: true,
    lock_holder: 'miner', uptime_s: 5,
  });
  if (path === '/api/gpuminer/control') return json(route, body.action === 'stop'
    ? { stopped: 4242, note: 'fixture stopped' }
    : { ok: true, pid: 4242, note: 'fixture started' });
  if (path === '/api/exp/state') return json(route, {
    enabled: false, writable: false, source: null, default_preset: null,
    entries: [], states: {}, fibers: [], services: [], events: 0,
    dropped_writes: 0, trace_path: null, presets: [], seq: 0,
  });
  if (path === '/api/exp/services') return json(route, []);
  if (path === '/api/exp/catalogue') return json(route, { plugins: [] });
  if (path === '/api/exp/events') return json(route, {
    events: [], seq: 0, buffered: 0, dropped: 0, persistent: false,
  });
  if (path.startsWith('/api/train/')) {
    return json(route, { detail: 'training surface disabled in browser fixture' }, 503);
  }
  return json(route, {});
});

await page.route('**/local/coder/**', async route => {
  const req = route.request();
  const url = new URL(req.url());
  const path = url.pathname;
  calls.set(path, called(path) + 1);
  if (path === '/local/coder/status') return json(route, {
    ok: true, workspace: '/fixture/Symoneural',
    gates: { enabled: true, token_set: true, allow_remote: false, peer_loopback: true },
    mount: { peer: '127.0.0.1', read_only: true, prefix: '/local/coder' },
  });
  if (path === '/local/coder/ls') return json(route, {
    ok: true, path: '.', truncated: false,
    entries: [{ name: 'README.md', type: 'file', bytes: 32, denied: false }],
  });
  if (path === '/local/coder/file') return json(route, {
    ok: true, path: 'README.md', bytes: 32, text: 'fixture workspace file\n',
  });
  if (path === '/local/coder/history') return json(route, {
    ok: true, versions: [{ version: 'fixture-v1', bytes: 32, when: '2026-08-26T00:00:00Z' }],
  });
  if (path === '/local/coder/journal') return json(route, {
    ok: true, records: [{ action: 'read', path: 'README.md', ts: '2026-08-26T00:00:00Z' }],
  });
  return json(route, { ok: false, error: 'fixture route absent' }, 404);
});

async function visit(path) {
  errors = [];
  await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(350);
}
async function clean(name) {
  record(`${name}: no uncaught JavaScript error`, errors.length === 0, errors.join('; '));
}

try {
  // Remix: selector state, one submit, success state, and control reset.
  await visit('/remix.html');
  await page.fill('#brief', 'Build a two-track fixture sequence');
  await page.$eval('#count', el => { el.value = '7'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  record('Remix: range state reaches its value label', await page.textContent('#countv') === '7');
  const remixBefore = called('/api/remix');
  await page.click('#send');
  await page.waitForSelector('#out .tracks li');
  record('Remix: submit executes exactly once', called('/api/remix') === remixBefore + 1);
  record('Remix: success state renders returned tracks', await page.locator('#out .tracks li').count() === 2);
  record('Remix: submit control clears loading state', !(await page.isDisabled('#send')));
  await clean('Remix');

  // Miner: firmware selection, emulator result, telemetry, guarded start, and stop.
  await visit('/miner.html');
  await page.click('[data-src="emu"]');
  await page.click('[data-vendor="antminer"]');
  await page.waitForSelector('#mn-models .mn-model');
  await page.click('#mn-models .mn-model');
  await page.waitForFunction(() => /booted Fixture Antminer/.test(document.querySelector('#mnnote').textContent));
  record('Miner: emulator flow reaches a definite success state', /pid 4242/.test(await page.textContent('#mnnote')));
  await page.fill('#mg-token', 'fixture-token');
  await page.click('#mg-read');
  await page.waitForFunction(() => /42 MH\/s/.test(document.querySelector('#mg-hr').textContent));
  record('Miner: telemetry action renders a measured value', /42 MH\/s/.test(await page.textContent('#mg-hr')));
  await page.click('#mg-start');
  record('Miner: first start click arms instead of starting', /Confirm/.test(await page.textContent('#mg-start')));
  await page.click('#mg-start');
  await page.waitForFunction(() => /started, pid 4242/.test(document.querySelector('#mgnote').textContent));
  record('Miner: confirmed start executes once', called('/api/gpuminer/control') === 1);
  await page.click('#mg-stop');
  await page.waitForFunction(() => /stopped pid 4242/.test(document.querySelector('#mgnote').textContent));
  record('Miner: stop clears to a definite state', /stopped pid/.test(await page.textContent('#mgnote')));
  await clean('Miner');

  // Gateway: the folded rack row is found inside sub[], not only at top level.
  await visit('/gateway.html');
  await page.waitForFunction(() => document.querySelector('#gwstate').textContent.trim() === 'ready');
  record('Gateway: nested rack status renders', await page.textContent('#gwstate') === 'ready');
  record('Gateway: API detail is preserved', /license checks/.test(await page.textContent('#gwdetail')));
  await clean('Gateway');

  // Exp: read-only state paints, and local validation stops an invalid call before fetch.
  await visit('/exp.html');
  await page.waitForSelector('#ex-strip .ex-cell');
  record('Exp: state response paints six instrument cells', await page.locator('#ex-strip .ex-cell').count() === 6);
  // The call form lives inside `<details id="ex-call-wrap">` and ships closed, so the
  // textarea resolves as a locator and is never fillable -- Playwright waits the full 30s
  // on "element is not visible" rather than failing fast. Open the disclosure the way a
  // visitor does, which is also what the Coder journal assertion below already does.
  await page.click('#ex-call-wrap > summary');
  await page.fill('#ex-call-args', '{}');
  const expBefore = called('/api/exp/call');
  await page.click('#ex-call-go');
  await page.waitForFunction(() => /must be a JSON array/.test(document.querySelector('#ex-said').textContent));
  record('Exp: invalid call is explained without an API write', called('/api/exp/call') === expBefore);
  await clean('Exp');

  // Reinforce: the server-off state remains visible and disables every mutating control.
  await visit('/reinforce.html');
  await page.waitForFunction(() => !document.querySelector('#rf-gate').hidden);
  record('Reinforce: disabled runtime shows its gate', await page.isVisible('#rf-gate'));
  record('Reinforce: disabled runtime cannot start a run', await page.isDisabled('#rf-start-btn'));
  record('Reinforce: selectors are disabled with the runtime', await page.isDisabled('#rf-pick-model'));
  await clean('Reinforce');

  // Coder: load, reload exactly once, file reader, history and lazy journal.
  await visit('/livestack/coder');
  await page.waitForFunction(() => document.querySelector('#cd-headstate').textContent.trim() === 'reading');
  record('Coder: local status unlocks the read-only workspace', await page.locator('#cd-list .cd-row').count() === 1);
  const lsBefore = called('/local/coder/ls');
  await page.click('#cd-reload');
  await page.waitForTimeout(150);
  record('Coder: Reload performs exactly one directory read', called('/local/coder/ls') === lsBefore + 1);
  await page.click('#cd-list .cd-name');
  await page.waitForFunction(() => /fixture workspace file/.test(document.querySelector('#cd-filetext').textContent));
  record('Coder: file and history render together', /fixture-v1/.test(await page.textContent('#cd-hist')));
  await page.click('#cd-jrnwrap > summary');
  await page.waitForFunction(() => /README\.md/.test(document.querySelector('#cd-jrn').textContent));
  record('Coder: journal loads on first expansion', called('/local/coder/journal') === 1);
  await clean('Coder');

  // The split front-page routes own folds and route-aware state.
  await visit('/livestack');
  await page.click('#rk-fold');
  record('Live stack: fold changes aria-pressed', await page.getAttribute('#rk-fold', 'aria-pressed') === 'true');
  record('Live stack: route marks itself current', await page.getAttribute('.ns-tab.on', 'aria-current') === 'page');
  await clean('Live stack');

  await visit('/controlboard');
  await page.click('#cn-fold');
  record('Control board: fold changes aria-pressed', await page.getAttribute('#cn-fold', 'aria-pressed') === 'true');
  record('Control board: route marks itself current', await page.getAttribute('.ns-tab.on', 'aria-current') === 'page');
  await clean('Control board');

  await visit('/receipts');
  record('Receipts: route marks itself current', await page.getAttribute('.ns-tab.on', 'aria-current') === 'page');
  record('Receipts: evidence cards retain destinations', (await page.getAttribute('a.card', 'href') || '').startsWith('/documentation'));
  await clean('Receipts');

  // Overview and Documentation own shared ui.js behaviour: lightbox and tab/hash state.
  await visit('/overview');
  await page.click('a.gart');
  // `.lightbox.on`, not `.open`. site/ui.js:124 sets `on` and symoneural.css:1455 is
  // `.lightbox.on{display:flex}`. The wrong class did not just fail the open assertion --
  // `isVisible()` answers false for a selector that matches nothing, so the Escape check
  // below would have passed without a lightbox ever existing. A check that can pass while
  // the feature is absent is the kind this repo archives tasks on.
  await page.waitForSelector('.lightbox.on');
  record('Overview: render opens in the shared lightbox', await page.isVisible('.lightbox.on'));
  await page.keyboard.press('Escape');
  record('Overview: Escape closes the lightbox', !(await page.isVisible('.lightbox.on')));
  await clean('Overview');

  await visit('/documentation.html');
  const tabs = page.locator('.tab[role="tab"]');
  if (await tabs.count() > 1) {
    const target = tabs.nth(1);
    const id = await target.getAttribute('id');
    await target.click();
    record('Documentation: tab click updates selected state', await target.getAttribute('aria-selected') === 'true');
    record('Documentation: tab state is addressable in the hash', page.url().endsWith('#' + id.replace(/^tab-/, '')));
  } else {
    record('Documentation: a second tab exists to exercise', false, `${await tabs.count()} tab(s)`);
  }
  await clean('Documentation');

  // These surfaces are documents, not control planes; direct load and their real outbound
  // action are the applicable behaviours.
  for (const [path, name] of [['/credits.html', 'Credits'], ['/build.html', 'Build']]) {
    await visit(path);
    record(`${name}: direct route loads its own document`, (await page.title()).includes('SyMoNeuRaL'));
    record(`${name}: page retains at least one actionable destination`, await page.locator('a[href]').count() > 0);
    await clean(name);
  }
} finally {
  await context.close();
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}

console.log(`\n${pass}/${pass + fail} passed`);
process.exit(fail ? 1 : 0);
