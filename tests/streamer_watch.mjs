// Drive site/streamer-watch.html against the scripted provider in real Chrome.
//
// WHY THIS FILE EXISTS SEPARATELY FROM streamer_failpaths.mjs: the watch page carries its OWN
// copy of play(), its own statistics panel and its own `#ps-eng`, deliberately duplicated
// from STREAMER_JS and marked as such in the generator. Duplicated code needs duplicated
// assertions, or the identical bug can be reintroduced on the copy with every existing test
// still green -- which is exactly how the `canPlayType` dead-code bug survived on streamer.html.
//
// Self-contained: it starts tests/streamer_fake_provider.py and stops it again, so
// `node tests/streamer_watch.mjs` is the whole invocation. No account, no real stream, no API.
import { chromium } from './browser.mjs';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.argv[2] || '8946';
const BASE = `http://127.0.0.1:${PORT}`;
const WK = 'symoneural.streamer.watch';

const server = spawn('python3', [path.join(HERE, 'streamer_fake_provider.py'), PORT],
                     { stdio: ['ignore', 'pipe', 'inherit'] });
process.on('exit', () => server.kill());
await new Promise((res, rej) => {
  const t = setTimeout(() => rej(new Error('scripted provider did not start')), 8000);
  server.stdout.on('data', d => { if (String(d).includes('serving')) { clearTimeout(t); res(); } });
});

let pass = 0, fail = 0;
const ok = (name, cond, got) => {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}\n      got: ${JSON.stringify(got)}`); }
};

const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('pageerror', e => errors.push(String(e)));

// Seed the handoff exactly as streamer.html writes it when the visitor clicks "watch full screen",
// WITHOUT a session id -- the cold half of the handoff, where the watch page must tune for
// itself. Setting localStorage requires being on the origin first, hence the initial goto.
await page.goto(`${BASE}/streamer.html`, { waitUntil: 'domcontentloaded' });
await page.evaluate(() => fetch('/_case?name=aac').then(r => r.json()));
await page.evaluate(k => {
  localStorage.setItem('symoneural.streamer.cfg',
    JSON.stringify({ kind: 'm3u', url: 'http://example.invalid/playlist.m3u' }));
  localStorage.setItem(k, JSON.stringify({ name: 'Fixture One', url: 'http://example.invalid/one',
                                           stream_id: '1', group: 'x', sid: '' }));
}, WK);

await page.goto(`${BASE}/streamer-watch.html`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(3000);

// ---- the handoff record must carry a LIVE session id ---------------------------------
// THE BUG THIS EXISTS FOR. `tune()` calls `remember(c)` BEFORE the fetch resolves -- on
// purpose, so a reload during the seconds a tune takes still knows which channel to open --
// and at that moment `sid` is null, so the record stores `sid: ""`. Nothing rewrote it on the
// success path; only `adopt()` did. So after any channel change made on this page, a reload
// saw an empty id and cold-tuned with no `release`: one slot of a two-slot box left holding a
// stream nobody was watching until the reaper got to it, and the fresh tune refusable
// meanwhile. A second `remember(c)` after `sid = j.id` fixes it, and removing that one call
// puts this assertion straight back to red.
const rec = JSON.parse(await page.evaluate(k => localStorage.getItem(k) || '{}', WK));
ok('the handoff record carries the live session id after a tune',
   !!rec.sid, rec);
ok('and it still carries the channel it was opened on',
   rec.url === 'http://example.invalid/one', rec.url);

// ---- which player got the stream ------------------------------------------------------
// The watch page duplicates streamer.html's branch, so it can regress independently. On Chrome
// `video.canPlayType('application/vnd.apple.mpegurl')` returns the truthy string 'maybe', so
// asking the <video> first wins every time and the hls.js block below becomes dead code --
// Chrome's native HLS then declines mpeg-ts silently, which is the black rectangle. `#ps-eng`
// is the discriminator: "the browser's own HLS" when broken, "hls.js <version>" when not.
const eng = await page.$eval('#ps-eng', el => el.textContent.trim()).catch(() => '');
ok('the stream is handed to hls.js, not to the browser’s own HLS',
   /hls\.js/.test(eng), eng || '(#ps-eng absent -- play() never started the panel)');

// The status line is `#tnnow`, the same id the streamer page uses, because the two pages share
// the code that writes it. The assertion is that it reaches a DEFINITE state, not specifically
// "live": this fixture serves a manifest and no segment data, so "stopped" is a true report of
// what happened and asserting it away would be asserting that the page lies. What must never
// happen is sitting on "opening…" forever, which is the black rectangle with a caption.
const now = await page.$eval('#tnnow', el => el.textContent.trim()).catch(() => '');
ok('the page reaches a definite state rather than sitting on "opening"',
   now.length > 0 && !/opening/.test(now), now);

// ---- a cold visit, with nothing handed over -------------------------------------------
// Somebody typing the URL, or arriving with a cleared browser. It must explain itself rather
// than sit on a black rectangle -- and, more to the point, must not throw on the way.
const cold = await browser.newPage();
const coldErrors = [];
cold.on('pageerror', e => coldErrors.push(String(e)));
await cold.goto(`${BASE}/streamer-watch.html`, { waitUntil: 'domcontentloaded' });
await cold.waitForTimeout(1200);
const coldText = (await cold.evaluate(() => document.body.innerText)).replace(/\s+/g, ' ');
ok('a cold visit says nothing is playing instead of showing a black rectangle',
   /nothing playing/i.test(coldText), coldText.slice(0, 120));
ok('a cold visit throws no script error', coldErrors.length === 0, coldErrors.join(' | '));
await cold.close();

// ---- no ellipsis, same rule as everywhere else -----------------------------------------
// §4: folding is allowed, trimming is not. A channel name cut to "SportsCen…" is data loss.
const clipped = await page.evaluate(() => {
  const bad = [];
  document.querySelectorAll('*').forEach(el => {
    if (getComputedStyle(el).textOverflow === 'ellipsis') bad.push(el.id || el.className || el.tagName);
  });
  return bad.slice(0, 5);
});
ok('no text-overflow:ellipsis anywhere on the watch page', clipped.length === 0, clipped);

ok('no uncaught page errors', errors.length === 0, errors.join(' | '));

await browser.close();
server.kill();
console.log(`\n${pass}/${pass + fail} passed`);
process.exit(fail ? 1 : 0);
