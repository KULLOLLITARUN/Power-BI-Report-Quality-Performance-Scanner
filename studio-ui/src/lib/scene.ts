// The 3D "data city": tables stand on a floor as boxes (footprint and height
// grow with column count; colour = role), relationships are arcs between box
// tops, and dots on the arcs travel the way filters propagate (one side to many
// side). An optional report layer floats a page above the model with a thread
// from every visual down to each table it reads.
import * as THREE from 'three';
import type { PageInfo, RelationshipInfo, TableInfo } from '../types';
import { cardinalityLabel, isBidirectional, isManySide, relKey, type TableRole } from './model';
import { SEV, type Severity } from './severity';
import { anime, prefersReducedMotion } from './motion';

export interface ReportLayer {
  page: PageInfo;
  /** For each visual (same order as page.visuals), the model tables it reads. */
  visualTables: string[][];
  /** Indexes of visuals beyond the per-page limit, in reading order. */
  overLimit: Set<number>;
}

export interface SceneData {
  tables: TableInfo[];
  relationships: RelationshipInfo[];
  roles: Map<string, TableRole>;
  tableSeverity: Map<string, Severity>;
  relSeverity: Map<string, Severity>;
  findingCounts: Map<string, number>;
  report?: ReportLayer | null;
}

export interface SceneCallbacks {
  onTableClick?: (name: string | null) => void;
  onVisualClick?: (index: number | null) => void;
}

interface Node {
  t: TableInfo; role: TableRole; i: number;
  mesh: THREE.Mesh<THREE.BoxGeometry, THREE.MeshStandardMaterial>;
  edges: THREE.LineSegments<THREE.EdgesGeometry, THREE.LineBasicMaterial>;
  flag: THREE.Mesh<THREE.OctahedronGeometry, THREE.MeshStandardMaterial> | null;
  label: HTMLDivElement;
  x: number; z: number; w: number; h: number; d: number;
  s: number; L: { v: number };
}

interface Link {
  r: RelationshipInfo; key: string;
  line: THREE.Line<THREE.BufferGeometry, THREE.LineBasicMaterial | THREE.LineDashedMaterial>;
  curve: THREE.QuadraticBezierCurve3;
  sev: Severity | null;
  inFocus: boolean;
  cards: [HTMLDivElement, number][];
}

interface Tile {
  i: number;
  mesh: THREE.Mesh<THREE.BoxGeometry, THREE.MeshStandardMaterial>;
  edges: THREE.LineSegments<THREE.EdgesGeometry, THREE.LineBasicMaterial>;
  threads: { table: string; line: THREE.Line<THREE.BufferGeometry, THREE.LineBasicMaterial> }[];
  slicer: boolean; over: boolean; hidden: boolean;
}

const GRID_Y = 0.003;

/** Deterministic force layout on the floor plane: facts pulled to the centre, dimensions around them. */
export function layoutTables(tables: TableInfo[], rels: RelationshipInfo[], roles: Map<string, TableRole>) {
  const names = tables.map((t) => t.name);
  const n = names.length;
  const idx = new Map(names.map((nm, i) => [nm, i]));
  const facts = names.filter((nm) => roles.get(nm) === 'fact');
  const px = new Float64Array(n), pz = new Float64Array(n);
  const ring = 5 + Math.sqrt(n) * 1.1;
  names.forEach((nm, i) => {
    const fi = facts.indexOf(nm);
    if (fi >= 0) {
      const a = (fi / Math.max(1, facts.length)) * Math.PI * 2;
      const r = facts.length > 1 ? 1.4 * Math.sqrt(facts.length) : 0;
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
  const iters = n > 150 ? 160 : 360;
  const fx = new Float64Array(n), fz = new Float64Array(n);
  for (let it = 0; it < iters; it++) {
    const temp = 1 - it / iters;
    fx.fill(0); fz.fill(0);
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = px[i] - px[j], dz = pz[i] - pz[j];
        let d2 = dx * dx + dz * dz;
        if (d2 < 1e-4) { dx = 0.01 * (i - j); dz = 0.01; d2 = 1e-4; }
        const f = 7 / d2;
        const d = Math.sqrt(d2);
        fx[i] += (dx / d) * f; fz[i] += (dz / d) * f;
        fx[j] -= (dx / d) * f; fz[j] -= (dz / d) * f;
      }
    }
    for (const [a, b] of edges) {
      const dx = px[b] - px[a], dz = pz[b] - pz[a];
      const d = Math.max(0.01, Math.hypot(dx, dz));
      const f = (d - 4.4) * 0.09;
      fx[a] += (dx / d) * f; fz[a] += (dz / d) * f;
      fx[b] -= (dx / d) * f; fz[b] -= (dz / d) * f;
    }
    for (let i = 0; i < n; i++) {
      const role = roles.get(names[i]);
      const k = role === 'fact' ? 0.07 : degree[i] === 0 ? 0.008 : 0.016;
      fx[i] -= px[i] * k; fz[i] -= pz[i] * k;
      const step = 0.08 + 0.6 * temp;
      const m = Math.hypot(fx[i], fz[i]);
      const s = m > step ? step / m : 1;
      px[i] += fx[i] * s; pz[i] += fz[i] * s;
    }
  }
  // Resolve overlaps between footprints
  const size = tables.map((t) => boxSize(t, roles.get(t.name) ?? 'dim'));
  for (let pass = 0; pass < 6; pass++) {
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const minD = (Math.max(size[i].w, size[i].d) + Math.max(size[j].w, size[j].d)) / 2 + 0.9;
        const dx = px[j] - px[i], dz = pz[j] - pz[i];
        const d = Math.hypot(dx, dz) || 0.01;
        if (d < minD) {
          const push = (minD - d) / 2;
          px[i] -= (dx / d) * push; pz[i] -= (dz / d) * push;
          px[j] += (dx / d) * push; pz[j] += (dz / d) * push;
        }
      }
    }
  }
  let cx = 0, cz = 0;
  for (let i = 0; i < n; i++) { cx += px[i]; cz += pz[i]; }
  cx /= Math.max(1, n); cz /= Math.max(1, n);
  return new Map(names.map((nm, i) => [nm, { x: px[i] - cx, z: pz[i] - cz }]));
}

export function boxSize(t: TableInfo, role: TableRole) {
  const c = Math.min(Math.max(t.column_count || 0, 1), 60);
  const w = role === 'fact' ? 1.5 + c * 0.032 : 0.9 + c * 0.022;
  return { w, d: w * (role === 'fact' ? 0.62 : 0.72), h: 0.35 + Math.log2(1 + c) * 0.24 };
}

export class ModelScene {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(32, 1, 0.1, 500);
  private home = { theta: 0.62, phi: 0.98, r: 25, tx: 0, ty: 0.4, tz: 0 };
  private cam = { ...this.home };
  private ground: THREE.Mesh<THREE.PlaneGeometry, THREE.ShadowMaterial>;
  private grid: THREE.GridHelper;
  private nodes: Node[] = [];
  private byId = new Map<string, Node>();
  private links: Link[] = [];
  private linkFade = { o: 0 };
  private flows: { l: Link; rev: boolean }[] = [];
  private points: THREE.Points<THREE.BufferGeometry, THREE.PointsMaterial>;
  private pPos: Float32Array; private pCol: Float32Array;
  private plate: { group: THREE.Group; mesh: THREE.Mesh; edges: THREE.LineSegments; label: HTMLDivElement; y: number; s: { v: number } } | null = null;
  private tiles: Tile[] = [];
  private focusTables: Set<string> | null = null;
  private focusRels = new Set<string>();
  private marked: string | null = null;
  private hovered: string | null = null;
  private hoveredTile: number | null = null;
  private selectedTile: number | null = null;
  private flow = true;
  private reduce = prefersReducedMotion();
  private raf = 0; private tPrev = performance.now(); private clock = 0; private idle = 0;
  private visible = true;
  private drag: { x: number; y: number; moved: number; id: number } | null = null;
  private ray = new THREE.Raycaster(); private ndc = new THREE.Vector2();
  private v = new THREE.Vector3(); private tmp = new THREE.Vector3();
  private observers: { disconnect(): void }[] = [];
  private cleanups: (() => void)[] = [];
  private maxH = 1;
  readonly ok: boolean;

  static supported(): boolean {
    try {
      const c = document.createElement('canvas');
      return !!(c.getContext('webgl2') || c.getContext('webgl'));
    } catch {
      return false;
    }
  }

  constructor(
    private stage: HTMLElement,
    private labels: HTMLElement,
    private tip: HTMLElement,
    private data: SceneData,
    private cb: SceneCallbacks = {},
  ) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.domElement.setAttribute('aria-hidden', 'true');
    stage.prepend(this.renderer.domElement);
    this.ok = true;

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x9aa6b4, 0.55));
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.28));
    const sun = new THREE.DirectionalLight(0xffffff, 0.75);
    sun.position.set(10, 22, 8);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -0.0008;
    this.scene.add(sun);

    // ---- tables
    const pos = layoutTables(data.tables, data.relationships, data.roles);
    let extent = 4;
    data.tables.forEach((t, i) => {
      const role = data.roles.get(t.name) ?? 'dim';
      const { w, d, h } = boxSize(t, role);
      const p = pos.get(t.name)!;
      extent = Math.max(extent, Math.abs(p.x) + w, Math.abs(p.z) + d);
      this.maxH = Math.max(this.maxH, h);
      const geo = new THREE.BoxGeometry(w, h, d); geo.translate(0, h / 2, 0);
      const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ roughness: 0.82, metalness: 0, transparent: true }));
      mesh.castShadow = true; mesh.receiveShadow = true;
      mesh.position.set(p.x, 0, p.z);
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ transparent: true }));
      mesh.add(edges);
      this.scene.add(mesh);
      let flag: Node['flag'] = null;
      if (data.tableSeverity.get(t.name)) {
        flag = new THREE.Mesh(new THREE.OctahedronGeometry(0.2), new THREE.MeshStandardMaterial({ roughness: 0.5, transparent: true }));
        flag.castShadow = true;
        this.scene.add(flag);
      }
      const label = document.createElement('div');
      label.className = 'tlabel' + (role === 'fact' ? ' fact' : '');
      label.textContent = t.name;
      if (role === 'fact') {
        const small = document.createElement('small');
        small.textContent = `${t.column_count} cols · ${t.measures_count} measures`;
        label.appendChild(small);
      }
      labels.appendChild(label);
      const node: Node = { t, role, i, mesh, edges, flag, label, x: p.x, z: p.z, w, h, d, s: this.reduce ? 1 : 0, L: { v: 0 } };
      mesh.userData.node = node;
      this.nodes.push(node);
      this.byId.set(t.name, node);
    });

    const dense = this.nodes.length > 28;
    if (dense) this.nodes.forEach((n) => { if (n.role !== 'fact' && n.role !== 'date') n.label.dataset.quiet = '1'; });

    const groundSize = Math.max(40, extent * 4);
    this.ground = new THREE.Mesh(new THREE.PlaneGeometry(groundSize, groundSize), new THREE.ShadowMaterial({ opacity: 0.14 }));
    this.ground.rotation.x = -Math.PI / 2; this.ground.receiveShadow = true;
    this.scene.add(this.ground);
    const gridSize = Math.ceil(extent * 2.6 / 2) * 2;
    this.grid = new THREE.GridHelper(gridSize, gridSize);
    this.grid.position.y = GRID_Y;
    (this.grid.material as THREE.LineBasicMaterial).transparent = true;
    (this.grid.material as THREE.LineBasicMaterial).opacity = 0.6;
    this.scene.add(this.grid);
    Object.assign(sun.shadow.camera, { left: -extent - 4, right: extent + 4, top: extent + 4, bottom: -extent - 4, near: 1, far: 80 });

    // ---- relationships
    for (const r of data.relationships) {
      const A = this.byId.get(r.from_table), B = this.byId.get(r.to_table);
      if (!A || !B || A === B) continue;
      const a = new THREE.Vector3(A.x, A.h + 0.02, A.z);
      const b = new THREE.Vector3(B.x, B.h + 0.02, B.z);
      const mid = a.clone().add(b).multiplyScalar(0.5);
      mid.y = Math.max(a.y, b.y) + a.distanceTo(b) * 0.22 + 0.6;
      const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
      const geo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(48));
      const m2m = (r.cardinality || '').toLowerCase() === 'manytomany';
      const inactive = r.is_active === false;
      const mat = m2m || inactive
        ? new THREE.LineDashedMaterial({ dashSize: inactive ? 0.12 : 0.26, gapSize: inactive ? 0.18 : 0.16, transparent: true })
        : new THREE.LineBasicMaterial({ transparent: true });
      const line = new THREE.Line(geo, mat);
      if (m2m || inactive) line.computeLineDistances();
      this.scene.add(line);
      const [cf, ct] = cardinalityLabel(r);
      const mk = (txt: string) => {
        const el = document.createElement('div');
        el.className = 'clabel'; el.textContent = txt; el.hidden = true;
        labels.appendChild(el);
        return el;
      };
      const key = relKey(r);
      this.links.push({ r, key, line, curve, sev: data.relSeverity.get(key) ?? null, inFocus: true, cards: [[mk(cf), 0.1], [mk(ct), 0.9]] });
    }
    for (const l of this.links) {
      if (l.r.is_active === false) continue;
      const fromMany = isManySide(l.r, 'from'), toMany = isManySide(l.r, 'to');
      // filters flow from the one side to the many side; curve t=0 is the "from" table
      if (!fromMany || toMany || isBidirectional(l.r)) this.flows.push({ l, rev: false });
      if (fromMany || isBidirectional(l.r)) this.flows.push({ l, rev: true });
    }
    const PER = 3;
    this.pPos = new Float32Array(Math.max(1, this.flows.length * PER) * 3);
    this.pCol = new Float32Array(this.pPos.length);
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(this.pPos, 3));
    pGeo.setAttribute('color', new THREE.BufferAttribute(this.pCol, 3));
    this.points = new THREE.Points(pGeo, new THREE.PointsMaterial({ size: 0.17, vertexColors: true, transparent: true }));
    this.scene.add(this.points);

    // ---- report layer
    if (data.report) this.buildReport(data.report, extent);

    // ---- camera framing
    const R = extent * 2.5 + 7;
    this.home = data.report
      ? { theta: 0.62, phi: 1.12, r: R + 6, tx: 0, ty: (this.plate?.y ?? 4) * 0.5, tz: 0 }
      : { theta: 0.62, phi: 0.98, r: R, tx: 0, ty: 0.4, tz: 0 };
    this.cam = { ...this.home };

    this.bindEvents();
    this.paint();
    this.intro();
    this.raf = requestAnimationFrame(this.frame);
  }

  // ---------------------------------------------------------------- report layer
  private buildReport(rep: ReportLayer, extent: number) {
    const pw = rep.page.width || 1280, ph = rep.page.height || 720;
    const plateW = Math.min(24, Math.max(9, extent * 1.7));
    const plateD = plateW * (ph / pw);
    const y = this.maxH + 4.2;
    const group = new THREE.Group();
    group.position.set(0, y, 0);
    const geo = new THREE.BoxGeometry(plateW, 0.06, plateD);
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ transparent: true, opacity: 0.55, roughness: 0.9 }));
    mesh.receiveShadow = true;
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ transparent: true }));
    group.add(mesh); group.add(edges);
    this.scene.add(group);
    const label = document.createElement('div');
    label.className = 'tlabel page';
    label.textContent = rep.page.display_name;
    this.labels.appendChild(label);
    this.plate = { group, mesh, edges, label, y, s: { v: this.reduce ? 1 : 0 } };

    (rep.page.visuals || []).forEach((v, i) => {
      const vw = Math.max(0.15, (v.width / pw) * plateW), vd = Math.max(0.15, (v.height / ph) * plateD);
      const refs = rep.visualTables[i] || [];
      const vh = 0.1 + Math.min(refs.length, 8) * 0.05;
      const tgeo = new THREE.BoxGeometry(vw * 0.96, vh, vd * 0.96);
      tgeo.translate(0, vh / 2 + 0.03, 0);
      const tmesh = new THREE.Mesh(tgeo, new THREE.MeshStandardMaterial({ roughness: 0.7, transparent: true }));
      tmesh.castShadow = true;
      tmesh.position.set((v.x / pw) * plateW - plateW / 2 + vw / 2, 0, (v.y / ph) * plateD - plateD / 2 + vd / 2);
      const tedges = new THREE.LineSegments(new THREE.EdgesGeometry(tgeo), new THREE.LineBasicMaterial({ transparent: true }));
      tmesh.add(tedges);
      tmesh.userData.tile = i;
      group.add(tmesh);
      const threads = refs.flatMap((table) => {
        const n = this.byId.get(table);
        if (!n) return [];
        const from = new THREE.Vector3(tmesh.position.x, y - 0.03, tmesh.position.z);
        const to = new THREE.Vector3(n.x, n.h + 0.05, n.z);
        const lgeo = new THREE.BufferGeometry().setFromPoints([from, to]);
        const line = new THREE.Line(lgeo, new THREE.LineBasicMaterial({ transparent: true }));
        this.scene.add(line);
        return [{ table, line }];
      });
      this.tiles.push({ i, mesh: tmesh, edges: tedges, threads, slicer: v.is_slicer, over: rep.overLimit.has(i), hidden: v.hidden });
    });
  }

  // ---------------------------------------------------------------- colours
  private col(name: string) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return new THREE.Color(v || '#888888');
  }
  private isDark() {
    const t = document.documentElement.getAttribute('data-theme');
    return t ? t === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  paint = () => {
    const ink = this.col('--ink'), ink3 = this.col('--ink-3'), ruleStrong = this.col('--rule-strong'), rule = this.col('--rule');
    const accent = this.col('--accent');
    const grid = this.grid.material as THREE.LineBasicMaterial;
    if (grid.vertexColors) { grid.vertexColors = false; grid.needsUpdate = true; }
    grid.color = rule;
    this.ground.material.opacity = this.isDark() ? 0.42 : 0.13;
    const reportFocus = this.selectedTile !== null || this.hoveredTile !== null;
    const tileTables = new Set<string>();
    if (reportFocus) {
      const t = this.tiles[(this.hoveredTile ?? this.selectedTile)!];
      t?.threads.forEach((th) => tileTables.add(th.table));
    }
    for (const n of this.nodes) {
      const focus = this.focusTables;
      const inFocus = (!focus || focus.has(n.t.name)) && (!reportFocus || tileTables.has(n.t.name));
      const hot = (focus?.has(n.t.name) ?? false) || this.marked === n.t.name || this.hovered === n.t.name || (reportFocus && tileTables.has(n.t.name));
      const base = n.role === 'other' ? 'other' : n.role;
      const fill = this.col(`--t-${base}`);
      n.mesh.material.color = fill;
      n.mesh.material.emissive = hot ? fill.clone().multiplyScalar(this.isDark() ? 0.45 : 0.3) : new THREE.Color(0);
      n.mesh.material.opacity = (inFocus ? 1 : 0.2) * (n.t.hidden ? 0.55 : 1);
      n.mesh.material.depthWrite = inFocus;
      n.edges.material.color = hot ? ink : this.col(`--t-${base}-edge`);
      n.edges.material.opacity = inFocus ? 1 : 0.22;
      const sev = this.data.tableSeverity.get(n.t.name);
      if (n.flag && sev) { n.flag.material.color = this.col(SEV[sev].token); n.flag.material.opacity = inFocus ? 1 : 0.25; }
      n.label.classList.toggle('dim', !inFocus);
      n.label.classList.toggle('hot', hot);
      n.label.style.display = n.label.dataset.quiet && !hot ? 'none' : '';
    }
    for (const l of this.links) {
      l.inFocus = reportFocus ? false : !this.focusTables || this.focusRels.has(l.key);
      l.line.material.color = l.sev ? this.col(SEV[l.sev].token) : ruleStrong;
      const showCards = this.focusRels.has(l.key);
      l.cards.forEach(([el]) => { el.hidden = !showCards; });
    }
    const PER = 3;
    this.flows.forEach((f, fi) => {
      const c = f.l.sev ? this.col(SEV[f.l.sev].token) : ink3;
      for (let k = 0; k < PER; k++) { const o = (fi * PER + k) * 3; this.pCol[o] = c.r; this.pCol[o + 1] = c.g; this.pCol[o + 2] = c.b; }
    });
    this.points.geometry.attributes.color.needsUpdate = true;

    if (this.plate) {
      (this.plate.mesh.material as THREE.MeshStandardMaterial).color = this.col('--panel-2');
      (this.plate.edges.material as THREE.LineBasicMaterial).color = ruleStrong;
      const slicer = this.col('--t-slicer'), visual = this.col('--t-visual'), over = this.col('--sev-medium');
      for (const t of this.tiles) {
        const sel = this.selectedTile === t.i || this.hoveredTile === t.i;
        const linkedToMarked = !!this.marked && t.threads.some((th) => th.table === this.marked);
        const lit = sel || linkedToMarked;
        t.mesh.material.color = lit ? accent : t.slicer ? slicer : visual;
        t.mesh.material.opacity = t.hidden ? 0.35 : 1;
        t.edges.material.color = t.over ? over : lit ? ink : ruleStrong;
        for (const th of t.threads) {
          const on = sel || (this.marked ? th.table === this.marked : false);
          th.line.material.color = on ? accent : ink3;
          th.line.material.opacity = on ? 0.95 : (reportFocus || this.marked ? 0.06 : 0.28);
        }
      }
    }
    this.settle();
  };

  private settle() {
    for (const n of this.nodes) {
      const target = (this.focusTables?.has(n.t.name) ? 0.3 : 0) + (this.hovered === n.t.name ? 0.2 : 0);
      if (Math.abs(n.L.v - target) < 0.001) continue;
      if (this.reduce) { n.L.v = target; continue; }
      anime.remove(n.L);
      anime({ targets: n.L, v: target, duration: 420, easing: 'easeOutBack' });
    }
  }

  private intro() {
    if (this.reduce) { this.linkFade.o = 1; return; }
    const order = [...this.nodes].sort((a, b) => Math.hypot(a.x, a.z) - Math.hypot(b.x, b.z));
    const step = Math.min(70, 1200 / Math.max(1, order.length));
    order.forEach((n, k) => anime({ targets: n, s: [0, 1], delay: 120 + k * step, duration: 900, easing: 'easeOutElastic(1, .75)' }));
    const after = 120 + order.length * step;
    anime({ targets: this.linkFade, o: [0, 1], delay: after, duration: 700, easing: 'easeOutQuad' });
    if (this.plate) anime({ targets: this.plate.s, v: [0, 1], delay: after + 200, duration: 900, easing: 'easeOutCubic' });
  }

  // ---------------------------------------------------------------- public API
  /** Highlight tables/relationships for a finding; pass null to clear, [] to dim everything (model-wide finding). */
  setFocus(tables: string[] | null, rels: string[] = []) {
    this.focusTables = tables ? new Set(tables) : null;
    this.focusRels = new Set(rels);
    if (!tables || !tables.length) {
      this.tween({ tx: this.home.tx, ty: this.home.ty, tz: this.home.tz, r: this.home.r });
    } else {
      const ns = tables.map((t) => this.byId.get(t)).filter(Boolean) as Node[];
      if (ns.length) {
        const cx = ns.reduce((s, n) => s + n.x, 0) / ns.length;
        const cz = ns.reduce((s, n) => s + n.z, 0) / ns.length;
        const spread = Math.max(...ns.map((n) => Math.hypot(n.x - cx, n.z - cz)));
        // Move most of the way toward the focused tables but keep the rest of the model in view.
        const k = 0.65;
        this.tween({
          tx: this.home.tx + (cx - this.home.tx) * k, ty: ns[0].h * 0.5, tz: this.home.tz + (cz - this.home.tz) * k,
          r: Math.min(this.home.r, Math.max(this.home.r * 0.72, 10 + spread * 2.6)),
        });
      }
    }
    this.paint();
  }
  setMarked(name: string | null) { this.marked = name; this.paint(); }
  setSelectedVisual(i: number | null) { this.selectedTile = i; this.paint(); }
  setFlow(on: boolean) { this.flow = on; }
  zoom(dir: 1 | -1) { this.tween({ r: Math.min(this.home.r * 2, Math.max(7, this.cam.r - dir * 4)) }); }
  reset() { this.focusTables = null; this.focusRels.clear(); this.tween({ ...this.home }); this.paint(); }

  private tween(to: Partial<typeof this.cam>) {
    if (this.reduce) { Object.assign(this.cam, to); return; }
    anime.remove(this.cam);
    anime({ targets: this.cam, ...to, duration: 1000, easing: 'easeInOutCubic' });
  }

  // ---------------------------------------------------------------- events
  private bindEvents() {
    const s = this.stage;
    const on = <K extends keyof HTMLElementEventMap>(type: K, fn: (e: HTMLElementEventMap[K]) => void) => {
      s.addEventListener(type, fn as EventListener);
      this.cleanups.push(() => s.removeEventListener(type, fn as EventListener));
    };
    on('pointerdown', (e) => {
      if ((e.target as HTMLElement).closest('.map-tools')) return;
      this.drag = { x: e.clientX, y: e.clientY, moved: 0, id: e.pointerId };
    });
    on('pointermove', (e) => {
      if (this.drag && this.drag.id === e.pointerId) {
        const dx = e.clientX - this.drag.x, dy = e.clientY - this.drag.y;
        this.drag.moved += Math.abs(dx) + Math.abs(dy);
        if (this.drag.moved > 4) {
          try { s.setPointerCapture(e.pointerId); } catch { /* pointer already gone */ }
          this.cam.theta -= dx * 0.008;
          this.cam.phi = Math.min(1.38, Math.max(0.3, this.cam.phi - dy * 0.006));
          this.idle = 0;
          this.tip.hidden = true;
        }
        this.drag.x = e.clientX; this.drag.y = e.clientY;
      } else if (e.pointerType === 'mouse') {
        this.pick(e);
      }
    });
    on('pointerup', (e) => {
      if (this.drag && this.drag.moved < 5) {
        const hit = this.hit(e);
        if (hit?.tile !== undefined) {
          this.selectedTile = this.selectedTile === hit.tile ? null : hit.tile;
          this.cb.onVisualClick?.(this.selectedTile);
          this.paint();
        } else {
          const id = hit?.table ?? null;
          this.marked = id && this.marked !== id ? id : null;
          this.cb.onTableClick?.(this.marked);
          this.paint();
        }
      }
      this.drag = null;
    });
    on('pointercancel', () => { this.drag = null; });
    on('pointerleave', () => {
      this.tip.hidden = true;
      if (this.hovered || this.hoveredTile !== null) { this.hovered = null; this.hoveredTile = null; this.paint(); }
    });

    const ro = new ResizeObserver(() => this.resize());
    ro.observe(s); this.observers.push(ro);
    const io = new IntersectionObserver(([en]) => { this.visible = en.isIntersecting; });
    io.observe(s); this.observers.push(io);
    const mo = new MutationObserver(() => this.paint());
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    this.observers.push(mo);
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', this.paint);
    this.cleanups.push(() => mq.removeEventListener('change', this.paint));
    this.resize();
  }

  private hit(e: PointerEvent): { table?: string; tile?: number } | null {
    const rect = this.stage.getBoundingClientRect();
    this.ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    this.ray.setFromCamera(this.ndc, this.camera);
    const targets: THREE.Object3D[] = [...this.tiles.map((t) => t.mesh), ...this.nodes.map((n) => n.mesh)];
    const h = this.ray.intersectObjects(targets, false)[0];
    if (!h) return null;
    if (h.object.userData.tile !== undefined) return { tile: h.object.userData.tile as number };
    return { table: (h.object.userData.node as Node).t.name };
  }

  private pick(e: PointerEvent) {
    const hit = this.hit(e);
    const table = hit?.table ?? null, tile = hit?.tile ?? null;
    if (table !== this.hovered || tile !== this.hoveredTile) {
      this.hovered = table; this.hoveredTile = tile;
      this.stage.style.cursor = table || tile !== null ? 'pointer' : '';
      this.paint();
    }
    if (!table && tile === null) { this.tip.hidden = true; return; }
    const rect = this.stage.getBoundingClientRect();
    this.tip.replaceChildren();
    const add = (text: string, bold = false) => {
      const el = document.createElement(bold ? 'b' : 'div');
      el.textContent = text;
      this.tip.appendChild(el);
    };
    if (table) {
      const n = this.byId.get(table)!;
      const t = n.t;
      add(t.name, true);
      add(`${n.role === 'other' ? 'unrelated table' : n.role === 'dim' ? 'dimension' : n.role}${t.hidden ? ' · hidden' : ''}`);
      add(`${t.column_count} columns · ${t.measures_count} measures · ${t.calc_cols_count} calculated`);
      const c = this.data.findingCounts.get(table) ?? 0;
      add(c ? `${c} finding${c > 1 ? 's' : ''} · click to filter` : 'no findings');
    } else if (tile !== null && this.data.report) {
      const v = (this.data.report.page.visuals || [])[tile];
      const refs = this.data.report.visualTables[tile] || [];
      add(v.visual_type, true);
      add(refs.length ? `reads ${refs.join(', ')}` : 'reads no model tables');
      add(`${(v.measure_refs || []).length} measures${v.is_slicer ? ' · slicer' : ''}${v.hidden ? ' · hidden' : ''}`);
      if (this.tiles[tile]?.over) add('over the per-page visual limit');
    }
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    this.tip.hidden = false;
    const tw = this.tip.offsetWidth, th = this.tip.offsetHeight;
    this.tip.style.left = `${Math.min(x + 12, rect.width - tw - 6)}px`;
    this.tip.style.top = `${Math.min(y + 12, rect.height - th - 6)}px`;
  }

  private resize() {
    const w = this.stage.clientWidth, h = this.stage.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  private place(el: HTMLElement, pos: THREE.Vector3, w: number, h: number) {
    this.v.copy(pos).project(this.camera);
    if (this.v.z > 1 || this.v.z < -1) { el.style.visibility = 'hidden'; return; }
    el.style.visibility = 'visible';
    el.style.transform = `translate(${((this.v.x + 1) / 2) * w}px, ${((1 - this.v.y) / 2) * h}px) translate(-50%, -100%)`;
  }

  private frame = (now: number) => {
    this.raf = requestAnimationFrame(this.frame);
    const dt = Math.min(0.05, (now - this.tPrev) / 1000);
    this.tPrev = now;
    if (!this.visible || document.hidden) return;
    this.idle += dt; this.clock += dt;
    if (!this.reduce && !this.drag && this.idle > 3) this.cam.theta += dt * 0.045;

    const c = this.cam;
    this.camera.position.set(
      c.tx + c.r * Math.sin(c.phi) * Math.sin(c.theta),
      c.ty + c.r * Math.cos(c.phi),
      c.tz + c.r * Math.sin(c.phi) * Math.cos(c.theta));
    this.camera.lookAt(c.tx, c.ty, c.tz);

    const w = this.stage.clientWidth, h = this.stage.clientHeight;
    for (const n of this.nodes) {
      n.mesh.scale.y = Math.max(0.002, n.s);
      n.mesh.position.y = n.L.v;
      const top = n.h * n.s + n.L.v;
      if (n.flag) {
        n.flag.scale.setScalar(Math.max(0.001, n.s));
        n.flag.position.set(n.x, top + 0.5 + (this.reduce ? 0 : Math.sin(this.clock * 2.2 + n.i) * 0.07), n.z);
        if (!this.reduce) n.flag.rotation.y += dt * 0.9;
      }
      this.tmp.set(n.x, top + (n.flag ? 0.85 : 0.15), n.z);
      this.place(n.label, this.tmp, w, h);
    }
    for (const l of this.links) {
      l.line.material.opacity = this.linkFade.o * (l.inFocus ? 1 : 0.13);
      for (const [el, t] of l.cards) if (!el.hidden) this.place(el, l.curve.getPoint(t), w, h);
    }
    const PER = 3;
    this.points.visible = this.flow && this.linkFade.o > 0.5;
    if (this.points.visible) {
      this.flows.forEach((f, fi) => {
        for (let k = 0; k < PER; k++) {
          const base = ((this.reduce ? 0 : this.clock * 0.2) + k / PER + fi * 0.13) % 1;
          const o = (fi * PER + k) * 3;
          if (!f.l.inFocus) { this.pPos[o] = this.pPos[o + 1] = this.pPos[o + 2] = 1e5; continue; }
          f.l.curve.getPoint(f.rev ? 1 - base : base, this.tmp);
          this.pPos[o] = this.tmp.x; this.pPos[o + 1] = this.tmp.y; this.pPos[o + 2] = this.tmp.z;
        }
      });
      this.points.geometry.attributes.position.needsUpdate = true;
    }
    if (this.plate) {
      const s = this.plate.s.v;
      this.plate.group.position.y = this.plate.y + (1 - s) * 3;
      this.plate.group.scale.setScalar(0.6 + 0.4 * s);
      (this.plate.mesh.material as THREE.MeshStandardMaterial).opacity = 0.55 * s;
      for (const t of this.tiles) for (const th of t.threads) th.line.visible = s > 0.95;
      const p = this.plate.mesh.geometry as THREE.BoxGeometry;
      this.tmp.set(-p.parameters.width / 2 + 0.2, this.plate.group.position.y + 0.25, -p.parameters.depth / 2);
      this.place(this.plate.label, this.tmp, w, h);
      this.plate.label.style.transform += ' translate(50%, 0)';
    }
    this.renderer.render(this.scene, this.camera);
  };

  dispose() {
    cancelAnimationFrame(this.raf);
    anime.remove([this.cam, this.linkFade, ...this.nodes, ...this.nodes.map((n) => n.L), ...(this.plate ? [this.plate.s] : [])]);
    this.observers.forEach((o) => o.disconnect());
    this.cleanups.forEach((fn) => fn());
    this.scene.traverse((obj) => {
      const o = obj as THREE.Mesh;
      o.geometry?.dispose?.();
      const m = o.material as THREE.Material | THREE.Material[] | undefined;
      if (Array.isArray(m)) m.forEach((x) => x.dispose()); else m?.dispose?.();
    });
    this.renderer.dispose();
    this.renderer.domElement.remove();
    this.labels.replaceChildren();
    this.tip.hidden = true;
  }
}
