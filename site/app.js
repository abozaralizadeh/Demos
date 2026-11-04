// Demos project page. Plain JS, no build step.
(function () {
  "use strict";
  var root = document.documentElement;
  var still = matchMedia("(prefers-reduced-motion: reduce)");
  var clamp = function (v, a, b) { return Math.min(b, Math.max(a, v)); };

  // ---------- theme: "Other side" flips the page, like the app does ----------
  var themeBtn = document.querySelector(".theme");
  function setTheme(t, save) {
    root.dataset.theme = t;
    themeBtn.setAttribute("aria-pressed", String(t === "light"));
    document.querySelector('meta[name="theme-color"]').content = t === "light" ? "#f5f5f3" : "#000000";
    if (save) { try { localStorage.setItem("demos-theme", t); } catch (e) {} }
  }
  setTheme(root.dataset.theme || "dark", false);
  themeBtn.addEventListener("click", function () {
    setTheme(root.dataset.theme === "light" ? "dark" : "light", true);
  });

  // ---------- nav border once you scroll, hero rings close as you scroll ----------
  var nav = document.querySelector(".nav");
  var hero = document.querySelector(".hero");
  var flip = document.querySelector(".flip");
  function onScroll() {
    nav.classList.toggle("scrolled", scrollY > 8);
    var fr = flip.getBoundingClientRect();
    nav.classList.toggle("inv", flip.classList.contains("on") && fr.top < nav.offsetHeight && fr.bottom > nav.offsetHeight / 2);
    if (!still.matches) {
      var p = clamp(scrollY / (hero.offsetHeight * 0.9), 0, 1);
      hero.style.setProperty("--p", p.toFixed(3));
    }
  }
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // ---------- reveals ----------
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });

  // ---------- the flip section turns to the other side as it comes in ----------
  new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { flip.classList.toggle("on", e.isIntersecting); onScroll(); });
  }, { threshold: 0.35 }).observe(flip);

  // ---------- demo video: load after the page, captions follow the screens ----------
  var CAPS = [
    "Open it, and the World asks what's on your mind.",
    "You say it. The World asks why.",
    "It tells you where you stand, with real counts.",
    "The screen turns white: the other side, at its strongest.",
    "Facts come as data, in a square block.",
    "Then an idea both sides might take.",
    "Done. What you said counts now.",
    "The Map. Each topic is two circles.",
    "An idea that wins across groups becomes an Agreement."
  ];
  var STEP = 2.9; // seconds per screen in demo.mp4
  var video = document.querySelector(".demo-video");
  var capN = document.querySelector(".demo-n");
  var capT = document.querySelector(".demo-t");
  var shown = 0;
  function loadVideo() {
    video.src = video.dataset.src;
    if (still.matches) { video.controls = true; return; }
    video.play().catch(function () { video.controls = true; });
  }
  if (document.readyState === "complete") setTimeout(loadVideo, 300);
  else addEventListener("load", function () { setTimeout(loadVideo, 300); });
  video.addEventListener("timeupdate", function () {
    var i = Math.floor((video.currentTime + 0.25) / STEP) % CAPS.length;
    if (i === shown) return;
    shown = i;
    capT.style.opacity = 0;
    setTimeout(function () {
      capN.textContent = String(i + 1).padStart(2, "0");
      capT.textContent = CAPS[i];
      capT.style.opacity = 1;
    }, 180);
  });

  // ---------- copy buttons ----------
  document.querySelectorAll(".copy").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.parentElement.querySelector("code").innerText;
      var done = function () {
        btn.textContent = "Copied";
        btn.classList.add("done");
        setTimeout(function () { btn.textContent = "Copy"; btn.classList.remove("done"); }, 1600);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, done);
      else {
        var t = document.createElement("textarea");
        t.value = text; document.body.appendChild(t); t.select();
        try { document.execCommand("copy"); } catch (e) {}
        t.remove(); done();
      }
    });
  });

  // ---------- the crowd: two sides of dots that close the gap ----------
  var sec = document.querySelector(".crowd");
  var cv = document.querySelector(".crowd-canvas");
  var ctx = cv.getContext("2d");
  var rPeople = document.querySelector(".r-people");
  var rCommon = document.querySelector(".r-common");
  var rHeard = document.querySelector(".r-heard");
  var W = 0, H = 0, R = 0, dots = [], ripples = [], visible = false, sep = 0.2, raf = 0;

  function css(name) { return getComputedStyle(root).getPropertyValue(name).trim(); }

  function build() {
    var dpr = Math.min(devicePixelRatio || 1, 2);
    W = sec.clientWidth; H = sec.clientHeight;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    R = Math.min(H * 0.34, W * (W < 600 ? 0.215 : 0.24));
    var n = Math.round(clamp(W * 0.55, 220, 640));
    dots = [];
    for (var i = 0; i < n; i++) {
      var a = Math.random() * Math.PI * 2, d = Math.sqrt(Math.random());
      dots.push({
        side: i % 2, ux: Math.cos(a) * d, uy: Math.sin(a) * d,
        ph: Math.random() * 6.283, sp: 0.4 + Math.random() * 0.8,
        heard: 0, x: 0, y: 0
      });
    }
    rPeople.textContent = n.toLocaleString("en");
    draw(performance.now());
  }

  function targetSep() {
    if (still.matches) return 0.62;
    var r = sec.getBoundingClientRect();
    // 0 when the crowd's middle enters at the bottom, 1 once it's 40% from the top
    var p = clamp((innerHeight - (r.top + r.height / 2)) / (innerHeight * 0.6), 0, 1);
    return 0.08 + p * 0.82;
  }

  var last = 0;
  function draw(now) {
    var t = now / 1000;
    // frames at 60 fps, so it moves the same on a 120 Hz screen or a throttled tab
    var f = last ? clamp((now - last) / 16.7, 0, 6) : 1;
    last = now;
    sep = still.matches ? targetSep() : sep + (targetSep() - sep) * (1 - Math.pow(0.92, f));
    // centre distance: apart at sep 0, overlapping at sep 1
    var D = 2 * R * (1.12 - 0.78 * sep);
    var cy = H * 0.56, cx = W / 2;
    var cA = cx - D / 2, cB = cx + D / 2;
    var ink = css("--dot"), agree = css("--agree-fill"), full = css("--ink");
    ctx.clearRect(0, 0, W, H);
    var common = 0, size = W < 600 ? 1.6 : 2;
    for (var i = 0; i < dots.length; i++) {
      var p = dots[i];
      var c = p.side ? cB : cA;
      var wob = still.matches ? 0 : 3;
      var x = c + p.ux * R + Math.sin(t * p.sp + p.ph) * wob;
      var y = cy + p.uy * R + Math.cos(t * p.sp * 0.8 + p.ph) * wob;
      // voice ripples push dots out as they pass
      for (var k = 0; k < ripples.length; k++) {
        var rp = ripples[k], dx = x - rp.x, dy = y - rp.y, dist = Math.hypot(dx, dy) || 1;
        var band = Math.abs(dist - rp.r);
        if (band < 34) {
          var push = (1 - band / 34) * 10 * rp.life;
          x += dx / dist * push; y += dy / dist * push;
          if (!p.heard || p.heard < rp.id) { p.heard = rp.id; rp.count++; }
          p.glow = 1;
        }
      }
      var other = p.side ? cA : cB;
      var inOverlap = Math.hypot(x - other, y - cy) < R;
      if (inOverlap) common++;
      ctx.fillStyle = inOverlap ? agree : (p.glow > 0.05 ? full : ink);
      if (p.glow) p.glow *= Math.pow(0.94, f);
      ctx.beginPath();
      ctx.arc(x, y, inOverlap ? size + 0.5 : size, 0, 6.283);
      ctx.fill();
    }
    rCommon.textContent = Math.round(common / dots.length * 100) + "%";

    for (var j = ripples.length - 1; j >= 0; j--) {
      var q = ripples[j];
      q.r += 9 * f; q.life = clamp(1 - q.r / q.max, 0, 1);
      if (q.r >= q.max) { rHeard.textContent = q.count.toLocaleString("en") + " people"; ripples.splice(j, 1); }
    }
  }

  // one loop at most, only while the crowd is on screen
  function loop(now) {
    raf = 0;
    draw(now);
    if (visible && !still.matches) raf = requestAnimationFrame(loop);
    else last = 0;
  }
  function start() { if (!raf && visible && !still.matches) raf = requestAnimationFrame(loop); }

  var rid = 0;
  function speak(x, y) {
    rid++;
    var max = Math.hypot(Math.max(x, W - x), Math.max(y, H - y));
    if (still.matches) {
      // no ripple without motion, just the answer
      rHeard.textContent = dots.length.toLocaleString("en") + " people";
      return;
    }
    rHeard.textContent = "Listening";
    ripples.push({ x: x, y: y, r: 0, max: max, life: 1, id: rid, count: 0 });
    start();
  }
  cv.addEventListener("pointerdown", function (e) {
    var r = cv.getBoundingClientRect();
    speak(e.clientX - r.left, e.clientY - r.top);
  });
  document.querySelector(".speak").addEventListener("click", function () { speak(W / 2, H * 0.56); });

  new IntersectionObserver(function (entries) {
    visible = entries[0].isIntersecting;
    start();
  }).observe(sec);
  addEventListener("scroll", function () { if (still.matches && visible) draw(performance.now()); }, { passive: true });
  var rt;
  addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(build, 150); });
  themeBtn.addEventListener("click", function () { if (!raf) draw(performance.now()); });
  build();
})();
