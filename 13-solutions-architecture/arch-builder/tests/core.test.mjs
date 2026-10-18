// Pruebas de app/core.js (lógica pura del juego). Origen: qa/unit/game-core.test.mjs de studykit, sin Leitner,
// rachas ni tipos de negocio. Correr: node --test tests/
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const K = require(join(ROOT, 'app', 'core.js'));

// 4 slots: s3 y s4 aceptan el mismo servicio (uses 2), con near-misses y distractores.
const P = () => ({
  id: 'e99-aws',
  scenario: 'e99',
  cloud: 'aws',
  slots: [
    { id: 's1', number: 1, accept: ['aws-ec2'], near_miss: 'aws-lambda', hint_cue: 'parcha' },
    { id: 's2', number: 2, accept: ['aws-alb'], near_miss: 'aws-nlb', hint_cue: 'ruta' },
    { id: 's3', number: 3, accept: ['aws-nat'], near_miss: 'aws-igw', hint_cue: 'salida' },
    { id: 's4', number: 4, accept: ['aws-nat'], near_miss: null, hint_cue: 'otra zona' },
  ],
  palette: [
    { service: 'aws-ec2' },
    { service: 'aws-alb' },
    { service: 'aws-nat', uses: 2 },
    { service: 'aws-lambda', role: 'near-miss' },
    { service: 'aws-nlb', role: 'near-miss' },
    { service: 'aws-igw', role: 'near-miss' },
    { service: 'aws-kms', role: 'distractor' },
  ],
});
const ANSWERS = { s1: 'aws-ec2', s2: 'aws-alb', s3: 'aws-nat', s4: 'aws-nat' };
const fill = (p, att, map) =>
  Object.entries(map).reduce((a, [s, v]) => K.place(p, a, s, v).att, att);
const seeded = (seed) => {
  let x = seed >>> 0;
  return () => {
    x = (x * 1664525 + 1013904223) >>> 0;
    return x / 2 ** 32;
  };
};

describe('puntos por slot', () => {
  test('primer envío, reintentos, pistas y mínimo de 2', () => {
    const cases = [
      [1, 0, 10],
      [2, 0, 5],
      [3, 0, 2],
      [4, 0, 2],
      [1, 1, 5],
      [1, 2, 2],
      [2, 1, 2],
    ];
    for (const [attempt, hints, pts] of cases) assert.equal(K.slotPoints(attempt, hints), pts);
  });
  test('propiedad: entre 2 y 10, y más pistas o intentos nunca suben los puntos', () => {
    for (let a = 1; a <= 6; a++)
      for (let h = 0; h <= 3; h++) {
        const v = K.slotPoints(a, h);
        assert.ok(v >= 2 && v <= 10);
        assert.ok(K.slotPoints(a + 1, h) <= v);
        assert.ok(K.slotPoints(a, h + 1) <= v);
      }
  });
});

describe('colocar fichas', () => {
  test('poner, reemplazar (la anterior regresa), quitar y mover entre slots', () => {
    const p = P();
    let r = K.place(p, K.newAttempt(), 's1', 'aws-lambda');
    assert.ok(r.ok);
    r = K.place(p, r.att, 's1', 'aws-ec2');
    assert.equal(r.returned, 'aws-lambda');
    const moved = K.move(p, r.att, 's1', 's2');
    assert.deepEqual(moved.att.placements, { s2: 'aws-ec2' });
    assert.deepEqual(K.remove(moved.att, 's2').placements, {});
  });
  test('uses: una ficha de un uso no se pone dos veces; la de dos usos sí', () => {
    const p = P();
    const a = K.place(p, K.newAttempt(), 's1', 'aws-kms').att;
    assert.equal(K.place(p, a, 's2', 'aws-kms').reason, 'used');
    const b = K.place(p, K.place(p, a, 's3', 'aws-nat').att, 's4', 'aws-nat');
    assert.ok(b.ok);
    assert.equal(K.remaining(p, b.att.placements)['aws-nat'], 0);
  });
  test('invariante: fichas en la paleta más fichas puestas = usos totales (operaciones al azar)', () => {
    const p = P();
    const total = Object.values(K.uses(p)).reduce((a, b) => a + b, 0);
    const rnd = seeded(7);
    let att = K.newAttempt();
    const sids = p.slots.map((s) => s.id);
    const svcs = p.palette.map((t) => t.service);
    for (let i = 0; i < 400; i++) {
      const op = Math.floor(rnd() * 3);
      const s = sids[Math.floor(rnd() * sids.length)];
      if (op === 0) att = K.place(p, att, s, svcs[Math.floor(rnd() * svcs.length)]).att;
      else if (op === 1) att = K.remove(att, s);
      else att = K.move(p, att, s, sids[Math.floor(rnd() * sids.length)]).att;
      const left = Object.values(K.remaining(p, att.placements)).reduce((a, b) => a + b, 0);
      assert.equal(left + Object.keys(att.placements).length, total);
      assert.ok(Object.values(K.remaining(p, att.placements)).every((n) => n >= 0));
    }
  });
  test('slot o servicio desconocido se rechaza; vaciar respeta los bloqueados', () => {
    const p = P();
    assert.equal(K.place(p, K.newAttempt(), 's9', 'aws-ec2').reason, 'slot');
    assert.equal(K.place(p, K.newAttempt(), 's1', 'azure-vm').reason, 'service');
    const done = K.submit(p, fill(p, K.newAttempt(), { s1: 'aws-ec2', s2: 'aws-nlb' })).att;
    assert.deepEqual(K.resetAttempt(done).placements, { s1: 'aws-ec2' });
    assert.equal(K.place(p, done, 's1', 'aws-lambda').reason, 'locked');
  });
});

describe('enviar, reintentar, revelar y puntaje', () => {
  test('perfecto al primer intento: 10 por slot más 20 % de bono', () => {
    const p = P();
    const { att } = K.submit(p, fill(p, K.newAttempt(), ANSWERS));
    const sc = K.score(p, att);
    assert.equal(att.done, true);
    assert.deepEqual([sc.points, sc.max, sc.bonus, sc.perfect], [48, 40, 8, true]);
  });
  test('el reintento bloquea los correctos, limpia el resto y paga 5', () => {
    const p = P();
    const first = K.submit(
      p,
      fill(p, K.newAttempt(), { s1: 'aws-ec2', s2: 'aws-nlb', s3: 'aws-nat' }),
    );
    assert.deepEqual(first.verdict, { correct: ['s1', 's3'], wrong: ['s2'], empty: ['s4'] });
    const again = K.retry(p, first.att);
    assert.deepEqual(again.placements, { s1: 'aws-ec2', s3: 'aws-nat' });
    const done = K.submit(p, fill(p, again, { s2: 'aws-alb', s4: 'aws-nat' })).att;
    const sc = K.score(p, done);
    assert.deepEqual([sc.points, sc.perfect, sc.firstTry], [30, false, 2]);
  });
  test('revelar termina el intento con 0 en los no resueltos y recuerda la elección', () => {
    const p = P();
    const first = K.submit(p, fill(p, K.newAttempt(), { s1: 'aws-lambda' })).att;
    const r = K.reveal(p, first);
    assert.equal(r.done && r.revealed, true);
    assert.equal(r.results.s1.got, 'aws-lambda');
    assert.equal(r.placements.s1, 'aws-ec2');
    assert.equal(K.score(p, r).points, 0);
  });
  test('reto: un solo envío y luego se revela; el tiempo agotado también termina', () => {
    const p = P();
    const c = K.challengeSubmit(p, fill(p, K.newAttempt(), { s1: 'aws-ec2' }));
    assert.equal(c.att.done && c.att.revealed, true);
    const tu = K.timeUp(p, K.newAttempt());
    assert.deepEqual(tu.verdict.empty, ['s1', 's2', 's3', 's4']);
    assert.equal(tu.att.done, true);
    assert.equal(K.submit(p, K.newAttempt()).verdict, null);
  });
  test('las pistas reducen el slot y quitan el bono; el bono de tiempo solo en reto', () => {
    const p = P();
    const hinted = K.useHint(fill(p, K.newAttempt(), ANSWERS), 's1', 'practice');
    const sc = K.score(p, K.submit(p, hinted).att);
    assert.deepEqual([sc.points, sc.perfect], [35, false]);
    assert.equal(K.useHint(K.newAttempt(), 's1', 'challenge').hints.s1, undefined);
    const done = K.submit(p, fill(p, K.newAttempt(), ANSWERS)).att;
    assert.equal(K.score(p, done, { mode: 'challenge', elapsedMs: 1000 }).timer, 4);
    assert.equal(K.score(p, done, { mode: 'practice', elapsedMs: 1000 }).timer, 0);
    assert.equal(K.score(p, done, { mode: 'challenge', elapsedMs: K.budgetMs(p) + 1 }).timer, 0);
  });
});

describe('pistas y orden de la paleta', () => {
  test('nivel 1 da la frase y la categoría, 2 atenúa la mitad sin tocar el near-miss, 3 deja dos', () => {
    const p = P();
    const h1 = K.hintView(p, 's2', 1, 'x');
    assert.equal(h1.cue, 'ruta');
    const h2 = K.hintView(p, 's2', 2, 'x');
    assert.ok(!h2.faded.includes('aws-nlb') && !h2.faded.includes('aws-alb'));
    assert.equal(h2.faded.length, 2);
    assert.deepEqual(K.hintView(p, 's2', 3, 'x').pair, ['aws-alb', 'aws-nlb']);
  });
  test('el orden es determinista por semilla, cambia entre semillas y conserva todas las fichas', () => {
    const p = P();
    assert.deepEqual(K.paletteOrder(p, 'a'), K.paletteOrder(p, 'a'));
    const orders = new Set(Array.from({ length: 30 }, (_, i) => K.paletteOrder(p, 's' + i).join()));
    assert.ok(orders.size > 10);
    assert.deepEqual(K.paletteOrder(p, 'z').slice().sort(), p.palette.map((t) => t.service).sort());
  });
});

describe('persistencia y rutas', () => {
  const mem = (init) => {
    const m = new Map(Object.entries(init || {}));
    return {
      getItem: (k) => (m.has(k) ? m.get(k) : null),
      setItem: (k, v) => m.set(k, v),
      removeItem: (k) => m.delete(k),
      m,
    };
  };
  test('ida y vuelta, JSON dañado y versión nueva', () => {
    const s = mem();
    const st = K.emptyState();
    st.puzzles['e02-aws'] = K.updateRecord(null, { perfect: true, points: 60, hints: 0 }, 't');
    assert.ok(K.saveState(s, 'k', st));
    assert.deepEqual(K.loadState(s, 'k').state.puzzles['e02-aws'].best, 60);
    assert.equal(K.loadState(mem({ k: '{oops' }), 'k').notice, 'corrupt');
    assert.equal(K.loadState(mem({ k: '{"v":9}' }), 'k').notice, 'newer');
    const bad = {
      getItem() {
        throw new Error('privado');
      },
    };
    assert.equal(K.loadState(bad, 'k').notice, 'unavailable');
  });
  test('la nube y el modo guardados se reparan si traen valores desconocidos', () => {
    const s = mem({ k: JSON.stringify({ v: 1, settings: { cloud: 'ibm', mode: 'x' } }) });
    const st = K.loadState(s, 'k').state;
    assert.deepEqual([st.settings.cloud, st.settings.mode], ['aws', 'practice']);
    assert.equal(K.prune(Object.assign(st, { open: { id: 'e77-aws' } }), ['e02-aws']).open, null);
  });
  test('#p=, #cloud= y &mode=', () => {
    assert.deepEqual(K.parseHash('#p=e02-gcp'), { view: 'puzzle', id: 'e02-gcp' });
    assert.deepEqual(K.parseHash('#cloud=oci&mode=challenge'), {
      view: 'start',
      cloud: 'oci',
      mode: 'challenge',
    });
    assert.deepEqual(K.parseHash('#cloud=ibm&mode=x'), { view: 'start' });
    assert.equal(
      K.hashFor({ view: 'puzzle', id: 'e02-aws', mode: 'challenge' }),
      '#p=e02-aws&mode=challenge',
    );
    assert.equal(K.hashFor({ view: 'start', cloud: 'gcp' }), '#cloud=gcp');
  });
  test('puzzles por nube en orden de escenario y el mismo escenario en otra nube', () => {
    const list = ['e03-aws', 'e02-gcp', 'e02-aws', 'e01-aws'].map((id) => ({
      id,
      scenario: id.slice(0, 3),
      cloud: id.slice(4),
    }));
    assert.deepEqual(
      K.cloudPuzzles(list, 'aws').map((p) => p.id),
      ['e01-aws', 'e02-aws', 'e03-aws'],
    );
    assert.equal(K.sibling(list, list[2], 'gcp').id, 'e02-gcp');
    assert.equal(K.sibling(list, list[0], 'gcp'), null);
  });
  test('los cuatro puzzles piloto resueltos con sus respuestas dan perfecto', () => {
    for (const cloud of K.CLOUDS) {
      const p = JSON.parse(readFileSync(join(ROOT, 'puzzles', `e02-${cloud}.json`), 'utf8'));
      const answers = Object.fromEntries(p.slots.map((s) => [s.id, s.accept[0]]));
      const { att } = K.submit(p, fill(p, K.newAttempt(), answers));
      assert.equal(K.score(p, att).perfect, true, cloud);
    }
  });
});
