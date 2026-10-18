/* global module, globalThis */
/* Juego "completa el diagrama": lógica pura (sin DOM). UMD: window.ArchCore en el navegador, module.exports en node.
 * Origen: studykit/app/game-core.js (GAME-SPEC.md 1.2 a 1.9) sin tipos de negocio, sin tarjetas ni repetición
 * espaciada. Todo es inmutable: cada función devuelve un intento o estado nuevo, así "deshacer" es conservar el anterior.
 *
 * Intento  {placements: {slotId: serviceId}, locked: {slotId: true}, attempt: 1.., hints: {slotId: 0..3},
 *           results: {slotId: {status: correct|wrong|empty|revealed, points, attempt, got}}, done, revealed, elapsed_ms}
 * Estado   {v: 1, puzzles: {id: registro}, open, settings}   (localStorage dse_arch_v1)
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ArchCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : window, function () {
  'use strict';

  const BASE = [10, 5, 2]; // puntos por slot resuelto en el envío 1, 2, 3 o más
  const MIN_POINTS = 2;
  const MODES = ['practice', 'challenge'];
  const CLOUDS = ['aws', 'azure', 'gcp', 'oci'];
  const SLOT_SECONDS = 40;
  const VERSION = 1;
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const isDraft = (p) => !!p && p.status === 'draft';
  const slotById = (p, id) => p.slots.find((s) => s.id === id);

  // ---------------------------------------------------------------- puntaje
  function slotPoints(attempt, hints) {
    const base = BASE[Math.min(attempt, BASE.length) - 1];
    return Math.max(MIN_POINTS, Math.floor(base / Math.pow(2, hints || 0)));
  }
  /** 30 s de lectura más 40 s por slot. */
  function budgetMs(p) {
    return (SLOT_SECONDS * p.slots.length + 30) * 1000;
  }

  // ---------------------------------------------------------------- modos y reloj
  function hintsAllowed(mode) {
    return mode !== 'challenge';
  }
  function timerOn(mode, settings) {
    return mode === 'challenge' || !!(settings && settings.timer);
  }
  function clock(p, elapsedMs) {
    const budget = budgetMs(p);
    const elapsed = Math.max(0, Number(elapsedMs) || 0);
    return {
      budget,
      elapsed,
      left: Math.max(0, budget - elapsed),
      over: Math.max(0, elapsed - budget),
      expired: elapsed >= budget,
    };
  }
  function formatClock(ms, up) {
    const v = Math.max(0, Number(ms) || 0) / 1000;
    const sec = up ? Math.ceil(v) : Math.floor(v);
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
  }
  function addElapsed(att, ms) {
    if (att.done || !(Number(ms) > 0)) return att;
    const next = clone(att);
    next.elapsed_ms = (next.elapsed_ms || 0) + Number(ms);
    return next;
  }

  // ---------------------------------------------------------------- colocar fichas
  function uses(p) {
    const out = {};
    for (const t of p.palette) out[t.service] = t.uses || 1;
    return out;
  }
  function remaining(p, placements) {
    const out = uses(p);
    for (const svc of Object.values(placements)) if (svc in out) out[svc] -= 1;
    return out;
  }
  function newAttempt() {
    return {
      placements: {},
      locked: {},
      attempt: 1,
      hints: {},
      results: {},
      done: false,
      revealed: false,
      elapsed_ms: 0,
    };
  }
  /** Pone `service` en `slotId`; la ficha que estaba ahí regresa a la paleta (`returned`). */
  function place(p, att, slotId, service) {
    if (!slotById(p, slotId)) return { att, ok: false, reason: 'slot' };
    if (!(service in uses(p))) return { att, ok: false, reason: 'service' };
    if (att.done || att.locked[slotId]) return { att, ok: false, reason: 'locked' };
    const prev = att.placements[slotId] || null;
    if (prev === service) return { att, ok: true, returned: null };
    if (remaining(p, att.placements)[service] <= 0) return { att, ok: false, reason: 'used' };
    const next = clone(att);
    next.placements[slotId] = service;
    return { att: next, ok: true, returned: prev };
  }
  /** Mueve una ficha a otro slot; la que estaba en el destino regresa a la paleta (no se intercambian). */
  function move(p, att, from, to) {
    if (!slotById(p, from) || !slotById(p, to)) return { att, ok: false, reason: 'slot' };
    if (att.done || att.locked[from] || att.locked[to]) return { att, ok: false, reason: 'locked' };
    const svc = att.placements[from];
    if (!svc) return { att, ok: false, reason: 'empty' };
    if (from === to) return { att, ok: true, returned: null };
    const next = clone(att);
    const returned = next.placements[to] || null;
    delete next.placements[from];
    next.placements[to] = svc;
    return { att: next, ok: true, returned };
  }
  function remove(att, slotId) {
    if (att.done || att.locked[slotId] || !(slotId in att.placements)) return att;
    const next = clone(att);
    delete next.placements[slotId];
    return next;
  }
  function resetAttempt(att) {
    if (att.done) return att;
    const next = clone(att);
    for (const s of Object.keys(next.placements)) if (!next.locked[s]) delete next.placements[s];
    return next;
  }

  // ---------------------------------------------------------------- revisar
  function check(p, placements) {
    const out = {};
    for (const s of p.slots) {
      const got = placements[s.id];
      out[s.id] = !got ? 'empty' : got === s.accept[0] ? 'correct' : 'wrong';
    }
    return out;
  }
  /** Envío: veredicto por slot abierto; los correctos se bloquean con sus puntos. verdict null si no hay nada puesto. */
  function submit(p, att) {
    if (att.done) return { att, verdict: null };
    const open = p.slots.filter((s) => !att.locked[s.id]);
    if (!open.some((s) => att.placements[s.id])) return { att, verdict: null };
    const next = clone(att);
    const verdict = { correct: [], wrong: [], empty: [] };
    const marks = check(p, att.placements);
    for (const s of open) {
      const status = marks[s.id];
      verdict[status].push(s.id);
      const got = att.placements[s.id] || null;
      if (status === 'correct') {
        next.locked[s.id] = true;
        next.results[s.id] = {
          status,
          points: slotPoints(att.attempt, att.hints[s.id] || 0),
          attempt: att.attempt,
          got,
        };
      } else {
        next.results[s.id] = { status, points: 0, attempt: att.attempt, got };
      }
    }
    next.done = p.slots.every((s) => next.locked[s.id]);
    return { att: next, verdict };
  }
  /** Reintento: los correctos siguen bloqueados, los incorrectos y vacíos se limpian, el siguiente envío paga menos. */
  function retry(p, att) {
    if (att.done) return att;
    const next = clone(att);
    next.attempt += 1;
    for (const s of p.slots) {
      if (next.locked[s.id]) continue;
      delete next.placements[s.id];
      delete next.results[s.id];
    }
    return next;
  }
  /** Ver respuestas: los slots sin resolver reciben la respuesta con 0 puntos; la última elección queda en got. */
  function reveal(p, att) {
    if (att.done && att.revealed) return att;
    const next = clone(att);
    for (const s of p.slots) {
      if (next.locked[s.id]) continue;
      const prev = next.results[s.id];
      next.results[s.id] = {
        status: 'revealed',
        points: 0,
        attempt: next.attempt,
        got: prev ? prev.got : att.placements[s.id] || null,
      };
      next.placements[s.id] = s.accept[0];
      next.locked[s.id] = true;
    }
    next.done = true;
    next.revealed = true;
    return next;
  }
  /** Reto: un solo envío y luego se revela todo lo que falte (sin reintento). */
  function challengeSubmit(p, att) {
    const r = submit(p, att);
    if (!r.verdict) return r;
    return { att: r.att.done ? r.att : reveal(p, r.att), verdict: r.verdict };
  }
  /** Se acabó el tiempo del reto: envía lo que haya, revela el resto y termina siempre el intento. */
  function timeUp(p, att) {
    if (att.done) return { att, verdict: null };
    const r = submit(p, att);
    if (r.verdict) return { att: r.att.done ? r.att : reveal(p, r.att), verdict: r.verdict };
    const verdict = {
      correct: [],
      wrong: [],
      empty: p.slots.filter((s) => !att.locked[s.id]).map((s) => s.id),
    };
    return { att: reveal(p, att), verdict };
  }
  function score(p, att, opts) {
    const o = opts || {};
    const max = 10 * p.slots.length;
    let points = 0;
    let right = 0;
    let firstTry = 0;
    for (const s of p.slots) {
      const r = att.results[s.id];
      if (!r) continue;
      points += r.points;
      if (r.status === 'correct') {
        right += 1;
        if (r.attempt === 1) firstTry += 1;
      }
    }
    const perfect =
      att.done &&
      !att.revealed &&
      firstTry === p.slots.length &&
      Object.values(att.hints).every((h) => !h);
    const bonus = perfect ? Math.round(0.2 * max) : 0;
    const timer =
      o.mode === 'challenge' &&
      att.done &&
      o.elapsedMs !== null &&
      o.elapsedMs !== undefined &&
      o.elapsedMs < budgetMs(p)
        ? Math.round(0.1 * max)
        : 0;
    return {
      points: points + bonus + timer,
      max,
      bonus,
      timer,
      perfect,
      right,
      total: p.slots.length,
      firstTry,
    };
  }

  // ---------------------------------------------------------------- pistas
  function useHint(att, slotId, mode) {
    if (att.done || att.locked[slotId] || !hintsAllowed(mode)) return att;
    const next = clone(att);
    next.hints[slotId] = Math.min(3, (next.hints[slotId] || 0) + 1);
    return next;
  }
  /** Nivel 1: resalta la frase decisiva y dice la categoría; 2: atenúa la mitad de los distractores (nunca el
   *  near-miss); 3: solo quedan la respuesta y su near-miss. */
  function hintView(p, slotId, level, seed) {
    const s = slotById(p, slotId);
    const out = { level: level || 0, cue: null, category: null, faded: [], pair: [] };
    if (!s || !level) return out;
    out.cue = s.hint_cue;
    out.category = s.category || null;
    if (level < 2) return out;
    const answer = s.accept[0];
    const others = shuffle(
      p.palette.map((t) => t.service).filter((x) => x !== answer && x !== s.near_miss),
      `${seed}|${slotId}|hint`,
    );
    if (level === 2) {
      out.faded = others.slice(0, Math.floor(others.length / 2));
      return out;
    }
    const partner = s.near_miss || others[others.length - 1];
    out.pair = [answer, partner];
    out.faded = p.palette.map((t) => t.service).filter((x) => x !== answer && x !== partner);
    return out;
  }

  // ---------------------------------------------------------------- orden aleatorio con semilla
  function hash(str) {
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return h >>> 0;
  }
  function rng(seed) {
    let a = typeof seed === 'number' ? seed >>> 0 : hash(String(seed));
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffle(arr, seed) {
    const out = arr.slice();
    const r = rng(seed);
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(r() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }
  function paletteOrder(p, seed) {
    return shuffle(
      p.palette.map((t) => t.service),
      seed,
    );
  }

  // ---------------------------------------------------------------- registro por puzzle
  const pad = (n) => String(n).padStart(2, '0');
  function localDay(d) {
    const x = d || new Date();
    return `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}`;
  }
  /** outcome {perfect, points, hints} */
  function updateRecord(rec, outcome, when) {
    const r = Object.assign(
      { attempts: 0, best: 0, last: null, last_points: 0, perfects: 0, hints: 0 },
      rec ? clone(rec) : {},
    );
    r.attempts += 1;
    r.best = Math.max(r.best, outcome.points || 0);
    r.last_points = outcome.points || 0;
    r.last = when || null;
    r.hints += outcome.hints || 0;
    if (outcome.perfect) r.perfects += 1;
    return r;
  }

  // ---------------------------------------------------------------- persistencia
  function emptyState() {
    return {
      v: VERSION,
      puzzles: {},
      open: null,
      settings: { timer: false, mode: 'practice', cloud: 'aws' },
    };
  }
  const isObj = (x) => x && typeof x === 'object' && !Array.isArray(x);
  function repair(raw) {
    const s = emptyState();
    if (isObj(raw.puzzles))
      for (const [k, v] of Object.entries(raw.puzzles)) if (isObj(v)) s.puzzles[k] = v;
    if (isObj(raw.open) && typeof raw.open.id === 'string') s.open = raw.open;
    if (isObj(raw.settings)) s.settings = Object.assign(s.settings, raw.settings);
    if (!CLOUDS.includes(s.settings.cloud)) s.settings.cloud = 'aws';
    if (!MODES.includes(s.settings.mode)) s.settings.mode = 'practice';
    return s;
  }
  /** Lee el estado guardado; un valor dañado solo reinicia esta llave y avisa (notice). */
  function loadState(storage, key) {
    let text;
    try {
      text = storage.getItem(key);
    } catch {
      return { state: emptyState(), notice: 'unavailable' };
    }
    if (text === null || text === undefined) return { state: emptyState(), notice: null };
    let raw;
    try {
      raw = JSON.parse(text);
    } catch {
      raw = undefined;
    }
    if (!isObj(raw)) {
      try {
        storage.removeItem(key);
      } catch {
        /* sin almacenamiento: el estado vive en memoria */
      }
      return { state: emptyState(), notice: 'corrupt' };
    }
    if (raw.v !== VERSION)
      return { state: emptyState(), notice: raw.v > VERSION ? 'newer' : 'corrupt' };
    return { state: repair(raw), notice: null };
  }
  function saveState(storage, key, state) {
    try {
      storage.setItem(key, JSON.stringify(state));
      return true;
    } catch {
      return false;
    }
  }
  /** Quita del estado un puzzle abierto que ya no existe. */
  function prune(state, ids) {
    const known = new Set(ids);
    const s = clone(state);
    if (s.open && !known.has(s.open.id)) s.open = null;
    return s;
  }

  // ---------------------------------------------------------------- rutas (#p=e02-aws, #cloud=gcp, &mode=challenge)
  function parseHash(hash) {
    const params = {};
    for (const part of String(hash || '')
      .replace(/^#/, '')
      .split('&')) {
      if (!part) continue;
      const i = part.indexOf('=');
      const k = i < 0 ? part : part.slice(0, i);
      let v = i < 0 ? '' : part.slice(i + 1);
      try {
        v = decodeURIComponent(v.replace(/\+/g, ' '));
      } catch {
        /* se queda el valor crudo */
      }
      params[k] = v.trim();
    }
    const route = params.p ? { view: 'puzzle', id: params.p } : { view: 'start' };
    if (CLOUDS.includes(params.cloud)) route.cloud = params.cloud;
    if (MODES.includes(params.mode)) route.mode = params.mode;
    return route;
  }
  function hashFor(route) {
    const extra = route.mode === 'challenge' ? '&mode=challenge' : '';
    if (route.view === 'puzzle') return '#p=' + encodeURIComponent(route.id) + extra;
    return route.cloud ? '#cloud=' + route.cloud + extra : '#' + extra.slice(1);
  }
  /** Puzzles de una nube, en orden de escenario. */
  function cloudPuzzles(puzzles, cloud) {
    return puzzles
      .filter((p) => p.cloud === cloud)
      .slice()
      .sort((a, b) => (a.scenario < b.scenario ? -1 : a.scenario > b.scenario ? 1 : 0));
  }
  /** El mismo escenario en otra nube (null si todavía no existe). */
  function sibling(puzzles, p, cloud) {
    return puzzles.find((q) => q.scenario === p.scenario && q.cloud === cloud) || null;
  }
  function progress(puzzles, state) {
    let played = 0;
    let perfect = 0;
    for (const p of puzzles) {
      const r = state.puzzles[p.id];
      if (r && r.attempts > 0) played += 1;
      if (r && r.perfects > 0) perfect += 1;
    }
    return { total: puzzles.length, played, perfect };
  }

  return {
    VERSION,
    MODES,
    CLOUDS,
    isDraft,
    slotPoints,
    budgetMs,
    hintsAllowed,
    timerOn,
    clock,
    formatClock,
    addElapsed,
    uses,
    remaining,
    newAttempt,
    place,
    move,
    remove,
    resetAttempt,
    check,
    submit,
    retry,
    reveal,
    challengeSubmit,
    timeUp,
    score,
    useHint,
    hintView,
    hash,
    rng,
    shuffle,
    paletteOrder,
    localDay,
    updateRecord,
    emptyState,
    loadState,
    saveState,
    prune,
    parseHash,
    hashFor,
    cloudPuzzles,
    sibling,
    progress,
  };
});
