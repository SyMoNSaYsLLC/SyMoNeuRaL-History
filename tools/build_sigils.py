#!/usr/bin/env python3
"""Generate site/sigils.html -- the SyMoNeuRaL Sigils surface page.

    python3 tools/build_sigils.py

**Writes exactly one file** and rewrites the whole of it, so running it twice produces a
byte-identical page. There are no BEGIN/END markers here on purpose: markers are the
contract for a generator that edits a *shared* file, and the failure they exist to prevent
-- a second block appended because a marker string drifted -- cannot happen to a generator
that owns its output outright. Nothing in this file reads the clock, the GPU or the API, for
the same reason: a figure fetched at build time would make the page differ between runs and
would also be a measurement presented without the date and command that produced it.

The header, nav, footer and live GPU panel are **imported** from `tools/build_pages.py`
rather than copied. That file exists precisely so five pages cannot drift apart, and a sixth
page with its own hand-maintained copy of the shell would be the drift it was written to
stop. It is imported, never called: `build_pages.page()` writes the other pages, and this
generator must not touch them.

Every figure on the page is a constant in this file, each with the date it was taken and the
command that took it. If a number here cannot be traced to a run on this box, it does not
belong on the page.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
assert (ROOT / "backend" / "api.py").is_file(), f"repo root not found at {ROOT}"
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "tools"))

import build_pages  # noqa: E402  -- for NAV, SHELL and the live GPU panel. Read, not run:
                    # importing it is safe (its work is behind __main__) and calling
                    # page() would rewrite pages this generator does not own.

#: Where the API is mounted. One constant, because the page and the wiring have to agree
#: and a prefix scattered through the JavaScript is how they stop agreeing.
API = "/api/sigils"

# --------------------------------------------------------------------- measurements
#
# Taken on this box on 2026-08-17. RTX 5070 Ti, 15.92 GiB; i9-10900KF for the CPU work.
# The renders were driven through this surface's own code path:
#
#   python3 - <<'PY'   # backend/apps/sigils/render.py + matte.py, 8 subjects x 2 fields
#   ... render.run(render.build_argv(prompt, raw, seed, steps=4, size=512)) ...
#
# Sixteen renders: eight subject types (animal, object, person, dark, light, thin/spindly,
# text-heavy, warm) at fixed seeds, rendered once against each field colour so a failure
# could be attributed to keying or to the colour, not to both at once.
TRIAL = {
    "renders": 16,
    "subjects": 8,
    "steps": 4,
    "size": 512,
    # Engine wall-clock, lock wait excluded. NOT scaled from the 768-canvas figure
    # elsewhere on this site: step count, attention and tiling do not scale with area.
    "render_lo": 9.5,
    "render_hi": 11.3,
    "render_median": 9.6,
    # Decode + key + despill + feather + RGBA encode, timed end to end in the serving
    # interpreter over the same sixteen files.
    "matte_lo": 0.10,
    "matte_hi": 0.16,
    "matte_median": 0.12,
    "png_lo": 208,
    "png_hi": 371,
    "png_median": 272,
    "pass_magenta": 8,
    "pass_green": 8,
    "transparent_lo": 0.56,
    "transparent_hi": 0.92,
    # What the engine actually painted when asked for a flat #FF00FF field, as the range of
    # the eight measured fields. Not one of them is within 150 counts of the colour the
    # prompt named, and the blue channel misses by ~150 on its own.
    "field_seen": "(243, 1, 98) to (252, 67, 114)",
}

#: Apple's Messages sticker size cap. Vendor -- Human Interface Guidelines, messaging
#: extensions. A maximum *pixel* dimension is widely repeated alongside it, but the only
#: source found for that was a developer-forum thread rather than Apple's own guidance, so
#: it is not quoted here at all: an unverified number dressed as a specification is the
#: exact error this site's labelling rules exist to catch.
APPLE_CAP_KB = 500


def measured(text: str) -> str:
    return f'<span class="sg-tag sg-measured">measured</span> {text}'


def vendor(text: str) -> str:
    return f'<span class="sg-tag sg-vendor">vendor</span> {text}'


# --------------------------------------------------------------------- page CSS
#
# Every class here is prefixed `sg-`. That is not tidiness, it is the fix for a bug this
# site has now had four times: `.bar` collapsed the site header to 7px sitewide, `.live`
# restyled the control-board legend from a nav badge, and `#console .sub` outranked
# `.mod .sub` and rendered a footnote larger than the sentence above it. There are also no
# descendant rules of the shape `#sigils .something` here, because that is the shape that
# outranks a shared component rule from another file.
#
# There is no `text-overflow` rule anywhere in this file and there must never be one. A
# prompt, a licence attribution or a reading cut off with an ellipsis is data loss with
# extra steps; long strings wrap instead, which is what `overflow-wrap` below is for.
CSS = """
.sg-fields{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 2px}
.sg-field{flex:1 1 120px;display:flex;align-items:center;gap:8px;padding:8px 10px;
  border:1px solid var(--line);border-radius:8px;background:var(--panel2);cursor:pointer;
  font-size:13px;color:var(--fg)}
.sg-field[aria-pressed="true"]{border-color:var(--accent)}
.sg-swatch{width:14px;height:14px;border-radius:3px;flex:0 0 auto;border:1px solid var(--line)}
.sg-swatch-magenta{background:#FF00FF}
.sg-swatch-green{background:#00FF00}
.sg-packs{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 0}
.sg-pack{padding:6px 10px;border:1px solid var(--line);border-radius:999px;
  background:var(--panel2);color:var(--fg);font-size:12.5px;cursor:pointer;
  text-align:left;overflow-wrap:anywhere}
.sg-packhead{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);
  margin:14px 0 2px}
.sg-sheet{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}
.sg-card{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--panel2)}
/* The checkerboard is the honest way to show an alpha channel: on a flat panel a keyed
   sticker and an unkeyed one look identical. Drawn in CSS -- no image request. */
.sg-plate{aspect-ratio:1/1;display:grid;place-items:center;
  background-color:#e9e9ea;
  background-image:linear-gradient(45deg,#c9c9cc 25%,transparent 25%,transparent 75%,#c9c9cc 75%),
                   linear-gradient(45deg,#c9c9cc 25%,transparent 25%,transparent 75%,#c9c9cc 75%);
  background-size:20px 20px;background-position:0 0,10px 10px}
.sg-plate img{width:100%;height:100%;object-fit:contain;display:block}
.sg-note{padding:10px 12px;border-top:1px solid var(--line);font-size:12.5px;
  color:var(--dim);overflow-wrap:anywhere}
.sg-readings{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:8px 0 0;
  font-size:12.5px}
.sg-readings dt{color:var(--faint)}
.sg-readings dd{margin:0;color:var(--fg);overflow-wrap:anywhere}
.sg-warn{color:var(--accent);font-size:12.5px;margin:8px 0 0}
.sg-tag{display:inline-block;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
  padding:1px 6px;border-radius:999px;border:1px solid var(--line);color:var(--dim);
  margin-right:6px;white-space:nowrap}
.sg-measured{border-color:var(--accent);color:var(--accent)}
.sg-facts{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:10px}
.sg-facts th,.sg-facts td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);
  vertical-align:top;overflow-wrap:anywhere}
.sg-facts th{color:var(--dim);font-weight:600}
.sg-scroll{overflow-x:auto}
/* On a phone the two-column table is 465px wide against a 390px viewport -- measured in a
   browser, not guessed. The fix is to stack the header above its cell so every word still
   fits and every word is still there. Truncating the cell would be the same data loss as
   an ellipsis rule, and putting the table behind a sideways scroll hides content behind a
   gesture nobody knows to make. */
@media (max-width:640px){
  .sg-facts,.sg-facts tbody,.sg-facts tr,.sg-facts th,.sg-facts td{display:block;width:auto}
  .sg-facts th{border-bottom:0;padding-bottom:0}
  .sg-facts td{padding-top:4px}
}
.sg-suffix{display:block;padding:10px 12px;border:1px solid var(--line);border-radius:8px;
  background:var(--panel2);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:12.5px;line-height:1.55;overflow-wrap:anywhere;white-space:pre-wrap}
.sg-empty{padding:40px 20px;text-align:center;color:var(--dim);font-size:13.5px;
  border:1px dashed var(--line);border-radius:10px;grid-column:1/-1}
"""


def body() -> str:
    """The middle of the page. Everything measured carries its label and its provenance."""
    gpu = build_pages.gpu_panel(True, "Sigils")
    facts = "\n".join([
        f"""          <tr><th>Render, 512&nbsp;px, four steps</th>
            <td>{measured(f"{TRIAL['render_lo']}&ndash;{TRIAL['render_hi']}&nbsp;s")} of engine
            wall-clock across {TRIAL['renders']} renders on 2026-08-17, median
            {TRIAL['render_median']}&nbsp;s, waiting for the card excluded. Not scaled from the 768&nbsp;px figure elsewhere on this site &mdash;
            step count, attention and tiling do not scale with area.</td></tr>""",
        f"""          <tr><th>Cutting the background out</th>
            <td>{measured(f"{TRIAL['matte_lo']}&ndash;{TRIAL['matte_hi']}&nbsp;s")} on the CPU,
            median {TRIAL['matte_median']}&nbsp;s, for the whole post-render step: decode,
            key, despill, feather and re-encode with an alpha channel. It runs <em>after</em> the GPU lock is handed back, so it costs
            the next surface in the queue nothing.</td></tr>""",
        f"""          <tr><th>Sticker file size</th>
            <td>{measured(f"{TRIAL['png_lo']}&ndash;{TRIAL['png_hi']}&nbsp;KiB")} across the
            same {TRIAL['renders']} renders, median {TRIAL['png_median']}&nbsp;KiB, against
            {vendor(f"a {APPLE_CAP_KB}&nbsp;KB per-sticker cap")} in Apple's Human Interface
            Guidelines for Messages. Every one of the sixteen came in under it, which is a
            result on these sixteen and not a guarantee about the next one.</td></tr>""",
        f"""          <tr><th>How much of the frame ends up transparent</th>
            <td>{measured(f"{int(TRIAL['transparent_lo'] * 100)}&ndash;{int(TRIAL['transparent_hi'] * 100)}%")}
            of pixels. The figure comes back with every sticker, because a cut that failed
            produces a file that decodes perfectly and is a solid square &mdash; and a number
            is the only thing that tells those apart without looking.</td></tr>""",
        f"""          <tr><th>Did the cut work?</th>
            <td>{measured(f"{TRIAL['pass_magenta']}/{TRIAL['subjects']} on the pink field and "
                          f"{TRIAL['pass_green']}/{TRIAL['subjects']} on the green")},
            over eight subject types &mdash; animal, object, person, dark, light, spindly,
            text-heavy and warm-coloured &mdash; at fixed seeds, each rendered once against
            each field so a failure could be blamed on the right thing. Sixteen renders is a
            small sample and is quoted as one.</td></tr>""",
    ])

    return f"""    <div class="pgwrap">
      <div class="stage">
        <div class="head" id="sg-head"><s></s>SyMoNeuRaL Sigils
          <span class="grow">idle</span></div>
        <div class="body">
          <div class="sg-sheet" id="sg-sheet">
            <div class="sg-empty" id="sg-empty">
              Say what the sticker should be of. One subject, no scene &mdash; the background
              is removed, so anything behind the subject is thrown away rather than drawn.
            </div>
          </div>
        </div>
        <form class="composer" id="form">
          <textarea id="prompt" rows="3" maxlength="100000"
                    placeholder="a raven perched, wings folded"></textarea>
          <button class="cta" id="send" type="submit">Make a sigil</button>
        </form>
      </div>

      <aside class="panel">
        {gpu}
        <h3>Field colour</h3>
        <div class="sg-fields" id="sg-field" role="group" aria-label="Field colour">
          <button type="button" class="sg-field" data-v="magenta" aria-pressed="true">
            <span class="sg-swatch sg-swatch-magenta"></span>pink field</button>
          <button type="button" class="sg-field" data-v="green" aria-pressed="false">
            <span class="sg-swatch sg-swatch-green"></span>green field</button>
        </div>
        <p class="hint">
          The subject is drawn on a flat field and that field is cut away afterwards. Green is
          the film industry's default because it sits far from skin and warm tones; pink sits
          far from foliage. Neither wins on every subject, so both are here and both were
          measured.
        </p>

        <h3>Parameters</h3>
        <div class="ctl">
          <label for="steps">Steps <b id="sg-stepsv">4</b></label>
          <input type="range" id="steps" min="1" max="8" step="1" value="4">
        </div>
        <div class="ctl">
          <label for="seed">Seed <b id="sg-seedlock">random</b></label>
          <input type="number" id="seed" min="0" max="2147483647"
                 placeholder="leave blank for random">
        </div>
        <p class="hint">
          512&nbsp;px square. The engine is distilled for four steps; more costs time and
          buys little, but the ceiling is yours to find.
        </p>
        <p class="hint" id="sg-stat">&nbsp;</p>
      </aside>
    </div>

    <h2 id="prompt-suffix" style="margin-top:40px">What gets added to what you type</h2>
    <p>
      This surface rewrites your prompt, so it shows you the rewrite. Your subject goes in
      front; this goes on the end of every request, and it is the whole reason the background
      can be removed at all &mdash; asking for &ldquo;no background&rdquo; produces nothing
      useful, because the engine has no concept of absence and will draw <em>something</em>.
      Naming a flat colour gives the cut something to find.
    </p>
    <code class="sg-suffix" id="sg-suffix">&hellip;, sticker illustration, single subject,
centred, thick clean outline, flat vector shading, no scene, no shadow, no text,
isolated on a solid flat &lt;field&gt; background, no gradient</code>
    <p class="hint" id="sg-suffix-note">
      Shown from a static copy until the surface answers; the live text above is whatever the
      API actually sends.
    </p>

    <h2 style="margin-top:36px">Themed packs</h2>
    <p>
      Starting points, and nothing more &mdash; no separate model, no curation of what else
      may be asked for. They exist because &ldquo;what do I type&rdquo; is the real first
      obstacle on a surface like this.
    </p>
    <div id="sg-packlist"></div>

    <h2 style="margin-top:36px">What this actually costs, on this machine</h2>
    <div class="sg-scroll">
      <table class="sg-facts">
        <tbody>
{facts}
        </tbody>
      </table>
    </div>
    <p class="hint">
      <span class="sg-tag sg-measured">measured</span> means taken on this box, on the date
      stated. <span class="sg-tag sg-vendor">vendor</span> means read off a publisher's
      specification. Nothing on this page is a projection, and nothing here is a price:
      pricing questions go to
      <a href="mailto:symonsayadmin@symoneural.com">symonsayadmin@symoneural.com</a>.
    </p>

    <details style="margin-top:26px">
      <summary>How the transparency is made, and the two things that went wrong first</summary>
      <p>
        The engine returns three channels and has no transparency output of any kind, so the
        fourth channel is made here: the subject is rendered on a flat field, the field is
        measured, and every region of that colour <em>connected to the frame edge</em> is
        made transparent. The connection test is what stops a hole being punched through the
        subject when it legitimately contains the field colour &mdash; an eye, a highlight, a
        gap between an arm and a body. Edge pixels that picked up the field are corrected
        before the transparency is attached, because otherwise the sticker wears a coloured
        halo the moment it lands on a white message bubble.
      </p>
      <p>
        <strong>The field colour is measured, not assumed.</strong> The prompt asks for a
        flat <code>#FF00FF</code>. Asked for exactly that, the engine painted
        <code>{TRIAL['field_seen']}</code> &mdash; a hot pink &mdash; consistently, on every
        subject. Cutting against the colour that was <em>requested</em> matched nothing at
        all: the first sixteen renders came back 0% transparent, which is a file that decodes
        perfectly and is worthless. The cut now reads the field off the render's own border,
        and reports what it found with every sticker.
      </p>
      <p>
        <strong>The GPU lock could not be taken the recommended way.</strong> This box hands
        the card to one surface at a time through a governor, and the recommended form wraps
        the job so the card is returned even on a crash. That form kills this particular job:
        making room for a new tenant works by matching the previous tenant's command line,
        and the wrapper's own command line contains the engine's name, so the governor
        terminated the process that was running the governor &mdash; silently, sixteen times,
        while logging a successful handover. The lock is now taken and released explicitly,
        always naming this surface, and always returned even when a render fails.
      </p>
      <p>
        <strong>What it still gets wrong.</strong> The connection test cannot tell a hole in
        the subject from detail inside it, so background trapped <em>inside</em> a shape
        &mdash; the middle of a coiled cable, the gap inside a handle &mdash; stays opaque
        and comes back as a coloured patch. That is the deliberate trade: the alternative
        cuts a hole through every eye and every highlight. It showed up on 2 of the
        {TRIAL['renders']} test renders, both of them the same coiled-cable subject, and the
        fix today is to pick a subject without an enclosed gap.
      </p>
      <p>
        Both of those are on this page rather than quietly fixed because negative results are
        the ones worth publishing: they are what the next person needs and what a brochure
        would leave out.
      </p>
    </details>

    <details style="margin-top:14px">
      <summary>What a sticker file carries, and how long the link lasts</summary>
      <p>
        Homepage art on this site carries a printed bar naming the model, size and seed. A
        sticker does not: a caption strip burned into the artwork is not a sticker. The same
        facts ride inside the PNG's metadata instead &mdash; software, model, seed, steps,
        canvas, field colour and the full prompt &mdash; so a sticker saved to a phone still
        knows how it was made and not one pixel of it is defaced.
      </p>
      <p>
        <strong>The link is temporary and the response says so.</strong> Renders on this box
        are kept to the newest sixty and then deleted, because a public endpoint writing a
        few hundred kilobytes per request fills a disk quietly and takes the whole site down
        with it. Keep the file, not the URL.
      </p>
    </details>"""


SCRIPT = """<script>
// The Sigils surface. Everything shown here is a real reading from a real response:
// there is no placeholder sticker, no sample gallery and no activity light that is not
// driven by an actual request.
const SG_API = '""" + API + """';
const sgSheet = $('#sg-sheet'), sgHead = $('#sg-head'), sgSend = $('#send');
let sgField = 'magenta', sgFirst = true;

$('#steps').addEventListener('input', e => $('#sg-stepsv').textContent = e.target.value);
$('#seed').addEventListener('input', e =>
  $('#sg-seedlock').textContent = e.target.value === '' ? 'random' : 'locked');
$('#sg-field').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  sgField = b.dataset.v;
  [...e.currentTarget.children].forEach(x => x.setAttribute('aria-pressed', x === b));
});

// Packs and the prompt suffix come from the surface itself rather than being duplicated
// into this page, so the text shown as "what gets added" cannot drift from what is sent.
(async () => {
  try {
    const r = await fetch(SG_API + '/packs');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const doc = await r.json();
    const box = $('#sg-packlist');
    box.textContent = '';
    Object.keys(doc.packs).sort().forEach(name => {
      const h = document.createElement('p');
      h.className = 'sg-packhead';
      h.textContent = name;
      const row = document.createElement('div');
      row.className = 'sg-packs';
      doc.packs[name].forEach(text => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'sg-pack';
        b.textContent = text;
        b.addEventListener('click', () => {
          $('#prompt').value = text;
          $('#prompt').focus();
        });
        row.appendChild(b);
      });
      box.appendChild(h);
      box.appendChild(row);
    });
    $('#sg-suffix').textContent = '\\u2026, ' + doc.suffix
      .replace('{key}', sgField).replace('{hex}', sgField === 'green' ? '00FF00' : 'FF00FF');
    $('#sg-suffix-note').textContent =
      'Read from the surface just now, so it is what the API sends.';
  } catch (err) {
    $('#sg-packlist').textContent = '';
    $('#sg-suffix-note').textContent =
      'The surface did not answer (' + err.message + '), so the text above is a static copy '
      + 'and the packs are unavailable.';
  }
})();

function sgLine(dl, key, value) {
  const dt = document.createElement('dt'); dt.textContent = key;
  const dd = document.createElement('dd'); dd.textContent = value;
  dl.appendChild(dt); dl.appendChild(dd);
}

$('#form').addEventListener('submit', async e => {
  e.preventDefault();
  const subject = $('#prompt').value.trim();
  if (!subject) return;
  sgSend.disabled = true;
  status(sgHead, 'holding the card for one render', true);

  const card = document.createElement('div');
  card.className = 'sg-card';
  card.innerHTML = '<div class="sg-plate">' +
    '<span style="font-size:13px;color:#555">rendering\\u2026</span></div>' +
    '<div class="sg-note"></div>';
  $('.sg-note', card).textContent = subject;
  if (sgFirst) { sgSheet.textContent = ''; sgFirst = false; }
  sgSheet.prepend(card);

  try {
    const seedRaw = $('#seed').value;
    const doc = await api(SG_API + '/render', {
      prompt: subject,
      key: sgField,
      steps: parseInt($('#steps').value, 10),
      seed: seedRaw === '' ? null : parseInt(seedRaw, 10)
    });
    const plate = $('.sg-plate', card);
    plate.textContent = '';
    const img = document.createElement('img');
    img.alt = subject;
    img.src = doc.url;
    plate.appendChild(img);

    const note = $('.sg-note', card);
    note.textContent = '';
    const dl = document.createElement('dl');
    dl.className = 'sg-readings';
    sgLine(dl, 'subject', doc.subject);
    sgLine(dl, 'render', doc.render_seconds + ' s on the card');
    sgLine(dl, 'queued', doc.queued_seconds + ' s behind another surface');
    sgLine(dl, 'cut', doc.matte_seconds + ' s on the CPU, lock already released');
    sgLine(dl, 'transparent', Math.round(doc.transparent_fraction * 1000) / 10 + '% of pixels');
    sgLine(dl, 'field found', '(' + doc.field_rgb.join(', ') + ') for the ' + doc.key + ' field');
    sgLine(dl, 'file', Math.round(doc.bytes / 1024) + ' KiB');
    sgLine(dl, 'seed', String(doc.seed));
    sgLine(dl, 'model', doc.model);
    note.appendChild(dl);
    if (doc.degenerate) {
      const warn = document.createElement('p');
      warn.className = 'sg-warn';
      warn.textContent = 'This one did not cut: almost the whole frame came out on one side '
        + 'of the line. Try the other field colour, or a simpler subject.';
      note.appendChild(warn);
    }
    const link = document.createElement('p');
    link.className = 'sg-warn';
    link.style.color = 'var(--dim)';
    link.textContent = doc.note;
    note.appendChild(link);
    status(sgHead, 'idle', false);
    $('#sg-stat').textContent = 'last: ' + doc.render_seconds + ' s render, '
      + doc.matte_seconds + ' s cut';
  } catch (err) {
    $('.sg-plate', card).textContent = '';
    const note = $('.sg-note', card);
    note.textContent = 'That did not work: ' + err.message;
    status(sgHead, 'idle', false);
  } finally {
    sgSend.disabled = false;
  }
});
</script>"""


def main() -> int:
    html_out = build_pages.SHELL.replace("@@NAV@@", build_pages.NAV)
    fields = {
        "TITLE": "SyMoNeuRaL Sigils — stickers with a real transparent background",
        "DESC": ("Small themed stickers, one subject, cut out of their background on this "
                 "machine. Every figure on the page was measured here."),
        "ICON": "/image-64.png",
        "EYEBROW": "Live surface · GPU",
        "HEADING": "Stickers, cut out properly.",
        "LEDE": ("One subject, hard edges, and a genuine alpha channel — not a white square "
                 "pretending to be transparent. The engine cannot produce transparency at "
                 "all, so the subject is drawn on a flat field and that field is measured "
                 "and cut away here, on the CPU, after the card has already been handed to "
                 "whoever is next in the queue."),
        "BODY": body(),
        "SCRIPT": f"<style>{CSS}</style>\n{SCRIPT}",
    }
    for key, value in fields.items():
        html_out = html_out.replace(f"@@{key}@@", value)
    # A leftover marker means the shell grew a field this generator does not fill, which
    # would ship the literal '@@SOMETHING@@' to a visitor.
    assert "@@" not in html_out, "unsubstituted placeholder left in the page"
    assert "text-overflow" not in html_out, "an ellipsis rule reached the page"
    (SITE / "sigils.html").write_text(html_out)
    print("  sigils.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
