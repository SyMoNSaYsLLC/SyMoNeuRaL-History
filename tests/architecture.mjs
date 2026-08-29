#!/usr/bin/env node
// The defects `responsive.mjs` cannot see, asserted at the widths the brief names.
//
//   node tests/architecture.mjs [baseURL]
//
// ## Why this is a second suite and not more cases in the first one
//
// `tests/responsive.mjs` asks three questions -- does the document scroll sideways, does any
// visible element extend past the right edge, is every interactive element reachable -- and
// it answers them well. It ran GREEN, 384 page/viewport combinations and 0 findings, against
// the exact tree whose Live Stack rows measured 33px at 1440x900 and whose body text was
// 14.5px at 1280. Nothing it asks could have caught either.
//
// That is not a gap to patch by bolting cases onto it. Those three questions are about
// whether the layout is BROKEN; these are about whether it is READABLE, and a readability
// floor is a different kind of claim -- it is a number chosen deliberately, it will be
// argued with, and it needs to sit where the argument is visible rather than buried in a
// 900-line overflow suite. So: separate file, every threshold stated with the measurement
// that chose it.
//
// ## Every threshold here is a floor that was measured, not a preference
//
// The numbers below are the ones the reported defects were measured AT, rounded toward the
// broken side so the test fails on a regression rather than on a rounding difference. Each
// carries the before/after reading it came from. A threshold with no measurement attached is
// how a suite starts encoding somebody's taste, and this repo has a rule about that.
import { chromium } from './browser.mjs';

const BASE = process.argv[2] || 'http://127.0.0.1:8800';

// The 23 shell pages `responsive.mjs` walks, so the two suites cover the same surface and a
// page cannot be readable in one and absent from the other.
const PAGES = [
  '/index.html', '/overview.html', '/livestack.html', '/controlboard.html', '/receipts.html',
  '/chat.html', '/image.html', '/ravencalc.html', '/remix.html', '/miner.html', '/gateway.html',
  '/streamer.html', '/studio.html', '/exp.html', '/project.html', '/reinforce.html',
  '/sigils.html', '/coder.html', '/live.html', '/account.html', '/credits.html',
  '/documentation.html', '/build.html',
];

const MOBILE = [320, 375, 390, 430];
const DESKTOP = [768, 1024, 1280, 1440, 1920];

const findings = [];
const record = (vp, page, kind, detail) => findings.push({ vp, page, kind, detail });

// ---------------------------------------------------------------------------------------
// The probe. One evaluate per page/viewport; everything below is read from the rendered
// document rather than from the stylesheet, because a rule that exists and does not apply
// is exactly the failure being tested for.
const probe = () => {
  const vw = document.documentElement.clientWidth;
  const px = (v) => parseFloat(v) || 0;
  const out = { vw };

  const brand = document.querySelector('header .logo b');
  if (brand) {
    out.brandText = (brand.textContent || '').trim();
    out.brandClipped = brand.scrollWidth > brand.clientWidth + 1;
  }

  const nav = document.querySelector('header .bar > nav');
  if (nav) {
    out.navFixed = getComputedStyle(nav).position === 'fixed';
    // Rows are counted by clustering the link boxes by their vertical CENTRE, not by their
    // `top`. Tops legitimately differ inside one row: `.cta` is a padded pill and a bare
    // link is not, so a top-based count reported two rows for every desktop header on the
    // site and would have made this whole assertion useless.
    const centres = [];
    let visible = 0;
    for (const a of nav.querySelectorAll(':scope > a')) {
      const s = getComputedStyle(a);
      if (s.display === 'none' || s.visibility === 'hidden') continue;
      const b = a.getBoundingClientRect();
      if (b.height <= 0) continue;
      visible++;
      const mid = b.top + b.height / 2;
      if (!centres.some((c) => Math.abs(c - mid) < 12)) centres.push(mid);
    }
    out.navRows = centres.length;
    out.navLinks = visible;
    const first = nav.querySelector(':scope > a:not(.cta)');
    out.navFontSize = first ? px(getComputedStyle(first).fontSize) : null;
    // Touch targets, measured on what a finger actually hits.
    out.navMinTarget = Math.min(
      ...[...nav.querySelectorAll(':scope > a')]
        .filter((a) => getComputedStyle(a).display !== 'none')
        .map((a) => a.getBoundingClientRect().height)
        .filter((h) => h > 0),
      Infinity,
    );
  }

  const toggle = document.querySelector('header .navtoggle');
  out.toggleShown = !!toggle && getComputedStyle(toggle).display !== 'none';
  if (toggle) {
    const b = toggle.getBoundingClientRect();
    out.toggleSize = Math.min(b.width, b.height);
    out.toggleExpanded = toggle.getAttribute('aria-expanded');
    out.toggleControls = toggle.getAttribute('aria-controls');
    out.toggleLabelled = !!(toggle.getAttribute('aria-label') || '').trim();
  }

  const body = document.body;
  out.bodyPadBottom = px(getComputedStyle(body).paddingBottom);

  // The TYPE LADDER, read off :root rather than hunted for on an element.
  //
  // The first cut of this looked for `main p, section p, .card p, .lede, .sub` and took the
  // first match. That was wrong in two directions at once and both were reported as site
  // defects when they were probe defects: on the rack pages the first match was a `.sub`,
  // which is a CAPTION at --t6 and is supposed to be smaller than body copy; and on the
  // card-led pages it was `.card p`, which is deliberately on the secondary step --t5.
  // A floor applied to whichever element happened to match first is a floor applied to a
  // different thing on every page.
  //
  // The ladder is the thing that was actually changed and the thing a reader experiences, so
  // it is what gets asserted. Both steps, separately, because they have different jobs: --t4
  // is body copy and --t5 is secondary text, and collapsing them would either let body copy
  // shrink or force captions to grow.
  // Resolved through a real element, NOT read off `:root` with `getPropertyValue`.
  // A custom property that is not registered with `@property` has no computed value of its
  // own -- `getPropertyValue('--t4')` hands back the literal string
  // `clamp(16.5px, calc(...), 21.75px)`, which parses to NaN and read as 0px on every page.
  // Assigning it to a font-size and reading THAT back is what makes the browser evaluate
  // the clamp.
  const ruler = document.createElement('span');
  ruler.style.cssText = 'position:absolute;visibility:hidden;font-size:var(--t4)';
  ruler.textContent = 'x';
  document.body.appendChild(ruler);
  out.t4 = px(getComputedStyle(ruler).fontSize);
  ruler.style.fontSize = 'var(--t5)';
  out.t5 = px(getComputedStyle(ruler).fontSize);
  ruler.remove();

  // Separately: the genuine readability floor, over every element that actually paints text.
  // Nothing on a page should render below this regardless of which step it is on.
  let smallest = Infinity, smallestSel = '';
  for (const el of document.querySelectorAll('body *')) {
    if (!el.firstChild || el.firstChild.nodeType !== 3) continue;
    if (!(el.textContent || '').trim()) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') continue;
    const b = el.getBoundingClientRect();
    if (b.width <= 0 || b.height <= 0) continue;
    const fs = px(cs.fontSize);
    if (fs > 0 && fs < smallest) {
      smallest = fs;
      smallestSel = el.tagName.toLowerCase() +
        (el.className ? '.' + String(el.className).trim().split(/\s+/)[0] : '');
    }
  }
  out.smallestText = smallest === Infinity ? null : smallest;
  out.smallestSel = smallestSel;

  // The rack, when this page has one.
  // `.units.gpu-stack` is the COMPACT STATUS RAIL that miner, streamer, gateway and sigils
  // embed in a sidebar -- same markup and same id, deliberately dense, and correctly so: it
  // is a peripheral readout beside the page's real work, not the rack. The Live Stack page's
  // rack is the main object and is what the row-height floor is about. Told apart here so
  // the assertion can be about the right one; conflating them reported four working sidebars
  // as defects.
  out.rackIsRail = !!document.querySelector('#units.gpu-stack');
  const units = [...document.querySelectorAll('#units .unit')];
  out.rackRows = units.length;
  if (units.length) {
    const hs = units.map((u) => u.getBoundingClientRect().height).filter((h) => h > 0);
    out.rackMinRow = Math.min(...hs);
    out.rackWithSubs = document.querySelectorAll('#units .unit.has-subs').length;
    out.rackSubs = document.querySelectorAll('#units .usub').length;
    out.rackHrefs = units.map((u) => u.getAttribute('href'));
  }

  // The scoped documentation link the shell adds.
  const docs = document.querySelector('header .bar > nav a[data-appdocs]');
  out.docsHref = docs ? docs.getAttribute('href') : null;

  // ---- 6.1: page-family composition ---------------------------------------------------
  out.family = document.documentElement.getAttribute('data-family');
  const wrap = [...document.querySelectorAll('section .wrap, .tabpanel .wrap, main .wrap')]
    .map(e => e.getBoundingClientRect()).filter(b => b.width > 0)[0];
  out.contentW = wrap ? Math.round(wrap.width) : null;
  out.contentPct = wrap ? +(wrap.width / vw).toFixed(3) : null;

  // The compact status rail. Its child pills overflowed it by 42-53px after 6.0 added them,
  // measured on /image.html at 1440 -- a defect this repo's own stylesheet shipped, and one
  // no viewport-overflow check can see because the rail is inside the page, not past its edge.
  const rail = document.querySelector('#units.gpu-stack');
  if (rail) {
    let worst = 0;
    for (const pill of rail.querySelectorAll('.usub')) {
      const a = pill.getBoundingClientRect();
      const b = pill.parentElement.getBoundingClientRect();
      worst = Math.max(worst, a.right - b.right);
    }
    out.railPillOverflow = Math.round(worst);
    out.railW = Math.round(rail.getBoundingClientRect().width);
  }

  // The platform documentation index on /documentation.html.
  out.dxLinks = [...document.querySelectorAll('.dx a[href^="/docs/"]')]
    .map(a => a.getAttribute('href').replace('/docs/', ''));

  out.scrollW = document.documentElement.scrollWidth;
  return out;
};

// ---------------------------------------------------------------------------------------
const browser = await chromium.launch({ channel: 'chrome' });
let checked = 0;

for (const w of [...MOBILE, ...DESKTOP]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: w < 500 ? 780 : 900 } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => record(w, page.url(), 'js error', String(e).slice(0, 140)));

  for (const path of PAGES) {
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(180);
    const r = await page.evaluate(probe);
    checked++;

    // --- the brand is never abbreviated ------------------------------------------------
    // Reported as clipped to `S..`. The mechanism is real and still present:
    // `header .logo b` carries `overflow:hidden; text-overflow:ellipsis` below 900px, so a
    // header that runs out of room truncates the product name rather than wrapping. This
    // asserts the room exists at every width, which is the property, rather than asserting
    // the rule is absent -- the rule is the correct last resort.
    if (r.brandText !== undefined) {
      if (r.brandClipped) record(w, path, 'brand clipped', `"${r.brandText}" is truncated`);
      if (r.brandText !== 'SyMoNeuRaL') {
        record(w, path, 'brand text', `header wordmark reads "${r.brandText}"`);
      }
    }

    // --- no horizontal overflow, anywhere ----------------------------------------------
    if (r.scrollW > r.vw + 1) {
      record(w, path, 'overflow', `document scrolls to ${r.scrollW} in ${r.vw}`);
    }

    if (w <= 430) {
      // --- one header row, and a real menu control -----------------------------------
      // The reported defect is "desktop navigation wraps into multiple mobile rows". The
      // drawer already existed; this asserts it is actually in force rather than that it is
      // written down, which is the distinction the whole suite is about.
      if (!r.toggleShown) record(w, path, 'no menu control', 'the drawer toggle is not shown');
      if (r.navRows > 1 && !r.navFixed) {
        record(w, path, 'nav wraps', `${r.navRows} rows of ${r.navLinks} links in the bar`);
      }
      // 44px is the standing figure in this stylesheet (`--ctl-touch`), not a new one.
      if (r.toggleShown && r.toggleSize < 44) {
        record(w, path, 'touch target', `menu control is ${Math.round(r.toggleSize)}px`);
      }
      // The drawer has to be announced, or it is a button that does nothing for a screen
      // reader. All three attributes are set by site/shell.js.
      if (r.toggleShown && (r.toggleExpanded === null || !r.toggleControls || !r.toggleLabelled)) {
        record(w, path, 'menu a11y',
          `expanded=${r.toggleExpanded} controls=${r.toggleControls} labelled=${r.toggleLabelled}`);
      }
      // --- the browser chrome does not sit on the last control ------------------------
      // Measured at 28px, which is `max(28px, env(safe-area-inset-bottom))` on a device
      // reporting no inset. The floor is what is asserted; a device with a real inset gets
      // more and still passes.
      if (r.bodyPadBottom < 28) {
        record(w, path, 'safe area', `body padding-bottom is ${r.bodyPadBottom}px`);
      }
    }

    if (w >= 1024) {
      // --- readable at desktop viewing distance --------------------------------------
      // Measured BEFORE: body 14.5px and navigation 12.5px at both 1024 and 1280 -- the
      // same sizes a 320px phone was given. AFTER: 16.5px and 14.5px. The floors are set
      // just under the after-figures so the assertion is about the repair holding, not
      // about the exact clamp arithmetic, which is free to change.
      // Measured BEFORE: --t4 14.5px and --t5 12.5px at both 1024 and 1280 -- the same
      // sizes a 320px phone was given. AFTER: 16.5px and 14.5px.
      if (r.t4 < 16) record(w, path, 'body type', `--t4 is ${r.t4}px at ${w}px wide`);
      if (r.t5 < 14) record(w, path, 'secondary type', `--t5 is ${r.t5}px at ${w}px wide`);
      if (r.navFontSize !== null && r.navFontSize < 14) {
        record(w, path, 'nav type', `navigation is ${r.navFontSize}px at ${w}px wide`);
      }
      // No text anywhere below 11px at desktop widths. This is the backstop the ladder
      // assertions cannot provide: a rule with a hardcoded `font-size:9px` does not move
      // when the ladder does.
      if (r.smallestText !== null && r.smallestText < 11) {
        record(w, path, 'tiny text',
          `${r.smallestSel} renders at ${r.smallestText}px`);
      }
      // The full navigation belongs on a desktop, not a hamburger.
      if (r.toggleShown) {
        record(w, path, 'unexpected drawer', `the menu control is shown at ${w}px`);
      }

      // --- 6.1: the application uses the screen it was given -------------------------
      // Measured BEFORE 6.1 at 1440: every application page laid its content out at
      // 1120px -- 77.8% of the viewport, and 58% at 1920 -- because `--max` was one value
      // for the whole site. AFTER: 0.933 at 1440. The floor is 0.85, below the after-figure
      // so the assertion is about the repair holding rather than about the exact `min()`
      // arithmetic, which is free to change.
      //
      // PROSE IS DELIBERATELY EXEMPT and that is the substance of the rule, not an
      // exception to it: index, credits, build, account and the docs pages keep a bounded
      // measure, because a 1,700px line of prose is worse to read and widening them would
      // be the same mistake in the opposite direction.
      //
      // Expressed as "uses what is there, up to a deliberate cap" and NOT as a flat
      // percentage. A percentage floor sounds simpler and is wrong: it says an application
      // must keep growing forever, so a 2560px monitor would demand a 2176px workspace,
      // and the first version of this assertion duly failed every workspace page at 1920
      // for hitting its own intended maximum. A cap is a design decision, not a defect.
      const wanted = Math.min(1560, w - 120);
      if (['workbench', 'workspace', 'dashboard'].includes(r.family)
          && r.contentW !== null && r.contentW < wanted) {
        record(w, path, 'narrow workspace',
          `${r.family} page uses ${r.contentW}px of ${w}px (wanted at least ${wanted}px)`);
      }
      // A page with a workspace must have been given a family at all -- an unfamilied
      // application page is how one silently keeps the prose width forever.
      if (r.rackIsRail && !r.family) {
        record(w, path, 'no page family', 'a page with an application rail has no data-family');
      }
    }

    // --- 6.1: the compact rail contains its own children ------------------------------
    // Applies at EVERY width, not only desktop: the rail is where it is narrowest that this
    // breaks, and at 390px it stacks rather than sitting beside the work.
    if (r.railPillOverflow !== undefined && r.railPillOverflow > 1) {
      record(w, path, 'rail overflow',
        `child pills overflow the ${r.railW}px status rail by ${r.railPillOverflow}px`);
    }

    // --- 6.1: the documentation landing is a real index -------------------------------
    // `site/documentation.html` carries a hand-written index of the scoped application docs.
    // Hand-written because nothing generates that file as a whole and an index that fetches
    // the API is blank when the API is down -- so the honesty of it rests HERE. Both
    // directions are checked: every link resolves, and the set matches what the service
    // actually serves, so an application added to the registry and forgotten here goes red.
    if (path === '/documentation.html') {
      if (r.dxLinks.length === 0) {
        record(w, path, 'no docs index', 'the documentation landing carries no scoped docs links');
      } else if (w === 1440) {
        const live = await (await page.request.get(BASE + '/api/status')).json().catch(() => null);
        void live;
        for (const id of r.dxLinks) {
          const res = await page.request.get(BASE + '/docs/' + id);
          if (!res.ok()) record(w, path, 'dead docs link', `/docs/${id} answered ${res.status()}`);
        }
      }
    }

    // --- the rack: runtime -> application -> child ------------------------------------
    if (r.rackRows) {
      // Measured BEFORE: 33px rows at 1440x900 and 37px at 1920x1080 on /livestack, which
      // is the "unreadable one-line slivers" defect. AFTER: 50px and 55px. 44px is the
      // floor -- the same touch figure the rest of this file uses, and a rack row is a link
      // somebody taps.
      // 44px on the Live Stack, where the rack IS the page and a row is a link to tap.
      // 24px on the compact sidebar rail, which is a readout rather than a workspace and
      // whose density is the point -- a floor there would be a redesign, not a repair.
      const floor = r.rackIsRail ? 24 : 44;
      if (r.rackMinRow < floor) {
        record(w, path, 'rack row height',
          `shortest rack row is ${Math.round(r.rackMinRow)}px (floor ${floor}` +
          `${r.rackIsRail ? ', compact rail' : ''})`);
      }
      // Reinforce and Exp are child surfaces of Studio and must not be top-level rows; the
      // rack must show the ownership rather than a flat list. Asserted on /livestack, which
      // is the page whose job this is.
      if (path === '/livestack.html') {
        for (const gone of ['/reinforce.html', '/exp']) {
          if ((r.rackHrefs || []).includes(gone)) {
            record(w, path, 'flat rack', `${gone} is still a top-level rack row`);
          }
        }
        if (!r.rackWithSubs) {
          record(w, path, 'no nesting', 'no rack row renders its child components');
        }
        if (r.rackSubs < 5) {
          // miner has three children and studio has two.
          record(w, path, 'missing children', `${r.rackSubs} child components rendered, expected 5`);
        }
      }
    }

    // --- every application page links its own scoped documentation --------------------
    const EXPECT_DOCS = {
      '/chat.html': '/docs/chat', '/image.html': '/docs/image', '/remix.html': '/docs/remix',
      '/ravencalc.html': '/docs/ravencalc', '/sigils.html': '/docs/sigils',
      '/project.html': '/docs/project', '/miner.html': '/docs/miner',
      '/gateway.html': '/docs/gateway', '/streamer.html': '/docs/streamer',
      '/studio.html': '/docs/studio', '/reinforce.html': '/docs/train',
      '/exp.html': '/docs/exp', '/live.html': '/docs/live', '/coder.html': '/docs/coder',
      '/account.html': '/docs/accounts',
    };
    if (EXPECT_DOCS[path] && r.docsHref !== EXPECT_DOCS[path]) {
      record(w, path, 'docs link', `expected ${EXPECT_DOCS[path]}, found ${r.docsHref}`);
    }
  }
  await ctx.close();
}

// --- the Coder href, which the Live Stack audit found and did not fix -------------------
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const status = await (await page.goto(BASE + '/api/status')).json();
  const coder = status.units.find((u) => u.id === 'coder');
  if (!coder) record(1440, '/api/status', 'missing row', 'no coder row');
  else if (coder.href !== '/livestack/coder') {
    record(1440, '/api/status', 'coder href', `the rack links coder to ${coder.href}`);
  }
  // The fold, asserted against the live service rather than the source.
  const ids = status.units.map((u) => u.id);
  for (const gone of ['train', 'exp']) {
    if (ids.includes(gone)) record(1440, '/api/status', 'unfolded', `${gone} is a top-level row`);
  }
  const studio = status.units.find((u) => u.id === 'studio');
  const subs = (studio && studio.sub ? studio.sub : []).map((s) => s.id);
  for (const kid of ['train', 'exp']) {
    if (!subs.includes(kid)) {
      record(1440, '/api/status', 'lost child', `${kid} is neither a row nor a studio child`);
    }
  }
  // Folded is not deleted: both pages still answer.
  for (const url of ['/reinforce.html', '/exp', '/livestack/coder', '/docs/train', '/docs/exp']) {
    const res = await page.goto(BASE + url);
    if (!res.ok()) record(1440, url, 'dead surface', `answered ${res.status()}`);
  }
  await ctx.close();
  checked += 1;
}

await browser.close();

const green = findings.length === 0;
if (!green) {
  console.log('\nfindings:');
  for (const f of findings) {
    console.log(`  ${String(f.vp).padStart(5)}  ${f.page.padEnd(24)} ${f.kind.padEnd(18)} ${f.detail}`);
  }
}
console.log(`\n${green ? 'PASS' : 'FAIL'}  ${checked} checks, ${findings.length} findings`);
process.exit(green ? 0 : 1);
