import { describe, expect, it } from 'vitest';
import type { DaxGraphNode, ScanResult, SemanticReferenceInfo } from '../types';
import { measureEvidence, summarizeSources } from './usage';

const ref = (target: string, source_type: SemanticReferenceInfo['source_type'], opts: Partial<SemanticReferenceInfo> = {}): SemanticReferenceInfo => ({
  target_name: target,
  target_table: null,
  target_type: 'measure',
  source_type,
  source_object: 'Overview.card',
  source_file: '',
  source_expression: null,
  activates_root: true,
  ...opts,
});

const node = (name: string, referenced_by: string[] = [], references: string[] = []): DaxGraphNode => ({
  name, table: 'Sales', kind: 'measure', expression: '', references, referenced_by,
});

const scan = (refs: SemanticReferenceInfo[] | null, roots: string[], nodes: DaxGraphNode[] | null): ScanResult => ({
  report_name: 'r', source_path: '',
  scores: { overall: 100, category_scores: { model: 100, dax: 100, report: 100 } },
  findings: [], tables: [], relationships: [], measures: [], calculated_columns: [], pages: [], warnings: [],
  summary: { total_findings: 0, table_count: 0, relationship_count: 0, measure_count: 0, page_count: 0 },
  ...(refs ? { semantic_references: { total_count: refs.length, active_roots: roots, references: refs } } : {}),
  ...(nodes ? { dax_graph: { nodes, edges: [], has_cycles: false } } : {}),
});

const row = (ev: ReturnType<typeof measureEvidence>, id: string) => ev.rows.find((r) => r.id === id)!;

describe('measureEvidence', () => {
  it('groups references by where they were found, case-insensitively', () => {
    const s = scan([
      ref('Total Sales', 'visual_projection'),
      ref('total sales', 'visual_filter', { source_object: 'Overview.filters' }),
      ref('Total Sales', 'report_filter', { source_object: 'report' }),
      ref('Total Sales', 'calc_item_predicate'),
      ref('Total Sales', 'calc_item_dax'),
      ref('Total Sales', 'field_parameter_grouped'),
      ref('Total Sales', 'rls_table_permission'),
      ref('Total Sales', 'report_extension_measure'),
      ref('Other', 'visual_projection'),
      ref('Total Sales', 'visual_projection', { target_type: 'column' }),
    ], ['Total Sales'], [node('Total Sales')]);
    const ev = measureEvidence('Total Sales', s);
    expect(ev.rows.map((r) => [r.id, r.refs.length])).toEqual([
      ['visuals', 1], ['filters', 2], ['report_measures', 1], ['calc_groups', 2], ['field_parameters', 1], ['rls', 1],
    ]);
    expect(ev.isRoot).toBe(true);
    expect(ev.used).toBe(true);
  });

  it('shows an unused measure with every place empty', () => {
    const ev = measureEvidence('Orphan', scan([ref('Total Sales', 'visual_projection')], ['Total Sales'], [node('Orphan'), node('Total Sales')]));
    expect(ev.rows.every((r) => r.refs.length === 0)).toBe(true);
    expect(ev.referencedBy).toEqual([]);
    expect(ev.used).toBe(false);
  });

  it('follows DAX references through chains and marks referrers that are themselves unused', () => {
    const nodes = [
      node('Base', ['Mid', 'Dead']),
      node('Mid', ['Top'], ['Base']),
      node('Top', [], ['Mid']),
      node('Dead', [], ['Base']),
      node('Lonely', ['Dead']),
    ];
    const s = scan([ref('Top', 'visual_projection')], ['Top'], nodes);
    const base = measureEvidence('Base', s);
    expect(base.isRoot).toBe(false);
    expect(base.used).toBe(true);
    expect(base.referencedBy).toEqual([{ name: 'Mid', used: true }, { name: 'Dead', used: false }]);
    expect(measureEvidence('Lonely', s).used).toBe(false);
  });

  it('survives reference cycles', () => {
    const s = scan([], [], [node('A', ['B']), node('B', ['A'])]);
    expect(measureEvidence('A', s).used).toBe(false);
  });

  it('keeps references that do not count as a use apart', () => {
    const ev = measureEvidence('M', scan([ref('M', 'field_parameter', { activates_root: false })], [], [node('M')]));
    expect(row(ev, 'field_parameters').refs).toEqual([]);
    expect(row(ev, 'field_parameters').uncounted).toHaveLength(1);
  });

  it('reports missing data for older scan JSON', () => {
    const ev = measureEvidence('M', scan(null, [], null));
    expect(ev.hasReferences).toBe(false);
    expect(ev.hasGraph).toBe(false);
  });
});

describe('summarizeSources', () => {
  it('counts repeated sources', () => {
    expect(summarizeSources([ref('M', 'visual_projection'), ref('M', 'visual_projection'), ref('M', 'visual_projection', { source_object: 'Detail.table' })]))
      .toEqual(['Overview.card ×2', 'Detail.table']);
  });
});
