#!/usr/bin/env python3
"""Generate the surface pages into site/.

Four pages that differ only in their middle. Generating them from one shell means the
header, banner, nav and footer cannot drift apart, which is the failure mode when five
static pages are maintained by hand and someone edits four of them.

The pages are plain HTML with a little inline JS and no build step, no framework and no
external request -- everything a visitor loads comes off this box.
"""
from __future__ import annotations

import pathlib

SITE = pathlib.Path(__file__).resolve().parent / "site"

NAV = """    <nav>
      <a class="navlink" href="/">Live stack</a>
      <div class="navitem has-menu">
        <button class="navlink" aria-expanded="false" aria-haspopup="true">Documentation <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></button>
        <div class="menu">
          <a href="/documentation.html#cost">Owned vs Rented<small>a $1,000 card vs a rented 48 GB server</small></a>
          <a href="/documentation.html#stack">Inference Architecture<small>mapped onto the NVIDIA stack</small></a>
          <a href="/documentation.html#hardware">Hardware<small>the card, measured</small></a>
          <a href="/documentation.html#interconnect">Interconnect<small>PCIe Gen 3 x8, host capped</small></a>
          <a href="/documentation.html#kernels">Kernels<small>occupancy, atomics, graph replay</small></a>
          <a href="/documentation.html#inference">Inference<small>decode rates and batching</small></a>
          <a href="/documentation.html#architecture">Architecture<small>how the surfaces fit together</small></a>
          <a href="/documentation.html#environment">Environment<small>the 7-package base and its isolates</small></a>
        </div>
      </div>
      <a class="navlink" href="/training.html">Manuals</a>
      <a class="navlink" href="/docs">API</a>
      <div class="navitem has-menu">
        <button class="navlink" aria-expanded="false" aria-haspopup="true">Account <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></button>
        <div class="menu">
          <a href="/account.html">Subscription<small>not open yet</small></a>
          <a href="/account.html#billing">Billing<small>not open yet</small></a>
          <a href="/account.html#support">Support<small>talk to a person</small></a>
        </div>
      </div>
      <a class="cta ghost" href="mailto:symonsayadmin@symoneural.com">Contact</a>
    </nav>"""

SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>@@TITLE@@</title>
<meta name="description" content="@@DESC@@">
<link rel="stylesheet" href="/symoneural.css">
<link rel="stylesheet" href="/rack-detail.css">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/favicon-16.png" sizes="16x16" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0e100f">
</head>
<body>

<div class="status">
  <div class="wrap">
    <b><s></s>Under Construction</b>
    <span>Active infrastructure development in progress. Every surface on this site runs
    live on one consumer GPU in production &mdash; be kind to it.</span>
  </div>
</div>

<header>
  <div class="wrap bar">
    <a class="logo" href="/">
      <img src="/mark-64.png" srcset="/mark-32.png 1x, /mark-64.png 2x" alt="SyMoNeuRaL" width="30" height="30">
      <b>SyMoNeu<i>RaL</i></b>
    </a>
@@NAV@@
  </div>
</header>

<div class="hero" style="padding:56px 0 26px">
  <div class="wrap">
    <p class="eyebrow"><img src="@@ICON@@" alt="" width="20" height="20"
       style="display:inline-block;vertical-align:-4px;margin-right:8px">@@EYEBROW@@</p>
    <h1 style="font-size:clamp(28px,3.6vw,40px);max-width:24ch">@@HEADING@@</h1>
    <p class="lede" style="font-size:16.5px">@@LEDE@@</p>
  </div>
</div>

<section style="border-top:0;padding-top:0">
  <div class="wrap">
@@BODY@@

    <div class="callout" style="margin-top:34px">
      <h3>This is a 16 GB consumer card, and it is a test bench</h3>
      <p>
        Chat and image never run at the same time here. A lock hands the GPU to exactly one
        surface and the other waits, because both weight sets do not fit in 15.92&nbsp;GiB at
        once &mdash; and when they swap, we wait for the driver to actually hand the memory
        back before the next one starts. If you are queued behind someone, that is not a bug;
        it is one card doing one thing at a time.
      </p>
      <p>
        <strong>RavenCalc is the exception</strong> &mdash; it is SymPy on the CPU, so it never
        touches the GPU and never queues. Everything here is a demonstration of the stack on
        the smallest machine we would ever ship, not a statement of capacity. A server we spec
        for you would not be sharing one GPU with itself.
      </p>
    </div>
  </div>
</section>

<footer>
  <div class="wrap foot">
    <a class="logo" href="/" style="text-decoration:none;display:flex;align-items:center;gap:10px">
      <img src="/mark-32.png" alt="" width="22" height="22">
      <b style="font-size:14.5px;color:var(--fg)">SyMoNeu<i style="font-style:normal;color:var(--accent)">RaL</i></b>
    </a>
    <span>&copy; SymonSays LLC &middot; <a href="mailto:symonsayadmin@symoneural.com"
      style="color:var(--dim);text-decoration:none">symonsayadmin@symoneural.com</a></span>
    <nav>
      <a href="/">Home</a>
      <a href="/training.html">Training</a>
      <a href="/#hardware">Hardware</a>
      <a href="/#inference">Inference</a>
    </nav>
  </div>
</footer>

<script>
// Shared helpers. Every bound below is also enforced on the server -- these exist to make
// the UI honest about the limits, not to be the limits.
const $ = (s, r=document) => r.querySelector(s);
function status(el, text, busy) {
  const dot = $('s', el); if (dot) dot.className = busy ? 'busy' : 'on';
  const grow = $('.grow', el); if (grow) grow.textContent = text;
}
async function api(path, payload) {
  const r = await fetch(path, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const body = await r.json().catch(() => ({error: 'Unreadable response.'}));
  if (!r.ok) throw new Error(body.error || ('HTTP ' + r.status));
  return body;
}
</script>
<script src="/console.js" defer></script>
<script src="/ui.js" defer></script>
@@SCRIPT@@
</body>
</html>
"""


def page(name: str, **kw) -> None:
    html = SHELL.replace("@@NAV@@", NAV)
    for key, value in kw.items():
        html = html.replace(f"@@{key.upper()}@@", value)
    (SITE / name).write_text(html)
    print(f"  {name}")


# ---------------------------------------------------------------- chat
CHAT_BODY = """    <div class="pgwrap">
      <div class="stage">
        <div class="head" id="chead"><s></s>SyMoNeuRaL Chat
          <span class="grow">idle</span></div>
        <div class="body" id="log">
          <div class="turn bot">
            <div class="who">SyMoNeuRaL</div>
            <div class="msg">Ask me about this machine, what we build, or local AI engineering \
generally. I run on the RTX 5070 Ti described on the home page &mdash; nothing you type here \
leaves the box.</div>
          </div>
        </div>
        <form class="composer" id="form">
          <textarea id="prompt" rows="1" maxlength="1200" placeholder="Why is decode memory-bandwidth bound?"></textarea>
          <button class="cta" id="send" type="submit">Send</button>
        </form>
      </div>

      <aside class="panel">
        <h3>Parameters</h3>
        <div class="ctl">
          <label for="temp">Temperature <b id="tempv">0.7</b></label>
          <input type="range" id="temp" min="0" max="1.5" step="0.05" value="0.7">
        </div>
        <div class="ctl">
          <label for="toks">Max tokens <b id="toksv">320</b></label>
          <input type="range" id="toks" min="16" max="512" step="16" value="320">
        </div>
        <p class="hint">
          Low temperature keeps it factual; high makes it wander. Both are clamped server-side
          &mdash; the sliders describe the range, they do not define it.
        </p>
        <p class="hint" id="stat">&nbsp;</p>
      </aside>
    </div>"""

CHAT_JS = """<script>
const log = $('#log'), form = $('#form'), promptEl = $('#prompt'), send = $('#send');
const head = $('#chead');
for (const [id, out] of [['temp','tempv'],['toks','toksv']])
  $('#'+id).addEventListener('input', e => $('#'+out).textContent = e.target.value);

promptEl.addEventListener('input', () => {
  promptEl.style.height = 'auto';
  promptEl.style.height = Math.min(150, promptEl.scrollHeight) + 'px';
});
promptEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});

function turn(who, cls) {
  const d = document.createElement('div');
  d.className = 'turn ' + cls;
  d.innerHTML = '<div class="who"></div><div class="msg"></div>';
  $('.who', d).textContent = who;
  log.appendChild(d); log.scrollTop = log.scrollHeight;
  return d;
}

form.addEventListener('submit', async e => {
  e.preventDefault();
  const text = promptEl.value.trim();
  if (!text) return;
  promptEl.value = ''; promptEl.style.height = 'auto';
  send.disabled = true;
  turn('You', 'you').querySelector('.msg').textContent = text;

  const bot = turn('SyMoNeuRaL', 'bot');
  const msg = $('.msg', bot);
  msg.innerHTML = '<span class="caret"></span>';
  status(head, 'generating', true);

  try {
    const r = await fetch('/api/chat', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        prompt: text,
        temperature: parseFloat($('#temp').value),
        max_tokens: parseInt($('#toks').value, 10)
      })
    });
    if (!r.ok) {
      const b = await r.json().catch(() => ({}));
      throw new Error(b.error || ('HTTP ' + r.status));
    }
    // The stream is the point: tokens land as the card produces them.
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = '', out = '';
    for (;;) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream:true});
      const lines = buf.split('\\n\\n'); buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        const ev = JSON.parse(line.slice(5));
        if (ev.delta) { out += ev.delta; msg.innerHTML = ''; msg.append(out);
          msg.insertAdjacentHTML('beforeend', '<span class="caret"></span>');
          log.scrollTop = log.scrollHeight; }
        if (ev.assist) {
          // RavenCalc got there first. Show its exact result above the model's answer --
          // the point is that the algebra was computed, not predicted.
          const a = ev.assist, c = a.check || {};
          const box = document.createElement('div');
          box.className = 'assist';
          box.innerHTML =
            '<div class="who">RavenCalc &middot; answered before the model loaded</div>' +
            '<div class="rows"></div>';
          const rows = $('.rows', box);
          const add = (k, v, cls) => {
            const d = document.createElement('div');
            d.innerHTML = '<span class="k"></span><span class="' + (cls||'v') + '"></span>';
            d.querySelector('.k').textContent = k;
            d.querySelector('span:last-child').textContent = v;
            rows.appendChild(d);
          };
          add('in',  a.input);
          add('out', a.result);
          add('chk', c.passed === true ? 'verified \u2014 ' + (c.how || '')
                   : c.performed ? 'unconfirmed' : 'not checked',
                   c.passed === true ? 'v' : 'bad');
          add('cpu', a.ms + ' ms, while the GPU was still loading');
          bot.parentNode.insertBefore(box, bot);
        }
        if (ev.done) {
          msg.textContent = out;
          const m = document.createElement('div');
          m.className = 'meta';
          m.textContent = `${ev.tokens} tok \\u00b7 ${ev.seconds}s \\u00b7 ${ev.tok_per_s} tok/s \\u00b7 ${ev.model}` +
                          (ev.adapter ? ' \\u00b7 symoneural adapter' : '');
          bot.appendChild(m);
          $('#stat').textContent = `last: ${ev.tok_per_s} tok/s`;
        }
      }
    }
  } catch (err) {
    msg.innerHTML = '';
    msg.append(err.message);
    msg.style.color = 'var(--amber)';
  } finally {
    send.disabled = false; status(head, 'idle', false);
    log.scrollTop = log.scrollHeight;
  }
});
</script>"""

# ---------------------------------------------------------------- image
IMAGE_BODY = """    <div class="pgwrap">
      <div class="stage">
        <div class="head" id="ihead"><s></s>SyMoNeuRaL Image
          <span class="grow">idle</span></div>
        <div class="body">
          <div class="shots" id="shots">
            <div class="shot" style="grid-column:1/-1;border-style:dashed">
              <div class="cap" style="border-top:0;text-align:center;padding:40px 20px">
                Describe something and press Generate. FLUX.1-schnell, four steps, rendered on
                the card in this machine.
              </div>
            </div>
          </div>
        </div>
        <form class="composer" id="form">
          <input type="text" id="prompt" maxlength="1200"
                 placeholder="a raven perched on a server rack, volumetric light, cinematic">
          <button class="cta" id="send" type="submit">Generate</button>
        </form>
      </div>

      <aside class="panel">
        <h3>Parameters</h3>
        <div class="ctl">
          <label for="steps">Steps <b id="stepsv">4</b></label>
          <input type="range" id="steps" min="4" max="8" step="1" value="4">
        </div>
        <div class="ctl">
          <label>Size</label>
          <div class="seg" id="size">
            <button type="button" data-v="512">512</button>
            <button type="button" data-v="768" aria-pressed="true">768</button>
          </div>
        </div>
        <div class="ctl">
          <label for="seed">Seed <b id="seedlock">random</b></label>
          <input type="number" id="seed" min="0" max="2147483647" placeholder="leave blank for random">
        </div>
        <p class="hint">
          schnell is a distilled model: four steps is what it was trained for, and guidance is
          pinned to 1.0 because raising it degrades this model rather than sharpening it. More
          steps costs time without buying much.
        </p>
        <p class="hint" id="stat">&nbsp;</p>
      </aside>
    </div>"""

IMAGE_JS = """<script>
const form = $('#form'), send = $('#send'), shots = $('#shots'), head = $('#ihead');
let size = 768, first = true;
$('#steps').addEventListener('input', e => $('#stepsv').textContent = e.target.value);
$('#seed').addEventListener('input', e =>
  $('#seedlock').textContent = e.target.value === '' ? 'random' : 'locked');
$('#size').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  size = parseInt(b.dataset.v, 10);
  [...e.currentTarget.children].forEach(x => x.setAttribute('aria-pressed', x === b));
});

form.addEventListener('submit', async e => {
  e.preventDefault();
  const prompt = $('#prompt').value.trim();
  if (!prompt) return;
  send.disabled = true;
  status(head, 'loading the image model \\u2014 chat is being evicted to make room', true);

  const card = document.createElement('div');
  card.className = 'shot';
  card.innerHTML = '<div style="aspect-ratio:1/1;display:grid;place-items:center;' +
                   'background:var(--panel2);color:var(--faint);font-size:13px">rendering\\u2026</div>' +
                   '<div class="cap"></div>';
  $('.cap', card).textContent = prompt;
  if (first) { shots.innerHTML = ''; first = false; }
  shots.prepend(card);

  const t0 = performance.now();
  try {
    const seedRaw = $('#seed').value;
    const r = await api('/api/image', {
      prompt, size,
      steps: parseInt($('#steps').value, 10),
      ...(seedRaw === '' ? {} : {seed: parseInt(seedRaw, 10)})
    });
    card.innerHTML = '';
    const img = document.createElement('img');
    img.src = r.url; img.alt = prompt; img.loading = 'lazy';
    const cap = document.createElement('div');
    cap.className = 'cap';
    // The wall-clock is the point. It is what this card actually took, round trip included.
    cap.textContent = `${prompt}\\n${r.size}\\u00d7${r.size} \\u00b7 ${r.steps} steps \\u00b7 ` +
                      `seed ${r.seed} \\u00b7 ${r.seconds}s on the card \\u00b7 ${r.model}`;
    cap.style.whiteSpace = 'pre-line';
    card.append(img, cap);
    $('#stat').textContent = `last render: ${r.seconds}s`;
  } catch (err) {
    card.innerHTML = '';
    const cap = document.createElement('div');
    cap.className = 'cap'; cap.style.color = 'var(--amber)';
    cap.textContent = err.message;
    card.append(cap);
  } finally {
    send.disabled = false; status(head, 'idle', false);
  }
});
</script>"""

# ---------------------------------------------------------------- calc
CALC_BODY = """    <div class="pgwrap">
      <div class="stage">
        <div class="head" id="rhead"><s class="on"></s>SyMoNeuRaL RavenCalc
          <span class="grow">cpu &middot; never queues</span></div>
        <div class="body">
          <div class="readout" id="out" style="color:var(--faint)">
            Exact symbolic mathematics. Not a language model guessing at algebra &mdash; SymPy
            computing it, and checking its own answer where checking is cheap.
          </div>
        </div>
        <form class="composer" id="form">
          <input type="text" id="expr" maxlength="1000" placeholder="x**2*sin(x)">
          <button class="cta" id="send" type="submit">Compute</button>
        </form>
      </div>

      <aside class="panel">
        <h3>Operation</h3>
        <div class="ctl">
          <select id="op">
            <option value="integrate">integrate</option>
            <option value="differentiate">differentiate</option>
            <option value="simplify">simplify</option>
            <option value="solve">solve</option>
            <option value="limit">limit</option>
            <option value="series">series</option>
            <option value="evaluate">evaluate</option>
          </select>
        </div>
        <div class="ctl">
          <label for="var">Variable</label>
          <input type="text" id="var" value="x" maxlength="16">
        </div>
        <div class="ctl" id="ptwrap" style="display:none">
          <label for="pt">Point</label>
          <input type="text" id="pt" value="0" maxlength="32">
        </div>
        <p class="hint">
          Symbolic in, symbolic out &mdash; you get an exact answer rather than a float that
          already lost the argument. An antiderivative is differentiated back and simplified
          against zero before you see it, and if that check cannot confirm the result it says
          so rather than rounding up to &ldquo;verified&rdquo;.
        </p>
      </aside>
    </div>"""

CALC_JS = """<script>
const form = $('#form'), out = $('#out'), op = $('#op');
op.addEventListener('change', () =>
  $('#ptwrap').style.display = op.value === 'limit' ? '' : 'none');

form.addEventListener('submit', async e => {
  e.preventDefault();
  const expression = $('#expr').value.trim();
  if (!expression) return;
  out.style.color = 'var(--fg)';
  out.textContent = 'computing\\u2026';
  try {
    const payload = {expression, operation: op.value, variable: $('#var').value.trim()};
    if (op.value === 'limit') payload.point = $('#pt').value.trim();
    const r = await api('/api/calc', payload);
    const c = r.check || {};
    const verdict = c.performed
      ? (c.passed === true ? '<span class="v">verified</span>'
         : c.passed === false ? '<span class="bad">CHECK FAILED</span>'
         : '<span class="bad">unconfirmed</span>')
      : '<span class="k">not checked</span>';
    out.innerHTML =
      `<div><span class="k">in</span> ${esc(r.input.text)}</div>` +
      `<div><span class="k">out</span> <span class="v">${esc(r.result.text)}</span></div>` +
      `<div><span class="k">chk</span> ${verdict}` +
        (c.how ? ` <span class="k">&mdash; ${esc(c.how)}</span>` : '') + `</div>` +
      `<div><span class="k">eng</span> <span class="k">${esc(r.engine)} \\u00b7 ${r.seconds}s \\u00b7 ` +
        `${r.exact ? 'exact' : 'symbolic'}</span></div>`;
  } catch (err) {
    out.innerHTML = '<span class="bad">' + esc(err.message) + '</span>';
  }
});
function esc(s){ const d=document.createElement('div'); d.textContent=s==null?'':String(s); return d.innerHTML; }
</script>"""

# ---------------------------------------------------------------- remix
REMIX_BODY = """    <div class="pgwrap">
      <div class="stage">
        <div class="head" id="mhead"><s></s>SyMoNeuRaL Remix
          <span class="grow">idle</span></div>
        <div class="body">
          <div id="out" style="color:var(--faint);font-size:14.5px;line-height:1.66">
            Describe a mood, a night, a drive, a room. You get an ordered set rather than a pile
            of songs &mdash; sequenced so it actually flows.
          </div>
        </div>
        <form class="composer" id="form">
          <input type="text" id="brief" maxlength="1200"
                 placeholder="late-night drive through a rainy city, building slowly">
          <button class="cta" id="send" type="submit">Build it</button>
        </form>
      </div>

      <aside class="panel">
        <h3>Parameters</h3>
        <div class="ctl">
          <label for="count">Tracks <b id="countv">12</b></label>
          <input type="range" id="count" min="5" max="20" step="1" value="12">
        </div>
        <p class="hint">
          Remix is a client of the chat surface rather than its own model &mdash; the same 7B
          that answers questions writes the sequence, which is what &ldquo;one server
          underneath&rdquo; means in practice. So it queues behind chat, and behind image.
        </p>
        <p class="hint">
          <strong style="color:var(--dim)">Generation only, here.</strong> Resolving these
          against Spotify and writing the playlist to an account needs OAuth, and that half
          runs on the box behind admin auth &mdash; not from a public page.
        </p>
      </aside>
    </div>"""

REMIX_JS = """<script>
const form = $('#form'), out = $('#out'), send = $('#send'), head = $('#mhead');
$('#count').addEventListener('input', e => $('#countv').textContent = e.target.value);

form.addEventListener('submit', async e => {
  e.preventDefault();
  const prompt = $('#brief').value.trim();
  if (!prompt) return;
  send.disabled = true;
  out.style.color = 'var(--faint)';
  out.textContent = 'sequencing\\u2026';
  status(head, 'generating', true);
  try {
    const r = await api('/api/remix', {prompt, count: parseInt($('#count').value, 10)});
    if (!r.tracks || !r.tracks.length) {
      out.innerHTML = '<span style="color:var(--amber)">The model did not return a clean list. ' +
                      'Try phrasing the brief differently.</span>';
    } else {
      const ul = document.createElement('ul');
      ul.className = 'tracks';
      for (const t of r.tracks) {
        const li = document.createElement('li');
        const d = document.createElement('div');
        d.innerHTML = '<span class="t"></span> <span class="a"></span><span class="w"></span>';
        d.querySelector('.t').textContent = t.title || '';
        d.querySelector('.a').textContent = t.artist ? '\\u2014 ' + t.artist : '';
        d.querySelector('.w').textContent = t.why || '';
        li.append(d); ul.append(li);
      }
      out.innerHTML = '';
      out.style.color = 'var(--fg)';
      out.append(ul);
      const m = document.createElement('p');
      m.className = 'hint';
      m.textContent = `${r.tracks.length} tracks \\u00b7 ${r.seconds}s on the card \\u00b7 ${r.note}`;
      out.append(m);
    }
  } catch (err) {
    out.innerHTML = '<span style="color:var(--amber)">' + err.message + '</span>';
  } finally {
    send.disabled = false; status(head, 'idle', false);
  }
});
</script>"""


def main() -> int:
    print("building surface pages:")
    page("chat.html",
         title="SyMoNeuRaL Chat — talk to the box",
         desc="A 7B running locally on an RTX 5070 Ti. Nothing leaves the machine.",
         icon="/chat-64.png", eyebrow="Live surface",
         heading="Talk to the box.",
         lede="This is a 7B at Q4 on the RTX 5070 Ti described on the home page, streaming "
              "tokens as the card produces them. The tokens-per-second under each answer is "
              "measured, not claimed.",
         body=CHAT_BODY, script=CHAT_JS)

    page("image.html",
         title="SyMoNeuRaL Image — make it draw",
         desc="FLUX.1-schnell in four steps, rendered locally on a consumer GPU.",
         icon="/image-64.png", eyebrow="Live surface",
         heading="Make it draw something.",
         lede="FLUX.1-schnell, quantized to q4_k and rendered on the card in this machine. "
              "Every image below prints the wall-clock it actually took.",
         body=IMAGE_BODY, script=IMAGE_JS)

    page("calc.html",
         title="SyMoNeuRaL RavenCalc — exact mathematics",
         desc="SymPy-powered symbolic computation that checks its own work.",
         icon="/calc-64.png", eyebrow="Live surface · CPU",
         heading="Mathematics, computed rather than predicted.",
         lede="RavenCalc is SymPy underneath, not a language model guessing at algebra. It "
              "runs on the CPU, so it is the one surface here that never waits for the GPU.",
         body=CALC_BODY, script=CALC_JS)

    page("remix.html",
         title="SyMoNeuRaL Remix — playlists that are ordered sets",
         desc="Prompt to sequenced tracklist, generated locally.",
         icon="/dj-64.png", eyebrow="Live surface",
         heading="Playlists that are ordered sets, not piles of songs.",
         lede="Remix asks the same local 7B that answers questions on the chat page. One "
              "model, one GPU, one server underneath — which is the whole architecture in "
              "one page.",
         body=REMIX_BODY, script=REMIX_JS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
