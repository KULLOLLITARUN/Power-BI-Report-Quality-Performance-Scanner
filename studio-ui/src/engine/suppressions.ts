// Port of pbiscan/engine/suppressions.py: loads pbiscan.suppressions.json from
// the dropped project and marks matching findings as suppressed. Suppressed
// findings stay in the list (auditable) but are excluded from scoring.
import type { AuditFinding } from '../types';

export const SUPPRESSIONS_FILENAME = 'pbiscan.suppressions.json';

interface SuppressionRule {
  rule_id: string;
  location_pattern: string;
  reason: string;
}

function normaliseLoc(loc: string): string {
  return loc.toLowerCase().replace(/↔/g, '<->').replace(/→/g, '->').replace(/←/g, '<-').trim();
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function matches(rule: SuppressionRule, ruleId: string, location: string | undefined): boolean {
  if (rule.rule_id.toUpperCase() !== ruleId.toUpperCase()) return false;
  if (!rule.location_pattern || rule.location_pattern === '*') return true;
  if (!location) return false;

  const pat = normaliseLoc(rule.location_pattern);
  const loc = normaliseLoc(location);

  if (pat === loc) return true;

  if (pat.includes('*') || pat.includes('?')) {
    const regex = '^' + pat.split('*').map((p) => escapeRegex(p).replace(/\\\?/g, '.')).join('.*') + '$';
    if (new RegExp(regex, 'i').test(loc)) return true;
  }

  return loc.includes(pat);
}

/** Parse the suppressions file content; malformed content yields no rules plus a warning. */
export function loadSuppressions(content: string, filePath: string, warnings: string[]): SuppressionRule[] {
  const report = (problem: string): SuppressionRule[] => {
    warnings.push(`Ignoring suppressions in ${filePath}: ${problem}`);
    return [];
  };

  let data: unknown;
  try {
    data = JSON.parse(content);
  } catch (err) {
    return report(err instanceof Error ? err.message : String(err));
  }

  const list = data && typeof data === 'object' && !Array.isArray(data)
    ? (data as Record<string, unknown>).suppressions ?? []
    : undefined;
  if (!Array.isArray(list)) {
    return report('expected an object with a "suppressions" list');
  }

  const rules: SuppressionRule[] = [];
  for (const item of list) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const rec = item as Record<string, unknown>;
    if (!rec.rule_id) continue;
    rules.push({
      rule_id: String(rec.rule_id),
      location_pattern: String(rec.location || rec.location_pattern || '*'),
      reason: String(rec.reason ?? 'Suppressed by team policy'),
    });
  }
  return rules;
}

export function applySuppressions(findings: AuditFinding[], rules: SuppressionRule[]): void {
  for (const finding of findings) {
    const rule = rules.find((r) => matches(r, finding.rule_id, finding.location));
    if (rule) {
      finding.suppressed = true;
      finding.suppression_reason = rule.reason;
    }
  }
}
