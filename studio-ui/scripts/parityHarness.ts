// Parity harness: runs the browser-side clientScanner.ts against a fixture
// directory on disk and prints its findings as JSON to stdout, so a Python
// test can diff them against pbiscan.service.ScanService's output for the
// same fixture. See tests/unit/test_client_scanner_parity.py.
import { readdirSync, readFileSync, statSync } from 'fs';
import { join, relative } from 'path';
import { parseDroppedPbip, DroppedFile } from '../src/engine/clientScanner';

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

const fixtureDir = process.argv[2];
if (!fixtureDir) {
  console.error('Usage: parityHarness.mjs <fixture-dir>');
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
      overall: result.scores.overall,
      category_scores: result.scores.category_scores,
    })
  );
}
