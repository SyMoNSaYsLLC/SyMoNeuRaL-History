// Heading outlines and keyboard focus, on every page at every width, in a real browser.
//
//   node tests/accessibility.mjs [baseURL]      # default http://127.0.0.1:8800
//
// ## Why this exists as a file rather than as a probe somebody runs once
//
// The residual findings this file was written to close were found by an ad-hoc probe during
// the 2026-08-29 session and nothing in the repository could re-run it. Its count did not
// survive contact with a repeatable check -- two of its heading findings were missing and
// five of its focus findings did not exist. That is the same shape as
// every other failure `.claude/CLAUDE.md` records: a reading nobody can reproduce is a claim,
// and this project has already published one figure that was never true of the commit beside
// it. A finding with no committed check is a finding that comes back.
//
// So the sweep is a suite, it writes a stamped record, and the record names the source commit.
//
// ## The two things measured, and why each needs a browser
//
//   1. HEADING OUTLINE -- no level may be skipped on the way down. `h1` then `h3` tells a
//      screen-reader user a section is nested inside something that is not there.
//
//      This cannot be checked by reading `site/*.html`. Three of the four defects it found
//      are built at RUNTIME by backend-owned JavaScript -- studio, exp and streamer assemble
//      headings after load -- so the file on disk has a correct outline and the rendered page
//      does not. `backend/apps/test_page_families.py` names those pages as known exemptions
//      precisely because a static reader cannot see them.
//
//   2. FOCUS INDICATOR -- focusing a control must visibly change something. Measured by
//      diffing computed style on the element AND its three nearest ancestors, before and
//      after focus, because `:focus-within` on a wrapper is a legitimate way to draw the
//      ring and an element-only check calls it a defect. A stylesheet that sets
//      `outline:none` and supplies nothing anywhere leaves a keyboard user with no cursor:
//      the page still works and there is no way to see where you are.
//
//      Both readings are computed style on a laid-out element, which is the browser's answer
//      and not a guess from a selector.
//
// ## Why it writes a record
//
// Same reason `tests/responsive.mjs` does, and the same enforcement: a task carrying
// `ngrep FINDING -- docs/ops/SMOKE-ACCESSIBILITY.md` can only go green after a run that found
// none. Editing a source file cannot satisfy it.
import { chromium } from './browser.mjs';
import { writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const BASE = process.argv[2] || 'http://127.0.0.1:8800';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
// NOT in site/: that directory is the webroot and `scripts/deploy.sh --prune` publishes it.
// A smoke record is an internal reading, not a page.
const OUT = join(ROOT, 'docs', 'ops', 'SMOKE-ACCESSIBILITY.md');

// Three widths, because a finding can be width-dependent and a desktop-only sweep would then
// report zero and be wrong. Measured here, none of the current findings actually is: the one
// focus defect and all five heading jumps reproduce identically at 390, 768 and 1440, which is
// what tells you they are structural rather than a media-query artifact.
//
// A handoff note claimed five focus failures specific to 390px on coder, exp, image, reinforce
// and remix. None reproduced, under this check or under real keyboard Tab traversal of all 141
// focusable elements across those five pages. That claim came from an ad-hoc probe that was
// never committed and cannot be re-read -- which is the argument for this file.
const VIEWPORTS = [
  { w: 390, h: 844, label: '390' },
  { w: 768, h: 1024, label: '768' },
  { w: 1440, h: 900, label: '1440' },
];

// The same surfaces tests/responsive.mjs drives, for the same reasons: streamer-watch and
// share-dispatchos carry no shell, so neither is in scope here.
const PAGES = [
  '/index.html', '/overview.html', '/livestack.html', '/controlboard.html', '/receipts.html',
  '/chat.html', '/image.html', '/ravencalc.html', '/remix.html', '/miner.html', '/gateway.html',
  '/streamer.html', '/studio.html', '/exp.html', '/project.html', '/reinforce.html',
  '/sigils.html', '/coder.html', '/live.html', '/account.html', '/credits.html',
  '/documentation.html', '/build.html',
];

// `/training.html` is deliberately absent, and named here rather than left out quietly.
//
// It is the manual: `tools/build_training.py` renders it from Markdown, and it carries ten
// part-level `<h1>`s with h2..h6 beneath them -- a book outline, not a page outline.
// `tools/page_families.py` already classifies it as "the manual; already carries its own
// <main> and is not a shell page", and `backend/apps/test_page_families.py` excludes it from
// its own PAGES list for the same reason.
//
// Measured before excluding it: 12 heading jumps per viewport, all `2 -> 4`, all from the
// Markdown source's own sectioning. That is one editorial decision about how the manual is
// structured, owned by the Markdown and not by any generator this sweep can reach -- not 36
// findings. If the manual's outline is ever brought into scope, delete this constant and
// this comment; the exemption should die with the exception.
const EXCLUDED = { '/training.html': 'the manual: book outline, owned by its Markdown source' };

const findings = [];
const record = (page, vp, kind, detail) =>
  findings.push({ page, vp, kind, detail });

const browser = await chromium.launch({ channel: 'chrome' });

for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
  const pg = await ctx.newPage();

  for (const path of PAGES) {
    try {
      await pg.goto(BASE + path, { waitUntil: 'networkidle', timeout: 20000 });
    } catch {
      // A page that will not settle is a different defect and responsive.mjs owns it.
      await pg.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 20000 });
    }
    // Runtime-built headings arrive after load on studio/exp/streamer. Without this the
    // sweep reads the pre-hydration outline and reports a clean page that is not clean.
    await pg.waitForTimeout(400);

    // ---- 1. heading outline -------------------------------------------------------------
    const jumps = await pg.evaluate(() => {
      const out = [];
      const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
        .filter(h => {
          const s = getComputedStyle(h);
          // A heading nobody can see is not in the outline a screen reader announces.
          return s.display !== 'none' && s.visibility !== 'hidden'
                 && h.offsetWidth + h.offsetHeight > 0;
        });
      let prev = 0;
      for (const h of hs) {
        const lvl = Number(h.tagName[1]);
        if (prev && lvl > prev + 1) {
          out.push({ from: prev, to: lvl,
                     text: (h.textContent || '').trim().slice(0, 48) });
        }
        prev = lvl;
      }
      return out;
    });
    for (const j of jumps) {
      record(path, vp.label, 'heading', `${j.from} -> ${j.to}  "${j.text}"`);
    }

    // ---- 2. focus indicator -------------------------------------------------------------
    const noFocus = await pg.evaluate(() => {
      const out = [];
      const sel = 'a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])';
      const vis = el => {
        const s = getComputedStyle(el);
        return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0'
               && el.offsetWidth + el.offsetHeight > 0;
      };
      const snap = el => {
        const s = getComputedStyle(el);
        return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.outlineOffset,
                s.boxShadow, s.borderColor, s.borderWidth, s.backgroundColor].join('|');
      };
      // The indicator does not have to be ON the focused element. `:focus-within` on a
      // wrapper is a normal and deliberate pattern -- chat's composer draws the ring on
      // `.cu-composer` and leaves the textarea itself bare, which looks like a missing
      // indicator to anything that only inspects the element. Measured: the wrapper's
      // border goes rgb(40,48,43) -> rgba(46,224,138,.45) on focus. That is the indicator.
      //
      // So the snapshot covers the element and its nearest ancestors, and a finding requires
      // that NONE of them responded. Reporting the bare element would have sent someone to
      // add a redundant outline and break a working design -- which is worse than the bug it
      // would have been reported as.
      const chain = el => { const c = [el]; let n = el.parentElement;
                            for (let i = 0; i < 3 && n; i++, n = n.parentElement) c.push(n);
                            return c; };
      const snapAll = el => chain(el).map(snap).join('#');
      const els = [...document.querySelectorAll(sel)].filter(vis);
      for (const el of els) {
        const before = snapAll(el);
        try { el.focus({ preventScroll: true }); } catch { continue; }
        if (document.activeElement !== el) continue;   // not actually focusable
        const after = snapAll(el);
        // `:focus-visible` is the browser's own answer to "is this a keyboard focus that
        // deserves a ring". Requiring it means an element whose indicator is legitimately
        // mouse-only is not reported, and an element the browser HAS decided deserves a ring
        // and which showed nothing is reported with no ambiguity left.
        const fv = el.matches(':focus-visible');
        el.blur();
        if (before === after && fv) {
          const label = (el.getAttribute('aria-label') || el.textContent || el.name
                         || el.id || el.tagName).toString().trim().slice(0, 40);
          out.push(`${el.tagName.toLowerCase()} "${label}"`);
        }
      }
      return out;
    });
    // One finding per page/viewport, listing the controls. Five identical findings for five
    // controls on one page would inflate the count and hide that it is one root cause.
    if (noFocus.length) {
      record(path, vp.label, 'focus',
             `${noFocus.length} focusable element(s) show no focus indicator: `
             + noFocus.slice(0, 4).join(', ') + (noFocus.length > 4 ? ', ...' : ''));
    }
  }
  await ctx.close();
}
await browser.close();

let sha = 'unknown';
try { sha = execSync('git rev-parse --short HEAD', { cwd: ROOT }).toString().trim(); } catch {}

const headings = findings.filter(f => f.kind === 'heading');
const focus = findings.filter(f => f.kind === 'focus');
const uniquePages = new Set(findings.map(f => f.page)).size;

const lines = [
  '# Accessibility sweep',
  '',
  `Generated by \`tests/accessibility.mjs\` at commit \`${sha}\` on ${new Date().toISOString()}.`,
  'Regenerate with `node tests/accessibility.mjs`. Do not hand-edit: this file is a reading,',
  'and a hand-edited reading is exactly the unSHA\'d figure `.claude/CLAUDE.md` warns about.',
  '',
  `Pages: ${PAGES.length}. Viewports: ${VIEWPORTS.map(v => v.label).join(', ')}.`,
  '',
  '## Result',
  '',
  findings.length === 0
    ? 'No findings. Every heading outline descends one level at a time, and every focusable'
      + ' control shows a visible focus indicator at every width measured.'
    : `**${findings.length} FINDING${findings.length === 1 ? '' : 'S'}** across ${uniquePages}`
      + ` page(s): ${headings.length} heading-level, ${focus.length} focus-indicator.`,
  '',
];

if (findings.length) {
  lines.push('| page | viewport | kind | detail |', '|---|---|---|---|');
  for (const f of findings) {
    lines.push(`| \`${f.page}\` | ${f.vp} | ${f.kind} | ${f.detail.replace(/\|/g, '\\|')} |`);
  }
  lines.push('');
}

writeFileSync(OUT, lines.join('\n') + '\n');
console.log(lines.slice(7).join('\n'));
console.log(`\nwrote ${OUT}`);
process.exit(findings.length ? 1 : 0);
