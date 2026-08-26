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

const probe = () => {
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

  // (2) right edges
  const over = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!shown(el)) continue;
    const b = el.getBoundingClientRect();
    if (b.right > vw + 1 && !scrollable(el)) over.push({ el: name(el), right: Math.round(b.right) });
  }

  // (3) reachability of interactive elements. Off-screen-below is fine -- that is scrolling,
  // not a defect -- so only horizontal position and hit-testing are judged, and only for
  // controls currently within the vertical viewport (elementFromPoint cannot answer for the
  // rest without scrolling them into view).
  const unreachable = [];
  for (const el of document.querySelectorAll('a[href], button, input, select, textarea, [role="button"], [role="tab"]')) {
    if (!shown(el)) continue;
    const b = el.getBoundingClientRect();
    if ((b.left < -1 || b.right > vw + 1) && !scrollable(el)) {
      unreachable.push({ el: name(el), why: `x ${Math.round(b.left)}..${Math.round(b.right)} outside 0..${vw}` });
      continue;
    }
    if (b.left < -1 || b.right > vw + 1) continue;   // reachable by scrolling its container
    if (b.top < 0 || b.bottom > vh) continue;          // simply below the fold
    const hit = document.elementFromPoint((b.left + b.right) / 2, (b.top + b.bottom) / 2);
    if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) {
      unreachable.push({ el: name(el), why: `covered by ${name(hit)}` });
    }
  }

  return {
    vw, scrollW: document.documentElement.scrollWidth,
    over: over.slice(0, 25), overCount: over.length,
    unreachable: unreachable.slice(0, 25), unreachableCount: unreachable.length,
  };
};

const browser = await chromium.launch({ channel: 'chrome', args: ['--no-sandbox'] });
const findings = [];
let checked = 0;

for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
  const page = await ctx.newPage();
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
      findings.push({ vp: vp.label, path, kind: 'ERROR', detail: e.message.split('\n')[0] });
      continue;
    }
    if (r.scrollW > r.vw + 1 || r.overCount) {
      findings.push({
        vp: vp.label, path, kind: 'OVERFLOW',
        detail: `scrollWidth ${r.scrollW} vs ${r.vw}; ${r.overCount} element(s) past the right edge: `
              + r.over.map(o => `${o.el}@${o.right}`).join(', '),
      });
    }
    if (r.unreachableCount) {
      findings.push({
        vp: vp.label, path, kind: 'UNREACHABLE',
        detail: `${r.unreachableCount}: ` + r.unreachable.map(u => `${u.el} (${u.why})`).join(', '),
      });
    }
    if (jsErrors.length) {
      findings.push({ vp: vp.label, path, kind: 'JSERROR', detail: [...new Set(jsErrors)].join(' | ') });
    }
  }
  await ctx.close();
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
  `- pages x viewports checked: **${checked}**`,
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
  `Pages: ${PAGES.length}.`);

writeFileSync(OUT, lines.join('\n') + '\n');

console.log(`\n${green ? 'PASS' : 'FAIL'}  ${checked} page/viewport combinations, ${findings.length} findings`);
for (const f of findings) console.log(`  ${f.kind.padEnd(12)} ${String(f.vp).padEnd(16)} ${f.path.padEnd(22)} ${f.detail.slice(0, 150)}`);
console.log(`\nwrote ${OUT}`);
process.exit(green ? 0 : 1);
