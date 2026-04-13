/* global document, setTimeout */

// Module-specific JavaScript for the Proxies presentation.

function highlightTier(btn, tierClass) {
  var section = btn.closest('section');
  if (!section) return;
  var svg = section.querySelector('svg');
  if (!svg) return;
  var tiers = svg.querySelectorAll('.arch-tier');
  tiers.forEach(function (t) {
    t.setAttribute('opacity', t.classList.contains(tierClass) ? '1' : '0.25');
  });
  var descs = section.querySelectorAll('.tier-desc');
  descs.forEach(function (d) {
    d.style.display = d.dataset.tier === tierClass ? 'block' : 'none';
  });
  setTimeout(function () {
    tiers.forEach(function (t) {
      t.setAttribute('opacity', '1');
    });
  }, 3000);
}

window.PRES_CONFIG = {};
