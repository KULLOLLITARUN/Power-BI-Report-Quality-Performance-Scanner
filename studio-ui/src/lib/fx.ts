// Shared 3D effects for the Studio scenes: a soft glow sprite, pulsing floor rings, comet
// trails for the flow particles, and image-based lighting. Everything here is decoration:
// it never takes part in picking, and each effect has a still version for reduced motion.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

let glowTex: THREE.CanvasTexture | null = null;

/** A white radial falloff, tinted per sprite through the material colour. Created once. */
export function glowTexture(): THREE.CanvasTexture {
  if (glowTex) return glowTex;
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  if (g) {
    const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.3, 'rgba(255,255,255,0.5)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grad;
    g.fillRect(0, 0, 128, 128);
  }
  glowTex = new THREE.CanvasTexture(c);
  glowTex.colorSpace = THREE.SRGBColorSpace;
  return glowTex;
}

export type GlowSprite = THREE.Sprite;

export function makeGlow(): GlowSprite {
  const mat = new THREE.SpriteMaterial({ map: glowTexture(), transparent: true, depthWrite: false, opacity: 0 });
  const s = new THREE.Sprite(mat);
  s.raycast = () => { /* decoration: never picked */ };
  return s;
}

/** A flat ring lying on the floor, scaled and faded by the caller to make a pulse. */
export function makeRing(): THREE.Mesh<THREE.RingGeometry, THREE.MeshBasicMaterial> {
  const m = new THREE.Mesh(
    new THREE.RingGeometry(0.9, 1, 72),
    new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide, opacity: 0 }),
  );
  m.rotation.x = -Math.PI / 2;
  m.raycast = () => { /* decoration: never picked */ };
  return m;
}

/** On a dark page glow adds light; on a light page it has to tint instead, or it vanishes. */
export function setGlowBlend(mat: THREE.Material, dark: boolean) {
  const next = dark ? THREE.AdditiveBlending : THREE.NormalBlending;
  if (mat.blending !== next) { mat.blending = next; mat.needsUpdate = true; }
}

/** Phase 0..1 of a repeating pulse; a fixed mid-pulse frame when motion is reduced. */
export function pulsePhase(clock: number, offset: number, reduce: boolean, speed = 0.55): number {
  if (reduce) return 0.35;
  const p = (clock * speed + offset) % 1;
  return p < 0 ? p + 1 : p;
}

export interface TrailLayer {
  /** How far behind the head (as a share of the arc) this layer sits. */
  lag: number;
  points: THREE.Points<THREE.BufferGeometry, THREE.PointsMaterial>;
  pos: Float32Array;
}

const TRAIL_SPEC = [
  { lag: 0.02, size: 0.13, opacity: 0.55 },
  { lag: 0.045, size: 0.09, opacity: 0.3 },
  { lag: 0.07, size: 0.06, opacity: 0.15 },
] as const;

/**
 * Fading dots that follow each flow particle. They share the head's colour buffer, so a
 * recolour of the particles recolours the trail too.
 */
export function makeTrails(count: number, colors: THREE.BufferAttribute): TrailLayer[] {
  return TRAIL_SPEC.map((spec) => {
    const pos = new Float32Array(Math.max(1, count) * 3);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('color', colors);
    const points = new THREE.Points(
      geo,
      new THREE.PointsMaterial({ size: spec.size, vertexColors: true, transparent: true, opacity: spec.opacity, depthWrite: false }),
    );
    points.frustumCulled = false;
    return { lag: spec.lag, points, pos };
  });
}

/** Position of a trail dot: the head's place on the arc, pulled back toward where it came from. */
export function trailParam(head: number, reversed: boolean, lag: number): number {
  const t = reversed ? head + lag : head - lag;
  return Math.min(1, Math.max(0, t));
}

/**
 * Soft studio lighting for reflections and depth. Returns a disposer, or null when the GPU
 * cannot build it (the scene then keeps its plain lights).
 */
export function applyEnvironment(renderer: THREE.WebGLRenderer, scene: THREE.Scene, intensity = 0.3): { dispose(): void } | null {
  try {
    const pmrem = new THREE.PMREMGenerator(renderer);
    const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = env;
    scene.environmentIntensity = intensity;
    pmrem.dispose();
    return { dispose: () => { env.dispose(); scene.environment = null; } };
  } catch {
    return null;
  }
}
