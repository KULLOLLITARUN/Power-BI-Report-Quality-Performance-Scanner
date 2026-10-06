// Read-side helpers that connect findings, tables, relationships, measures and
// report visuals. Nothing here changes what a scan reports; it only decides
// what the Studio highlights.
import type { AuditFinding, MeasureInfo, PageInfo, RelationshipInfo, ScanResult, TableInfo, VisualInfo } from '../types';
import { worstSeverity, type Severity } from './severity';

export type TableRole = 'fact' | 'dim' | 'date' | 'other';

/** Hidden tables Power BI generates for Auto date/time; drawn as a count, not as boxes. */
export const isAutoDateTable = (name: string) => /^(LocalDateTable_|DateTableTemplate_)/i.test(name);

export const relKey = (r: RelationshipInfo) => `${r.from_table}.${r.from_column}->${r.to_table}.${r.to_column}`;

const norm = (s: string) => (s || '').toLowerCase();

/** pbiscan's "oneToMany" is any ordinary relationship: TMDL's default is fromCardinality many,
 * toCardinality one (CanonicalBuilder._parse_cardinality), so the from table is the many side. */
export function isManySide(r: RelationshipInfo, side: 'from' | 'to'): boolean {
  const c = norm(r.cardinality);
  if (c === 'manytomany') return true;
  if (c === 'onetoone') return false;
  return side === 'from';
}

export function isBidirectional(r: RelationshipInfo): boolean {
  const d = norm(r.cross_filter_direction);
  return d === 'both' || d === 'bothdirections';
}

export function cardinalityLabel(r: RelationshipInfo): [string, string] {
  return [isManySide(r, 'from') ? '*' : '1', isManySide(r, 'to') ? '*' : '1'];
}

/** Fact = on the many side of two or more relationships (or named like one); date = marked or calendar-like. */
export function classifyTables(tables: TableInfo[], rels: RelationshipInfo[]): Map<string, TableRole> {
  const manySides = new Map<string, number>();
  const linked = new Set<string>();
  for (const r of rels) {
    linked.add(r.from_table); linked.add(r.to_table);
    if (isManySide(r, 'from') && !isManySide(r, 'to')) manySides.set(r.from_table, (manySides.get(r.from_table) ?? 0) + 1);
    if (isManySide(r, 'to') && !isManySide(r, 'from')) manySides.set(r.to_table, (manySides.get(r.to_table) ?? 0) + 1);
  }
  const roles = new Map<string, TableRole>();
  for (const t of tables) {
    const n = t.name;
    let role: TableRole;
    if (t.is_date_table || /^(dim)?_?(date|calendar|dates)$/i.test(n.replace(/\s+/g, ''))) role = 'date';
    else if (/^(fact|fct|f_)/i.test(n) || (manySides.get(n) ?? 0) >= 2) role = 'fact';
    else if (linked.has(n)) role = 'dim';
    else role = 'other';
    roles.set(n, role);
  }
  return roles;
}

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Table names mentioned in a finding's location/evidence/issue text, longest names first so "FactSales" wins over "Sales". */
export function tablesInText(text: string, tableNames: string[]): string[] {
  if (!text) return [];
  let rest = text;
  const found: string[] = [];
  for (const name of [...tableNames].sort((a, b) => b.length - a.length)) {
    const re = new RegExp(`(^|[^\\w])'?${escapeRe(name)}'?(?=$|[^\\w])`, 'g');
    if (re.test(rest)) {
      found.push(name);
      rest = rest.replace(re, '$1\u0000');
    }
  }
  return found;
}

export interface FindingTargets {
  tables: string[];
  rels: string[];
  page: string | null;
  measure: { name: string; table: string } | null;
}

export function findingTargets(f: AuditFinding, scan: ScanResult): FindingTargets {
  const tableNames = (scan.tables || []).map((t) => t.name);
  const text = [f.location, f.evidence, f.issue].filter(Boolean).join('  ');
  const out: FindingTargets = { tables: [], rels: [], page: null, measure: null };

  // Measures: "Table[Measure]" in the location, or a quoted measure name the model has.
  const m = /([^[\]]+)\[([^\]]+)\]/.exec(f.location || '');
  const measures = scan.measures || [];
  if (f.category === 'dax') {
    const hit = m
      ? measures.find((x) => norm(x.name) === norm(m[2]) && norm(x.table) === norm(m[1].replace(/^Table:\s*|'/g, '').trim()))
        ?? measures.find((x) => norm(x.name) === norm(m[2]))
      : measures.find((x) => text.includes(`'${x.name}'`) || text.includes(`[${x.name}]`));
    if (hit) out.measure = { name: hit.name, table: hit.table };
  }

  if (f.category === 'report') {
    const page = (scan.pages || []).find((p) => text.includes(`'${p.display_name}'`) || text.includes(p.display_name) || text.includes(p.name));
    out.page = page ? page.name : null;
    return out;
  }

  out.tables = tablesInText(text, tableNames);
  if (out.measure && !out.tables.includes(out.measure.table)) out.tables.push(out.measure.table);

  if (f.category === 'model' && out.tables.length >= 2) {
    const set = new Set(out.tables);
    const candidates = (scan.relationships || []).filter((r) => set.has(r.from_table) && set.has(r.to_table));
    const byColumn = candidates.filter((r) => text.includes(r.from_column) || text.includes(r.to_column));
    out.rels = (byColumn.length ? byColumn : candidates).map(relKey);
  }
  return out;
}

/** Worst open finding per table and per relationship, for colouring the map. */
export function severityIndex(scan: ScanResult, findings: AuditFinding[]) {
  const tables = new Map<string, Severity[]>();
  const rels = new Map<string, Severity[]>();
  for (const f of findings) {
    const t = findingTargets(f, scan);
    for (const name of t.tables) tables.set(name, [...(tables.get(name) ?? []), f.severity]);
    for (const key of t.rels) rels.set(key, [...(rels.get(key) ?? []), f.severity]);
  }
  const collapse = (m: Map<string, Severity[]>) => new Map([...m].map(([k, v]) => [k, worstSeverity(v)!]));
  return { tables: collapse(tables), rels: collapse(rels) };
}

/** Model tables a visual reads: its table_refs, else whatever its measure/field names resolve to. */
export function visualTables(v: VisualInfo, scan: ScanResult): string[] {
  const known = new Set((scan.tables || []).map((t) => t.name));
  const out = new Set<string>((v.table_refs || []).filter((t) => known.has(t)));
  if (out.size) return [...out];
  const measures = new Map((scan.measures || []).map((m) => [norm(m.name), m.table]));
  const columnOwners = new Map<string, string[]>();
  for (const t of scan.tables || []) {
    for (const c of t.columns || []) columnOwners.set(norm(c.name), [...(columnOwners.get(norm(c.name)) ?? []), t.name]);
  }
  for (const f of [...(v.measure_refs || []), ...(v.fields_used || [])]) {
    const home = measures.get(norm(f));
    if (home) { out.add(home); continue; }
    const owners = columnOwners.get(norm(f));
    if (owners && owners.length === 1) out.add(owners[0]);
  }
  return [...out].filter((t) => known.has(t));
}

/** Pages and visual counts that use a measure (directly, via measure_refs). */
export function measureUsage(measure: MeasureInfo, pages: PageInfo[]) {
  const name = norm(measure.name);
  const usage: { page: PageInfo; visuals: number }[] = [];
  for (const p of pages) {
    const n = (p.visuals || []).filter((v) => (v.measure_refs || []).some((r) => norm(r) === name)).length;
    if (n) usage.push({ page: p, visuals: n });
  }
  return usage;
}

/** Visuals in reading order (top-to-bottom, then left-to-right). */
export function readingOrder(visuals: VisualInfo[]): VisualInfo[] {
  return [...visuals].sort((a, b) => (Math.abs(a.y - b.y) > 20 ? a.y - b.y : a.x - b.x));
}

export const VISUAL_LIMIT = 15;
