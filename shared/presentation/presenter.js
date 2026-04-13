/* global Reveal, localStorage, cancelAnimationFrame, getComputedStyle */

// ---------------------------------------------------------------------------
// presenter.js -- Shared presentation engine for all module slide decks.
// Provides theme/lang toggling, particle background, animated counters,
// slide element animations, SVG restart, expandable cards, and Reveal.js
// initialization with configurable defaults via window.PRES_CONFIG.
// ---------------------------------------------------------------------------

let particleAnimId = null;

// ========================== THEME MANAGEMENT ==============================

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const vp = document.querySelector('.reveal-viewport');
  if (vp) {
    const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
    vp.style.background = bg;
  }
  localStorage.setItem('pres-theme', theme);
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.innerHTML = theme === 'dark' ? '&#9790;' : '&#9788;';
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  initParticles();
}

function toggleLang() {
  const html = document.documentElement;
  const current = html.getAttribute('data-lang');
  const next = current === 'en' ? 'es' : 'en';
  html.setAttribute('data-lang', next);
  localStorage.setItem('pres-lang', next);
  document.getElementById('lang-toggle').textContent = next.toUpperCase();
}

// ======================== PARTICLE BACKGROUND =============================

function initParticles() {
  // Respect prefers-reduced-motion -- skip particle animation entirely.
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (motionQuery.matches) {
    if (particleAnimId) {
      cancelAnimationFrame(particleAnimId);
      particleAnimId = null;
    }
    const canvas = document.getElementById('particle-canvas');
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    return;
  }

  if (particleAnimId) cancelAnimationFrame(particleAnimId);

  const canvas = document.getElementById('particle-canvas');
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const particleColor = isDark ? 'rgba(88,166,255,0.3)' : 'rgba(9,105,218,0.18)';
  const lineColor = isDark ? 'rgba(88,166,255,0.08)' : 'rgba(9,105,218,0.06)';
  const particles = [];
  const count = 50;
  const maxDist = 120;

  for (let i = 0; i < count; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      r: Math.random() * 2 + 1,
    });
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < count; i++) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = particleColor;
      ctx.fill();
      for (let j = i + 1; j < count; j++) {
        const q = particles[j];
        const dx = p.x - q.x;
        const dy = p.y - q.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < maxDist) {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(q.x, q.y);
          ctx.strokeStyle = lineColor;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
    particleAnimId = requestAnimationFrame(draw);
  }

  draw();
}

// Resize particle canvas when window size changes.
window.addEventListener('resize', () => {
  const canvas = document.getElementById('particle-canvas');
  if (canvas) {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
});

// ========================= ANIMATED COUNTERS ==============================

function animateCounter(el, target, suffix, prefix, decimals, duration) {
  let current = 0;
  const step = target / (duration / 16);

  function tick() {
    current += step;
    if (current >= target) {
      el.textContent =
        (prefix || '') + (decimals > 0 ? target.toFixed(decimals) : target) + (suffix || '');
      return;
    }
    el.textContent =
      (prefix || '') +
      (decimals > 0 ? current.toFixed(decimals) : Math.floor(current)) +
      (suffix || '');
    requestAnimationFrame(tick);
  }

  tick();
}

function triggerCounters(slide) {
  const counters = slide.querySelectorAll('[data-counter]');
  counters.forEach((el) => {
    const target = parseFloat(el.getAttribute('data-counter'));
    const suffix = el.getAttribute('data-suffix') || '';
    const prefix = el.getAttribute('data-prefix') || '';
    const decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);
    animateCounter(el, target, suffix, prefix, decimals, 800);
  });
}

// =================== FLOAT-IN / SLIDE-IN ANIMATIONS ======================

function animateSlideElements(slide) {
  const floats = slide.querySelectorAll('.float-in');
  floats.forEach((el, i) => {
    el.classList.remove('visible');
    setTimeout(() => {
      el.classList.add('visible');
    }, i * 100);
  });

  const slideIns = slide.querySelectorAll('.slide-in');
  slideIns.forEach((el, i) => {
    el.classList.remove('visible');
    setTimeout(() => {
      el.classList.add('visible');
    }, i * 80);
  });
}

// ===================== SVG ANIMATION RESTART ==============================

function restartSVGAnimations(slide) {
  const svgs = slide.querySelectorAll('svg');
  svgs.forEach((svg) => {
    const anims = svg.querySelectorAll('animate, animateMotion, animateTransform');
    anims.forEach((a) => {
      if (a.beginElement) a.beginElement();
    });
  });
}

// ========================= REVEAL.JS INIT =================================

const DEFAULTS = {
  width: 960,
  height: 600,
  margin: 0.04,
  center: false,
  hash: true,
  transition: 'slide',
  transitionSpeed: 'default',
  controls: true,
  progress: true,
  slideNumber: true,
  overview: true,
  touch: true,
};

const config = Object.assign({}, DEFAULTS, window.PRES_CONFIG || {});

Reveal.initialize(config).then(() => {
  applyTheme(localStorage.getItem('pres-theme') || 'dark');
  const savedLang = localStorage.getItem('pres-lang') || 'en';
  const langBtn = document.getElementById('lang-toggle');
  if (langBtn) langBtn.textContent = savedLang.toUpperCase();
  initParticles();
  const firstSlide = Reveal.getCurrentSlide();
  animateSlideElements(firstSlide);
  triggerCounters(firstSlide);
  restartSVGAnimations(firstSlide);
});

Reveal.on('slidechanged', (event) => {
  animateSlideElements(event.currentSlide);
  triggerCounters(event.currentSlide);
  restartSVGAnimations(event.currentSlide);
});

// ======================== EXPANDABLE CARDS ================================

document.addEventListener('click', (e) => {
  const card = e.target.closest('.expandable');
  if (card) {
    e.stopPropagation();
    card.classList.toggle('expanded');
  }
});

// Keyboard support for expandable cards (Enter and Space).
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const card = e.target.closest('.expandable');
  if (card) {
    e.preventDefault();
    card.classList.toggle('expanded');
  }
});

// Expose helpers so module-specific slides.js files can call them.
window.applyTheme = applyTheme;
window.toggleTheme = toggleTheme;
window.toggleLang = toggleLang;
window.initParticles = initParticles;
