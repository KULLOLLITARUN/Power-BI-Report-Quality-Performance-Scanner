// Floor-plan layout for the 3D model map (lib/scene.ts). Pure and deterministic:
// the same tables, relationships and roles always give the same positions.
import type { RelationshipInfo, TableInfo } from '../types';
import type { TableRole } from './model';

/** Repulsion between two tables: force = REPULSION / distance². */
const REPULSION = 7;
/** From this many tables, repulsion uses a Barnes-Hut quadtree instead of every pair.
 * Below it the exact O(n²) loop is faster in V8 (see src/lib/layout.test.ts). */
export const BARNES_HUT_MIN_TABLES = 800;
/** Barnes-Hut opening angle: a cell narrower than THETA × its distance pushes as one body. */
const THETA = 0.7;
/** Quadtree depth limit; tables that still share a cell there are chained in one leaf. */
const MAX_DEPTH = 20;
/** Above this many tables, only the most connected fact and date tables keep a label at rest. */
export const DENSE_TABLES = 28;
/** On a dense map, at most this many table labels show without hover or focus. */
export const LABEL_CAP = 16;

export function boxSize(t: TableInfo, role: TableRole) {
  const c = Math.min(Math.max(t.column_count || 0, 1), 60);
  const w = role === 'fact' ? 1.5 + c * 0.032 : 0.9 + c * 0.022;
  return { w, d: w * (role === 'fact' ? 0.62 : 0.72), h: 0.35 + Math.log2(1 + c) * 0.24 };
}

/** Every-pair repulsion, O(n²). Adds to fx/fz. */
export function repelExact(n: number, px: Float64Array, pz: Float64Array, fx: Float64Array, fz: Float64Array) {
  for (let i = 0; i < n; i++) {
    const xi = px[i], zi = pz[i];
    let ax = 0, az = 0;
    for (let j = i + 1; j < n; j++) {
      let dx = xi - px[j], dz = zi - pz[j];
      let d2 = dx * dx + dz * dz;
      if (d2 < 1e-4) { dx = 0.01 * (i - j); dz = 0.01; d2 = 1e-4; }
      const s = REPULSION / (d2 * Math.sqrt(d2));
      const gx = dx * s, gz = dz * s;
      ax += gx; az += gz;
      fx[j] -= gx; fz[j] -= gz;
    }
    fx[i] += ax; fz[i] += az;
  }
}

/** Barnes-Hut repulsion, O(n log n): a far-away group of tables pushes as one body at its
 * centre of mass. The tree is rebuilt from the positions in index order, so the result is
 * deterministic. Buffers are reused across iterations of one layout. */
export class BarnesHut {
  private cap: number;
  private cx!: Float64Array; private cz!: Float64Array; private hw!: Float64Array;
  private mass!: Float64Array; private mx!: Float64Array; private mz!: Float64Array;
  /** Index of the first of a node's four children (allocated together), or -1 for a leaf. */
  private first!: Int32Array;
  /** A leaf's body, or the head of its chain at MAX_DEPTH; -1 when empty. */
  private body!: Int32Array;
  private depth!: Int32Array;
  private next: Int32Array;
  private stack = new Int32Array(3 * MAX_DEPTH + 8);
  private count = 0;

  constructor(private n: number) {
    this.cap = 0;
    this.next = new Int32Array(n);
    this.alloc(8 * n + 64);
  }

  private alloc(cap: number) {
    const f64 = (a: Float64Array | undefined) => { const b = new Float64Array(cap); if (a) b.set(a.subarray(0, this.cap)); return b; };
    const i32 = (a: Int32Array | undefined) => { const b = new Int32Array(cap); if (a) b.set(a.subarray(0, this.cap)); return b; };
    this.cx = f64(this.cx); this.cz = f64(this.cz); this.hw = f64(this.hw);
    this.mass = f64(this.mass); this.mx = f64(this.mx); this.mz = f64(this.mz);
    this.first = i32(this.first); this.body = i32(this.body); this.depth = i32(this.depth);
    this.cap = cap;
  }

  private node(x: number, z: number, h: number, dp: number) {
    const k = this.count++;
    this.cx[k] = x; this.cz[k] = z; this.hw[k] = h; this.depth[k] = dp;
    this.mass[k] = 0; this.mx[k] = 0; this.mz[k] = 0; this.first[k] = -1; this.body[k] = -1;
    return k;
  }

  private split(k: number) {
    if (this.count + 4 > this.cap) this.alloc(this.cap * 2);
    const h = this.hw[k] / 2, x = this.cx[k], z = this.cz[k], dp = this.depth[k] + 1;
    this.first[k] = this.count;
    this.node(x - h, z - h, h, dp); this.node(x + h, z - h, h, dp);
    this.node(x - h, z + h, h, dp); this.node(x + h, z + h, h, dp);
  }

  private quadrant(k: number, x: number, z: number) {
    return this.first[k] + (x >= this.cx[k] ? 1 : 0) + (z >= this.cz[k] ? 2 : 0);
  }

  private build(px: Float64Array, pz: Float64Array) {
    const n = this.n;
    let minX = Infinity, minZ = Infinity, maxX = -Infinity, maxZ = -Infinity;
    for (let i = 0; i < n; i++) {
      const x = px[i], z = pz[i];
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
    }
    this.count = 0;
    this.node((minX + maxX) / 2, (minZ + maxZ) / 2, Math.max(maxX - minX, maxZ - minZ, 1e-3) / 2 + 1e-6, 0);
    // Read arrays through `this`: split() may reallocate them.
    const next = this.next;
    for (let i = 0; i < n; i++) {
      const x = px[i], z = pz[i];
      next[i] = -1;
      let k = 0;
      for (;;) {
        this.mass[k] += 1; this.mx[k] += x; this.mz[k] += z;
        if (this.first[k] >= 0) { k = this.quadrant(k, x, z); continue; }
        if (this.body[k] < 0) { this.body[k] = i; break; }
        if (this.depth[k] >= MAX_DEPTH) { next[i] = this.body[k]; this.body[k] = i; break; }
        // Occupied leaf: move its body one level down, then keep descending with i.
        const b = this.body[k];
        this.body[k] = -1;
        this.split(k);
        const c = this.quadrant(k, px[b], pz[b]);
        this.body[c] = b; this.mass[c] = 1; this.mx[c] = px[b]; this.mz[c] = pz[b];
        k = this.quadrant(k, x, z);
      }
    }
  }

  /** Adds each table's repulsion to fx/fz. */
  apply(px: Float64Array, pz: Float64Array, fx: Float64Array, fz: Float64Array) {
    this.build(px, pz);
    const { mass, mx, mz, first, body, hw, next, stack } = this;
    const theta2 = THETA * THETA;
    for (let i = 0; i < this.n; i++) {
      const xi = px[i], zi = pz[i];
      let ax = 0, az = 0, sp = 0;
      stack[sp++] = 0;
      while (sp) {
        const k = stack[--sp];
        const m = mass[k];
        if (m === 0) continue;
        if (first[k] < 0) {
          for (let j = body[k]; j >= 0; j = next[j]) {
            if (j === i) continue;
            let dx = xi - px[j], dz = zi - pz[j];
            let d2 = dx * dx + dz * dz;
            if (d2 < 1e-4) { dx = 0.01 * (i - j); dz = 0.01; d2 = 1e-4; }
            const s = REPULSION / (d2 * Math.sqrt(d2));
            ax += dx * s; az += dz * s;
          }
          continue;
        }
        const dx = xi - mx[k] / m, dz = zi - mz[k] / m;
        const d2 = dx * dx + dz * dz;
        const w = 2 * hw[k];
        if (w * w < theta2 * d2) {
          const s = (REPULSION * m) / (d2 * Math.sqrt(d2));
          ax += dx * s; az += dz * s;
          continue;
        }
        const c = first[k];
        stack[sp++] = c; stack[sp++] = c + 1; stack[sp++] = c + 2; stack[sp++] = c + 3;
      }
      fx[i] += ax; fz[i] += az;
    }
  }
}

/** Deterministic force layout on the floor plane: facts pulled to the centre, dimensions around them. */
export function layoutTables(tables: TableInfo[], rels: RelationshipInfo[], roles: Map<string, TableRole>) {
  const names = tables.map((t) => t.name);
  const n = names.length;
  const idx = new Map(names.map((nm, i) => [nm, i]));
  const factIndex = new Map(names.filter((nm) => roles.get(nm) === 'fact').map((nm, i) => [nm, i]));
  const factCount = factIndex.size;
  const px = new Float64Array(n), pz = new Float64Array(n);
  const ring = 5 + Math.sqrt(n) * 1.1;
  names.forEach((nm, i) => {
    const fi = factIndex.get(nm);
    if (fi !== undefined) {
      const a = (fi / Math.max(1, factCount)) * Math.PI * 2;
      const r = factCount > 1 ? 1.4 * Math.sqrt(factCount) : 0;
      px[i] = Math.cos(a) * r; pz[i] = Math.sin(a) * r;
    } else {
      const a = i * 2.399963; // golden angle
      const r = ring * (0.7 + 0.3 * ((i * 7919) % 13) / 13);
      px[i] = Math.cos(a) * r; pz[i] = Math.sin(a) * r;
    }
  });
  const edges: [number, number][] = [];
  const seen = new Set<string>();
  for (const r of rels) {
    const a = idx.get(r.from_table), b = idx.get(r.to_table);
    if (a === undefined || b === undefined || a === b) continue;
    const k = a < b ? `${a}:${b}` : `${b}:${a}`;
    if (!seen.has(k)) { seen.add(k); edges.push([a, b]); }
  }
  const degree = new Float64Array(n);
  edges.forEach(([a, b]) => { degree[a]++; degree[b]++; });
  const gravity = new Float64Array(n);
  for (let i = 0; i < n; i++) gravity[i] = roles.get(names[i]) === 'fact' ? 0.07 : degree[i] === 0 ? 0.008 : 0.016;
  const iters = n > 150 ? 160 : 360;
  const fx = new Float64Array(n), fz = new Float64Array(n);
  const tree = n >= BARNES_HUT_MIN_TABLES ? new BarnesHut(n) : null;
  for (let it = 0; it < iters; it++) {
    const temp = 1 - it / iters;
    fx.fill(0); fz.fill(0);
    if (tree) tree.apply(px, pz, fx, fz);
    else repelExact(n, px, pz, fx, fz);
    for (const [a, b] of edges) {
      const dx = px[b] - px[a], dz = pz[b] - pz[a];
      const d = Math.max(0.01, Math.sqrt(dx * dx + dz * dz));
      const f = (d - 4.4) * 0.09 / d;
      fx[a] += dx * f; fz[a] += dz * f;
      fx[b] -= dx * f; fz[b] -= dz * f;
    }
    const step = 0.08 + 0.6 * temp;
    for (let i = 0; i < n; i++) {
      fx[i] -= px[i] * gravity[i]; fz[i] -= pz[i] * gravity[i];
      const m = Math.sqrt(fx[i] * fx[i] + fz[i] * fz[i]);
      const s = m > step ? step / m : 1;
      px[i] += fx[i] * s; pz[i] += fz[i] * s;
    }
  }
  // Resolve overlaps between footprints
  const radius = tables.map((t) => { const s = boxSize(t, roles.get(t.name) ?? 'dim'); return Math.max(s.w, s.d) / 2; });
  for (let pass = 0; pass < 6; pass++) {
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const minD = radius[i] + radius[j] + 0.9;
        const dx = px[j] - px[i], dz = pz[j] - pz[i];
        const d2 = dx * dx + dz * dz;
        if (d2 >= minD * minD) continue;
        const d = Math.sqrt(d2) || 0.01;
        const push = (minD - d) / 2;
        px[i] -= (dx / d) * push; pz[i] -= (dz / d) * push;
        px[j] += (dx / d) * push; pz[j] += (dz / d) * push;
      }
    }
  }
  let cx = 0, cz = 0;
  for (let i = 0; i < n; i++) { cx += px[i]; cz += pz[i]; }
  cx /= Math.max(1, n); cz /= Math.max(1, n);
  return new Map(names.map((nm, i) => [nm, { x: px[i] - cx, z: pz[i] - cz }]));
}

/** Tables whose label shows without hover or focus. Small maps label everything; dense maps
 * keep the LABEL_CAP most connected fact tables, then date tables, ties by name. */
export function persistentLabels(tables: TableInfo[], rels: RelationshipInfo[], roles: Map<string, TableRole>): Set<string> {
  if (tables.length <= DENSE_TABLES) return new Set(tables.map((t) => t.name));
  const degree = new Map<string, number>();
  for (const r of rels) {
    degree.set(r.from_table, (degree.get(r.from_table) ?? 0) + 1);
    degree.set(r.to_table, (degree.get(r.to_table) ?? 0) + 1);
  }
  const rank = (role: TableRole | undefined) => (role === 'fact' ? 0 : role === 'date' ? 1 : 2);
  return new Set(tables
    .filter((t) => rank(roles.get(t.name)) < 2)
    .sort((a, b) => rank(roles.get(a.name)) - rank(roles.get(b.name))
      || (degree.get(b.name) ?? 0) - (degree.get(a.name) ?? 0)
      || a.name.localeCompare(b.name))
    .slice(0, LABEL_CAP)
    .map((t) => t.name));
}
