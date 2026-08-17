/* SyMoNeuRaL control board client.
 *
 * One socket drives every live element on the page: the rack units and the instrument
 * modules. It costs one upgrade handshake and one baseline snapshot, and after that the
 * server sends only what changed. An idle machine sends nothing at all -- which is most of
 * the time, and is the point.
 *
 * State lives here and gets patched in place. The server never re-sends a field that did
 * not move, so the client is the thing that knows the whole picture; the wire only ever
 * carries news. Falls back to conditional polling if the socket cannot be established,
 * because a proxy that will not upgrade should degrade to a working page rather than a
 * dead one.
 *
 * Served as a separate file on purpose: it is byte-identical across five pages, so the
 * browser fetches it once and reuses it. Inlining it would re-send the same 6 KB per page.
 */
(function () {
  'use strict';

  var state = null;          // the whole rack, patched in place
  var socket = null;
  var pollTimer = null;
  var etag = null;
  var retry = 0;
  var reconnectTimer = null;

  // ---------------------------------------------------------------- rendering

  var POWER =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" ' +
    'stroke-linecap="round"><path d="M12 3v9"/><path d="M6.6 6.6a8 8 0 1 0 10.8 0"/></svg>';
  var WORDS = {ready: 'ready', busy: 'busy', queued: 'queued', offline: 'offline'};
  // The bus plate names the hardware a surface actually runs on. It used to be
  // `u.bus === 'cpu' ? 'CPU' : 'GPU'`, which was fine while there were only two buses and
  // silently wrong the moment there were more -- an ASIC surface would have printed "GPU",
  // a plate on a page arguing that every reading is real, claiming the wrong hardware.
  // Anything unrecognised prints '--' rather than guessing.
  var BUSES = {gpu: 'GPU', cpu: 'CPU', asic: 'ASIC', net: 'NET'};
  function busLabel(b) { return BUSES[b] || '--'; }

  function el(id) { return document.getElementById(id); }
  function txt(id, value) { var n = el(id); if (n) n.textContent = value; }

  function leds(u) {
    var act = u.state === 'busy' ? 'led amber blink'
            : u.state === 'queued' ? 'led blue blink' : 'led';
    var pwr = u.state === 'offline' ? 'led' : 'led on';
    return '<span class="leds"><i class="' + pwr + '"></i><i class="' + act + '"></i>' +
           '<i class="led ' + (u.bus !== 'gpu' ? 'blue' : '') + '"></i></span>';
  }

  function renderRack() {
    var host = el('units');
    if (!host || !state) return;
    host.innerHTML = state.units.map(function (u) {
      return '<a class="unit" data-state="' + u.state + '" href="' + u.href + '">' +
        leds(u) +
        '<span class="pwr">' + POWER + '</span>' +
        '<span class="uname"><b>' + u.label + '</b><span>' + u.spec +
          ' &middot; ' + u.detail + '</span></span>' +
        '<span class="ubus">' + busLabel(u.bus) + '</span>' +
        '<span class="ustate"><span class="txt">' + (WORDS[u.state] || u.state) + '</span>' +
          '<span class="slot">' + u.slot + '</span></span>' +
        '<span class="scan"><i></i></span></a>';
    }).join('');
  }

  function meter(id, pct, warn) {
    var n = el(id);
    if (!n) return;
    n.firstElementChild.style.width = Math.max(0, Math.min(100, pct)) + '%';
    n.classList.toggle('warn', !!warn);
  }

  function renderConsole() {
    if (!state) return;
    var g = state.gpu || {};

    if (g.vram_free_mib != null && g.vram_total_mib) {
      txt('m-vram', (g.vram_free_mib / 1024).toFixed(1));
      var vn = el('m-vram');
      if (vn && !vn.querySelector('u')) vn.insertAdjacentHTML('beforeend', '<u>GiB</u>');
      meter('m-vrambar', g.vram_used_pct || 0, (g.vram_used_pct || 0) > 80);
    }
    if (g.power_w != null) {
      txt('m-pwr', g.power_w.toFixed(1));
      var pn = el('m-pwr');
      if (pn && !pn.querySelector('u')) pn.insertAdjacentHTML('beforeend', '<u>W</u>');
      meter('m-pwrbar', (g.power_w / 300) * 100, g.power_w > 240);
    }
    if (g.temp_c != null) {
      txt('m-temp', g.temp_c);
      var tn = el('m-temp');
      if (tn && !tn.querySelector('u')) tn.insertAdjacentHTML('beforeend', '<u>&deg;C</u>');
    }
    txt('m-holder', g.holder || 'idle');
    txt('m-queue', g.queued != null ? String(g.queued) : '0');

    // The rack chassis carries its own gauge ids. They were rendered and then never
    // written, so the chassis sat at "—" with both bars empty, directly beneath copy
    // saying the rack is live. Same data, second home.
    if (g.vram_total_mib) {
      txt('g-vram', (g.vram_free_mib / 1024).toFixed(1) + ' GiB free of ' +
                    (g.vram_total_mib / 1024).toFixed(2));
      meter('g-vrambar', g.vram_used_pct || 0, (g.vram_used_pct || 0) > 80);
    }
    if (g.power_w != null) {
      txt('g-pwr', g.power_w.toFixed(1) + ' W of 300');
      meter('g-pwrbar', (g.power_w / 300) * 100, g.power_w > 240);
    }
    if (g.temp_c != null) txt('g-temp', g.temp_c + ' \u00b0C');

    // The rack note doubles as the "someone else is using it" explanation.
    // Restore the explanation when the queue drains. Without an else branch the amber
    // "N waiting" banner was written once and never removed, so the page kept claiming a
    // queue long after the card went idle.
    var note = el('rack-note');
    if (note) {
      if (g.queued > 0) {
        note.innerHTML = '<strong style="color:var(--amber)">' + g.queued +
          ' job(s) waiting.</strong> One card, one job at a time &mdash; RavenCalc runs on ' +
          'the CPU and is still free.';
      } else if (note.dataset.original) {
        note.innerHTML = note.dataset.original;
      }
    }
  }

  function render() { renderRack(); renderConsole(); }

  // Keep the original wording so the queue banner can be undone rather than being a
  // one-way replacement.
  (function () {
    var note = el('rack-note');
    if (note && !note.dataset.original) note.dataset.original = note.innerHTML;
  })();

  function offline(reason) {
    var host = el('units');
    if (host) {
      host.innerHTML = '<div class="unit" data-state="offline" style="cursor:default">' +
        '<span class="leds"><i class="led"></i><i class="led"></i><i class="led"></i></span>' +
        '<span class="pwr">' + POWER + '</span>' +
        '<span class="uname"><b>Stack powered down</b><span>' + reason +
        ' &mdash; the rest of the site is unaffected</span></span>' +
        '<span class="ubus">--</span>' +
        '<span class="ustate"><span class="txt">offline</span><span class="slot">--</span></span>' +
        '</div>';
    }
    ['m-vram', 'm-pwr', 'm-temp', 'm-queue'].forEach(function (id) { txt(id, '--'); });
    txt('m-holder', 'offline');
    link('socket: offline');
  }

  function link(text) { txt('con-link', text); }

  // ---------------------------------------------------------------- patching

  function applyPatch(patch) {
    if (!state) return;
    if (patch.units) {
      // Addressed by id, never by position -- a positional patch silently corrupts the
      // display the day a unit is added or reordered. Iterate the PATCH, not our own list,
      // so a unit the server has newly added actually appears; the server already sends
      // whole objects for that case and we were discarding them.
      var byId = {};
      state.units.forEach(function (u) { byId[u.id] = u; });
      Object.keys(patch.units).forEach(function (id) {
        var change = patch.units[id];
        if (byId[id]) { for (var k in change) byId[id][k] = change[k]; }
        else if (change.label) { state.units.push(change); }
      });
    }
    if (patch.gpu) for (var k in patch.gpu) state.gpu[k] = patch.gpu[k];
  }

  // ---------------------------------------------------------------- transport

  function connect() {
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = proto + '//' + location.host + '/api/ws';
    try { socket = new WebSocket(url); }
    catch (e) { return startPolling(); }

    socket.onopen = function () {
      retry = 0; clearTimeout(reconnectTimer); reconnectTimer = null;
      link('socket: live'); stopPolling();
    };

    socket.onmessage = function (ev) {
      var msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (msg.t === 'welcome') {
        link('socket: live · proto ' + msg.proto);
      } else if (msg.t === 'rack') {
        state = {units: msg.units, gpu: msg.gpu, link: msg.link};
        render();
      } else if (msg.t === 'patch') {
        applyPatch(msg);
        render();
      } else if (msg.t === 'bus') {
        // An agent announcing what it did. Surfaced so a waiting visitor can see why.
        if (msg.event === 'queued' && msg.behind) {
          link('socket: live · ' + msg.from + ' waiting behind ' + msg.behind);
        } else if (msg.event === 'released') {
          link('socket: live');
        }
      }
    };

    socket.onclose = function () {
      socket = null;
      // Back off rather than hammering a box that may simply be switched off.
      retry = Math.min(retry + 1, 6);
      link('socket: reconnecting…');
      // Hold the handle. Without it, the visibility handler's `if (!socket) connect()`
      // fired a second connect while this one was still armed, and every close armed
      // another -- a hide/show cycle against a flapping backend multiplied connections
      // instead of replacing them.
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(function () {
        reconnectTimer = null;
        if (!document.hidden && !socket) connect();
      }, 1000 * retry);
      if (!document.hidden) startPolling();
    };

    socket.onerror = function () { try { socket.close(); } catch (e) {} };
  }

  // Fallback only. Conditional so an unchanged rack costs a bare 304 with no body.
  function poll() {
    var headers = etag ? {'If-None-Match': etag} : {};
    fetch('/api/status', {headers: headers, cache: 'no-store'})
      .then(function (r) {
        if (r.status === 304) return null;
        if (!r.ok) throw new Error('down');
        etag = r.headers.get('ETag');
        return r.json();
      })
      .then(function (data) { if (data) { state = data; render(); } })
      .catch(function () { offline('the live surfaces are off right now'); });
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(function () { if (!document.hidden) poll(); }, 4000);
    // The immediate poll needs the same guard as the interval. Closing the socket on
    // hide called startPolling(), which fired one request at a machine we had just
    // promised not to touch while the tab was hidden.
    if (!document.hidden) poll();
  }
  function stopPolling() { clearInterval(pollTimer); pollTimer = null; }

  // Nothing runs while the tab is hidden. This hits a real GPU on someone's desk.
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      stopPolling();
      clearTimeout(reconnectTimer); reconnectTimer = null;
      if (socket) { try { socket.close(); } catch (e) {} }
    } else if (!socket) {
      connect();
    }
  });

  // ---- the rack's fold control -------------------------------------------
  // In the one-screen layout the rack cannot fit with every unit's attribution on screen
  // (units 611px + chassis 71px against 584-589px of panel), so that line is collapsed by
  // default there and this puts it back. It is a fold, not a truncation: the text is intact
  // in the DOM and one click away, and the control is hidden entirely below the gate, where
  // the page scrolls and there is nothing to save.
  //
  // This attaches even though renderRack() rewrites #units on every update -- the class
  // lives on #rack, the container, which is never rewritten. Toggling a descendant's class
  // here would be undone by the next status push.
  var FOLD_KEY = 'symoneural.rack.detail';
  var foldBtn = el('rk-fold'), rackSec = document.getElementById('rack');
  if (foldBtn && rackSec) {
    var setFold = function (open) {
      rackSec.classList.toggle('rk-open', open);
      foldBtn.setAttribute('aria-pressed', open ? 'true' : 'false');
      foldBtn.textContent = open ? 'Hide what each unit is running'
                                 : 'Show what each unit is running';
      try { localStorage.setItem(FOLD_KEY, open ? '1' : '0'); } catch (e) {}
    };
    var remembered = '0';
    try { remembered = localStorage.getItem(FOLD_KEY) || '0'; } catch (e) {}
    setFold(remembered === '1');
    foldBtn.addEventListener('click', function () {
      setFold(!rackSec.classList.contains('rk-open'));
    });
  }

  // The control board's fold, same contract as the rack's. Its own key and its own class
  // so the two remember independently -- someone reading the rack in detail is not
  // necessarily reading nineteen module explanations too.
  var cnBtn = el('cn-fold'), cnSec = document.getElementById('console');
  if (cnBtn && cnSec) {
    var setCn = function (open) {
      cnSec.classList.toggle('cn-open', open);
      cnBtn.setAttribute('aria-pressed', open ? 'true' : 'false');
      cnBtn.textContent = open ? 'Hide what each reading means'
                               : 'Show what each reading means';
      try { localStorage.setItem('symoneural.console.detail', open ? '1' : '0'); } catch (e) {}
    };
    var cnSaved = '0';
    try { cnSaved = localStorage.getItem('symoneural.console.detail') || '0'; } catch (e) {}
    setCn(cnSaved === '1');
    cnBtn.addEventListener('click', function () {
      setCn(!cnSec.classList.contains('cn-open'));
    });
  }

  if (el('units') || el('m-vram')) connect();
})();
