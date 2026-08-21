// Drive site/live.html in a real browser.
//
//   python3 tests/live-harness.py &      # 127.0.0.1:8897, throwaway store, no OBS, no GPU
//   node tests/live.mjs [baseURL]
//   kill %1
//
// Separate from tests/frontend.mjs on purpose, and separate in the direction that matters:
// frontend.mjs and studio.mjs both TAKE THE CARD and must never run beside each other. This
// one takes nothing -- no GPU, no OBS, no provider account, no token -- and it has to stay
// that way, or it becomes a third thing in that scheduling constraint and stops being run.
//
// THE ASSERTION THIS SUITE EXISTS FOR is `video decodes`. A <video> element with an HLS URL
// behind it satisfies `exists`, `grep` and every DOM assertion anybody would think to write,
// while playing nothing at all -- that is #94's shape, eighteen green checks and a surface
// that was dead on arrival, archived by the timer two minutes later. `readyState >= 3` and a
// `currentTime` that advances are the two things only real decoded video produces.
import { chromium } from './browser.mjs';

const BASE = process.argv[2] || 'http://127.0.0.1:8897';

let pass = 0, fail = 0;
const rec = (name, ok, detail = '') => {
  (ok ? pass++ : fail++);
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  -- ' + detail : ''}`);
};

// `--autoplay-policy=no-user-gesture-required` is set so the run can OBSERVE decoding, and
// it is not hiding anything: the page's own safePlay() swallows a rejected play() by design,
// because autoplay policy and an undecodable codec both reject there and only the second is
// a fault. `readyState` is asserted separately below and is reached by buffering alone, with
// no playback at all -- so the decode assertion does not depend on this flag. The flag is
// only what lets `currentTime` be watched moving.
const b = await chromium.launch({
  channel: 'chrome',
  args: ['--autoplay-policy=no-user-gesture-required']
});
const p = await b.newPage();

const errors = [];
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('uncaught: ' + String(e)));

// The real address he asked every app to be at, not /live.html. Both answer; this is the one
// that would silently stop working if the route in api.py were dropped.
await p.goto(`${BASE}/livestack/live`, { waitUntil: 'networkidle' });

// ---- the trap, asserted rather than assumed ------------------------------------------
//
// site/streamer.html:1989 records that Chrome returns 'maybe' -- a TRUTHY string -- from
// canPlayType('application/vnd.apple.mpegurl'), so `if (canPlayType(...)) native;` takes a
// native branch that then plays nothing. Asserting the measurement here means that if a
// future Chrome ever changes it, this suite says so rather than the finding quietly rotting
// into folklore in two comments.
const native = await p.evaluate(() =>
  document.createElement('video').canPlayType('application/vnd.apple.mpegurl'));
rec('Chrome still reports a truthy canPlayType for HLS it cannot actually play',
    native === 'maybe', `canPlayType => ${JSON.stringify(native)}`);
rec('hls.js loaded and reports itself supported',
    await p.evaluate(() => !!(window.Hls && window.Hls.isSupported())),
    await p.evaluate(() => (window.Hls && window.Hls.version) || 'no window.Hls'));

// ---- the live session ------------------------------------------------------------------

await p.waitForSelector('#lv-player:not([hidden])', { timeout: 15000 });
rec('the header reads live', (await p.textContent('#lv-headstate')).trim() === 'live',
    (await p.textContent('#lv-headstate')).trim());
rec('the lamp is lit', (await p.getAttribute('#lv-lamp', 'class')).includes('is-on'));

// The lamp is a real reading, so check it is actually painted green rather than trusting
// that a class name implies a colour -- `.claude/CLAUDE.md`: read computed styles rather
// than reasoning about the cascade. Three bugs in this repo came from class collisions.
const lampColour = await p.evaluate(() =>
  getComputedStyle(document.getElementById('lv-lamp')).backgroundColor);
rec('the lamp is painted the accent green', lampColour === 'rgb(46, 224, 138)', lampColour);

// ---- THE ONE THAT MATTERS ---------------------------------------------------------------

await p.waitForFunction(() => {
  const v = document.getElementById('lv-video');
  return v && v.readyState >= 3;
}, null, { timeout: 20000 }).catch(() => {});

const ready = await p.evaluate(() => document.getElementById('lv-video').readyState);
rec('video decodes (readyState >= 3, HAVE_FUTURE_DATA)', ready >= 3, `readyState=${ready}`);

const dims = await p.evaluate(() => {
  const v = document.getElementById('lv-video');
  return { w: v.videoWidth, h: v.videoHeight };
});
// Real frames have real dimensions. A manifest that loaded but produced no video leaves
// these at 0, which readyState alone can briefly fail to distinguish.
rec('real frames arrived (videoWidth/Height are the fixture’s)',
    dims.w === 320 && dims.h === 180, `${dims.w}x${dims.h}`);

const advanced = await p.evaluate(async () => {
  const v = document.getElementById('lv-video');
  v.muted = true;
  try { await v.play(); } catch (e) { /* policy; readyState above already proved decode */ }
  const t0 = v.currentTime;
  await new Promise(r => setTimeout(r, 1200));
  return { t0, t1: v.currentTime };
});
rec('playback actually advances', advanced.t1 > advanced.t0,
    `currentTime ${advanced.t0.toFixed(2)} -> ${advanced.t1.toFixed(2)}`);

// ---- honesty of the readings -------------------------------------------------------------

// No OBS in this run, so the bridge has nothing. Every reading it owns must render an em dash
// and NOT a zero: a dropped-frame count of 0 before anything has connected is a decorative
// gauge, which this site bars outright. This is the assertion that stops someone "tidying"
// the formatter into `value || 0`.
const drop = (await p.textContent('#lv-r-drop')).trim();
const fps = (await p.textContent('#lv-r-fps')).trim();
rec('an unmeasured drop count is an em dash, never 0', drop === '—', JSON.stringify(drop));
rec('an unmeasured fps is an em dash, never 0', fps === '—', JSON.stringify(fps));
rec('the bridge says in words that it is not configured',
    /SYMONEURAL_OBS_PASSWORD|not configured|not started/i.test(await p.textContent('#lv-r-bridge')),
    (await p.textContent('#lv-r-bridge')).trim());

// Measured readings, by contrast, must be present -- the disk half needs no credential, and
// the whole design claim is that it keeps working while the bridge is down.
rec('the disk half still reports, with no OBS anywhere',
    (await p.textContent('#lv-r-segs')).trim() === '3',
    `segments=${(await p.textContent('#lv-r-segs')).trim()}`);

// ---- the unservable recording is SHOWN, not skipped ----------------------------------------

const bad = await p.textContent('#lv-vods');
rec('a recording OBS wrote under an unusable name is shown with its reason',
    /cannot be served/.test(bad) && /Filename Formatting/.test(bad),
    /cannot be served/.test(bad) ? 'reason and repair both present' : 'not shown at all');

// ---- the VOD half ---------------------------------------------------------------------------

rec('the finished recording is listed', (await p.locator('.lv-vod').count()) >= 1,
    `${await p.locator('.lv-vod').count()} listed`);

await p.locator('.lv-vod button').first().click();
await p.waitForFunction(() => {
  const n = document.getElementById('lv-now');
  return n && /Recording/.test(n.textContent);
}, null, { timeout: 10000 }).catch(() => {});
rec('clicking Watch switches the same window to the recording',
    /Recording/.test(await p.textContent('#lv-now')),
    (await p.textContent('#lv-now')).trim());

await p.waitForFunction(() => {
  const v = document.getElementById('lv-video');
  return v && v.readyState >= 3;
}, null, { timeout: 20000 }).catch(() => {});
rec('the recording decodes too',
    (await p.evaluate(() => document.getElementById('lv-video').readyState)) >= 3);

// ---- layout ---------------------------------------------------------------------------------

// The three viewports the rest of this repo's suites gate on. Horizontal overflow is the
// failure mode that a desktop-only look never shows you.
for (const [w, h] of [[1440, 900], [1301, 740], [390, 844]]) {
  await p.setViewportSize({ width: w, height: h });
  await p.waitForTimeout(120);
  const over = await p.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  rec(`nothing overflows horizontally at ${w}x${h}`, over <= 0, `overflow ${over}px`);
}

// No ellipsis anywhere on this page. Every `text-overflow` rule was removed from this site
// deliberately -- the rack was cutting `built on Qwen2.5-7B-Instruct` down to `...7B-Ins...`
// and that attribution is an Apache-2.0 licence condition. This catches one being added back.
const clipped = await p.evaluate(() => Array.from(document.querySelectorAll('*'))
  .filter(el => getComputedStyle(el).textOverflow === 'ellipsis').length);
rec('no element on this page clips its text with an ellipsis', clipped === 0, `${clipped} found`);

rec('no uncaught JavaScript errors', errors.length === 0, errors.slice(0, 3).join(' | '));

await b.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
