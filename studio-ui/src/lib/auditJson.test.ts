import { describe, it, expect } from 'vitest';
import { parseAuditJson } from './auditJson';

describe('parseAuditJson', () => {
  it('parses valid pbiscan audit JSON', () => {
    const raw = JSON.stringify({
      report_name: 'Sales Model',
      scores: { overall: 85.5 },
      findings: [
        { finding_id: 'f1', rule_id: 'M001', severity: 'HIGH', title: 'Bi-directional' },
      ],
    });
    const result = parseAuditJson(raw, 'sales.json');
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.report_name).toBe('Sales Model');
      expect(result.value.data.scores).toEqual({ overall: 85.5 });
    }
  });

  it('defaults report_name to "audit" when missing or non-string', () => {
    const raw = JSON.stringify({
      findings: [{ rule_id: 'M001' }],
    });
    const result = parseAuditJson(raw, 'custom.json');
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.report_name).toBe('audit');
    }
  });

  it('rejects invalid JSON syntax', () => {
    const result = parseAuditJson('{not valid json', 'broken.json');
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain('broken.json');
      expect(result.error).toContain('invalid JSON syntax');
    }
  });

  it('rejects non-object JSON (array or primitive)', () => {
    const result = parseAuditJson('["not", "an", "object"]', 'array.json');
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain('not a valid JSON object');
    }
  });

  it('rejects JSON missing the findings array', () => {
    const raw = JSON.stringify({ version: '1.0', name: 'package' });
    const result = parseAuditJson(raw, 'package.json');
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain('missing "findings" array');
    }
  });

  it('rejects JSON where findings has invalid elements', () => {
    const raw = JSON.stringify({
      findings: ['not an object'],
    });
    const result = parseAuditJson(raw, 'bad_findings.json');
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain('findings array contains invalid entries');
    }
  });

  it('rejects JSON where findings elements lack rule_id string', () => {
    const raw = JSON.stringify({
      findings: [{ finding_id: '123' }],
    });
    const result = parseAuditJson(raw, 'no_rule_id.json');
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain('must be objects with a string rule_id');
    }
  });

  it('allows malformed optional fields through to backend validation', () => {
    const raw = JSON.stringify({
      report_name: 12345, // non-string fallback
      scores: 'invalid-scores-type',
      findings: [
        {
          rule_id: 'DAX001',
          confidence: 'high-not-number', // backend handles type check
          suppressed: 'maybe',
        },
      ],
    });
    const result = parseAuditJson(raw, 'optional_fields.json');
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.report_name).toBe('audit');
      expect(result.value.data.findings).toHaveLength(1);
    }
  });
});
