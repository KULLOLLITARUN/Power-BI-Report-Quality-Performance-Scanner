import { describe, expect, it } from 'vitest';
import { extractColumnRefs } from './semanticReferences';

const col = (entity: string, prop: string) => ({ Column: { Expression: { SourceRef: { Entity: entity } }, Property: prop } });

describe('extractColumnRefs (mirrors tests/unit/test_column_refs.py)', () => {
  it('reads projections and a column inside an aggregation, sorted', () => {
    const node = { queryState: { Values: { projections: [
      { field: col('Sales', 'Region') },
      { field: { Aggregation: { Expression: col('Sales', 'Amount'), Function: 0 } } },
    ] } } };
    expect(extractColumnRefs(node)).toEqual([['Sales', 'Amount'], ['Sales', 'Region']]);
  });

  it('ignores measures and hierarchy levels', () => {
    const node = [
      { Measure: { Expression: { SourceRef: { Entity: 'Sales' } }, Property: 'Total' } },
      { HierarchyLevel: { Expression: { Hierarchy: { Expression: { SourceRef: { Entity: 'Date' } }, Hierarchy: 'H' } }, Level: 'Year' } },
    ];
    expect(extractColumnRefs(node)).toEqual([]);
  });

  it('resolves an alias through the surrounding From', () => {
    const query = {
      From: [{ Name: 's', Entity: 'Sales', Type: 0 }],
      Select: [{ Column: { Expression: { SourceRef: { Source: 's' } }, Property: 'Region' }, Name: 'Sales.Region' }],
      Where: [{ Condition: { In: { Expressions: [{ Column: { Expression: { SourceRef: { Source: 's' } }, Property: 'Year' } }] } } }],
    };
    expect(extractColumnRefs(query)).toEqual([['Sales', 'Region'], ['Sales', 'Year']]);
  });

  it('leaves out an alias with no matching From', () => {
    expect(extractColumnRefs({ Column: { Expression: { SourceRef: { Source: 'x' } }, Property: 'Region' } })).toEqual([]);
  });

  it('does not leak an alias to a sibling scope', () => {
    const node = [
      { From: [{ Name: 's', Entity: 'Sales' }], Where: [{ Column: { Expression: { SourceRef: { Source: 's' } }, Property: 'A' } }] },
      { Where: [{ Column: { Expression: { SourceRef: { Source: 's' } }, Property: 'B' } }] },
    ];
    expect(extractColumnRefs(node)).toEqual([['Sales', 'A']]);
  });

  it('ignores odd shapes without throwing', () => {
    for (const node of [null, 'text', 3, { Column: 'x' }, { Column: { Property: 5 } }, { From: 'nope' }, [[], {}]]) {
      expect(extractColumnRefs(node)).toEqual([]);
    }
  });

  it('does not take Object.prototype names as aliases', () => {
    expect(extractColumnRefs({ Column: { Expression: { SourceRef: { Source: 'constructor' } }, Property: 'X' } })).toEqual([]);
  });
});
