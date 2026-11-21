/**
 * Layout sketches for the page preview.
 *
 * pbiscan never reads a report's data, so a visual is drawn as a fixed pictogram of its KIND
 * (bars, a line, a grid ...). The shapes are the same every time, carry no text and no numbers,
 * and never depend on the visual's fields, so they cannot be mistaken for real values.
 */

export type SketchKind =
  | 'bar' | 'column' | 'combo' | 'line' | 'area' | 'pie' | 'scatter' | 'treemap'
  | 'table' | 'card' | 'slicer';

/** One drawing primitive, in coordinates local to the sketch box (0,0 to w,h). */
export type SketchShape =
  | { t: 'rect'; x: number; y: number; w: number; h: number; tone: 'soft' | 'solid' }
  | { t: 'line'; x1: number; y1: number; x2: number; y2: number }
  | { t: 'poly'; pts: Array<[number, number]>; closed: boolean }
  | { t: 'dot'; cx: number; cy: number; r: number }
  | { t: 'arc'; cx: number; cy: number; r: number; sw: number; a0: number; a1: number; tone: 1 | 2 | 3 };

const CARD_TYPES = new Set(['card', 'multirowcard', 'kpi', 'gauge', 'cardvisual', 'scorecard']);
const TABLE_TYPES = new Set(['tableex', 'matrix', 'pivottable', 'table']);

/** The sketch for a visual type, or null when the plain box is the honest picture. */
export function sketchKind(visualType: string, isSlicer?: boolean): SketchKind | null {
  const t = (visualType || '').toLowerCase().trim();
  if (isSlicer || t.includes('slicer')) return 'slicer';
  if (CARD_TYPES.has(t)) return 'card';
  if (TABLE_TYPES.has(t)) return 'table';
  if (t.includes('combochart')) return 'combo';
  if (t === 'piechart' || t === 'donutchart') return 'pie';
  if (t === 'scatterchart' || t === 'bubblechart') return 'scatter';
  if (t === 'treemap') return 'treemap';
  if (t === 'areachart' || t === 'stackedareachart') return 'area';
  if (t === 'linechart') return 'line';
  if (t === 'funnel' || t.includes('barchart')) return 'bar';
  if (t.includes('columnchart') || t === 'waterfallchart' || t === 'ribbonchart') return 'column';
  return null;
}

/** Room inside a visual's box under its label, or null when it is too small for a readable sketch. */
export function sketchRegion(
  v: { x: number; y: number; width: number; height: number },
  labelFontSize: number,
): { x: number; y: number; w: number; h: number } | null {
  // The label sits at y + 12 + 16 (badge) + font size; leave a little air below it.
  const top = 34 + labelFontSize;
  const w = v.width - 20;
  const h = v.height - top - 8;
  if (w < 56 || h < 32) return null;
  return { x: v.x + 10, y: v.y + top, w, h };
}

const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));

function bars(w: number, h: number, scale = 1): SketchShape[] {
  const fracs = [0.5, 0.78, 0.62, 0.9, 0.45];
  const n = fracs.length;
  const bw = w / (n * 1.7);
  const gap = (w - n * bw) / (n - 1);
  const out: SketchShape[] = fracs.map((f, i) => {
    const bh = Math.max(3, (h - 2) * f * scale);
    return { t: 'rect' as const, x: i * (bw + gap), y: h - 1 - bh, w: bw, h: bh, tone: 'soft' as const };
  });
  out.push({ t: 'line', x1: 0, y1: h - 0.5, x2: w, y2: h - 0.5 });
  return out;
}

const LINE_POINTS: Array<[number, number]> = [[0, 0.7], [0.25, 0.45], [0.5, 0.6], [0.75, 0.25], [1, 0.4]];

/** Fixed shapes for a sketch kind inside a w by h box. Same input, same output. */
export function sketchShapes(kind: SketchKind, w: number, h: number): SketchShape[] {
  switch (kind) {
    case 'bar': {
      const fracs = [0.92, 0.7, 0.52, 0.34];
      const t = clamp(h / (fracs.length * 1.7), 3, 14);
      const g = t * 0.7;
      const total = fracs.length * t + (fracs.length - 1) * g;
      const y0 = (h - total) / 2;
      const out: SketchShape[] = fracs.map((f, i) => ({
        t: 'rect' as const, x: 2, y: y0 + i * (t + g), w: Math.max(3, (w - 2) * f), h: t, tone: 'soft' as const,
      }));
      out.push({ t: 'line', x1: 0.5, y1: y0 - 2, x2: 0.5, y2: y0 + total + 2 });
      return out;
    }
    case 'column':
      return bars(w, h);
    case 'combo': {
      const out = bars(w, h, 0.8);
      out.push({ t: 'poly', closed: false, pts: LINE_POINTS.map(([px, py]) => [px * w, py * (h - 4) + 2] as [number, number]) });
      return out;
    }
    case 'line':
    case 'area': {
      const pts = LINE_POINTS.map(([px, py]) => [px * w, py * (h - 4) + 2] as [number, number]);
      const out: SketchShape[] = [];
      if (kind === 'area') out.push({ t: 'poly', closed: true, pts: [[0, h - 0.5], ...pts, [w, h - 0.5]] });
      else out.push({ t: 'line', x1: 0.5, y1: 0, x2: 0.5, y2: h });
      out.push({ t: 'line', x1: 0, y1: h - 0.5, x2: w, y2: h - 0.5 });
      out.push({ t: 'poly', closed: false, pts });
      return out;
    }
    case 'pie': {
      const r = Math.min(w, h) / 2;
      const sw = r * 0.44;
      const ring = r - sw / 2;
      const cx = w / 2, cy = h / 2;
      return [
        { t: 'arc', cx, cy, r: ring, sw, a0: 0, a1: 0.5, tone: 1 },
        { t: 'arc', cx, cy, r: ring, sw, a0: 0.5, a1: 0.8, tone: 2 },
        { t: 'arc', cx, cy, r: ring, sw, a0: 0.8, a1: 1, tone: 3 },
      ];
    }
    case 'scatter': {
      const r = clamp(Math.min(w, h) / 14, 2.5, 6);
      const spots: Array<[number, number]> = [[0.1, 0.8], [0.22, 0.55], [0.35, 0.7], [0.5, 0.4], [0.62, 0.55], [0.78, 0.25], [0.9, 0.35]];
      const out: SketchShape[] = spots.map(([px, py]) => ({
        t: 'dot' as const, cx: r + px * (w - 2 * r), cy: r + py * (h - 2 * r), r,
      }));
      out.push({ t: 'line', x1: 0.5, y1: 0, x2: 0.5, y2: h });
      out.push({ t: 'line', x1: 0, y1: h - 0.5, x2: w, y2: h - 0.5 });
      return out;
    }
    case 'treemap': {
      const g = 2;
      const lw = w * 0.55 - g / 2;
      const rx = w * 0.55 + g / 2;
      const rw = w - rx;
      const th = h * 0.58 - g / 2;
      const by = h * 0.58 + g / 2;
      const bh = h - by;
      return [
        { t: 'rect', x: 0, y: 0, w: lw, h, tone: 'soft' },
        { t: 'rect', x: rx, y: 0, w: rw, h: th, tone: 'soft' },
        { t: 'rect', x: rx, y: by, w: rw * 0.5 - g / 2, h: bh, tone: 'soft' },
        { t: 'rect', x: rx + rw * 0.5 + g / 2, y: by, w: rw * 0.5 - g / 2, h: bh, tone: 'soft' },
      ];
    }
    case 'table': {
      const head = clamp(h * 0.18, 6, 14);
      const rows = Math.max(1, Math.min(5, Math.floor((h - head) / 12)));
      const out: SketchShape[] = [{ t: 'rect', x: 0, y: 0, w, h: head, tone: 'soft' }];
      for (let i = 1; i <= rows; i++) {
        const y = head + ((h - head) * i) / (rows + 0.5);
        out.push({ t: 'line', x1: 0, y1: y, x2: w, y2: y });
      }
      for (let c = 1; c < 3; c++) out.push({ t: 'line', x1: (w * c) / 3, y1: 0, x2: (w * c) / 3, y2: h });
      return out;
    }
    case 'card':
      return [
        { t: 'rect', x: w * 0.2, y: h * 0.2, w: w * 0.6, h: h * 0.38, tone: 'solid' },
        { t: 'rect', x: w * 0.3, y: h * 0.68, w: w * 0.4, h: Math.min(5, h * 0.1), tone: 'soft' },
      ];
    case 'slicer': {
      const rows = h >= 54 ? 3 : 2;
      const s = clamp(h / (rows * 2), 5, 10);
      const step = (h - s) / (rows - 1);
      const out: SketchShape[] = [];
      for (let i = 0; i < rows; i++) {
        const y = i * step;
        out.push({ t: 'rect', x: 0, y, w: s, h: s, tone: i === 0 ? 'solid' : 'soft' });
        out.push({ t: 'line', x1: s + 6, y1: y + s / 2, x2: w * 0.72, y2: y + s / 2 });
      }
      return out;
    }
  }
}
