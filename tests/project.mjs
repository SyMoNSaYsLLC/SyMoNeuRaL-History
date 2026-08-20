// Drive site/project.html in a real browser.
//
//   python3 tests/project-harness.py &      # 127.0.0.1:8899, throwaway store
//   node tests/project.mjs [baseURL]
//
// Separate from tests/frontend.mjs on purpose: this page needs a surface that is off by
// default and a token that lives in the systemd unit environment on a configured box, so
// it needs its own harness rather than the live API on 8800. Everything here asserts on
// what the DOM actually shows -- `.claude/CLAUDE.md`: read computed styles rather than
// reasoning about the cascade. The `[hidden]` assertion below exists because the first
// version of this page rendered the whole workspace behind the token gate: `#pj-app` at
// specificity (1,0,0) beat the UA stylesheet's `[hidden]` rule at (0,0,1), and nothing but
// a computed style in a real browser would have caught it.

// Playwright lives in the llama.cpp web UI's node_modules, installed when that UI was
// built. Resolved relative to this file so the repo can be cloned anywhere. That directory
// is untracked, so it is absent from a git worktree even though it is present in the
// checkout the worktree came from. `browser.mjs` owns that resolution and its failure
// message names the cause, so there is no fallback ladder here to keep in step with it.
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from './browser.mjs';
const REPO = dirname(dirname(fileURLToPath(import.meta.url)));

const BASE = process.argv[2] || 'http://127.0.0.1:8899';
// Matches tests/project-harness.py. Not a secret, and not a production token.
const TOKEN = 'harness-token-not-a-secret';

let pass = 0, fail = 0;
const rec = (name, ok, detail = '') => {
  (ok ? pass++ : fail++);
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  -- ' + detail : ''}`);
};

const b = await chromium.launch({ channel: 'chrome' });
const p = await b.newPage();

// Only uncaught exceptions count. This run deliberately provokes three error statuses that
// the page handles and displays: 401 (no token yet), 403 (the denylist refusing the
// corpus) and 503 (no chat model wired into the draft endpoint). Each has its own
// assertion below proving the page showed the reason. Chrome logs every failed fetch to
// the console regardless, so those are not evidence of a bug; anything else still counts.
const errors = [];
p.on('console', m => {
  if (m.type() !== 'error') return;
  const t = m.text();
  if (/Failed to load resource/.test(t) && /\b(401|403|503)\b/.test(t)) return;
  errors.push(t);
});
p.on('pageerror', e => errors.push('uncaught: ' + String(e)));

await p.goto(`${BASE}/project.html`, { waitUntil: 'networkidle' });

await p.waitForSelector('#pj-gate:not([hidden])', { timeout: 5000 });
rec('gate shown when no token is held',
    await p.isVisible('#pj-tok'), await p.textContent('#pj-gate b'));
rec('the workspace stays hidden behind the gate', !(await p.isVisible('#pj-app')));

await p.fill('#pj-tok', TOKEN);
await p.click('#pj-tok-save');
await p.waitForSelector('#pj-app:not([hidden])', { timeout: 5000 });
rec('token unlocks the surface', await p.isVisible('#pj-app'));

await p.fill('#pj-proj-name', 'Going online');
await p.click('#pj-proj-form button[type=submit]');
await p.waitForFunction(
  () => document.getElementById('pj-title').textContent === 'Going online', null,
  { timeout: 5000 });
rec('creating a workspace opens it', true, await p.textContent('#pj-title'));

await p.fill('#pj-item-title', 'Ship the project page');
await p.click('#pj-item-form button[type=submit]');
await p.waitForSelector('.pj-item-title', { timeout: 5000 });
rec('work item renders after adding',
    (await p.textContent('.pj-item-title')) === 'Ship the project page');

// Exercises the optimistic-concurrency path: the PATCH carries if_version.
await p.selectOption('.pj-item select', 'doing');
await p.waitForTimeout(600);
await p.reload({ waitUntil: 'networkidle' });
await p.waitForSelector('.pj-item select', { timeout: 5000 });
rec('state change persists across a reload',
    (await p.inputValue('.pj-item select')) === 'doing');

await p.fill('#pj-file-path', 'backend/apps/project/README.md');
await p.click('#pj-file-form button[type=submit]');
await p.waitForSelector('.pj-path', { timeout: 5000 });
rec('file reference renders with a live stat',
    (await p.textContent('.pj-path')).includes('README.md'));

// `.claude/CLAUDE.md`: the corpus is trade secret and must never be served or quoted. The
// store's denylist matches on the RESOLVED path; this asserts the refusal reaches the UI
// and that the path never appears in the rendered list.
await p.fill('#pj-file-path', 'training/corpus.jsonl');
await p.click('#pj-file-form button[type=submit]');
await p.waitForTimeout(800);
const denyErr = (await p.textContent('#pj-compose-err')) || '';
const paths = await p.$$eval('.pj-path', els => els.map(e => e.textContent));
rec('the training corpus is refused and never listed',
    denyErr.length > 0 && !paths.some(t => t.includes('corpus.jsonl')),
    denyErr.slice(0, 80));

await p.fill('#pj-note', 'Built the page against the existing API.');
await p.click('#pj-record');
await p.waitForSelector('.pj-ev-text', { timeout: 5000 });
rec('history entry renders',
    (await p.textContent('.pj-ev-text')).includes('Built the page'));

await p.fill('#pj-q', 'page');
await p.click('#pj-search-form button[type=submit]');
await p.waitForTimeout(900);
const results = await p.$$eval('#pj-results li', els => els.length);
rec('search returns results', results > 0, `${results} rows`);

// A surface with no model wired must say so. An empty panel would read as "the model had
// nothing to say", which is the quiet lie this site exists to avoid.
await p.fill('#pj-note', 'turn this into tasks');
await p.click('#pj-draft-items');
await p.waitForTimeout(900);
const draftTxt = (await p.textContent('#pj-draft')) || '';
rec('no-model draft reports why rather than failing silently',
    /no model|not wired|chat surface/i.test(draftTxt), draftTxt.trim().slice(0, 90));

// The reading must agree with what is listed, not merely contain a digit -- the panel is
// re-read from the store after every change, so a mismatch means it went stale.
const shownProjects = await p.$$eval('#pj-projects .pj-proj', els => els.length);
const readWorkspaces = await p.$$eval('#pj-readings li', els => {
  for (const li of els) {
    if (/Workspaces/.test(li.textContent)) {
      return parseInt(li.querySelector('b').textContent, 10);
    }
  }
  return -1;
});
rec('readings agree with the workspaces listed',
    readWorkspaces === shownProjects && shownProjects > 0,
    `reading=${readWorkspaces} listed=${shownProjects}`);

// This page shipped with all ten asset links bare, because `tools/build_project.py` borrows
// `SHELL` from `build_pages` and that emits plain `href="/symoneural.css"` --
// `tools/build_cachebust.py` adds the stamps and has to run last. Nothing downstream catches
// it: `scripts/deploy.sh` strips `?v=` before resolving references, so a destamped page
// deploys quietly and green, and the Caddyfile then lets a visitor hold the old stylesheet
// for a week against new markup. The equivalent assertion in `tests/frontend.mjs` only ever
// examines the page it happens to have loaded, so it never covered this one.
const unstamped = await p.$$eval(
  'link[rel=stylesheet][href^="/"], script[src^="/"]',
  els => els.map(e => e.getAttribute('href') || e.getAttribute('src'))
           .filter(u => !/\?v=[0-9a-f]{6,}$/.test(u)));
rec('every local asset on this page is cache-busted', unstamped.length === 0,
    unstamped.join(', ') || 'all stamped');

// `.claude/CLAUDE.md`: every ellipsis rule has been removed sitewide and none may come
// back. text-overflow on a detail line is data loss with extra steps.
const ell = await p.evaluate(() => {
  let n = 0;
  for (const el of document.querySelectorAll('*')) {
    if (getComputedStyle(el).textOverflow === 'ellipsis') n++;
  }
  return n;
});
rec('no ellipsis rule clips a detail line', ell === 0, `${ell} found`);

await p.setViewportSize({ width: 390, height: 800 });
await p.waitForTimeout(400);
const ovf = await p.evaluate(() =>
  document.documentElement.scrollWidth - document.documentElement.clientWidth);
rec('no horizontal overflow at 390px', ovf <= 1, `${ovf}px`);

rec('no uncaught JavaScript errors', errors.length === 0, errors.slice(0, 2).join(' | '));

console.log(`\n${pass}/${pass + fail} passed`);
await b.close();
process.exit(fail ? 1 : 0);
