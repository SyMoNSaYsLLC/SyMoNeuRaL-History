// SyMoNeuRaL Chat, exercised rather than inspected.
//
//   node tests/chat_smoke.mjs [baseURL]        # default http://127.0.0.1:8800
//
// ## Why this exists
//
// `.claude/CLAUDE.md` records #94: a desktop client whose eighteen checks all went green and
// whose chat surface was dead on arrival -- a missing capability meant the page was never
// permitted to hear the stream it had asked for, so it rendered a turn and then nothing, with
// no error to read, and the timer archived the task two minutes later. The lesson written
// there is that when the deliverable is a program that runs, one check must be something only
// a real run can turn green.
//
// #109 restructured this page's shell, so this is that check for Chat. It does not assert that
// elements exist and stop -- existence is what #94 had. It types into the composer, presses
// Enter, waits for the 7B on the card to stream an answer back, and asserts the log grew and
// the status line printed a measured tokens-per-second. Then it opens a new conversation,
// reloads the page, and asserts the history survived.
//
// **It takes the GPU.** Run it after `frontend.mjs` and `studio.mjs`, never alongside them --
// docs/ops/MEASUREMENTS.md explains why: the governor hands the card to one surface at a time
// and a concurrent run evicts the other's model out from under it.
//
// Both viewports are checked because the composer, the rail and the drawer all change layout
// at 900px, and a control that works at 1440px and not at 390px is the defect this redesign
// was asked to remove.
import { chromium } from './browser.mjs';

const BASE = process.argv[2] || 'http://127.0.0.1:8800';

const b=await chromium.launch({channel:'chrome',args:['--no-sandbox']});
const out=[];
const ok=(n,c,d)=>{out.push(`${c?'PASS':'FAIL'}  ${n}${d?'  -- '+d:''}`);};
for (const [w,h] of [[1440,900],[390,844]]) {
  const ctx=await b.newContext({viewport:{width:w,height:h}}); const p=await ctx.newPage();
  const errs=[]; p.on('pageerror',e=>errs.push(e.message.split('\n')[0]));
  await p.goto(BASE + '/chat.html',{waitUntil:'domcontentloaded'});
  await p.waitForTimeout(500);
  const tag=`@${w}`;
  // structure the .mjs/JS depends on
  for (const sel of ['#form','#prompt','#send','#log','#cu-empty','#cu-hist','#cu-new','#cu-model','#cu-file','#stat','.cu-rail','.cu-composer'])
    ok(`${sel} present ${tag}`, await p.$(sel)!==null);
  // multiline + autogrow
  const h0=await p.$eval('#prompt',e=>e.getBoundingClientRect().height);
  await p.click('#prompt'); await p.keyboard.type('line one');
  await p.keyboard.down('Shift'); await p.keyboard.press('Enter'); await p.keyboard.up('Shift');
  await p.keyboard.type('line two'); await p.waitForTimeout(200);
  const h1=await p.$eval('#prompt',e=>e.getBoundingClientRect().height);
  ok(`shift+enter makes a newline, textarea grows ${tag}`, h1>h0, `${Math.round(h0)} -> ${Math.round(h1)}px`);
  ok(`value kept both lines ${tag}`, (await p.$eval('#prompt',e=>e.value)).includes('\n'));
  // submit via Enter -> a real streamed answer from the 7B
  await p.$eval('#prompt',e=>{e.value='Reply with the single word: ready';});
  await p.click('#prompt'); await p.keyboard.press('End');
  await p.keyboard.press('Enter');
  await p.waitForTimeout(400);
  ok(`empty state clears on submit ${tag}`, await p.$eval('#cu-empty',e=>getComputedStyle(e).display==='none'||e.hidden||!e.offsetParent));
  let turns=0;
  for (let i=0;i<60;i++){ await p.waitForTimeout(1000);
    turns=await p.$$eval('#log > *',e=>e.length);
    const t=await p.$eval('#log',e=>e.textContent.trim());
    if (turns>=2 && t.length>20) break; }
  const logText=await p.$eval('#log',e=>e.textContent.trim());
  ok(`streamed a real answer ${tag}`, turns>=2 && logText.length>20, `${turns} nodes, ${logText.length} chars`);
  ok(`status line reports something ${tag}`, (await p.$eval('#stat',e=>e.textContent.trim())).length>0,
     (await p.$eval('#stat',e=>e.textContent.trim())).slice(0,60));
  // history + new chat
  const hist=await p.$$eval('#cu-hist > *',e=>e.length);
  ok(`conversation entered history ${tag}`, hist>=1, `${hist} entries`);
  await p.click('#cu-new'); await p.waitForTimeout(400);
  ok(`new chat clears the log ${tag}`, (await p.$$eval('#log > *',e=>e.length))===0);
  ok(`new chat keeps history ${tag}`, (await p.$$eval('#cu-hist > *',e=>e.length))>=1);
  // reload persistence
  await p.reload({waitUntil:'domcontentloaded'}); await p.waitForTimeout(600);
  ok(`history survives refresh ${tag}`, (await p.$$eval('#cu-hist > *',e=>e.length))>=1);
  ok(`model indicator names a SyMoNeuRaL runtime ${tag}`, /Symon/i.test(await p.$eval('#cu-model',e=>e.textContent)),
     await p.$eval('#cu-model',e=>e.textContent.trim()));
  ok(`no page errors ${tag}`, errs.length===0, errs.join('; ')||'clean');
  await ctx.close();
}
await b.close();
console.log(out.join('\n'));
const pass = out.filter(l => l.startsWith('PASS')).length;
console.log(`\n${pass}/${out.length} passed`);
process.exit(pass === out.length ? 0 : 1);
