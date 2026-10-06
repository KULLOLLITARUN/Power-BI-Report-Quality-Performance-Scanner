// Per-browser scan history, used for the score trend. It is a convenience:
// storage can be blocked or cleared, and every reader handles an empty list.
import type { ScanResult } from '../types';

export interface HistoryPoint {
  t: string;        // ISO time
  overall: number;
  findings: number;
}

const KEY = (path: string) => `pbiscan_history:${path.toLowerCase()}`;
const MAX = 12;

export function readHistory(path: string): HistoryPoint[] {
  if (!path) return [];
  try {
    const raw = localStorage.getItem(KEY(path));
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter((p) => typeof p?.overall === 'number' && typeof p?.t === 'string') : [];
  } catch {
    return [];
  }
}

/** Append this scan and return the updated list (oldest first). */
export function recordScan(path: string, scan: ScanResult): HistoryPoint[] {
  const point: HistoryPoint = {
    t: new Date().toISOString(),
    overall: scan.scores?.overall ?? 0,
    findings: (scan.findings || []).filter((f) => !f.suppressed).length,
  };
  const list = [...readHistory(path), point].slice(-MAX);
  try {
    localStorage.setItem(KEY(path), JSON.stringify(list));
  } catch {
    // Storage blocked: the trend just shows this one scan.
  }
  return list;
}

export function shortDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

export function shortTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}
