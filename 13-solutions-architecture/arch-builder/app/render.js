/* global module, globalThis */
/* Juego "completa el diagrama": puzzle JSON -> SVG en línea. UMD: window.ArchRender en el navegador, module.exports
 * en node (pruebas). Origen: studykit/app/game-render.js, con estilos de grupo para AWS, Azure, Google Cloud y OCI.
 *
 * Rejilla: celda de 120 x 112 unidades, viewBox = cols*120 x rows*112 (GEOM igual que en tools/build.py).
 * Orden: lienzo, grupos (de afuera hacia adentro, las zonas encima), flechas, nodos y slots, insignias.
 * Los iconos son <use href="#gi-<id>"> de los símbolos oficiales (sprite de game-data.js): nunca se recolorean ni se
 * filtran; el estado se dibuja alrededor (contornos, insignias, opacidad de la ficha).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ArchRender = api;
})(typeof globalThis !== 'undefined' ? globalThis : window, function () {
  'use strict';

  const GEOM = {
    CW: 120,
    CH: 112,
    ICON: 52,
    ICON_TOP: 12,
    SLOT: 60,
    SLOT_TOP: 8,
    BOX: [-54, 0, 54, 104],
    LABEL_Y: 82,
    LINE: 16,
  };
  const INK = '#232F3E';
  // Convenciones de grupo de cada proveedor (AWS: Architecture Group Icons; Azure: Architecture Center; Google Cloud:
  // guía de diagramas; OCI: librería draw.io "Physical - Grouping"). Las zonas no llevan relleno: cruzan las subredes.
  const GROUP_STYLE = {
    'aws-cloud': { stroke: '#232F3E', font: '#232F3E', icon: true },
    'aws-account': { stroke: '#CD2264', font: '#CD2264', icon: true },
    region: { stroke: '#00A4A6', font: '#147EBA', dash: '5 4', icon: true },
    az: { stroke: '#00A4A6', font: '#147EBA', dash: '8 4', center: true },
    vpc: { stroke: '#8C4FFF', font: '#8C4FFF', icon: true },
    'public-subnet': { stroke: '#7AA116', fill: '#F2F6E8', font: '#248814', icon: true },
    'private-subnet': { stroke: '#00A4A6', fill: '#E6F6F7', font: '#147EBA', icon: true },
    'security-group': { stroke: '#DD3522', font: '#DD3522' },
    'auto-scaling-group': { stroke: '#D86613', font: '#D86613', dash: '8 4', icon: true },
    'corporate-dc': { stroke: '#7D8998', font: '#5A6C86', icon: true },
    'azure-subscription': { stroke: '#0078D4', font: '#005BA1', icon: true },
    'azure-resource-group': { stroke: '#767676', font: '#505050', dash: '6 4', icon: true },
    'azure-region': { stroke: '#0078D4', font: '#005BA1', dash: '5 4' },
    'azure-vnet': { stroke: '#0078D4', font: '#005BA1', icon: true },
    'azure-subnet': { stroke: '#50A5E6', fill: '#EEF6FC', font: '#005BA1', icon: true },
    'azure-zone': { stroke: '#0078D4', font: '#005BA1', dash: '8 4', center: true },
    'gcp-cloud': { stroke: '#5F6368', font: '#3C4043' },
    'gcp-project': { stroke: '#5F6368', font: '#3C4043' },
    'gcp-region': { stroke: '#4285F4', font: '#1967D2', dash: '5 4' },
    'gcp-vpc': { stroke: '#4285F4', font: '#1967D2' },
    'gcp-subnet': { stroke: '#8AB4F8', fill: '#F1F6FE', font: '#1967D2' },
    'gcp-zone': { stroke: '#34A853', font: '#137333', dash: '8 4', center: true },
    'oci-tenancy': { stroke: '#9E9892', font: '#312D2A', dash: '6 4' },
    'oci-compartment': { stroke: '#AE562C', font: '#312D2A', dash: '2 3' },
    'oci-region': { stroke: '#9E9892', fill: '#F5F4F2', font: '#312D2A', rx: 10 },
    'oci-ad': { stroke: '#9E9892', font: '#312D2A', rx: 8, center: true },
    'oci-fault-domain': { stroke: '#9E9892', font: '#312D2A', rx: 7, dash: '8 4', center: true },
    'oci-vcn': { stroke: '#AE562C', font: '#AE562C', dash: '6 4', width: 2, icon: true },
    'oci-subnet': { stroke: '#AE562C', fill: '#FCFBFA', font: '#AE562C', dash: '6 4' },
    generic: { stroke: '#7D8998', font: '#5A6C86', dash: '6 4' },
  };
  const SLOT_FILL = '#FFF1C7';
  const SLOT_STROKE = '#8F5E00';
  const OK = '#176A02';
  const BAD = '#B32A0F';
  const REVEAL = '#0B5FA5';
  const DASH = { solid: null, dashed: '7 5', dotted: '2 5' };
  // Halo blanco bajo el nombre de nodos y slots: los bordes de zona y de grupo pasan por debajo del texto.
  const LABEL_HALO =
    ' stroke="#FFFFFF" stroke-width="4" paint-order="stroke" stroke-linejoin="round"';
  const CROSS = new Set([
    'auto-scaling-group',
    'security-group',
    'az',
    'azure-zone',
    'gcp-zone',
    'oci-ad',
    'oci-fault-domain',
  ]);

  const esc = (s) =>
    String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  const r1 = (n) => Math.round(n * 10) / 10;

  // ---------------------------------------------------------------- layout
  function depthOf(p) {
    const by = Object.fromEntries(p.groups.map((g) => [g.id, g]));
    const d = {};
    const depth = (id, guard) =>
      guard > 40 || !by[id] || !by[id].parent ? 0 : 1 + depth(by[id].parent, guard + 1);
    for (const g of p.groups) d[g.id] = depth(g.id, 0);
    return d;
  }
  function itemGeom(cell) {
    const cx = (cell.c + 0.5) * GEOM.CW;
    const top = cell.r * GEOM.CH;
    return {
      cx,
      top,
      cy: top + GEOM.ICON_TOP + GEOM.ICON / 2,
      icon: { x: cx - GEOM.ICON / 2, y: top + GEOM.ICON_TOP, s: GEOM.ICON },
      slot: { x: cx - GEOM.SLOT / 2, y: top + GEOM.SLOT_TOP, s: GEOM.SLOT },
      box: [cx + GEOM.BOX[0], top + GEOM.BOX[1], cx + GEOM.BOX[2], top + GEOM.BOX[3]],
    };
  }
  function layout(p) {
    const depth = depthOf(p);
    const groups = p.groups
      .map((g) => ({
        id: g.id,
        kind: g.kind,
        label: g.label,
        depth: depth[g.id],
        x: g.cell.c * GEOM.CW,
        y: g.cell.r * GEOM.CH,
        w: g.cell.w * GEOM.CW,
        h: g.cell.h * GEOM.CH,
      }))
      .sort((a, b) => CROSS.has(a.kind) - CROSS.has(b.kind) || a.depth - b.depth);
    const items = {};
    for (const n of p.nodes)
      items[n.id] = Object.assign({ id: n.id, kind: 'node', number: n.number }, itemGeom(n.cell));
    for (const s of p.slots)
      items[s.id] = Object.assign({ id: s.id, kind: 'slot', number: s.number }, itemGeom(s.cell));
    const edges = p.edges.map((e) => Object.assign({ id: e.id }, routeEdge(e, items)));
    return { w: p.layout.cols * GEOM.CW, h: p.layout.rows * GEOM.CH, groups, items, edges };
  }

  // ---------------------------------------------------------------- rutas ortogonales
  function anchor(it, side) {
    const half = it.kind === 'slot' ? GEOM.SLOT / 2 : GEOM.ICON / 2;
    if (side === 'left') return [it.cx - half - 2, it.cy];
    if (side === 'right') return [it.cx + half + 2, it.cy];
    if (side === 'top')
      return [it.cx, it.top + (it.kind === 'slot' ? GEOM.SLOT_TOP : GEOM.ICON_TOP) - 4];
    return [it.cx, it.top + GEOM.BOX[3]];
  }
  function sideToward(it, x, y) {
    const dx = x - it.cx;
    const dy = y - it.cy;
    if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? 'right' : 'left';
    return dy >= 0 ? 'bottom' : 'top';
  }
  function routeEdge(e, items) {
    const a = items[e.from];
    const b = items[e.to];
    if (!a || !b) return { points: [], missing: true };
    const route = e.route || 'auto';
    let pts;
    if (route === 'points' && e.points && e.points.length) {
      const way = e.points.map((q) => [q.c * GEOM.CW, q.r * GEOM.CH]);
      const s = anchor(a, sideToward(a, way[0][0], way[0][1]));
      const t = anchor(b, sideToward(b, way[way.length - 1][0], way[way.length - 1][1]));
      const snap = (w, q) => {
        if (Math.abs(w[1] - q[1]) < 3) w[1] = q[1];
        else if (Math.abs(w[0] - q[0]) < 3) w[0] = q[0];
      };
      snap(way[0], s);
      snap(way[way.length - 1], t);
      pts = [s, ...way, t];
    } else if (route === 'h-first') {
      const s = anchor(a, b.cx >= a.cx ? 'right' : 'left');
      const t = anchor(b, b.cy >= a.cy ? 'top' : 'bottom');
      pts = [s, [t[0], s[1]], t];
    } else if (route === 'v-first') {
      const s = anchor(a, b.cy >= a.cy ? 'bottom' : 'top');
      const t = anchor(b, b.cx >= a.cx ? 'left' : 'right');
      pts = [s, [s[0], t[1]], t];
    } else {
      const dx = b.cx - a.cx;
      const dy = b.cy - a.cy;
      if (Math.abs(dx) >= Math.abs(dy)) {
        const s = anchor(a, dx >= 0 ? 'right' : 'left');
        const t = anchor(b, dx >= 0 ? 'left' : 'right');
        if (Math.abs(s[1] - t[1]) < 1) pts = [s, t];
        else {
          const mx = (s[0] + t[0]) / 2;
          pts = [s, [mx, s[1]], [mx, t[1]], t];
        }
      } else {
        const s = anchor(a, dy >= 0 ? 'bottom' : 'top');
        const t = anchor(b, dy >= 0 ? 'top' : 'bottom');
        if (Math.abs(s[0] - t[0]) < 1) pts = [s, t];
        else {
          const my = (s[1] + t[1]) / 2;
          pts = [s, [s[0], my], [t[0], my], t];
        }
      }
    }
    return { points: pts, mid: labelAnchor(pts) };
  }
  function labelAnchor(pts) {
    let best = null;
    for (let i = 0; i < pts.length - 1; i++) {
      const [x1, y1] = pts[i];
      const [x2, y2] = pts[i + 1];
      const len = Math.abs(x2 - x1) + Math.abs(y2 - y1);
      if (!best || len > best.len)
        best = {
          len,
          x: (x1 + x2) / 2,
          y: (y1 + y2) / 2,
          horizontal: Math.abs(y2 - y1) < Math.abs(x2 - x1),
        };
    }
    return best || { x: 0, y: 0, horizontal: true, len: 0 };
  }
  function offsetPath(pts, d) {
    if (pts.length < 2) return pts;
    return pts.map(([x, y], i) => {
      const [ax, ay] = pts[Math.max(0, i - 1)];
      const [bx, by] = pts[Math.min(pts.length - 1, i + 1)];
      const horizontal = Math.abs(by - ay) < Math.abs(bx - ax);
      const sign = horizontal ? Math.sign(bx - ax) : Math.sign(by - ay);
      return horizontal ? [x, y - d * sign] : [x + d * sign, y];
    });
  }

  // ---------------------------------------------------------------- texto
  function wrap(text, max) {
    const words = String(text || '')
      .split(/\s+/)
      .filter(Boolean);
    const lines = [];
    let cur = '';
    for (const w of words) {
      if (!cur) cur = w;
      else if ((cur + ' ' + w).length <= max) cur += ' ' + w;
      else {
        lines.push(cur);
        cur = w;
      }
    }
    if (cur) lines.push(cur);
    if (lines.length > 2) lines.splice(1, lines.length - 1, lines.slice(1).join(' '));
    return lines;
  }
  function textLines(lines, x, y, attrs) {
    return lines
      .map((l, i) => `<text x="${r1(x)}" y="${r1(y + i * GEOM.LINE)}" ${attrs}>${esc(l)}</text>`)
      .join('');
  }
  /** Insignia del requisito (nodos y slots): cuadrado relleno, para que no se confunda con un paso. */
  function badge(x, y, n, fill) {
    return (
      `<g class="gm-badge"><rect x="${r1(x - 11)}" y="${r1(y - 11)}" width="22" height="22" rx="4" fill="${fill || INK}"/>` +
      `<text x="${r1(x)}" y="${r1(y + 5)}" text-anchor="middle" font-size="14" font-weight="700" fill="#FFFFFF">${esc(n)}</text></g>`
    );
  }
  /** Paso de una flecha: círculo con contorno sobre la línea. */
  function stepMark(x, y, n, on) {
    return (
      `<g class="gm-step"><circle cx="${r1(x)}" cy="${r1(y)}" r="11" fill="${on ? '#0B5FA5' : '#FFFFFF'}" stroke="${on ? '#0B5FA5' : INK}" stroke-width="2"/>` +
      `<text x="${r1(x)}" y="${r1(y + 4.5)}" text-anchor="middle" font-size="13" font-weight="700" fill="${on ? '#FFFFFF' : INK}">${esc(n)}</text></g>`
    );
  }
  const textWidth = (s, size) => String(s || '').length * (size || 14) * 0.53;

  const GLYPH = {
    correct: (x, y) =>
      `<g class="gm-glyph"><circle cx="${x}" cy="${y}" r="12" fill="${OK}"/><path d="M${x - 6} ${y}l4 4.5 8-9" fill="none" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></g>`,
    wrong: (x, y) =>
      `<g class="gm-glyph"><circle cx="${x}" cy="${y}" r="12" fill="${BAD}"/><path d="M${x - 5} ${y - 5}l10 10M${x + 5} ${y - 5}l-10 10" fill="none" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round"/></g>`,
    revealed: (x, y) =>
      `<g class="gm-glyph"><circle cx="${x}" cy="${y}" r="12" fill="${REVEAL}"/><path d="M${x - 6} ${y}h12M${x} ${y - 6}v12" fill="none" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round"/></g>`,
  };
  GLYPH.empty = GLYPH.wrong;

  // ---------------------------------------------------------------- dibujo
  /**
   * opts: {icons: {id: {label, short}}, placements, results, reveal, activeStep, groupIcons: [kind],
   *        text: {slot, empty, youPicked, title, desc}, sprite (incluido en <defs>), standalone (xmlns y tamaño)}
   */
  function render(p, opts) {
    const o = opts || {};
    const L = layout(p);
    const icons = o.icons || {};
    const placements = o.placements || {};
    const results = o.results || {};
    const withIcons = new Set(o.groupIcons || []);
    const short = (id) => (icons[id] && icons[id].short) || id;
    const nameOf = (id) => (icons[id] && icons[id].label) || id;
    const text = Object.assign({ title: p.title, desc: p.summary }, o.text || {});
    const out = [];
    out.push(
      `<svg ${o.standalone ? 'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ' : ''}` +
        `class="gm-svg" viewBox="0 0 ${L.w} ${L.h}" width="${o.standalone ? L.w : '100%'}"${o.standalone ? ` height="${L.h}"` : ''} ` +
        `preserveAspectRatio="xMidYMid meet" role="img" aria-labelledby="gm-t-${esc(p.id)} gm-d-${esc(p.id)}" font-family="Helvetica, Arial, sans-serif">`,
    );
    out.push(
      `<title id="gm-t-${esc(p.id)}">${esc(text.title)}</title><desc id="gm-d-${esc(p.id)}">${esc(text.desc)}</desc>`,
    );
    out.push(
      '<defs>' +
        (o.sprite || '') +
        `<marker id="gm-arrow" viewBox="0 0 12 12" refX="10.5" refY="6" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto-start-reverse">` +
        `<path d="M1 1.5 10.5 6 1 10.5" fill="none" stroke="${INK}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></marker></defs>`,
    );
    out.push(`<rect x="0" y="0" width="${L.w}" height="${L.h}" fill="#FFFFFF"/>`);

    for (const g of L.groups) {
      const st = GROUP_STYLE[g.kind] || GROUP_STYLE.generic;
      const dash = st.dash ? ` stroke-dasharray="${st.dash}"` : '';
      out.push(
        `<g class="gm-group gm-k-${g.kind}" data-group="${esc(g.id)}">` +
          `<rect x="${r1(g.x)}" y="${r1(g.y)}" width="${r1(g.w)}" height="${r1(g.h)}"${st.rx ? ` rx="${st.rx}"` : ''} fill="${st.fill || 'none'}" stroke="${st.stroke}" stroke-width="${st.width || 1.6}"${dash}/>`,
      );
      const hasIcon = st.icon && withIcons.has(g.kind);
      if (hasIcon)
        out.push(
          `<use href="#gi-group-${g.kind}" xlink:href="#gi-group-${g.kind}" x="${r1(g.x + 1)}" y="${r1(g.y + 1)}" width="24" height="24"/>`,
        );
      const tx = st.center ? g.x + g.w / 2 : g.x + (hasIcon ? 32 : 8);
      const halo = CROSS.has(g.kind)
        ? ' stroke="#FFFFFF" stroke-width="4" paint-order="stroke" stroke-linejoin="round"'
        : '';
      out.push(
        `<text x="${r1(tx)}" y="${r1(g.y + 18)}" font-size="15" font-weight="700" fill="${st.font}"${st.center ? ' text-anchor="middle"' : ''}${halo}>${esc(g.label)}</text></g>`,
      );
    }

    const edgeById = Object.fromEntries(p.edges.map((e) => [e.id, e]));
    for (const le of L.edges) {
      const e = edgeById[le.id];
      if (!le.points.length) continue;
      const on = o.activeStep !== null && o.activeStep !== undefined && e.step === o.activeStep;
      const dim = o.activeStep !== null && o.activeStep !== undefined && !on;
      const dash = DASH[e.style || 'solid'] ? ` stroke-dasharray="${DASH[e.style]}"` : '';
      const width = on ? 3.5 : 2;
      const line = (pts, start, end) =>
        `<polyline points="${pts.map(([x, y]) => `${r1(x)},${r1(y)}`).join(' ')}" fill="none" stroke="${INK}" stroke-width="${width}"${dash}` +
        `${end ? ' marker-end="url(#gm-arrow)"' : ''}${start ? ' marker-start="url(#gm-arrow)"' : ''} stroke-linejoin="round"/>`;
      out.push(
        `<g class="gm-edge${on ? ' on' : ''}" data-edge="${esc(e.id)}"${e.step ? ` data-step="${e.step}"` : ''}${dim ? ' opacity="0.28"' : ''}>`,
      );
      if (e.dir === 'both')
        out.push(
          line(offsetPath(le.points, 5), false, true),
          line(offsetPath(le.points, -5).slice().reverse(), false, true),
        );
      else out.push(line(le.points, false, e.dir !== 'none'));
      const m = le.mid;
      const label = e.label || '';
      const fits =
        label &&
        o.edgeLabels !== false &&
        (m.horizontal ? textWidth(label) <= m.len - 16 : m.x + 16 + textWidth(label) <= L.w - 4);
      if (fits) {
        const at = m.horizontal
          ? `x="${r1(m.x)}" y="${r1(m.y - (e.step ? 17 : 8))}" text-anchor="middle"`
          : `x="${r1(m.x + (e.step ? 16 : 8))}" y="${r1(m.y + 5)}"`;
        out.push(
          `<text class="gm-elabel" ${at} font-size="14" fill="${INK}" stroke="#FFFFFF" stroke-width="4" paint-order="stroke" stroke-linejoin="round">${esc(label)}</text>`,
        );
      }
      if (e.step) out.push(stepMark(m.x, m.y, e.step, on));
      out.push('</g>');
    }

    for (const n of p.nodes) {
      const it = L.items[n.id];
      const lines = wrap(n.label || short(n.icon), 15);
      out.push(
        `<g class="gm-node" data-node="${esc(n.id)}"><title>${esc(n.label || nameOf(n.icon))}</title>` +
          `<use href="#gi-${esc(n.icon)}" xlink:href="#gi-${esc(n.icon)}" x="${r1(it.icon.x)}" y="${r1(it.icon.y)}" width="${GEOM.ICON}" height="${GEOM.ICON}"/>` +
          textLines(
            lines,
            it.cx,
            it.top + GEOM.LABEL_Y,
            `font-size="14" text-anchor="middle" fill="${INK}"${LABEL_HALO}`,
          ),
      );
      if (n.number !== null && n.number !== undefined)
        out.push(badge(it.icon.x - 4, it.icon.y - 2, n.number));
      out.push('</g>');
    }

    for (const s of p.slots) {
      const it = L.items[s.id];
      const res = results[s.id];
      const shown = o.reveal
        ? s.accept[0]
        : res && res.status === 'revealed'
          ? s.accept[0]
          : placements[s.id];
      const status = res ? res.status : null;
      const edge =
        status === 'correct'
          ? OK
          : status === 'wrong' || status === 'empty'
            ? BAD
            : status === 'revealed'
              ? REVEAL
              : SLOT_STROKE;
      const sq = it.slot;
      const cls = `gm-slot${shown ? ' filled' : ''}${status ? ' v-' + status : ''}`;
      out.push(
        `<g class="${cls}" data-slot="${esc(s.id)}"><title>${esc((text.slot || 'Slot {n}').replace('{n}', s.number))}</title>`,
      );
      if (shown) {
        const wrongPick = status === 'revealed' && res.got && res.got !== s.accept[0];
        out.push(
          `<rect x="${r1(sq.x)}" y="${r1(sq.y)}" width="${sq.s}" height="${sq.s}" rx="8" fill="#FFFFFF" stroke="${edge}" stroke-width="${status ? 3 : 2}"${status ? '' : ' stroke-dasharray="6 4"'}/>`,
        );
        out.push(
          `<use href="#gi-${esc(shown)}" xlink:href="#gi-${esc(shown)}" x="${r1(it.cx - 23)}" y="${r1(sq.y + 7)}" width="46" height="46"${status === 'wrong' ? ' opacity="0.55"' : ''}/>`,
        );
        if (status === 'wrong')
          out.push(
            `<path d="M${r1(sq.x + 6)} ${r1(sq.y + sq.s - 6)}L${r1(sq.x + sq.s - 6)} ${r1(sq.y + 6)}" stroke="${BAD}" stroke-width="3" stroke-linecap="round"/>`,
          );
        const label =
          (o.reveal || status === 'correct' || status === 'revealed') && s.label
            ? s.label
            : short(shown);
        out.push(
          textLines(
            wrap(label, 15),
            it.cx,
            it.top + GEOM.LABEL_Y,
            `font-size="14" text-anchor="middle" fill="${INK}"${LABEL_HALO}${o.reveal || status ? ' font-weight="700"' : ''}`,
          ),
        );
        if (wrongPick)
          out.push(
            `<text x="${r1(it.cx)}" y="${r1(it.top + GEOM.LABEL_Y + 2 * GEOM.LINE - 2)}" font-size="12" text-anchor="middle" fill="${BAD}">${esc((text.youPicked || 'you: {s}').replace('{s}', short(res.got)))}</text>`,
          );
      } else {
        out.push(
          `<rect x="${r1(sq.x)}" y="${r1(sq.y)}" width="${sq.s}" height="${sq.s}" rx="8" fill="${SLOT_FILL}" stroke="${edge}" stroke-width="${status ? 3 : 2}" stroke-dasharray="6 4"/>`,
        );
        out.push(
          `<text x="${r1(it.cx)}" y="${r1(sq.y + sq.s / 2 + 8)}" font-size="22" font-weight="700" text-anchor="middle" fill="${SLOT_STROKE}">${esc(s.number)}?</text>`,
        );
        if (status === 'empty')
          out.push(
            `<text x="${r1(it.cx)}" y="${r1(it.top + GEOM.LABEL_Y)}" font-size="14" font-weight="700" text-anchor="middle" fill="${BAD}">${esc(text.empty || 'Empty')}</text>`,
          );
      }
      out.push(
        badge(
          sq.x,
          sq.y,
          s.number,
          status === 'correct' ? OK : status === 'wrong' || status === 'empty' ? BAD : INK,
        ),
      );
      if (status && GLYPH[status]) out.push(GLYPH[status](r1(sq.x + sq.s), r1(sq.y)));
      out.push('</g>');
    }
    out.push('</svg>');
    return out.join('');
  }

  // ---------------------------------------------------------------- zonas de toque y texto alternativo
  /** Rectángulo de cada slot como fracción del viewBox (botones HTML encima del SVG, con foco y toque). */
  function slotRects(p) {
    const L = layout(p);
    const out = {};
    for (const s of p.slots) {
      const it = L.items[s.id];
      const x0 = it.box[0];
      const y0 = it.box[1];
      const x1 = it.box[2];
      const y1 = it.top + 70; // termina antes del nombre (LABEL_Y), para que el foco no lo tape
      out[s.id] = { x: x0 / L.w, y: y0 / L.h, w: (x1 - x0) / L.w, h: (y1 - y0) / L.h };
    }
    return out;
  }
  /** Descripción en orden de lectura: grupos, nodos y flechas ("Compradores a Internet, paso 1, ..."). */
  function describe(p, names, t) {
    const tr =
      t ||
      ((k, v) => ({ slot: `slot ${v.n}`, edge: `${v.from} to ${v.to}`, step: `step ${v.n}` })[k]);
    const icons = names || {};
    const label = (id) => {
      const n = p.nodes.find((x) => x.id === id);
      if (n) return n.label || (icons[n.icon] && icons[n.icon].label) || n.icon;
      const s = p.slots.find((x) => x.id === id);
      return s ? tr('slot', { n: s.number }) : id;
    };
    const lines = [];
    for (const g of p.groups) lines.push(g.label);
    for (const n of p.nodes) lines.push(label(n.id));
    const edges = p.edges.slice().sort((a, b) => (a.step || 99) - (b.step || 99));
    for (const e of edges) {
      const parts = [tr('edge', { from: label(e.from), to: label(e.to) })];
      if (e.step) parts.push(tr('step', { n: e.step }));
      if (e.label) parts.push(e.label);
      lines.push(parts.join(', '));
    }
    return lines;
  }

  // ---------------------------------------------------------------- avisos de autoría
  function segHitsBox(a, b, box) {
    const [x1, y1] = a;
    const [x2, y2] = b;
    return (
      Math.max(x1, x2) > box[0] &&
      Math.min(x1, x2) < box[2] &&
      Math.max(y1, y2) > box[1] &&
      Math.min(y1, y2) < box[3]
    );
  }
  function crosses(pa, pb) {
    for (let i = 0; i < pa.length - 1; i++)
      for (let j = 0; j < pb.length - 1; j++) {
        const [a, b] = [pa[i], pa[i + 1]];
        const [c, d] = [pb[j], pb[j + 1]];
        const ah = Math.abs(a[1] - b[1]) < 0.5;
        const ch = Math.abs(c[1] - d[1]) < 0.5;
        if (ah === ch) continue;
        const [h1, h2, v1, v2] = ah ? [a, b, c, d] : [c, d, a, b];
        const x = v1[0];
        const y = h1[1];
        const inH = x > Math.min(h1[0], h2[0]) + 1 && x < Math.max(h1[0], h2[0]) - 1;
        const inV = y > Math.min(v1[1], v2[1]) + 1 && y < Math.max(v1[1], v2[1]) - 1;
        if (inH && inV) return true;
      }
    return false;
  }
  /** Flechas que atraviesan iconos, segmentos diagonales y cruces entre flechas. */
  function lint(p) {
    const L = layout(p);
    const warnings = [];
    for (const le of L.edges) {
      const e = p.edges.find((x) => x.id === le.id);
      for (const it of Object.values(L.items)) {
        if (it.id === e.from || it.id === e.to) continue;
        const box = [it.box[0] + 8, it.box[1] + 8, it.box[2] - 8, it.box[3] - 8];
        for (let i = 0; i < le.points.length - 1; i++) {
          if (segHitsBox(le.points[i], le.points[i + 1], box)) {
            warnings.push(`edge ${e.id} crosses ${it.id}`);
            break;
          }
        }
      }
      for (let i = 0; i < le.points.length - 1; i++) {
        const [a, b] = [le.points[i], le.points[i + 1]];
        if (Math.abs(a[0] - b[0]) > 0.5 && Math.abs(a[1] - b[1]) > 0.5)
          warnings.push(`edge ${e.id} has a diagonal segment`);
      }
    }
    for (let i = 0; i < L.edges.length; i++)
      for (let j = i + 1; j < L.edges.length; j++) {
        if (crosses(L.edges[i].points, L.edges[j].points))
          warnings.push(`edges ${L.edges[i].id} and ${L.edges[j].id} cross`);
      }
    return warnings;
  }

  return { GEOM, GROUP_STYLE, CROSS, layout, routeEdge, render, slotRects, describe, lint, wrap };
});
