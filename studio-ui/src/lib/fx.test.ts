import { describe, expect, it } from 'vitest';
import { pulsePhase, trailParam } from './fx';

describe('trailParam', () => {
  it('sits behind a forward flow, toward where it started', () => {
    expect(trailParam(0.5, false, 0.05)).toBeCloseTo(0.45);
  });
  it('sits behind a reversed flow, toward where it started', () => {
    // a reversed flow runs from 1 down to 0, so "behind" is the larger value
    expect(trailParam(0.5, true, 0.05)).toBeCloseTo(0.55);
  });
  it('never leaves the arc', () => {
    expect(trailParam(0.01, false, 0.07)).toBe(0);
    expect(trailParam(0.99, true, 0.07)).toBe(1);
  });
});

describe('pulsePhase', () => {
  it('repeats in the range 0 to 1', () => {
    for (let t = 0; t < 20; t += 0.37) {
      const p = pulsePhase(t, 0.2, false);
      expect(p).toBeGreaterThanOrEqual(0);
      expect(p).toBeLessThan(1);
    }
  });
  it('is still when motion is reduced', () => {
    expect(pulsePhase(0, 0, true)).toBe(pulsePhase(123.4, 0.9, true));
  });
});
