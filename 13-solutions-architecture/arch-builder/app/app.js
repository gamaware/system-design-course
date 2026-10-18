/* global navigator, location, history, matchMedia, clearTimeout, Intl, URL */
/* Juego "completa el diagrama" (Lab 13, Diseño de Sistemas Escalables, ITESO). Origen: studykit/app/game-app.js.
 * Datos: window.GAME (game-data.js, lo escribe tools/build.py). Lógica: ArchCore. Dibujo: ArchRender.
 * Tres caminos equivalentes: arrastrar (Pointer Events, umbral de 6 px), tocar y colocar (ficha y luego slot, o slot y
 * luego ficha) y teclado (flechas en la paleta, dígitos, Enter, Supr, H, S, R, N, P, Z, ?). Cada cambio se guarda en
 * localStorage (dse_arch_v1) y se anuncia en una región viva. Idioma: español por defecto; inglés con el botón de la
 * barra (dse_arch_lang). Modos: práctica (pistas, reintento) y reto (reloj, sin pistas, un solo envío).
 */
(function () {
  'use strict';
  const G = window.GAME;
  const K = window.ArchCore;
  const R = window.ArchRender;
  if (!G || !K || !R) return;
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const esc = (s) =>
    String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  const STORE = G.store_key;
  const LANG_KEY = 'dse_arch_lang';
  const PUZ = Object.fromEntries(G.puzzles.map((p) => [p.id, p]));
  const IDS = G.puzzles.map((p) => p.id).sort();
  const store = (() => {
    try {
      return window.localStorage;
    } catch {
      return null;
    }
  })() || { getItem: () => null, setItem() {}, removeItem() {} };

  // ---------------------------------------------------------------- idioma
  // el idioma vive en memoria: si el almacenamiento falla (bloqueado o lleno) el botón sigue cambiándolo
  let langPref = (() => {
    try {
      return store.getItem(LANG_KEY) === 'en' ? 'en' : 'es';
    } catch {
      return 'es';
    }
  })();
  function lang() {
    return langPref;
  }
  function fill(str, vars) {
    return String(str).replace(/\{(\w+)\}/g, (m, k) =>
      vars && vars[k] !== null && vars[k] !== undefined ? vars[k] : m,
    );
  }
  function t(key, vars) {
    const table = (G.strings && G.strings[lang()]) || {};
    const es = (G.strings && G.strings.es) || {};
    return fill(
      table[key] !== null && table[key] !== undefined
        ? table[key]
        : es[key] !== null && es[key] !== undefined
          ? es[key]
          : key,
      vars,
    );
  }
  const num = (n) => new Intl.NumberFormat(lang() === 'en' ? 'en-US' : 'es-MX').format(n);
  const pick = (a, b) => (a !== null && a !== undefined && a !== '' ? a : b);
  const svcName = (id) => (G.icons[id] ? G.icons[id].label : id);
  const svcShort = (id) => (G.icons[id] ? G.icons[id].short : id);
  const svcMode = (id) => {
    const m = G.icons[id] && G.icons[id].mode;
    return m ? m[lang()] || m.es : '';
  };
  const fullName = (id) => (svcMode(id) ? `${svcName(id)} (${svcMode(id)})` : svcName(id));
  const cloudName = (c) => (G.clouds[c] ? G.clouds[c].label : c);
  const cloudFull = (c) => (G.clouds[c] ? G.clouds[c].name : c);
  /** Texto del puzzle en el idioma activo: español base, inglés si existe la traducción. */
  function tx(p) {
    const tr = lang() === 'en' && p.en ? p.en : null;
    return {
      tr: !!tr,
      missing: lang() === 'en' && !p.en,
      title: pick(tr && tr.title, p.title),
      summary: pick(tr && tr.summary, p.summary),
      req: (r) => pick(tr && tr.requirements && tr.requirements[String(r.n)], r.text),
      expl: (s) =>
        pick(tr && tr.slots && tr.slots[s.id] && tr.slots[s.id].explanation, s.explanation),
      cue: (s) => pick(tr && tr.slots && tr.slots[s.id] && tr.slots[s.id].hint_cue, s.hint_cue),
      node: (n) => pick(tr && tr.nodes && tr.nodes[n.id], n.label),
      edge: (e) => pick(tr && tr.edges && tr.edges[e.id], e.label),
      group: (g) => pick(tr && tr.groups && tr.groups[g.id], g.label),
      whyNot: (svc, sid) => {
        const tile = p.palette.find((x) => x.service === svc);
        const m = tr && tr.why_not && tr.why_not[svc];
        if (m && (m[sid] || m['*'])) return m[sid] || m['*'];
        if (tile && tile.why_not && (tile.why_not[sid] || tile.why_not['*']))
          return tile.why_not[sid] || tile.why_not['*'];
        return null;
      },
    };
  }
  /** Copia del puzzle con las etiquetas del idioma activo, para el dibujo (ids y geometría sin cambio). */
  function localized(p) {
    const T = tx(p);
    if (!T.tr) return p;
    const q = JSON.parse(JSON.stringify(p));
    q.title = T.title;
    q.summary = T.summary;
    q.nodes.forEach((n) => {
      n.label = T.node(n);
    });
    q.edges.forEach((e) => {
      e.label = T.edge(e);
    });
    q.groups.forEach((g) => {
      g.label = T.group(g);
    });
    return q;
  }
  const scenarioNo = (p) => Number(String(p.scenario).replace(/^e/, ''));

  // ---------------------------------------------------------------- estado
  const loaded = K.loadState(store, STORE);
  const S = K.prune(loaded.state, IDS);
  let noticeKey = loaded.notice ? 'notice.' + loaded.notice : null;
  function save() {
    K.saveState(store, STORE, S);
  }
  const V = {
    route: { view: 'start' },
    p: null,
    att: null,
    seed: '',
    order: [],
    sel: null,
    target: null,
    panel: null,
    undo: null,
    undoTimer: 0,
    reviewStep: 0,
    review: false,
    lastPlaced: null,
    mode: 'practice',
  };
  const settingMode = () => (K.MODES.includes(S.settings.mode) ? S.settings.mode : 'practice');
  const currentCloud = () => (K.CLOUDS.includes(S.settings.cloud) ? S.settings.cloud : 'aws');

  // ---------------------------------------------------------------- región viva y avisos
  let liveTimer = 0;
  function say(msg) {
    const el = $('#gm-live');
    el.textContent = '';
    clearTimeout(liveTimer);
    liveTimer = setTimeout(() => {
      el.textContent = msg;
    }, 30);
  }
  function showNotice() {
    const el = $('#gm-notice');
    if (!noticeKey) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    el.innerHTML = `<span>${esc(t(noticeKey))}</span> <button type="button" class="btn quiet" data-dismiss>${esc(t('action.dismiss'))}</button>`;
    el.querySelector('[data-dismiss]').onclick = () => {
      noticeKey = null;
      showNotice();
    };
  }

  // ---------------------------------------------------------------- textos fijos de la página
  function applyStatic() {
    document.documentElement.lang = lang() === 'en' ? 'en' : 'es-MX';
    $$('[data-i18n]').forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    $$('[data-i18n-aria]').forEach((el) => el.setAttribute('aria-label', t(el.dataset.i18nAria)));
    const lb = $('#gm-lang');
    if (lb) {
      lb.textContent = lang() === 'en' ? 'Español' : 'English';
      lb.setAttribute('lang', lang() === 'en' ? 'es' : 'en');
    }
    document.title = t('app.title');
    renderFooter();
  }
  function renderFooter() {
    const el = $('#gm-foot-text');
    if (!el) return;
    const cloud = V.p ? V.p.cloud : currentCloud();
    const pk = G.clouds[cloud] ? G.clouds[cloud].package : null;
    const pkgs = G.packages.filter(
      (x) => x.id === pk || (cloud === 'gcp' && x.id.startsWith('gcp')),
    );
    const list = pkgs.map((x) => `<a href="${esc(x.url)}">${esc(x.file)}</a>`).join(', ');
    el.innerHTML = `${esc(t('footer.icons', { cloud: G.clouds[cloud] ? G.clouds[cloud].name : cloud }))} ${list}. ${cloud === 'oci' ? esc(t('footer.oci')) + ' ' : ''}${esc(t('footer.disclaimer'))}`;
  }

  // ---------------------------------------------------------------- iconos
  function injectSprite() {
    if ($('#gm-sprite')) return;
    const div = document.createElement('div');
    div.innerHTML = `<svg id="gm-sprite" width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>${G.sprite}</defs></svg>`;
    document.body.prepend(div.firstChild);
  }
  /** Icono oficial de la nube (símbolo gi-cloud-<id> del sprite) en una caja w x h; decorativo: el nombre va en texto. */
  const cloudLogo = (c, cls, w, h) =>
    G.clouds[c] && G.clouds[c].logo
      ? `<svg class="${cls}" viewBox="0 0 ${w} ${h}" aria-hidden="true" focusable="false"><use href="#${esc(G.clouds[c].logo)}" width="${w}" height="${h}"/></svg>`
      : '';
  /** El logo ya es el nombre escrito (Google Cloud): caja ancha y el texto queda solo para lectores de pantalla. */
  const isWordmark = (c) => Boolean(G.clouds[c] && G.clouds[c].logo && G.clouds[c].wordmark);
  const cloudMark = (c) =>
    isWordmark(c)
      ? cloudLogo(c, 'gm-cloud-mark is-wordmark', 104, 18)
      : cloudLogo(c, 'gm-cloud-mark', 32, 20);
  const cloudLinkName = (c) =>
    `${cloudMark(c)}<span${isWordmark(c) ? ' class="vh"' : ''}>${esc(cloudName(c))}</span>`;
  const iconSVG = (id, size) =>
    `<svg class="gm-ico" width="${size}" height="${size}" viewBox="0 0 64 64" aria-hidden="true" focusable="false"><use href="#gi-${esc(id)}" width="64" height="64"/></svg>`;
  const GLYPH = {
    correct:
      '<svg class="gm-g" viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5l3.5 3.5 7.5-8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    wrong:
      '<svg class="gm-g" viewBox="0 0 20 20" aria-hidden="true"><path d="M5.5 5.5l9 9M14.5 5.5l-9 9" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
    revealed:
      '<svg class="gm-g" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="2.5" fill="currentColor"/><path d="M2.5 10s3-5 7.5-5 7.5 5 7.5 5-3 5-7.5 5-7.5-5-7.5-5z" fill="none" stroke="currentColor" stroke-width="1.75"/></svg>',
  };
  GLYPH.empty = GLYPH.wrong;

  // ---------------------------------------------------------------- rutas
  function go(hash) {
    if (location.hash === hash) route();
    else location.hash = hash;
  }
  function route() {
    pauseTimer();
    V.route = K.parseHash(location.hash);
    if (V.route.mode && V.route.mode !== S.settings.mode) {
      S.settings.mode = V.route.mode;
      save();
    }
    if (V.route.cloud && V.route.cloud !== S.settings.cloud) {
      S.settings.cloud = V.route.cloud;
      save();
    }
    if (V.route.view === 'puzzle' && !PUZ[V.route.id]) {
      noticeKey = 'notice.missing';
      V.route = { view: 'start' };
    }
    if (V.route.view === 'puzzle') openPuzzle(V.route.id);
    else {
      V.p = null;
      V.review = false;
    }
    render();
    const h = V.route.view === 'puzzle' ? $('#gm-title') : null;
    if (h && document.activeElement === document.body) h.focus({ preventScroll: true });
    window.scrollTo(0, 0);
    syncTimer();
  }
  function sessionFor(p) {
    return K.cloudPuzzles(G.puzzles, p.cloud).map((q) => q.id);
  }
  function openPuzzle(id) {
    const p = PUZ[id];
    if (V.p && V.p.id === id) return;
    V.p = p;
    V.sel = null;
    V.target = null;
    V.panel = null;
    V.hintSlot = null;
    V.hintFor = null;
    V.focusSvc = null;
    V.undo = null;
    V.review = false;
    V.reviewStep = 0;
    V.lastPlaced = null;
    if (S.settings.cloud !== p.cloud) S.settings.cloud = p.cloud;
    const o = S.open;
    const want = (V.route && V.route.mode) || settingMode();
    const untouched = (a) =>
      !Object.keys(a.placements || {}).length && !Object.keys(a.results || {}).length;
    const oMode = o && K.MODES.includes(o.mode) ? o.mode : 'practice';
    if (o && o.id === id && o.att && !(oMode !== want && (o.att.done || untouched(o.att)))) {
      V.att = o.att;
      V.seed = o.seed || `${id}|${o.started || ''}`;
      V.review = !!o.review;
      V.mode = oMode;
    } else {
      V.att = K.newAttempt();
      V.mode = want;
      const started = new Date().toISOString();
      V.seed = `${id}|${started}`;
      S.open = { id, att: V.att, seed: V.seed, started, review: false, mode: V.mode };
    }
    V.order = K.paletteOrder(p, V.seed);
    save();
  }
  function persistAttempt() {
    if (!V.p) return;
    bankTime();
    S.open = Object.assign(S.open || {}, {
      id: V.p.id,
      att: V.att,
      seed: V.seed,
      review: V.review,
      mode: V.mode,
    });
    save();
  }

  // ---------------------------------------------------------------- reloj
  const TM = { id: 0, since: 0, said: {} };
  const timerWanted = () =>
    !!(V.p && V.att && V.route.view === 'puzzle' && K.timerOn(V.mode, S.settings));
  const timerRunning = () =>
    timerWanted() && !V.att.done && !V.review && !document.hidden && !$('#gm-play').hidden;
  function elapsedNow() {
    return ((V.att && V.att.elapsed_ms) || 0) + (TM.since ? Math.max(0, Date.now() - TM.since) : 0);
  }
  function bankTime() {
    if (!TM.since || !V.att) return;
    const now = Date.now();
    V.att = K.addElapsed(V.att, now - TM.since);
    TM.since = now;
  }
  function pauseTimer() {
    if (TM.since && V.p) {
      bankTime();
      S.open = Object.assign(S.open || {}, { att: V.att });
      save();
    }
    clearInterval(TM.id);
    TM.id = 0;
    TM.since = 0;
  }
  function syncTimer() {
    if (timerRunning()) {
      if (!TM.id) {
        TM.since = Date.now();
        TM.id = setInterval(tick, 250);
      }
    } else if (TM.id || TM.since) pauseTimer();
    paintTimer();
  }
  let tickN = 0;
  function tick() {
    if (!timerRunning()) {
      syncTimer();
      return;
    }
    const c = K.clock(V.p, elapsedNow());
    paintTimer(c);
    const key = V.p.id + '|' + (S.open && S.open.started);
    if (V.mode === 'challenge' && c.expired) {
      onTimeUp();
      return;
    }
    if (!c.expired && c.left <= 60000 && c.budget > 60000 && !TM.said[key + 'm']) {
      TM.said[key + 'm'] = 1;
      say(t('say.oneMinute'));
    }
    if (V.mode !== 'challenge' && c.expired && !TM.said[key + 'b']) {
      TM.said[key + 'b'] = 1;
      say(t('say.budgetUsed'));
    }
    if (++tickN % 20 === 0) persistAttempt();
  }
  function timerText(c) {
    return c.expired && V.mode !== 'challenge'
      ? t('timer.over', { time: K.formatClock(c.over) })
      : t('timer.left', { time: K.formatClock(c.left, true) });
  }
  function timerAria(c) {
    return c.expired && V.mode !== 'challenge'
      ? t('timer.overAria', { time: K.formatClock(c.over), budget: K.formatClock(c.budget) })
      : t('timer.aria', { time: K.formatClock(c.left, true), budget: K.formatClock(c.budget) });
  }
  function timerHTML() {
    if (!timerWanted()) return '';
    const c = K.clock(V.p, elapsedNow());
    return `<span class="gm-timer tnum${c.expired ? ' is-over' : ''}" id="gm-timer" role="timer" aria-label="${esc(timerAria(c))}"><span class="gm-timer-t">${esc(timerText(c))}</span></span>`;
  }
  function paintTimer(c) {
    const el = $('#gm-timer');
    if (!el || !V.p) return;
    const cc = c || K.clock(V.p, elapsedNow());
    const txt = timerText(cc);
    const tEl = el.querySelector('.gm-timer-t');
    if (tEl && tEl.textContent !== txt) tEl.textContent = txt;
    el.classList.toggle('is-over', cc.expired);
    el.setAttribute('aria-label', timerAria(cc));
  }
  function onTimeUp() {
    bankTime();
    const res = K.timeUp(V.p, V.att);
    V.att = res.att;
    V.sel = null;
    V.target = null;
    V.undo = null;
    finish();
    V.panel = firstInteresting();
    persistAttempt();
    V.motion = 'reveal';
    renderPlay();
    say(t('say.timeUp') + ' ' + verdictLine());
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) pauseTimer();
    else syncTimer();
  });
  window.addEventListener('pagehide', () => pauseTimer());

  // ---------------------------------------------------------------- portada
  function statusOf(p) {
    const r = S.puzzles[p.id];
    if (!r) return t('status.new');
    if (r.perfects > 0) return t('status.perfect');
    return t('status.best', { points: num(r.best), max: num(10 * p.slots.length) });
  }
  const countText = (n) => t(n === 1 ? 'start.countOne' : 'start.count', { n: num(n) });
  function cloudPicker() {
    const cur = currentCloud();
    const opt = (c) =>
      `<label class="gm-cloud-opt" title="${esc(cloudFull(c))}"><input type="radio" name="gm-cloud" value="${c}"${c === cur ? ' checked' : ''}>` +
      `${isWordmark(c) ? cloudLogo(c, 'gm-cloud-logo is-wordmark', 140, 76) : cloudLogo(c, 'gm-cloud-logo', 72, 48)}<span class="gm-cloud-name${isWordmark(c) ? ' vh' : ''}">${esc(cloudName(c))}</span><span class="gm-cloud-count tnum">${esc(countText(K.cloudPuzzles(G.puzzles, c).length))}</span></label>`;
    return `<fieldset class="gm-clouds"><legend>${esc(t('start.cloud'))}</legend><div class="gm-cloud-opts">${K.CLOUDS.map(opt).join('')}</div></fieldset>`;
  }
  function renderStart() {
    const root = $('#gm-start');
    const cloud = currentCloud();
    const ps = K.cloudPuzzles(G.puzzles, cloud);
    const pr = K.progress(ps, S);
    const open = S.open && PUZ[S.open.id] && S.open.att && !S.open.att.done ? PUZ[S.open.id] : null;
    const primary = open
      ? `<a class="btn primary gm-cta" href="#p=${encodeURIComponent(open.id)}">${esc(t('start.resume', { title: tx(open).title, cloud: cloudName(open.cloud) }))}</a>`
      : ps.length
        ? `<a class="btn primary gm-cta" href="#p=${encodeURIComponent(ps[0].id)}">${esc(t('start.first', { n: num(scenarioNo(ps[0])), cloud: cloudName(cloud) }))}</a>`
        : '';
    const rows = ps
      .map((p) => {
        const others = K.CLOUDS.filter((c) => c !== cloud && K.sibling(G.puzzles, p, c));
        return (
          `<li><a class="gm-prow" href="#p=${encodeURIComponent(p.id)}"><span class="gm-row-title">${esc(t('start.scenario', { n: num(scenarioNo(p)) }))} · ${esc(tx(p).title)}</span>` +
          `<span class="gm-row-meta">${esc(t('level.' + p.difficulty))} · ${esc(t('meta.slots', { n: num(p.slots.length) }))} · ${esc(statusOf(p))}` +
          `${K.isDraft(p) ? ` · <span class="gm-draft">${esc(t('status.draft'))}</span>` : ''}` +
          `${others.length ? ` · ${esc(t('start.alsoIn', { clouds: others.map(cloudName).join(', ') }))}` : ''}</span></a></li>`
        );
      })
      .join('');
    root.innerHTML = `
      <div class="gm-start-head">
        <h1 id="gm-start-title">${esc(t('app.title'))}</h1>
        <p class="gm-lede">${esc(t('start.lede'))}</p>
        ${cloudPicker()}
        <p class="gm-progress tnum">${esc(t('start.progress', { played: num(pr.played), total: num(pr.total), perfect: num(pr.perfect), cloud: cloudName(cloud) }))}</p>
        <div class="gm-cta-row">${primary}<button type="button" class="btn quiet" data-help>${esc(t('help.title'))}</button></div>
        ${modeHTML()}
      </div>
      <section class="gm-block" aria-labelledby="gm-h-scen"><h2 id="gm-h-scen">${esc(t('start.scenarios', { cloud: cloudName(cloud) }))}</h2>
      ${ps.length ? `<ol class="gm-plist">${rows}</ol>` : `<p class="gm-empty">${esc(t('start.empty', { cloud: cloudName(cloud) }))}</p>`}</section>`;
    $('[data-help]', root).onclick = (e) => openHelp(e.currentTarget);
    $$('input[name="gm-cloud"]', root).forEach((r) =>
      r.addEventListener('change', () => {
        if (!r.checked) return;
        S.settings.cloud = r.value;
        save();
        renderStart();
        renderFooter();
        const again = $(`input[name="gm-cloud"][value="${r.value}"]`, root);
        if (again) again.focus();
        say(t('say.cloud', { cloud: cloudName(r.value) }));
      }),
    );
    wireMode(root);
  }
  function modeHTML() {
    const m = settingMode();
    const opt = (id) =>
      `<label class="gm-mode-opt"><input type="radio" name="gm-mode" value="${id}"${m === id ? ' checked' : ''}>` +
      `<span class="gm-mode-name">${esc(t('mode.' + id))}</span><span class="gm-mode-note">${esc(t('mode.' + id + 'Note'))}</span></label>`;
    return (
      `<fieldset class="gm-modes"><legend>${esc(t('mode.title'))}</legend><div class="gm-mode-opts">${opt('practice')}${opt('challenge')}</div>` +
      `<label class="gm-check"><input type="checkbox" data-timer${S.settings.timer ? ' checked' : ''}${m === 'challenge' ? ' disabled' : ''}>${esc(t('timer.setting'))}</label></fieldset>`
    );
  }
  function wireMode(root) {
    $$('input[name="gm-mode"]', root).forEach((r) =>
      r.addEventListener('change', () => {
        if (!r.checked) return;
        S.settings.mode = r.value;
        save();
        const tb = $('input[data-timer]', root);
        if (tb) tb.disabled = r.value === 'challenge';
        say(t('say.mode', { mode: t('mode.' + r.value) }));
      }),
    );
    const tb = $('input[data-timer]', root);
    if (tb)
      tb.addEventListener('change', () => {
        S.settings.timer = tb.checked;
        save();
      });
  }

  // ---------------------------------------------------------------- juego
  const isList = () => window.matchMedia && matchMedia('(max-width: 599.98px)').matches;
  const slotBy = (id) => V.p.slots.find((s) => s.id === id);
  const slotByNumber = (n) => V.p.slots.find((s) => s.number === n);
  const reqFor = (sid) => V.p.requirements.find((r) => r.slot === sid);
  const results = () => V.att.results || {};
  const hintLevel = (sid) => (V.att.hints && V.att.hints[sid]) || 0;
  function mdInline(s) {
    return esc(s)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  }
  function highlight(html, cue) {
    if (!cue) return html;
    const c = esc(cue);
    const i = html.indexOf(c);
    return i < 0
      ? html
      : html.slice(0, i) + `<mark class="gm-cue">${c}</mark>` + html.slice(i + c.length);
  }
  function slotState(sid) {
    const r = results()[sid];
    return {
      r,
      placed: V.att.placements[sid] || null,
      // Solo estados conocidos: el resultado puede venir de localStorage y el estado entra a atributos class.
      status: r && Object.prototype.hasOwnProperty.call(GLYPH, r.status) ? r.status : null,
      locked: !!V.att.locked[sid],
    };
  }
  function slotAria(s) {
    const req = reqFor(s.id);
    const reqText = req
      ? tx(V.p)
          .req(req)
          .replace(/\{\{s\d+\}\}/g, '…')
      : '';
    const st = slotState(s.id);
    let state = st.placed ? t('aria.holds', { svc: fullName(st.placed) }) : t('aria.empty');
    if (st.status) state += ', ' + t('verdict.' + st.status);
    return t('aria.slot', { n: s.number, total: V.p.slots.length, req: reqText, state });
  }
  function blankHTML(s) {
    const st = slotState(s.id);
    const svc = st.status === 'revealed' || V.review ? s.accept[0] : st.placed;
    const cls = [
      'gm-blank',
      svc ? 'filled' : '',
      st.status ? 'v-' + st.status : '',
      V.target === s.id ? 'is-target' : '',
      V.panel === s.id ? 'is-panel' : '',
    ]
      .filter(Boolean)
      .join(' ');
    const inner = svc
      ? `${iconSVG(svc, 24)}<span class="gm-blank-name" lang="en">${esc(svcShort(svc))}</span>`
      : `<span class="gm-blank-num">${num(s.number)}?</span><span class="gm-blank-pick">${esc(t('blank.pick'))}</span>`;
    const verdict = st.status
      ? `<span class="gm-verdict v-${st.status}">${GLYPH[st.status]}<span>${esc(t('verdict.' + st.status))}</span></span>`
      : '';
    return `<button type="button" class="${cls}" data-slot="${s.id}" data-kind="blank" aria-label="${esc(slotAria(s))}">${inner}</button>${verdict}`;
  }
  function renderRequirements() {
    const T = tx(V.p);
    return V.p.requirements
      .map((r) => {
        const s = r.slot ? slotBy(r.slot) : null;
        let html = mdInline(T.req(r));
        if (s) {
          if (hintLevel(s.id) >= 1 || V.att.done) html = highlight(html, T.cue(s));
          html = html.replace(/\{\{(s\d+)\}\}/, () => blankHTML(s));
        }
        const st = s ? slotState(s.id) : null;
        const cls = [
          'gm-req',
          s ? 'has-slot' : 'is-context',
          st && st.status ? 'v-' + st.status : '',
          s && V.panel === s.id ? 'is-panel' : '',
        ]
          .filter(Boolean)
          .join(' ');
        const hint =
          s && hintLevel(s.id) ? `<span class="gm-hint-note">${esc(hintNote(s))}</span>` : '';
        return `<li class="${cls}" data-req="${r.n}"${s ? ` data-for="${s.id}"` : ''} value="${r.n}"><span class="gm-req-n" aria-hidden="true">${num(r.n)}</span><span class="gm-req-text">${html}${hint}</span></li>`;
      })
      .join('');
  }
  function hintNote(s) {
    const lvl = hintLevel(s.id);
    const cat = G.categories[s.category] ? G.categories[s.category][lang()] : s.category;
    const parts = [t('hint.level', { n: lvl })];
    if (lvl >= 1) parts.push(t('hint.category', { category: cat }));
    if (lvl >= 3) {
      const h = K.hintView(V.p, s.id, 3, V.seed);
      parts.push(t('hint.pair', { a: svcShort(h.pair[0]), b: svcShort(h.pair[1]) }));
    }
    return parts.join(' · ');
  }
  function fadedFor() {
    const sid =
      V.target ||
      focusedSlot() ||
      V.hintSlot ||
      (V.panel && !V.att.locked[V.panel] ? V.panel : null);
    if (!sid || V.att.locked[sid]) return { faded: new Set(), pair: new Set() };
    const lvl = hintLevel(sid);
    if (lvl < 2) return { faded: new Set(), pair: new Set() };
    const h = K.hintView(V.p, sid, lvl, V.seed);
    return { faded: new Set(h.faded), pair: new Set(h.pair) };
  }
  function renderPalette() {
    const rem = K.remaining(V.p, V.att.placements);
    const uses = K.uses(V.p);
    const hint = fadedFor();
    // ficha del tabindex itinerante: solo si existe en esta paleta (otra nube u otro puzzle traen otras fichas)
    const focusSvc =
      [V.focusSvc, V.sel && V.sel.service].find((svc) => svc && V.order.includes(svc)) ||
      V.order[0];
    return V.order
      .map((svc) => {
        const left = rem[svc];
        const selected = !!(V.sel && V.sel.service === svc && !V.sel.from);
        const cls = [
          'gm-tile',
          left <= 0 ? 'used' : '',
          selected ? 'selected' : '',
          hint.faded.has(svc) ? 'faded' : '',
          hint.pair.has(svc) ? 'paired' : '',
        ]
          .filter(Boolean)
          .join(' ');
        const badge =
          uses[svc] > 1 ? `<span class="gm-uses tnum" aria-hidden="true">×${num(left)}</span>` : '';
        const label =
          t('aria.tile', { svc: fullName(svc), left: num(left) }) +
          (selected ? ', ' + t('aria.selected') : '') +
          (left <= 0 ? ', ' + t('aria.used') : '');
        const mode = svcMode(svc) ? `<span class="gm-tile-mode">${esc(svcMode(svc))}</span>` : '';
        return (
          `<div class="${cls}" role="option" id="gm-t-${svc}" data-svc="${svc}" aria-selected="${selected}" aria-disabled="${left <= 0}" aria-label="${esc(label)}" tabindex="${svc === focusSvc ? 0 : -1}">` +
          `${iconSVG(svc, 40)}<span class="gm-tile-name" lang="en">${esc(svcShort(svc))}</span>${mode}${badge}</div>`
        );
      })
      .join('');
  }
  function diagramSVG(extra) {
    const p = localized(V.p);
    const T = tx(V.p);
    return R.render(
      p,
      Object.assign(
        {
          icons: G.icons,
          placements: Object.assign({}, V.att.placements),
          results: V.review ? {} : results(),
          reveal: V.review || false,
          activeStep: V.review && V.reviewStep ? V.reviewStep : null,
          groupIcons: G.groupIcons,
          text: {
            slot: t('svg.slot'),
            empty: t('verdict.empty'),
            youPicked: t('svg.youPicked'),
            title: T.title,
            desc: T.summary,
          },
        },
        extra || {},
      ),
    );
  }
  function renderDiagram() {
    const rects = R.slotRects(V.p);
    const hits = isList()
      ? ''
      : V.p.slots
          .map((s) => {
            const r = rects[s.id];
            const st = slotState(s.id);
            const cls = [
              'gm-hit',
              st.placed ? 'filled' : '',
              st.status ? 'v-' + st.status : '',
              V.target === s.id ? 'is-target' : '',
              V.panel === s.id ? 'is-panel' : '',
            ]
              .filter(Boolean)
              .join(' ');
            return `<button type="button" class="${cls}" data-slot="${s.id}" data-kind="hit" style="left:${(r.x * 100).toFixed(3)}%;top:${(r.y * 100).toFixed(3)}%;width:${(r.w * 100).toFixed(3)}%;height:${(r.h * 100).toFixed(3)}%" aria-label="${esc(slotAria(s))}"></button>`;
          })
          .join('');
    const lines = R.describe(localized(V.p), G.icons, (k, v) => t('desc.' + k, v));
    // el lienzo toma la proporción del viewBox: los botones en % del lienzo caen sobre los slots aunque se acote el alto
    const L = R.layout(V.p);
    return `<div class="gm-canvas" style="--gm-ratio:${(L.w / L.h).toFixed(5)}">${diagramSVG()}${hits}</div>
      <div class="gm-diagram-tools"><button type="button" class="btn quiet" data-zoom>${esc(t('action.zoom'))}</button></div>
      <details class="gm-alt"><summary>${esc(t('diagram.textAlt'))}</summary><ul>${lines.map((l) => `<li>${esc(l)}</li>`).join('')}</ul></details>`;
  }
  function stepList() {
    const T = tx(V.p);
    const steps = V.p.edges.filter((e) => e.step).sort((a, b) => a.step - b.step);
    if (!steps.length) return '';
    return `<ol class="gm-steps">${steps.map((e) => `<li class="${V.review && V.reviewStep === e.step ? 'on' : ''}" value="${e.step}"><span class="gm-step-n tnum" aria-hidden="true">${num(e.step)}</span>${esc(T.edge(e) || t('review.noLabel'))}</li>`).join('')}</ol>`;
  }
  function scoreNow() {
    return K.score(V.p, V.att, {
      mode: V.mode,
      elapsedMs: K.timerOn(V.mode, S.settings) ? elapsedNow() : null,
    });
  }
  function verdictLine() {
    const sc = scoreNow();
    const vars = {
      right: num(sc.right),
      total: num(sc.total),
      points: num(sc.points - (sc.bonus || 0) - (sc.timer || 0)),
      max: num(sc.max),
    };
    let s = t('verdict.line', vars);
    if (sc.perfect) s += ' ' + t('verdict.perfect', { bonus: num(sc.bonus) });
    else if (V.att.attempt === 1 && !V.att.revealed && Object.keys(results()).length)
      s += ' ' + t('verdict.firstTry');
    if (K.timerOn(V.mode, S.settings)) {
      s +=
        ' ' +
        t('verdict.time', {
          time: K.formatClock(elapsedNow()),
          budget: K.formatClock(K.budgetMs(V.p)),
        });
      if (sc.timer) s += ' ' + t('verdict.timeBonus', { bonus: num(sc.timer) });
    }
    return s;
  }
  function refLabel(url) {
    try {
      const u = new URL(url);
      return u.hostname.replace(/^www\./, '') + u.pathname.replace(/\/$/, '');
    } catch {
      return url;
    }
  }
  function panelHTML() {
    if (!Object.keys(results()).length || V.review) return '';
    const sid = V.panel || firstInteresting();
    if (!sid) return '';
    const s = slotBy(sid);
    const T = tx(V.p);
    const st = slotState(sid);
    const status = st.status || 'empty';
    const answer = s.accept[0];
    const known = status === 'correct' || status === 'revealed' || V.att.done;
    const got = st.r && st.r.got;
    const title = t('panel.slot', { n: num(s.number), verdict: t('verdict.' + status) });
    const parts = [
      `<h2 class="gm-panel-title v-${status}" id="gm-panel-title" tabindex="-1">${GLYPH[status]}<span>${esc(title)}</span></h2>`,
    ];
    if (known)
      parts.push(
        `<h3>${esc(t('panel.why', { svc: fullName(answer) }))}</h3><p>${esc(T.expl(s))}</p>`,
      );
    if (got && got !== answer) {
      const role =
        G.icons[got] && G.icons[got].role ? G.icons[got].role[lang()] || G.icons[got].role.es : '';
      const wn = T.whyNot(got, sid) || t('panel.whyNotFallback', { svc: fullName(got), role });
      parts.push(`<h3>${esc(t('panel.whyNot', { svc: fullName(got) }))}</h3><p>${esc(wn)}</p>`);
    }
    if (!known) parts.push(`<p class="gm-panel-nudge">${esc(t('panel.nudge'))}</p>`);
    if (known) {
      parts.push(
        `<p class="gm-panel-cue">${esc(t('panel.cue'))} <mark class="gm-cue">${esc(T.cue(s))}</mark></p>`,
      );
      const links = (s.refs || [])
        .map(
          (u) =>
            `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(refLabel(u))}</a>`,
        )
        .join('');
      if (links) parts.push(`<h3>${esc(t('panel.sources'))}</h3><p class="gm-links">${links}</p>`);
    }
    return `<div class="gm-panel-body">${parts.join('')}</div>`;
  }
  function firstInteresting() {
    const order = V.p.slots.map((s) => s.id);
    return order.find((id) => results()[id] && results()[id].status !== 'correct') || order[0];
  }
  function actionsHTML() {
    const att = V.att;
    const anyPlaced = Object.keys(att.placements).some((k) => !att.locked[k]);
    const submitted = Object.keys(results()).length > 0;
    const last = results();
    const pendingRetry =
      submitted &&
      !att.done &&
      V.p.slots.some(
        (s) => last[s.id] && last[s.id].status !== 'correct' && last[s.id].attempt === att.attempt,
      );
    const b = [];
    const sid = hintTarget();
    if (V.review) {
      b.push(
        `<button type="button" class="btn secondary" data-act="prev-step"${V.reviewStep <= 1 ? ' disabled' : ''}>${esc(t('review.prev'))}</button>`,
      );
      b.push(
        `<button type="button" class="btn secondary" data-act="next-step">${esc(V.reviewStep ? t('review.next') : t('review.play'))}</button>`,
      );
      b.push(
        `<button type="button" class="btn quiet" data-act="close-review">${esc(t('review.close'))}</button>`,
      );
      b.push(
        `<button type="button" class="btn primary" data-act="next">${esc(t('action.next'))}</button>`,
      );
    } else if (att.done) {
      b.push(
        `<button type="button" class="btn secondary" data-act="review">${esc(t('action.review'))}</button>`,
      );
      b.push(
        `<button type="button" class="btn quiet" data-act="again">${esc(t('action.again'))}</button>`,
      );
      b.push(
        `<button type="button" class="btn primary" data-act="next">${esc(t('action.next'))}</button>`,
      );
    } else if (pendingRetry) {
      b.push(
        `<button type="button" class="btn quiet" data-act="reveal">${esc(t('action.reveal'))}</button>`,
      );
      b.push(
        `<button type="button" class="btn primary" data-act="retry">${esc(t('action.retry'))}</button>`,
      );
    } else {
      if (K.hintsAllowed(V.mode))
        b.push(
          `<button type="button" class="btn quiet" data-act="hint"${sid && !att.locked[sid] && hintLevel(sid) < 3 ? '' : ' disabled'}${sid ? ` aria-label="${esc(t('action.hintFor', { n: num(slotBy(sid).number) }))}"` : ''}>${esc(sid && !isList() ? t('action.hintFor', { n: num(slotBy(sid).number) }) : t('action.hint'))}</button>`,
        );
      b.push(
        `<button type="button" class="btn quiet" data-act="reset"${anyPlaced ? '' : ' disabled'}>${esc(t('action.reset'))}</button>`,
      );
      if (V.undo)
        b.push(
          `<button type="button" class="btn quiet" data-act="undo">${esc(t('action.undo'))}</button>`,
        );
      b.push(
        `<button type="button" class="btn primary" data-act="submit"${anyPlaced ? '' : ' disabled'}>${esc(t('action.submit'))}</button>`,
      );
    }
    return b.join('');
  }
  function statusText() {
    if (V.sel) {
      if (V.sel.from)
        return t('status.pickedUp', {
          n: num(slotBy(V.sel.from).number),
          svc: fullName(V.sel.service),
        });
      return t('status.selected', { svc: fullName(V.sel.service) });
    }
    if (V.target) return t('status.target', { n: num(slotBy(V.target).number) });
    if (V.review) return V.reviewStep ? reviewCaption() : t('review.intro');
    if (Object.keys(results()).length) return verdictLine();
    return isList() ? t('status.idleList') : t('status.idle');
  }
  function reviewCaption() {
    const e = V.p.edges.find((x) => x.step === V.reviewStep);
    if (!e) return '';
    const T = tx(V.p);
    const target = [e.to, e.from]
      .map((id) => V.p.slots.find((s) => s.id === id) || V.p.nodes.find((n) => n.id === id))
      .find((x) => x && x.number !== null && x.number !== undefined);
    const req = target ? V.p.requirements.find((r) => r.n === target.number) : null;
    const reqText = req
      ? T.req(req).replace(/\{\{(s\d+)\}\}/g, (m, sid) => svcShort(slotBy(sid).accept[0]))
      : '';
    return t('review.caption', {
      n: num(e.step),
      label: T.edge(e) || t('review.noLabel'),
      req: reqText,
    });
  }
  function barHTML() {
    const sess = sessionFor(V.p);
    const idx = Math.max(0, sess.indexOf(V.p.id));
    const others = K.CLOUDS.map((c) => {
      const q = K.sibling(G.puzzles, V.p, c);
      if (c === V.p.cloud)
        return `<span class="gm-cloud-link is-current" aria-current="true" title="${esc(cloudFull(c))}">${cloudLinkName(c)}</span>`;
      return q
        ? `<a class="gm-cloud-link" href="#p=${encodeURIComponent(q.id)}" title="${esc(cloudFull(c))}">${cloudLinkName(c)}</a>`
        : `<span class="gm-cloud-link is-missing" title="${esc(cloudFull(c))}">${cloudLinkName(c)}</span>`;
    }).join('');
    const rec = S.puzzles[V.p.id];
    return `<a class="gm-bar-back" href="${K.hashFor({ view: 'start', cloud: V.p.cloud })}"><span>${esc(t('bar.back'))}</span></a>
      <nav class="gm-cloud-switch" aria-label="${esc(t('bar.cloud'))}">${others}</nav>
      <span class="gm-bar-pos tnum">${esc(t('bar.position', { n: num(idx + 1), m: num(sess.length) }))}</span>
      ${rec ? `<span class="gm-bar-score tnum">${esc(t('bar.best', { points: num(rec.best), max: num(10 * V.p.slots.length) }))}</span>` : ''}
      ${V.mode === 'challenge' ? `<span class="tag gm-mode-tag">${esc(t('mode.tag'))}</span>` : ''}${timerHTML()}
      <button type="button" class="btn quiet" data-act="list">${esc(t('list.button'))}</button>
      <button type="button" class="btn quiet icon-only" data-act="help" aria-label="${esc(t('help.title'))}">?</button>`;
  }
  function renderPlay() {
    const root = $('#gm-play');
    const T = tx(V.p);
    const focus = focusKey();
    const sx = window.scrollX;
    const sy = window.scrollY;
    root.setAttribute('data-motion', V.motion || '');
    V.motion = null;
    const topics = (V.p.topics || []).map((x) => `<span class="tag">${esc(x)}</span>`).join('');
    root.innerHTML = `
      <div class="gm-bar">${barHTML()}</div>
      <div class="gm-grid${V.review ? ' is-review' : ''}${isList() ? ' is-list' : ''}">
        <section class="gm-brief" aria-labelledby="gm-title">
          <p class="gm-kicker">${esc(t('start.scenario', { n: num(scenarioNo(V.p)) }))} · ${esc(cloudName(V.p.cloud))}</p>
          <h1 id="gm-title" tabindex="-1">${esc(T.title)}${T.missing ? ' <span class="gm-en" lang="es">ES</span>' : ''}</h1>
          <p class="gm-summary">${esc(T.summary)}</p>
          <p class="gm-meta">${topics}${V.att.done ? `<span class="tag">${esc(t('level.' + V.p.difficulty))}</span>` : ''}${K.isDraft(V.p) ? `<span class="tag gm-draft">${esc(t('status.draft'))}</span>` : ''}</p>
          <p class="gm-h-req sk-label" role="heading" aria-level="2">${esc(t('requirements'))}</p>
          <ol class="gm-reqs">${renderRequirements()}</ol>
        </section>
        <section class="gm-work" aria-label="${esc(t('work'))}">
          <div class="gm-palette-wrap${isList() ? ' is-tray' : ''}">
            <p class="gm-h-pal sk-label" role="heading" aria-level="2" id="gm-pal-label">${esc(t('palette.title'))}</p>
            <div class="gm-palette" role="listbox" aria-labelledby="gm-pal-label" aria-orientation="horizontal">${renderPalette()}</div>
          </div>
          <figure class="gm-diagram">${renderDiagram()}<figcaption>${stepList()}</figcaption></figure>
        </section>
        <aside class="gm-panel" aria-live="off" aria-labelledby="gm-panel-title">${panelHTML()}</aside>
      </div>
      <div class="gm-dock">
        <p class="gm-status" id="gm-status">${esc(statusText())}</p>
        <div class="gm-actions">${actionsHTML()}</div>
      </div>`;
    wirePlay(root);
    if (window.scrollY !== sy || window.scrollX !== sx) window.scrollTo(sx, sy);
    restoreFocus(focus);
    if (V.lastPlaced) {
      root
        .querySelectorAll(
          `.gm-svg [data-slot="${V.lastPlaced}"], .gm-blank[data-slot="${V.lastPlaced}"]`,
        )
        .forEach((g) => g.classList.add('pop'));
      V.lastPlaced = null;
    }
    renderFooter();
    syncTimer();
  }

  // ---------------------------------------------------------------- foco entre redibujos
  function focusKey() {
    const a = document.activeElement;
    if (!a || !$('#gm-play').contains(a)) return null;
    if (a.dataset.slot) return `[data-slot="${a.dataset.slot}"][data-kind="${a.dataset.kind}"]`;
    if (a.dataset.svc) return `.gm-tile[data-svc="${a.dataset.svc}"]`;
    if (a.dataset.act) return `[data-act="${a.dataset.act}"]`;
    if (a.id) return '#' + a.id;
    return null;
  }
  function restoreFocus(sel) {
    if (!sel) return;
    let el = $(sel, $('#gm-play'));
    if (!el && sel.startsWith('[data-act'))
      el = $('.gm-actions .btn.primary:not([disabled])') || $('.gm-actions .btn:not([disabled])');
    if (el) el.focus({ preventScroll: true });
  }
  function focusedSlot() {
    const a = document.activeElement;
    return a && a.dataset && a.dataset.slot && $('#gm-play').contains(a) ? a.dataset.slot : null;
  }

  // ---------------------------------------------------------------- acciones
  function update(att, msg) {
    V.att = att;
    persistAttempt();
    renderPlay();
    if (msg) say(msg);
  }
  /** Slot ya calificado en este intento: no cambia hasta pedir otro intento. */
  const judgedNow = (sid) => !!(results()[sid] && results()[sid].attempt === V.att.attempt);
  function placeService(sid, svc, from) {
    const s = slotBy(sid);
    if (!V.att.done && (judgedNow(sid) || (from && judgedNow(from)))) {
      say(t('say.judged'));
      return false;
    }
    if (V.att.done || V.att.locked[sid]) {
      say(t('say.locked', { n: num(s.number) }));
      return false;
    }
    const r = from ? K.move(V.p, V.att, from, sid) : K.place(V.p, V.att, sid, svc);
    if (!r.ok) {
      if (r.reason === 'used') say(t('say.used', { svc: fullName(svc) }));
      else if (r.reason === 'locked') say(t('say.locked', { n: num(s.number) }));
      return false;
    }
    V.sel = null;
    V.target = null;
    V.undo = null;
    V.lastPlaced = sid;
    let msg = t('say.placed', { n: num(s.number), svc: fullName(svc) });
    if (r.returned) msg += ' ' + t('say.returned', { svc: fullName(r.returned) });
    update(r.att, msg);
    return true;
  }
  function removeFrom(sid) {
    const svc = V.att.placements[sid];
    if (!svc || V.att.locked[sid]) return;
    if (judgedNow(sid)) {
      say(t('say.judged'));
      return;
    }
    V.sel = null;
    update(K.remove(V.att, sid), t('say.removed', { svc: fullName(svc) }));
  }
  function onSlotActivate(sid) {
    if (V.review) return;
    const s = slotBy(sid);
    if (V.att.done || V.att.locked[sid]) {
      if (V.sel && !V.att.done) {
        say(t('say.locked', { n: num(s.number) }));
        return;
      }
      if (Object.keys(results()).length) {
        V.panel = sid;
        renderPlay();
        say(
          t('panel.slot', {
            n: num(s.number),
            verdict: t('verdict.' + (slotState(sid).status || 'empty')),
          }),
        );
      }
      return;
    }
    if (V.sel) {
      placeService(sid, V.sel.service, V.sel.from && V.sel.from !== sid ? V.sel.from : null);
      return;
    }
    const placed = V.att.placements[sid];
    const judged = results()[sid];
    if (judgedNow(sid)) {
      // ya enviado en este intento: mostrar su explicación; para cambiarlo primero se pide otro intento
      V.panel = sid;
      renderPlay();
      say(t('panel.slot', { n: num(s.number), verdict: t('verdict.' + judged.status) }));
      return;
    }
    if (placed) {
      V.sel = { service: placed, from: sid };
      V.target = null;
      renderPlay();
      say(t('status.pickedUp', { n: num(s.number), svc: fullName(placed) }));
      return;
    }
    V.target = V.target === sid ? null : sid;
    renderPlay();
    say(V.target ? t('status.target', { n: num(s.number) }) : t('say.cancelled'));
  }
  function onTileActivate(svc) {
    if (V.review || V.att.done) return;
    if (V.sel && V.sel.from) {
      const from = V.sel.from;
      V.sel = null;
      removeFrom(from);
      return;
    }
    if (K.remaining(V.p, V.att.placements)[svc] <= 0) {
      say(t('say.used', { svc: fullName(svc) }));
      return;
    }
    if (V.target) {
      V.focusSvc = svc;
      placeService(V.target, svc);
      return;
    }
    V.focusSvc = svc;
    V.sel = V.sel && V.sel.service === svc ? null : { service: svc, from: null };
    renderPlay();
    say(V.sel ? t('status.selected', { svc: fullName(svc) }) : t('say.cancelled'));
  }
  function cancelSelection() {
    if (!V.sel && !V.target) return;
    V.sel = null;
    V.target = null;
    renderPlay();
    say(t('say.cancelled'));
  }
  function doSubmit(force) {
    const empties = V.p.slots.filter((s) => !V.att.locked[s.id] && !V.att.placements[s.id]);
    if (!Object.keys(V.att.placements).some((k) => !V.att.locked[k])) return;
    if (empties.length && !force) {
      confirmBox(
        t('confirm.emptyTitle'),
        t('confirm.empty', { n: num(empties.length) }),
        t('confirm.submitAnyway'),
        t('confirm.keepPlaying'),
        () => doSubmit(true),
      );
      return;
    }
    bankTime();
    const res = V.mode === 'challenge' ? K.challengeSubmit(V.p, V.att) : K.submit(V.p, V.att);
    const verdict = res.verdict;
    if (!verdict) return;
    V.sel = null;
    V.target = null;
    V.undo = null;
    V.panel = verdict.wrong[0] || verdict.empty[0] || verdict.correct[0];
    V.att = res.att;
    if (V.att.done) finish();
    persistAttempt();
    V.motion = 'reveal';
    renderPlay();
    const lines = [verdictLine()];
    for (const sid of [...verdict.wrong, ...verdict.empty]) {
      const s = slotBy(sid);
      const got = V.att.results[sid].got;
      lines.push(
        got
          ? t('say.wrong', { n: num(s.number), svc: fullName(got) })
          : t('say.empty', { n: num(s.number) }),
      );
    }
    say(lines.join(' '));
    const h = $('#gm-panel-title');
    if (h && h.getBoundingClientRect().top > window.innerHeight) h.focus({ preventScroll: false });
  }
  function finish() {
    if (V.att.recorded) return;
    const sc = scoreNow();
    const hints = Object.values(V.att.hints).reduce((a, b) => a + b, 0);
    S.puzzles[V.p.id] = K.updateRecord(
      S.puzzles[V.p.id],
      { perfect: sc.perfect, points: sc.points, hints },
      new Date().toISOString(),
    );
    V.att = Object.assign({}, V.att, { recorded: true });
  }
  function doRetry() {
    V.att = K.retry(V.p, V.att);
    V.panel = null;
    V.sel = null;
    V.target = null;
    persistAttempt();
    renderPlay();
    say(t('say.retry', { n: num(V.att.attempt) }));
    const first = V.p.slots.find((s) => !V.att.locked[s.id]);
    const el =
      first && ($(`.gm-hit[data-slot="${first.id}"]`) || $(`.gm-blank[data-slot="${first.id}"]`));
    if (el) el.focus();
  }
  function doReveal() {
    bankTime();
    V.att = K.reveal(V.p, V.att);
    finish();
    V.panel = firstInteresting();
    persistAttempt();
    renderPlay();
    say(t('say.revealed'));
  }
  function doReset(force) {
    if (!Object.keys(V.att.placements).some((k) => !V.att.locked[k])) return;
    if (!force) {
      confirmBox(
        t('confirm.resetTitle'),
        t('confirm.reset'),
        t('action.reset'),
        t('confirm.keepPlaying'),
        () => doReset(true),
      );
      return;
    }
    V.undo = V.att;
    V.sel = null;
    V.target = null;
    clearTimeout(V.undoTimer);
    V.undoTimer = setTimeout(() => {
      V.undo = null;
      if (V.p) renderPlay();
    }, 5000);
    update(K.resetAttempt(V.att), t('say.reset'));
  }
  function doUndo() {
    if (!V.undo) return;
    const a = V.undo;
    V.undo = null;
    update(a, t('say.undone'));
  }
  /** Slot de la pista: el enfocado, el último slot elegible que tuvo el foco (el que nombra el botón), el
   *  objetivo o el del panel. */
  function hintTarget() {
    return (
      focusedSlot() ||
      (V.hintFor && !V.att.locked[V.hintFor] ? V.hintFor : null) ||
      V.target ||
      (V.panel && !V.att.locked[V.panel] ? V.panel : null)
    );
  }
  function doHint() {
    const sid = hintTarget();
    if (!K.hintsAllowed(V.mode)) {
      say(t('say.noHints'));
      return;
    }
    if (!sid) {
      say(t('say.hintWhich'));
      return;
    }
    if (V.att.locked[sid] || hintLevel(sid) >= 3 || V.att.done) return;
    V.hintSlot = sid;
    V.att = K.useHint(V.att, sid, V.mode);
    persistAttempt();
    renderPlay();
    say(t('say.hint', { n: num(slotBy(sid).number), note: hintNote(slotBy(sid)) }));
  }
  function nextPuzzle(delta) {
    const sess = sessionFor(V.p);
    const i = sess.indexOf(V.p.id);
    const next = sess[i + delta];
    if (next) {
      V.p = null;
      go('#p=' + encodeURIComponent(next));
    } else if (delta > 0) {
      const cloud = V.p.cloud;
      S.open = null;
      save();
      V.p = null;
      go(K.hashFor({ view: 'start', cloud }));
      say(t('say.sessionDone'));
    }
  }
  function playAgain() {
    const id = V.p.id;
    pauseTimer();
    S.open = null;
    V.p = null;
    openPuzzle(id);
    render();
    syncTimer();
    say(t('say.again'));
  }
  function startReview() {
    V.review = true;
    V.reviewStep = 0;
    persistAttempt();
    renderPlay();
    say(t('review.intro'));
  }
  function stepReview(d) {
    const max = V.p.edges.reduce((m, e) => Math.max(m, e.step || 0), 0);
    V.reviewStep = Math.min(max, Math.max(1, V.reviewStep + d));
    renderPlay();
    say(reviewCaption());
  }
  function zoom(trigger) {
    const d = $('#gm-zoom');
    $('#gm-zoom-body').innerHTML = diagramSVG();
    $('#gm-zoom-title').textContent = tx(V.p).title;
    openDialog(d, trigger);
  }

  // ---------------------------------------------------------------- diálogos
  function openDialog(d, trigger) {
    d._trigger = trigger || document.activeElement;
    if (typeof d.showModal === 'function') d.showModal();
    else d.setAttribute('open', '');
    const h = d.querySelector('h2');
    if (h) h.focus();
  }
  function closeDialog(d) {
    if (typeof d.close === 'function') d.close();
    else d.removeAttribute('open');
    if (d._trigger && document.contains(d._trigger)) d._trigger.focus();
  }
  function openHelp(trigger) {
    openDialog($('#gm-help'), trigger);
  }
  function confirmBox(title, text, yes, no, onYes) {
    const d = $('#gm-confirm');
    $('#gm-confirm-title').textContent = title;
    $('#gm-confirm-text').textContent = text;
    const by = d.querySelector('[data-yes]');
    const bn = d.querySelector('[data-no]');
    by.textContent = yes;
    bn.textContent = no;
    by.onclick = () => {
      closeDialog(d);
      onYes();
    };
    bn.onclick = () => closeDialog(d);
    openDialog(d);
    bn.focus();
  }
  function openList(trigger) {
    const sess = sessionFor(V.p);
    $('#gm-list-title').textContent = t('list.title', { cloud: cloudName(V.p.cloud) });
    $('#gm-list-items').innerHTML = sess
      .map((id) => {
        const p = PUZ[id];
        return `<li${id === V.p.id ? ' aria-current="true"' : ''}><a href="#p=${encodeURIComponent(id)}" data-jump><span class="tnum">${num(scenarioNo(p))}.</span> ${esc(tx(p).title)}</a><span class="gm-list-v">${esc(statusOf(p))}</span></li>`;
      })
      .join('');
    $$('#gm-list-items [data-jump]').forEach((a) =>
      a.addEventListener('click', () => {
        const d = $('#gm-list');
        if (d.open) d.close();
        V.p = null;
      }),
    );
    openDialog($('#gm-list'), trigger);
  }
  $$('dialog [data-close]').forEach((b) =>
    b.addEventListener('click', () => closeDialog(b.closest('dialog'))),
  );
  $$('dialog').forEach((d) =>
    d.addEventListener('cancel', (e) => {
      e.preventDefault();
      closeDialog(d);
    }),
  );

  // ---------------------------------------------------------------- clics, teclado y arrastre
  function wirePlay(root) {
    $$('[data-act]', root).forEach((b) =>
      b.addEventListener('click', (e) => {
        const a = b.dataset.act;
        if (a === 'submit') doSubmit(false);
        else if (a === 'retry') doRetry();
        else if (a === 'reveal') doReveal();
        else if (a === 'reset') doReset(false);
        else if (a === 'undo') doUndo();
        else if (a === 'hint') doHint();
        else if (a === 'next') nextPuzzle(1);
        else if (a === 'again') playAgain();
        else if (a === 'review') startReview();
        else if (a === 'close-review') {
          V.review = false;
          persistAttempt();
          renderPlay();
        } else if (a === 'next-step') stepReview(1);
        else if (a === 'prev-step') stepReview(-1);
        else if (a === 'list') openList(e.currentTarget);
        else if (a === 'help') openHelp(e.currentTarget);
      }),
    );
    const z = $('[data-zoom]', root);
    if (z) z.addEventListener('click', (e) => zoom(e.currentTarget));
    const pal = $('.gm-palette', root);
    if (pal)
      pal.addEventListener('click', (e) => {
        if (e.target.closest('.gm-tile') || !V.sel || !V.sel.from) return;
        const from = V.sel.from;
        V.sel = null;
        removeFrom(from);
      });
    $$('.gm-tile', root).forEach((el) => {
      el.addEventListener('pointerdown', (e) =>
        pointerDown(e, { svc: el.dataset.svc, from: null, el }),
      );
      el.addEventListener('click', (e) => {
        if (drag.suppressClick) {
          drag.suppressClick = false;
          return;
        }
        onTileActivate(el.dataset.svc);
        e.preventDefault();
      });
      el.addEventListener('focus', () => {
        V.focusSvc = el.dataset.svc;
      });
    });
    $$('[data-slot]', root).forEach((el) => {
      el.addEventListener('pointerdown', (e) => {
        const sid = el.dataset.slot;
        const svc = V.att.placements[sid];
        if (V.att.locked[sid] || V.review || judgedNow(sid)) return;
        if (svc) pointerDown(e, { svc, from: sid, el });
      });
      el.addEventListener('click', (e) => {
        if (drag.suppressClick) {
          drag.suppressClick = false;
          return;
        }
        onSlotActivate(el.dataset.slot);
        e.preventDefault();
      });
      el.addEventListener('mouseenter', () => linkHover(el.dataset.slot, true));
      el.addEventListener('mouseleave', () => linkHover(el.dataset.slot, false));
      el.addEventListener('focus', () => {
        linkHover(el.dataset.slot, true);
        refreshHintButton();
      });
      el.addEventListener('blur', () => linkHover(el.dataset.slot, false));
    });
    $$('.gm-req.has-slot', root).forEach((li) => {
      li.addEventListener('mouseenter', () => linkHover(li.dataset.for, true));
      li.addEventListener('mouseleave', () => linkHover(li.dataset.for, false));
    });
  }
  function refreshHintButton() {
    const b = $('.gm-actions [data-act="hint"]');
    const sid = focusedSlot();
    if (!b || !sid) return;
    if (!V.att.locked[sid] && hintLevel(sid) < 3) V.hintFor = sid;
    // en teléfonos el texto no cambia: la barra no debe crecer bajo el dedo mientras se toca un hueco
    if (!isList()) b.textContent = t('action.hintFor', { n: num(slotBy(sid).number) });
    b.setAttribute('aria-label', t('action.hintFor', { n: num(slotBy(sid).number) }));
    b.disabled = !!V.att.locked[sid] || hintLevel(sid) >= 3;
  }
  function linkHover(sid, on) {
    $$(`.gm-req[data-for="${sid}"], .gm-hit[data-slot="${sid}"]`).forEach((el) =>
      el.classList.toggle('is-linked', on),
    );
    const g = $(`.gm-svg [data-slot="${sid}"]`);
    if (g) g.classList.toggle('is-linked', on);
  }

  // Arrastre con Pointer Events: umbral de 6 px, la ficha fantasma sigue al puntero, el destino válido más cercano
  // dentro de 24 px se ilumina, y la página se desplaza sola cerca de los bordes.
  const drag = { active: null, suppressClick: false };
  function pointerDown(e, src) {
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    if (V.att.done || V.review) return;
    if (!src.from && K.remaining(V.p, V.att.placements)[src.svc] <= 0) return;
    drag.active = {
      src,
      x0: e.clientX,
      y0: e.clientY,
      id: e.pointerId,
      started: false,
      ghost: null,
      over: null,
    };
    try {
      src.el.setPointerCapture(e.pointerId);
    } catch {
      /* motores viejos sin captura */
    }
    src.el.addEventListener('pointermove', pointerMove);
    src.el.addEventListener('pointerup', pointerUp);
    src.el.addEventListener('pointercancel', pointerCancel);
    src.el.addEventListener('lostpointercapture', pointerCancel);
  }
  function pointerMove(e) {
    const d = drag.active;
    if (!d || e.pointerId !== d.id) return;
    if (!d.started) {
      if (Math.hypot(e.clientX - d.x0, e.clientY - d.y0) < 6) return;
      d.started = true;
      d.ghost = document.createElement('div');
      d.ghost.className = 'gm-ghost';
      d.ghost.innerHTML = `${iconSVG(d.src.svc, 48)}<span lang="en">${esc(svcShort(d.src.svc))}</span>`;
      document.body.appendChild(d.ghost);
      document.documentElement.classList.add('gm-dragging');
      say(t('say.dragging', { svc: fullName(d.src.svc) }));
    }
    e.preventDefault();
    d.ghost.style.transform = `translate(${e.clientX - 32}px, ${e.clientY - 32}px)`;
    const over = hitTarget(e.clientX, e.clientY);
    const key = over ? (over.slot ? 's:' + over.slot : 'palette') : null;
    if (key !== d.over) {
      $$('.is-over').forEach((el) => el.classList.remove('is-over'));
      if (over && over.slot)
        $$(`[data-slot="${over.slot}"]`).forEach((el) => el.classList.add('is-over'));
      if (over && over.palette) {
        const p = $('.gm-palette');
        if (p) p.classList.add('is-over');
      }
      d.over = key;
      d.target = over;
    }
    const edge = 48;
    if (e.clientY < edge) window.scrollBy(0, -12);
    else if (e.clientY > window.innerHeight - edge) window.scrollBy(0, 12);
  }
  function hitTarget(x, y) {
    const els = document.elementsFromPoint
      ? document.elementsFromPoint(x, y)
      : [document.elementFromPoint(x, y)];
    for (const el of els) {
      if (!el || !el.closest) continue;
      const s = el.closest('[data-slot]');
      if (s && $('#gm-play').contains(s)) return { slot: s.dataset.slot };
      if (el.closest('.gm-palette')) return { palette: true };
    }
    let best = null;
    let bestD = 24;
    for (const el of $$('.gm-hit, .gm-blank')) {
      const r = el.getBoundingClientRect();
      const dist = Math.hypot(
        Math.max(r.left - x, 0, x - r.right),
        Math.max(r.top - y, 0, y - r.bottom),
      );
      if (dist < bestD) {
        bestD = dist;
        best = el.dataset.slot;
      }
    }
    return best ? { slot: best } : null;
  }
  function endDrag() {
    const d = drag.active;
    drag.active = null;
    if (!d) return null;
    const el = d.src.el;
    el.removeEventListener('pointermove', pointerMove);
    el.removeEventListener('pointerup', pointerUp);
    el.removeEventListener('pointercancel', pointerCancel);
    el.removeEventListener('lostpointercapture', pointerCancel);
    if (d.ghost) d.ghost.remove();
    document.documentElement.classList.remove('gm-dragging');
    $$('.is-over').forEach((x) => x.classList.remove('is-over'));
    return d;
  }
  function pointerUp(e) {
    const d = drag.active;
    if (!d || e.pointerId !== d.id) return;
    if (!d.started) {
      endDrag();
      return;
    }
    drag.suppressClick = true;
    setTimeout(() => {
      drag.suppressClick = false;
    }, 0);
    endDrag();
    const tgt = d.target;
    if (tgt && tgt.slot) placeService(tgt.slot, d.src.svc, d.src.from);
    else if (tgt && tgt.palette && d.src.from) removeFrom(d.src.from);
    else say(t('say.dropCancelled'));
  }
  function pointerCancel(e) {
    const d = drag.active;
    if (!d || (e.pointerId !== null && e.pointerId !== undefined && e.pointerId !== d.id)) return;
    if (e.type === 'lostpointercapture') {
      if (!d.started) endDrag();
      return;
    }
    endDrag();
    say(t('say.dropCancelled'));
  }
  window.addEventListener('blur', () => {
    if (drag.active) endDrag();
  });

  // Teclado: dentro de la paleta las letras saltan por nombre; fuera de ella son atajos.
  let typeahead = '';
  let typeTimer = 0;
  document.addEventListener('keydown', (e) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && V.p && V.undo) {
        e.preventDefault();
        doUndo();
      }
      return;
    }
    if ($('dialog[open]')) return;
    const tag = (e.target && e.target.tagName) || '';
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(tag)) return;
    if (!V.p || V.route.view !== 'puzzle') {
      if (e.key === '?') {
        openHelp();
        e.preventDefault();
      }
      return;
    }
    const tile = e.target.closest && e.target.closest('.gm-tile');
    const slotEl = e.target.closest && e.target.closest('[data-slot]');
    if (tile) {
      const tiles = $$('.gm-tile');
      const i = tiles.indexOf(tile);
      const moveTo = (j) => {
        const n = tiles[(j + tiles.length) % tiles.length];
        tiles.forEach((x) => {
          x.tabIndex = -1;
        });
        n.tabIndex = 0;
        n.focus();
        V.focusSvc = n.dataset.svc;
      };
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        moveTo(i + 1);
        return;
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        moveTo(i - 1);
        return;
      }
      if (e.key === 'Home') {
        e.preventDefault();
        moveTo(0);
        return;
      }
      if (e.key === 'End') {
        e.preventDefault();
        moveTo(tiles.length - 1);
        return;
      }
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onTileActivate(tile.dataset.svc);
        return;
      }
      if (/^[a-z]$/i.test(e.key)) {
        e.preventDefault();
        clearTimeout(typeTimer);
        typeahead += e.key.toLowerCase();
        typeTimer = setTimeout(() => {
          typeahead = '';
        }, 700);
        const names = tiles.map((x) =>
          svcShort(x.dataset.svc)
            .toLowerCase()
            .replace(/^(amazon|aws|azure|oci|cloud)\s+/, ''),
        );
        let j = names.findIndex((n, k) => k > i && n.startsWith(typeahead));
        if (j < 0) j = names.findIndex((n) => n.startsWith(typeahead));
        if (j >= 0) moveTo(j);
        return;
      }
    }
    if (slotEl && (e.key === 'Delete' || e.key === 'Backspace')) {
      e.preventDefault();
      removeFrom(slotEl.dataset.slot);
      return;
    }
    if (/^[1-9]$/.test(e.key)) {
      const s = slotByNumber(Number(e.key));
      if (s && V.sel) {
        e.preventDefault();
        placeService(s.id, V.sel.service, V.sel.from || null);
      } else if (s) {
        e.preventDefault();
        const el = $(`.gm-hit[data-slot="${s.id}"]`) || $(`.gm-blank[data-slot="${s.id}"]`);
        if (el) el.focus();
      }
      return;
    }
    const k = e.key;
    if (k === 'Escape') {
      cancelSelection();
      return;
    }
    if (k === '?') {
      e.preventDefault();
      openHelp();
      return;
    }
    const lower = k.toLowerCase();
    if (lower === 'h') {
      e.preventDefault();
      doHint();
    } else if (lower === 's') {
      e.preventDefault();
      if (!V.att.done && !V.review) doSubmit(false);
    } else if (lower === 'r') {
      e.preventDefault();
      if (!V.att.done && !V.review) doReset(false);
    } else if (lower === 'n') {
      e.preventDefault();
      nextPuzzle(1);
    } else if (lower === 'p') {
      e.preventDefault();
      nextPuzzle(-1);
    } else if (lower === 'z') {
      e.preventDefault();
      zoom(document.activeElement);
    }
  });

  // ---------------------------------------------------------------- arranque
  function render() {
    const view = V.route.view;
    $('#gm').dataset.view = view;
    $('#gm-start').hidden = view !== 'start';
    $('#gm-play').hidden = view !== 'puzzle';
    showNotice();
    if (view === 'start') renderStart();
    else if (view === 'puzzle' && V.p) renderPlay();
    renderFooter();
  }
  const mqList = window.matchMedia ? matchMedia('(max-width: 599.98px)') : null;
  if (mqList && mqList.addEventListener)
    mqList.addEventListener('change', () => {
      if (V.p && V.route.view === 'puzzle') renderPlay();
    });
  window.addEventListener('hashchange', route);
  const langBtn = $('#gm-lang');
  if (langBtn)
    langBtn.addEventListener('click', () => {
      langPref = lang() === 'en' ? 'es' : 'en';
      try {
        store.setItem(LANG_KEY, langPref);
      } catch {
        /* sin almacenamiento: el idioma nuevo vale solo en esta visita */
      }
      applyStatic();
      render();
      langBtn.focus();
      say(t('say.lang'));
    });
  try {
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  } catch {
    /* navegador sin control de desplazamiento */
  }
  if (!navigator.cookieEnabled && !loaded.notice) noticeKey = 'notice.unavailable';
  injectSprite();
  applyStatic();
  route();
  window.ArchGame = { state: () => S, view: () => V, t, render, store: STORE };
})();
