import { describe, expect, it } from 'vitest';
import {
  hasNestedCalculate,
  looksLikeDateTableName,
  looksLikeDimensionName,
  parseDroppedPbip,
  stripDaxComments,
} from './clientScanner';
import { bracketNames } from './daxGraph';

// These mirror the Python rules in pbiscan/; tests/unit/test_client_scanner_parity.py compares
// the two engines over the golden fixtures, and these pin the edge cases directly.

describe('looksLikeDimensionName', () => {
  it('matches dim words and whole dimension words', () => {
    for (const name of ['DimCustomer', 'dim_customer', 'dimcustomer', 'Dim Date', 'Customer Lookup', 'Product Reference', 'Bridge Table', 'RefData']) {
      expect(looksLikeDimensionName(name), name).toBe(true);
    }
  });
  it('does not read ref or dim inside a longer word', () => {
    for (const name of ['Refunds', 'Preferences', 'Sales', 'Orders']) {
      expect(looksLikeDimensionName(name), name).toBe(false);
    }
  });
});

describe('looksLikeDateTableName', () => {
  it('matches whole date words and auto date tables, not look-alikes', () => {
    for (const name of ['Dim Date', 'DimDate', 'dim_date', 'Calendar', 'Fiscal Calendar', 'LocalDateTable_1a', 'localdatetable_x']) {
      expect(looksLikeDateTableName(name), name).toBe(true);
    }
    for (const name of ['Sales Updates', 'Candidates', 'Timesheet', 'Sometimes', 'Datasets']) {
      expect(looksLikeDateTableName(name), name).toBe(false);
    }
  });
});

describe('DAX scanning', () => {
  it('reads ]] as an escaped bracket, so a comment marker inside a name is not a comment', () => {
    expect(bracketNames('[Margin [%]]] + [Other]')).toEqual(['Margin [%]', 'Other']);
    const expr = 'T[a]]--b] + 1';
    expect(stripDaxComments(expr)).toBe(expr);
  });
  it('tells nested CALCULATE from sequential calls', () => {
    expect(hasNestedCalculate('CALCULATE(1) + CALCULATE(2)')).toBe(false);
    expect(hasNestedCalculate('CALCULATE(CALCULATE(1))')).toBe(true);
    expect(hasNestedCalculate('CALCULATE(T[a]]--b] + CALCULATE(1))')).toBe(true);
  });
});

describe('TMDL measure bodies', () => {
  const scan = (table: string) =>
    parseDroppedPbip([{ name: 'T.tmdl', path: 'p.SemanticModel/definition/tables/T.tmdl', content: table }]);

  it('keeps a dynamic format string in the measure DAX, so the measure it names counts as used', () => {
    const result = scan(
      'table T\n\tmeasure A = 1\n\t\tformatStringDefinition = IF([B] > 0, "0.0", "0")\n\n\tmeasure B = 2\n',
    );
    const a = result.measures.find((m) => m.name === 'A')!;
    expect(a.expression).toContain('[B]');
    expect(result.measures.find((m) => m.name === 'B')).toBeDefined();
  });

  it('treats a bare isHidden as a property, not DAX', () => {
    const result = scan('table T\n\tmeasure A = 1\n\t\tisHidden\n\t\tformatString: 0\n\n\tmeasure B = 2\n');
    const a = result.measures.find((m) => m.name === 'A')!;
    expect(a.expression).toBe('1');
    expect(a.hidden).toBe(true);
    expect(result.measures.find((m) => m.name === 'B')!.hidden).toBe(false);
  });

  it('keeps a date variation block out of the DAX', () => {
    const result = scan(
      'table T\n\tmeasure A = 1 + 1\n\t\tvariation V\n\t\t\tisDefault\n\t\t\trelationship: abc\n\t\t\tdefaultHierarchy: L.\'Date Hierarchy\'\n',
    );
    expect(result.measures.find((m) => m.name === 'A')!.expression).toBe('1 + 1');
  });
});
