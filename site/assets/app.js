(function () {
  'use strict';

  var C = window.SRTW_CONFIG || {};
  var POINTS = C.points || [];
  var PHOTO_BASE = String(C.photoBaseUrl || '/demo-photos').replace(/\/+$/, '');
  var DATA_BASE = String(C.dataBaseUrl || '/data').replace(/\/+$/, '');
  var PAGE_SIZE = C.pageSize || 24;
  var SLOT_MIN = C.slotMinutes || 15;
  var EVENT = C.eventName || 'She Runs The World 2026';
  var DEFAULT_HINT = 'Nomor BIB ada di bagian depan jersey kamu.';
  var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var isLocal = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || location.protocol === 'file:';
  var PRETTY = C.prettyUrls === 'auto' || C.prettyUrls === undefined ? !isLocal : !!C.prettyUrls;

  var pointById = {};
  POINTS.forEach(function (p) { pointById[p.id] = p; });

  /* ---------- Helpers ---------- */

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v == null || v === false) return;
        if (k === 'class') el.className = v;
        else if (k === 'text') el.textContent = v;
        else if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v === true ? '' : v);
      });
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null || c === false) continue;
      if (Array.isArray(c)) c.forEach(function (x) { if (x != null) el.append(x); });
      else el.append(c);
    }
    return el;
  }

  var ICON_DOWNLOAD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>';
  function icon(svg) {
    var s = h('span', { class: 'icon', 'aria-hidden': 'true' });
    s.innerHTML = svg; // ikon statis, bukan data pengguna
    return s;
  }

  function cleanBib(v) { return String(v || '').replace(/\D/g, '').slice(0, 8); }
  function fmtTime(t) { return String(t || '').replace(':', '.'); }
  function pointLabel(id) { return (pointById[id] && pointById[id].label) || id || 'Foto'; }
  function photoUrl(variant, id) { return PHOTO_BASE + '/' + variant + '/' + encodeURIComponent(id) + '.jpg'; }
  function byTime(a, b) {
    var ta = a.time || '99:99', tb = b.time || '99:99';
    return ta < tb ? -1 : ta > tb ? 1 : (a.id < b.id ? -1 : 1);
  }
  function bibPath(bib) { return PRETTY ? '/bib/' + bib : '/?bib=' + bib; }
  function fileName(photo, bib) { return 'SRTW2026' + (bib ? '-BIB' + bib : '') + '-' + photo.id + '.jpg'; }
  function plural(n) { return n.toLocaleString('id-ID'); }

  function readBibFromUrl() {
    var m = location.pathname.match(/\/bib\/(\d+)/);
    if (m) return cleanBib(m[1]);
    var q = new URLSearchParams(location.search).get('bib');
    return q ? cleanBib(q) : null;
  }

  function fetchJSON(path) {
    return fetch(path).then(function (res) {
      if (res.status === 404) return null;
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var type = res.headers.get('content-type') || '';
      if (type.indexOf('json') === -1) return null; // host yang mengembalikan index.html untuk file yang tidak ada
      return res.json();
    });
  }

  var toastTimer;
  function toast(msg) {
    var t = $('#toast');
    t.textContent = msg;
    t.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove('is-visible'); }, 4000);
  }

  function saveBlob(blob, name) {
    var url = URL.createObjectURL(blob);
    var a = h('a', { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 15000);
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      if (window.JSZip) return resolve();
      var s = h('script', { src: src, crossorigin: 'anonymous' });
      s.onload = function () { resolve(); };
      s.onerror = function () { reject(new Error('Gagal memuat ' + src)); };
      document.head.append(s);
    });
  }

  /* ---------- Elements & state ---------- */

  var el = {
    form: $('#search-form'),
    input: $('#bib-input'),
    hint: $('#search-hint'),
    results: $('#hasil'),
    title: $('#results-title'),
    meta: $('#results-meta'),
    body: $('#results-body'),
    filters: $('#result-filters'),
    grid: $('#result-grid'),
    empty: $('#results-empty'),
    emptyTitle: $('#empty-title'),
    emptyText: $('#empty-text'),
    retry: $('#retry-btn'),
    mobileBar: $('#mobile-bar'),
    pointGrid: $('#point-grid'),
    browse: $('#browse-results'),
    browseTitle: $('#browse-title'),
    browseStatus: $('#browse-status'),
    slots: $('#slot-filters'),
    browseGrid: $('#browse-grid'),
    loadMore: $('#load-more'),
    viewer: $('#viewer'),
    viewerImg: $('#viewer-img'),
    viewerCaption: $('#viewer-caption'),
    viewerCounter: $('#viewer-counter'),
    viewerTags: $('#viewer-tags'),
    viewerPrev: $('#viewer-prev'),
    viewerNext: $('#viewer-next'),
    viewerClose: $('#viewer-close'),
    viewerDownload: $('#viewer-download'),
    viewerStage: $('#viewer-stage')
  };

  var state = {
    reqId: 0,
    bib: null,
    photos: [],
    category: null,
    filter: 'all',
    zipping: false,
    meta: null,
    browse: { point: null, photos: [], slot: 'all', shown: 0 },
    viewer: { list: [], index: 0, bib: null, returnFocus: null }
  };

  /* ---------- Shared bits ---------- */

  function tagList(bibs, current) {
    var wrap = h('div', { class: 'tags' });
    if (!bibs || !bibs.length) {
      wrap.append(h('span', { class: 'tag-none', text: 'BIB tidak terbaca' }));
      return wrap;
    }
    bibs.forEach(function (b) {
      var isCurrent = b === current;
      wrap.append(h('a', {
        class: 'tag' + (isCurrent ? ' is-current' : ''),
        href: bibPath(b),
        'aria-current': isCurrent ? 'true' : null,
        'aria-label': 'Lihat foto BIB ' + b,
        text: '#' + b,
        onclick: function (e) {
          e.preventDefault();
          if (el.viewer.open) closeViewer(false);
          searchBib(b);
        }
      }));
    });
    return wrap;
  }

  function photoCard(photo, index, list, bib) {
    var label = pointLabel(photo.point);
    var img = h('img', {
      src: photoUrl('thumb', photo.id),
      alt: '',
      loading: 'lazy',
      decoding: 'async',
      width: '400',
      height: '500'
    });
    var thumb = h('button', {
      class: 'thumb',
      type: 'button',
      'aria-label': 'Buka foto ' + label + ', jam ' + fmtTime(photo.time),
      onclick: function () { openViewer(list, index, bib, thumb); }
    }, img);
    img.addEventListener('error', function () { thumb.classList.add('is-broken'); });

    return h('li', { class: 'card' },
      thumb,
      h('div', { class: 'card-info' },
        h('span', { class: 'card-point', text: label }),
        h('span', { class: 'card-time', text: fmtTime(photo.time) })
      ),
      h('div', { class: 'card-foot' },
        tagList(photo.bibs, bib),
        h('button', {
          class: 'icon-btn',
          type: 'button',
          'aria-label': 'Download foto ' + label + ' ' + fmtTime(photo.time),
          onclick: function () { downloadPhoto(photo, bib); }
        }, icon(ICON_DOWNLOAD))
      )
    );
  }

  function skeletonCards(n) {
    var out = [];
    for (var i = 0; i < n; i++) {
      out.push(h('li', { class: 'card is-skeleton', 'aria-hidden': 'true' },
        h('div', { class: 'thumb' }),
        h('div', { class: 'sk-line' }),
        h('div', { class: 'sk-line short' })
      ));
    }
    return out;
  }

  function pillButton(label, count, pressed, onClick) {
    return h('button', {
      class: 'pill',
      type: 'button',
      'aria-pressed': pressed ? 'true' : 'false',
      onclick: onClick
    }, label, h('span', { class: 'n', text: String(count) }));
  }

  /* ---------- Search by BIB ---------- */

  function showHint(msg, isError) {
    el.hint.textContent = msg;
    el.hint.classList.toggle('is-error', !!isError);
  }

  function setActions(enabled) {
    $$('[data-action]').forEach(function (b) { b.disabled = !enabled; });
  }

  function setTitle(bib) {
    el.title.querySelector('.bib-no').textContent = bib;
  }

  function searchBib(raw, opts) {
    opts = opts || {};
    var bib = cleanBib(raw);
    if (!bib) {
      showHint('Masukkan nomor BIB dulu, cukup angkanya saja.', true);
      el.input.focus();
      return;
    }
    el.input.value = bib;
    showHint(DEFAULT_HINT, false);

    if (opts.push !== false && readBibFromUrl() !== bib) {
      history.pushState({ bib: bib }, '', bibPath(bib));
    }
    document.title = 'BIB ' + bib + ' | Foto ' + EVENT;

    var req = ++state.reqId;
    state.bib = bib;
    state.filter = 'all';
    state.photos = [];

    el.results.hidden = false;
    el.body.hidden = false;
    el.empty.hidden = true;
    el.mobileBar.hidden = false;
    setTitle(bib);
    el.meta.replaceChildren(h('span', { text: 'Mencari foto…' }));
    el.filters.replaceChildren();
    el.grid.replaceChildren.apply(el.grid, skeletonCards(8));
    setActions(false);

    if (opts.scroll !== false) {
      el.results.scrollIntoView({ behavior: REDUCED ? 'auto' : 'smooth', block: 'start' });
    }

    fetchJSON(DATA_BASE + '/bib/' + bib + '.json').then(function (data) {
      if (req !== state.reqId) return;
      if (!data || !data.photos || !data.photos.length) return renderNotFound(bib);
      state.photos = data.photos.slice().sort(byTime);
      state.category = data.category || null;
      renderResults();
    }).catch(function () {
      if (req !== state.reqId) return;
      renderError(bib);
    });
  }

  function resultsInfo() {
    var cat = state.category;
    if (!cat) return null;
    var cats = C.resultsCategories || ['10K'];
    if (C.resultsUrl && cats.indexOf(cat) !== -1) {
      return h('a', {
        href: C.resultsUrl.replace('{bib}', encodeURIComponent(state.bib)),
        target: '_blank',
        rel: 'noopener',
        text: 'Lihat catatan waktu resmi'
      });
    }
    if (cats.indexOf(cat) === -1) {
      return h('span', { text: 'Kategori ' + cat + ' tidak memakai timing resmi.' });
    }
    return null;
  }

  function renderResults() {
    var n = state.photos.length;
    el.meta.replaceChildren(
      h('span', { class: 'count', text: plural(n) + ' foto' }),
      state.category ? h('span', { class: 'chip chip-dark', text: state.category }) : '',
      resultsInfo() || ''
    );
    renderFilters();
    renderGrid();
    setActions(true);
  }

  function renderFilters() {
    var counts = {};
    state.photos.forEach(function (p) { counts[p.point] = (counts[p.point] || 0) + 1; });
    var buttons = [pillButton('Semua', state.photos.length, state.filter === 'all', function () { setFilter('all'); })];
    var known = POINTS.map(function (p) { return p.id; });
    var ids = known.concat(Object.keys(counts).filter(function (id) { return known.indexOf(id) === -1; }));
    ids.forEach(function (id) {
      if (!counts[id]) return;
      buttons.push(pillButton(pointLabel(id), counts[id], state.filter === id, function () { setFilter(id); }));
    });
    el.filters.replaceChildren.apply(el.filters, buttons);
  }

  function setFilter(id) {
    state.filter = id;
    renderFilters();
    renderGrid();
  }

  function renderGrid() {
    var list = state.filter === 'all'
      ? state.photos
      : state.photos.filter(function (p) { return p.point === state.filter; });
    el.grid.replaceChildren.apply(el.grid, list.map(function (p, i) { return photoCard(p, i, list, state.bib); }));
  }

  function renderNotFound(bib) {
    el.body.hidden = true;
    el.mobileBar.hidden = true;
    el.empty.hidden = false;
    el.retry.hidden = true;
    el.meta.replaceChildren(h('span', { text: 'Belum ada foto' }));
    el.emptyTitle.textContent = 'Belum ada foto untuk BIB ' + bib + '.';
    el.emptyText.textContent = 'Cek lagi nomornya. Kalau sudah benar, mungkin BIB kamu tertutup atau foto masih diproses. Kamu tetap bisa cari manual berdasarkan titik foto dan jam.';
    setActions(false);
  }

  function renderError(bib) {
    el.body.hidden = true;
    el.mobileBar.hidden = true;
    el.empty.hidden = false;
    el.retry.hidden = false;
    el.meta.replaceChildren();
    el.emptyTitle.textContent = 'Foto BIB ' + bib + ' gagal dimuat.';
    el.emptyText.textContent = 'Periksa koneksi internet kamu, lalu coba lagi.';
    setActions(false);
  }

  function resetSearch() {
    state.reqId++;
    state.bib = null;
    el.results.hidden = true;
    el.input.value = '';
    document.title = 'Cari Foto ' + EVENT;
  }

  /* ---------- Download dan ZIP ---------- */

  function downloadPhoto(photo, bib) {
    var src = photoUrl('full', photo.id);
    toast('Mengunduh foto…');
    fetch(src, { mode: 'cors' }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.blob();
    }).then(function (blob) {
      saveBlob(blob, fileName(photo, bib));
      toast('Foto tersimpan.');
    }).catch(function () {
      // Kalau CORS belum diatur, buka foto di tab baru supaya tetap bisa disimpan manual
      window.open(src, '_blank', 'noopener');
    });
  }

  function setZipLabel(text) {
    $$('[data-zip-label]').forEach(function (s) { s.textContent = text || 'Download semua (ZIP)'; });
  }

  function downloadZip() {
    if (state.zipping || !state.photos.length) return;
    state.zipping = true;
    var bib = state.bib;
    var photos = state.photos.slice();
    var total = photos.length;
    var done = 0;
    var failed = 0;
    setActions(false);
    setZipLabel('Menyiapkan 0/' + total);

    loadScript(C.jszipUrl).then(function () {
      var zip = new window.JSZip();
      var queue = photos.slice();
      function worker() {
        if (!queue.length) return Promise.resolve();
        var p = queue.shift();
        return fetch(photoUrl(C.zipVariant || 'web', p.id), { mode: 'cors' })
          .then(function (res) { if (!res.ok) throw new Error(); return res.blob(); })
          .then(function (blob) { zip.file(fileName(p, bib), blob); })
          .catch(function () { failed++; })
          .then(function () {
            done++;
            setZipLabel('Menyiapkan ' + done + '/' + total);
            return worker();
          });
      }
      return Promise.all([worker(), worker(), worker(), worker()]).then(function () {
        if (failed === total) throw new Error('Semua foto gagal diunduh');
        setZipLabel('Membuat ZIP…');
        return zip.generateAsync({ type: 'blob', compression: 'STORE' });
      });
    }).then(function (blob) {
      saveBlob(blob, 'SRTW2026-BIB' + bib + '.zip');
      toast(failed
        ? 'ZIP tersimpan. ' + failed + ' foto gagal masuk, unduh satu per satu ya.'
        : 'ZIP berisi ' + total + ' foto tersimpan.');
    }).catch(function () {
      toast('ZIP gagal dibuat. Coba unduh foto satu per satu.');
    }).then(function () {
      state.zipping = false;
      setZipLabel(null);
      setActions(true);
    });
  }

  /* ---------- Viewer ---------- */

  function openViewer(list, index, bib, returnFocus) {
    state.viewer = { list: list, index: index, bib: bib, returnFocus: returnFocus || document.activeElement };
    showViewerPhoto();
    if (!el.viewer.open) {
      el.viewer.showModal();
      document.documentElement.classList.add('is-locked');
    }
  }

  function showViewerPhoto() {
    var v = state.viewer;
    var p = v.list[v.index];
    if (!p) return;
    var label = pointLabel(p.point);
    el.viewerImg.classList.add('is-loading');
    el.viewerImg.src = photoUrl('web', p.id);
    el.viewerImg.alt = 'Foto ' + label + ', jam ' + fmtTime(p.time);
    el.viewerCaption.textContent = label + ', ' + fmtTime(p.time);
    el.viewerCounter.textContent = (v.index + 1) + ' / ' + v.list.length;
    el.viewerTags.replaceChildren(tagList(p.bibs, v.bib));
    el.viewerPrev.disabled = v.index === 0;
    el.viewerNext.disabled = v.index === v.list.length - 1;
    [v.index + 1, v.index - 1].forEach(function (i) {
      if (v.list[i]) { var im = new Image(); im.src = photoUrl('web', v.list[i].id); }
    });
  }

  function stepViewer(d) {
    var v = state.viewer;
    var next = v.index + d;
    if (next < 0 || next >= v.list.length) return;
    v.index = next;
    showViewerPhoto();
  }

  function closeViewer(restoreFocus) {
    if (el.viewer.open) el.viewer.close();
    document.documentElement.classList.remove('is-locked');
    var rf = state.viewer.returnFocus;
    if (restoreFocus !== false && rf && document.contains(rf)) rf.focus();
  }

  /* ---------- Browse by point ---------- */

  var ALL = { id: 'all', label: 'Semua foto', desc: 'Semua titik foto, urut jam' };

  function renderPoints() {
    var counts = {};
    var mp = (state.meta && state.meta.points) || {};
    for (var k in mp) counts[k] = mp[k];
    if (state.meta && state.meta.totalPhotos != null) counts.all = state.meta.totalPhotos;
    var buttons = [ALL].concat(POINTS).map(function (p) {
      var c = counts[p.id];
      return h('button', {
        class: 'point-btn' + (p.id === 'all' ? ' point-btn-all' : ''),
        type: 'button',
        'data-point': p.id,
        'aria-pressed': state.browse.point === p.id ? 'true' : 'false',
        onclick: function () { openPoint(p.id); }
      },
        h('strong', { text: p.label }),
        h('span', { text: p.desc || '' }),
        c != null ? h('span', { class: 'pc', text: plural(c) + ' foto' }) : ''
      );
    });
    el.pointGrid.replaceChildren.apply(el.pointGrid, buttons);
  }

  function slotKey(time) {
    var m = /^(\d{1,2}):(\d{2})/.exec(time || '');
    if (!m) return 'x';
    var mins = parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
    return String(Math.floor(mins / SLOT_MIN) * SLOT_MIN);
  }
  function slotLabel(key) {
    if (key === 'x') return 'Tanpa jam';
    var a = parseInt(key, 10), b = a + SLOT_MIN;
    function f(m) { return String(Math.floor(m / 60)).padStart(2, '0') + '.' + String(m % 60).padStart(2, '0'); }
    return f(a) + '–' + f(b);
  }

  function openPoint(id, opts) {
    opts = opts || {};
    var p = id === 'all' ? ALL : pointById[id];
    state.browse = { point: id, photos: [], slot: 'all', shown: 0 };
    $$('.point-btn').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-point') === id ? 'true' : 'false'); });
    el.browse.hidden = false;
    el.browseTitle.textContent = id === 'all' ? 'Semua foto' : 'Foto di ' + (p ? p.label : id);
    el.browseStatus.textContent = 'Memuat foto…';
    el.slots.replaceChildren();
    el.browseGrid.replaceChildren.apply(el.browseGrid, skeletonCards(8));
    el.loadMore.hidden = true;
    if (!opts.quiet) {
      el.browseTitle.focus({ preventScroll: true });
      el.browse.scrollIntoView({ behavior: REDUCED ? 'auto' : 'smooth', block: 'start' });
    }

    var url = id === 'all' ? DATA_BASE + '/all.json' : DATA_BASE + '/points/' + id + '.json';
    fetchJSON(url).then(function (data) {
      if (state.browse.point !== id) return;
      var photos = ((data && data.photos) || []).map(function (ph) {
        return { id: ph.id, time: ph.time, bibs: ph.bibs || [], point: ph.point || id, slot: slotKey(ph.time) };
      }).sort(byTime);
      state.browse.photos = photos;
      if (!photos.length) {
        el.browseGrid.replaceChildren();
        el.browseStatus.textContent = 'Belum ada foto di titik ini.';
        return;
      }
      renderSlots();
      renderBrowseGrid(true);
    }).catch(function () {
      if (state.browse.point !== id) return;
      el.browseGrid.replaceChildren();
      el.browseStatus.textContent = 'Foto gagal dimuat. Periksa koneksi lalu pilih titiknya lagi.';
    });
  }

  function browseList() {
    var b = state.browse;
    return b.slot === 'all' ? b.photos : b.photos.filter(function (p) { return p.slot === b.slot; });
  }

  function renderSlots() {
    var b = state.browse;
    var counts = {};
    var order = [];
    b.photos.forEach(function (p) {
      if (!counts[p.slot]) { counts[p.slot] = 0; order.push(p.slot); }
      counts[p.slot]++;
    });
    var buttons = [pillButton('Semua jam', b.photos.length, b.slot === 'all', function () { setSlot('all'); })];
    if (order.length > 1) {
      order.forEach(function (k) {
        buttons.push(pillButton(slotLabel(k), counts[k], b.slot === k, function () { setSlot(k); }));
      });
    }
    el.slots.replaceChildren.apply(el.slots, buttons);
  }

  function setSlot(k) {
    state.browse.slot = k;
    renderSlots();
    renderBrowseGrid(true);
  }

  function renderBrowseGrid(reset) {
    var b = state.browse;
    var list = browseList();
    if (reset) {
      b.shown = 0;
      el.browseGrid.replaceChildren();
    }
    var end = Math.min(b.shown + PAGE_SIZE, list.length);
    var cards = [];
    for (var i = b.shown; i < end; i++) cards.push(photoCard(list[i], i, list, null));
    el.browseGrid.append.apply(el.browseGrid, cards);
    b.shown = end;
    el.loadMore.hidden = b.shown >= list.length;
    el.browseStatus.textContent = 'Menampilkan ' + plural(b.shown) + ' dari ' + plural(list.length) + ' foto';
  }

  /* ---------- Meta ---------- */

  function loadMeta() {
    return fetchJSON(DATA_BASE + '/meta.json').then(function (meta) {
      if (!meta) return;
      state.meta = meta;
      renderPoints();
      if (meta.totalPhotos && !state.bib) {
        showHint(DEFAULT_HINT + ' ' + plural(meta.totalPhotos) + ' foto sudah bisa dicari.', false);
        DEFAULT_HINT = el.hint.textContent;
      }
      if (meta.updatedAt) {
        var d = new Date(meta.updatedAt);
        if (!isNaN(d)) {
          $('#footer-updated').textContent = 'Foto terakhir diperbarui ' + d.toLocaleString('id-ID', {
            day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta'
          }) + ' WIB';
        }
      }
    }).catch(function () { /* meta opsional */ });
  }

  /* ---------- Wiring ---------- */

  el.form.addEventListener('submit', function (e) {
    e.preventDefault();
    searchBib(el.input.value);
  });
  el.input.addEventListener('input', function () {
    var c = el.input.value.replace(/\D/g, '');
    if (c !== el.input.value) el.input.value = c;
    if (el.hint.classList.contains('is-error')) showHint(DEFAULT_HINT, false);
  });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-action]');
    if (!btn || btn.disabled) return;
    var a = btn.getAttribute('data-action');
    if (a === 'zip') downloadZip();
  });

  el.retry.addEventListener('click', function () { if (state.bib) searchBib(state.bib, { push: false }); });
  el.loadMore.addEventListener('click', function () { renderBrowseGrid(false); });

  el.viewerPrev.addEventListener('click', function () { stepViewer(-1); });
  el.viewerNext.addEventListener('click', function () { stepViewer(1); });
  el.viewerClose.addEventListener('click', function () { closeViewer(); });
  el.viewerDownload.addEventListener('click', function () {
    var v = state.viewer;
    if (v.list[v.index]) downloadPhoto(v.list[v.index], v.bib);
  });
  el.viewerImg.addEventListener('load', function () { el.viewerImg.classList.remove('is-loading'); });
  el.viewerImg.addEventListener('error', function () { el.viewerImg.classList.remove('is-loading'); });
  el.viewer.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') { e.preventDefault(); stepViewer(-1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); stepViewer(1); }
  });
  el.viewer.addEventListener('cancel', function (e) { e.preventDefault(); closeViewer(); });
  el.viewer.addEventListener('click', function (e) {
    if (e.target === el.viewer || e.target === el.viewerStage) closeViewer();
  });

  var touchX = null;
  el.viewerStage.addEventListener('touchstart', function (e) { touchX = e.touches[0].clientX; }, { passive: true });
  el.viewerStage.addEventListener('touchend', function (e) {
    if (touchX == null) return;
    var dx = e.changedTouches[0].clientX - touchX;
    touchX = null;
    if (Math.abs(dx) > 50) stepViewer(dx < 0 ? 1 : -1);
  });

  window.addEventListener('popstate', function () {
    if (el.viewer.open) closeViewer(false);
    var b = readBibFromUrl();
    if (b) searchBib(b, { push: false });
    else resetSearch();
  });

  renderPoints();
  loadMeta();
  var initial = readBibFromUrl();
  if (initial) searchBib(initial, { push: false });
  if (C.showAllOnHome !== false) openPoint('all', { quiet: true });
})();
