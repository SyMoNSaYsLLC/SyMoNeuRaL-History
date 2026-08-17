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

# The generators live in tools/, so the repo root is one level up. This exact
# calculation has been wrong twice in this repo's history -- once when demo/ was
# flattened and once here -- and it fails *silently*, because the wrong parent is
# usually a directory that exists. Assert rather than trust it.
ROOT = pathlib.Path(__file__).resolve().parent.parent
assert (ROOT / "backend" / "api.py").is_file(), f"repo root not found at {ROOT}"
SITE = ROOT / "site"

NAV = """    <nav>
      <a class="navlink" href="/">Live stack</a>
      <a class="navlink" href="/documentation.html">Documentation</a>
      <a class="navlink" href="/training.html">Manuals</a>
      <a class="navlink" href="/docs">API</a>
      <a class="navlink" href="/account.html">Account</a>
      <a class="navlink" href="mailto:symonsayadmin@symoneural.com">Contact</a>
      <a class="cta" href="/build.html">Have one built</a>
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
    const r = await api('/api/ravencalc', payload);
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


# ---------------------------------------------------------------- miner (ASIC)
# Deliberately has no controls on it. The rig actions -- reboot, pool change, power mode --
# are operator functions behind a token, and putting the buttons on a public page and then
# refusing the click is worse than not drawing them: it advertises an attack surface and
# teaches visitors that the site's controls are ornamental. This page reports, and says
# plainly what it would report if hardware were attached.
MINER_BODY = """    <div class="pgwrap">
      <div class="stage">
        <div class="head" id="mnhead"><s></s>SyMoNeuRaL Miner &mdash; stack controller
          <span class="grow" id="mnstate">reading&hellip;</span></div>
        <div class="body" id="mnbody">

          <ol class="mn-steps" id="mn-steps">
            <li class="on" data-step="1"><b>1</b> Source</li>
            <li data-step="2"><b>2</b> Vendor</li>
            <li data-step="3"><b>3</b> Model</li>
          </ol>

          <section class="mn-pane on" id="mn-p1">
            <p class="mn-q">Where should the controller look for rigs?</p>
            <div class="mn-choices">
              <button type="button" class="mn-choice" data-src="scan">
                <b>IP scanner</b>
                <span>Sweep a private range for anything answering on the miner API port,
                  then identify it. Real hardware only.</span>
              </button>
              <button type="button" class="mn-choice" data-src="emu">
                <b>Emulator</b>
                <span>Boot real vendor firmware under QEMU and drive that instead. For
                  working on the flash path without risking a rig.</span>
              </button>
            </div>
          </section>

          <section class="mn-pane" id="mn-p2">
            <p class="mn-q">Which vendor?</p>
            <div class="mn-choices">
              <button type="button" class="mn-choice" data-vendor="antminer">
                <b>Antminer</b><span>Bitmain &middot; Xilinx Zynq control board</span>
              </button>
              <button type="button" class="mn-choice" data-vendor="microbt">
                <b>MicroBT</b><span>Whatsminer</span>
              </button>
            </div>
            <button type="button" class="mn-back" data-to="1">&larr; back</button>
          </section>

          <section class="mn-pane" id="mn-p3">
            <p class="mn-q">Which model?</p>
            <div class="mn-models" id="mn-models"></div>
            <p class="mn-legend">
              <i class="mn-dot ok"></i> boots, verified
              <i class="mn-dot part"></i> firmware present, does not boot yet
              <i class="mn-dot no"></i> no firmware on this machine
            </p>
            <button type="button" class="mn-back" data-to="2">&larr; back</button>
          </section>

          <p class="mn-note" id="mnnote"></p>
        </div>
      </div>

      <aside class="side">
        <div class="callout">
          <h3>What the emulator is and is not</h3>
          <p>QEMU runs the control board&rsquo;s ARM cores. It does <b>not</b> emulate the
            FPGA fabric or the links to the hashboards &mdash; those are the part that is not
            there. So the firmware&rsquo;s web UI and its upgrade path run, and <b>bmminer
            does not</b>: with the miner&rsquo;s own init the firmware finds no hashboards
            and reboot-loops, which is correct behaviour and useless as a target.</p>
          <p>It is a good way to work on <b>flashing</b> without risking a rig. It is
            <b>not</b> a substitute for hardware when testing telemetry.</p>
        </div>
        <div class="callout">
          <h3>Why models are greyed out</h3>
          <p>A model is listed as available only if its firmware is actually on this machine
            and has been booted. Nothing is listed on the strength of the hardware existing
            &mdash; the same rule the rack follows.</p>
        </div>
        <div class="callout">
          <h3>Operator surface</h3>
          <p>Scanning and emulation are disabled unless <code>SYM_ASIC_ENABLED</code> and
            <code>SYM_ASIC_TOKEN</code> are set. The scanner refuses any range that is not
            private, so it cannot be aimed at the internet from this host.</p>
        </div>
      </aside>
    </div>
"""


MINER_JS = """<script>
(function () {
  'use strict';
  // `have` is what this machine can ACTUALLY do, not a guess. "ok" = firmware is in
  // references/ and has been booted under QEMU to a shell; "part" = firmware present but
  // does not boot yet; "no" = no firmware here. Listing a model because the hardware exists
  // would be the same lie as a decorative status light.
  var CATALOG = {
    antminer: [
      {id: 'S17 Pro', have: 'ok',   note: 'Zynq-7007 \u2014 boots to a shell, lighttpd runs'},
      {id: 'S17+',    have: 'ok',   note: 'same package generation as the S17 Pro'},
      {id: 'T17',     have: 'ok',   note: 'same package generation as the S17 Pro'},
      {id: 'S9',      have: 'part', note: 'JFFS2 rootfs unpacks; the older kernel gives no console under QEMU yet'},
      {id: 'S19j',    have: 'part', note: 'SD recovery image only, and it fails its own SHA-256 manifest'},
      {id: 'S17',     have: 'no',   note: 'only the unsigned MD package is here, with no fw.tar.gz'},
      {id: 'T9',      have: 'no',   note: 'unsigned dual-variant package; the c5 half is an Altera Cyclone V'},
      {id: 'S19',     have: 'no',   note: 'no firmware on this machine'},
      {id: 'S19 Pro', have: 'no',   note: 'no firmware on this machine'},
      {id: 'S21',     have: 'no',   note: 'no firmware on this machine'}
    ],
    microbt: [
      {id: 'M30 series', have: 'no', note: 'the .bin here is a 4,983-byte HTML page, not firmware'},
      {id: 'M50 series', have: 'no', note: 'the .bin here is 0 bytes'},
      {id: 'M20 series', have: 'no', note: 'no firmware on this machine'},
      {id: 'M60 series', have: 'no', note: 'no firmware on this machine'}
    ]
  };

  var state = {src: null, vendor: null, model: null};
  var note = document.getElementById('mnnote');
  var stEl = document.getElementById('mnstate');

  function show(n) {
    for (var i = 1; i <= 3; i++) {
      var pane = document.getElementById('mn-p' + i);
      if (pane) pane.classList.toggle('on', i === n);
    }
    document.querySelectorAll('.mn-steps li').forEach(function (li) {
      li.classList.toggle('on', Number(li.dataset.step) <= n);
    });
  }

  document.querySelectorAll('[data-src]').forEach(function (b) {
    b.addEventListener('click', function () {
      state.src = b.dataset.src;
      if (state.src === 'scan') {
        note.textContent = 'The IP scanner needs the surface switched on and a private '
          + 'range to sweep. It refuses any range that is not private, so it cannot be '
          + 'aimed at the internet from this host.';
        show(1);
        return;
      }
      note.textContent = '';
      show(2);
    });
  });

  document.querySelectorAll('[data-vendor]').forEach(function (b) {
    b.addEventListener('click', function () {
      state.vendor = b.dataset.vendor;
      renderModels();
      show(3);
    });
  });

  document.querySelectorAll('.mn-back').forEach(function (b) {
    b.addEventListener('click', function () { show(Number(b.dataset.to)); });
  });

  function renderModels() {
    var host = document.getElementById('mn-models');
    host.innerHTML = '';
    (CATALOG[state.vendor] || []).forEach(function (m) {
      var el = document.createElement('button');
      el.type = 'button';
      el.className = 'mn-model ' + m.have;
      el.disabled = (m.have === 'no');
      var d = document.createElement('i'); d.className = 'mn-dot ' + m.have;
      var b = document.createElement('b'); b.textContent = m.id;
      var sp = document.createElement('span'); sp.textContent = m.note;
      el.appendChild(d); el.appendChild(b); el.appendChild(sp);
      el.addEventListener('click', function () {
        state.model = m.id;
        host.querySelectorAll('.mn-model').forEach(function (x) {
          x.classList.remove('sel');
        });
        el.classList.add('sel');
        note.textContent = m.have === 'ok'
          ? m.id + ' selected. Start it with  scripts/qemu-antminer.sh <package> --shell '
            + '--serve  \u2014 the guest web UI lands on http://127.0.0.1:8080'
          : m.id + ' cannot be emulated here: ' + m.note + '.';
      });
      host.appendChild(el);
    });
  }

  fetch('/api/status', {headers: {'Accept': 'application/json'}})
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (s) {
      var u = s && (s.units || []).filter(function (x) { return x.id === 'asicminer'; })[0];
      stEl.textContent = u ? u.state : 'not present';
      if (u && u.state === 'offline') note.textContent = u.detail;
    })
    .catch(function () { stEl.textContent = 'unreachable'; });
})();
</script>"""


# ---------------------------------------------------------------- gateway (TRON)
# No fee figures anywhere on this page, and that is not an oversight. Prices are quoted,
# not published, and a licensing surface is the worst possible place to break that rule.
GATEWAY_BODY = """    <div class="pgwrap">
      <div class="stage">
        <div class="head" id="gwhead"><s></s>SyMoNeuRaL Gateway
          <span class="grow" id="gwstate">reading&hellip;</span></div>
        <div class="body" id="gwbody">
          <p class="gw-note" id="gwdetail">Reading the surface state from
            <code>/api/status</code>&hellip;</p>
          <h3>How a licence would clear</h3>
          <ol class="gw-steps">
            <li><b>Contract (on-chain).</b> A licensing contract on the TRON Virtual
              Machine, denominated in USDT (TRC-20) rather than a native token.</li>
            <li><b>Daemon (off-chain).</b> Runs on the operator&rsquo;s own machine. It
              hashes the build logs into a reviewable tree and <b>pauses for a human to
              approve the configuration</b> before anything is broadcast. No blind script
              touches a rig.</li>
            <li><b>Energy.</b> TRON meters execution as Bandwidth and Energy rather than a
              gas auction. Renting Energy moves the execution cost off the end user.</li>
            <li><b>Settlement.</b> The daemon broadcasts the validation state and the
              payment; DPoS confirmation unlocks the compiled workspace.</li>
          </ol>
        </div>
      </div>

      <aside class="side">
        <div class="callout">
          <h3>Every figure here is someone else&rsquo;s</h3>
          <p><b>~3 second confirmation</b> and <b>27 Super Representatives</b> are
            <b>vendor</b> figures &mdash; published parameters of the TRON network, not
            timings taken on this machine. Block times are a target, not a guarantee.</p>
          <p>&ldquo;Effectively zero fee&rdquo; is <b>projected</b>. Energy rental does not
            make execution free; it moves the cost from the end user to whoever rents the
            Energy. Calling that zero would describe an accounting choice as a physical
            property.</p>
          <p><b>Nothing here is measured</b>, because nothing has run.</p>
        </div>
        <div class="callout">
          <h3>Pricing</h3>
          <p>Licence fees are quoted, not published &mdash; the same answer this site gives
            for hardware, and for the same reason. Ask
            <a href="mailto:symonsayadmin@symoneural.com">symonsayadmin@symoneural.com</a>.</p>
        </div>
        <div class="callout">
          <h3>Why it reads offline</h3>
          <p>There is no deployed contract, no wallet, no daemon and <b>no key material on
            this box</b>. Signing belongs on the operator&rsquo;s own machine, never in the
            environment of a public-facing web process.</p>
        </div>
      </aside>
    </div>
"""

GATEWAY_JS = """<script>
(function () {
  'use strict';
  var st = document.getElementById('gwstate'), d = document.getElementById('gwdetail');
  fetch('/api/status', {headers: {'Accept': 'application/json'}})
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (s) {
      var u = s && (s.units || []).filter(function (x) { return x.id === 'gateway'; })[0];
      if (!u) { st.textContent = 'not present'; d.textContent =
        'The gateway surface is not present in this API build.'; return; }
      st.textContent = u.state;
      d.textContent = u.detail;   // the API's own words, not a rewrite of them
    })
    .catch(function () { st.textContent = 'unreachable';
      d.textContent = 'Could not reach /api/status.'; });
})();
</script>"""


# ---------------------------------------------------------------- tuner (IPTV)
# The credentials never reach this box. They live in the visitor's localStorage and are
# sent per request; the backend registers them for the life of a stream session and scrubs
# them from every error path. Nothing is written to disk and nothing is logged.
TUNER_BODY = """    <div class="pgwrap">
      <div class="stage">
        <div class="head" id="tnhead"><s></s>SyMoNeuRaL Tuner
          <span class="grow" id="tnstate">idle</span></div>
        <div class="body" id="tnbody">
          <form class="tn-load" id="tnform">
            <div class="tn-tabs">
              <button type="button" class="tn-tab on" data-mode="m3u">M3U playlist</button>
              <button type="button" class="tn-tab" data-mode="xtream">Xtream Codes</button>
            </div>
            <div class="tn-fields" id="tn-m3u">
              <label for="tn-url">Playlist URL</label>
              <input id="tn-url" type="url" placeholder="https://example.com/playlist.m3u"
                     autocomplete="off" spellcheck="false">
            </div>
            <div class="tn-fields" id="tn-xtream" hidden>
              <label for="tn-host">Server</label>
              <input id="tn-host" type="url" placeholder="http://example.com:8080"
                     autocomplete="off" spellcheck="false">
              <label for="tn-user">Username</label>
              <input id="tn-user" type="text" autocomplete="off" spellcheck="false">
              <label for="tn-pass">Password</label>
              <input id="tn-pass" type="password" autocomplete="off">
            </div>
            <button class="cta" id="tn-go" type="submit">Load channels</button>
          </form>
          <p class="tn-note" id="tnnote">Your playlist is yours. It is held in this
            browser&rsquo;s localStorage, sent per request, and never stored on this
            machine.</p>
          <ul class="tn-list" id="tnlist"></ul>
        </div>
      </div>

      <aside class="side">
        <div class="callout">
          <h3>Where your credentials go</h3>
          <p><b>Nowhere.</b> They stay in this browser&rsquo;s localStorage and travel with
            each request. The server holds them only for the life of a stream and keeps
            them out of process arguments and error text. Nothing is written to disk.</p>
        </div>
        <div class="callout">
          <h3>How the stream is handled</h3>
          <p>ffmpeg copies the stream rather than re-encoding it, so it costs muxing and
            network rather than compute &mdash; this surface never queues behind the GPU.
            The upstream socket is opened in Python against a pinned, validated address and
            the bytes are piped in; <b>ffmpeg is never handed a URL</b>, so it cannot make
            its own DNS lookup or follow its own redirect.</p>
        </div>
        <div class="callout">
          <h3>Known gaps, stated rather than hidden</h3>
          <p>Playback needs <code>hls.js</code>, which is <b>not vendored here yet</b>:
            Chrome and Firefox cannot play an <code>.m3u8</code> natively, so channels list
            and stream, but in-page playback currently works only in Safari. The Xtream
            client is written to the protocol and <b>has never been tested against a live
            panel</b>. Series episodes list without URLs rather than with guessed ones, and
            AES-encrypted HLS is refused rather than decrypted.</p>
        </div>
      </aside>
    </div>
"""

TUNER_JS = """<script>
(function () {
  'use strict';
  var K = 'symoneural.tuner';
  var form = document.getElementById('tnform'), list = document.getElementById('tnlist');
  var note = document.getElementById('tnnote'), st = document.getElementById('tnstate');
  var mode = 'm3u';

  document.querySelectorAll('.tn-tab').forEach(function (b) {
    b.addEventListener('click', function () {
      mode = b.dataset.mode;
      document.querySelectorAll('.tn-tab').forEach(function (x) {
        x.classList.toggle('on', x === b); });
      document.getElementById('tn-m3u').hidden = mode !== 'm3u';
      document.getElementById('tn-xtream').hidden = mode !== 'xtream';
    });
  });

  // Restore whatever this browser last used. This is the only place it is kept.
  try {
    var saved = JSON.parse(localStorage.getItem(K) || 'null');
    if (saved) {
      mode = saved.mode || 'm3u';
      document.querySelector('.tn-tab[data-mode="' + mode + '"]').click();
      ['url', 'host', 'user', 'pass'].forEach(function (f) {
        if (saved[f]) document.getElementById('tn-' + f).value = saved[f]; });
    }
  } catch (e) { /* corrupt entry -- ignore and start clean */ }

  function creds() {
    if (mode === 'm3u') return {mode: 'm3u', url: document.getElementById('tn-url').value.trim()};
    return {mode: 'xtream',
            host: document.getElementById('tn-host').value.trim(),
            user: document.getElementById('tn-user').value,
            pass: document.getElementById('tn-pass').value};
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var c = creds();
    try { localStorage.setItem(K, JSON.stringify(c)); } catch (e2) { /* private mode */ }
    st.textContent = 'loading'; list.innerHTML = ''; note.textContent = 'Fetching\u2026';

    // Two different endpoints, not one. Posting to a path the router does not serve
    // falls through to the static mount at "/", which answers 405 Method Not Allowed --
    // a confusing way to be told the URL is wrong.
    var url  = c.mode === 'm3u' ? '/api/tuner/playlist' : '/api/tuner/xtream/channels';
    var body = c.mode === 'm3u' ? {url: c.url}
             : {server: c.host, username: c.user, password: c.pass, kinds: ['live']};
    fetch(url, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    }).then(function (r) { return r.json().then(function (j) { return {ok: r.ok, j: j}; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.j.error || res.j.detail || 'load failed');
        var ch = res.j.channels || [];
        st.textContent = ch.length ? ch.length + ' channels' : 'empty';
        var notes = (res.j.notes || []).join(' ');
        note.textContent = (ch.length ? 'Loaded from your playlist. Nothing was stored here.'
                                      : 'That playlist parsed but contained no channels.')
                           + (notes ? '  ' + notes : '');
        list.innerHTML = ch.slice(0, 400).map(function (c2) {
          return '<li><b></b><span></span></li>'; }).join('');
        list.querySelectorAll('li').forEach(function (li, i) {
          li.querySelector('b').textContent = ch[i].name || '(unnamed)';
          li.querySelector('span').textContent = ch[i].group || '';
        });
      })
      .catch(function (err) {
        st.textContent = 'failed';
        note.textContent = String(err.message || err);
      });
  });
})();
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

    page("ravencalc.html",
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

    page("miner.html",
         title="SyMoNeuRaL Miner — Antminer and MicroBT, read honestly",
         desc="An operator surface for ASIC mining rigs. Offline until real hardware answers.",
         icon="/terminal-64.png", eyebrow="Operator surface · ASIC",
         heading="Mining hardware, read the same way as the card.",
         lede="The rack on the home page reads real sensors off an RTX 5070 Ti. This does "
              "the same for Antminer and MicroBT rigs on the operator's network. No rigs "
              "are attached to this machine, so it reports offline — which is the reading, "
              "not a placeholder.",
         body=MINER_BODY, script=MINER_JS)

    page("gateway.html",
         title="SyMoNeuRaL Gateway — stablecoin licensing, honestly labelled",
         desc="A TRON/USDT licensing and validation gateway. Designed, not yet deployed.",
         icon="/terminal-64.png", eyebrow="Surface · designed, not deployed",
         heading="Licensing that clears in seconds, and says whose number that is.",
         lede="A licensing gateway on the TRON Virtual Machine, settling in USDT, with a "
              "local daemon that makes a human approve the configuration before anything "
              "is broadcast. Nothing is deployed yet, so this page reports offline and "
              "labels every figure it quotes as vendor or projected.",
         body=GATEWAY_BODY, script=GATEWAY_JS)

    page("tuner.html",
         title="SyMoNeuRaL Tuner — your playlist, your credentials",
         desc="IPTV over ffmpeg stream copy. Credentials stay in your browser.",
         icon="/terminal-64.png", eyebrow="Live surface · network",
         heading="Bring your own playlist.",
         lede="Load an M3U or Xtream Codes subscription and the box will copy the stream "
              "rather than re-encode it. Your credentials stay in this browser and are "
              "never written to disk here — which is the same promise the rest of this "
              "site makes about your data.",
         body=TUNER_BODY, script=TUNER_JS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
