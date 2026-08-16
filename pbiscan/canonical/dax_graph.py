"""DAX Dependency Graph — canonical representation of references between measures and calculated columns.

Built once during CanonicalBuilder construction from DaxDictionary.
Enables multi-hop dependency analysis, transitive reachability, and cycle detection.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pbiscan.canonical.model import DaxDictionary


@dataclass
class DaxNode:
    """A single measure or calculated column as a graph node."""
    name: str
    table: str
    kind: str  # "measure" | "calculated_column"


@dataclass
class DaxDependencyGraph:
    """Directed graph of DAX object references, built once from DaxDictionary."""
    nodes: dict[str, DaxNode] = field(default_factory=dict)
    edges: dict[str, set[str]] = field(default_factory=dict)          # name -> set of names it references
    reverse_edges: dict[str, set[str]] = field(default_factory=dict)  # name -> set of names that reference it

    def references(self, name: str) -> set[str]:
        """Direct (1-hop) outgoing references from this object."""
        return set(self.edges.get(name, set()))

    def referenced_by(self, name: str) -> set[str]:
        """Direct (1-hop) incoming references to this object."""
        return set(self.reverse_edges.get(name, set()))

    def transitive_references(self, name: str) -> set[str]:
        """All objects reachable by following outgoing edges, any depth (cycle-safe)."""
        visited: set[str] = set()
        stack = list(self.edges.get(name, set()))
        while stack:
            curr = stack.pop()
            if curr not in visited:
                visited.add(curr)
                for nxt in self.edges.get(curr, set()):
                    if nxt not in visited:
                        stack.append(nxt)
        return visited

    def transitive_referenced_by(self, name: str) -> set[str]:
        """All objects that can reach this one, any depth (cycle-safe)."""
        visited: set[str] = set()
        stack = list(self.reverse_edges.get(name, set()))
        while stack:
            curr = stack.pop()
            if curr not in visited:
                visited.add(curr)
                for prev in self.reverse_edges.get(curr, set()):
                    if prev not in visited:
                        stack.append(prev)
        return visited

    def is_reachable_from_visual(self, name: str, used_in_visuals: set[str]) -> bool:
        """True if `name` is in `used_in_visuals`, or is transitively referenced by anything in `used_in_visuals`."""
        lower_used = {u.lower() for u in used_in_visuals}
        
        # 1. Direct use in a visual
        if name.lower() in lower_used:
            return True

        # 2. Transitive use: check if any object that references `name` (directly or indirectly) is used in visuals
        ancestors = self.transitive_referenced_by(name)
        for anc in ancestors:
            if anc.lower() in lower_used:
                return True

        return False

    def find_cycles(self) -> list[list[str]]:
        """Returns each detected cycle as an ordered list of node names.
        
        Empty list if acyclic.
        """
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: list[str] = []
        rec_set: set[str] = set()

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)
            rec_set.add(node)

            for neighbor in self.edges.get(node, set()):
                if neighbor in rec_set:
                    # Cycle detected
                    idx = rec_stack.index(neighbor)
                    cycle = rec_stack[idx:] + [neighbor]
                    cycles.append(cycle)
                elif neighbor not in visited:
                    dfs(neighbor)

            rec_stack.pop()
            rec_set.remove(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        return cycles


def build_dax_graph(dax_dict: DaxDictionary) -> DaxDependencyGraph:
    """Build a DaxDependencyGraph from a DaxDictionary."""
    nodes: dict[str, DaxNode] = {}
    edges: dict[str, set[str]] = {}
    reverse_edges: dict[str, set[str]] = {}

    # 1. Register all nodes
    for m in dax_dict.measures:
        nodes[m.name] = DaxNode(name=m.name, table=m.table, kind="measure")
        edges[m.name] = set()
        reverse_edges[m.name] = set()

    for cc in dax_dict.calculated_columns:
        nodes[cc.name] = DaxNode(name=cc.name, table=cc.table, kind="calculated_column")
        edges[cc.name] = set()
        reverse_edges[cc.name] = set()

    all_names = set(nodes.keys())
    # Case-insensitive lookup map: lower_name -> canonical_name
    name_lookup = {n.lower(): n for n in all_names}

    # 2. Extract edges via [Name] matching in expressions
    for m in dax_dict.measures:
        _extract_edges_for_expr(m.name, m.expression, name_lookup, edges, reverse_edges)

    for cc in dax_dict.calculated_columns:
        _extract_edges_for_expr(cc.name, cc.expression, name_lookup, edges, reverse_edges)

    return DaxDependencyGraph(nodes=nodes, edges=edges, reverse_edges=reverse_edges)


def _extract_edges_for_expr(
    source_name: str,
    expression: str,
    name_lookup: dict[str, str],
    edges: dict[str, set[str]],
    reverse_edges: dict[str, set[str]],
) -> None:
    if not expression:
        return

    # Extract all bracketed identifiers [Identifier]
    matches = re.findall(r"\[([^\]]+)\]", expression)
    for raw_ref in matches:
        ref_clean = raw_ref.strip()
        ref_lower = ref_clean.lower()
        if ref_lower in name_lookup:
            target_name = name_lookup[ref_lower]
            if target_name != source_name:
                edges[source_name].add(target_name)
                reverse_edges[target_name].add(source_name)
