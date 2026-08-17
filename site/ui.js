/* Header menus and documentation tabs.
 *
 * Both are progressive enhancement. Without this file the menus are plain lists and
 * every documentation panel is visible, so the page degrades to a long document rather
 * than to eight empty boxes -- the same reason the rack ships a <noscript> unit.
 */
(function () {
  'use strict';

  // ---- header dropdowns ---------------------------------------------------
  var items = [].slice.call(document.querySelectorAll('.navitem.has-menu'));

  function closeAll(except) {
    items.forEach(function (it) {
      if (it === except) return;
      it.classList.remove('open');
      var b = it.querySelector('.navlink');
      if (b) b.setAttribute('aria-expanded', 'false');
    });
  }

  items.forEach(function (it) {
    var btn = it.querySelector('.navlink');
    if (!btn) return;
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var open = it.classList.contains('open');
      closeAll(it);
      it.classList.toggle('open', !open);
      btn.setAttribute('aria-expanded', String(!open));
    });
  });

  document.addEventListener('click', function (e) {
    if (!e.target.closest || !e.target.closest('.navitem.has-menu')) closeAll(null);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll(null);
  });

  // ---- documentation tabs -------------------------------------------------
  var tabs = [].slice.call(document.querySelectorAll('.tab[role="tab"]'));
  if (!tabs.length) return;

  function show(id, push) {
    tabs.forEach(function (t) {
      var on = t.id === 'tab-' + id;
      t.classList.toggle('on', on);
      t.setAttribute('aria-selected', String(on));
    });
    [].slice.call(document.querySelectorAll('.tabpanel')).forEach(function (p) {
      p.hidden = p.id !== 'panel-' + id;
    });
    // The header menu deep-links straight to a section, and people share those urls,
    // so the hash has to survive a reload rather than always landing on the first tab.
    if (push && history.replaceState) history.replaceState(null, '', '#' + id);
  }

  tabs.forEach(function (t) {
    t.addEventListener('click', function () { show(t.id.replace(/^tab-/, ''), true); });
  });

  // JS is running, so it is now safe to hide the inactive panels.
  var want = (location.hash || '').replace(/^#/, '');
  var known = tabs.some(function (t) { return t.id === 'tab-' + want; });
  show(known ? want : tabs[0].id.replace(/^tab-/, ''), false);

  window.addEventListener('hashchange', function () {
    var h = (location.hash || '').replace(/^#/, '');
    if (tabs.some(function (t) { return t.id === 'tab-' + h; })) show(h, false);
  });
})();
