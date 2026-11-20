import { describe, expect, it } from 'vitest';
import type { AuditFinding } from '../types';
import { groupByRule, groupWhere } from './groups';

const f = (rule_id: string, location: string, severity: AuditFinding['severity'] = 'HIGH', confidence = 95): AuditFinding => ({
  rule_id, category: 'model', severity, title: `Title of ${rule_id}`, issue: '', evidence: '', impact: '', recommendation: '', confidence, location,
});
const fixable = (id: string) => id === 'M_HARDCODED_DATA_SOURCE';

describe('groupByRule', () => {
  it('collapses identical rules into one row and keeps first-seen order', () => {
    const groups = groupByRule([
      f('M_HARDCODED_DATA_SOURCE', 'A'), f('DAX_DUPLICATE_MEASURE', 'X', 'MEDIUM'), f('M_HARDCODED_DATA_SOURCE', 'B'), f('M_HARDCODED_DATA_SOURCE', 'C'),
    ], fixable);
    expect(groups.map((g) => g.rule_id)).toEqual(['M_HARDCODED_DATA_SOURCE', 'DAX_DUPLICATE_MEASURE']);
    expect(groups[0].members).toHaveLength(3);
    expect(groups[0].fixable).toBe(true);
    expect(groups[1].fixable).toBe(false);
  });

  it('reports the worst severity and the weakest confidence of the members', () => {
    const [g] = groupByRule([f('R', 'A', 'MEDIUM', 90), f('R', 'B', 'HIGH', 70), f('R', 'C', 'ADVISORY', 99)], () => false);
    expect(g.severity).toBe('HIGH');
    expect(g.confidence).toBe(70);
  });

  it('returns nothing for no findings', () => {
    expect(groupByRule([], fixable)).toEqual([]);
  });
});

describe('groupWhere', () => {
  it('shows the location of a single finding', () => {
    const [g] = groupByRule([f('R', 'Banana Exports')], () => false);
    expect(groupWhere(g)).toBe('Banana Exports');
  });

  it('summarises a group by count and the first places', () => {
    const [g] = groupByRule(['A', 'B', 'C', 'D'].map((l) => f('R', l)), () => false);
    expect(groupWhere(g)).toBe('4 findings: A, B and 2 more');
  });

  it('does not say "and 0 more" and ignores repeated locations', () => {
    const [g] = groupByRule([f('R', 'A'), f('R', 'A'), f('R', 'B')], () => false);
    expect(groupWhere(g)).toBe('3 findings: A, B');
  });

  it('drops the "Table: " prefix from locations', () => {
    const [g] = groupByRule([f('R', 'Table: A'), f('R', 'Table: B'), f('R', 'Table: C')], () => false);
    expect(groupWhere(g)).toBe('3 findings: A, B and 1 more');
  });
});
