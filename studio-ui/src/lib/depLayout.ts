// Layout for the 3D measure dependency graph. Height is the dependency depth:
// a measure that references nothing sits on the floor, and every measure sits one
// level above the highest thing it references, so a chain reads bottom to top.
// Nothing here changes what a scan reports; it only decides where nodes are drawn.
import type { DaxGraphNode, ScanResult } from '../types';

export interface DepNode {
  id: string;
  name: string;
  table: string;
  kind: string;
  /** 0 = references no other measure or column. */
  level: number;
  /** Used directly by the report (a semantic-reference root). */
  isRoot: boolean;
  /** Reachable from a root. null when the scan carries no reference data. */
  used: boolean | null;
  references: string[];
  referencedBy: string[];
  x: number; y: number; z: number;
}

export interface DepEdge { from: string; to: string }

export interface DepLayout {
  nodes: DepNode[];
  edges: DepEdge[];
  levels: number;
  /** Measures nothing in the report reaches; these are the candidates `pbiscan fix` would remove. */
  unusedCount: number;
}

export const LEVEL_GAP = 2.6;
export const NODE_GAP = 1.7;

const lower = (s: string) => (s || '').toLowerCase();

/** Longest path down to a node that references nothing. A cycle edge counts as zero so it terminates. */
function levelsOf(nodes: DaxGraphNode[]): Map<string, number> {
  const refs = new Map(nodes.map((n) => [lower(n.name), n.references.map(lower)]));
  const level = new Map<string, number>();
  const onPath = new Set<string>();
  const visit = (id: string): number => {
    const known = level.get(id);
    if (known !== undefined) return known;
    if (onPath.has(id)) return -1;
    onPath.add(id);
    let best = -1;
    for (const r of refs.get(id) ?? []) if (refs.has(r)) best = Math.max(best, visit(r));
    onPath.delete(id);
    level.set(id, best + 1);
    return best + 1;
  };
  for (const id of refs.keys()) visit(id);
  return level;
}

/** Everything reachable by following references down from the report's roots. */
function usedSet(nodes: DaxGraphNode[], roots: string[]): Set<string> {
  const refs = new Map(nodes.map((n) => [lower(n.name), n.references.map(lower)]));
  const seen = new Set<string>();
  const stack = roots.map(lower).filter((r) => refs.has(r));
  while (stack.length) {
    const cur = stack.pop()!;
    if (seen.has(cur)) continue;
    seen.add(cur);
    stack.push(...(refs.get(cur) ?? []));
  }
  return seen;
}

export function buildDepLayout(scan: ScanResult): DepLayout | null {
  const graph = scan.dax_graph;
  if (!graph || !graph.nodes.length) return null;
  const roots = scan.semantic_references?.active_roots;
  const rootSet = new Set((roots ?? []).map(lower));
  const used = roots ? usedSet(graph.nodes, roots) : null;
  const level = levelsOf(graph.nodes);
  const ids = new Set(graph.nodes.map((n) => lower(n.name)));

  const byLevel = new Map<number, DaxGraphNode[]>();
  for (const n of graph.nodes) {
    const l = level.get(lower(n.name)) ?? 0;
    byLevel.set(l, [...(byLevel.get(l) ?? []), n]);
  }

  const nodes: DepNode[] = [];
  for (const [l, group] of [...byLevel].sort((a, b) => a[0] - b[0])) {
    group.sort((a, b) => a.table.localeCompare(b.table) || a.name.localeCompare(b.name));
    const cols = Math.ceil(Math.sqrt(group.length));
    const rows = Math.ceil(group.length / cols);
    group.forEach((n, i) => {
      const id = lower(n.name);
      nodes.push({
        id, name: n.name, table: n.table, kind: n.kind, level: l,
        isRoot: rootSet.has(id),
        used: used ? used.has(id) : null,
        references: n.references, referencedBy: n.referenced_by,
        x: ((i % cols) - (cols - 1) / 2) * NODE_GAP,
        y: l * LEVEL_GAP,
        z: (Math.floor(i / cols) - (rows - 1) / 2) * NODE_GAP,
      });
    });
  }

  const edges: DepEdge[] = graph.nodes.flatMap((n) =>
    n.references.map(lower).filter((r) => ids.has(r)).map((r) => ({ from: lower(n.name), to: r })));
  return {
    nodes,
    edges,
    levels: Math.max(0, ...nodes.map((n) => n.level)) + 1,
    unusedCount: nodes.filter((n) => n.kind === 'measure' && n.used === false).length,
  };
}
