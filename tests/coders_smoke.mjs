// Real provider/browser smoke, followed by explicitly labeled UI failure fixtures.
// Use a scratch API with lifespan disabled; never restart production from this test.
import {chromium} from './browser.mjs';
import {writeFileSync, mkdirSync} from 'node:fs';
const BASE = process.env.CODERS_BASE || 'http://127.0.0.1:8898';
const EVIDENCE = process.env.CODERS_EVIDENCE_DIR;
let failures = 0;
function check(name, ok) { console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); if (!ok) failures++; }
function save(name, data) { if (EVIDENCE) { mkdirSync(EVIDENCE,{recursive:true}); writeFileSync(`${EVIDENCE}/${name}`,JSON.stringify(data,null,2)); } }
const browser = await chromium.launch({executablePath:process.env.CHROMIUM_EXE || '/usr/bin/chromium-headless-shell'});
const page = await browser.newPage();
page.setDefaultTimeout(160000);
async function submit(prompt) {
  await page.fill('#prompt',prompt);
  const pending = page.waitForResponse(r => r.url() === BASE+'/local/coders/ask' && r.request().method() === 'POST');
  await page.click('#go');
  const r = await pending;
  const data = await r.json();
  await page.waitForFunction(id => location.hash === '#'+id,data.session_id);
  await page.waitForFunction(() => !document.getElementById('go').disabled);
  return data;
}
try {
  await page.goto(BASE+'/coders'); await page.waitForSelector('.preset');
  check('all seven presets render',await page.locator('.preset').count() === 7);
  const disabled = await page.locator('.preset:disabled').evaluateAll(xs => xs.map(x => x.title));
  check('unavailable presets retain reasons',disabled.length === 4 && disabled.every(x => x.length > 10));
  const modes = await page.locator('#modes').innerText();
  check('rotation and training remain unavailable',/rotation: unavailable/.test(modes) && /training: unavailable/.test(modes));
  await page.click('.preset[data-i="3"]');
  const count = await submit('How do you count to 10? Answer with only the numbers, comma separated.');
  save('browser-live-count.json',count);
  check('real Symon and Claude answers complete',count.answers.length === 2 && count.answers.every(a => a.state === 'completed' && a.text));
  check('count outputs agree',count.agree === true);
  check('two attributed answers stay separate',await page.locator('.round .ans').count() === 2);
  const initial = await submit('Recommend one sorting algorithm for ten integers and explain why in one short sentence.');
  save('browser-live-initial.json',initial);
  check('comparison does not choose for the user',initial.decision === '');
  check('each completed coder has a selectable proposal',await page.locator('[data-pick]').count() === initial.answers.filter(a => a.state === 'completed').length);
  await page.fill('#clarification','Compare the other coder’s recommendation with your own. Explain whether you hold or revise your answer. Keep your reply under 80 words.');
  const waitRound = page.waitForResponse(r => r.url().endsWith('/debate') && r.request().method() === 'POST');
  await page.click('#debate');
  const result = await waitRound; const d = await result.json(); save('browser-live-debate.json',d);
  await page.waitForSelector('[data-round="1"]'); await page.waitForFunction(() => !document.getElementById('go').disabled);
  check('real discussion round completes with both providers',d.rounds.length === 1 && d.rounds[0].answers.length === 2 && d.rounds[0].answers.every(a => a.state === 'completed' && a.text));
  check('shared prompt contains both original positions',initial.answers.every(a => d.rounds[0].prompt.includes(a.text)));
  check('initial and discussion replies all remain visible',await page.locator('.round .ans').count() === 4);
  check('discussion does not automatically select',d.decision === '');
  const stale = await page.request.post(BASE+'/local/coders/session/'+d.session_id+'/debate',{data:{clarification:'stale duplicate',expected_round:0}});
  check('stale discussion submission refused',stale.status() === 409);
  const waitPick = page.waitForResponse(r => r.url().endsWith('/decide'));
  await page.click('[data-pick="claude"]'); const picked = await (await waitPick).json();
  await page.waitForSelector('#decision');
  check('user click records the chosen round',picked.decision === 'claude' && picked.decisions.at(-1).round_number === 1);
  await page.reload(); await page.waitForSelector('[data-round="1"]');
  check('refresh recovers discussion and choice',await page.locator('.round .ans').count() === 4 && /claude/.test(await page.locator('#decision').innerText()));
  if (EVIDENCE) await page.screenshot({path:EVIDENCE+'/debate-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  check('mobile page has no horizontal overflow',await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  if (EVIDENCE) await page.screenshot({path:EVIDENCE+'/debate-mobile.png',fullPage:true});
  // UI fixture: deliberate disagreement + failed third provider. No real provider call.
  const fixture = {session_id:'1234567890abcdef',prompt:'LABELED failure fixture',coder_ids:['symon','claude','codex'],fixture:true,state:'done',round_number:0,rounds:[],decisions:[],decision:'',agree:false,
    debate:{available:false,max_rounds:3,remaining:0},answers:[{coder_id:'symon',display:'Symon',state:'completed',text:'Option A'},{coder_id:'claude',display:'Claude',state:'completed',text:'Option B'},{coder_id:'codex',display:'Codex',state:'timed_out',error:'Labeled timeout fixture'}]};
  await page.route('**/local/coders/ask',route => route.fulfill({json:fixture}));
  await page.click('.preset[data-i="3"]'); await submit(fixture.prompt);
  check('fixture disagreement retains all participants',await page.locator('.round .ans').count() === 3 && await page.locator('[data-pick]').count() === 2);
  check('timeout remains visible and fixture is labeled',/Labeled timeout fixture/.test(await page.locator('#out').innerText()) && /Labeled test fixture/.test(await page.locator('#out').innerText()));
  check('machine preselects no fixture winner',await page.locator('#decision').count() === 0);
  check('bounded limit is visible',/Discussion limit reached/.test(await page.locator('#out').innerText()));
  await page.unroute('**/local/coders/ask');
} catch(e) { failures++; console.error(e); }
finally { await browser.close(); }
console.log(failures ? `${failures} FAILED` : 'all browser checks passed');
process.exit(failures ? 1 : 0);
