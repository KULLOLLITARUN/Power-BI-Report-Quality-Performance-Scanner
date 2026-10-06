// Parity harness: runs the browser-side clientScanner.ts against a fixture
// directory on disk and prints its findings as JSON to stdout, so a Python
// test can diff them against pbiscan.service.ScanService's output for the
// same fixture. See tests/unit/test_client_scanner_parity.py.
import { readdirSync, readFileSync, statSync } from 'fs';
import { join, relative } from 'path';
import { parseDroppedPbip, DroppedFile, SEVERITY_DEDUCTIONS, CATEGORY_WEIGHTS, RULE_CATALOG, overallScore } from '../src/engine/clientScanner';

function collectFiles(root: string): DroppedFile[] {
  const out: DroppedFile[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const rel = relative(root, full).replace(/\\/g, '/');
      const st = statSync(full);
      if (st.isDirectory()) {
        walk(full);
      } else {
        out.push({ name: entry, path: rel, content: readFileSync(full, 'utf-8') });
      }
    }
  };
  walk(root);
  return out;
}

if (process.argv[2] === '--scoring-constants') {
  process.stdout.write(JSON.stringify({ deductions: SEVERITY_DEDUCTIONS, weights: CATEGORY_WEIGHTS, rules: RULE_CATALOG }));
  process.exit(0);
}

// Overall score for every [model, dax, report] triple read as JSON from stdin
if (process.argv[2] === '--overall-scores') {
  const triples: [number, number, number][] = JSON.parse(readFileSync(0, 'utf-8'));
  process.stdout.write(JSON.stringify(triples.map(([m, d, r]) => overallScore(m, d, r))));
  process.exit(0);
}

const fixtureDir = process.argv[2];
if (!fixtureDir) {
  console.error('Usage: parityHarness.cjs <fixture-dir> [--verbose] | --scoring-constants | --overall-scores');
  process.exit(1);
}

const files = collectFiles(fixtureDir);
const result = parseDroppedPbip(files, 'fixture');

if (process.argv[3] === '--verbose') {
  process.stdout.write(JSON.stringify(result.findings.map((f) => ({ rule_id: f.rule_id, location: f.location })), null, 2));
} else {
  process.stdout.write(
    JSON.stringify({
      rule_ids: result.findings.map((f) => f.rule_id).sort(),
      findings: result.findings.map((f) => [f.rule_id, f.category, f.severity, f.confidence]),
      overall: result.scores.overall,
      category_scores: result.scores.category_scores,
      unused_measures: result.findings
        .filter((f) => f.rule_id === 'DAX_UNUSED_MEASURE')
        .map((f) => f.location)
        .sort(),
      warnings: result.warnings,
    })
  );
}
