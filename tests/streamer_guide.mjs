// The floating guide prompt, driven in real Chrome against the REAL SyMoNeuRaL Guide
// route -- not a stub. The whole point of the panel is that asking a question re-ticks
// the subcategory grid, so every assertion here is about the grid's state afterwards.
//
// Self-contained: it starts one throwaway API process carrying the guide router plus the
// site as static files (one origin, exactly as api.py serves it), and a scripted playlist
// endpoint so no provider account is needed.
import { chromium } from '../contrib/llama.cpp/tools/ui/node_modules/playwright/index.mjs';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'sym-guide-'));
const PORT = Number(process.argv[2] || 8981);

// A playlist with two adult groups spelled differently, a film whose URL cannot be
// classified, and two ordinary channels. Every defect this page has had lives in here.
const CHANNELS = [
  { name: 'BBC One HD', group: 'UK | ENTERTAINMENT', kind: 'live', url: 'http://x.invalid/live/1.ts' },
  { name: 'Sky Sports F1', group: 'UK | SPORTS', kind: 'live', url: 'http://x.invalid/live/2.ts' },
  { name: 'Sky Sports Main Event', group: 'UK | SPORTS', kind: 'live', url: 'http://x.invalid/live/3.ts' },
  { name: 'The Godfather (1972)', group: 'VOD | Movies', kind: 'live', url: 'http://x.invalid/9.mp4' },
  { name: 'Private XXX 1', group: 'XXX ADULT', kind: 'live', url: 'http://x.invalid/10.mp4' },
  { name: 'Hot 18+ Channel', group: '18+ FOR ADULTS', kind: 'live', url: 'http://x.invalid/11.mp4' },
  { name: 'Shop Direct', group: 'UK | SHOPPING', kind: 'live', url: 'http://x.invalid/live/4.ts' },
];

fs.writeFileSync(path.join(TMP, 'app.py'), `
import sys
sys.path.insert(0, ${JSON.stringify(path.join(ROOT, 'backend', 'apps'))})
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from guide import routes as guide_routes

CHANNELS = ${JSON.stringify(CHANNELS)}

app = FastAPI()
app.include_router(guide_routes.router, prefix="/api/guide")

@app.post("/api/streamer/playlist")
async def playlist(body: dict | None = None):
    groups = []
    for c in CHANNELS:
        if c["group"] not in groups:
            groups.append(c["group"])
    return {"source": "pasted", "count": len(CHANNELS), "truncated": False,
            "limit": 10000, "groups": groups, "channels": CHANNELS}

app.mount("/", StaticFiles(directory=${JSON.stringify(path.join(ROOT, 'site'))}, html=True), name="site")
`);

const srv = spawn('python3', ['-m', 'uvicorn', 'app:app', '--port', String(PORT),
                              '--log-level', 'warning'],
                  { cwd: TMP, stdio: 'ignore' });
const stop = () => { try { srv.kill(); } catch {} fs.rmSync(TMP, { recursive: true, force: true }); };
process.on('exit', stop);
for (let i = 0; i < 60; i++) {
  await new Promise(r => setTimeout(r, 400));
  try { if ((await fetch(`http://127.0.0.1:${PORT}/api/guide/state`)).ok) break; } catch {}
}

let pass = 0, fail = 0;
const ok = (n, c, got) => { c ? (pass++, console.log(`PASS  ${n}`))
                              : (fail++, console.log(`FAIL  ${n}\n      got: ${JSON.stringify(got)}`)); };

const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('pageerror', e => errors.push(String(e)));

await page.goto(`http://127.0.0.1:${PORT}/streamer.html`, { waitUntil: 'domcontentloaded' });
await page.fill('#tn-url', 'http://x.invalid/p.m3u');
await page.click('#tn-go');
await page.waitForSelector('li.playable', { timeout: 10000 });

// ---- the prompt appears only once there is something to guide ----------------------
ok('the floating prompt is visible once a playlist is loaded',
   await page.$eval('#tnfg', e => !e.hidden));
const pill = await page.$eval('#tnfgcount', e => e.textContent.trim());
ok('the pill states how many subcategories are ticked', /Guide · \d+ ticked/.test(pill), pill);

await page.click('#tnfgpill');
await page.waitForSelector('#tnfgbody:not([hidden])', { timeout: 5000 });
const ctx = await page.$eval('#tnfgctx', e => e.textContent.trim());
ok('it says what it will read and that nothing leaves the box',
   /subcategor/.test(ctx) && /channels/.test(ctx) && /not sent anywhere but this box/.test(ctx), ctx);

// ---- the count follows the ticks ----------------------------------------------------
await page.click('#tngnone');
await page.waitForTimeout(200);
ok('unticking everything is reflected in the prompt',
   /Guide · 0 ticked/.test(await page.$eval('#tnfgcount', e => e.textContent)),
   await page.$eval('#tnfgcount', e => e.textContent));
await page.fill('#tnfgq', 'sports');
await page.click('#tnfggo');
await page.waitForFunction(() => !document.getElementById('tnfgwhy').hidden, { timeout: 8000 });
ok('and asking with nothing ticked says so instead of returning everything',
   /Nothing is ticked/.test(await page.$eval('#tnfgwhy', e => e.textContent)),
   await page.$eval('#tnfgwhy', e => e.textContent));
await page.click('#tngall');
await page.waitForTimeout(200);

// ---- the real ask -------------------------------------------------------------------
await page.fill('#tnfgq', 'adult');
await page.click('#tnfggo');
await page.waitForFunction(
  () => /channel/.test(document.getElementById('tnfgwhy').textContent), { timeout: 15000 });
const why = await page.$eval('#tnfgwhy', e => e.textContent.trim());
ok('Guide answers with a channel count', /^\d+ channels?\./.test(why), why);
ok('and BOTH adult groups are found, not just the first', /^2 channels\./.test(why), why);
ok('the answer carries Guide\'s own account of how it matched',
   /playlist's own categories|no model/.test(why), why);
ok('the re-tick button appears only when there are groups to apply',
   await page.$eval('#tnfgapplyrow', e => !e.hidden));

// ---- the outcome is the guide, not a transcript --------------------------------------
await page.click('#tnfgapply');
await page.waitForTimeout(300);
const ticked = await page.$$eval('#tngrid .tn-gcell',
  els => els.filter(e => e.querySelector('input').checked)
            .map(e => e.querySelector('.tn-gname').textContent.trim()));
ok('the grid is re-ticked to exactly the groups Guide returned',
   ticked.length === 2 && ticked.every(t => /ADULT/i.test(t)), ticked);
const saved = await page.$eval('#tnfgsaved', e => e.textContent.trim());
ok('and it says plainly that nothing was removed from the playlist',
   /Nothing was removed from your playlist/.test(saved), saved);

// ---- saving is local only -------------------------------------------------------------
await page.click('#tnfgsave');
await page.waitForTimeout(200);
const store = await page.evaluate(() => localStorage.getItem('symoneural.streamer.guide'));
ok('the saved guide is written to this browser only', store && store.includes('ADULT'), store);

// ---- house rules ----------------------------------------------------------------------
const ell = await page.$$eval('#tnfg, #tnfg *',
  els => els.filter(e => getComputedStyle(e).textOverflow === 'ellipsis').length);
ok('no text-overflow:ellipsis anywhere in the prompt', ell === 0, ell);
for (const [w, h] of [[1440, 900], [1301, 740], [390, 800]]) {
  await page.setViewportSize({ width: w, height: h });
  await page.waitForTimeout(200);
  const ov = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  ok(`the fixed panel causes no horizontal overflow at ${w}px`, ov <= 0, ov);
}
ok('no uncaught page errors', errors.length === 0, errors);

await browser.close();
stop();
console.log(`\n${pass}/${pass + fail} passed`);
process.exit(fail ? 1 : 0);
