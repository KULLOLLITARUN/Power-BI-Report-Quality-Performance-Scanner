// The 3D measure dependency graph: one marker per measure or calculated column,
// stacked by dependency depth, with a line for every "uses" reference. Unused
// measures keep their amber colour so they stand out from the connected ones.
// Selecting a node lights its whole chain, up to the visuals and down to the base.
import * as THREE from 'three';
import type { DepEdge, DepLayout, DepNode } from './depLayout';
import { LEVEL_GAP } from './depLayout';
import { prefersReducedMotion } from './motion';
import { applyEnvironment, makeGlow, makeTrails, setGlowBlend, trailParam, type GlowSprite, type TrailLayer } from './fx';

export interface DepSceneCallbacks {
  onSelect?: (name: string | null) => void;
}

type NodeMesh = THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;

const LABEL_LIMIT = 14;

export class DepScene {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(36, 1, 0.1, 500);
  private home = { theta: 0.7, phi: 1.12, r: 20, ty: 0 };
  private cam = { ...this.home };
  private meshes = new Map<string, NodeMesh>();
  private byId = new Map<string, DepNode>();
  private lines: THREE.LineSegments<THREE.BufferGeometry, THREE.LineBasicMaterial>;
  private lineColors: Float32Array;
  private floors: THREE.Mesh[] = [];
  private labels = new Map<string, HTMLDivElement>();
  private selected: string | null = null;
  private hovered: string | null = null;
  private chain: Set<string> | null = null;
  /** Soft halo behind a node: strong when selected, faint amber on an unused measure. */
  private glows = new Map<string, { sprite: GlowSprite; base: number; size: number; phase: number }>();
  private headPts: THREE.Points<THREE.BufferGeometry, THREE.PointsMaterial>;
  private headPos: Float32Array;
  private trails: TrailLayer[] = [];
  /** Indexes of the edges inside the selected chain: data flows along these, from used to user. */
  private flowEdges: number[] = [];
  private envFx: { dispose(): void } | null = null;
  private reduce = prefersReducedMotion();
  private raf = 0; private tPrev = performance.now(); private idle = 0; private clock = 0;
  private visible = true;
  private drag: { x: number; y: number; moved: number; id: number } | null = null;
  private ray = new THREE.Raycaster(); private ndc = new THREE.Vector2();
  private tmp = new THREE.Vector3();
  private observers: { disconnect(): void }[] = [];
  private cleanups: (() => void)[] = [];

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
    private labelHost: HTMLElement,
    private tip: HTMLElement,
    private layout: DepLayout,
    private cb: DepSceneCallbacks = {},
  ) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.domElement.setAttribute('aria-hidden', 'true');
    stage.prepend(this.renderer.domElement);

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x9aa6b4, 0.8));
    const sun = new THREE.DirectionalLight(0xffffff, 0.8);
    sun.position.set(8, 20, 10);
    this.scene.add(sun);
    this.envFx = applyEnvironment(this.renderer, this.scene, 0.3);

    const sphere = new THREE.SphereGeometry(0.34, 20, 14);
    const cube = new THREE.BoxGeometry(0.56, 0.56, 0.56);
    let extent = 3;
    for (const n of layout.nodes) {
      this.byId.set(n.id, n);
      extent = Math.max(extent, Math.abs(n.x), Math.abs(n.z));
      const mesh: NodeMesh = new THREE.Mesh(
        n.kind === 'calculated_column' ? cube : sphere,
        new THREE.MeshPhysicalMaterial({ roughness: 0.42, metalness: 0.05, clearcoat: 0.3, clearcoatRoughness: 0.35, transparent: true }),
      );
      mesh.position.set(n.x, n.y, n.z);
      mesh.userData.id = n.id;
      this.scene.add(mesh);
      this.meshes.set(n.id, mesh);
      const sprite = makeGlow();
      sprite.position.set(n.x, n.y, n.z);
      this.scene.add(sprite);
      this.glows.set(n.id, { sprite, base: 0, size: 1.6, phase: this.glows.size * 0.7 });
    }

    // one faint floor per depth level, so the stacking reads even with few edges
    for (let l = 0; l < layout.levels; l++) {
      const floor = new THREE.Mesh(
        new THREE.PlaneGeometry(extent * 2 + 3, extent * 2 + 3),
        new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.1, side: THREE.DoubleSide, depthWrite: false }),
      );
      floor.rotation.x = -Math.PI / 2;
      floor.position.y = l * LEVEL_GAP - 0.5;
      this.scene.add(floor);
      this.floors.push(floor);
    }

    const pos = new Float32Array(layout.edges.length * 6);
    layout.edges.forEach((e, i) => {
      const a = this.byId.get(e.from)!, b = this.byId.get(e.to)!;
      pos.set([a.x, a.y, a.z, b.x, b.y, b.z], i * 6);
    });
    this.lineColors = new Float32Array(layout.edges.length * 6);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(this.lineColors, 3));
    this.lines = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.85 }));
    this.scene.add(this.lines);

    // One bright dot per edge inside the selected chain, with a short fading tail.
    const E = layout.edges.length;
    this.headPos = new Float32Array(Math.max(1, E) * 3).fill(1e5);
    const headCol = new Float32Array(Math.max(1, E) * 3);
    const headGeo = new THREE.BufferGeometry();
    headGeo.setAttribute('position', new THREE.BufferAttribute(this.headPos, 3));
    const headColAttr = new THREE.BufferAttribute(headCol, 3);
    headGeo.setAttribute('color', headColAttr);
    this.headPts = new THREE.Points(headGeo, new THREE.PointsMaterial({ size: 0.2, vertexColors: true, transparent: true, depthWrite: false }));
    this.headPts.frustumCulled = false;
    this.headPts.visible = false;
    this.scene.add(this.headPts);
    this.trails = makeTrails(E, headColAttr);
    this.trails.forEach((tl) => { tl.pos.fill(1e5); tl.points.visible = false; this.scene.add(tl.points); });

    const top = (layout.levels - 1) * LEVEL_GAP;
    this.home = { theta: 0.7, phi: 1.12, r: Math.max(14, extent * 2.4 + top * 0.9 + 6), ty: top / 2 };
    this.cam = { ...this.home };

    this.bindEvents();
    this.paint();
    this.raf = requestAnimationFrame(this.frame);
  }

  // ---------------------------------------------------------------- state
  select(name: string | null) {
    const id = name ? name.toLowerCase() : null;
    this.selected = id && this.byId.has(id) ? id : null;
    this.chain = this.selected ? this.chainOf(this.selected) : null;
    this.paint();
  }
  zoom(dir: 1 | -1) { this.cam.r = Math.min(this.home.r * 2, Math.max(6, this.cam.r - dir * 3)); }
  reset() { Object.assign(this.cam, this.home); this.idle = 0; }

  /** The node, everything it uses (down) and everything that uses it (up). */
  private chainOf(id: string): Set<string> {
    const out = new Set<string>([id]);
    const walk = (start: string, next: (n: DepNode) => string[]) => {
      const stack = [start];
      while (stack.length) {
        const n = this.byId.get(stack.pop()!);
        if (!n) continue;
        for (const m of next(n).map((s) => s.toLowerCase())) {
          if (!out.has(m) && this.byId.has(m)) { out.add(m); stack.push(m); }
        }
      }
    };
    walk(id, (n) => n.references);
    walk(id, (n) => n.referencedBy);
    return out;
  }

  // ---------------------------------------------------------------- colours
  private col(name: string) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return new THREE.Color(v || '#888888');
  }

  private nodeColor(n: DepNode): THREE.Color {
    if (n.used === false) return this.col('--sev-medium');
    if (n.isRoot) return this.col('--t-fact');
    if (n.used === true) return this.col('--t-dim');
    return this.col('--t-other');
  }

  private isDark() {
    const t = document.documentElement.getAttribute('data-theme');
    return t ? t === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  paint = () => {
    const rule = this.col('--rule-strong'), accent = this.col('--accent'), ink = this.col('--ink');
    const focus = this.chain;
    const dark = this.isDark();
    for (const [id, mesh] of this.meshes) {
      const n = this.byId.get(id)!;
      const inFocus = !focus || focus.has(id);
      const hot = id === this.selected || id === this.hovered;
      const c = this.nodeColor(n);
      mesh.material.color = c;
      mesh.material.emissive = hot ? c.clone().multiplyScalar(0.5) : new THREE.Color(0);
      mesh.material.opacity = inFocus ? 1 : 0.14;
      mesh.material.depthWrite = inFocus;
      mesh.scale.setScalar(hot ? 1.35 : n.isRoot ? 1.15 : 1);
      const g = this.glows.get(id);
      if (g) {
        g.sprite.material.color = c;
        setGlowBlend(g.sprite.material, dark);
        g.base = id === this.selected ? 0.75 : id === this.hovered ? 0.5 : n.used === false && inFocus ? 0.3 : 0;
        g.size = id === this.selected ? 2.4 : id === this.hovered ? 2 : 1.7;
      }
    }
    const inChain = (e: DepEdge) => !focus || (focus.has(e.from) && focus.has(e.to));
    const headCol = this.headPts.geometry.attributes.color as THREE.BufferAttribute;
    this.flowEdges = [];
    this.layout.edges.forEach((e, i) => {
      const lit = !!focus && inChain(e);
      const c = !focus ? rule : lit ? accent : rule.clone().lerp(this.col('--paper'), 0.82);
      for (let k = 0; k < 2; k++) this.lineColors.set([c.r, c.g, c.b], i * 6 + k * 3);
      headCol.setXYZ(i, accent.r, accent.g, accent.b);
      if (lit) this.flowEdges.push(i);
    });
    this.lines.geometry.attributes.color.needsUpdate = true;
    headCol.needsUpdate = true;
    this.trails.forEach((tl) => setGlowBlend(tl.points.material, dark));
    const floor = this.col('--panel-2');
    for (const f of this.floors) (f.material as THREE.MeshBasicMaterial).color = floor;
    this.syncLabels(ink);
  };

  /** Names for the selected node and its direct neighbours only; naming everything would bury the graph. */
  private syncLabels(ink: THREE.Color) {
    const want = new Set<string>();
    const add = (id: string | null) => { if (id) want.add(id); };
    add(this.selected);
    const sel = this.selected ? this.byId.get(this.selected) : null;
    if (sel) {
      [...sel.references, ...sel.referencedBy].slice(0, LABEL_LIMIT).forEach((m) => add(m.toLowerCase()));
    }
    for (const [id, el] of this.labels) if (!want.has(id)) { el.remove(); this.labels.delete(id); }
    for (const id of want) {
      const n = this.byId.get(id);
      if (!n) continue;
      let el = this.labels.get(id);
      if (!el) {
        el = document.createElement('div');
        el.className = 'dlabel';
        el.textContent = n.name;
        this.labelHost.appendChild(el);
        this.labels.set(id, el);
      }
      el.classList.toggle('sel', id === this.selected);
      el.style.color = id === this.selected ? '' : `#${ink.getHexString()}`;
    }
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
          this.cam.phi = Math.min(1.5, Math.max(0.25, this.cam.phi - dy * 0.006));
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
        const id = this.hit(e);
        const next = id && id !== this.selected ? id : null;
        this.select(next ? this.byId.get(next)!.name : null);
        this.cb.onSelect?.(next ? this.byId.get(next)!.name : null);
      }
      this.drag = null;
    });
    on('pointercancel', () => { this.drag = null; });
    on('pointerleave', () => {
      this.tip.hidden = true;
      if (this.hovered) { this.hovered = null; this.paint(); }
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

  private hit(e: PointerEvent): string | null {
    const rect = this.stage.getBoundingClientRect();
    this.ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    this.ray.setFromCamera(this.ndc, this.camera);
    const hit = this.ray.intersectObjects([...this.meshes.values()], false)[0];
    return hit ? (hit.object.userData.id as string) : null;
  }

  private pick(e: PointerEvent) {
    const id = this.hit(e);
    if (id !== this.hovered) { this.hovered = id; this.paint(); }
    this.stage.style.cursor = id ? 'pointer' : '';
    const n = id ? this.byId.get(id) : null;
    if (!n) { this.tip.hidden = true; return; }
    const rect = this.stage.getBoundingClientRect();
    const state = n.used === false ? 'not reached by the report' : n.isRoot ? 'used by the report' : n.used ? 'used through other measures' : 'usage unknown';
    this.tip.replaceChildren();
    const b = document.createElement('b');
    b.textContent = n.name;
    this.tip.append(b, document.createElement('br'), `${n.table} · ${state}`, document.createElement('br'),
      `uses ${n.references.length} · used by ${n.referencedBy.length}`);
    this.tip.hidden = false;
    this.tip.style.left = `${Math.min(rect.width - 240, e.clientX - rect.left + 14)}px`;
    this.tip.style.top = `${Math.max(4, e.clientY - rect.top + 14)}px`;
  }

  private resize() {
    const w = this.stage.clientWidth, h = this.stage.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  private frame = (now: number) => {
    this.raf = requestAnimationFrame(this.frame);
    const dt = Math.min(0.05, (now - this.tPrev) / 1000);
    this.tPrev = now;
    if (!this.visible || document.hidden) return;
    this.idle += dt; this.clock += dt;
    if (!this.reduce && !this.drag && !this.selected && this.idle > 3) this.cam.theta += dt * 0.04;

    const c = this.cam;
    this.camera.position.set(
      c.r * Math.sin(c.phi) * Math.sin(c.theta),
      c.ty + c.r * Math.cos(c.phi),
      c.r * Math.sin(c.phi) * Math.cos(c.theta));
    this.camera.lookAt(0, c.ty, 0);

    const w = this.stage.clientWidth, h = this.stage.clientHeight;
    for (const [id, el] of this.labels) {
      const m = this.meshes.get(id);
      if (!m) continue;
      this.tmp.copy(m.position).y += 0.6;
      this.tmp.project(this.camera);
      const behind = this.tmp.z > 1;
      el.style.display = behind ? 'none' : '';
      el.style.transform = `translate(${((this.tmp.x + 1) / 2) * w}px, ${((1 - this.tmp.y) / 2) * h}px) translate(-50%, -100%)`;
    }
    for (const g of this.glows.values()) {
      const breathe = this.reduce ? 1 : 0.85 + 0.15 * Math.sin(this.clock * 2 + g.phase);
      g.sprite.material.opacity = g.base * breathe;
      g.sprite.scale.setScalar(g.size * breathe);
    }
    // Data moves from what a measure uses up to the measure that uses it, along the selected chain only.
    const flowing = !this.reduce && this.flowEdges.length > 0;
    this.headPts.visible = flowing;
    for (const tl of this.trails) tl.points.visible = flowing;
    if (flowing) {
      this.headPos.fill(1e5);
      for (const tl of this.trails) tl.pos.fill(1e5);
      for (const i of this.flowEdges) {
        const e = this.layout.edges[i];
        const a = this.byId.get(e.to), b = this.byId.get(e.from);
        if (!a || !b) continue;
        const base = (this.clock * 0.35 + i * 0.137) % 1;
        const o = i * 3;
        this.headPos[o] = a.x + (b.x - a.x) * base;
        this.headPos[o + 1] = a.y + (b.y - a.y) * base;
        this.headPos[o + 2] = a.z + (b.z - a.z) * base;
        for (const tl of this.trails) {
          const t = trailParam(base, false, tl.lag);
          tl.pos[o] = a.x + (b.x - a.x) * t;
          tl.pos[o + 1] = a.y + (b.y - a.y) * t;
          tl.pos[o + 2] = a.z + (b.z - a.z) * t;
        }
      }
      this.headPts.geometry.attributes.position.needsUpdate = true;
      for (const tl of this.trails) tl.points.geometry.attributes.position.needsUpdate = true;
    }
    this.renderer.render(this.scene, this.camera);
  };

  dispose() {
    cancelAnimationFrame(this.raf);
    this.observers.forEach((o) => o.disconnect());
    this.cleanups.forEach((fn) => fn());
    this.labels.forEach((el) => el.remove());
    this.envFx?.dispose();
    this.scene.traverse((o) => {
      const m = o as THREE.Mesh;
      m.geometry?.dispose?.();
      const mat = m.material as THREE.Material | THREE.Material[] | undefined;
      if (Array.isArray(mat)) mat.forEach((x) => x.dispose()); else mat?.dispose?.();
    });
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
