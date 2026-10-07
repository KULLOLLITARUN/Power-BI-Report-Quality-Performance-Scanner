// Deterministic synthetic semantic models for layout tests and benchmarks.
// A star-ish enterprise shape: a few fact tables, many dimensions, each fact
// linked to a spread of dimensions, plus some snowflake and fact-to-fact links.
import type { RelationshipInfo, TableInfo } from '../../types';

/** Small seeded PRNG (mulberry32) so every run builds the same model. */
export function seeded(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function syntheticModel(tableCount = 300, relationshipCount = 600, seed = 1): { tables: TableInfo[]; relationships: RelationshipInfo[] } {
  const rand = seeded(seed);
  const factCount = Math.max(1, Math.round(tableCount / 12));
  const tables: TableInfo[] = [];
  for (let i = 0; i < tableCount; i++) {
    const fact = i < factCount;
    const name = fact ? `Fact${String(i).padStart(3, '0')}` : i === factCount ? 'Date' : `Dim${String(i).padStart(3, '0')}`;
    const cols = fact ? 12 + Math.floor(rand() * 40) : 3 + Math.floor(rand() * 20);
    tables.push({
      name, hidden: false, is_date_table: name === 'Date', column_count: cols,
      columns: Array.from({ length: cols }, (_, c) => ({ name: `c${c}`, data_type: 'string', is_unique: c === 0, in_relationship: false, hidden: false })),
      measures_count: fact ? Math.floor(rand() * 30) : 0, calc_cols_count: 0,
    });
  }
  const relationships: RelationshipInfo[] = [];
  const seen = new Set<string>();
  const add = (from: number, to: number) => {
    const key = `${from}>${to}`;
    if (from === to || seen.has(key)) return false;
    seen.add(key);
    relationships.push({
      from_table: tables[from].name, from_column: `${tables[to].name}Key`,
      to_table: tables[to].name, to_column: `${tables[to].name}Key`,
      cardinality: 'oneToMany', cross_filter_direction: rand() < 0.05 ? 'bothDirections' : 'oneDirection', is_active: rand() > 0.03,
    });
    return true;
  };
  // Every fact reads the date table, and every dimension hangs off at least one fact.
  if (factCount < tableCount) for (let f = 0; f < factCount; f++) add(f, factCount);
  for (let d = factCount + 1; d < tableCount && relationships.length < relationshipCount; d++) add(Math.floor(rand() * factCount), d);
  // Fill with more fact->dim links, some snowflakes (dim->dim) and a few fact->fact.
  let guard = 0;
  while (relationships.length < relationshipCount && guard++ < relationshipCount * 20) {
    const r = rand();
    if (r < 0.7) add(Math.floor(rand() * factCount), factCount + Math.floor(rand() * (tableCount - factCount)));
    else if (r < 0.95) add(factCount + 1 + Math.floor(rand() * (tableCount - factCount - 1)), factCount + 1 + Math.floor(rand() * (tableCount - factCount - 1)));
    else add(Math.floor(rand() * factCount), Math.floor(rand() * factCount));
  }
  return { tables, relationships };
}
