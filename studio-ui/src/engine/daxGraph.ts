// DAX Dependency Graph — TypeScript port of pbiscan.canonical.dax_graph.
//
// Builds a directed graph of `[Name]` bracket references between measures and
// calculated columns, and answers "is this measure transitively reachable from
// something used in a visual/semantic reference root?" — the same multi-hop,
// cycle-safe reachability check the Python engine uses for DAX_UNUSED_MEASURE,
// so a base measure that's only ever consumed by another measure (which is
// itself bound to a visual) is correctly treated as used.

export interface DaxNode {
  name: string;
  table: string;
  kind: 'measure' | 'calculated_column';
}

export class DaxDependencyGraph {
  nodes: Map<string, DaxNode> = new Map();
  edges: Map<string, Set<string>> = new Map();
  reverseEdges: Map<string, Set<string>> = new Map();

  references(name: string): Set<string> {
    return new Set(this.edges.get(name) ?? []);
  }

  referencedBy(name: string): Set<string> {
    return new Set(this.reverseEdges.get(name) ?? []);
  }

  transitiveReferencedBy(name: string): Set<string> {
    const visited = new Set<string>();
    const stack = [...(this.reverseEdges.get(name) ?? [])];
    while (stack.length) {
      const curr = stack.pop()!;
      if (!visited.has(curr)) {
        visited.add(curr);
        for (const prev of this.reverseEdges.get(curr) ?? []) {
          if (!visited.has(prev)) stack.push(prev);
        }
      }
    }
    return visited;
  }

  /** True if `name` is itself in `usedInVisuals`, or is transitively referenced
   * (directly or through any number of hops) by anything in `usedInVisuals`. */
  isReachableFromVisual(name: string, usedInVisuals: Set<string>): boolean {
    const lowerUsed = new Set(Array.from(usedInVisuals).map((u) => u.toLowerCase()));

    if (lowerUsed.has(name.toLowerCase())) return true;

    const ancestors = this.transitiveReferencedBy(name);
    for (const anc of ancestors) {
      if (lowerUsed.has(anc.toLowerCase())) return true;
    }
    return false;
  }
}

interface DaxObject {
  name: string;
  table: string;
  expression: string;
}

export function buildDaxGraph(measures: DaxObject[], calcColumns: DaxObject[]): DaxDependencyGraph {
  const graph = new DaxDependencyGraph();

  for (const m of measures) {
    graph.nodes.set(m.name, { name: m.name, table: m.table, kind: 'measure' });
    graph.edges.set(m.name, new Set());
    graph.reverseEdges.set(m.name, new Set());
  }
  for (const cc of calcColumns) {
    graph.nodes.set(cc.name, { name: cc.name, table: cc.table, kind: 'calculated_column' });
    graph.edges.set(cc.name, new Set());
    graph.reverseEdges.set(cc.name, new Set());
  }

  const nameLookup = new Map<string, string>();
  for (const n of graph.nodes.keys()) nameLookup.set(n.toLowerCase(), n);

  const extractEdges = (sourceName: string, expression: string) => {
    if (!expression) return;
    const matches = expression.matchAll(/\[([^\]]+)\]/g);
    for (const m of matches) {
      const refClean = m[1].trim();
      const targetName = nameLookup.get(refClean.toLowerCase());
      if (targetName && targetName !== sourceName) {
        graph.edges.get(sourceName)!.add(targetName);
        graph.reverseEdges.get(targetName)!.add(sourceName);
      }
    }
  };

  for (const m of measures) extractEdges(m.name, m.expression);
  for (const cc of calcColumns) extractEdges(cc.name, cc.expression);

  return graph;
}
