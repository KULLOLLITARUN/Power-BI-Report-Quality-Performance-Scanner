import React, { useState } from 'react';
import { 
  GitCompare, 
  ArrowRight, 
  RefreshCw, 
  AlertCircle, 
  CheckCircle2, 
  XCircle, 
  FolderOpen, 
  FileText, 
  ChevronDown, 
  ChevronRight, 
  Copy, 
  Download, 
  ShieldCheck, 
  ShieldAlert,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Sparkles
} from 'lucide-react';
import { DiffResult, FindingTransition } from '../types';

interface DiffViewerProps {
  initialBaselinePath?: string;
  initialCurrentPath?: string;
  onNativeBrowse?: (mode: 'file' | 'folder', target: 'baseline' | 'current') => void;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  initialBaselinePath = '',
  initialCurrentPath = '',
  onNativeBrowse,
}) => {
  const [baselinePath, setBaselinePath] = useState(initialBaselinePath);
  const [currentPath, setCurrentPath] = useState(initialCurrentPath);
  const [failOnRegression, setFailOnRegression] = useState(false);
  const [failOnNew, setFailOnNew] = useState<string>('NONE');
  const [maxScoreDrop, setMaxScoreDrop] = useState<string>('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diffResult, setDiffResult] = useState<DiffResult | null>(null);

  // Accordion / Collapsible state
  const [showPersistent, setShowPersistent] = useState(false);
  const [expandedFindings, setExpandedFindings] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState(false);

  const toggleFindingExpanded = (id: string) => {
    setExpandedFindings((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const triggerBrowse = async (mode: 'file' | 'folder', target: 'baseline' | 'current') => {
    if (onNativeBrowse) {
      onNativeBrowse(mode, target);
      return;
    }
    try {
      const res = await fetch('/api/native-dialog', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      if (res.ok) {
        const data = await res.json();
        if (!data.canceled && data.path) {
          if (target === 'baseline') {
            setBaselinePath(data.path);
          } else {
            setCurrentPath(data.path);
          }
        }
      }
    } catch (e) {
      // Ignore if dialog is unavailable in non-desktop environments
    }
  };

  const handleCompare = async () => {
    if (!baselinePath.trim() || !currentPath.trim()) {
      setError('Both baseline and current scan paths are required.');
      return;
    }

    setLoading(true);
    setError(null);
    setDiffResult(null);

    try {
      const payload: any = {
        baseline_path: baselinePath.trim(),
        current_path: currentPath.trim(),
        fail_on_regression: failOnRegression,
      };

      if (failOnNew !== 'NONE') {
        payload.fail_on_new = failOnNew;
      }

      if (maxScoreDrop.trim() && !isNaN(Number(maxScoreDrop))) {
        payload.max_score_drop = Number(maxScoreDrop);
      }

      const res = await fetch('/api/diff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Comparison failed (${res.status}: ${res.statusText})`);
      }

      const data: DiffResult = await res.json();
      setDiffResult(data);
    } catch (err: any) {
      console.error('Diff error:', err);
      setError(err.message || 'Failed to compare scans');
      setDiffResult(null);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityBadgeStyle = (severity: string) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return {
          bg: 'var(--severity-critical-bg)',
          border: 'var(--severity-critical-border)',
          color: 'var(--severity-critical)',
        };
      case 'HIGH':
        return {
          bg: 'var(--severity-high-bg)',
          border: 'var(--severity-high-border)',
          color: 'var(--severity-high)',
        };
      case 'MEDIUM':
        return {
          bg: 'var(--severity-medium-bg)',
          border: 'var(--severity-medium-border)',
          color: 'var(--severity-medium)',
        };
      case 'WARNING':
        return {
          bg: 'var(--severity-warning-bg)',
          border: 'var(--severity-warning-border)',
          color: 'var(--severity-warning)',
        };
      case 'ADVISORY':
      default:
        return {
          bg: 'var(--severity-advisory-bg)',
          border: 'var(--severity-advisory-border)',
          color: 'var(--severity-advisory)',
        };
    }
  };

  const handleCopySummary = () => {
    if (!diffResult) return;
    const text = [
      `PBIP Sentinel Scan Diff — ${diffResult.current_name}`,
      `Quality Gate: ${diffResult.quality_gate.passed ? 'PASS' : 'FAIL'}`,
      `Health Score: ${diffResult.score_drift.baseline_score.toFixed(1)} -> ${diffResult.score_drift.current_score.toFixed(1)} (${diffResult.score_drift.overall_delta >= 0 ? '+' : ''}${diffResult.score_drift.overall_delta.toFixed(1)} ${diffResult.score_drift.direction})`,
      `Transitions: ${diffResult.counts.new} New, ${diffResult.counts.resolved} Resolved, ${diffResult.counts.persistent} Persistent, ${diffResult.counts.modified} Modified`,
    ].join('\n');

    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExportJson = () => {
    if (!diffResult) return;
    const blob = new Blob([JSON.stringify(diffResult, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `diff-${diffResult.current_name || 'report'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const newFindings = diffResult?.transitions.filter((t) => t.state === 'NEW') || [];
  const resolvedFindings = diffResult?.transitions.filter((t) => t.state === 'RESOLVED') || [];
  const modifiedFindings = diffResult?.transitions.filter((t) => t.state === 'MODIFIED') || [];
  const persistentFindings = diffResult?.transitions.filter((t) => t.state === 'PERSISTENT') || [];

  return (
    <div className="max-w-5xl mx-auto space-y-6 font-mono">
      {/* Header Banner */}
      <div 
        className="p-5 rounded border flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderColor: 'var(--border-hairline)',
        }}
      >
        <div className="flex items-center gap-3.5">
          <div 
            className="w-10 h-10 rounded border flex items-center justify-center shadow-sm shrink-0"
            style={{
              backgroundColor: 'var(--accent-muted)',
              borderColor: 'var(--accent)',
              color: 'var(--accent)',
            }}
          >
            <GitCompare className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Scan Comparison &amp; CI/CD Drift Engine
            </h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Compare two PBIP project directories or exported JSON scan artifacts
            </p>
          </div>
        </div>

        {diffResult && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopySummary}
              className="px-3 py-1.5 rounded border text-xs flex items-center gap-1.5 transition font-medium"
              style={{
                backgroundColor: 'var(--bg-canvas)',
                borderColor: 'var(--border-hairline)',
                color: 'var(--text-primary)',
              }}
            >
              <Copy className="w-3.5 h-3.5" />
              <span>{copied ? 'Copied!' : 'Copy Summary'}</span>
            </button>
            <button
              onClick={handleExportJson}
              className="px-3 py-1.5 rounded border text-xs flex items-center gap-1.5 transition font-medium"
              style={{
                backgroundColor: 'var(--accent-muted)',
                borderColor: 'var(--accent)',
                color: 'var(--accent)',
              }}
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export JSON</span>
            </button>
          </div>
        )}
      </div>

      {/* Comparison Inputs Form */}
      <div 
        className="p-5 rounded border space-y-4"
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderColor: 'var(--border-hairline)',
        }}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Baseline Input */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider flex items-center justify-between" style={{ color: 'var(--text-secondary)' }}>
              <span>1. Baseline Scan (Previous / Main)</span>
              <span className="text-[10px] lowercase text-muted font-normal">PBIP folder or .json</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={baselinePath}
                onChange={(e) => setBaselinePath(e.target.value)}
                placeholder="e.g. C:/Reports/Main_Baseline.json or PBIP folder"
                className="flex-1 px-3 py-2 rounded border text-xs font-mono outline-none transition"
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--text-primary)',
                }}
              />
              <button
                type="button"
                onClick={() => triggerBrowse('folder', 'baseline')}
                className="px-2.5 py-2 rounded border text-xs hover:opacity-80 transition shrink-0"
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--accent)',
                }}
                title="Browse Folder / File"
              >
                <FolderOpen className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Current Input */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider flex items-center justify-between" style={{ color: 'var(--text-secondary)' }}>
              <span>2. Current Scan (PR / Feature)</span>
              <span className="text-[10px] lowercase text-muted font-normal">PBIP folder or .json</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={currentPath}
                onChange={(e) => setCurrentPath(e.target.value)}
                placeholder="e.g. C:/Reports/Feature_Branch.pbip or .json"
                className="flex-1 px-3 py-2 rounded border text-xs font-mono outline-none transition"
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--text-primary)',
                }}
              />
              <button
                type="button"
                onClick={() => triggerBrowse('folder', 'current')}
                className="px-2.5 py-2 rounded border text-xs hover:opacity-80 transition shrink-0"
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--accent)',
                }}
                title="Browse Folder / File"
              >
                <FolderOpen className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Quality Gate Controls & Action */}
        <div className="pt-3 border-t flex flex-col md:flex-row items-start md:items-center justify-between gap-4" style={{ borderColor: 'var(--border-hairline)' }}>
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={failOnRegression}
                onChange={(e) => setFailOnRegression(e.target.checked)}
                className="rounded accent-emerald-500"
              />
              <span style={{ color: 'var(--text-secondary)' }}>Fail on Score Regression</span>
            </label>

            <div className="flex items-center gap-1.5">
              <span style={{ color: 'var(--text-muted)' }}>Fail on New:</span>
              <select
                value={failOnNew}
                onChange={(e) => setFailOnNew(e.target.value)}
                className="px-2 py-1 rounded border text-xs font-mono outline-none"
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--text-primary)',
                }}
              >
                <option value="NONE">None</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="WARNING">WARNING</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleCompare}
            disabled={loading || !baselinePath.trim() || !currentPath.trim()}
            className="w-full md:w-auto px-5 py-2 rounded border font-mono text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition disabled:opacity-50"
            style={{
              backgroundColor: 'var(--accent)',
              borderColor: 'var(--accent)',
              color: 'var(--bg-canvas)',
            }}
          >
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Comparing Scans...</span>
              </>
            ) : (
              <>
                <GitCompare className="w-4 h-4" />
                <span>Run Comparison</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div 
          className="p-4 rounded border text-xs flex items-center gap-3 font-mono"
          style={{
            backgroundColor: 'var(--severity-critical-bg)',
            borderColor: 'var(--severity-critical-border)',
            color: 'var(--severity-critical)',
          }}
        >
          <AlertCircle className="w-5 h-5 shrink-0" />
          <div>
            <strong>Scan comparison failed:</strong> {error}
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div 
          className="p-16 rounded border text-center space-y-3 font-mono"
          style={{
            backgroundColor: 'var(--bg-surface)',
            borderColor: 'var(--border-hairline)',
          }}
        >
          <RefreshCw className="w-8 h-8 animate-spin mx-auto" style={{ color: 'var(--accent)' }} />
          <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
            Comparing baseline and current scan...
          </h3>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Resolving canonical semantic structures, calculating score drift, and evaluating quality gates.
          </p>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && !diffResult && (
        <div 
          className="p-16 rounded border text-center space-y-3 font-mono"
          style={{
            backgroundColor: 'var(--bg-surface)',
            borderColor: 'var(--border-hairline)',
          }}
        >
          <GitCompare className="w-10 h-10 mx-auto" style={{ color: 'var(--accent)' }} />
          <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
            Scan Comparison Ready
          </h3>
          <p className="text-xs max-w-md mx-auto" style={{ color: 'var(--text-muted)' }}>
            Compare two scans to see health drift, new findings, resolved findings, and CI quality-gate status.
          </p>
        </div>
      )}

      {/* Diff Dashboard (Success State) */}
      {!loading && diffResult && (
        <div className="space-y-6">
          {/* 1. Quality Gate Decision Card */}
          <div 
            className="p-4 rounded border flex flex-col md:flex-row items-start md:items-center justify-between gap-3"
            style={{
              backgroundColor: diffResult.quality_gate.passed ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
              borderColor: diffResult.quality_gate.passed ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)',
            }}
          >
            <div className="flex items-center gap-3">
              {diffResult.quality_gate.passed ? (
                <ShieldCheck className="w-6 h-6 text-emerald-500 shrink-0" />
              ) : (
                <ShieldAlert className="w-6 h-6 text-red-500 shrink-0" />
              )}
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                    Quality Gate Verdict:
                  </span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded border ${diffResult.quality_gate.passed ? 'text-emerald-500 bg-emerald-950/40 border-emerald-800' : 'text-red-500 bg-red-950/40 border-red-800'}`}>
                    {diffResult.quality_gate.passed ? 'PASS' : 'FAIL'}
                  </span>
                </div>
                {diffResult.quality_gate.reasons.length > 0 ? (
                  <ul className="text-xs mt-1 space-y-0.5 text-red-400">
                    {diffResult.quality_gate.reasons.map((r, i) => (
                      <li key={i}>• {r}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs mt-0.5 text-emerald-400">
                    All quality gate policies satisfied. Safe for pull-request merge.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* 2. Health Score Drift & Category Drift */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Overall Score Comparison Card */}
            <div 
              className="p-5 rounded border flex flex-col justify-between"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <div className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                Health Score Comparison
              </div>

              <div className="my-4 flex items-center justify-between">
                <div>
                  <div className="text-[10px] uppercase font-bold" style={{ color: 'var(--text-muted)' }}>Baseline</div>
                  <div className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                    {diffResult.score_drift.baseline_score.toFixed(1)}
                  </div>
                </div>

                <ArrowRight className="w-5 h-5 text-muted shrink-0" />

                <div>
                  <div className="text-[10px] uppercase font-bold" style={{ color: 'var(--text-muted)' }}>Current</div>
                  <div className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                    {diffResult.score_drift.current_score.toFixed(1)}
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t flex items-center justify-between text-xs" style={{ borderColor: 'var(--border-hairline)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Delta:</span>
                <span 
                  className="font-bold flex items-center gap-1"
                  style={{
                    color: diffResult.score_drift.overall_delta > 0 
                      ? 'var(--accent)' 
                      : diffResult.score_drift.overall_delta < 0 
                      ? 'var(--severity-critical)' 
                      : 'var(--text-muted)',
                  }}
                >
                  {diffResult.score_drift.overall_delta > 0 ? (
                    <ArrowUpRight className="w-4 h-4" />
                  ) : diffResult.score_drift.overall_delta < 0 ? (
                    <ArrowDownRight className="w-4 h-4" />
                  ) : (
                    <Minus className="w-4 h-4" />
                  )}
                  {diffResult.score_drift.overall_delta >= 0 ? `+${diffResult.score_drift.overall_delta.toFixed(1)}` : diffResult.score_drift.overall_delta.toFixed(1)}
                  {' '}({diffResult.score_drift.direction})
                </span>
              </div>
            </div>

            {/* Category Drift Breakdown Table */}
            <div 
              className="md:col-span-2 p-5 rounded border space-y-3"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <div className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                Category Drift Breakdown
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b" style={{ borderColor: 'var(--border-hairline)', color: 'var(--text-muted)' }}>
                      <th className="py-1.5 font-bold uppercase">Architecture Category</th>
                      <th className="py-1.5 text-right font-bold uppercase">Baseline</th>
                      <th className="py-1.5 text-right font-bold uppercase">Current</th>
                      <th className="py-1.5 text-right font-bold uppercase">Delta</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y" style={{ borderColor: 'var(--border-hairline)' }}>
                    {Object.entries(diffResult.score_drift.category_deltas).map(([cat, delta]) => {
                      const baseCat = diffResult.score_drift.baseline_categories[cat] ?? 100;
                      const currCat = diffResult.score_drift.current_categories[cat] ?? 100;
                      return (
                        <tr key={cat}>
                          <td className="py-2 capitalize font-medium" style={{ color: 'var(--text-primary)' }}>
                            {cat} Architecture
                          </td>
                          <td className="py-2 text-right font-mono" style={{ color: 'var(--text-secondary)' }}>
                            {baseCat}
                          </td>
                          <td className="py-2 text-right font-mono font-bold" style={{ color: 'var(--text-primary)' }}>
                            {currCat}
                          </td>
                          <td 
                            className="py-2 text-right font-mono font-bold"
                            style={{
                              color: delta > 0 ? 'var(--accent)' : delta < 0 ? 'var(--severity-critical)' : 'var(--text-muted)',
                            }}
                          >
                            {delta > 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* 3. Finding Transitions Counters */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div 
              className="p-3.5 rounded border flex items-center justify-between"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-red-400">New (+)</div>
                <div className="text-xl font-bold text-red-500 font-mono">{diffResult.counts.new}</div>
              </div>
              <span className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
            </div>

            <div 
              className="p-3.5 rounded border flex items-center justify-between"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Resolved (-)</div>
                <div className="text-xl font-bold text-emerald-500 font-mono">{diffResult.counts.resolved}</div>
              </div>
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
            </div>

            <div 
              className="p-3.5 rounded border flex items-center justify-between"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Modified (Δ)</div>
                <div className="text-xl font-bold text-amber-500 font-mono">{diffResult.counts.modified}</div>
              </div>
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
            </div>

            <div 
              className="p-3.5 rounded border flex items-center justify-between"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Persistent (=)</div>
                <div className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>{diffResult.counts.persistent}</div>
              </div>
              <span className="w-2.5 h-2.5 rounded-full bg-neutral-400/80" />
            </div>
          </div>

          {/* 4. Section: NEW Findings */}
          {newFindings.length > 0 && (
            <div className="space-y-3">
              <div className="text-xs font-bold uppercase tracking-wider flex items-center gap-2 text-red-400">
                <span>Newly Introduced Issues (+{newFindings.length})</span>
              </div>

              <div className="space-y-2">
                {newFindings.map((f, idx) => {
                  const badgeStyle = getSeverityBadgeStyle(f.severity);
                  const isExp = !!expandedFindings[`new-${idx}`];
                  return (
                    <div 
                      key={`new-${idx}`}
                      className="p-3.5 rounded border space-y-2 transition"
                      style={{
                        backgroundColor: 'var(--bg-surface)',
                        borderColor: badgeStyle.border,
                      }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span 
                              className="text-[10px] font-bold px-2 py-0.5 rounded border"
                              style={{
                                backgroundColor: badgeStyle.bg,
                                borderColor: badgeStyle.border,
                                color: badgeStyle.color,
                              }}
                            >
                              {f.severity}
                            </span>
                            <span className="font-bold text-xs" style={{ color: 'var(--text-primary)' }}>
                              {f.rule_id}
                            </span>
                            {f.location && (
                              <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                                • {f.location}
                              </span>
                            )}
                          </div>
                          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                            {f.title}
                          </p>
                        </div>

                        {f.evidence && (
                          <button
                            onClick={() => toggleFindingExpanded(`new-${idx}`)}
                            className="p-1 rounded text-muted hover:text-primary transition"
                            title="Toggle Evidence"
                          >
                            {isExp ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </button>
                        )}
                      </div>

                      {isExp && f.evidence && (
                        <div 
                          className="p-2.5 rounded border text-[11px] font-mono whitespace-pre-wrap mt-2"
                          style={{
                            backgroundColor: 'var(--bg-canvas)',
                            borderColor: 'var(--border-hairline)',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          <strong>Evidence:</strong> {f.evidence}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 5. Section: RESOLVED Findings */}
          {resolvedFindings.length > 0 && (
            <div className="space-y-3">
              <div className="text-xs font-bold uppercase tracking-wider flex items-center gap-2 text-emerald-400">
                <span>Resolved Issues (-{resolvedFindings.length})</span>
              </div>

              <div className="space-y-2">
                {resolvedFindings.map((f, idx) => (
                  <div 
                    key={`res-${idx}`}
                    className="p-3.5 rounded border flex items-center justify-between gap-3"
                    style={{
                      backgroundColor: 'rgba(16, 185, 129, 0.04)',
                      borderColor: 'rgba(16, 185, 129, 0.25)',
                    }}
                  >
                    <div className="flex items-center gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-xs text-emerald-400">
                            {f.rule_id}
                          </span>
                          {f.location && (
                            <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                              • {f.location}
                            </span>
                          )}
                        </div>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                          {f.title}
                        </p>
                      </div>
                    </div>
                    <span className="text-[10px] uppercase font-bold text-emerald-500">
                      RESOLVED
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 6. Section: MODIFIED Severity Findings */}
          {modifiedFindings.length > 0 && (
            <div className="space-y-3">
              <div className="text-xs font-bold uppercase tracking-wider flex items-center gap-2 text-amber-400">
                <span>Modified Findings (Δ{modifiedFindings.length})</span>
              </div>

              <div className="space-y-2">
                {modifiedFindings.map((f, idx) => (
                  <div 
                    key={`mod-${idx}`}
                    className="p-3.5 rounded border flex items-center justify-between gap-3"
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      borderColor: 'rgba(245, 158, 11, 0.3)',
                    }}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs" style={{ color: 'var(--text-primary)' }}>
                          {f.rule_id}
                        </span>
                        {f.location && (
                          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                            • {f.location}
                          </span>
                        )}
                      </div>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                        {f.title}
                      </p>
                    </div>

                    <div className="flex items-center gap-1.5 text-xs font-mono">
                      <span className="text-neutral-400">{f.baseline_severity}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-muted" />
                      <span className="font-bold text-amber-400">{f.severity}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 7. Section: PERSISTENT Findings (Collapsible) */}
          {persistentFindings.length > 0 && (
            <div 
              className="rounded border overflow-hidden"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <button
                onClick={() => setShowPersistent(!showPersistent)}
                className="w-full p-3.5 flex items-center justify-between text-xs font-bold uppercase tracking-wider transition"
                style={{ color: 'var(--text-secondary)' }}
              >
                <span>Persistent Issues ({persistentFindings.length})</span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] lowercase text-muted font-normal">
                    {showPersistent ? 'Hide unchanged findings' : 'Show unchanged findings'}
                  </span>
                  {showPersistent ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </div>
              </button>

              {showPersistent && (
                <div className="p-3.5 border-t space-y-2" style={{ borderColor: 'var(--border-hairline)' }}>
                  {persistentFindings.map((f, idx) => {
                    const badgeStyle = getSeverityBadgeStyle(f.severity);
                    return (
                      <div 
                        key={`per-${idx}`}
                        className="p-2.5 rounded border text-xs flex items-center justify-between"
                        style={{
                          backgroundColor: 'var(--bg-canvas)',
                          borderColor: 'var(--border-hairline)',
                        }}
                      >
                        <div className="flex items-center gap-2">
                          <span 
                            className="text-[10px] font-bold px-1.5 py-0.2 rounded border"
                            style={{
                              backgroundColor: badgeStyle.bg,
                              borderColor: badgeStyle.border,
                              color: badgeStyle.color,
                            }}
                          >
                            {f.severity}
                          </span>
                          <span className="font-bold" style={{ color: 'var(--text-primary)' }}>
                            {f.rule_id}
                          </span>
                          {f.location && (
                            <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                              • {f.location}
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] text-muted">UNCHANGED</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
