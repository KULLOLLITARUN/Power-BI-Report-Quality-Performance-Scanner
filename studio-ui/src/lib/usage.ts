// Where a measure is used, as the scan saw it: the evidence behind DAX_UNUSED_MEASURE.
// Reads semantic_references and dax_graph from the scan result; it does not decide
// anything the rule (pbiscan.rules.dax.check_unused_measures) has not already decided.
import type { ReferenceSourceType, ScanResult, SemanticReferenceInfo } from '../types';

export type UsageGroupId = 'visuals' | 'filters' | 'report_measures' | 'calc_groups' | 'field_parameters' | 'rls';

/** Display groups for reference source types. tests/unit/test_client_scanner_parity.py keeps a copy. */
export const USAGE_GROUPS: { id: UsageGroupId; label: string; sources: ReferenceSourceType[] }[] = [
  { id: 'visuals', label: 'Report visuals', sources: ['visual_projection', 'visual_property'] },
  { id: 'filters', label: 'Page and report filters, bookmarks', sources: ['visual_filter', 'report_filter'] },
  { id: 'report_measures', label: 'Report-level measures', sources: ['report_extension_measure'] },
  { id: 'calc_groups', label: 'Calculation groups', sources: ['calc_item_dax', 'calc_item_predicate'] },
  { id: 'field_parameters', label: 'Field parameters', sources: ['field_parameter', 'field_parameter_grouped'] },
  { id: 'rls', label: 'Row-level security roles', sources: ['rls_table_permission'] },
];

export interface UsageRow {
  id: UsageGroupId;
  label: string;
  /** References that make the measure count as used. */
  refs: SemanticReferenceInfo[];
  /** References found but not counted (e.g. a field parameter entry pbiscan could not confirm). */
  uncounted: SemanticReferenceInfo[];
}

export interface DaxReferrer {
  name: string;
  /** False when the referrer is itself unreachable, so its reference does not keep this measure alive. */
  used: boolean;
}

export interface MeasureEvidence {
  /** False for scan JSON from versions that did not export semantic_references. */
  hasReferences: boolean;
  hasGraph: boolean;
  rows: UsageRow[];
  /** Measures and calculated columns whose DAX names this measure. */
  referencedBy: DaxReferrer[];
  /** Used directly by a visual, filter, calculation group, field parameter or RLS role. */
  isRoot: boolean;
  /** isRoot, or referenced (through any chain) by a measure that is. */
  used: boolean;
}

const lower = (s: string) => s.toLowerCase();

/** Every node whose DAX reaches `name` through any chain of references. Mirrors transitive_referenced_by. */
function ancestors(name: string, referencedBy: Map<string, string[]>): Set<string> {
  const seen = new Set<string>();
  const stack = [...(referencedBy.get(lower(name)) ?? [])];
  while (stack.length) {
    const cur = stack.pop()!;
    if (seen.has(lower(cur))) continue;
    seen.add(lower(cur));
    stack.push(...(referencedBy.get(lower(cur)) ?? []));
  }
  return seen;
}

export function measureEvidence(name: string, scan: ScanResult): MeasureEvidence {
  const sem = scan.semantic_references;
  const graph = scan.dax_graph;
  const roots = new Set((sem?.active_roots ?? []).map(lower));
  const refs = (sem?.references ?? []).filter((r) => r.target_type === 'measure' && lower(r.target_name) === lower(name));

  const rows: UsageRow[] = USAGE_GROUPS.map((g) => {
    const inGroup = refs.filter((r) => g.sources.includes(r.source_type));
    return { id: g.id, label: g.label, refs: inGroup.filter((r) => r.activates_root), uncounted: inGroup.filter((r) => !r.activates_root) };
  });

  const referencedByMap = new Map<string, string[]>((graph?.nodes ?? []).map((n) => [lower(n.name), n.referenced_by]));
  const isUsed = (n: string) => roots.has(lower(n)) || [...ancestors(n, referencedByMap)].some((a) => roots.has(a));
  const referencedBy = (referencedByMap.get(lower(name)) ?? []).map((r) => ({ name: r, used: isUsed(r) }));

  return {
    hasReferences: !!sem,
    hasGraph: !!graph,
    rows,
    referencedBy,
    isRoot: roots.has(lower(name)),
    used: isUsed(name),
  };
}

/** "Page.visual" source objects grouped by page, for a compact visual summary. */
export function summarizeSources(refs: SemanticReferenceInfo[]): string[] {
  const counts = new Map<string, number>();
  for (const r of refs) counts.set(r.source_object || 'report', (counts.get(r.source_object || 'report') ?? 0) + 1);
  return [...counts].map(([obj, n]) => (n > 1 ? `${obj} ×${n}` : obj));
}
