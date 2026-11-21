import { describe, expect, it } from 'vitest';
import { sketchKind, sketchRegion, sketchShapes, type SketchKind, type SketchShape } from './visualSketch';

const KINDS: SketchKind[] = ['bar', 'column', 'combo', 'line', 'area', 'pie', 'scatter', 'treemap', 'table', 'card', 'slicer'];

describe('sketchKind', () => {
  it.each([
    ['barChart', 'bar'], ['clusteredBarChart', 'bar'], ['stackedBarChart', 'bar'], ['hundredPercentStackedBarChart', 'bar'], ['funnel', 'bar'],
    ['columnChart', 'column'], ['clusteredColumnChart', 'column'], ['waterfallChart', 'column'], ['ribbonChart', 'column'],
    ['lineClusteredColumnComboChart', 'combo'], ['lineStackedColumnComboChart', 'combo'],
    ['lineChart', 'line'], ['areaChart', 'area'], ['stackedAreaChart', 'area'],
    ['pieChart', 'pie'], ['donutChart', 'pie'], ['scatterChart', 'scatter'], ['treemap', 'treemap'],
    ['tableEx', 'table'], ['pivotTable', 'table'], ['matrix', 'table'],
    ['card', 'card'], ['multiRowCard', 'card'], ['kpi', 'card'], ['gauge', 'card'],
    ['slicer', 'slicer'], ['advancedSlicerVisual', 'slicer'],
  ])('%s gets the %s sketch', (type, kind) => {
    expect(sketchKind(type)).toBe(kind);
  });

  it('treats any visual flagged as a slicer as a slicer', () => {
    expect(sketchKind('somethingNew', true)).toBe('slicer');
  });

  it('leaves text boxes, shapes, images, maps and unknown types as plain boxes', () => {
    for (const t of ['textbox', 'shape', 'image', 'actionButton', 'map', 'filledMap', 'decompositionTreeVisual', 'customVisual123', '', 'unknown']) {
      expect(sketchKind(t)).toBeNull();
    }
  });
});

describe('sketchRegion', () => {
  it('is null when the box is too small to read a sketch in', () => {
    expect(sketchRegion({ x: 0, y: 0, width: 70, height: 60 }, 12)).toBeNull();   // too short under the label
    expect(sketchRegion({ x: 0, y: 0, width: 60, height: 200 }, 12)).toBeNull();  // too narrow
  });

  it('sits inside the box, under the label', () => {
    const r = sketchRegion({ x: 100, y: 50, width: 400, height: 300 }, 14)!;
    expect(r).not.toBeNull();
    expect(r.x).toBeGreaterThanOrEqual(100);
    expect(r.y).toBeGreaterThanOrEqual(50 + 34 + 14);
    expect(r.x + r.w).toBeLessThanOrEqual(500);
    expect(r.y + r.h).toBeLessThanOrEqual(350);
  });
});

/** Is the shape inside the w by h box, allowing half a pixel for line caps? */
function inside(s: SketchShape, w: number, h: number): boolean {
  const e = 0.6;
  const ok = (x: number, y: number) => x >= -e && y >= -e && x <= w + e && y <= h + e;
  switch (s.t) {
    case 'rect': return s.w >= 0 && s.h >= 0 && ok(s.x, s.y) && ok(s.x + s.w, s.y + s.h);
    case 'line': return ok(s.x1, s.y1) && ok(s.x2, s.y2);
    case 'poly': return s.pts.every(([x, y]) => ok(x, y));
    case 'dot': return ok(s.cx - s.r, s.cy - s.r) && ok(s.cx + s.r, s.cy + s.r);
    case 'arc': { const o = s.r + s.sw / 2; return ok(s.cx - o, s.cy - o) && ok(s.cx + o, s.cy + o); }
  }
}

describe('sketchShapes', () => {
  const SIZES: Array<[number, number]> = [[56, 32], [120, 60], [200, 120], [380, 220], [800, 500], [90, 400]];

  it.each(KINDS)('%s draws something and stays inside its box at every size', (kind) => {
    for (const [w, h] of SIZES) {
      const shapes = sketchShapes(kind, w, h);
      expect(shapes.length).toBeGreaterThan(0);
      for (const s of shapes) expect(inside(s, w, h), `${kind} ${JSON.stringify(s)} at ${w}x${h}`).toBe(true);
    }
  });

  it.each(KINDS)('%s is the same every time, so it cannot pass for data', (kind) => {
    expect(sketchShapes(kind, 300, 160)).toEqual(sketchShapes(kind, 300, 160));
  });

  it('draws no text: the shape list has no label or number', () => {
    for (const kind of KINDS) {
      const json = JSON.stringify(sketchShapes(kind, 300, 160));
      expect(json).not.toMatch(/"text"|"label"|"title"|"value"/);
    }
  });

  it('draws a bar sketch as four bars of different lengths, longest first', () => {
    const bars = sketchShapes('bar', 200, 120).filter((s) => s.t === 'rect') as Array<Extract<SketchShape, { t: 'rect' }>>;
    expect(bars).toHaveLength(4);
    const lengths = bars.map((b) => b.w);
    expect([...lengths].sort((a, b) => b - a)).toEqual(lengths);
  });
});
