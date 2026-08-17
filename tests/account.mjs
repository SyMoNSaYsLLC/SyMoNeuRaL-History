// Drive site/account.html in real Chrome against the real accounts router.
// Asserts on what the page SHOWS -- the page has three states and each one is a claim
// about this box that has to be true.
//
// Self-contained: it starts TWO throwaway API processes -- one with a session secret and
// one without -- because "accounts are closed on this box" is a state the page must get
// right and is the state production is actually in. Neither touches run/accounts.
import { chromium } from '../contrib/llama.cpp/tools/ui/node_modules/playwright/index.mjs';
import { spawn, execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'sym-acct-'));
fs.writeFileSync(path.join(TMP, 'acct_app.py'), `
import sys
sys.path.insert(0, ${JSON.stringify(path.join(ROOT, 'backend', 'apps'))})
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from accounts import routes
app = FastAPI()
app.include_router(routes.router, prefix="/api/accounts")
app.mount("/", StaticFiles(directory=${JSON.stringify(path.join(ROOT, 'site'))}, html=True), name="site")
`);

const P_ON = Number(process.argv[2] || 8962), P_OFF = Number(process.argv[3] || 8963);
const secret = execSync('openssl rand -base64 48').toString().trim();
const procs = [
  spawn('python3', ['-m', 'uvicorn', 'acct_app:app', '--port', String(P_ON), '--log-level', 'warning'],
        { cwd: TMP, stdio: 'ignore',
          env: { ...process.env, SYM_ACCOUNTS_ENABLED: '1', SYM_SESSION_SECRET: secret,
                 SYM_ACCOUNTS_DB: path.join(TMP, 'a.db') } }),
  spawn('python3', ['-m', 'uvicorn', 'acct_app:app', '--port', String(P_OFF), '--log-level', 'warning'],
        { cwd: TMP, stdio: 'ignore',
          env: { ...process.env, SYM_ACCOUNTS_ENABLED: '', SYM_SESSION_SECRET: '',
                 SYM_ACCOUNTS_DB: path.join(TMP, 'b.db') } }),
];
const stop = () => { procs.forEach(p => { try { p.kill(); } catch {} });
                     fs.rmSync(TMP, { recursive: true, force: true }); };
process.on('exit', stop);
for (let i = 0; i < 60; i++) {
  await new Promise(r => setTimeout(r, 400));
  try {
    const a = await fetch(`http://127.0.0.1:${P_ON}/api/accounts/status`);
    const b = await fetch(`http://127.0.0.1:${P_OFF}/api/accounts/status`);
    if (a.ok && b.ok) break;
  } catch {}
}

const ON = `http://127.0.0.1:${P_ON}`;    // accounts enabled
const OFF = `http://127.0.0.1:${P_OFF}`;  // accounts not configured
let pass = 0, fail = 0;
const ok = (n, c, got) => { c ? (pass++, console.log(`PASS  ${n}`))
                              : (fail++, console.log(`FAIL  ${n}\n      got: ${JSON.stringify(got)}`)); };

const browser = await chromium.launch({ channel: 'chrome' });
const errors = [];

// ---- closed box: the honest "not open" state ---------------------------------------
let page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on('pageerror', e => errors.push('OFF ' + e));
await page.goto(`${OFF}/account.html`, { waitUntil: 'networkidle' });
let state = await page.$eval('#ac-state', e => e.textContent.trim());
let h1 = await page.$eval('#ac-h1', e => e.textContent.trim());
let formVisible = await page.$eval('#ac-form', e => !e.hidden);
ok('a box with no session secret reports "closed"', state === 'closed', state);
ok('and does not show a sign-in form it cannot honour', formVisible === false, formVisible);
ok('the headline says it is not open', /not open/i.test(h1), h1);
const note = await page.$eval('#ac-msg', e => e.textContent.trim());
ok('and it names what is missing rather than just refusing',
   /session secret/i.test(note), note);
await page.close();

// ---- open box: signup, signed-in, sign out -----------------------------------------
page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on('pageerror', e => errors.push('ON ' + e));
await page.goto(`${ON}/account.html`, { waitUntil: 'networkidle' });
state = await page.$eval('#ac-state', e => e.textContent.trim());
ok('an enabled box reports "not signed in"', state === 'not signed in', state);

// weak password must be refused with the SERVER's sentence, not a generic one
await page.click('#ac-toggle');
const email = `browser${Date.now()}@symoneural.com`;
await page.fill('#ac-email', email);
await page.fill('#ac-pw', 'short');
await page.click('#ac-submit');
await page.waitForFunction(() => !document.getElementById('ac-msg').hidden, { timeout: 8000 });
let m = await page.$eval('#ac-msg', e => e.textContent.trim());
ok('a weak password is refused in the server\'s own words',
   /at least 12 characters/i.test(m), m);

await page.fill('#ac-pw', 'a-properly-long-passphrase-2718');
await page.click('#ac-submit');
await page.waitForFunction(() => !document.getElementById('ac-in').hidden, { timeout: 15000 });
ok('signing up lands on the signed-in view',
   (await page.$eval('#ac-state', e => e.textContent.trim())) === 'signed in');
ok('the signed-in view shows the address that was registered',
   (await page.$eval('#ac-who', e => e.textContent.trim())) === email.toLowerCase());
await page.waitForFunction(() => /session/.test(document.getElementById('ac-sess').textContent),
                           { timeout: 8000 });
ok('and a real session count read from the server',
   /1 session/.test(await page.$eval('#ac-sess', e => e.textContent.trim())));

// the session token must not be reachable from script
const cookieVisible = await page.evaluate(() => document.cookie.includes('sym_session'));
ok('the session cookie is HttpOnly and invisible to page script', cookieVisible === false);

await page.click('#ac-out');
await page.waitForFunction(() => !document.getElementById('ac-form').hidden, { timeout: 8000 });
ok('signing out returns to the form',
   (await page.$eval('#ac-state', e => e.textContent.trim())) === 'not signed in');

// sign back in with the same credentials
await page.fill('#ac-email', email);
await page.fill('#ac-pw', 'a-properly-long-passphrase-2718');
await page.click('#ac-submit');
await page.waitForFunction(() => !document.getElementById('ac-in').hidden, { timeout: 15000 });
ok('and the account can be signed into again',
   (await page.$eval('#ac-who', e => e.textContent.trim())) === email.toLowerCase());

// ---- house rules --------------------------------------------------------------------
const ell = await page.$$eval('#acct, #acct *',
  els => els.filter(e => getComputedStyle(e).textOverflow === 'ellipsis').length);
ok('no text-overflow:ellipsis anywhere in the account panel', ell === 0, ell);
for (const w of [1440, 1301, 390]) {
  await page.setViewportSize({ width: w, height: 800 });
  await page.waitForTimeout(150);
  const ov = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  ok(`no horizontal overflow at ${w}px`, ov <= 0, ov);
}
ok('no uncaught page errors', errors.length === 0, errors);

await browser.close();
stop();
console.log(`\n${pass}/${pass + fail} passed`);
process.exit(fail ? 1 : 0);
