// Drive site/tuner.html against the scripted provider in real Chrome and assert on
// what the page SHOWS. The bug being tested is a blank screen, so every assertion here
// is about visible text -- reading state out of JS would pass while the visitor still
// stared at a black rectangle.
//
// Self-contained: it starts its own scripted provider (tests/tuner_fake_provider.py)
// and stops it again, so `node tests/tuner_failpaths.mjs` is the whole invocation and
// it does not need the real API, a provider account, or a working stream.
import { chromium } from '../contrib/llama.cpp/tools/ui/node_modules/playwright/index.mjs';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.argv[2] || '8944';
const BASE = `http://127.0.0.1:${PORT}`;

const server = spawn('python3', [path.join(HERE, 'tuner_fake_provider.py'), PORT],
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

async function loadChannels() {
  await page.goto(`${BASE}/tuner.html`, { waitUntil: 'domcontentloaded' });
  await page.fill('#tn-url', 'http://example.invalid/playlist.m3u');
  await page.click('#tn-go');
  await page.waitForSelector('li.playable', { timeout: 10000 });
}

async function setCase(name) {
  await page.evaluate(n => fetch('/_case?name=' + n).then(r => r.json()), name);
}

async function panel() {
  const hidden = await page.$eval('#tnfail', el => el.hidden);
  if (hidden) return null;
  return {
    head: (await page.$eval('#tnfailh', el => el.textContent)).trim(),
    body: (await page.$eval('#tnfailp', el => el.innerText)).replace(/\s+/g, ' ').trim(),
    now: (await page.$eval('#tnnow', el => el.textContent)).trim(),
    visible: await page.$eval('#tnfail', el => el.getBoundingClientRect().height > 20),
  };
}

// ---- case 1: the provider refuses, with its own words -------------------------------
await loadChannels();
await setCase('refused');
await page.click('li.playable');
await page.waitForSelector('#tnfail:not([hidden])', { timeout: 10000 });
let p = await panel();
ok('provider refusal renders a visible panel', p && p.visible, p);
ok('the provider\'s own sentence is on the page',
   p && p.body.includes('Stream is currently offline'), p && p.body);
ok('the page says the box is not the one blocking it',
   p && /nothing on this machine filters/i.test(p.body), p && p.body);
ok('status line stops claiming it is opening',
   p && /did not open/.test(p.now), p && p.now);

// ---- case 2: 200 + state "starting" that never becomes live -------------------------
// This is the response that produced the blank screen: res.ok is true and the manifest
// does not exist. The page must NOT hand it to hls.js and go quiet.
await loadChannels();
await setCase('stuck');
await page.click('li.playable');
await page.waitForTimeout(2500);
let now = (await page.$eval('#tnnow', el => el.textContent)).trim();
ok('a 200 "starting" is reported as still opening, not as playing',
   /opening/.test(now) && !/live/.test(now), now);
ok('no hls.js jargon is shown to the visitor',
   !/manifestLoad|networkError|hls\.js/i.test(now), now);
const src = await page.$eval('#tnvideo', el => el.getAttribute('src') || '');
ok('the not-yet-existent manifest was never given to the <video>', src === '', src);

// ---- case 3: it starts, then the server reports why it failed -----------------------
await loadChannels();
await setCase('html');
await page.click('li.playable');
await page.waitForSelector('#tnfail:not([hidden])', { timeout: 15000 });
p = await panel();
ok('a failed session shows the server\'s reason', p && p.visible, p);
ok('the provider\'s maintenance message reaches the page',
   p && p.body.includes('temporarily unavailable while we perform maintenance'), p && p.body);

// ---- case 4: HEVC -- everything works and the picture is still black -----------------
await loadChannels();
await setCase('hevc');
await page.click('li.playable');
await page.waitForSelector('#tnfail:not([hidden])', { timeout: 10000 });
p = await panel();
ok('an undecodable codec is named outright', p && /H\.265/.test(p.head), p && p.head);
ok('and it says nothing here has failed', p && /nothing here has failed/.test(p.body), p && p.body);

// ---- case 4b: "live", and the playlist is still empty ---------------------------------
// The last shape of the blank screen. ffmpeg writes the .m3u8 header before it has cut a
// single segment, so `state` flips to "live" while there is nothing to fetch; hls.js gets a
// manifest with zero fragments, reports nothing useful, and the visitor sees black. The page
// now waits for `segments > 0` instead of trusting `state`, so this must stay "opening" and
// the <video> must stay empty. Case 4 above found this fixture stale for exactly this reason.
await loadChannels();
await setCase('emptylive');
await page.click('li.playable');
await page.waitForTimeout(2500);
now = (await page.$eval('#tnnow', el => el.textContent)).trim();
ok('a live session with an empty playlist still reads as opening',
   /opening/.test(now) && !/playing/.test(now), now);
ok('an empty manifest is never handed to the <video>',
   (await page.$eval('#tnvideo', el => el.getAttribute('src') || '')) === '',
   await page.$eval('#tnvideo', el => el.getAttribute('src') || ''));

// ---- case 5: the parse stopped early and the page must say so ------------------------
// The M3U parser caps at MAX_CHANNELS and returns `truncated`. The page read it nowhere,
// so a playlist over the cap lost its tail -- usually the Movies block, since it is the
// largest and last in most provider files -- and the page still said "Loaded".
await setCase('truncated');
await loadChannels();
let notes = (await page.$eval('#tnnote', el => el.innerText)).replace(/\s+/g, ' ').trim();
ok('a truncated playlist says it was cut off', /cut off|Only the first/i.test(notes), notes);
ok('and it names the limit that bit', /20000/.test(notes), notes);
await setCase('refused');
await loadChannels();
notes = (await page.$eval('#tnnote', el => el.innerText)).replace(/\s+/g, ' ').trim();
ok('an untruncated playlist does not cry truncation', !/cut off|Only the first/i.test(notes),
   notes);

// ---- case 6: the panel had movies and this box declined to load them ------------------
// The reported bug: Live TV and Series populate, Movies never do. The backend now says why
// in `notes`; this asserts the sentence actually reaches the visitor's screen.
await page.goto(`${BASE}/tuner.html`, { waitUntil: 'domcontentloaded' });
await page.click('.tn-tab[data-mode="xtream"]');
await page.fill('#tn-host', 'http://panel.invalid:80');
await page.fill('#tn-user', 'u');
await page.fill('#tn-pass', 'p');
await page.click('#tn-go');
await page.waitForSelector('li.playable', { timeout: 10000 });
notes = (await page.$eval('#tnnote', el => el.innerText)).replace(/\s+/g, ' ').trim();
ok('a skipped movie catalogue is explained on the page', /skipped/.test(notes), notes);
ok('the explanation blames this box, not the provider',
   /this box will load/.test(notes) && !/unavailable on this panel/.test(notes), notes);
ok('an Xtream load is not described as a playlist', !/from your playlist/.test(notes), notes);

// ---- house rules --------------------------------------------------------------------
const ell = await page.$$eval('#tnfail, #tnfail *',
  els => els.filter(e => getComputedStyle(e).textOverflow === 'ellipsis').length);
ok('no text-overflow:ellipsis anywhere in the failure panel', ell === 0, ell);
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
ok('page does not scroll horizontally at 1440px', overflow <= 0, overflow);
await page.setViewportSize({ width: 390, height: 800 });
await page.waitForTimeout(200);
const ov390 = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
ok('page does not scroll horizontally at 390px', ov390 <= 0, ov390);
ok('no uncaught page errors', errors.length === 0, errors);

await browser.close();
server.kill();
console.log(`\n${pass}/${pass + fail} passed`);
process.exit(fail ? 1 : 0);
