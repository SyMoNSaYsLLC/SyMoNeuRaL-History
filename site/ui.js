/* Documentation tabs, and the lightbox for the renders.
 *
 * The header used to have two JavaScript dropdowns. They are gone: both opened onto a
 * single destination anyway, and the menu -- z-index:60 inside a header that is itself a
 * z-index:20 stacking context -- painted underneath the hero. A nav link cannot do that.
 *
 * The tabs are progressive enhancement. Without this file every documentation panel is
 * visible, so the page degrades to a long document rather than to eight empty boxes --
 * the same reason the rack ships a <noscript> unit.
 */
(function () {
  'use strict';

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

/* Lightbox for the constellation renders.
 *
 * Separate IIFE on purpose: the block above returns early on any page with no
 * documentation tabs, which is every page the band appears on.
 *
 * The renders sit at 38-59px so the band reads as a network rather than a contact sheet,
 * and at that size the watermark burned into each one -- model, quantisation, resolution,
 * steps, seed, and the wall-clock it took on this card -- cannot be read at all. That
 * watermark is the entire claim: these were drawn by the machine on this page. Clicking
 * opens the full 768px render with its prompt and seed beside it. The markup is a plain
 * link to the PNG, so with no JavaScript the click still shows the file.
 */
(function () {
  'use strict';
  var links = [].slice.call(document.querySelectorAll('a.art, a.gart'));
  if (!links.length) return;

  var box, img, cap, meta, opener;

  function build() {
    box = document.createElement('div');
    box.className = 'lightbox';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', 'Full-size render');
    box.innerHTML =
      '<button class="lb-close" aria-label="Close">&times;</button>' +
      '<figure class="lb-fig">' +
        '<img alt="">' +
        '<figcaption><q class="lb-prompt"></q><span class="lb-meta"></span></figcaption>' +
      '</figure>';
    document.body.appendChild(box);
    img = box.querySelector('img');
    cap = box.querySelector('.lb-prompt');
    meta = box.querySelector('.lb-meta');
    box.addEventListener('click', function (e) {
      // the backdrop and the close button dismiss; the figure itself does not
      if (!e.target.closest('.lb-fig') || e.target.closest('.lb-close')) close();
    });
  }

  function open(a) {
    if (!box) build();
    opener = a;
    img.src = a.getAttribute('href');
    img.alt = a.querySelector('img').alt;
    cap.textContent = a.getAttribute('data-prompt') || '';
    // Deliberately not a repeat of the strip along the bottom of the image. That strip is
    // burned into the PNG by tools/build_gallery.py and already names the model, size,
    // steps, seed and seconds; printing the same line underneath would read as a page
    // caption *about* the image rather than as something the file itself carries.
    var secs = a.getAttribute('data-secs');
    meta.textContent = secs
      ? 'The strip along the bottom is printed into the file, not added by this page. '
        + secs + ' seconds, start to finish, on the card in the rack below.'
      : '';
    box.classList.add('on');
    document.documentElement.style.overflow = 'hidden';
    box.querySelector('.lb-close').focus();
  }

  function close() {
    if (!box) return;
    box.classList.remove('on');
    document.documentElement.style.overflow = '';
    // hand focus back to the render that was clicked, or a keyboard user is dropped
    // at the top of the document
    if (opener) opener.focus();
  }

  links.forEach(function (a) {
    a.addEventListener('click', function (e) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;  // let "open in new tab" work
      e.preventDefault();
      open(a);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && box && box.classList.contains('on')) close();
  });
})();
