/* SyMoNeuRaL Reinforce -- the training bay's frontend.
 *
 * Deploys to `site/reinforce.js`; `page.html` loads it with `<script src="/reinforce.js" defer>`.
 *
 * Talks to the API on the SAME ORIGIN, at `/api/train/*`. That is not incidental: FastAPI does
 * all the routing here and mounts `site/` last, and a split origin breaks the rest of the
 * site's live plumbing. There is no base URL to configure and there must not be one.
 *
 * ## Two rules this file is written around
 *
 * **Nothing renders that is not a reading.** Every number below comes out of a response body.
 * There is no placeholder progress, no simulated loss and no default job. With no run, the job
 * panel says there is no run -- which is why `renderJob` has an explicit `none` branch instead
 * of falling through to a zeroed-out table. A progress bar with no total behind it is the
 * dishonest pixel the no-decorative-indicators rule exists to prevent.
 *
 * **Every figure carries its label.** `lab()` renders the measured / vendor / projected badge,
 * and it is called at every point a byte count or a VRAM figure reaches the DOM. A figure
 * without one is a bug, not a style choice.
 *
 * ## Text handling
 *
 * All server strings go in through `textContent`, never `innerHTML`. The API's own guard means
 * these strings are written by us rather than echoed from a file, but a dataset path is
 * operator-supplied and ends up in an error message, so the sink is kept safe rather than the
 * source trusted.
 *
 * Nothing here truncates. Long reasons and long attributions wrap, or fold into a <details>.
 * The CSS block in page.html says the same thing at more length and for the same reason.
 */
(function () {
  'use strict';

  var API = '/api/train';
  var GIB = 1024 * 1024 * 1024;
  var state = { models: [], presets: [], fit: [], measured: {}, poll: null };

  function $(id) { return document.getElementById(id); }

  function gib(bytes) {
    if (bytes === null || bytes === undefined) { return '--'; }
    if (bytes < GIB / 10) { return (bytes / (1024 * 1024)).toFixed(0) + ' MiB'; }
    return (bytes / GIB).toFixed(2) + ' GiB';
  }

  /* The measured / vendor / projected badge. Called wherever a figure reaches the DOM. */
  function lab(kind) {
    if (!kind) { return null; }
    var span = document.createElement('span');
    // A compound label such as "measured (architecture read from the GGUF...)" keeps its
    // explanation in a title attribute and shows its first word -- the explanation is data, so
    // it is preserved rather than dropped.
    var head = String(kind).split(' ')[0];
    span.className = 'rf-lab rf-lab-' + head;
    span.textContent = head;
    if (String(kind) !== head) { span.title = String(kind); }
    return span;
  }

  function cell(row, text, labelKind, numeric) {
    var td = document.createElement('td');
    if (numeric) { td.className = 'rf-num'; }
    td.appendChild(document.createTextNode(text === null || text === undefined ? '--' : String(text)));
    var badge = lab(labelKind);
    if (badge) { td.appendChild(badge); }
    row.appendChild(td);
    return td;
  }

  function get(path) {
    return fetch(API + path, { headers: { accept: 'application/json' } })
      .then(function (r) {
        return r.json().then(function (body) { return { ok: r.ok, status: r.status, body: body }; });
      });
  }

  function post(path, payload, token) {
    var headers = { 'content-type': 'application/json', accept: 'application/json' };
    // The operator token travels in a header, never in the URL. uvicorn logs the full request
    // line, so a secret in a query string is a secret written to the server's log on every
    // request.
    if (token) { headers['x-reinforce-token'] = token; }
    return fetch(API + path, { method: 'POST', headers: headers, body: JSON.stringify(payload || {}) })
      .then(function (r) {
        return r.json().then(function (body) { return { ok: r.ok, status: r.status, body: body }; });
      });
  }

  /* ------------------------------------------------------------------ 1. models */

  function renderModels(data) {
    var tbody = $('rf-models').querySelector('tbody');
    tbody.textContent = '';
    state.models = data.models || [];

    state.models.forEach(function (m) {
      var tr = document.createElement('tr');

      var name = document.createElement('td');
      var strong = document.createElement('strong');
      strong.textContent = m.label;
      name.appendChild(strong);
      // The path is shown in full. It is short, it is the answer to "which copy is this", and
      // truncating it would hide the difference between two snapshots of one repository.
      var path = document.createElement('div');
      path.className = 'rf-note';
      path.textContent = m.path;
      name.appendChild(path);
      tr.appendChild(name);

      cell(tr, m.kind === 'hf' ? 'safetensors' : 'GGUF');
      if (m.present) {
        cell(tr, gib(m.bytes_on_disk), 'measured', true);
      } else {
        cell(tr, 'not on this box · ' + gib(m.fetch_bytes) + ' to fetch', 'projected', true);
      }
      cell(tr, m.quantisation || '--', m.quant_label);

      var params = document.createElement('td');
      params.className = 'rf-num';
      if (m.params) {
        params.appendChild(document.createTextNode(
          (m.params.total / 1e9).toFixed(2) + 'B total · ' +
          (m.params.quantised_4bit / 1e9).toFixed(2) + 'B to four bits · ' +
          (m.params.resident_bf16 / 1e9).toFixed(2) + 'B stays full width'));
        params.appendChild(lab(m.params.label));
        var note = document.createElement('div');
        note.className = 'rf-note';
        note.textContent = m.params.note;
        params.appendChild(note);
      } else {
        params.textContent = '--';
      }
      tr.appendChild(params);

      var ok = document.createElement('td');
      if (m.trainable) {
        var yes = document.createElement('span');
        yes.className = 'rf-verdict rf-fits';
        yes.textContent = 'yes';
        ok.appendChild(yes);
      } else {
        var no = document.createElement('span');
        no.className = 'rf-verdict rf-refused';
        no.textContent = 'no';
        ok.appendChild(no);
        // The reason, in full and never clipped. "Unsupported" on its own is what makes an
        // operator file a bug report; the reason is what makes them pick the other row.
        var why = document.createElement('div');
        why.className = 'rf-note';
        why.textContent = m.reason;
        ok.appendChild(why);
      }
      tr.appendChild(ok);
      tbody.appendChild(tr);
    });

    var vram = $('rf-vram');
    vram.textContent = '';
    if (data.free_vram_bytes) {
      vram.appendChild(document.createTextNode('Free on the card right now: ' + gib(data.free_vram_bytes)));
      vram.appendChild(lab(data.free_vram_label));
      vram.appendChild(document.createTextNode('. Planning budget: ' + gib(data.budget_bytes)));
      vram.appendChild(lab(data.budget_label));
      vram.appendChild(document.createTextNode('. ' + data.budget_note + ' ' + data.fetch_note));
    } else {
      vram.textContent = 'Free VRAM could not be read: ' + (data.free_vram_label || 'unknown') +
        '. Nothing is guessed in its place — the fit column falls back to the planning budget.';
    }

    var pick = $('rf-pick-model');
    pick.textContent = '';
    state.models.filter(function (m) { return m.trainable; }).forEach(function (m) {
      var opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.label;
      pick.appendChild(opt);
    });
    if (!pick.options.length) {
      var none = document.createElement('option');
      none.textContent = 'no model on this box can be fine-tuned';
      none.value = '';
      pick.appendChild(none);
    }
  }

  /* ------------------------------------------------------------------ 2. presets */

  function renderPresets(data) {
    state.presets = data.presets || [];
    state.fit = data.fit || [];
    state.measured = data.measured_peaks || {};
    var fitById = {};
    state.fit.forEach(function (f) { fitById[f.preset] = f; });

    var tbody = $('rf-presets').querySelector('tbody');
    tbody.textContent = '';

    state.presets.forEach(function (p) {
      var f = fitById[p.id];
      var plan = f ? f.plan : null;
      var tr = document.createElement('tr');

      var name = document.createElement('td');
      var b = document.createElement('strong');
      b.textContent = p.label;
      name.appendChild(b);
      tr.appendChild(name);

      cell(tr, p.when);
      cell(tr, 'r=' + p.rank + ' · alpha=' + p.lora_alpha + ' · ' +
               p.target_modules.length + ' target module(s)', null, true);
      cell(tr, p.epochs + ' epoch(s) · ' + p.learning_rate + ' · ' + p.lr_scheduler_type, null, true);
      cell(tr, p.max_length + ' tokens · batch 1 x ' + p.gradient_accumulation_steps +
               ' (effective ' + p.effective_batch + ')', null, true);

      /* Peak VRAM. A cell shows a MEASURED figure only when a run of this exact model and
       * preset has recorded one; otherwise the projection, labelled as such. Scaling one
       * measurement onto the other cells would be a projection wearing a measurement's badge. */
      var vram = document.createElement('td');
      vram.className = 'rf-num';
      var key = (f ? f.model : '') + '|' + p.id;
      if (state.measured[key]) {
        vram.appendChild(document.createTextNode(gib(state.measured[key].peak_alloc) + ' allocated'));
        vram.appendChild(lab('measured'));
        var res = document.createElement('div');
        res.className = 'rf-note';
        res.textContent = gib(state.measured[key].peak_reserved) + ' reserved, over ' +
          state.measured[key].steps + ' step(s). Projection for this configuration was ' +
          (plan ? gib(plan.projected_peak_bytes) : '--') + '.';
        vram.appendChild(res);
      } else if (plan) {
        vram.appendChild(document.createTextNode(gib(plan.projected_peak_bytes)));
        vram.appendChild(lab('projected'));
        var terms = document.createElement('details');
        terms.className = 'rf-why';
        var sum = document.createElement('summary');
        sum.textContent = 'show the arithmetic';
        terms.appendChild(sum);
        var dl = document.createElement('dl');
        Object.keys(plan.terms).forEach(function (k) {
          var dt = document.createElement('dt');
          dt.textContent = k.replace(/_/g, ' ') + ' — ' + gib(plan.terms[k].bytes);
          dt.appendChild(lab(plan.terms[k].label));
          dl.appendChild(dt);
          var dd = document.createElement('dd');
          dd.textContent = plan.terms[k].basis;
          dl.appendChild(dd);
        });
        var dt2 = document.createElement('dt');
        dt2.textContent = 'how accurate has this been?';
        dl.appendChild(dt2);
        var dd2 = document.createElement('dd');
        dd2.textContent = plan.accuracy.runs_measured + ' run measured so far (' +
          plan.accuracy.cell + '): ' + plan.accuracy.content_term_error + '. ' +
          plan.accuracy.direction + '. ' + plan.accuracy.first_correction + '.';
        dl.appendChild(dd2);
        terms.appendChild(dl);
        vram.appendChild(terms);
      } else {
        vram.textContent = '--';
      }
      tr.appendChild(vram);

      var verdict = document.createElement('td');
      if (plan) {
        var v = document.createElement('span');
        v.className = 'rf-verdict rf-' + plan.verdict;
        v.textContent = plan.verdict;
        verdict.appendChild(v);
        var vw = document.createElement('div');
        vw.className = 'rf-note';
        vw.textContent = plan.verdict_why + ' Headroom ' + gib(plan.headroom_bytes) +
          ' against a ' + gib(plan.budget_bytes) + ' budget.';
        verdict.appendChild(vw);
        if (plan.ladder && plan.ladder.length) {
          var lad = document.createElement('div');
          lad.className = 'rf-note';
          lad.textContent = 'To make it fit: ' + plan.ladder.join('; ') + '.';
          verdict.appendChild(lad);
        }
        var pct = document.createElement('div');
        pct.className = 'rf-note';
        pct.textContent = plan.trainable_params.toLocaleString() + ' trainable parameters, ' +
          plan.trainable_pct + '% of the base — ' + plan.trainable_pct_note + '.';
        verdict.appendChild(pct);
      }
      tr.appendChild(verdict);

      /* The rationale, folded rather than trimmed. This is the answer to "predetermined
       * professional tuning methods": a preset whose values cannot be justified is a form. */
      var why = document.createElement('tr');
      var wtd = document.createElement('td');
      wtd.colSpan = 7;
      var det = document.createElement('details');
      det.className = 'rf-why';
      var s2 = document.createElement('summary');
      s2.textContent = 'why these values for ' + p.label;
      det.appendChild(s2);
      var dl2 = document.createElement('dl');
      Object.keys(p.rationale).forEach(function (k) {
        var dt = document.createElement('dt');
        dt.textContent = k.replace(/_/g, ' ');
        dl2.appendChild(dt);
        var dd = document.createElement('dd');
        dd.textContent = p.rationale[k];
        dl2.appendChild(dd);
      });
      det.appendChild(dl2);
      wtd.appendChild(det);
      why.appendChild(wtd);

      tbody.appendChild(tr);
      tbody.appendChild(why);
    });

    fillDefinitionList($('rf-shared').querySelector('dl'), data.shared, true);
    fillDefinitionList($('rf-notoffered').querySelector('dl'), data.not_offered, false);

    var pick = $('rf-pick-preset');
    pick.textContent = '';
    state.presets.forEach(function (p) {
      var opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.label;
      pick.appendChild(opt);
    });
  }

  function fillDefinitionList(dl, obj, structured) {
    dl.textContent = '';
    Object.keys(obj || {}).forEach(function (k) {
      var dt = document.createElement('dt');
      dt.textContent = k.replace(/_/g, ' ');
      dl.appendChild(dt);
      var dd = document.createElement('dd');
      if (structured) {
        dd.textContent = String(obj[k].value) + ' — ' + obj[k].why +
          ' (source: ' + obj[k].provenance + ')';
      } else {
        dd.textContent = obj[k];
      }
      dl.appendChild(dd);
    });
  }

  /* ------------------------------------------------------------------ 3. preflight and start */

  function body() {
    return {
      model: $('rf-pick-model').value,
      preset: $('rf-pick-preset').value,
      dataset: $('rf-pick-dataset').value
    };
  }

  function showPreflight(res) {
    var out = $('rf-preflight-out');
    out.textContent = '';
    // 501 is not an error and is not rendered as one: it means this box does not have the
    // capability for that configuration. The arithmetic comes back in the body either way.
    var data = (res.status === 501 && res.body && res.body.detail) ? res.body.detail : res.body;
    var line = document.createElement('div');
    if (data.ok) {
      line.textContent = 'This run fits. ' + (data.plan ? data.plan.verdict_why : '');
      $('rf-start-btn').disabled = false;
    } else {
      line.textContent = (res.status === 501 ? 'This box cannot run that: ' : 'Not started: ') +
        (data.message || data.reason || 'refused');
      $('rf-start-btn').disabled = true;
    }
    out.appendChild(line);
    if (data.plan) {
      var sums = document.createElement('div');
      sums.className = 'rf-note';
      sums.textContent = 'Projected peak ' + gib(data.plan.projected_peak_bytes) +
        ' against ' + gib(data.plan.budget_bytes) + ' available (' +
        data.plan.budget_basis + '). Headroom ' + gib(data.plan.headroom_bytes) + '.';
      out.appendChild(sums);
    }
    if (data.gpu_note) {
      var note = document.createElement('div');
      note.className = 'rf-note';
      note.textContent = data.gpu_note;
      out.appendChild(note);
    }
    if (data.dataset) {
      var ds = document.createElement('div');
      ds.className = 'rf-note';
      // Shape only. The API returns no dataset content and this shows none.
      ds.textContent = 'Dataset accepted: ' + data.dataset.rows + ' example(s), ' +
        gib(data.dataset.bytes_on_disk) + ' on disk. ' + data.dataset.note;
      out.appendChild(ds);
    }
  }

  /* ------------------------------------------------------------------ 4. job state */

  function renderJob(snap) {
    var dot = $('rf-dot');
    var text = $('rf-state-text');
    dot.setAttribute('data-state', snap.state);
    text.textContent = snap.state === 'none' ? snap.detail : snap.state + ' — ' + snap.detail;
    $('rf-stop-btn').hidden = !(snap.state === 'running' || snap.state === 'queued');

    var tbody = $('rf-job').querySelector('tbody');
    tbody.textContent = '';

    if (snap.state === 'none') {
      var tr = document.createElement('tr');
      var td = document.createElement('td');
      td.textContent = 'There is no run. Nothing on this panel is a placeholder — when a run ' +
        'exists, every figure below is a reading taken from it.';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    var rows = [
      ['method', snap.job ? snap.job.preset : null, null],
      ['base model', snap.job ? snap.job.model : null, null],
      ['examples', snap.job ? snap.job.dataset_rows : null, 'measured'],
      ['step', snap.total_steps ? (snap.step + ' of ' + snap.total_steps) : snap.step, 'measured'],
      ['epoch', snap.epoch, 'measured'],
      ['training loss', snap.train_loss, snap.train_loss_label],
      ['validation loss', snap.val_loss, snap.val_loss_label],
      ['learning rate', snap.learning_rate, 'measured'],
      ['elapsed', snap.elapsed_s === null ? null : snap.elapsed_s + ' s', snap.elapsed_label],
      ['time remaining', snap.eta_s === null || snap.eta_s === undefined ? null : snap.eta_s + ' s',
       snap.eta_label],
      ['peak VRAM allocated', gib(snap.vram_peak_alloc_bytes), snap.vram_label],
      ['peak VRAM reserved', gib(snap.vram_peak_reserved_bytes), snap.vram_label],
      ['GPU held by', snap.holder, 'measured'],
      ['exit code', snap.exit_code, null]
    ];
    rows.forEach(function (r) {
      if (r[1] === null || r[1] === undefined || r[1] === '--') { return; }
      var tr = document.createElement('tr');
      var th = document.createElement('th');
      th.textContent = r[0];
      tr.appendChild(th);
      cell(tr, r[1], r[2], true);
      tbody.appendChild(tr);
    });
    if (snap.eta_s !== null && snap.eta_s !== undefined) {
      var tr2 = document.createElement('tr');
      var td2 = document.createElement('td');
      td2.colSpan = 2;
      td2.className = 'rf-note';
      td2.textContent = snap.eta_note;
      tr2.appendChild(td2);
      tbody.appendChild(tr2);
    }
  }

  /* Polling rather than a socket: a training run reports once per logging step, which is
   * minutes apart on a real preset, so a socket would idle. The interval slows right down when
   * nothing is running, because the rack panel already carries the state a visitor needs. */
  function pollJob() {
    get('/status').then(function (res) {
      if (!res.ok) { return; }
      renderJob(res.body);
      var busy = res.body.state === 'running' || res.body.state === 'queued';
      if (state.poll) { clearTimeout(state.poll); }
      state.poll = setTimeout(pollJob, busy ? 4000 : 20000);
    }).catch(function () {
      if (state.poll) { clearTimeout(state.poll); }
      state.poll = setTimeout(pollJob, 20000);
    });
  }

  /* ------------------------------------------------------------------ wiring */

  function boot() {
    get('/models').then(function (res) {
      if (res.status === 503) {
        $('rf-gate').hidden = false;
        // Every control is disabled rather than hidden. A surface that vanishes when it is off
        // reads as broken; one that says why reads as configured.
        ['rf-preflight-btn', 'rf-start-btn', 'rf-pick-model', 'rf-pick-preset',
         'rf-pick-dataset', 'rf-token'].forEach(function (id) { $(id).disabled = true; });
        return;
      }
      renderModels(res.body);
      return get('/presets?model=' + encodeURIComponent($('rf-pick-model').value || ''))
        .then(function (p) { if (p.ok) { renderPresets(p.body); } });
    }).catch(function () { /* offline: the panel keeps its "loading" text rather than inventing one */ });

    pollJob();

    $('rf-pick-model').addEventListener('change', function () {
      get('/presets?model=' + encodeURIComponent($('rf-pick-model').value))
        .then(function (p) { if (p.ok) { renderPresets(p.body); } });
    });

    $('rf-preflight-btn').addEventListener('click', function () {
      $('rf-preflight-out').textContent = 'Costing the run…';
      post('/preflight', body()).then(showPreflight);
    });

    $('rf-start-btn').addEventListener('click', function () {
      post('/start', body(), $('rf-token').value).then(function (res) {
        var out = $('rf-preflight-out');
        out.textContent = '';
        var line = document.createElement('div');
        if (res.ok) {
          line.textContent = 'Started. ' + res.body.warning;
          $('rf-start-btn').disabled = true;
        } else {
          var d = res.body && res.body.detail;
          line.textContent = 'Not started: ' +
            (typeof d === 'string' ? d : (d && d.message) || ('HTTP ' + res.status));
        }
        out.appendChild(line);
        pollJob();
      });
    });

    $('rf-stop-btn').addEventListener('click', function () {
      post('/stop', {}, $('rf-token').value).then(function (res) {
        var out = $('rf-preflight-out');
        out.textContent = res.ok
          ? (res.body.stopped ? res.body.note : res.body.reason)
          : 'Stop refused: HTTP ' + res.status;
        pollJob();
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
