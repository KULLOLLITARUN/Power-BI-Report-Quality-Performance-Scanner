import { describe, expect, it } from 'vitest';
import type { AuditFinding, ColumnInfo, MeasureInfo, PageInfo, RelationshipInfo, ScanResult, TableInfo, VisualInfo } from '../types';
import { classifyTables, findingTargets, isManySide, relKey, tablesInText, visualTables } from './model';

const col = (name: string): ColumnInfo => ({ name, data_type: 'string', is_unique: false, in_relationship: false, hidden: false });

const table = (name: string, opts: Partial<TableInfo> = {}): TableInfo => ({
  name,
  hidden: false,
  is_date_table: false,
  column_count: opts.columns?.length ?? 0,
  columns: [],
  measures_count: 0,
  calc_cols_count: 0,
  ...opts,
});

const rel = (from_table: string, to_table: string, opts: Partial<RelationshipInfo> = {}): RelationshipInfo => ({
  from_table,
  from_column: `${to_table}Key`,
  to_table,
  to_column: `${to_table}Key`,
  cardinality: 'oneToMany',
  cross_filter_direction: 'single',
  is_active: true,
  ...opts,
});

const measure = (name: string, tableName: string): MeasureInfo => ({ name, table: tableName, expression: '1', hidden: false });

const finding = (opts: Partial<AuditFinding>): AuditFinding => ({
  rule_id: 'X',
  category: 'model',
  severity: 'MEDIUM',
  title: '',
  issue: '',
  evidence: '',
  impact: '',
  recommendation: '',
  confidence: 1,
  ...opts,
});

const visual = (opts: Partial<VisualInfo>): VisualInfo => ({
  visual_type: 'card',
  x: 0,
  y: 0,
  width: 100,
  height: 100,
  measure_refs: [],
  fields_used: [],
  table_refs: [],
  is_slicer: false,
  hidden: false,
  ...opts,
});

const scan = (opts: Partial<ScanResult>): ScanResult => ({
  report_name: 'r',
  source_path: '',
  scores: { overall: 100, category_scores: { model: 100, dax: 100, report: 100 } },
  findings: [],
  tables: [],
  relationships: [],
  measures: [],
  calculated_columns: [],
  pages: [],
  warnings: [],
  summary: { total_findings: 0, table_count: 0, relationship_count: 0, measure_count: 0, page_count: 0 },
  ...opts,
});

describe('isManySide', () => {
  it('treats the from table of a oneToMany relationship as the many side', () => {
    const r = rel('Sales', 'Customer');
    expect(isManySide(r, 'from')).toBe(true);
    expect(isManySide(r, 'to')).toBe(false);
  });

  it('handles oneToOne and manyToMany', () => {
    expect(isManySide(rel('A', 'B', { cardinality: 'oneToOne' }), 'from')).toBe(false);
    expect(isManySide(rel('A', 'B', { cardinality: 'oneToOne' }), 'to')).toBe(false);
    expect(isManySide(rel('A', 'B', { cardinality: 'manyToMany' }), 'from')).toBe(true);
    expect(isManySide(rel('A', 'B', { cardinality: 'manyToMany' }), 'to')).toBe(true);
  });
});

describe('classifyTables', () => {
  it('marks tables named like facts as fact even without relationships', () => {
    const roles = classifyTables([table('FactSales'), table('fct_orders'), table('f_returns')], []);
    expect(roles.get('FactSales')).toBe('fact');
    expect(roles.get('fct_orders')).toBe('fact');
    expect(roles.get('f_returns')).toBe('fact');
  });

  it('marks the many side of two or more relationships as fact and the one sides as dim', () => {
    const tables = [table('Orders'), table('Customer'), table('Product'), table('Notes')];
    const roles = classifyTables(tables, [rel('Orders', 'Customer'), rel('Orders', 'Product')]);
    expect(roles.get('Orders')).toBe('fact');
    expect(roles.get('Customer')).toBe('dim');
    expect(roles.get('Product')).toBe('dim');
    expect(roles.get('Notes')).toBe('other');
  });

  it('does not count a single many side, or many-to-many sides, towards fact', () => {
    const tables = [table('Orders'), table('Customer'), table('Bridge'), table('Region')];
    const roles = classifyTables(tables, [
      rel('Orders', 'Customer'),
      rel('Bridge', 'Region', { cardinality: 'manyToMany' }),
      rel('Bridge', 'Customer', { cardinality: 'manyToMany' }),
    ]);
    expect(roles.get('Orders')).toBe('dim');
    expect(roles.get('Bridge')).toBe('dim');
  });

  it('marks date tables via is_date_table or a calendar-like name', () => {
    const tables = [table('Periods', { is_date_table: true }), table('Calendar'), table('Dim Date'), table('Dates'), table('DateOfBirth')];
    const roles = classifyTables(tables, [rel('Periods', 'X'), rel('Periods', 'Y')]);
    expect(roles.get('Periods')).toBe('date');
    expect(roles.get('Calendar')).toBe('date');
    expect(roles.get('Dim Date')).toBe('date');
    expect(roles.get('Dates')).toBe('date');
    expect(roles.get('DateOfBirth')).toBe('other');
  });
});

describe('tablesInText', () => {
  it('does not also match "Sales" inside "FactSales"', () => {
    expect(tablesInText('Relationship FactSales[CustomerKey] is bidirectional', ['Sales', 'FactSales'])).toEqual(['FactSales']);
  });

  it('matches both when both are mentioned, and quoted names', () => {
    expect(tablesInText("'Sales' and FactSales", ['Sales', 'FactSales']).sort()).toEqual(['FactSales', 'Sales']);
  });

  it('requires word boundaries and handles empty text', () => {
    expect(tablesInText('SalesTarget', ['Sales'])).toEqual([]);
    expect(tablesInText('', ['Sales'])).toEqual([]);
  });
});

describe('findingTargets', () => {
  const tables = [table('Sales', { columns: [col('CustomerKey')] }), table('Customer', { columns: [col('CustomerKey')] }), table('Product')];
  const relationships = [rel('Sales', 'Customer'), rel('Sales', 'Product')];
  const measures = [measure('Total Sales', 'Sales'), measure('Total Sales', 'Product')];
  const pages: PageInfo[] = [{ name: 'ReportSection1', display_name: 'Overview', is_hidden: false, visual_count: 0, slicer_count: 0 }];
  const s = scan({ tables, relationships, measures, pages });

  it('resolves relationship findings to both tables and the relationship key', () => {
    const t = findingTargets(finding({ category: 'model', location: 'Sales[CustomerKey] -> Customer[CustomerKey]' }), s);
    expect(t.tables.sort()).toEqual(['Customer', 'Sales']);
    expect(t.rels).toEqual([relKey(relationships[0])]);
    expect(t.page).toBeNull();
  });

  it('resolves measure findings via "Table[Measure]", preferring the named table', () => {
    const t = findingTargets(finding({ category: 'dax', location: 'Product[Total Sales]' }), s);
    expect(t.measure).toEqual({ name: 'Total Sales', table: 'Product' });
    expect(t.tables).toContain('Product');
  });

  it('accepts a quoted table and falls back to the measure name alone', () => {
    expect(findingTargets(finding({ category: 'dax', location: "'Sales'[Total Sales]" }), s).measure).toEqual({ name: 'Total Sales', table: 'Sales' });
    expect(findingTargets(finding({ category: 'dax', location: 'Elsewhere[Total Sales]' }), s).measure?.name).toBe('Total Sales');
  });

  it('resolves page findings by display name and does not touch tables', () => {
    const t = findingTargets(finding({ category: 'report', issue: "Page 'Overview' has 40 visuals mentioning Sales" }), s);
    expect(t.page).toBe('ReportSection1');
    expect(t.tables).toEqual([]);
  });
});

describe('visualTables', () => {
  const tables = [
    table('Sales', { columns: [col('Amount'), col('Region')] }),
    table('Customer', { columns: [col('Name'), col('Region')] }),
  ];
  const s = scan({ tables, measures: [measure('Total Sales', 'Sales')] });

  it('uses table_refs first, ignoring unknown tables', () => {
    expect(visualTables(visual({ table_refs: ['Customer', 'Ghost'], measure_refs: ['Total Sales'] }), s)).toEqual(['Customer']);
  });

  it('falls back to measure and unambiguous column names', () => {
    expect(visualTables(visual({ measure_refs: ['total sales'], fields_used: ['Name', 'Region'] }), s).sort()).toEqual(['Customer', 'Sales']);
  });

  it('skips column names owned by more than one table', () => {
    expect(visualTables(visual({ fields_used: ['Region'] }), s)).toEqual([]);
  });
});
