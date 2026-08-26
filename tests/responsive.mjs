// Every page, every target width, in a real browser -- and a stamped record of what it found.
//
//   node tests/responsive.mjs [baseURL]        # default http://127.0.0.1:8800
//
// ## Why this file exists rather than another `grep` check
//
// `.claude/CLAUDE.md` records that #94 and #74 both archived themselves at 100% while
// broken, because `exists` and `grep` ask what is written on disk and cannot ask whether the
// thing works. #94 shipped a chat surface that was dead on arrival with eighteen green
// checks. This redesign is the same shape of task, so #109's binding check is this run.
//
// It writes `docs/ops/SMOKE-FRONTEND.md`, and it writes the word OVERFLOW into that file once
// per page x width that still overflows. #109 carries `ngrep OVERFLOW -- docs/ops/SMOKE-FRONTEND.md`,
// so the check can only go green after a run that found none. Editing a source file cannot
// satisfy it; only a run can.
//
// ## What "overflow" means here, and why scrollWidth alone is not enough
//
// The defect this file was written to catch was INVISIBLE to a scrollWidth check. At 360px
// the header's "Have one built" button laid out at left=336 inside a bar that sets
// `overflow-x:hidden` and clips at 328. The document never scrolled sideways, so
// `documentElement.scrollWidth` read exactly 360 and every existing assertion passed -- while
// the button sat entirely outside the viewport, unreachable, on fourteen pages.
//
// So three separate things are measured:
//
//   1. scrollWidth        the page does not scroll sideways
//   2. right edges        no VISIBLE element extends past the viewport, clipped or not
//   3. reachability       every interactive element is inside the viewport AND is the thing
//                         that would actually receive the click at its own centre point
//
// (3) is what a clip cannot fake. `elementFromPoint` at the control's centre returns the
// control (or a descendant of it) only if a real click there would land on it.

import { chromium } from './browser.mjs';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const BASE = process.argv[2] || 'http://127.0.0.1:8800';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
// NOT in site/: that directory is the webroot and `scripts/deploy.sh --prune`
// publishes it. A smoke record is an internal reading, not a page.
const OUT = join(ROOT, 'docs', 'ops', 'SMOKE-FRONTEND.md');

// The seven widths #109 names, plus one short-height desktop -- the brief asks for short
// windows explicitly, and the front page's tab gate has a documented cliff at 741px of
// height (tools/build_split.py), so a height case is not hypothetical here.
const VIEWPORTS = [
  { w: 360, h: 800, label: '360' },
  { w: 390, h: 844, label: '390' },
  { w: 430, h: 932, label: '430' },
  { w: 768, h: 1024, label: '768' },
  { w: 1024, h: 768, label: '1024' },
  { w: 1440, h: 900, label: '1440' },
  { w: 1920, h: 1080, label: '1920' },
  { w: 1440, h: 700, label: '1440x700 (short)' },
];

// Every user-facing surface. streamer-watch and share-dispatchos are deliberately absent:
// the first is a bare player with no chrome and the second is credential-gated, so neither
// carries the shell this file is checking.
const PAGES = [
  '/index.html', '/overview.html', '/livestack.html', '/controlboard.html', '/receipts.html',
  '/chat.html', '/image.html', '/ravencalc.html', '/remix.html', '/miner.html', '/gateway.html',
  '/streamer.html', '/studio.html', '/exp.html', '/project.html', '/reinforce.html',
  '/sigils.html', '/coder.html', '/live.html', '/account.html', '/credits.html',
  '/documentation.html', '/build.html', '/training.html',
];

const probe = (expectNews) => {
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const name = (el) => {
    const cls = (el.className && el.className.baseVal !== undefined
      ? el.className.baseVal : el.className || '').toString().trim().split(/\s+/)[0];
    return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (cls ? '.' + cls : '');
  };
  const shown = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    const b = el.getBoundingClientRect();
    return b.width > 0 || b.height > 0;
  };

  // A wide element is only a defect if the reader cannot get to it. Two ancestors can put
  // it past the right edge and they are opposites:
  //
  //   overflow-x: auto|scroll   a SCROLL CONTAINER. The far columns of a wide data table are
  //                             reachable by dragging it, the page itself does not move, and
  //                             this is the correct treatment for a table that will not fit.
  //   overflow-x: hidden|clip   a CLIP. The content is gone with no way to reach it. This is
  //                             the header defect exactly, and it must stay a finding.
  //
  // Without this distinction the check reports `#reinforce .rf-scroll`'s seven tables -- which
  // work correctly -- and reporting working code as broken is how a check stops being read.
  const scrollable = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if ((ox === 'auto' || ox === 'scroll') && p.scrollWidth > p.clientWidth + 1) return true;
    }
    return false;
  };

  // The one clip on this site that is not a defect, exempted BY NAME rather than by relaxing
  // the rule above -- relaxing it would re-admit the header bug this whole file exists for.
  //
  // Symon Say News is a marquee. `.sn-window` is `overflow:hidden` and `.sn-run` is
  // `width:max-content`, so the lane is deliberately about 2,000px wide inside a 360px
  // window and every headline sits past the right edge until the animation carries it in.
  // That is content arriving over TIME rather than content thrown away, and the bar itself
  // is `left:0; right:0`, i.e. bounded to the viewport. What still has to hold about the bar
  // is that the bar does not COVER anything -- and that is checked, not exempted, because
  // `elementFromPoint` below would name `aside#symonsaynews` as the thing a click hits.
  const inTicker = (el) => !!el.closest('#symonsaynews .sn-window');

  // (2) right edges
  const over = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!shown(el)) continue;
    const b = el.getBoundingClientRect();
    if (b.right > vw + 1 && !scrollable(el) && !inTicker(el)) over.push({ el: name(el), right: Math.round(b.right) });
  }

  // (3) reachability of interactive elements. Off-screen-below is fine -- that is scrolling,
  // not a defect -- so only horizontal position and hit-testing are judged, and only for
  // controls currently within the vertical viewport (elementFromPoint cannot answer for the
  // rest without scrolling them into view).
  const unreachable = [];
  const covered = [];
  for (const el of document.querySelectorAll('a[href], button, input, select, textarea, [role="button"], [role="tab"]')) {
    if (!shown(el)) continue;
    const b = el.getBoundingClientRect();
    if ((b.left < -1 || b.right > vw + 1) && !scrollable(el) && !inTicker(el)) {
      unreachable.push({ el: name(el), why: `x ${Math.round(b.left)}..${Math.round(b.right)} outside 0..${vw}` });
      continue;
    }
    if (b.left < -1 || b.right > vw + 1) continue;   // reachable by scrolling, or by waiting for the crawl
    if (b.top < 0 || b.bottom > vh) continue;          // simply below the fold
    const hit = document.elementFromPoint((b.left + b.right) / 2, (b.top + b.bottom) / 2);
    if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) covered.push(el);
  }

  // SECOND CHANCE, and it is what separates a real defect from a fixed overlay.
  //
  // Symon Say News is `position:fixed` along the bottom of a page that scrolls, so at any
  // given scroll offset SOME control is under it -- at 1024x768 the chat send button sits at
  // y=725..755 and the bar occupies 741..768, so its centre point lands on the bar. That is
  // the same relationship a fixed header has with the top of a page: the control is not gone,
  // it is one scroll away, and `html.sn-on body{padding-bottom:var(--sn-h)}` already
  // guarantees the END of the document clears the bar.
  //
  // A control clipped outside the viewport, by contrast, is unreachable at EVERY scroll
  // offset. So rather than exempting the bar -- which would blunt the check the same way
  // relaxing the clip rule would -- each covered control is scrolled to the middle of the
  // viewport and re-tested. Whatever is still covered dead centre is genuinely unreachable
  // and stays a finding.
  const stillCovered = [];
  for (const el of covered) {
    el.scrollIntoView({ block: 'center', behavior: 'instant' });
    const b = el.getBoundingClientRect();
    const hit = document.elementFromPoint((b.left + b.right) / 2, (b.top + b.bottom) / 2);
    if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) {
      stillCovered.push({ el: name(el), why: `covered by ${name(hit)} even when scrolled to centre` });
    }
  }
  window.scrollTo(0, 0);
  unreachable.push(...stillCovered);

  return {
    newsOn: document.documentElement.classList.contains('sn-on'),
    vw, scrollW: document.documentElement.scrollWidth,
    over: over.slice(0, 25), overCount: over.length,
    unreachable: unreachable.slice(0, 25), unreachableCount: unreachable.length,
  };
};

// The Symon Say News bar is `position:fixed` along the bottom of EVERY page, and it does not
// exist until the endpoint returns headlines. `SYMONEURAL_NEWS_ENABLED` is unset by default,
// so a run against this box measures the site with the bar absent -- which is a real state,
// and also exactly half of the states this site ships. The first pass of this suite reported
// "0 findings" having never once seen `html.sn-on`, and the composer is at the bottom of the
// page too. So the whole matrix runs twice and the endpoint is intercepted for the second
// pass. Nothing here reaches a publisher; the payload is fabricated, the same way
// `tests/frontend.mjs` drives its two age branches.
const NEWS = {
  enabled: true, count: 2, at: 1, age_s: 30, stale: false,
  newest_at: 1, newest_age_s: 900, interval_s: 900, sources: [], error: null,
  items: [
    { title: 'A synthetic headline, served by tests/responsive.mjs', url: 'https://example.com/a',
      source: 'Test', topic: 'releases', at: 1, score: 1 },
    { title: 'A second synthetic headline, long enough to make the lane measure something',
      url: 'https://example.com/b', source: 'Test', topic: 'models', at: 1, score: 0.9 },
  ],
};

const browser = await chromium.launch({ channel: 'chrome', args: ['--no-sandbox'] });
const findings = [];
let checked = 0;

for (const newsOn of [false, true]) {
for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
  const page = await ctx.newPage();
  if (newsOn) {
    await page.route('**/api/news/ticker', r => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify(NEWS),
    }));
  }
  const jsErrors = [];
  page.on('pageerror', e => jsErrors.push(e.message.split('\n')[0]));

  for (const path of PAGES) {
    checked++;
    jsErrors.length = 0;
    let r;
    try {
      await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForTimeout(400);          // let the news bar and rack paint
      r = await page.evaluate(probe);
    } catch (e) {
      findings.push({ vp: vp.label + (newsOn ? ' +news' : ''), path, kind: 'ERROR', detail: e.message.split('\n')[0] });
      continue;
    }
    if (r.scrollW > r.vw + 1 || r.overCount) {
      findings.push({
        vp: vp.label + (newsOn ? ' +news' : ''), path, kind: 'OVERFLOW',
        detail: `scrollWidth ${r.scrollW} vs ${r.vw}; ${r.overCount} element(s) past the right edge: `
              + r.over.map(o => `${o.el}@${o.right}`).join(', '),
      });
    }
    if (r.unreachableCount) {
      findings.push({
        vp: vp.label + (newsOn ? ' +news' : ''), path, kind: 'UNREACHABLE',
        detail: `${r.unreachableCount}: ` + r.unreachable.map(u => `${u.el} (${u.why})`).join(', '),
      });
    }
    // A "+news" pass that never rendered the bar tests nothing, and would report green for
    // the wrong reason -- the exact failure this second pass was added to fix.
    if (newsOn && !r.newsOn && path !== '/training.html') {
      findings.push({ vp: vp.label + ' +news', path, kind: 'NEWSMISSING',
                      detail: 'the news bar was served headlines and did not appear' });
    }
    if (jsErrors.length) {
      findings.push({ vp: vp.label + (newsOn ? ' +news' : ''), path, kind: 'JSERROR', detail: [...new Set(jsErrors)].join(' | ') });
    }
  }
  await ctx.close();
}
}
await browser.close();

const counts = findings.reduce((a, f) => (a[f.kind] = (a[f.kind] || 0) + 1, a), {});
const green = findings.length === 0;

// The heading states the result in words as well as in the table, because the file is read
// by people as well as by `ngrep`. Note that the literal word OVERFLOW appears in the body
// ONLY via a finding -- the prose here is careful never to spell it, or the check #109
// carries would be red forever no matter how clean the run was.
const lines = [
  '# Frontend responsive smoke record',
  '',
  `Written by \`tests/responsive.mjs\` against \`${BASE}\`.`,
  'Do not hand-edit this file. It is a reading, and a hand-edited reading is worth nothing.',
  '',
  `- page x viewport x news-bar combinations checked: **${checked}**`,
  `- findings: **${findings.length}**`,
  ...Object.entries(counts).map(([k, v]) => `  - ${k}: ${v}`),
  '',
  green
    ? 'Every page laid out inside its viewport at every width, every interactive element was'
      + ' inside the viewport and received its own clicks, and no page raised a JavaScript error.'
    : 'This run found defects. They are listed below and #109 stays red until they are gone.',
  '',
];
if (!green) {
  lines.push('| viewport | page | kind | detail |', '|---|---|---|---|');
  for (const f of findings) {
    lines.push(`| ${f.vp} | \`${f.path}\` | ${f.kind} | ${f.detail.replace(/\|/g, '\\|').slice(0, 400)} |`);
  }
  lines.push('');
}
lines.push('## What was checked', '',
  '1. `documentElement.scrollWidth` against the viewport width.',
  '2. Every visible element\'s right edge -- **clipped elements included**, which is the case a',
  '   `scrollWidth` check cannot see and the case that hid the header defect for as long as it did.',
  '3. Every interactive element: inside the viewport horizontally, and returned by',
  '   `elementFromPoint` at its own centre, so a real click there would reach it.',
  '4. Uncaught JavaScript errors on load.',
  '',
  `Viewports: ${VIEWPORTS.map(v => v.label).join(', ')}.`,
  'Each runs twice: once as this box serves today (news bar off) and once with',
  '`/api/news/ticker` intercepted and answered with a fabricated payload, because the bar is',
  '`position:fixed` along the bottom of every page and the composers are at the bottom too.',
  `Pages: ${PAGES.length}.`);

writeFileSync(OUT, lines.join('\n') + '\n');

console.log(`\n${green ? 'PASS' : 'FAIL'}  ${checked} page/viewport combinations, ${findings.length} findings`);
for (const f of findings) console.log(`  ${f.kind.padEnd(12)} ${String(f.vp).padEnd(16)} ${f.path.padEnd(22)} ${f.detail.slice(0, 150)}`);
console.log(`\nwrote ${OUT}`);
process.exit(green ? 0 : 1);
