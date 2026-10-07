import { describe, expect, it } from 'vitest';
import { BARNES_HUT_MIN_TABLES, BarnesHut, LABEL_CAP, layoutTables, persistentLabels, repelExact } from './layout';
import { classifyTables } from './model';
import { syntheticModel } from './__fixtures__/syntheticModel';

const timed = <T,>(fn: () => T): [T, number] => {
  const t0 = performance.now();
  const out = fn();
  return [out, performance.now() - t0];
};

const scatter = (n: number) => {
  const px = new Float64Array(n), pz = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const r = (5 + (i % 17)) * Math.sqrt(n / 300);
    px[i] = Math.cos(i * 2.4) * r; pz[i] = Math.sin(i * 2.4) * r;
  }
  return { px, pz };
};

describe('syntheticModel', () => {
  it('builds the requested size, the same way every time', () => {
    const a = syntheticModel(300, 600);
    expect(a.tables).toHaveLength(300);
    expect(a.relationships).toHaveLength(600);
    expect(syntheticModel(300, 600)).toEqual(a);
  });
});

describe('layoutTables', () => {
  it('lays out a 300-table, 600-relationship model quickly and deterministically', () => {
    const m = syntheticModel(300, 600);
    const roles = classifyTables(m.tables, m.relationships);
    const [first, ms] = timed(() => layoutTables(m.tables, m.relationships, roles));
    // ~90 ms cold on a laptop in Node; the ceiling only catches an accidental blow-up on slow CI.
    console.log(`layoutTables(300 tables, 600 relationships): ${ms.toFixed(0)} ms`);
    expect(ms).toBeLessThan(1500);
    expect(layoutTables(m.tables, m.relationships, roles)).toEqual(first);
    for (const p of first.values()) expect(Number.isFinite(p.x) && Number.isFinite(p.z)).toBe(true);
  });

  it('keeps fact tables nearer the centre than dimensions', () => {
    const m = syntheticModel(120, 220, 7);
    const roles = classifyTables(m.tables, m.relationships);
    const pos = layoutTables(m.tables, m.relationships, roles);
    const meanDist = (role: string) => {
      const ds = m.tables.filter((t) => roles.get(t.name) === role).map((t) => Math.hypot(pos.get(t.name)!.x, pos.get(t.name)!.z));
      return ds.reduce((a, b) => a + b, 0) / ds.length;
    };
    expect(meanDist('fact')).toBeLessThan(meanDist('dim'));
  });

  it('is deterministic on the Barnes-Hut path too', () => {
    const m = syntheticModel(BARNES_HUT_MIN_TABLES, BARNES_HUT_MIN_TABLES * 2, 3);
    const roles = classifyTables(m.tables, m.relationships);
    const [a, ms] = timed(() => layoutTables(m.tables, m.relationships, roles));
    console.log(`layoutTables(${BARNES_HUT_MIN_TABLES} tables, Barnes-Hut): ${ms.toFixed(0)} ms`);
    expect(layoutTables(m.tables, m.relationships, roles)).toEqual(a);
  });

  it('handles empty and single-table models', () => {
    expect(layoutTables([], [], new Map()).size).toBe(0);
    const one = syntheticModel(1, 0).tables;
    expect(layoutTables(one, [], new Map()).get(one[0].name)).toEqual({ x: 0, z: 0 });
  });
});

describe('BarnesHut', () => {
  it('approximates the exact repulsion closely', () => {
    for (const n of [300, 1000]) {
      const { px, pz } = scatter(n);
      const ex = [new Float64Array(n), new Float64Array(n)];
      const bh = [new Float64Array(n), new Float64Array(n)];
      repelExact(n, px, pz, ex[0], ex[1]);
      new BarnesHut(n).apply(px, pz, bh[0], bh[1]);
      let err = 0, mag = 0;
      for (let i = 0; i < n; i++) {
        err += Math.hypot(ex[0][i] - bh[0][i], ex[1][i] - bh[1][i]);
        mag += Math.hypot(ex[0][i], ex[1][i]);
      }
      expect(err / mag).toBeLessThan(0.08);
    }
  });

  it('copes with tables stacked on the same spot', () => {
    const n = 64;
    const px = new Float64Array(n), pz = new Float64Array(n);
    const fx = new Float64Array(n), fz = new Float64Array(n);
    new BarnesHut(n).apply(px, pz, fx, fz);
    for (let i = 0; i < n; i++) expect(Number.isFinite(fx[i]) && Number.isFinite(fz[i])).toBe(true);
  });

  it('is faster than every-pair repulsion on large models', () => {
    const n = 2000;
    const { px, pz } = scatter(n);
    const fx = new Float64Array(n), fz = new Float64Array(n);
    const tree = new BarnesHut(n);
    tree.apply(px, pz, fx, fz); repelExact(n, px, pz, fx, fz); // warm up
    const [, bh] = timed(() => { for (let k = 0; k < 5; k++) tree.apply(px, pz, fx, fz); });
    const [, exact] = timed(() => { for (let k = 0; k < 5; k++) repelExact(n, px, pz, fx, fz); });
    console.log(`repulsion, 2000 tables: exact ${(exact / 5).toFixed(1)} ms/iter, Barnes-Hut ${(bh / 5).toFixed(1)} ms/iter`);
    expect(bh).toBeLessThan(exact);
  });
});

describe('persistentLabels', () => {
  it('labels every table on small maps', () => {
    const m = syntheticModel(20, 30);
    expect(persistentLabels(m.tables, m.relationships, classifyTables(m.tables, m.relationships)).size).toBe(20);
  });

  it('caps labels on large maps, most connected facts first, then the date table', () => {
    const m = syntheticModel(300, 600);
    const roles = classifyTables(m.tables, m.relationships);
    const shown = persistentLabels(m.tables, m.relationships, roles);
    expect(shown.size).toBe(LABEL_CAP);
    expect([...shown].every((t) => roles.get(t) === 'fact')).toBe(true);

    const fewFacts = syntheticModel(60, 90);
    const fewRoles = classifyTables(fewFacts.tables, fewFacts.relationships);
    const labels = persistentLabels(fewFacts.tables, fewFacts.relationships, fewRoles);
    expect(labels.has('Date')).toBe(true);
    expect([...labels].every((t) => fewRoles.get(t) === 'fact' || fewRoles.get(t) === 'date')).toBe(true);
  });
});
