// Pruebas de app/render.js: geometría igual a tools/build.py, zonas encima de las subredes, iconos sin recolorear,
// texto alternativo y avisos de autoría sobre los puzzles reales. Correr: node --test tests/
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const R = require(join(ROOT, 'app', 'render.js'));
const PUZZLES = readdirSync(join(ROOT, 'puzzles'))
  .filter((f) => f.endsWith('.json'))
  .map((f) => JSON.parse(readFileSync(join(ROOT, 'puzzles', f), 'utf8')));
// Las aserciones de geometría y texto usan el piloto: el primer puzzle de AWS cambia al agregar escenarios.
const AWS = () => PUZZLES.find((p) => p.id === 'e02-aws');

describe('geometría', () => {
  test('viewBox = cols x 120 por rows x 112, y el svg se ajusta a su contenedor', () => {
    const svg = R.render(AWS(), {});
    assert.match(svg, /viewBox="0 0 1080 560"/);
    assert.match(svg, /width="100%"/);
  });
  test('la caja de un slot coincide con NODE_BOX de build.py (cx-54, top, cx+54, top+104)', () => {
    const s1 = R.layout(AWS()).items.s1;
    assert.deepEqual([s1.cx, s1.top, s1.box], [486, 280, [432, 280, 540, 384]]);
  });
  test('las zonas de toque son fracciones del mismo viewBox que layout (el lienzo toma L.w / L.h)', () => {
    for (const p of PUZZLES) {
      const L = R.layout(p);
      assert.match(R.render(p, {}), new RegExp(`viewBox="0 0 ${L.w} ${L.h}"`), p.id);
      const rects = R.slotRects(p);
      for (const s of p.slots) {
        const r = rects[s.id];
        const box = L.items[s.id].box;
        assert.ok(Math.abs(r.x * L.w - box[0]) < 1e-6 && Math.abs(r.y * L.h - box[1]) < 1e-6, s.id);
        assert.ok(r.x >= 0 && r.y >= 0 && r.x + r.w <= 1 && r.y + r.h <= 1, `${p.id} ${s.id}`);
      }
    }
  });
  test('las zonas (grupos que cruzan) se dibujan después de las subredes', () => {
    const order = R.layout(AWS()).groups.map((g) => g.id);
    assert.ok(order.indexOf('g-zone-a') > order.indexOf('g-priv'));
    assert.ok(order.indexOf('g-region') < order.indexOf('g-net'));
  });
  test('cada tipo de grupo del esquema tiene estilo', () => {
    const schema = JSON.parse(readFileSync(join(ROOT, 'schema', 'puzzle.schema.json'), 'utf8'));
    for (const k of schema.$defs.group.properties.kind.enum) assert.ok(R.GROUP_STYLE[k], k);
  });
});

describe('dibujo', () => {
  test('licencia: los <use> de iconos no llevan fill ni filter', () => {
    for (const p of PUZZLES) {
      const all = Object.fromEntries(p.slots.map((s) => [s.id, s.accept[0]]));
      const svg = R.render(p, {
        placements: all,
        reveal: true,
        groupIcons: ['vpc', 'region', 'azure-vnet'],
      });
      for (const use of svg.match(/<use [^>]*>/g))
        assert.doesNotMatch(use, /\b(fill|filter|style)=/, p.id);
    }
  });
  test('veredictos: correcto, incorrecto tachado y vacío', () => {
    const p = AWS();
    const svg = R.render(p, {
      placements: { s1: 'aws-ec2', s2: 'aws-launch-template' },
      results: { s1: { status: 'correct' }, s2: { status: 'wrong' }, s3: { status: 'empty' } },
      text: { empty: 'Vacío' },
    });
    assert.match(svg, /class="gm-slot filled v-correct" data-slot="s1"/);
    assert.match(svg, /class="gm-slot filled v-wrong" data-slot="s2"/);
    assert.match(svg, />Vacío</);
  });
  test('texto alternativo en orden de lectura con pasos', () => {
    const lines = R.describe(AWS(), {});
    assert.ok(lines.includes('Compradores to Internet, step 1, compra en tienda.mx'));
  });
});

describe('avisos de autoría en los puzzles reales', () => {
  test('ninguna flecha cruza iconos, va en diagonal o cruza otra flecha', () => {
    for (const p of PUZZLES) assert.deepEqual(R.lint(p), [], p.id);
  });
  test('las cuatro nubes de cada escenario comparten la misma geometría', () => {
    const geo = (p) =>
      JSON.stringify([
        p.layout,
        p.groups.map((g) => g.cell),
        p.slots.map((s) => s.cell),
        p.edges.map((e) => [e.from, e.to]),
      ]);
    for (const sc of new Set(PUZZLES.map((p) => p.scenario))) {
      const same = PUZZLES.filter((p) => p.scenario === sc);
      assert.equal(same.length, 4, sc);
      assert.equal(new Set(same.map(geo)).size, 1, sc);
    }
  });
});
