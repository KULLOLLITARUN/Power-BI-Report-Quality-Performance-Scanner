import type { AuditFinding } from '../types';

export type Severity = AuditFinding['severity'];

export interface SeverityMeta {
  label: string;
  token: string;
  shape: 'diamond' | 'tri' | 'square' | 'circle' | 'ring' | 'dash';
}

// Most severe first. Matches the scoring deductions in pbiscan.service.DEFAULT_CONFIG
// (CRITICAL 15, HIGH 10, MEDIUM 5, WARNING 3, LOW 2, ADVISORY 1).
export const SEV_ORDER: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'WARNING', 'LOW', 'ADVISORY'];

export const SEV: Record<Severity, SeverityMeta> = {
  CRITICAL: { label: 'Critical', token: '--sev-critical', shape: 'diamond' },
  HIGH: { label: 'High', token: '--sev-high', shape: 'tri' },
  MEDIUM: { label: 'Medium', token: '--sev-medium', shape: 'square' },
  WARNING: { label: 'Warning', token: '--sev-warning', shape: 'circle' },
  LOW: { label: 'Low', token: '--sev-low', shape: 'dash' },
  ADVISORY: { label: 'Advisory', token: '--sev-advisory', shape: 'ring' },
};

export function sevMeta(sev: string): SeverityMeta {
  return SEV[(sev || '').toUpperCase() as Severity] ?? SEV.ADVISORY;
}

export function sevRank(sev: string): number {
  const i = SEV_ORDER.indexOf((sev || '').toUpperCase() as Severity);
  return i === -1 ? SEV_ORDER.length : i;
}

export function worstSeverity(sevs: string[]): Severity | null {
  if (!sevs.length) return null;
  return [...sevs].sort((a, b) => sevRank(a) - sevRank(b))[0].toUpperCase() as Severity;
}

export function sortFindings(list: AuditFinding[]): AuditFinding[] {
  return [...list].sort((a, b) => sevRank(a.severity) - sevRank(b.severity) || (b.confidence ?? 0) - (a.confidence ?? 0));
}

export function grade(score: number): string {
  if (score >= 90) return 'A';
  if (score >= 80) return 'B';
  if (score >= 70) return 'C';
  if (score >= 60) return 'D';
  return 'F';
}

export const AREA_LABEL: Record<string, string> = { model: 'Model', dax: 'DAX', report: 'Report' };
