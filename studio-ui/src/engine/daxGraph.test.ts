import { describe, expect, it } from 'vitest';
import { buildDaxGraph, serializeDaxGraph } from './daxGraph';

describe('serializeDaxGraph', () => {
  it('emits nodes, edges and reverse references shaped like the Python scan output', () => {
    const measures = [
      { name: 'Total', table: 'Sales', expression: 'SUM(Sales[Amount])' },
      { name: 'Margin', table: 'Sales', expression: '[total] * 0.2' },
    ];
    const calcCols = [{ name: 'Band', table: 'Sales', expression: 'IF([Margin] > 1, "hi", "lo")' }];
    const out = serializeDaxGraph(buildDaxGraph(measures, calcCols), measures);
    expect(out.nodes).toEqual([
      { name: 'Total', table: 'Sales', kind: 'measure', expression: 'SUM(Sales[Amount])', references: [], referenced_by: ['Margin'] },
      { name: 'Margin', table: 'Sales', kind: 'measure', expression: '[total] * 0.2', references: ['Total'], referenced_by: ['Band'] },
      { name: 'Band', table: 'Sales', kind: 'calculated_column', expression: '', references: ['Margin'], referenced_by: [] },
    ]);
    expect(out.edges).toEqual([{ source: 'Margin', target: 'Total' }, { source: 'Band', target: 'Margin' }]);
    expect(out.has_cycles).toBe(false);
    expect(out.cycles).toEqual([]);
  });

  it('reports cycles closed by their first node', () => {
    const measures = [
      { name: 'A', table: 'T', expression: '[B]' },
      { name: 'B', table: 'T', expression: '[A]' },
    ];
    const out = serializeDaxGraph(buildDaxGraph(measures, []), measures);
    expect(out.has_cycles).toBe(true);
    expect(out.cycles).toEqual([['A', 'B', 'A']]);
  });
});
