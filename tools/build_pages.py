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
// These three surfaces use a <textarea> rather than an <input> so a long prompt WRAPS and
// can be read back. A textarea takes Enter as a newline, so submit is restored explicitly;
// Shift+Enter still gives a deliberate line break. Applied to whichever box the page has.
document.addEventListener('DOMContentLoaded', () => {
  const box = $('#prompt') || $('#expr') || $('#brief');
  const f = $('#form');
  if (!box || !f || box.tagName !== 'TEXTAREA' || box.dataset.enterBound) return;
  box.dataset.enterBound = '1';
  box.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); f.requestSubmit(); }
  });
});
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


# ---------------------------------------------------------------- the GPU panel
# Reuses `site/console.js` outright rather than adding a second data path. That file
# connects when it finds `#units` OR `#m-vram` on the page (console.js:266) and then writes
# m-vram / m-pwr / m-temp / m-holder / m-queue / con-link. So carrying those ids is the whole
# integration: same WebSocket, same readings, same fallback to polling. Its txt()/meter()
# helpers no-op on ids that are absent, so the ids the rack uses and this does not are safe.
#
# Every number here is read from nvidia-smi through /api/status. `holder` is which surface
# owns the card right now, which is the one that explains a wait -- if it names something
# other than this page, you are queued behind it, and that is why the button is slow.
def gpu_panel(uses_gpu: bool, surface: str) -> str:
    if uses_gpu:
        why = (f"While a prompt runs, <b>{surface}</b> holds the card and every other GPU "
               "surface waits. If <i>holding</i> names something else, you are queued behind "
               "it &mdash; that is the honest reason a request is slow.")
    else:
        why = (f"<b>{surface} does not use the GPU.</b> This is the card the rest of the "
               "stack shares, shown here so you can see what it is doing; nothing on this "
               "page waits for it.")
    return f'''<div class="gpu-panel">
          <p class="gpu-head"><s></s>RTX 5070 Ti<span class="gpu-link" id="con-link">socket: connecting</span></p>
          <div class="gpu-row">
            <label>VRAM free <b id="m-vram">&mdash;</b></label>
            <div class="gbar" id="m-vrambar"><i style="width:0%"></i></div>
          </div>
          <div class="gpu-row">
            <label>Power <b id="m-pwr">&mdash;</b></label>
            <div class="gbar" id="m-pwrbar"><i style="width:0%"></i></div>
          </div>
          <dl class="gpu-facts">
            <dt>Temperature</dt><dd id="m-temp">&mdash;</dd>
            <dt>Holding</dt><dd id="m-holder">&mdash;</dd>
            <dt>Queued</dt><dd id="m-queue">&mdash;</dd>
          </dl>
          <!-- The whole stack, not just the holder. console.js already renders the rack
               into #units, so carrying that id here shows every surface and which one is
               actually busy -- "something else is running" answered by looking, rather
               than inferred from one field. Styled compact for a sidebar. -->
          <div class="units gpu-stack" id="units"></div>
          <p class="gpu-why">{why}</p>
        </div>
        '''


def page(name: str, gpu: bool | None = None, surface: str = "", **kw) -> None:
    """Render one surface page.

    `gpu` places the live GPU panel at the top of the page's aside -- beside the prompt,
    which is where it answers the question it exists for ("why is this slow"). Pass False
    for a surface that does not use the card: the panel still appears, because the card is
    shared and its state is worth seeing, but it says plainly that this page does not wait
    for it. Omit entirely for a page with no prompt.
    """
    if gpu is not None:
        body = kw.get("body", "")
        i = body.find("<aside")
        if i >= 0:
            j = body.find(">", i)
            kw["body"] = (body[:j + 1] + "\n        " + gpu_panel(gpu, surface or name)
                          + body[j + 1:])
    html = SHELL.replace("@@NAV@@", NAV)
    for key, value in kw.items():
        html = html.replace(f"@@{key.upper()}@@", value)
    (SITE / name).write_text(html)
    print(f"  {name}")


# ---------------------------------------------------------------- chat
CHAT_BODY = """    <div class="cu">

      <!-- Left rail. A <div role=navigation>, NOT a <nav>: the sitewide rule
           `nav a:not(.cta){display:none}` hides nav links below 820px, which would delete
           every link in here on a phone. -->
      <div class="cu-rail" id="cu-rail" role="navigation" aria-label="Conversations">
        <div class="cu-railtop">
          <button type="button" class="cu-new" id="cu-new">+ New chat</button>
          <button type="button" class="cu-collapse" id="cu-collapse"
                  aria-label="Hide conversations">&#8942;</button>
        </div>
        <p class="cu-railhead">Conversations</p>
        <ul class="cu-hist" id="cu-hist"></ul>
        <p class="cu-railfoot">Kept in this browser only.<br>Nothing is stored on the box.</p>
      </div>

      <div class="cu-main">
        <!-- Empty state: centred, and it goes away once there is a transcript. -->
        <div class="cu-empty" id="cu-empty">
          <h2 class="cu-greet">Ask the box.</h2>
          <p class="cu-sub">A 7B at Q4 on the RTX 5070 Ti in this room. Nothing you type
            leaves the machine.</p>
        </div>

        <div class="cu-log" id="log"></div>

        <form class="cu-composer" id="form">
          <textarea id="prompt" rows="1" maxlength="1200"
                    placeholder="How can I help?"></textarea>
          <div class="cu-tools">
            <label class="cu-attach" title="Attach a text file">
              <input type="file" id="cu-file" accept=".txt,.md,.csv,.json,.log,.py,.js,.html,.css,.yaml,.yml,.toml,.ini,.sh">
              <span>&#43;</span>
            </label>
            <span class="cu-file-name" id="cu-filename"></span>
            <span class="cu-spacer"></span>
            <span class="cu-model" id="cu-model">SymonChat S1-7B</span>
            <button class="cu-send" id="send" type="submit" aria-label="Send">&#8593;</button>
          </div>
        </form>
        <p class="cu-hint" id="stat">&nbsp;</p>
      </div>
    </div>
"""


CHAT_JS = """<script>
(function () {
  'use strict';
  var log = document.getElementById('log'), form = document.getElementById('form');
  var box = document.getElementById('prompt'), send = document.getElementById('send');
  var empty = document.getElementById('cu-empty'), stat = document.getElementById('stat');
  var histEl = document.getElementById('cu-hist'), fileEl = document.getElementById('cu-file');
  var fileName = document.getElementById('cu-filename');
  var K = 'symoneural.chat.v1';
  var chats = [], cur = null, attached = null, busy = false;

  // ---------------------------------------------------------------- storage
  // Conversations live in THIS BROWSER and nowhere else. There is no history endpoint and
  // no conversation id on the server, which is not a gap -- it is the same promise the rest
  // of the site makes about your data. The transcript is replayed to /api/chat on each turn
  // so the model can follow along, and the server keeps none of it.
  function load() {
    try { chats = JSON.parse(localStorage.getItem(K) || '[]'); }
    catch (e) { chats = []; }
    if (!Array.isArray(chats)) chats = [];
  }
  function save() {
    try { localStorage.setItem(K, JSON.stringify(chats.slice(0, 50))); }
    catch (e) { /* private mode, or full -- the chat still works, it just will not persist */ }
  }
  function title(t) { return (t || 'New chat').replace(/\\s+/g, ' ').trim().slice(0, 42); }

  function renderHist() {
    histEl.innerHTML = '';
    chats.forEach(function (c, i) {
      var li = document.createElement('li');
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'cu-histbtn' + (cur === i ? ' on' : '');
      b.textContent = c.title;
      b.addEventListener('click', function () { open(i); });
      var d = document.createElement('button');
      d.type = 'button'; d.className = 'cu-del'; d.textContent = '×';
      d.setAttribute('aria-label', 'Delete this conversation');
      d.addEventListener('click', function (e) {
        e.stopPropagation();
        chats.splice(i, 1);
        if (cur === i) { cur = null; log.innerHTML = ''; empty.hidden = false; }
        else if (cur !== null && cur > i) cur--;
        save(); renderHist();
      });
      li.appendChild(b); li.appendChild(d); histEl.appendChild(li);
    });
    if (!chats.length) {
      var p = document.createElement('li');
      p.className = 'cu-histnone'; p.textContent = 'No conversations yet.';
      histEl.appendChild(p);
    }
  }

  function open(i) {
    cur = i; log.innerHTML = '';
    chats[i].turns.forEach(function (t) { paint(t.role, t.content); });
    empty.hidden = chats[i].turns.length > 0;
    renderHist();
    log.scrollTop = log.scrollHeight;
  }

  document.getElementById('cu-new').addEventListener('click', function () {
    cur = null; log.innerHTML = ''; empty.hidden = false; box.value = ''; clearFile();
    renderHist(); box.focus();
  });
  document.getElementById('cu-collapse').addEventListener('click', function () {
    document.getElementById('cu-rail').classList.toggle('shut');
  });

  // ---------------------------------------------------------------- transcript
  function paint(role, text) {
    var wrap = document.createElement('div');
    wrap.className = 'cu-turn ' + (role === 'user' ? 'you' : 'bot');
    var who = document.createElement('div');
    who.className = 'cu-who';
    who.textContent = role === 'user' ? 'You' : 'SyMoNeuRaL';
    var msg = document.createElement('div');
    msg.className = 'cu-msg';
    msg.textContent = text;
    wrap.appendChild(who); wrap.appendChild(msg);
    log.appendChild(wrap);
    return msg;
  }

  // ---------------------------------------------------------------- attachments
  // TEXT ONLY, and the accept list says so. The chat model is Qwen2.5-7B-Instruct with no
  // vision projector -- it cannot see an image, so an image picker here would be a control
  // that can never work. The file is read in the browser and its text is prepended to the
  // prompt; it is never uploaded, because there is no upload endpoint and none is needed.
  fileEl.addEventListener('change', function () {
    var f = fileEl.files && fileEl.files[0];
    if (!f) return clearFile();
    if (f.size > 200000) {
      fileName.textContent = f.name + ' is too large (200 KB max)';
      fileEl.value = ''; attached = null; return;
    }
    var r = new FileReader();
    r.onload = function () {
      attached = {name: f.name, text: String(r.result).slice(0, 24000)};
      fileName.textContent = f.name + '  ×';
    };
    r.readAsText(f);
  });
  fileName.addEventListener('click', clearFile);
  function clearFile() { attached = null; fileEl.value = ''; fileName.textContent = ''; }

  // ---------------------------------------------------------------- send
  box.addEventListener('input', function () {
    box.style.height = 'auto';
    box.style.height = Math.min(260, box.scrollHeight) + 'px';
  });
  box.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (busy) return;
    var q = box.value.trim();
    if (!q) return;
    var sent = q;
    if (attached) sent = 'File: ' + attached.name + '\\n\\n' + attached.text + '\\n\\n' + q;

    if (cur === null) {
      chats.unshift({title: title(q), turns: []});
      cur = 0;
    }
    empty.hidden = true;
    paint('user', attached ? (attached.name + '  —  ' + q) : q);
    chats[cur].turns.push({role: 'user', content: sent});
    box.value = ''; box.style.height = 'auto'; clearFile();
    log.scrollTop = log.scrollHeight;

    var out = paint('assistant', '');
    busy = true; send.disabled = true; stat.textContent = 'thinking…';

    // Everything before this turn, replayed. The cap matches the server's, so a long chat
    // is trimmed here rather than refused there.
    var prior = chats[cur].turns.slice(0, -1).slice(-19);

    fetch('/api/chat', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt: sent, history: prior,
                            temperature: 0.7, max_tokens: 512})
    }).then(function (r) {
      if (!r.ok) return r.json().catch(function () { return {}; }).then(function (j) {
        throw new Error(j.detail || j.error || ('HTTP ' + r.status));
      });
      var reader = r.body.getReader(), dec = new TextDecoder(), buf = '', text = '';
      return (function pump() {
        return reader.read().then(function (res) {
          if (res.done) return text;
          buf += dec.decode(res.value, {stream: true});
          var parts = buf.split('\\n\\n'); buf = parts.pop();
          parts.forEach(function (block) {
            block.split('\\n').forEach(function (line) {
              if (line.indexOf('data:') !== 0) return;
              var j; try { j = JSON.parse(line.slice(5)); } catch (e) { return; }
              if (j.delta) { text += j.delta; out.textContent = text; log.scrollTop = log.scrollHeight; }
              if (j.done) {
                // Measured, not claimed -- the server times the card and sends the rate.
                stat.textContent = j.tokens + ' tokens in ' + j.seconds + 's  ·  '
                                 + j.tok_per_s + ' tok/s measured on the card'
                                 + (j.adapter ? '  ·  persona adapter loaded' : '');
              }
              if (j.error) throw new Error(j.error);
            });
          });
          return pump();
        });
      })();
    }).then(function (text) {
      chats[cur].turns.push({role: 'assistant', content: text});
      if (chats[cur].turns.length === 2) chats[cur].title = title(q);
      save(); renderHist();
    }).catch(function (err) {
      out.textContent = String(err.message || err);
      out.parentElement.classList.add('failed');
      stat.textContent = '';
    }).then(function () {
      busy = false; send.disabled = false; box.focus();
    });
  });

  load(); renderHist();
})();
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
          <textarea id="prompt" rows="3" maxlength="1200"
                    placeholder="a raven perched on a server rack, volumetric light, cinematic"></textarea>
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
          <textarea id="expr" rows="3" maxlength="1000" placeholder="x**2*sin(x)"></textarea>
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
          <textarea id="brief" rows="3" maxlength="1200"
                    placeholder="late-night drive through a rainy city, building slowly"></textarea>
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
  var state = {src: null, vendor: null, pkg: null, packages: null};
  var note = document.getElementById('mnnote');
  var stEl = document.getElementById('mnstate');

  // The operator token. sessionStorage, not localStorage: this authorises scanning and
  // starting processes, so it should not outlive the tab. It is never sent anywhere but
  // this origin's own /api/asicminer routes.
  function token() {
    var t = sessionStorage.getItem('sym.asic.token');
    if (!t) {
      t = window.prompt('Operator token (SYM_ASIC_TOKEN)');
      if (t) sessionStorage.setItem('sym.asic.token', t);
    }
    return t || '';
  }
  function api(path, body) {
    return fetch(path, {
      method: body ? 'POST' : 'GET',
      headers: {'Content-Type': 'application/json', 'X-Sym-Token': token()},
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (r.status === 401) sessionStorage.removeItem('sym.asic.token');
        return {ok: r.ok, status: r.status, j: j};
      });
    });
  }
  function say(t) { note.textContent = t; }
  function fail(res, what) {
    say(what + ' failed (' + res.status + '): '
        + (res.j.detail || res.j.error || 'no reason given'));
  }

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
      if (state.src === 'scan') { runScan(); return; }
      say(''); show(2);
    });
  });

  function runScan() {
    var cidr = window.prompt('Private range to sweep', '192.168.1.0/24');
    if (!cidr) return;
    say('scanning ' + cidr + ' …');
    api('/api/asicminer/scan', {cidr: cidr}).then(function (res) {
      if (!res.ok) return fail(res, 'scan');
      var d = res.j;
      if (d.error) { say('scan refused: ' + d.error); return; }
      var found = (d.rigs || []).filter(function (r) { return r.identified; });
      say('swept ' + d.swept + ' addresses, ' + d.responded + ' answered on port '
          + d.port + ', ' + found.length + ' identified'
          + (found.length ? ': ' + found.map(function (r) {
               return r.host + ' ' + (r.vendor || '?') + ' ' + (r.model || ''); }).join(', ')
             : '. Nothing on this network is a rig.'));
    });
  }

  document.querySelectorAll('[data-vendor]').forEach(function (b) {
    b.addEventListener('click', function () {
      state.vendor = b.dataset.vendor;
      loadPackages();
      show(3);
    });
  });
  document.querySelectorAll('.mn-back').forEach(function (b) {
    b.addEventListener('click', function () { show(Number(b.dataset.to)); });
  });

  // The model list is READ OFF DISK, not hardcoded. A list written into this page goes
  // stale the moment firmware is added or removed, and would claim images that are not
  // there -- the same failure as a status light that is not wired to anything.
  function loadPackages() {
    var host = document.getElementById('mn-models');
    host.textContent = 'reading firmware on this machine…';
    api('/api/asicminer/firmware').then(function (res) {
      if (!res.ok) { host.textContent = ''; return fail(res, 'firmware listing'); }
      state.packages = res.j.packages || [];
      renderModels();
    });
  }

  function renderModels() {
    var host = document.getElementById('mn-models');
    var list = (state.packages || []).filter(function (p) {
      return p.vendor === state.vendor;
    });
    host.innerHTML = '';
    if (!list.length) {
      host.textContent = 'No ' + state.vendor + ' firmware is present on this machine.';
      return;
    }
    list.forEach(function (m) {
      var bootable = (m.kind === 'browser');
      var el = document.createElement('button');
      el.type = 'button';
      el.className = 'mn-model ' + (bootable ? 'ok' : 'part');
      var d = document.createElement('i'); d.className = 'mn-dot ' + (bootable ? 'ok' : 'part');
      var b = document.createElement('b'); b.textContent = m.name;
      var sp = document.createElement('span');
      sp.textContent = (m.bytes / 1048576).toFixed(1) + ' MB · '
        + (bootable ? 'browser-upgrade package — bootable'
                    : 'SD recovery package — not bootable this way');
      el.appendChild(d); el.appendChild(b); el.appendChild(sp);
      el.addEventListener('click', function () {
        state.pkg = m;
        host.querySelectorAll('.mn-model').forEach(function (x) { x.classList.remove('sel'); });
        el.classList.add('sel');
        if (!bootable) { say(m.name + ' is an SD recovery package; the emulator takes a '
                             + 'browser-upgrade .tar.gz.'); return; }
        startEmulator(m);
      });
      host.appendChild(el);
    });
  }

  function startEmulator(m) {
    say('starting ' + m.name + ' …');
    api('/api/asicminer/emulator', {action: 'start', package: m.id}).then(function (res) {
      if (!res.ok) return fail(res, 'emulator');
      if (!res.j.ok) { say('emulator: ' + res.j.error); return; }
      say('booted ' + res.j.package + ' (pid ' + res.j.pid + '). ' + res.j.note
          + '  Guest web UI: ' + res.j.web);
      refreshEmu();
    });
  }

  function refreshEmu() {
    api('/api/asicminer/emulator', {action: 'status'}).then(function (res) {
      if (res.ok && res.j.running) {
        stEl.textContent = 'emulating ' + (res.j.package || '');
      }
    });
  }

  fetch('/api/status', {headers: {'Accept': 'application/json'}})
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (s) {
      var u = s && (s.units || []).filter(function (x) { return x.id === 'asicminer'; })[0];
      stEl.textContent = u ? u.state : 'not present';
      if (u && u.state === 'offline') say(u.detail);
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

          <!-- player: hidden until something is tuned, because an empty <video> with
               controls is a piece of furniture that does nothing -->
          <div class="tn-player" id="tnplayer" hidden>
            <video id="tnvideo" controls playsinline></video>
            <p class="tn-now" id="tnnow"></p>
          </div>

          <p class="tn-note" id="tnnote">Your playlist is yours. It is held in this
            browser&rsquo;s localStorage, sent per request, and never stored on this
            machine.</p>

          <!-- browse: kind, then group, then an optional model-assisted filter -->
          <div class="tn-browse" id="tnbrowse" hidden>
            <div class="tn-kinds" id="tnkinds"></div>
            <div class="tn-ask">
              <input id="tnask" type="text" autocomplete="off"
                     placeholder="Ask for what you want &mdash; &ldquo;90s action movies&rdquo;, &ldquo;motorsport&rdquo;">
              <button type="button" class="tn-askgo" id="tnaskgo">Ask</button>
              <button type="button" class="tn-askclear" id="tnaskclear" hidden>clear</button>
            </div>
            <p class="tn-askwhy" id="tnaskwhy"></p>
            <div class="tn-groups" id="tngroups"></div>
          </div>

          <ul class="tn-list" id="tnlist"></ul>
        </div>
      </div>

      <aside class="side">
        <div class="callout">
          <h3>Where your credentials go</h3>
          <p><b>Nowhere.</b> They stay in this browser&rsquo;s localStorage and travel with
            each request. The server holds them only for the life of a stream and keeps them
            out of process arguments and error text. Nothing is written to disk.</p>
        </div>
        <div class="callout">
          <h3>How the stream is handled</h3>
          <p>ffmpeg copies the stream rather than re-encoding it, so it costs muxing and
            network rather than compute &mdash; this surface never queues behind the GPU. The
            upstream socket is opened in Python against a pinned, validated address and the
            bytes are piped in; <b>ffmpeg is never handed a URL</b>, so it cannot make its own
            DNS lookup or follow its own redirect.</p>
          <p>Playback is <b>hls.js</b> (Apache-2.0, vendored at <code>/hls.js</code>), because
            Chrome and Firefox will not play an <code>.m3u8</code> natively.</p>
        </div>
        <div class="callout">
          <h3>What the model actually does here</h3>
          <p>It reads <b>your question</b>, not your playlist. The prompt becomes a filter
            &mdash; terms to match, terms to exclude, which kind &mdash; and that filter is
            applied to the list already in this browser. One request to the card, not one per
            channel.</p>
          <p>Feeding thousands of channel names through a 7B would be slow, would hold the GPU
            lock while it ran, and would be worse at it than a substring match. If the model
            is busy or its answer will not parse, the box falls back to searching your words
            directly and says so.</p>
        </div>
        <div class="callout">
          <h3>Known gaps, stated rather than hidden</h3>
          <p>The vendored hls.js is the <b>light</b> build: no subtitle or alternate-audio
            rendering. The Xtream client has <b>never been tested against a live panel</b>
            beyond channel listing. Series episodes list without URLs rather than with guessed
            ones, and AES-encrypted HLS is refused rather than decrypted.</p>
        </div>
      </aside>
    </div>
"""


TUNER_JS = """<script src="/hls.js"></script>
<script>
(function () {
  'use strict';
  var K = 'symoneural.tuner';
  var form = document.getElementById('tnform'), list = document.getElementById('tnlist');
  var note = document.getElementById('tnnote'), st = document.getElementById('tnstate');
  var browse = document.getElementById('tnbrowse'), groupsEl = document.getElementById('tngroups');
  var kindsEl = document.getElementById('tnkinds'), askWhy = document.getElementById('tnaskwhy');
  var player = document.getElementById('tnplayer'), video = document.getElementById('tnvideo');
  var nowEl = document.getElementById('tnnow');
  var mode = 'm3u', all = [], view = [], kind = '', group = '', hls = null, aiFilter = null;

  document.querySelectorAll('.tn-tab').forEach(function (b) {
    b.addEventListener('click', function () {
      mode = b.dataset.mode;
      document.querySelectorAll('.tn-tab').forEach(function (x) {
        x.classList.toggle('on', x === b); });
      document.getElementById('tn-m3u').hidden = mode !== 'm3u';
      document.getElementById('tn-xtream').hidden = mode !== 'xtream';
    });
  });

  try {
    var saved = JSON.parse(localStorage.getItem(K) || 'null');
    if (saved) {
      mode = saved.mode || 'm3u';
      document.querySelector('.tn-tab[data-mode="' + mode + '"]').click();
      ['url', 'host', 'user', 'pass'].forEach(function (f) {
        if (saved[f]) document.getElementById('tn-' + f).value = saved[f]; });
    }
  } catch (e) { /* corrupt entry -- start clean */ }

  function creds() {
    if (mode === 'm3u') return {mode: 'm3u', url: document.getElementById('tn-url').value.trim()};
    return {mode: 'xtream', host: document.getElementById('tn-host').value.trim(),
            user: document.getElementById('tn-user').value,
            pass: document.getElementById('tn-pass').value};
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var c = creds();
    try { localStorage.setItem(K, JSON.stringify(c)); } catch (e2) { /* private mode */ }
    st.textContent = 'loading'; list.innerHTML = ''; browse.hidden = true;
    note.textContent = 'Fetching\\u2026';
    var url  = c.mode === 'm3u' ? '/api/tuner/playlist' : '/api/tuner/xtream/channels';
    var body = c.mode === 'm3u' ? {url: c.url}
             : {server: c.host, username: c.user, password: c.pass,
                kinds: ['live', 'movie', 'series']};
    fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)})
      .then(function (r) { return r.json().then(function (j) { return {ok: r.ok, j: j}; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.j.error || res.j.detail || 'load failed');
        all = res.j.channels || [];
        st.textContent = all.length ? all.length + ' channels' : 'empty';
        var notes = (res.j.notes || []).join(' ');
        note.textContent = (all.length
            ? 'Loaded from your playlist. Nothing was stored here.'
            : 'That playlist parsed but contained no channels.') + (notes ? '  ' + notes : '');
        kind = ''; group = ''; aiFilter = null; askWhy.textContent = '';
        document.getElementById('tnaskclear').hidden = true;
        if (all.length) { browse.hidden = false; renderKinds(); apply(); }
      })
      .catch(function (err) { st.textContent = 'failed'; note.textContent = String(err.message || err); });
  });

  // ---- browsing: kinds and groups come from the playlist itself, not a fixed list
  function renderKinds() {
    var counts = {};
    all.forEach(function (c) { var k = c.kind || 'live'; counts[k] = (counts[k] || 0) + 1; });
    var kinds = Object.keys(counts).sort();
    kindsEl.innerHTML = '';
    mkChip(kindsEl, 'Everything', all.length, kind === '', function () { kind = ''; group = ''; renderKinds(); apply(); });
    kinds.forEach(function (k) {
      var label = k === 'movie' ? 'Movies' : k === 'series' ? 'Series'
                : k === 'live' ? 'Live TV' : k;
      mkChip(kindsEl, label, counts[k], kind === k, function () {
        kind = k; group = ''; renderKinds(); apply(); });
    });
  }

  function mkChip(host, label, n, on, fn) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'tn-chip' + (on ? ' on' : '');
    var s1 = document.createElement('b'); s1.textContent = label;
    var s2 = document.createElement('i'); s2.textContent = n;
    b.appendChild(s1); b.appendChild(s2);
    b.addEventListener('click', fn); host.appendChild(b);
  }

  function inKind(c) { return !kind || (c.kind || 'live') === kind; }

  function renderGroups() {
    var counts = {};
    all.filter(inKind).forEach(function (c) {
      var g = c.group || '(no group)'; counts[g] = (counts[g] || 0) + 1; });
    var names = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });
    groupsEl.innerHTML = '';
    if (names.length < 2) return;
    mkChip(groupsEl, 'All groups', all.filter(inKind).length, group === '', function () {
      group = ''; renderGroups(); apply(); });
    names.slice(0, 40).forEach(function (g) {
      mkChip(groupsEl, g, counts[g], group === g, function () {
        group = g; renderGroups(); apply(); });
    });
  }

  function apply() {
    renderGroups();
    view = all.filter(function (c) {
      if (!inKind(c)) return false;
      if (group && (c.group || '(no group)') !== group) return false;
      if (aiFilter) {
        var hay = ((c.name || '') + ' ' + (c.group || '')).toLowerCase();
        if (aiFilter.match.length &&
            !aiFilter.match.some(function (t) { return hay.indexOf(t) >= 0; })) return false;
        if (aiFilter.exclude.some(function (t) { return hay.indexOf(t) >= 0; })) return false;
      }
      return true;
    });
    renderList();
  }

  function renderList() {
    list.innerHTML = '';
    view.slice(0, 500).forEach(function (c) {
      var li = document.createElement('li');
      var b = document.createElement('b'); b.textContent = c.name || '(unnamed)';
      var sp = document.createElement('span'); sp.textContent = c.group || '';
      li.appendChild(b); li.appendChild(sp);
      if (c.url) {
        li.className = 'playable';
        li.addEventListener('click', function () { tune(c); });
      } else {
        var no = document.createElement('em'); no.textContent = 'no stream url';
        li.appendChild(no);
      }
      list.appendChild(li);
    });
    if (view.length > 500) {
      var li = document.createElement('li');
      li.className = 'tn-more';
      li.textContent = 'showing 500 of ' + view.length + ' \\u2014 narrow it with a group or a question';
      list.appendChild(li);
    }
  }

  // ---- playback
  function tune(c) {
    nowEl.textContent = 'opening ' + (c.name || '') + '\\u2026';
    player.hidden = false;
    var creds_ = creds();
    fetch('/api/tuner/tune', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: c.url, label: c.name || '',
                            username: creds_.user || '', password: creds_.pass || ''})
    }).then(function (r) { return r.json().then(function (j) { return {ok: r.ok, j: j}; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.j.detail || res.j.error || 'could not tune');
        var src = '/api/tuner/' + res.j.playlist;
        nowEl.textContent = (c.name || '') + '  \\u00b7  ' + res.j.state;
        play(src);
      })
      .catch(function (e) { nowEl.textContent = 'could not tune: ' + (e.message || e); });
  }

  function play(src) {
    if (hls) { hls.destroy(); hls = null; }
    // Safari plays HLS natively; Chrome and Firefox need hls.js, which is why it is vendored.
    if (video.canPlayType('application/vnd.apple.mpegurl')) { video.src = src; video.play(); return; }
    if (!window.Hls || !window.Hls.isSupported()) {
      nowEl.textContent = 'this browser cannot play HLS and hls.js did not load';
      return;
    }
    hls = new window.Hls({lowLatencyMode: false});
    hls.loadSource(src); hls.attachMedia(video);
    hls.on(window.Hls.Events.MANIFEST_PARSED, function () { video.play(); });
    hls.on(window.Hls.Events.ERROR, function (_e, d) {
      if (d && d.fatal) nowEl.textContent = 'playback error: ' + d.type + ' / ' + d.details;
    });
  }

  // ---- the model turns a question into a filter. It never sees the playlist.
  var askBox = document.getElementById('tnask');
  document.getElementById('tnaskgo').addEventListener('click', ask);
  askBox.addEventListener('keydown', function (e) { if (e.key === 'Enter') ask(); });
  document.getElementById('tnaskclear').addEventListener('click', function () {
    aiFilter = null; askBox.value = ''; askWhy.textContent = '';
    this.hidden = true; apply();
  });

  function plainFilter(q) {
    // Honest fallback: the user's own words, matched directly. Used when the model is busy
    // or returns something that will not parse, and always said out loud.
    var terms = q.toLowerCase().split(/[^a-z0-9]+/).filter(function (t) { return t.length > 2; });
    return {match: terms, exclude: [], why: 'matched your words directly'};
  }

  function ask() {
    var q = askBox.value.trim();
    if (!q) return;
    askWhy.textContent = 'asking the model\\u2026';
    // A FLAT KEYWORD LIST, not JSON. Asking this 7B for a JSON object at temperature 0.2
    // makes it loop -- measured: it emitted {"match":["premier league","nfl","nba","mlb",
    // "f1","nfl","nba",... until it hit the token cap, so the object never closed and
    // nothing parsed. One line of comma-separated words it completes cleanly every time.
    // Small models are far better at a flat list than at nested structure; picking the
    // format the model can actually finish is the difference between this working and the
    // fallback firing on every request.
    var prompt = 'List the words to search for in a TV channel list to find: ' + q
      + '\\n\\nRules: reply with ONE line, at most 8 lowercase keywords, comma separated. '
      + 'No sentences, no repeats, no explanation.\\n\\nKeywords:';
    fetch('/api/chat', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt: prompt, temperature: 0.1, max_tokens: 64})
    }).then(function (r) {
      if (!r.ok) throw new Error('chat ' + r.status);
      return r.text();
    }).then(function (txt) {
      var out = '';
      txt.split('\\n').forEach(function (line) {
        if (line.indexOf('data:') !== 0) return;
        try { var j = JSON.parse(line.slice(5)); if (j.delta) out += j.delta; } catch (e) {}
      });
      var first = out.trim().split('\\n').filter(function (l) { return l.trim(); })[0] || '';
      var terms = first.split(',').map(function (t) {
        return t.trim().toLowerCase().replace(/^[^a-z0-9]+|[^a-z0-9 ]+$/g, '');
      }).filter(function (t) { return t.length > 1 && t.length < 24; }).slice(0, 12);
      if (!terms.length) throw new Error('no usable keywords');
      aiFilter = {match: terms, exclude: [],
                  why: 'the model read your question and searched for: ' + terms.join(', ')};
      finishAsk();
    }).catch(function (e) {
      aiFilter = plainFilter(q);
      aiFilter.why = 'the model could not be used (' + (e.message || e) + '), so this '
                   + 'matched your words directly';
      finishAsk();
    });
  }

  function finishAsk() {
    document.getElementById('tnaskclear').hidden = false;
    apply();
    askWhy.textContent = aiFilter.why + '  \\u2014  ' + view.length + ' of ' + all.length
                       + ' channels';
  }
})();
</script>"""



def main() -> int:
    print("building surface pages:")
    page("chat.html", gpu=True, surface="Chat",
         title="SyMoNeuRaL Chat — talk to the box",
         desc="A 7B running locally on an RTX 5070 Ti. Nothing leaves the machine.",
         icon="/chat-64.png", eyebrow="Live surface",
         heading="Talk to the box.",
         lede="This is a 7B at Q4 on the RTX 5070 Ti described on the home page, streaming "
              "tokens as the card produces them. The tokens-per-second under each answer is "
              "measured, not claimed.",
         body=CHAT_BODY, script=CHAT_JS)

    page("image.html", gpu=True, surface="Image",
         title="SyMoNeuRaL Image — make it draw",
         desc="FLUX.1-schnell in four steps, rendered locally on a consumer GPU.",
         icon="/image-64.png", eyebrow="Live surface",
         heading="Make it draw something.",
         lede="FLUX.1-schnell, quantized to q4_k and rendered on the card in this machine. "
              "Every image below prints the wall-clock it actually took.",
         body=IMAGE_BODY, script=IMAGE_JS)

    page("ravencalc.html", gpu=False, surface="RavenCalc",
         title="SyMoNeuRaL RavenCalc — exact mathematics",
         desc="SymPy-powered symbolic computation that checks its own work.",
         icon="/calc-64.png", eyebrow="Live surface · CPU",
         heading="Mathematics, computed rather than predicted.",
         lede="RavenCalc is SymPy underneath, not a language model guessing at algebra. It "
              "runs on the CPU, so it is the one surface here that never waits for the GPU.",
         body=CALC_BODY, script=CALC_JS)

    page("remix.html", gpu=True, surface="Remix",
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

    page("tuner.html", gpu=False, surface="Tuner",
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
