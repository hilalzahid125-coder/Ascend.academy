/* ==========================================================================
   ASCEND UI MOTION — progressive enhancement only.
   Nothing here is required for the page to be readable or usable:
   every initializer is guarded, and no content is ever hidden waiting on JS.
   No external libraries, no CDN, CSP-self friendly (classic script).
   ========================================================================== */
(function () {
  'use strict';

  var root = document.documentElement;
  var BRAND = window.APP_BRAND || { name: 'ASCEND', tagline: '', logoUrl: '/static/app-logo.svg' };
  var STORE = 'ascend_motion_pref';
  var reduceOS = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var debug = /(?:^|[?&])debug=1(?:&|$)/.test(location.search);

  function store(key, value) {
    try { return value === undefined ? localStorage.getItem(key) : localStorage.setItem(key, value); }
    catch (_) { return null; }
  }
  function cssVar(name, fallback) {
    var v = getComputedStyle(root).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  }
  function rand(min, max) { return min + Math.random() * (max - min); }
  function clamp(n, min, max) { return Math.max(min, Math.min(max, n)); }

  window.ASCEND_BRAND = BRAND;

  /* ---------------------------------------------------------------- motion */
  var Motion = {
    enabled: store(STORE) !== 'off',
    listeners: [],
    subscribers: [],
    get effective() { return this.enabled && !reduceOS ? true : this.enabled && reduceOS ? false : false; },
    onChange: function (fn) { this.subscribers.push(fn); fn(this.isOn()); return fn; },
    isOn: function () { return this.enabled && !reduceOS; },
    set: function (on, opts) {
      this.enabled = !!on;
      try { localStorage.setItem(STORE, on ? 'on' : 'off'); } catch (_) {}
      root.classList.toggle('ui-motion-off', !this.enabled || reduceOS);
      document.body && document.body.classList.toggle('ui-motion-off', !this.enabled || reduceOS);
      this.subscribers.forEach(function (fn) { try { fn(this.isOn()); } catch (_) {} }, this);
      var toggle = document.querySelector('[data-motion-toggle]');
      if (toggle) {
        toggle.setAttribute('aria-pressed', this.isOn() ? 'false' : 'true');
        toggle.textContent = this.isOn() ? 'Motion: On' : 'Motion: Off';
      }
      if (opts && opts.silent !== true && !this.isOn()) Bubble.stopAll();
      return this.isOn();
    },
    toggle: function () { return this.set(!this.isOn()); }
  };

  root.classList.toggle('ui-motion-off', !Motion.isOn());
  document.addEventListener('DOMContentLoaded', function () {
    document.body.classList.toggle('ui-motion-off', !Motion.isOn());
    var toggle = document.querySelector('[data-motion-toggle]');
    if (toggle) {
      toggle.hidden = false;
      toggle.setAttribute('aria-pressed', Motion.isOn() ? 'false' : 'true');
      toggle.textContent = Motion.isOn() ? 'Motion: On' : 'Motion: Off';
      toggle.addEventListener('click', function (event) { event.preventDefault(); Motion.toggle(); });
    }
    try {
      document.dispatchEvent(new CustomEvent('ascend:motionchange', { detail: { on: Motion.isOn() } }));
    } catch (_) {}
  });
  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    var onMq = function () {
      reduceOS = mq.matches;
      root.classList.toggle('ui-motion-off', !Motion.isOn());
      document.body && document.body.classList.toggle('ui-motion-off', !Motion.isOn());
      try { document.dispatchEvent(new CustomEvent('ascend:motionchange', { detail: { on: Motion.isOn() } })); } catch (_) {}
    };
    if (mq.addEventListener) mq.addEventListener('change', onMq); else if (mq.addListener) mq.addListener(onMq);
  }
  window.ASCEND_MOTION = Motion;

  /* ------------------------------------------------------------ topbar var */
  function updateTopbarHeight() {
    var bar = document.querySelector('.topbar');
    var h = bar ? Math.round(bar.getBoundingClientRect().height) : 0;
    if (h > 0) root.style.setProperty('--topbar-h', h + 'px');
  }
  updateTopbarHeight();
  window.addEventListener('resize', updateTopbarHeight, { passive: true });
  window.addEventListener('orientationchange', updateTopbarHeight, { passive: true });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(updateTopbarHeight).catch(function () {});
  document.addEventListener('ascend:page-loaded', updateTopbarHeight);

  /* ------------------------------------------------------------------ tilt */
  function initTilt(scope) {
    var nodes = (scope || document).querySelectorAll('.asc-tilt,[data-tilt]');
    Array.prototype.forEach.call(nodes, function (card) {
      if (card.dataset.tiltReady) return;
      card.dataset.tiltReady = '1';
      var raf = 0;
      card.addEventListener('pointermove', function (event) {
        if (!Motion.isOn()) return;
        if (raf) return;
        raf = requestAnimationFrame(function () {
          raf = 0;
          var box = card.getBoundingClientRect();
          var mx = ((event.clientX - box.left) / box.width) * 100;
          var my = ((event.clientY - box.top) / box.height) * 100;
          card.style.setProperty('--mx', mx.toFixed(1) + '%');
          card.style.setProperty('--my', my.toFixed(1) + '%');
        });
      });
      card.addEventListener('pointerleave', function () {
        card.style.removeProperty('--mx');
        card.style.removeProperty('--my');
      });
    });
  }

  /* ------------------------------------------------------- magnetic buttons */
  function initMagnetic(scope) {
    var nodes = (scope || document).querySelectorAll('[data-magnetic]');
    Array.prototype.forEach.call(nodes, function (btn) {
      if (btn.dataset.magneticReady) return;
      btn.dataset.magneticReady = '1';
      btn.addEventListener('pointermove', function (event) {
        if (!Motion.isOn()) return;
        var box = btn.getBoundingClientRect();
        var dx = (event.clientX - (box.left + box.width / 2)) / Math.max(box.width, 1);
        var dy = (event.clientY - (box.top + box.height / 2)) / Math.max(box.height, 1);
        btn.style.transform = 'translate(' + (dx * 6).toFixed(2) + 'px,' + (dy * 5 - 1).toFixed(2) + 'px)';
      });
      btn.addEventListener('pointerleave', function () { btn.style.transform = ''; });
    });
  }

  /* --------------------------------------------------------------- bubbles */
  var Bubble = {
    nodes: [],
    raf: 0,
    mount: function (host, count) {
      if (!host || host.dataset.bubblesReady) return;
      host.dataset.bubblesReady = '1';
      var total = count || 14;
      for (var i = 0; i < total; i++) {
        var b = document.createElement('span');
        var size = rand(10, 46);
        b.className = 'ui-bubble';
        b.setAttribute('aria-hidden', 'true');
        b.style.width = size.toFixed(0) + 'px';
        b.style.height = size.toFixed(0) + 'px';
        b.style.left = rand(2, 88).toFixed(1) + '%';
        b.style.top = rand(4, 86).toFixed(1) + '%';
        b.style.opacity = (rand(22, 55) / 100).toFixed(2);
        b._vy = rand(-0.22, -0.06);
        b._vx = rand(-0.12, 0.12);
        b._phase = rand(0, Math.PI * 2);
        host.appendChild(b);
        this.nodes.push(b);
      }
      this.start();
    },
    start: function () {
      if (this.raf || !this.nodes.length) return;
      if (!Motion.isOn()) { this.stopAll(); return; }
      var self = this;
      var tick = function (time) {
        self.raf = requestAnimationFrame(tick);
        if (!Motion.isOn()) { self.stopAll(); return; }
        for (var i = 0; i < self.nodes.length; i++) {
          var b = self.nodes[i];
          b._phase += 0.0055;
          b.style.transform = 'translate3d(' + (Math.sin(b._phase) * 14).toFixed(2) + 'px,' + (Math.cos(b._phase * 0.8) * 10).toFixed(2) + 'px,0)';
        }
      };
      this.raf = requestAnimationFrame(tick);
    },
    stopAll: function () {
      if (this.raf) cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.nodes.forEach(function (b) { b.style.transform = 'none'; });
    }
  };

  /* -------------------------------------------------------------- counters */
  function animateCount(node) {
    var target = parseFloat(String(node.dataset.count || node.textContent).replace(/[^0-9.\-]/g, ''));
    if (isNaN(target)) return;
    var prefix = node.dataset.countPrefix || '';
    var suffix = node.dataset.countSuffix || '';
    var decimals = (String(target).split('.')[1] || '').length;
    var start = performance.now();
    var duration = target > 4000 ? 1400 : 1000;
    cancelAnimationFrame(node._countRaf || 0);
    node.textContent = prefix + (0).toFixed(decimals) + suffix;
    var step = function (now) {
      var p = clamp((now - start) / duration, 0, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      var value = target * eased;
      node.textContent = prefix + (decimals ? value.toFixed(decimals) : Math.round(value)) + suffix;
      if (p < 1) node._countRaf = requestAnimationFrame(step);
      else { node.dataset.counted = '1'; node.textContent = prefix + (decimals ? target.toFixed(decimals) : target) + suffix; }
    };
    node._countRaf = requestAnimationFrame(step);
  }
  function initCounters(scope) {
    var nodes = (scope || document).querySelectorAll('[data-count]');
    if (!nodes.length) return;
    if (!('IntersectionObserver' in window)) {
      Array.prototype.forEach.call(nodes, function (n) { n.textContent = (n.dataset.countPrefix || '') + n.dataset.count + (n.dataset.countSuffix || ''); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting || entry.target.dataset.counted) return;
        io.unobserve(entry.target);
        if (Motion.isOn()) animateCount(entry.target);
        else {
          var n = entry.target;
          n.textContent = (n.dataset.countPrefix || '') + n.dataset.count + (n.dataset.countSuffix || '');
          n.dataset.counted = '1';
        }
      });
    }, { threshold: 0.35 });
    Array.prototype.forEach.call(nodes, function (n) { io.observe(n); });
  }

  /* ---------------------------------------------------------------- reveal */
  function initReveal(scope) {
    var nodes = (scope || document).querySelectorAll('.asc-reveal,[data-reveal]');
    if (!nodes.length || !Motion.isOn()) return;
    nodes.forEach(function (node, index) {
      if (node.dataset.revealReady) return;
      node.dataset.revealReady = '1';
      node.style.opacity = '0';
      node.style.transform = 'translateY(14px)';
      node.style.transition = 'opacity .6s cubic-bezier(.22,.61,.36,1) ' + (index * 55) + 'ms, transform .6s cubic-bezier(.22,.61,.36,1) ' + (index * 55) + 'ms';
    });
    requestAnimationFrame(function () {
      nodes.forEach(function (node) { node.style.opacity = ''; node.style.transform = ''; });
    });
  }

  /* -------------------------------------------------------- word splitter */
  function initWords(scope) {
    var nodes = (scope || document).querySelectorAll('.js-words');
    Array.prototype.forEach.call(nodes, function (node) {
      if (node.dataset.wordsReady) return;
      node.dataset.wordsReady = '1';
      var text = node.textContent || '';
      if (!text.trim()) return;
      node.textContent = '';
      node.setAttribute('aria-label', text);
      text.split(/(\s+)/).forEach(function (chunk) {
        if (!chunk.trim()) { node.appendChild(document.createTextNode(chunk)); return; }
        var wrap = document.createElement('span');
        wrap.className = 'word';
        var inner = document.createElement('span');
        inner.className = 'word-inner';
        inner.textContent = chunk;
        wrap.appendChild(inner);
        node.appendChild(wrap);
      });
      var inners = node.querySelectorAll('.word-inner');
      if (!Motion.isOn()) return;
      inners.forEach(function (el, i) {
        el.style.opacity = '0';
        el.style.transform = 'translateY(105%)';
        el.style.transition = 'opacity .5s ease ' + (i * 45) + 'ms, transform .7s cubic-bezier(.22,.61,.36,1) ' + (i * 45) + 'ms';
      });
      requestAnimationFrame(function () {
        inners.forEach(function (el) { el.style.opacity = ''; el.style.transform = ''; });
      });
    });
  }

  /* ------------------------------------------------------------ letter flip */
  function initLetters(scope) {
    var nodes = (scope || document).querySelectorAll('[data-letters]');
    Array.prototype.forEach.call(nodes, function (node) {
      if (node.dataset.lettersReady) return;
      node.dataset.lettersReady = '1';
      var text = node.textContent || '';
      if (!text.trim()) return;
      node.textContent = '';
      node.setAttribute('aria-label', text);
      var letters = [];
      text.split('').forEach(function (ch) {
        var span = document.createElement('span');
        span.className = 'asc-letter';
        span.textContent = ch === ' ' ? '\u00A0' : ch;
        span.setAttribute('aria-hidden', 'true');
        node.appendChild(span);
        letters.push(span);
      });
      if (!Motion.isOn()) return;
      letters.forEach(function (el, i) {
        el.style.opacity = '0';
        el.style.transform = 'translateY(24px) rotateX(-70deg)';
        el.style.transition = 'opacity .55s ease ' + (i * 55) + 'ms, transform .75s cubic-bezier(.22,.61,.36,1) ' + (i * 55) + 'ms';
      });
      requestAnimationFrame(function () {
        letters.forEach(function (el) { el.style.opacity = ''; el.style.transform = ''; });
      });
    });
  }

  /* -------------------------------------------------------------- sticky hero */
  var heroScroll = { nodes: [], ticking: false };
  function updateHeroScroll() {
    var y = window.scrollY || window.pageYOffset || 0;
    heroScroll.nodes.forEach(function (hero) {
      var wrap = hero.closest('[data-sticky-hero]') || hero;
      var box = wrap.getBoundingClientRect();
      if (box.bottom < 0) return;
      var top = parseFloat(getComputedStyle(root).getPropertyValue('--topbar-h')) || 68;
      var progress = clamp((y - (wrap.offsetTop - top)) / Math.max(box.height, 1), 0, 1);
      if (!Motion.isOn() || progress < 0.01) {
        hero.style.transform = '';
        hero.style.opacity = '';
        hero.style.filter = '';
        return;
      }
      hero.style.transform = 'scale(' + (1 - progress * 0.045).toFixed(4) + ') translateY(' + (progress * -6).toFixed(1) + 'px)';
      hero.style.opacity = (1 - progress * 0.34).toFixed(3);
    });
  }
  function initStickyHero(scope) {
    var nodes = (scope || document).querySelectorAll('[data-sticky-hero] .asc-hero,[data-sticky-hero] .student-home-hero,[data-sticky-hero] .overview-banner');
    heroScroll.nodes = Array.prototype.slice.call(nodes);
    if (!heroScroll.nodes.length) return;
    var onScroll = function () {
      if (heroScroll.ticking) return;
      heroScroll.ticking = true;
      requestAnimationFrame(function () { heroScroll.ticking = false; updateHeroScroll(); });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    Motion.onChange(onScroll);
    updateHeroScroll();
  }

  /* ------------------------------------------------------------------ toast */
  function toast(message, kind) {
    if (!message) return;
    var node = document.createElement('div');
    node.className = 'ui-toast toast' + (kind === 'error' ? ' danger is-error' : '');
    node.setAttribute('role', 'status');
    node.textContent = message;
    document.body.appendChild(node);
    requestAnimationFrame(function () { node.classList.add('is-show'); });
    setTimeout(function () {
      node.classList.remove('is-show');
      setTimeout(function () { node.remove(); }, 400);
    }, 4200);
  }
  window.uiToast = toast;

  /* ------------------------------------------------------- sidebar indicator */
  function initSidebar(scope) {
    var nav = (scope || document).querySelector('#sidebar nav');
    if (!nav) return;
    var move = function () {
      var active = nav.querySelector('a.active,a[aria-current="page"]');
      nav.style.setProperty('--indicator-opacity', active ? '1' : '0');
    };
    nav.addEventListener('mouseover', function () {});
    move();
    document.addEventListener('ascend:page-loaded', move);
  }

  /* ------------------------------------------------------- dialog behaviour */
  var lastFocus = null;
  function focusables(root) {
    return Array.prototype.slice.call(root.querySelectorAll(
      'a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'
    )).filter(function (el) { return el.offsetParent !== null || el === document.activeElement; });
  }
  function enhanceDialog(modal) {
    if (!modal || modal.dataset.dialogReady) return;
    modal.dataset.dialogReady = '1';
    var card = modal.querySelector('.modal-card') || modal;
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    if (!card.hasAttribute('aria-labelledby') && !card.hasAttribute('aria-label')) {
      var heading = card.querySelector('h1,h2,h3');
      if (heading) {
        if (!heading.id) heading.id = 'dlg-title-' + Math.random().toString(36).slice(2, 8);
        card.setAttribute('aria-labelledby', heading.id);
      } else {
        card.setAttribute('aria-label', 'Dialog');
      }
    }
  }
  function onDialogKey(event) {
    var modal = document.querySelector('.modal.open');
    if (!modal) return;
    if (event.key === 'Escape') {
      if (typeof window.closeModal === 'function') {
        event.preventDefault();
        window.closeModal(modal.id);
      }
      return;
    }
    if (event.key !== 'Tab') return;
    var list = focusables(modal);
    if (!list.length) return;
    var first = list[0], last = list[list.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
  function watchDialogs() {
    var sync = function () {
      var open = document.querySelector('.modal.open');
      Array.prototype.forEach.call(document.querySelectorAll('.modal'), enhanceDialog);
      if (open && !lastFocus) {
        lastFocus = document.activeElement;
        var list = focusables(open);
        (list[0] || open.querySelector('.modal-card') || open).focus({ preventScroll: true });
        if (!open.querySelector('.modal-card').hasAttribute('tabindex')) open.querySelector('.modal-card').setAttribute('tabindex', '-1');
      } else if (!open && lastFocus) {
        try { lastFocus.focus({ preventScroll: true }); } catch (_) {}
        lastFocus = null;
      }
    };
    var observer = new MutationObserver(sync);
    observer.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'] });
    document.addEventListener('keydown', onDialogKey, true);
    document.addEventListener('ascend:page-loaded', sync);
    sync();
  }

  /* --------------------------------------------------------------- debug HUD */
  function initDebug() {
    if (!debug) return;
    var box = document.createElement('div');
    box.style.cssText = 'position:fixed;right:12px;bottom:12px;z-index:9999;background:#03261c;color:#d9f2e8;font:11px/1.5 ui-monospace,monospace;padding:8px 10px;border-radius:10px;box-shadow:0 18px 40px -20px #000;max-width:240px';
    box.textContent = 'ASCEND UI debug';
    document.body.appendChild(box);
    var frames = 0, last = performance.now(), fps = 0;
    var loop = function (now) {
      frames++;
      if (now - last >= 1000) {
        fps = Math.round((frames * 1000) / (now - last));
        frames = 0;
        last = now;
        box.innerHTML = '<strong>' + BRAND.name + ' UI</strong><br>fps ' + fps +
          '<br>motion ' + (Motion.isOn() ? 'on' : 'off') +
          '<br>hero engine ' + (window.ASCEND_HERO ? (window.ASCEND_HERO.webgl ? 'webgl' : 'fallback') : 'none') +
          '<br>topbar ' + cssVar('--topbar-h', '68px');
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  /* ------------------------------------------------------------------- init */
  function initAll(scope) {
    initTilt(scope);
    initMagnetic(scope);
    initCounters(scope);
    initReveal(scope);
    initWords(scope);
    initLetters(scope);
    initStickyHero(scope);
    initSidebar(scope);
    watchDialogs();
    initDebug();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { initAll(document); });
  else initAll(document);
  document.addEventListener('ascend:page-loaded', function () { initAll(document); updateTopbarHeight(); });

  window.ASCEND_UI = { Motion: Motion, toast: toast, init: initAll, bubbles: Bubble, tilt: initTilt };
})();
