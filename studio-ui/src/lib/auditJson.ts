// Parsing and validation of pbiscan audit JSON files.

export interface ParsedAuditJson {
  report_name: string;
  data: Record<string, unknown>;
}

export type ParseAuditJsonResult =
  | { ok: true; value: ParsedAuditJson }
  | { ok: false; error: string };

/**
 * Validate that raw text is a valid pbiscan scan JSON file.
 * Requires:
 * 1. Valid JSON syntax
 * 2. Top-level object
 * 3. Array of findings
 * 4. Each finding is an object with a string rule_id
 */
export function parseAuditJson(text: string, filename = 'audit.json'): ParseAuditJsonResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { ok: false, error: `Failed to parse "${filename}": invalid JSON syntax.` };
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { ok: false, error: `"${filename}" is not a valid JSON object.` };
  }

  const record = parsed as Record<string, unknown>;

  if (!Array.isArray(record.findings)) {
    return { ok: false, error: `"${filename}" is not a valid pbiscan audit file (missing "findings" array).` };
  }

  const hasInvalidFinding = record.findings.some(
    (f) => !f || typeof f !== 'object' || Array.isArray(f) || typeof (f as Record<string, unknown>).rule_id !== 'string'
  );
  if (hasInvalidFinding) {
    return { ok: false, error: `"${filename}" findings array contains invalid entries (must be objects with a string rule_id).` };
  }

  const reportName =
    typeof record.report_name === 'string' && record.report_name.trim()
      ? record.report_name.trim()
      : 'audit';

  return {
    ok: true,
    value: {
      report_name: reportName,
      data: record,
    },
  };
}
