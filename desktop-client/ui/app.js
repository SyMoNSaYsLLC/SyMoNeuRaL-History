// SyMoNeuRaL Desktop Client -- the page half.
//
// This file names API *paths* and never a host. The host lives in src-tauri/src/main.rs as a
// constant the page cannot reach, so there is no base URL to configure here, nothing to point
// at a remote box, and no way for an edit to this file to change where a request goes. That
// is deliberate and backend/apps/test_desktop_client.py asserts it: any host-looking literal
// in this file would be either dead or a lie.
//
// Everything below goes through invoke(). There is no fetch() in this program -- backend/api.py
// mounts no CORS middleware and should not gain one to suit a desktop client, since `/api*` is
// proxied to the public internet.
//
// The rules this file is written to keep, from .claude/CLAUDE.md:
//   * Label every figure measured / vendor / projected. Every number rendered here is a
//     reading the server took and sent; none is computed on this side. `tok_per_s` especially
//     is forwarded, never recomputed -- a rate derived from a browser clock would be a
//     different quantity wearing the same name.
//   * No decorative status indicators. The dot is set only by a completed /api/status read.
//   * Never present a projection as a result. RavenCalc's `check.passed` is three-valued and
//     `null` renders as "unconfirmed" -- reported, not rounded up to a tick.

const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

/** Everything user-supplied reaches the DOM as textContent, never as HTML. */
function field(parent, key, value) {
  const row = el("div", "field");
  row.append(el("span", "k", key), el("span", "v", String(value)));
  parent.append(row);
  return row;
}

function fail(where, message) {
  const box = el("div", "err", String(message));
  where.append(box);
  // The transcript is only scrolled to the bottom when a turn is sent and on each delta, and
  // an error arrives after both. Measured with a 100 kB prompt: the 422 rendered twelve wheel
  // clicks below the fold, so the window showed a sent turn, no reply and no error -- which
  // reads as "still thinking" rather than as "refused". An error nobody scrolls to is an
  // error nobody was shown.
  box.scrollIntoView({ block: "nearest" });
}

// ------------------------------------------------------------------ tabs

document.querySelectorAll('[role="tab"]').forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll('[role="tab"]').forEach((other) => {
      const on = other === tab;
      other.setAttribute("aria-selected", String(on));
      const panel = $("panel-" + other.dataset.panel);
      if (on) panel.setAttribute("data-open", "1");
      else panel.removeAttribute("data-open");
    });
  });
});

// ------------------------------------------------------------------ /api/status
//
// The connection indicator. `unread` is the state the dot starts in and it is not a colour --
// a filled dot before a read has completed would be exactly the decorative indicator the
// house rules forbid. The three live states come from the units' own `state` field, which is
// the same reading the rack on the site renders.

async function readStatus() {
  const dot = $("dot");
  const text = $("conn-text");
  text.textContent = "reading...";
  try {
    const status = await invoke("api_get", { path: "/api/status" });
    const units = Array.isArray(status.units) ? status.units : [];
    const mine = units.filter((u) => ["chat", "image", "ravencalc"].includes(u.id));
    const offline = mine.filter((u) => u.state === "offline");

    if (!mine.length) {
      dot.dataset.state = "partial";
      text.textContent = "API answered, but reported none of chat/image/ravencalc";
    } else if (!offline.length) {
      dot.dataset.state = "up";
      text.textContent = mine.map((u) => `${u.id} ${u.state}`).join(" · ");
    } else {
      dot.dataset.state = "partial";
      text.textContent =
        mine.map((u) => `${u.id} ${u.state}`).join(" · ") +
        ` — ${offline.length} offline (weights or engine missing)`;
    }
  } catch (err) {
    dot.dataset.state = "down";
    text.textContent = String(err);
  }
}

$("refresh").addEventListener("click", readStatus);
readStatus();

// ------------------------------------------------------------------ /api/chat
//
// Server-Sent Events. The Rust side parses the stream and re-emits each frame on the event
// name passed in, unchanged; this listener does the rendering. Frames, per backend/api.py:
//   {"assist": {...}}  optional, once, before any delta -- RavenCalc got there first
//   {"delta": "..."}   zero or more
//   {"done": true, "tokens", "seconds", "tok_per_s", "model", "adapter"}
//   {"error": "..."}   inside a 200 stream, because the response has already begun
//
// The transcript is held here and sent back as `history` on the next turn. That matches the
// endpoint's contract: the client holds the transcript and the server stores nothing.

const history = [];
const CHAT_EVENT = "chat:main";

let streaming = null; // the .body node currently being appended to

// The prompt of the turn in flight. It is held here rather than pushed to `history` at send
// time because a turn can fail two different ways -- an {"error"} frame inside a 200 stream,
// or a rejected invoke -- and either one would otherwise leave a user turn in the transcript
// with no assistant reply after it. The next send would then carry two consecutive user roles
// to a chat template that does not expect them. A turn joins the history when it finishes.
let pendingUser = null;

listen(CHAT_EVENT, (event) => {
  const frame = event.payload || {};
  if (!streaming) return;

  if (frame.error) {
    fail(streaming.parentElement, frame.error);
    return;
  }

  if (frame.assist) {
    // RavenCalc answered exactly, on the CPU, inside the time the GPU spent loading. Shown
    // because it is a real second opinion arriving from a different engine -- and shown with
    // its own check state, on the same three-valued rule as the RavenCalc panel.
    const a = frame.assist;
    const box = el("div", "assist");
    box.append(el("div", null, `RavenCalc answered first — ${a.operation ?? "?"}`));
    if (a.input !== undefined && a.input !== null) field(box, "input", a.input);
    if (a.result !== undefined && a.result !== null) field(box, "result", a.result);
    const verdict = checkWords(a.check);
    if (verdict) {
      const row = field(box, "check", verdict.text);
      row.querySelector(".v").classList.add("check", verdict.cls);
    }
    if (a.ms !== undefined && a.ms !== null) field(box, "took", `${a.ms} ms (measured)`);
    streaming.parentElement.insertBefore(box, streaming);
    return;
  }

  if (typeof frame.delta === "string") {
    streaming.textContent += frame.delta;
    $("transcript").scrollTop = $("transcript").scrollHeight;
    return;
  }

  if (frame.done) {
    // Both halves land together, or neither does. See `pendingUser`.
    history.push(
      { role: "user", content: pendingUser },
      { role: "assistant", content: streaming.textContent },
    );
    pendingUser = null;
    // Every figure on this line is the server's. `tok_per_s` is the value it sent; this file
    // does not divide tokens by seconds to produce its own.
    const bits = [
      `${frame.tokens} tokens`,
      `${frame.seconds} s`,
      frame.tok_per_s === null || frame.tok_per_s === undefined
        ? "rate not reported"
        : `${frame.tok_per_s} tok/s`,
      "measured server-side",
    ];
    if (frame.model) bits.push(frame.model);
    if (frame.adapter) bits.push("fine-tuned adapter loaded");
    streaming.parentElement.append(el("div", "meta", bits.join(" · ")));
    streaming = null;
    $("chat-send").disabled = false;
  }
});

$("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const prompt = $("chat-prompt").value.trim();
  if (!prompt || streaming) return;

  const transcript = $("transcript");
  const you = el("div", "turn you");
  you.append(el("div", "who", "you"), el("div", "body", prompt));
  transcript.append(you);

  const them = el("div", "turn them");
  const body = el("div", "body", "");
  them.append(el("div", "who", "symoneural chat"), body);
  transcript.append(them);
  transcript.scrollTop = transcript.scrollHeight;

  streaming = body;
  $("chat-send").disabled = true;
  $("chat-prompt").value = "";

  const sent = history.slice();
  pendingUser = prompt;

  try {
    await invoke("api_chat", {
      event: CHAT_EVENT,
      path: "/api/chat",
      body: {
        prompt,
        history: sent,
        temperature: Number($("chat-temp").value),
        max_tokens: Number($("chat-max").value),
      },
    });
  } catch (err) {
    fail(them, err);
  } finally {
    // The stream can end without a `done` frame if the connection drops mid-turn. Releasing
    // the button here rather than only in the done handler is what stops that from wedging
    // the panel with no way back.
    if (streaming) {
      streaming = null;
      pendingUser = null;
      $("chat-send").disabled = false;
    }
  }
});

// ------------------------------------------------------------------ /api/image
//
// Two calls, not one. /api/image answers with an ImageResult whose `url` is a path
// (/api/gen/<name>), and the bytes are a second fetch. That indirection is in the API on
// purpose -- a render is written to backend/output/ and served by the API, not copied into
// the webroot -- so the client follows it rather than assuming a file path.

$("image-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const prompt = $("image-prompt").value.trim();
  if (!prompt) return;
  const out = $("image-out");
  out.replaceChildren(el("div", "meta", "rendering — the card may be queued behind another surface"));
  $("image-send").disabled = true;

  const seed = $("image-seed").value.trim();
  try {
    const result = await invoke("api_post", {
      path: "/api/image",
      body: {
        prompt,
        steps: Number($("image-steps").value),
        size: Number($("image-size").value),
        ...(seed === "" ? {} : { seed: Number(seed) }),
      },
    });

    out.replaceChildren();

    // `url` comes back as /api/gen/<name>. Pulled through the Rust side as a data: URL so the
    // window's content-security-policy never has to name a network origin for img-src.
    if (typeof result.url === "string" && result.url.startsWith("/api/gen/")) {
      try {
        const data = await invoke("api_bytes", { path: result.url });
        const img = el("img");
        img.src = data;
        img.alt = prompt;
        out.append(img);
      } catch (err) {
        fail(out, `rendered, but the image did not load: ${err}`);
      }
    } else {
      fail(out, `unexpected url in the result: ${JSON.stringify(result.url)}`);
    }

    const meta = el("div");
    field(meta, "took", `${result.seconds} s (measured, queue excluded)`);
    field(meta, "seed", result.seed);
    field(meta, "steps", result.steps);
    field(meta, "size", `${result.size}x${result.size}`);
    field(meta, "model", result.model);
    field(meta, "bytes", result.bytes);
    field(meta, "path", result.url);
    out.append(meta);
  } catch (err) {
    out.replaceChildren();
    fail(out, err);
  } finally {
    $("image-send").disabled = false;
  }
});

// ------------------------------------------------------------------ /api/ravencalc
//
// The three-valued check is the whole point of this panel's rendering. From the endpoint's
// own docstring: "`check.passed` is three-valued. `null` means the check could not confirm
// the result, which is reported rather than rounded up to success."
//
// So there are three renderings and `unconfirmed` is its own state with its own colour. It
// must never collapse into either a tick or a cross -- an unconfirmed antiderivative is not
// a wrong one, and showing it as verified would be presenting a projection as a result.

function checkWords(check) {
  if (!check || check.performed !== true) return null;
  if (check.passed === true) return { cls: "passed", text: `verified — ${check.how}` };
  if (check.passed === false) return { cls: "failed", text: `check failed — ${check.how}` };
  return { cls: "unconfirmed", text: `unconfirmed — ${check.how}` };
}

$("calc-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const expression = $("calc-expr").value.trim();
  if (!expression) return;
  const out = $("calc-out");
  out.replaceChildren();
  $("calc-send").disabled = true;

  const point = $("calc-point").value.trim();
  try {
    const result = await invoke("api_post", {
      path: "/api/ravencalc",
      body: {
        expression,
        operation: $("calc-op").value,
        variable: $("calc-var").value.trim() || "x",
        ...(point === "" ? {} : { point }),
      },
    });

    const pre = el("pre", null, result.result?.text ?? "");
    out.append(pre);

    const meta = el("div");
    field(meta, "input", result.input?.text ?? "");

    const verdict = checkWords(result.check);
    if (verdict) {
      const row = field(meta, "check", verdict.text);
      row.querySelector(".v").classList.add("check", verdict.cls);
    } else {
      // performed:false is not a pass either. Say so rather than showing nothing, because a
      // blank space where a verdict should be reads as "fine".
      const row = field(meta, "check", "not performed — no cheap verification exists for this operation");
      row.querySelector(".v").classList.add("check", "unconfirmed");
    }

    field(meta, "exact", result.exact === true ? "yes" : "no");
    if (result.note) field(meta, "note", result.note);

    // Reported even when empty, and the empty case is the informative one: it says every
    // variable was treated as an arbitrary complex number.
    const assumed = result.assumed || {};
    const names = Object.keys(assumed);
    field(
      meta,
      "assumed",
      names.length
        ? names.map((n) => `${n}: ${assumed[n].join(", ")}`).join(" · ")
        : "nothing — every symbol treated as an arbitrary complex number"
    );
    field(meta, "engine", result.engine ?? "");
    field(meta, "took", `${result.seconds} s (measured, CPU — no GPU lock taken)`);
    out.append(meta);

    // Folded, not trimmed. The unambiguous form is long and is exactly the thing the house
    // rule says to put behind a <details> rather than cut with an ellipsis.
    if (result.result?.tree) {
      const details = el("details");
      details.append(el("summary", null, "exact tree (srepr) and LaTeX"));
      details.append(el("pre", null, result.result.tree));
      if (result.result.latex) details.append(el("pre", null, result.result.latex));
      out.append(details);
    }
  } catch (err) {
    fail(out, err);
  } finally {
    $("calc-send").disabled = false;
  }
});
