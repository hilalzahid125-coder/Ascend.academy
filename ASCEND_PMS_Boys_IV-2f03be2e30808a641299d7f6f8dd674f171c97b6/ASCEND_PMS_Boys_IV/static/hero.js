/* ==========================================================================
   ASCEND HERO ENGINE — dependency-free canvas scenes.
   The approved design used a Three.js / GSAP pipeline; this app is served with
   a strict Content-Security-Policy (script-src 'self') and must work offline,
   so the same emerald/mint depth, bloom and parallax feel is produced with a
   hand-rolled 3D projection on a single <canvas>. If anything is unsupported
   the static fallback stays visible and no error is raised.

   FIVE SCENES, ONE LANGUAGE
   Every scene shares the same projection, lighting and pointer easing so the
   portals feel like one product. They differ in what they build, not how it
   moves:
     constellation (guest/login)  layered orbit rings + node web
     trophy        (student)      stepped podium + floating cubes + sparks
     orbit         (parent)       elliptical arcs + travelling pearls
     grid          (admin)        low tessellated depth field
     lectern       (teacher)      stacked books + rising light motes

   PERFORMANCE BUDGET
   - Device pixel ratio capped at 2 (1.35 on low-core machines).
   - Paused entirely by the Motion toggle and when the tab is hidden.
   - Off-screen canvases are not drawn (IntersectionObserver).
   - Particle counts scale with hero width and hardware concurrency.
   ========================================================================== */
(function () {
  'use strict';

  var reduceOS = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var motionOn = function () {
    return window.ASCEND_MOTION ? window.ASCEND_MOTION.isOn() : !reduceOS;
  };

  var cores = (navigator.hardwareConcurrency || 8);
  var LOW_POWER = cores <= 4 || window.innerWidth < 700;

  function palette() {
    var probe = document.createElement('span');
    probe.style.cssText = 'position:absolute;left:-9999px;top:0;color:var(--green-600)';
    document.body.appendChild(probe);
    var value = getComputedStyle(probe).color;
    probe.remove();
    var m = /(\d+)[,\s]+(\d+)[,\s]+(\d+)/.exec(value || '');
    return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : [15, 154, 115];
  }

  function rgba(c, alpha) {
    return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + alpha + ')';
  }

  function lift(c, amount) {
    return [
      Math.min(255, c[0] + amount),
      Math.min(255, c[1] + amount),
      Math.min(255, c[2] + amount)
    ];
  }

  function shade(c, amount) {
    return [
      Math.max(0, c[0] - amount),
      Math.max(0, c[1] - amount),
      Math.max(0, c[2] - amount)
    ];
  }

  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function roundRect(ctx, x, y, w, h, r) {
    var radius = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + w - radius, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
    ctx.lineTo(x + w, y + h - radius);
    ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
    ctx.lineTo(x + radius, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
  }

  /* ------------------------------------------------------------ composition
     The copy column may run to 70% of a banner, so the art is anchored past
     that line. On narrow banners the text spans nearly the full width, so the
     composition is pushed further right and shrunk until it clears the copy. */
  HeroScene.prototype.anchorX = function (ratio) {
    if (!this.fill) return this.w * ratio;
    var narrow = Math.min(1, Math.max(0, (this.w - 420) / 360));
    var r = ratio + (0.80 - ratio) * (1 - narrow) * 0.85;
    return this.w * Math.min(0.84, r);
  };

  /* =========================================================== THE SCENE */
  function HeroScene(canvas, host, options) {
    var opts = options || {};
    this.canvas = canvas;
    this.host = host;
    this.ctx = canvas.getContext('2d');
    this.dpr = Math.min(window.devicePixelRatio || 1, LOW_POWER ? 1.35 : 2);
    this.rgb = opts.rgb || [15, 154, 115];
    this.light = opts.light || false;
    this.count = opts.count || 46;
    this.soft = !!opts.soft;
    this.speed = opts.speed || 1;
    this.scene = opts.scene || 'constellation';
    this.fill = !!opts.fill;
    this.accent = opts.accent || [163, 214, 75];
    this.points = [];
    this.sparks = [];
    this.pearls = [];
    this.motes = [];
    this.gridNodes = [];
    this.cubes = [];
    this.raf = 0;
    this.visible = true;
    this.startAt = 0;
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
    var w = this.w, h = this.h;
    /* Wide, short banners (the dashboard .overview-banner) would shrink a
       min(w,h) radius to nothing, so they scale from the height instead. */
    this.radius = Math.min(
      Math.max(w, h) * 0.42,
      Math.min(w, h) * (this.fill ? 0.62 : 0.46)
    );
    var density = Math.min(1.35, Math.max(0.55, w / 620));
    var i;

    this.points = [];
    var total = Math.max(16, Math.round(this.count * density));
    for (i = 0; i < total; i++) {
      var theta = Math.acos(1 - 2 * ((i + 0.5) / total));
      var phi = Math.PI * (1 + Math.sqrt(5)) * i;
      this.points.push({
        x: Math.cos(phi) * Math.sin(theta),
        y: Math.cos(theta),
        z: Math.sin(phi) * Math.sin(theta),
        r: 1.1 + Math.random() * 2.2,
        tw: Math.random() * Math.PI * 2
      });
    }

    this.podium = [
      { bx: -0.44, bw: 0.30, bh: 0.42, by: 0.30, delay: 0 },
      { bx: 0.00, bw: 0.34, bh: 0.62, by: 0.10, delay: 0.14 },
      { bx: 0.42, bw: 0.28, bh: 0.34, by: 0.38, delay: 0.28 }
    ];
    this.cubes = [];
    var cubeCount = LOW_POWER ? 6 : 10;
    for (i = 0; i < cubeCount; i++) {
      this.cubes.push({
        x: (Math.random() - 0.5) * 2.1,
        y: (Math.random() - 0.5) * 1.5,
        size: 0.055 + Math.random() * 0.085,
        spin: Math.random() * Math.PI * 2,
        spinSpeed: (Math.random() - 0.5) * 0.6,
        bob: Math.random() * Math.PI * 2,
        depth: 0.5 + Math.random() * 0.8
      });
    }
    this.sparks = [];
    var sparkCount = LOW_POWER ? 22 : 46;
    for (i = 0; i < sparkCount; i++) {
      this.sparks.push({
        x: Math.random(),
        y: Math.random(),
        size: 0.7 + Math.random() * 1.8,
        rise: 0.006 + Math.random() * 0.018,
        drift: (Math.random() - 0.5) * 0.006,
        tw: Math.random() * Math.PI * 2,
        tone: Math.random() > 0.55 ? 'accent' : 'mint'
      });
    }

    this.orbitRings = [
      { rx: 0.86, ry: 0.30, rot: -0.22, speed: 0.55, alpha: 0.30 },
      { rx: 0.66, ry: 0.22, rot: 0.16, speed: -0.78, alpha: 0.34 },
      { rx: 1.02, ry: 0.36, rot: 0.42, speed: 0.34, alpha: 0.18 }
    ];
    this.pearls = [];
    var pearlCount = LOW_POWER ? 3 : 5;
    for (i = 0; i < pearlCount; i++) {
      this.pearls.push({
        ring: i % this.orbitRings.length,
        phase: Math.random() * Math.PI * 2,
        size: 2.4 + Math.random() * 3.4,
        depth: 0.4 + Math.random() * 0.9
      });
    }

    this.gridNodes = [];
    this.gridCols = LOW_POWER ? 9 : 13;
    this.gridRows = LOW_POWER ? 5 : 7;
    for (var r = 0; r < this.gridRows; r++) {
      for (var c = 0; c < this.gridCols; c++) {
        this.gridNodes.push({
          cx: (c / (this.gridCols - 1)) * 2 - 1,
          cy: (r / (this.gridRows - 1)) * 2 - 1,
          wave: Math.random() * Math.PI * 2
        });
      }
    }

    this.motes = [];
    var moteCount = LOW_POWER ? 26 : 52;
    for (i = 0; i < moteCount; i++) {
      this.motes.push({
        x: Math.random(),
        y: Math.random(),
        r: 0.8 + Math.random() * 2.1,
        rise: 0.004 + Math.random() * 0.012,
        drift: (Math.random() - 0.5) * 0.004,
        tw: Math.random() * Math.PI * 2
      });
    }

    this.density = density;
  };

  HeroScene.prototype.tick = function (time) {
    var self = this;
    if (!motionOn() || !this.visible) {
      this.draw(time || 0, true);
      this.raf = 0;
      return;
    }
    this.raf = requestAnimationFrame(function (t) { self.tick(t || 0); });
    /* Ease the pointer toward its target here rather than in a second global
       loop: one rAF per visible hero, and the easing stops when the scene does. */
    this.pointer.x += (this.pointer.tx - this.pointer.x) * 0.060;
    this.pointer.y += (this.pointer.ty - this.pointer.y) * 0.060;
    this.draw(time || 0, false);
  };

  HeroScene.prototype.start = function () {
    if (this.raf) return;
    if (!this.startAt) this.startAt = performance.now();
    this.host.classList.add('is-ready');
    this.canvas.style.opacity = '';
    var self = this;
    if (!motionOn()) { this.draw(0, true); return; }
    this.raf = requestAnimationFrame(function (t) { self.tick(t); });
  };

  HeroScene.prototype.stop = function () {
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
  };

  HeroScene.prototype.project = function (p, spin, tilt, cx, cy, radius) {
    var cosA = Math.cos(spin + p.tw * 0.02);
    var sinA = Math.sin(spin + p.tw * 0.02);
    var x = p.x * cosA - p.z * sinA;
    var z = p.x * sinA + p.z * cosA;
    var cosT = Math.cos(tilt);
    var sinT = Math.sin(tilt);
    var y2 = p.y * cosT - z * sinT;
    var z2 = p.y * sinT + z * cosT;
    var depth = (z2 + 1.6) / 2.6;
    var scale = 0.55 + depth * 0.75;
    return {
      x: cx + x * radius * scale,
      y: cy + y2 * radius * scale * 0.82,
      z: depth,
      scale: scale,
      r: p.r * scale,
      tw: p.tw
    };
  };

  /* ============================================ TONE TABLE (light vs dark)
     The login showcase and every .overview-banner are deep emerald panels;
     only .student-home-hero is a light mint banner. Painting light-theme
     emerald on top of a mint surface produces a washed-out haze, so light
     mode draws *ink* (deep emerald) for geometry and *white glass* for
     solids, and only the glow layer stays tinted. Dark mode paints luminous
     emerald, pale-mint solids and lime accents that read on dark green. */
  HeroScene.prototype.tones = function () {
    if (this.light) {
      return {
        ink: this.rgb,                       /* deep emerald for structure */
        deep: lift(this.rgb, 18),
        solid: [255, 255, 255],              /* glassy white cubes/pearls */
        accent: this.accent,
        dust: this.rgb
      };
    }
    return {
      ink: lift(this.rgb, 70),
      deep: lift(this.rgb, 130),
      solid: lift(this.accent, 60),
      accent: this.accent,
      dust: lift(this.rgb, 90)
    };
  };

  HeroScene.prototype.softGlow = function (w, h, gx, gy, kick) {
    var ctx = this.ctx, c = this.rgb;
    /* Banner scenes get one vast, faint wash. A small bright radial ends in a
       visible disc edge (and bands into rings on dark panels); a huge faint
       one simply lifts the banner behind the art, with no boundary anywhere
       on screen. Richness now lives in the objects, not in stacked fog. */
    var span = this.fill ? Math.max(w, h) * 0.95 : Math.max(w, h);
    var fade = this.fill ? span : Math.max(span * (0.60 + kick), Math.min(w, h) * 0.55);
    var g = ctx.createRadialGradient(gx, gy, 0, gx, gy, fade);
    if (this.light) {
      g.addColorStop(0, rgba(lift(c, 40), 0.13));
      g.addColorStop(0.5, rgba(lift(c, 70), 0.05));
      g.addColorStop(1, rgba(c, 0));
    } else {
      g.addColorStop(0, rgba(lift(c, 10), this.fill ? 0.10 : 0.30));
      g.addColorStop(0.45, rgba(c, this.fill ? 0.05 : 0.20));
      g.addColorStop(1, rgba(c, 0));
    }
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  };

  HeroScene.prototype.core = function (w, h, gx, gy, scale) {
    var ctx = this.ctx;
    var span = this.fill ? this.radius * 0.42 : Math.max(w, h) * 0.17;
    var a = this.light ? 0.13 : (this.fill ? 0.12 : 0.34);
    var g = ctx.createRadialGradient(gx, gy, 0, gx, gy, span * (scale || 1));
    g.addColorStop(0, rgba(this.accent, a));
    g.addColorStop(1, rgba(this.accent, 0));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  };

  /* Sparkle / node dot. Light mode needs a dark ink dot: a pale one vanishes. */
  HeroScene.prototype.dot = function (x, y, r, alpha, tone) {
    var ctx = this.ctx, t = this.tones();
    var c = tone || t.ink;
    ctx.fillStyle = rgba(c, alpha);
    ctx.beginPath();
    ctx.arc(x, y, Math.max(0.55, r), 0, Math.PI * 2);
    ctx.fill();
  };

  HeroScene.prototype.halo = function (x, y, r, alpha, tone) {
    var ctx = this.ctx, t = this.tones();
    var c = tone || t.accent;
    var g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, rgba(c, alpha));
    g.addColorStop(0.45, rgba(c, alpha * 0.40));
    g.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  };

  /* Isometric cube. Light: white top, mint-grey flanks, emerald edge.
     Dark: emerald top, deep flanks, lime edge. */
  HeroScene.prototype.cube = function (x, y, size, spin, depth, alpha) {
    var ctx = this.ctx, t = this.tones();
    var top, left, right, edge;
    if (this.light) {
      top = [255, 255, 255];
      left = lift(this.rgb, 118);
      right = lift(this.rgb, 86);
      edge = this.rgb;
    } else {
      /* Jade glass: luminous green top, deep saturated flanks. The old
         near-white top read as a white box on the dark banner. */
      top = lift(this.rgb, 118);
      left = lift(this.rgb, 18);
      right = lift(this.rgb, 62);
      edge = this.accent;
    }
    var s = size;
    var wob = Math.sin(spin) * s * 0.16;
    ctx.save();
    ctx.translate(x, y);
    ctx.beginPath();
    ctx.moveTo(0, -s);
    ctx.lineTo(s * 0.86, -s * 0.5);
    ctx.lineTo(0, 0);
    ctx.lineTo(-s * 0.86, -s * 0.5);
    ctx.closePath();
    ctx.fillStyle = rgba(top, alpha);
    ctx.fill();
    ctx.strokeStyle = rgba(edge, alpha * 0.30);
    ctx.lineWidth = 0.7;
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(-s * 0.86, -s * 0.5);
    ctx.lineTo(0, 0);
    ctx.lineTo(0, s * 1.02 + wob);
    ctx.lineTo(-s * 0.86, s * 0.52 + wob);
    ctx.closePath();
    ctx.fillStyle = rgba(left, alpha * (this.light ? 0.55 : 0.85));
    ctx.fill();
    ctx.strokeStyle = rgba(edge, alpha * 0.22);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(s * 0.86, -s * 0.5);
    ctx.lineTo(0, 0);
    ctx.lineTo(0, s * 1.02 + wob);
    ctx.lineTo(s * 0.86, s * 0.52 + wob);
    ctx.closePath();
    ctx.fillStyle = rgba(right, alpha * (this.light ? 0.45 : 0.72));
    ctx.fill();
    ctx.strokeStyle = rgba(edge, alpha * 0.20);
    ctx.stroke();
    ctx.restore();
  };

  /* ---------------------------------------------------------- SCENE: trophy
     Student portal. Three stepped rises on a floor disc, a light beam above
     the tallest, white glass cubes drifting in front, lime sparks rising. */
  /* ---------------------------------------------------------- SCENE: trophy
     Student portal. Three jade steps rising from a floor dial, a breathing
     light beam, drifting glass cubes and rising sparks. The steps never sit
     still: after their entrance they keep a slow staggered breath, and a
     specular sweep travels across their faces so the podium always feels
     lit rather than painted. */
  HeroScene.prototype.drawTrophy = function (time, still) {
    var ctx = this.ctx, w = this.w, h = this.h, t0 = this.tones(), c = this.rgb;
    var t = still ? 0.62 : time * 0.001 * this.speed;
    var gx = this.anchorX(0.73) + this.pointer.x * 26;
    var gy = h * 0.44 + this.pointer.y * 16;
    var radius = this.radius * (this.fill && w < 620 ? 0.80 : 1);

    this.softGlow(w, h, gx, gy, 0.04);
    this.core(w, h, gx, gy, 1.0);

    /* Floor dial: a soft pool of light plus one slowly-rotating dashed orbit
       etched on the ground, so the floor itself is alive. */
    var floorY = h * 0.82;
    var floorR = radius * 1.05;
    ctx.save();
    ctx.translate(gx, floorY);
    ctx.scale(1, 0.24);
    var disc = ctx.createRadialGradient(0, 0, 0, 0, 0, floorR);
    disc.addColorStop(0, rgba(lift(c, 60), this.light ? 0.20 : 0.18));
    disc.addColorStop(0.6, rgba(c, this.light ? 0.08 : 0.09));
    disc.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = disc;
    ctx.beginPath();
    ctx.arc(0, 0, floorR, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = this.light ? rgba(lift(c, 40), 0.30) : rgba(lift(c, 110), 0.30);
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 9]);
    ctx.lineDashOffset = still ? 0 : -t * 14;
    ctx.beginPath();
    ctx.arc(0, 0, floorR * 0.92, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();

    /* The beam breathes, and its edges feather out: the old flat trapezoid
       read as a cardboard column. */
    var beamPulse = still ? 0.5 : (0.5 + 0.5 * Math.sin(t * 1.3));
    var beamA = (this.light ? 0.10 : 0.16) * (0.7 + 0.5 * beamPulse);
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(gx - radius * 0.24, h * 0.02);
    ctx.lineTo(gx + radius * 0.24, h * 0.02);
    ctx.lineTo(gx + radius * 0.60, floorY);
    ctx.lineTo(gx - radius * 0.60, floorY);
    ctx.closePath();
    ctx.clip();
    var beam = ctx.createLinearGradient(gx - radius * 0.6, 0, gx + radius * 0.6, 0);
    beam.addColorStop(0, rgba(this.accent, 0));
    beam.addColorStop(0.5, rgba(this.accent, beamA));
    beam.addColorStop(1, rgba(this.accent, 0));
    ctx.fillStyle = beam;
    ctx.fillRect(gx - radius * 0.62, h * 0.02, radius * 1.24, floorY);
    var beamV = ctx.createLinearGradient(0, h * 0.02, 0, floorY);
    beamV.addColorStop(0, rgba(lift(c, 80), 0));
    beamV.addColorStop(1, rgba(lift(c, 80), beamA * 0.9));
    ctx.fillStyle = beamV;
    ctx.fillRect(gx - radius * 0.62, h * 0.02, radius * 1.24, floorY);
    ctx.restore();

    var appear = still ? 1 : Math.min(1, (time - this.startAt) / 900);
    /* One band of light travels across the whole podium and loops. Shared
       phase, per-step offset, so it reads as a single passing gleam. */
    var sweepT = still ? 0.35 : ((t * 0.14) % 1.4) - 0.2;
    for (var p = 0; p < this.podium.length; p++) {
      var step = this.podium[p];
      var local = Math.max(0, Math.min(1, (appear - step.delay) / (1 - step.delay || 1)));
      if (local <= 0) continue;
      var ease = easeOutCubic(local);
      var bw = step.bw * radius * 1.5;
      var bh = step.bh * radius * 1.25;
      var bx = gx + step.bx * radius * 1.35;
      var baseY = floorY + step.by * radius * 0.10;
      /* Entrance rise, then a perpetual staggered breath: the steps are never
         frozen once placed. */
      var breath = still ? 0 : Math.sin(t * 1.1 + p * 1.4) * 2.4 * ease;
      var rise = (1 - ease) * 22 - breath;
      var topY = baseY - bh + rise;

      var face = ctx.createLinearGradient(0, topY, 0, baseY + rise);
      if (this.light) {
        /* Deep emerald solids with a light top: on a mint banner, pale shapes
           disappear. Contrast comes from the ink, not from the fill. */
        face.addColorStop(0, rgba(lift(c, 40), 0.94 * ease));
        face.addColorStop(0.65, rgba(c, 0.95 * ease));
        face.addColorStop(1, rgba(shade(c, 26), 0.94 * ease));
      } else {
        /* Jade, not milk: a luminous rim at the top falling into deep
           saturated emerald at the base. */
        face.addColorStop(0, rgba([126, 224, 182], 0.96 * ease));
        face.addColorStop(0.38, rgba([34, 158, 122], 0.95 * ease));
        face.addColorStop(1, rgba([6, 84, 62], 0.96 * ease));
      }
      ctx.fillStyle = face;
      roundRect(ctx, bx - bw / 2, topY, bw, bh, 4);
      ctx.fill();
      ctx.strokeStyle = this.light
        ? rgba(lift(c, 60), 0.55 * ease)
        : rgba([150, 240, 200], 0.35 * ease);
      ctx.lineWidth = 1;
      ctx.stroke();

      /* travelling specular band, clipped to the step */
      var sxp = bx - bw / 2 + (sweepT + p * 0.12) * bw * 1.6 - bw * 0.3;
      if (sxp > bx - bw && sxp < bx + bw * 1.5) {
        ctx.save();
        roundRect(ctx, bx - bw / 2, topY, bw, bh, 4);
        ctx.clip();
        var sheen = ctx.createLinearGradient(sxp - bw * 0.22, 0, sxp + bw * 0.22, 0);
        sheen.addColorStop(0, 'rgba(255,255,255,0)');
        sheen.addColorStop(0.5, this.light
          ? rgba([255, 255, 255], 0.20 * ease)
          : rgba([220, 255, 236], 0.16 * ease));
        sheen.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = sheen;
        ctx.fillRect(bx - bw / 2, topY, bw, bh);
        ctx.restore();
      }

      /* cap: a radial sheen, bright heart melting into an emerald rim */
      var cap = ctx.createRadialGradient(bx - bw * 0.12, topY - 1, 0, bx, topY, bw * 0.55);
      if (this.light) {
        cap.addColorStop(0, rgba([255, 255, 255], 0.98 * ease));
        cap.addColorStop(1, rgba(lift(c, 120), 0.95 * ease));
      } else {
        cap.addColorStop(0, rgba([214, 255, 236], 0.98 * ease));
        cap.addColorStop(0.55, rgba([140, 232, 190], 0.95 * ease));
        cap.addColorStop(1, rgba([46, 160, 124], 0.95 * ease));
      }
      ctx.fillStyle = cap;
      ctx.beginPath();
      ctx.ellipse(bx, topY, bw / 2, bw / 6.2, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = this.light ? rgba(c, 0.32 * ease) : rgba([170, 245, 210], 0.40 * ease);
      ctx.lineWidth = 1;
      ctx.stroke();

      /* front edge highlight */
      ctx.strokeStyle = rgba([255, 255, 255], this.light ? 0.9 * ease : 0.34 * ease);
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(bx - bw / 2 + 2, topY + 3);
      ctx.lineTo(bx - bw / 2 + 2, baseY + rise - 1);
      ctx.stroke();
    }

    for (var i = 0; i < this.cubes.length; i++) {
      var cube = this.cubes[i];
      var bob = Math.sin(t * 0.9 + cube.bob) * 0.05;
      var cxp = gx + (cube.x + this.pointer.x * 0.10) * radius * 1.30;
      var cyp = gy + (cube.y + bob + this.pointer.y * 0.08) * radius * 0.95 - radius * 0.10;
      var size = cube.size * radius * (0.55 + cube.depth * 0.5);
      this.cube(cxp, cyp, size, t * cube.spinSpeed + cube.spin, cube.depth,
        (this.light ? 0.72 : 0.66) * (0.55 + cube.depth * 0.45));
    }

    for (var s = 0; s < this.sparks.length; s++) {
      var sp = this.sparks[s];
      var sy = still ? sp.y : (sp.y - (t * 0.16 * sp.rise * 100) % 1 + 1) % 1;
      var sx = sp.x + Math.sin(t * 0.6 + sp.tw) * 0.012;
      var twinkle = 0.45 + Math.sin(t * 1.6 + sp.tw) * 0.55;
      var tone = sp.tone === 'accent' ? this.accent : t0.dust;
      var spAlpha = twinkle * (this.light ? 0.30 : 0.66);
      if (sp.size > 1.9 && !this.fill) this.halo(w * (0.44 + sx * 0.34), h * (0.12 + sy * 0.66), sp.size * 5, spAlpha * 0.5, tone);
      this.dot(w * (0.44 + sx * 0.34), h * (0.12 + sy * 0.66), sp.size, spAlpha, tone);
    }

    this.drawDust(w, h, gx, gy, radius, t, still, 0.85);
  };

  /* ----------------------------------------------------------- SCENE: orbit
     Parent portal. Concentric elliptical arcs with tick dashes, white pearls
     travelling the rings, one emerald core with a lime centre. */
  /* ----------------------------------------------------------- SCENE: orbit
     Parent portal. A banded jade planet with a travelling specular, bright
     elliptical paths with flowing dash-trains, and pearls that drag light
     trails along their orbits. */
  HeroScene.prototype.drawOrbit = function (time, still) {
    var ctx = this.ctx, w = this.w, h = this.h, c = this.rgb;
    var t = still ? 0.5 : time * 0.001 * this.speed;
    var gx = this.anchorX(0.73) + this.pointer.x * 24;
    var gy = h * 0.50 + this.pointer.y * 16;
    var radius = this.radius * (this.fill && w < 620 ? 0.80 : 1);

    this.softGlow(w, h, gx, gy, 0.0);
    this.core(w, h, gx, gy, 0.85);

    for (var r = 0; r < this.orbitRings.length; r++) {
      var ring = this.orbitRings[r];
      var phase = t * ring.speed;
      ctx.save();
      ctx.translate(gx, gy);
      ctx.rotate(ring.rot + Math.sin(t * 0.22 + r) * 0.055 + this.pointer.x * 0.060);
      ctx.scale(1, ring.ry / ring.rx);

      /* The paths are this scene's identity: bright hairlines, with a comet
         dash-train flowing along an inner lane. */
      ctx.strokeStyle = this.light
        ? rgba(c, 0.55 * ring.alpha + 0.24)
        : rgba(lift(c, 120), ring.alpha + 0.12);
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      ctx.arc(0, 0, radius * ring.rx, 0, Math.PI * 2);
      ctx.stroke();

      ctx.setLineDash([2, 10]);
      ctx.lineDashOffset = -phase * 30;
      ctx.strokeStyle = this.light ? rgba(c, 0.34) : rgba(lift(c, 90), 0.22);
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(0, 0, radius * ring.rx * 0.84, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }

    var pulse = still ? 1 : 1 + 0.022 * Math.sin(t * 1.2);
    var coreR = Math.max(10, radius * 0.26) * pulse;
    if (this.light) {
      this.halo(gx, gy, coreR * 2.8, 0.34, c);
      var disc = ctx.createRadialGradient(gx - coreR * 0.35, gy - coreR * 0.40, 0, gx, gy, coreR);
      disc.addColorStop(0, rgba([255, 255, 255], 1));
      disc.addColorStop(0.72, rgba([255, 255, 255], 0.98));
      disc.addColorStop(1, rgba(lift(c, 120), 0.98));
    } else {
      /* A banded jade sphere: luminous upper-left falling to deep emerald at
         the limb, with a specular that slowly orbits so the planet turns. */
      var sphere = ctx.createRadialGradient(gx - coreR * 0.38, gy - coreR * 0.42, coreR * 0.08, gx, gy, coreR);
      sphere.addColorStop(0, rgba([196, 246, 222], 0.98));
      sphere.addColorStop(0.42, rgba([74, 196, 152], 0.96));
      sphere.addColorStop(0.78, rgba([16, 120, 92], 0.96));
      sphere.addColorStop(1, rgba([5, 70, 52], 0.98));
      disc = sphere;
    }
    ctx.fillStyle = disc;
    ctx.beginPath();
    ctx.arc(gx, gy, coreR, 0, Math.PI * 2);
    ctx.fill();

    if (!this.light) {
      /* lit-side rim, faint equatorial bands, orbiting specular */
      ctx.save();
      ctx.beginPath();
      ctx.arc(gx, gy, coreR, 0, Math.PI * 2);
      ctx.clip();
      ctx.strokeStyle = rgba([210, 255, 235], 0.5);
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.arc(gx, gy, coreR - 1, Math.PI * 0.95, Math.PI * 1.65);
      ctx.stroke();
      ctx.strokeStyle = rgba([8, 90, 66], 0.35);
      ctx.lineWidth = Math.max(1, coreR * 0.16);
      ctx.beginPath();
      ctx.moveTo(gx - coreR, gy + coreR * 0.18);
      ctx.quadraticCurveTo(gx, gy + coreR * 0.34, gx + coreR, gy + coreR * 0.18);
      ctx.stroke();
      ctx.strokeStyle = rgba([220, 255, 240], 0.28);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(gx - coreR, gy - coreR * 0.30);
      ctx.quadraticCurveTo(gx, gy - coreR * 0.16, gx + coreR, gy - coreR * 0.30);
      ctx.stroke();
      var specA = still ? 0.8 : t * 0.9;
      var specX = gx + Math.cos(specA) * coreR * 0.52;
      var specY = gy + Math.sin(specA) * coreR * 0.38;
      var spec = ctx.createRadialGradient(specX, specY, 0, specX, specY, coreR * 0.30);
      spec.addColorStop(0, rgba([255, 255, 255], 0.85));
      spec.addColorStop(1, rgba([255, 255, 255], 0));
      ctx.fillStyle = spec;
      ctx.beginPath();
      ctx.arc(specX, specY, coreR * 0.30, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    ctx.strokeStyle = rgba(c, this.light ? 0.75 : 0.38);
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(gx, gy, coreR, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = rgba(this.accent, this.light ? 0.92 : 0.72);
    ctx.beginPath();
    ctx.arc(gx, gy, coreR * 0.30, 0, Math.PI * 2);
    ctx.fill();

    for (var p = 0; p < this.pearls.length; p++) {
      var pearl = this.pearls[p];
      var pr = this.orbitRings[pearl.ring];
      var angle = t * pr.speed * 2.0 + pearl.phase;
      var px = Math.cos(angle) * radius * pr.rx;
      var py = Math.sin(angle) * radius * pr.ry;
      var rot = pr.rot + Math.sin(t * 0.22 + pearl.ring) * 0.055 + this.pointer.x * 0.060;
      var rx = px * Math.cos(rot) - py * Math.sin(rot);
      var ry = px * Math.sin(rot) + py * Math.cos(rot);
      var front = Math.sin(angle) > 0;
      var size = pearl.size * (0.95 + pearl.depth * 0.75) * (front ? 1 : 0.70) * (this.light ? 1 : 0.9);
      var alpha = (front ? 0.95 : 0.45) * (this.light ? 0.95 : 0.9);

      if (!this.light && !still) {
        /* light trail along the orbit behind the pearl */
        var tailA = angle - 0.38 * (pr.speed >= 0 ? 1 : -1);
        var txx = Math.cos(tailA) * radius * pr.rx;
        var tyy = Math.sin(tailA) * radius * pr.ry;
        var trx = txx * Math.cos(rot) - tyy * Math.sin(rot);
        var tryy = txx * Math.sin(rot) + tyy * Math.cos(rot);
        var trail = ctx.createLinearGradient(gx + trx, gy + tryy, gx + rx, gy + ry);
        trail.addColorStop(0, rgba(this.accent, 0));
        trail.addColorStop(1, rgba(this.accent, alpha * 0.5));
        ctx.strokeStyle = trail;
        ctx.lineWidth = Math.max(1, size * 0.55);
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(gx + trx, gy + tryy);
        ctx.quadraticCurveTo(gx + (trx + rx) / 2, gy + (tryy + ry) / 2 - size * 0.4, gx + rx, gy + ry);
        ctx.stroke();
        ctx.lineCap = 'butt';
      }

      this.halo(gx + rx, gy + ry, size * 3.4, alpha * (this.light ? 0.42 : 0.30), this.accent);
      ctx.fillStyle = this.light
        ? rgba([255, 255, 255], alpha)
        : rgba(lift(this.accent, 120), alpha);
      ctx.beginPath();
      ctx.arc(gx + rx, gy + ry, size, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = rgba(c, this.light ? alpha * 0.45 : 0);
      ctx.lineWidth = 0.9;
      ctx.stroke();
    }

    this.drawDust(w, h, gx, gy, radius, t, still, 0.65);
  };

  /* ------------------------------------------------------------ SCENE: grid
     Admin portal. A slow radar sweep over a polar lattice: concentric ranges,
     faint spokes, and nodes that light up as the beam passes. It reads as
     oversight at a glance and stays calm because only the beam moves. */
  HeroScene.prototype.drawGrid = function (time, still) {
    var ctx = this.ctx, w = this.w, h = this.h, c = this.rgb;
    var t = still ? 0.5 : time * 0.001 * this.speed;
    var gx = this.anchorX(0.74) + this.pointer.x * 20;
    var gy = h * 0.52 + this.pointer.y * 14;
    /* Sized from the banner height so the dial never clips the top or bottom
       edge, and never eats the copy column on narrow screens. */
    var R = Math.min(h * 0.40, w * (this.fill && w < 620 ? 0.15 : 0.19));

    this.softGlow(w, h, gx, gy, -0.15);
    this.core(w, h, gx, gy, 0.42);

    var rings = 3;
    for (var r = 1; r <= rings; r++) {
      var rr = (R * r) / rings;
      /* The outer ring carries the dial; on dark it needs real presence. */
      var ringA = this.light ? 0.26 : (r === rings ? 0.36 : 0.24);
      ctx.strokeStyle = rgba(c, ringA);
      ctx.lineWidth = 1;
      ctx.setLineDash(r === rings ? [] : [3, 7]);
      ctx.beginPath();
      ctx.arc(gx, gy, rr, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    var spokes = 12;
    for (var sp = 0; sp < spokes; sp++) {
      var a = (sp / spokes) * Math.PI * 2;
      ctx.strokeStyle = rgba(c, this.light ? 0.12 : 0.17);
      ctx.lineWidth = 0.7;
      ctx.beginPath();
      ctx.moveTo(gx + Math.cos(a) * R * 0.10, gy + Math.sin(a) * R * 0.10);
      ctx.lineTo(gx + Math.cos(a) * R, gy + Math.sin(a) * R);
      ctx.stroke();
    }

    /* instrument tick ring: sixty ticks crawling around the dial */
    var tickRot = still ? 0 : t * 0.12;
    ctx.strokeStyle = this.light ? rgba(c, 0.22) : rgba(lift(c, 90), 0.30);
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (var tk = 0; tk < 60; tk++) {
      var ta = tickRot + (tk / 60) * Math.PI * 2;
      var r0 = R * (tk % 5 === 0 ? 1.05 : 1.08);
      ctx.moveTo(gx + Math.cos(ta) * r0, gy + Math.sin(ta) * r0);
      ctx.lineTo(gx + Math.cos(ta) * R * 1.12, gy + Math.sin(ta) * R * 1.12);
    }
    ctx.stroke();

    /* rotating beam */
    var sweep = (still ? 1.1 : t * 0.80) % (Math.PI * 2);
    ctx.save();
    ctx.translate(gx, gy);
    ctx.rotate(sweep);
    var trail = ctx.createLinearGradient(0, 0, R, 0);
    trail.addColorStop(0, rgba(this.accent, this.light ? 0.10 : 0.10));
    trail.addColorStop(1, rgba(this.accent, 0));
    ctx.fillStyle = trail;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, R, -0.95, -0.42);
    ctx.closePath();
    ctx.fill();

    var beam = ctx.createLinearGradient(0, 0, R, 0);
    beam.addColorStop(0, rgba(this.accent, this.light ? 0.34 : 0.38));
    beam.addColorStop(1, rgba(this.accent, 0));
    ctx.fillStyle = beam;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, R, -0.42, 0.02);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = rgba(this.accent, this.light ? 0.55 : 0.55);
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(R, 0);
    ctx.stroke();
    ctx.restore();

    /* nodes: brightness rises as the beam passes, then decays */
    for (var i = 0; i < this.gridNodes.length; i++) {
      var node = this.gridNodes[i];
      var ang = node.wave;
      var dist = 0.28 + (Math.abs(node.cx) * 0.5 + 0.5) * 0.68;
      var px = gx + Math.cos(ang) * R * dist;
      var py = gy + Math.sin(ang) * R * dist * 0.98;

      var delta = ((sweep - ang) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
      var live = delta < 1.5 ? Math.exp(-Math.pow(delta * 1.5, 2)) : 0;
      var base = this.light ? 0.24 : 0.32;
      var size = (1.1 + dist * 1.4) * (0.85 + live * 0.7);

      if (live > 0.5) this.halo(px, py, size * 7, live * 0.34, this.accent);
      this.dot(px, py, size, base + live * 0.60, live > 0.4 ? this.accent : (this.light ? c : lift(c, 60)));
    }

    /* centre pin */
    this.dot(gx, gy, 2.4, this.light ? 0.75 : 0.7, c);
    this.halo(gx, gy, R * 0.55, this.light ? 0.10 : 0.16, c);

    this.drawDust(w, h, gx, gy, this.radius, t, still, 0.46);
  };

  /* --------------------------------------------------------- SCENE: lectern
     Teacher portal. Three stacked books, a lime page-light above them, and
     motes drifting up like read pages. */
  /* --------------------------------------------------------- SCENE: lectern
     Teacher portal. Three emerald volumes in slow levitation, page-light
     breathing above them, and glints rising like turned pages. */
  HeroScene.prototype.drawLectern = function (time, still) {
    var ctx = this.ctx, w = this.w, h = this.h, t0 = this.tones(), c = this.rgb;
    var t = still ? 0.6 : time * 0.001 * this.speed;
    var gx = this.anchorX(0.73) + this.pointer.x * 24;
    var gy = h * 0.40 + this.pointer.y * 16;
    var radius = this.radius * (this.fill && w < 620 ? 0.78 : 1);

    this.softGlow(w, h, gx, gy, 0.02);
    this.core(w, h, gx, gy, 0.8);

    var appear = still ? 1 : Math.min(1, (time - this.startAt) / 850);
    var bookW = radius * 1.30;
    var bookH = Math.max(9, radius * 0.205);
    var baseY = gy + radius * 0.66;

    for (var b = 0; b < 3; b++) {
      var local = Math.max(0, Math.min(1, (appear - b * 0.16) / 0.68));
      if (local <= 0) continue;
      var ease = easeOutCubic(local);
      var bwid = bookW * (1 - b * 0.085);
      var y = baseY - b * bookH * 1.02;
      /* Levitation: each volume breathes on its own phase once placed. */
      var hover = still ? 0 : Math.sin(t * 0.85 + b * 1.2) * 2.6 * ease;
      var rot = (still ? 0 : Math.sin(t * 0.8 + b) * 0.006) + (b % 2 ? 0.014 : -0.011) + this.pointer.x * 0.012;
      var alpha = ease;

      ctx.save();
      ctx.translate(gx, y + (1 - ease) * 16 - hover);
      ctx.rotate(rot);

      /* Three faces so each book reads as a volume, not a stacked plate. */
      var ddx = bwid * 0.055;
      var ddy = bookH * 0.55;

      /* side face: the darkest plane, carrying the page edges */
      var side = ctx.createLinearGradient(bwid / 2, 0, bwid / 2 + 8, 0);
      if (this.light) {
        side.addColorStop(0, rgba(shade(c, 28), 0.94 * alpha));
        side.addColorStop(1, rgba(shade(c, 44), 0.92 * alpha));
      } else {
        side.addColorStop(0, rgba([10, 96, 70], 0.94 * alpha));
        side.addColorStop(1, rgba([5, 62, 46], 0.92 * alpha));
      }
      ctx.fillStyle = side;
      ctx.beginPath();
      ctx.moveTo(bwid / 2, -bookH);
      ctx.lineTo(bwid / 2, 0);
      ctx.lineTo(bwid / 2 + ddx, -ddy);
      ctx.lineTo(bwid / 2 + ddx, -bookH - ddy);
      ctx.closePath();
      ctx.fill();

      /* page edges: fine rules across the side block */
      ctx.strokeStyle = this.light
        ? rgba([255, 255, 255], 0.30 * alpha)
        : rgba([205, 255, 232], 0.22 * alpha);
      ctx.lineWidth = 0.7;
      for (var pl = 1; pl <= 3; pl++) {
        var f = pl / 3.6;
        ctx.beginPath();
        ctx.moveTo(bwid / 2 + 1, -bookH + bookH * f);
        ctx.lineTo(bwid / 2 + ddx - 1, -bookH - ddy + bookH * f);
        ctx.stroke();
      }

      /* front face: deep jade with a lit upper edge */
      var grad = ctx.createLinearGradient(0, -bookH, 0, 0);
      if (this.light) {
        grad.addColorStop(0, rgba(lift(c, 12), alpha));
        grad.addColorStop(0.72, rgba(c, 0.95 * alpha));
        grad.addColorStop(1, rgba(shade(c, 22), 0.94 * alpha));
      } else {
        grad.addColorStop(0, rgba([96, 214, 168], 0.96 * alpha));
        grad.addColorStop(0.35, rgba([30, 150, 114], 0.95 * alpha));
        grad.addColorStop(1, rgba([7, 80, 58], 0.96 * alpha));
      }
      ctx.fillStyle = grad;
      roundRect(ctx, -bwid / 2, -bookH, bwid, bookH, 2.5);
      ctx.fill();
      ctx.strokeStyle = this.light
        ? rgba(c, 0.34 * alpha)
        : rgba([150, 240, 200], 0.30 * alpha);
      ctx.lineWidth = 0.9;
      ctx.stroke();

      /* top face: luminous mint melting into emerald — never flat white */
      var topf = ctx.createLinearGradient(-bwid / 2, 0, bwid / 2 + ddx, 0);
      if (this.light) {
        topf.addColorStop(0, rgba([255, 255, 255], 0.95 * alpha));
        topf.addColorStop(1, rgba(lift(c, 110), 0.92 * alpha));
      } else {
        topf.addColorStop(0, rgba([206, 248, 228], 0.96 * alpha));
        topf.addColorStop(0.6, rgba([120, 220, 180], 0.94 * alpha));
        topf.addColorStop(1, rgba([40, 140, 108], 0.94 * alpha));
      }
      ctx.fillStyle = topf;
      ctx.beginPath();
      ctx.moveTo(-bwid / 2, -bookH);
      ctx.lineTo(bwid / 2, -bookH);
      ctx.lineTo(bwid / 2 + ddx, -bookH - ddy);
      ctx.lineTo(-bwid / 2 + ddx, -bookH - ddy);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = rgba(c, this.light ? 0.26 * alpha : 0.22 * alpha);
      ctx.lineWidth = 0.8;
      ctx.stroke();

      /* spine light */
      ctx.fillStyle = this.light
        ? rgba(this.accent, 0.95 * alpha)
        : rgba(this.accent, 0.75 * alpha);
      roundRect(ctx, -bwid / 2 + 5, -bookH + 2.5, 3, bookH - 5, 1.2);
      ctx.fill();
      ctx.restore();
    }

    /* page-light breathes above the stack */
    var breathe = still ? 0.5 : 0.5 + 0.5 * Math.sin(t * 1.4);
    this.halo(gx, baseY - bookH * 3.15, radius * 0.55,
      this.light ? 0.16 : 0.24 + 0.12 * breathe, this.accent);

    /* glints: short bright ticks rising from the volumes like turned pages */
    for (var g = 0; g < 7; g++) {
      var gp = still ? (g / 7) : (((g / 7) + t * 0.05 * (0.7 + (g % 3) * 0.25)) % 1);
      var glx = gx + Math.sin(g * 2.3) * radius * 0.75 + (still ? 0 : Math.sin(t * 0.7 + g) * 6);
      var gly = baseY - bookH * 3.2 - gp * radius * 1.1;
      var ga = Math.sin(gp * Math.PI) * (this.light ? 0.35 : 0.55);
      if (ga <= 0.02) continue;
      ctx.strokeStyle = rgba(g % 2 ? [225, 255, 240] : this.accent, ga);
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(glx, gly);
      ctx.lineTo(glx + 3, gly - 7 - (g % 3) * 2);
      ctx.stroke();
    }

    for (var i = 0; i < this.motes.length; i++) {
      var m = this.motes[i];
      var my = still ? m.y : (m.y - (t * 0.10 * m.rise * 100) % 1 + 1) % 1;
      var mx = m.x + Math.sin(t * 0.5 + m.tw) * 0.018;
      var twinkle = 0.40 + Math.sin(t * 1.4 + m.tw) * 0.60;
      var tone = m.r > 2 ? this.accent : t0.dust;
      var alpha2 = twinkle * (this.light ? 0.34 : 0.60);
      var mxp = w * (0.40 + mx * 0.36), myp = h * (0.06 + my * 0.74);
      if (m.r > 2 && !this.fill) this.halo(mxp, myp, m.r * 5, alpha2 * 0.4, tone);
      this.dot(mxp, myp, this.fill ? Math.min(m.r, 1.5) : m.r, alpha2, tone);
    }

    this.drawDust(w, h, gx, gy, radius, t, still, 0.65);
  };

  /* --------------------------------------------------- SCENE: constellation
     Guest / login showcase. Orbiting node web with a soft horizon and a few
     accent nodes catching light. */
  HeroScene.prototype.drawConstellation = function (time, still) {
    var ctx = this.ctx, w = this.w, h = this.h, c = this.rgb;
    var t = still ? 0.6 : time * 0.001 * this.speed;
    var gx = w * 0.58 + this.pointer.x * 28;
    var gy = h * 0.50 + this.pointer.y * 18;
    var radius = this.radius;

    this.softGlow(w, h, gx, gy, 0.02);
    this.core(w, h, gx, gy, 0.30);

    /* Horizon as an elliptical bloom: a straight band left visible rectangle
       edges where it met the panel, which read as a rendering fault. */
    var horizonY = gy + radius * 0.74;
    ctx.save();
    ctx.translate(gx, horizonY);
    ctx.scale(1, 0.055);
    var hz = ctx.createRadialGradient(0, 0, 0, 0, 0, radius * 1.25);
    hz.addColorStop(0, rgba(lift(c, 150), this.light ? 0.42 : 0.42));
    hz.addColorStop(0.45, rgba(lift(c, 120), this.light ? 0.16 : 0.20));
    hz.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = hz;
    ctx.beginPath();
    ctx.arc(0, 0, radius * 1.25, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    /* A meteor crosses every few seconds: the login sky never fully rests. */
    if (!still) {
      var cycle = 7, mph = (t % cycle) / cycle;
      if (mph < 0.22) {
        var mp = mph / 0.22;
        var mx0 = w * 0.78, my0 = h * 0.10;
        var mdx = -w * 0.34, mdy = h * 0.30;
        var hxp = mx0 + mdx * mp, hyp = my0 + mdy * mp;
        var met = ctx.createLinearGradient(hxp, hyp, hxp - mdx * 0.16, hyp - mdy * 0.16);
        var ma = (1 - mp) * 0.8;
        met.addColorStop(0, rgba([255, 255, 255], ma));
        met.addColorStop(0.25, rgba(lift(c, 140), ma * 0.7));
        met.addColorStop(1, rgba(lift(c, 140), 0));
        ctx.strokeStyle = met;
        ctx.lineWidth = 1.6;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(hxp, hyp);
        ctx.lineTo(hxp - mdx * 0.16, hyp - mdy * 0.16);
        ctx.stroke();
        ctx.lineCap = 'butt';
        this.halo(hxp, hyp, 7, ma * 0.5, lift(c, 140));
      }
    }

    for (var r = 0; r < 2; r++) {
      ctx.save();
      ctx.translate(gx, gy);
      ctx.rotate(t * (r ? -0.10 : 0.14) + this.pointer.x * 0.04);
      ctx.scale(1, 0.24 + r * 0.10);
      ctx.strokeStyle = rgba(lift(c, 110), (this.light ? 0.26 : 0.34) - r * 0.09);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(0, 0, radius * (0.80 + r * 0.24), 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    var tilt = 0.30 + this.pointer.y * 0.12;
    var spin = t * 0.22 + this.pointer.x * 0.18;
    var projected = [];
    var i, p;
    for (i = 0; i < this.points.length; i++) {
      projected.push(this.project(this.points[i], spin, tilt, gx, gy, radius));
    }

    for (i = 0; i < projected.length; i++) {
      for (var k = 1; k <= 2; k++) {
        var q = projected[(i + k * 3) % projected.length];
        var near = 1 - Math.min(1, Math.hypot(projected[i].x - q.x, projected[i].y - q.y) / (radius * 0.50));
        if (near <= 0) continue;
        ctx.strokeStyle = rgba(lift(c, 80), near * (this.light ? 0.16 : 0.13));
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.moveTo(projected[i].x, projected[i].y);
        ctx.lineTo(q.x, q.y);
        ctx.stroke();
      }
    }

    for (i = 0; i < projected.length; i++) {
      p = projected[i];
      var twinkle = 0.60 + Math.sin((still ? 1 : t * 1.9) + p.tw) * 0.40;
      var alpha = (0.18 + p.z * 0.85) * twinkle;
      if (p.z > 0.84) {
        this.halo(p.x, p.y, p.r * 5.0, alpha * 0.34, this.accent);
        this.dot(p.x, p.y, p.r * 0.8, alpha, lift(this.accent, 90));
      } else {
        this.dot(p.x, p.y, Math.max(0.6, p.r * 0.62), alpha * (this.light ? 0.9 : 1), lift(c, 55));
      }
    }
  };

  HeroScene.prototype.drawDust = function (w, h, cx, cy, radius, t, still, strength) {
    var ctx = this.ctx;
    var dust = this.tones().dust;
    var tilt = 0.34 + this.pointer.y * 0.10;
    var spin = t * 0.55 + this.pointer.x * 0.14;
    for (var i = 0; i < this.points.length; i++) {
      var p = this.project(this.points[i], spin, tilt, cx, cy, radius * 0.9);
      var twinkle = 0.62 + Math.sin((still ? 1 : t * 2.2) + p.tw) * 0.38;
      var alpha = (0.10 + p.z * 0.34) * twinkle * strength * (this.light ? 1 : 1.15);
      this.dot(p.x, p.y, Math.max(0.6, p.r * 0.55), alpha, dust);
    }
  };

  HeroScene.prototype.draw = function (time, still) {
    var ctx = this.ctx;
    if (!this.startAt && time) this.startAt = time;
    if (!this.startAt) this.startAt = performance.now();
    ctx.clearRect(0, 0, this.w, this.h);
    switch (this.scene) {
      case 'trophy': this.drawTrophy(time, still); break;
      case 'orbit': this.drawOrbit(time, still); break;
      case 'grid': this.drawGrid(time, still); break;
      case 'lectern': this.drawLectern(time, still); break;
      default: this.drawConstellation(time, still);
    }
  };

  /* ========================================================== MOUNTING */
  var scenes = [];

  /* Any of these hosts may contain a <canvas class="hero-canvas">. The banner is
     last so a richer hero inside it always wins via closest(). */
  var HOST_SEL = '.auth-showcase,.student-home-hero,.asc-hero,.ui-hero,[data-hero],.overview-banner';

  /* Only the student home hero is a light surface; every other banner is a
     dark emerald gradient, so only the student scene paints light-mode ink. */
  var ROLE_OPTS = {
    student: { scene: 'trophy', speed: 1.15, light: true },
    parent: { scene: 'orbit', speed: 1.05, light: false },
    admin: { scene: 'grid', speed: 1.00, light: false, count: 30 },
    teacher: { scene: 'lectern', speed: 1.10, light: false },
    guest: { scene: 'constellation', speed: 1.05, light: false, count: 62 }
  };

  /* body carries role-student for student, parent AND teacher pages, so the
     role-parent / role-teacher markers decide between them. */
  function roleName() {
    var body = document.body;
    if (!body) return '';
    var list = body.classList;
    if (list.contains('role-admin')) return 'admin';
    if (list.contains('role-parent')) return 'parent';
    if (list.contains('role-teacher')) return 'teacher';
    if (list.contains('role-student')) {
      /* base.html renders role-student for students, parents and teachers, so
         the URL is the only reliable discriminator for the teaching portal. */
      return /^\/teacher(\/|$)/.test(location.pathname) ? 'teacher' : 'student';
    }
    return '';
  }

  function primaryHero() {
    /* A purpose-built hero wins over the generic dashboard banner even when the
       banner comes first in the DOM. */
    var groups = ['.student-home-hero,.auth-showcase,.asc-hero,.ui-hero,[data-hero]', '.overview-banner'];
    for (var g = 0; g < groups.length; g++) {
      var list = document.querySelectorAll(groups[g]);
      for (var i = 0; i < list.length; i++) {
        if (list[i].querySelector('canvas.hero-canvas')) return list[i];
      }
    }
    return null;
  }

  function mount(id, options) {
    var canvas = typeof id === 'string' ? document.getElementById(id) : id;
    if (!canvas || canvas.tagName !== 'CANVAS' || canvas.__heroScene) {
      return canvas && canvas.__heroScene;
    }
    if (!canvas.getContext) return null;
    var host = canvas.closest(HOST_SEL) || canvas.parentElement;
    if (!host) return null;

    var opts = {};
    for (var key in options) if (options.hasOwnProperty(key)) opts[key] = options[key];
    if (host.dataset.heroScene) opts.scene = host.dataset.heroScene;
    if (canvas.dataset.heroScene) opts.scene = canvas.dataset.heroScene;
    if (!opts.rgb) opts.rgb = palette();

    var scene;
    try {
      scene = new HeroScene(canvas, host, opts);
    } catch (err) {
      /* Canvas is decorative: if it cannot run, hide it and leave the hero's
         CSS fallback untouched rather than leaving a black rectangle. */
      canvas.style.display = 'none';
      return null;
    }
    canvas.__heroScene = scene;
    scenes.push(scene);
    scene.start();

    if ('IntersectionObserver' in window) {
      scene.io = new IntersectionObserver(function (entries) {
        for (var i = 0; i < entries.length; i++) {
          scene.visible = entries[i].isIntersecting;
          if (scene.visible) scene.start();
          else scene.stop();
        }
      }, { rootMargin: '120px' });
      scene.io.observe(host);
    }

    if (window.ASCEND_MOTION) {
      try {
        window.ASCEND_MOTION.onChange(function (on) {
          if (on) scene.start();
          else { scene.stop(); scene.draw(performance.now(), true); }
        });
      } catch (err) { /* keep the scene running */ }
    }

    var resizeTimer = 0;
    var onResize = function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        scene.resize();
        scene.draw(performance.now(), !motionOn() || !scene.visible);
      }, 160);
    };
    window.addEventListener('resize', onResize, { passive: true });
    window.addEventListener('orientationchange', onResize, { passive: true });
    return scene;
  }

  function boot() {
    var role = roleName();
    var hero = primaryHero();
    if (!hero) return;
    var host = hero.dataset.heroScene;
    var roleOpts = ROLE_OPTS[role] || ROLE_OPTS.guest || {};

    /* The dashboard banner is wide and short, and its text already occupies the
       left two thirds: scale from the height and pull the composition left. */
    var banner = hero.classList.contains('overview-banner');
    var opts = {
      scene: host || roleOpts.scene || 'constellation',
      /* The host decides the palette: .student-home-hero is the only light
         surface (mint gradient); .overview-banner and .auth-showcase are dark
         emerald and need dark-mode tones. A blanket flag either way paints
         one portal wrong — that is exactly the washed-out-banner bug. */
      light: hero.classList.contains('student-home-hero'),
      fill: banner,
      soft: !banner,
      speed: roleOpts.speed || 1,
      count: roleOpts.count
    };

    mount('hero-canvas', opts);
    if (window.ASCEND_HERO) window.ASCEND_HERO.scenes = scenes;
  }

  /* One passive listener and one easing loop for the whole document: scenes
     read the shared pointer target, so adding hero canvases costs no extra
     listeners. */
  var target = { x: 0, y: 0 };
  document.addEventListener('pointermove', function (e) {
    if (e.pointerType === 'touch') return;
    target.x = (e.clientX / window.innerWidth - 0.5) * 2;
    target.y = (e.clientY / window.innerHeight - 0.5) * 2;
    for (var i = 0; i < scenes.length; i++) {
      scenes[i].pointer.tx = target.x;
      scenes[i].pointer.ty = target.y;
    }
  }, { passive: true });

  document.addEventListener('visibilitychange', function () {
    for (var i = 0; i < scenes.length; i++) {
      if (document.hidden) scenes[i].stop();
      else if (scenes[i].visible) scenes[i].start();
    }
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  /* Public API. boot() only fills api.scenes, so the surface stays intact no
     matter when the DOM becomes ready. */
  var api = window.ASCEND_HERO || {};
  api.webgl = false;
  api.canvas = true;
  api.scenes = scenes;
  api.mount = mount;
  api.boot = boot;
  api.HeroScene = HeroScene;
  api.palette = palette;
  window.ASCEND_HERO = api;
})();
