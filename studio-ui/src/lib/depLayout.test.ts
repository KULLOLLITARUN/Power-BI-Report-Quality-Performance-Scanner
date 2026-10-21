import { describe, expect, it } from 'vitest';
import type { DaxGraphNode, ScanResult } from '../types';
import { buildDepLayout } from './depLayout';

const node = (name: string, references: string[] = [], referenced_by: string[] = []): DaxGraphNode => ({
  name, table: 'Sales', kind: 'measure', expression: '', references, referenced_by,
});

const scan = (nodes: DaxGraphNode[], roots: string[] | null): ScanResult => ({
  report_name: 'r', source_path: '',
  scores: { overall: 100, category_scores: { model: 100, dax: 100, report: 100 } },
  findings: [], tables: [], relationships: [], measures: [], calculated_columns: [], pages: [], warnings: [],
  summary: { total_findings: 0, table_count: 0, relationship_count: 0, measure_count: 0, page_count: 0 },
  dax_graph: { nodes, edges: [], has_cycles: false },
  ...(roots ? { semantic_references: { total_count: 0, active_roots: roots, references: [] } } : {}),
});

const by = (l: NonNullable<ReturnType<typeof buildDepLayout>>, name: string) => l.nodes.find((n) => n.name === name)!;

describe('buildDepLayout', () => {
  it('returns null without graph data', () => {
    expect(buildDepLayout({ ...scan([], null), dax_graph: undefined })).toBeNull();
    expect(buildDepLayout(scan([], null))).toBeNull();
  });

  it('stacks a chain bottom to top and takes the longest path for diamonds', () => {
    const l = buildDepLayout(scan([
      node('Base', [], ['Mid', 'Top']),
      node('Mid', ['Base'], ['Top']),
      node('Top', ['Base', 'Mid']),
    ], ['Top']))!;
    expect([by(l, 'Base').level, by(l, 'Mid').level, by(l, 'Top').level]).toEqual([0, 1, 2]);
    expect(by(l, 'Top').y).toBeGreaterThan(by(l, 'Mid').y);
    expect(l.levels).toBe(3);
    expect(l.edges).toHaveLength(3);
  });

  it('marks what the report reaches as used and the rest as unused', () => {
    const l = buildDepLayout(scan([
      node('Base', [], ['Top']),
      node('Top', ['Base']),
      node('Orphan'),
    ], ['Top']))!;
    expect(by(l, 'Top').isRoot).toBe(true);
    expect(by(l, 'Base').used).toBe(true);
    expect(by(l, 'Orphan').used).toBe(false);
    expect(l.unusedCount).toBe(1);
  });

  it('matches names case-insensitively', () => {
    const l = buildDepLayout(scan([node('Base', [], ['Top']), node('Top', ['base'])], ['top']))!;
    expect(by(l, 'Base').used).toBe(true);
    expect(l.edges).toEqual([{ from: 'top', to: 'base' }]);
  });

  it('reports used as unknown when the scan has no reference data', () => {
    const l = buildDepLayout(scan([node('A')], null))!;
    expect(by(l, 'A').used).toBeNull();
    expect(l.unusedCount).toBe(0);
  });

  it('terminates on cycles', () => {
    const l = buildDepLayout(scan([node('A', ['B'], ['B']), node('B', ['A'], ['A'])], ['A']))!;
    expect(l.nodes).toHaveLength(2);
    expect(by(l, 'A').used).toBe(true);
    expect(by(l, 'B').used).toBe(true);
  });

  it('does not place two nodes of a level on the same spot', () => {
    const l = buildDepLayout(scan(Array.from({ length: 10 }, (_, i) => node(`M${i}`)), []))!;
    const spots = new Set(l.nodes.map((n) => `${n.x},${n.z}`));
    expect(spots.size).toBe(10);
  });
});
