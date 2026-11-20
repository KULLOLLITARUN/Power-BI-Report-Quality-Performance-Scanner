// Groups findings by rule, so thirteen identical hardcoded-path findings read as one row.
// Pure and presentation-only: it never changes what a scan reports.
import type { AuditFinding } from '../types';
import { sevRank } from './severity';

export interface FindingGroup {
  rule_id: string;
  title: string;
  category: AuditFinding['category'];
  /** The most severe member. */
  severity: AuditFinding['severity'];
  /** The lowest confidence among the members, so a group never claims more than its weakest finding. */
  confidence: number;
  members: AuditFinding[];
  fixable: boolean;
}

/** One group per rule, in the order each rule first appears (the input is already sorted). */
export function groupByRule(findings: AuditFinding[], isFixable: (ruleId: string) => boolean): FindingGroup[] {
  const byRule = new Map<string, AuditFinding[]>();
  for (const f of findings) {
    const list = byRule.get(f.rule_id);
    if (list) list.push(f); else byRule.set(f.rule_id, [f]);
  }
  return [...byRule.entries()].map(([rule_id, members]) => {
    const worst = members.reduce((a, b) => (sevRank(b.severity) < sevRank(a.severity) ? b : a));
    return {
      rule_id,
      title: members[0].title,
      category: members[0].category,
      severity: worst.severity,
      confidence: Math.min(...members.map((m) => m.confidence ?? 0)),
      members,
      fixable: isFixable(rule_id),
    };
  });
}

/** Locations read "Table: Banana Exports"; the prefix is noise in a summary line. */
const plainPlace = (l: string) => l.replace(/^(Table|Measure|Page|Relationship):\s*/i, '');

/** "Banana Exports" for one finding; "13 places, Banana Exports and Banana Imports and 11 more" for a group. */
export function groupWhere(g: FindingGroup, shown = 2): string {
  const places = [...new Set(g.members.map((m) => m.location).filter((l): l is string => !!l).map(plainPlace))];
  if (g.members.length === 1) return places[0] ?? '';
  const head = places.slice(0, shown).join(', ');
  const rest = places.length - shown;
  const count = `${g.members.length} findings`;
  if (!head) return count;
  return rest > 0 ? `${count}: ${head} and ${rest} more` : `${count}: ${head}`;
}
