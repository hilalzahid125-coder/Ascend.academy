/* ==========================================================================
   ASCEND HERO ENGINE — dependency-free canvas scenes.
   The approved design used a Three.js / GSAP pipeline; this app is served with
   a strict Content-Security-Policy (script-src 'self') and must work offline,
   so the same emerald/mint depth, bloom and parallax feel is produced with a
   hand-rolled 3D projection on a single <canvas>. If anything is unsupported
   the static SVG fallback stays visible and no error is raised.
   ========================================================================== */
(function () {
  'use strict';

  var reduceOS = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var motionOn = function () {
    return window.ASCEND_MOTION ? window.ASCEND_MOTION.isOn() : !reduceOS;
  };

  function palette() {
    var probe = document.createElement('span');
    probe.style.cssText = 'position:absolute;left:-9999px;top:0;color:var(--green-600)';
    document.body.appendChild(probe);
    var value = getComputedStyle(probe).color;
    probe.remove();
    var m = /(\d+)[,\s]+(\d+)[,\s]+(\d+)/.exec(value || '');
    return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : [15, 154, 115];
  }

  function HeroScene(canvas, host, options) {
    var opts = options || {};
    this.canvas = canvas;
    this.host = host;
    this.ctx = canvas.getContext('2d');
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.rgb = opts.rgb || [15, 154, 115];
    this.light = opts.light || false;
    this.count = opts.count || 46;
    this.soft = !!opts.soft;
    this.speed = opts.speed || 1;
    this.points = [];
    this.raf = 0;
    this.angle = 0;
    this.pointer = { x: 0, y: 0, tx: 0, ty: 0 };
    this.resize();
    this.seed();
  }

  HeroScene.prototype.resize = function () {
    var box = this.host.getBoundingClientRect();
    var width = Math.max(1, Math.round(box.width));
    var height = Math.max(1, Math.round(box.height));
    this.w = width;
    this.h = height;
    this.canvas.width = Math.round(width * this.dpr);
    this.canvas.height = Math.round(height * this.dpr);
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    if (this.points.length) this.seed();
  };

  HeroScene.prototype.seed = function () {
    var radius = Math.max(this.w, this.h) * 0.42;
    this.radius = radius;
    this.points = [];
    var total = Math.max(18, Math.round(this.count * Math.min(1.4, Math.max(0.55, this.w / 620))));
    for (var i = 0; i < total; i++) {
      var theta = Math.acos(1 - 2 * ((i + 0.5) / total));
      var phi = Math.PI * (1 + Math.sqrt(5)) * i;
      this.points.push({
        x: Math.cos(phi) * Math.sin(theta),
        y: Math.cos(theta),
        z: Math.sin(phi) * Math.sin(theta),
        r: 1.1 + Math.random() * 2.4,
        tw: Math.random() * Math.PI * 2
      });
    }
  };

  HeroScene.prototype.tick = function (time) {
    var self = this;
    if (!this.raf) this.raf = 1;
    if (!motionOn()) { this.draw(time, true); this.raf = 0; return; }
    this.raf = requestAnimationFrame(function (t) { self.tick(t || 0); });
    this.draw(time || 0, false);
  };

  HeroScene.prototype.start = function () {
    if (this.raf) return;
    this.host.classList.add('is-ready');
    this.canvas.style.opacity = '';
    var self = this;
    if (!motionOn()) { this.draw(0, true); return; }
    this.raf = requestAnimationFrame(function (t) { self.tick(t); });
  };

  HeroScene.prototype.stop = function () {
    if (this.raf && this.raf !== 1) cancelAnimationFrame(this.raf);
    this.raf = 0;
  };

  HeroScene.prototype.draw = function (time, still) {
    var ctx = this.ctx, w = this.w, h = this.h;
    if (!w || !h) return;
    var t = still ? 12 : time * 0.00018 * this.speed;
    var c = this.rgb;
    var base = this.light ? 'rgba(238,249,244,' : 'rgba(4,26,19,';
    ctx.clearRect(0, 0, w, h);

    /* soft radial bloom behind the constellation */
    var gx = w * 0.7, gy = h * 0.46;
    var glow = ctx.createRadialGradient(gx, gy, 0, gx, gy, Math.max(w, h) * 0.62);
    if (this.light) {
      glow.addColorStop(0, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',.20)');
      glow.addColorStop(0.55, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',.08)');
      glow.addColorStop(1, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',0)');
    } else {
      glow.addColorStop(0, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',.42)');
      glow.addColorStop(0.5, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',.14)');
      glow.addColorStop(1, 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',0)');
    }
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, w, h);

    /* inner core */
    var core = ctx.createRadialGradient(gx, gy, 0, gx, gy, Math.max(w, h) * 0.24);
    core.addColorStop(0, this.light ? 'rgba(163,214,75,.22)' : 'rgba(163,214,75,.30)');
    core.addColorStop(1, 'rgba(163,214,75,0)');
    ctx.fillStyle = core;
    ctx.fillRect(0, 0, w, h);

    this.pointer.x += (this.pointer.tx - this.pointer.x) * 0.045;
    this.pointer.y += (this.pointer.ty - this.pointer.y) * 0.045;

    var cx = w * 0.63 + this.pointer.x * 18;
    var cy = h * 0.48 + this.pointer.y * 14;
    var radius = Math.min(this.radius, Math.min(w, h) * 0.46);
    var tilt = 0.34 + this.pointer.y * 0.12;
    var spin = t * 0.55 + this.pointer.x * 0.16;
    var projected = [];
    var i, p, cosA, sinA, cosT, sinT, x, y, z, scale, depth, px, py;

    for (i = 0; i < this.points.length; i++) {
      p = this.points[i];
      cosA = Math.cos(spin + p.tw * 0.02);
      sinA = Math.sin(spin + p.tw * 0.02);
      x = p.x * cosA - p.z * sinA;
      z = p.x * sinA + p.z * cosA;
      y = p.y;
      cosT = Math.cos(tilt);
      sinT = Math.sin(tilt);
      y = y * cosT - z * sinT;
      z = y * sinT + z * cosT;
      depth = (z + 1.6) / 2.6;
      scale = 0.55 + depth * 0.75;
      px = cx + x * radius * scale;
      py = cy + y * radius * scale * 0.82;
      projected.push({ x: px, y: py, z: depth, r: p.r * scale, tw: p.tw });
    }

    /* links between nearby nodes */
    for (i = 0; i < projected.length; i++) {
      for (var j = i + 1; j < projected.length; j++) {
        var a = projected[i], b = projected[j];
        var dist = Math.hypot(a.x - b.x, a.y - b.y);
        var limit = Math.min(w, h) * 0.24;
        if (dist > limit) continue;
        var alpha = (1 - dist / limit) * (this.soft ? 0.16 : 0.30) * Math.min(a.z, b.z);
        ctx.strokeStyle = 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + alpha.toFixed(3) + ')';
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }

    /* orbit rings */
    var rings = 3;
    for (i = 0; i < rings; i++) {
      var ringR = radius * (0.62 + i * 0.17);
      ctx.strokeStyle = this.light
        ? 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (0.16 - i * 0.035) + ')'
        : 'rgba(' + Math.min(255, c[0] + 90) + ',' + Math.min(255, c[1] + 80) + ',' + Math.min(255, c[2] + 60) + ',' + (0.20 - i * 0.045) + ')';
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      ctx.ellipse(cx, cy, ringR, ringR * (0.30 + i * 0.03), spin * 0.4 + i * 0.6, 0, Math.PI * 2);
      ctx.stroke();
    }

    /* nodes */
    for (i = 0; i < projected.length; i++) {
      p = projected[i];
      var twinkle = 0.65 + Math.sin((still ? 1 : time * 0.0022) + p.tw) * 0.35;
      var alpha2 = (0.25 + p.z * 0.75) * twinkle * (this.soft ? 0.7 : 1);
      var size = Math.max(0.9, p.r * (1 + p.z * 0.5));
      var nodeFill = this.light
        ? 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (alpha2 * 0.85).toFixed(3) + ')'
        : 'rgba(' + Math.min(255, c[0] + 120) + ',' + Math.min(255, c[1] + 60) + ',' + Math.min(255, c[2] + 40) + ',' + alpha2.toFixed(3) + ')';
      ctx.fillStyle = nodeFill;
      ctx.beginPath();
      ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
      ctx.fill();
      if (p.z > 0.72) {
        ctx.fillStyle = this.light ? 'rgba(163,214,75,' + (alpha2 * 0.5).toFixed(3) + ')' : 'rgba(255,255,255,' + (alpha2 * 0.65).toFixed(3) + ')';
        ctx.beginPath();
        ctx.arc(p.x, p.y, size * 0.42, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    /* horizon line for depth */
    var horizon = ctx.createLinearGradient(0, h * 0.72, 0, h);
    horizon.addColorStop(0, this.light ? 'rgba(238,249,244,0)' : base + '0)');
    horizon.addColorStop(1, this.light ? 'rgba(238,249,244,.35)' : base + '.55)');
    ctx.fillStyle = horizon;
    ctx.fillRect(0, h * 0.72, w, h * 0.28);
  };

  /* -------------------------------------------------------------- mounting */
  var scenes = [];
  function mount(id, options) {
    var canvas = document.getElementById(id);
    if (!canvas) return null;
    var host = canvas.closest('.auth-showcase,.student-home-hero,.asc-hero,.ui-hero,[data-hero]');
    if (!host) return null;
    if (host === document.body) return null;
    var fallback = host.querySelector('.hero-fallback');
    var scene;
    try {
      scene = new HeroScene(canvas, host, options);
    } catch (error) {
      if (window.console && console.warn) console.warn('[ASCEND hero] canvas unavailable:', error);
      if (fallback) fallback.hidden = false;
      return null;
    }
    scene.fallback = fallback;
    if (!motionOn()) {
      host.classList.add('is-ready');
      canvas.style.opacity = '1';
      scene.draw(0, true);
    } else {
      scene.start();
    }
    host.addEventListener('pointermove', function (event) {
      var box = host.getBoundingClientRect();
      scene.pointer.tx = ((event.clientX - box.left) / Math.max(box.width, 1) - 0.5) * 2;
      scene.pointer.ty = ((event.clientY - box.top) / Math.max(box.height, 1) - 0.5) * 2;
    }, { passive: true });
    host.addEventListener('pointerleave', function () { scene.pointer.tx = 0; scene.pointer.ty = 0; });
    var resizeTimer = 0;
    var onResize = function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        scene.resize();
        scene.draw(0, !motionOn());
        if (window.ASCEND_UI && window.ASCEND_UI.Motion) window.ASCEND_UI.Motion.onChange(function (on) { if (!on) scene.draw(0, true); });
      }, 160);
    };
    window.addEventListener('resize', onResize, { passive: true });
    if (window.ASCEND_MOTION) {
      window.ASCEND_MOTION.onChange(function (on) {
        if (on) scene.start(); else { scene.stop(); scene.draw(0, true); }
      });
    }
    scenes.push(scene);
    return scene;
  }

  function boot() {
    var rgb = palette();
    var guest = document.body.classList.contains('role-guest');
    var light = document.body.classList.contains('role-student') || document.body.classList.contains('role-parent');
    var scene = mount('hero-canvas', guest
      ? { rgb: rgb, light: false, count: 68, speed: 1.15 }
      : { rgb: rgb, light: light, count: 34, speed: 0.85, soft: true });
    window.ASCEND_HERO = { webgl: false, canvas: true, scenes: scene ? [scene] : [] };
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
