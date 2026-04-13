/* global document, setTimeout */

const vscaleSpecs = [
  { name: 'db.t3.micro', vcpu: 2, ram: '1 GB', storage: '20 GB', scale: 0.7 },
  { name: 'db.t3.medium', vcpu: 2, ram: '4 GB', storage: '100 GB', scale: 0.85 },
  { name: 'db.r6g.large', vcpu: 2, ram: '16 GB', storage: '500 GB', scale: 1.0 },
  { name: 'db.r6g.4xlarge', vcpu: 16, ram: '128 GB', storage: '2 TB', scale: 1.15 },
  { name: 'db.r6g.16xlarge', vcpu: 64, ram: '512 GB', storage: '64 TB', scale: 1.3 },
];

function updateVScale(val) {
  if (val < 1 || val > vscaleSpecs.length) return;
  const spec = vscaleSpecs[val - 1];
  const svg = document.getElementById('vscale-svg');
  if (svg) {
    const s = spec.scale;
    svg.setAttribute('width', Math.round(240 * s));
    svg.setAttribute('height', Math.round(200 * s));
    svg.setAttribute('viewBox', '0 0 240 200');
  }
  const specEl = document.getElementById('vscale-spec');
  if (specEl) {
    specEl.innerHTML =
      '<b>' +
      spec.name +
      '</b> &mdash; ' +
      spec.vcpu +
      ' vCPU, ' +
      spec.ram +
      ' RAM, ' +
      spec.storage +
      ' storage';
  }
}

function highlightTier(btn, tierClass) {
  const section = btn.closest('section');
  if (!section) return;
  const svg = section.querySelector('svg');
  if (!svg) return;
  const tiers = svg.querySelectorAll('.arch-tier');
  tiers.forEach((t) => {
    t.setAttribute('opacity', t.classList.contains(tierClass) ? '1' : '0.25');
  });
  const descs = section.querySelectorAll('.tier-desc');
  descs.forEach((d) => {
    d.style.display = d.dataset.tier === tierClass ? 'block' : 'none';
  });
  setTimeout(() => {
    tiers.forEach((t) => {
      t.setAttribute('opacity', '1');
    });
  }, 3000);
}

window.PRES_CONFIG = {};
