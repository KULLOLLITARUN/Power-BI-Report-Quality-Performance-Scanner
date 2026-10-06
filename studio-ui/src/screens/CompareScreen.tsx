import React, { useState } from 'react';
import { ChevronRight, CircleX, ClipboardCopy, Download, FolderOpen, GitCompareArrows, RefreshCw, Terminal } from 'lucide-react';
import type { DiffResult, FindingTransition } from '../types';
import { apiFetch } from '../utils/api';
import { sortFindings } from '../lib/severity';
import { SevMarker, copyText, useToast } from '../components/ui';

export const CompareScreen: React.FC<{ hasBackend: boolean; initialBaseline?: string }> = ({ hasBackend, initialBaseline = '' }) => {
  const toast = useToast();
  const [baseline, setBaseline] = useState(initialBaseline);
  const [current, setCurrent] = useState('');
  const [failOnRegression, setFailOnRegression] = useState(false);
  const [failOnNew, setFailOnNew] = useState('NONE');
  const [maxDrop, setMaxDrop] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiffResult | null>(null);

  const browse = async (target: 'baseline' | 'current') => {
    try {
      const res = await apiFetch('/api/native-dialog', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'folder' }) });
      const data = await res.json().catch(() => ({}));
      if (res.ok && !data.canceled && data.path) (target === 'baseline' ? setBaseline : setCurrent)(data.path);
      else if (!res.ok) toast(data.detail || 'The folder picker is unavailable. Type the path instead.', 'error');
    } catch {
      toast('The folder picker is unavailable. Type the path instead.', 'error');
    }
  };

  const run = async () => {
    setLoading(true); setError(null); setResult(null);
    try {
      const payload: Record<string, unknown> = { baseline_path: baseline.trim(), current_path: current.trim(), fail_on_regression: failOnRegression };
      if (failOnNew !== 'NONE') payload.fail_on_new = failOnNew;
      if (maxDrop.trim() && !Number.isNaN(Number(maxDrop))) payload.max_score_drop = Number(maxDrop);
      const res = await apiFetch('/api/diff', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Comparison failed (${res.status})`);
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Comparison failed.');
    } finally {
      setLoading(false);
    }
  };

  const summary = (r: DiffResult) => [
    `pbiscan comparison: ${r.baseline_name} -> ${r.current_name}`,
    `Quality gate: ${r.quality_gate.passed ? 'PASS' : 'FAIL'}`,
    `Score: ${r.score_drift.baseline_score.toFixed(1)} -> ${r.score_drift.current_score.toFixed(1)} (${r.score_drift.overall_delta >= 0 ? '+' : ''}${r.score_drift.overall_delta.toFixed(1)})`,
    `New ${r.counts.new} · Resolved ${r.counts.resolved} · Changed ${r.counts.modified} · Unchanged ${r.counts.persistent}`,
    ...r.quality_gate.reasons.map((x) => `- ${x}`),
  ].join('\n');

  const exportJson = (r: DiffResult) => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url; a.download = `pbiscan-diff-${r.current_name || 'scan'}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  if (!hasBackend) {
    return (
      <>
        <div className="page-head"><div><h2>Compare scans</h2><p>Compare a baseline scan with a new one and apply a CI quality gate.</p></div></div>
        <div className="notice"><Terminal aria-hidden="true" /><div className="grow"><strong>Comparing reads two projects from disk, so it needs the local engine.</strong> Run it from a terminal:
          <pre className="code" style={{ marginTop: 8 }}>pbiscan diff baseline.json current.pbip --fail-on-regression --fail-on-new HIGH</pre></div></div>
      </>
    );
  }

  const by = (state: FindingTransition['state']) => sortFindings((result?.transitions || []).filter((t) => t.state === state) as any) as unknown as FindingTransition[];

  return (
    <>
      <div className="page-head">
        <div><h2>Compare scans</h2><p>Each side can be a .pbip project folder or a scan exported as JSON. The gate settings match the CLI flags, so CI gives the same verdict.</p></div>
        {result && (
          <div className="actions">
            <button className="btn" onClick={async () => toast((await copyText(summary(result))) ? 'Copied the summary.' : 'Copying is blocked here.')}><ClipboardCopy aria-hidden="true" />Copy summary</button>
            <button className="btn" onClick={() => exportJson(result)}><Download aria-hidden="true" />Export JSON</button>
          </div>
        )}
      </div>

      <section className="panel">
        <div className="panel-body">
          <div className="grid-2">
            {([['baseline', 'Baseline', 'Main branch or last release', baseline, setBaseline], ['current', 'Current', 'Your branch or the new version', current, setCurrent]] as const).map(([id, label, hint, value, set]) => (
              <div className="blk" key={id}>
                <label className="label" htmlFor={`cmp-${id}`}>{label} <span style={{ textTransform: 'none', letterSpacing: 0 }}>· {hint}</span></label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input id={`cmp-${id}`} className="input mono" style={{ flex: 1 }} value={value} onChange={(e) => set(e.target.value)} placeholder="C:\\Reports\\Sales.pbip or scan.json" />
                  <button className="btn icon-btn" onClick={() => browse(id)} aria-label={`Browse for ${label.toLowerCase()} folder`}><FolderOpen aria-hidden="true" /></button>
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: '10px 20px', flexWrap: 'wrap', alignItems: 'center', borderTop: '1px solid var(--rule)', paddingTop: 14 }}>
            <label className="check"><input type="checkbox" checked={failOnRegression} onChange={(e) => setFailOnRegression(e.target.checked)} />Fail if the score drops</label>
            <label className="check">Fail on new
              <select className="select" value={failOnNew} onChange={(e) => setFailOnNew(e.target.value)}>
                <option value="NONE">nothing</option><option value="CRITICAL">critical</option><option value="HIGH">high or worse</option>
                <option value="MEDIUM">medium or worse</option><option value="WARNING">warning or worse</option>
              </select>
            </label>
            <label className="check">Max score drop
              <input className="input" style={{ width: 70 }} inputMode="decimal" value={maxDrop} onChange={(e) => setMaxDrop(e.target.value)} placeholder="any" />
            </label>
            <span style={{ flex: 1 }} />
            <button className="btn btn-primary" onClick={run} disabled={loading || !baseline.trim() || !current.trim()}>
              {loading ? <RefreshCw className="spin" aria-hidden="true" /> : <GitCompareArrows aria-hidden="true" />}{loading ? 'Comparing…' : 'Compare'}
            </button>
          </div>
        </div>
      </section>

      {error && <div className="notice error"><CircleX aria-hidden="true" /><span className="grow"><strong>Comparison failed.</strong> {error}</span></div>}

      {result && (
        <>
          <section className={`panel gate ${result.quality_gate.passed ? 'pass' : 'fail'}`}>
            <span className="verdict">{result.quality_gate.passed ? 'Pass' : 'Fail'}</span>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div className="mono muted" style={{ fontSize: 12 }}>{result.baseline_name} → {result.current_name}</div>
              {result.quality_gate.reasons.length ? <ul>{result.quality_gate.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
                : <p className="ink-2" style={{ margin: '4px 0 0', fontSize: 13 }}>Every gate rule is satisfied.</p>}
            </div>
            <div className="stat" style={{ textAlign: 'right' }}>
              <b>{result.score_drift.baseline_score.toFixed(1)} → {result.score_drift.current_score.toFixed(1)}</b>
              <span style={{ color: result.score_drift.overall_delta < 0 ? 'var(--sev-critical)' : result.score_drift.overall_delta > 0 ? 'var(--good)' : undefined }}>
                {result.score_drift.overall_delta >= 0 ? '+' : ''}{result.score_drift.overall_delta.toFixed(1)} {result.score_drift.direction.toLowerCase()}
              </span>
            </div>
          </section>
          <div className="panel grid-4">
            <div className="stat"><b style={{ color: 'var(--sev-critical)' }}>{result.counts.new}</b><span>new</span></div>
            <div className="stat"><b style={{ color: 'var(--good)' }}>{result.counts.resolved}</b><span>resolved</span></div>
            <div className="stat"><b style={{ color: 'var(--sev-medium)' }}>{result.counts.modified}</b><span>changed severity</span></div>
            <div className="stat"><b>{result.counts.persistent}</b><span>unchanged</span></div>
          </div>
          {Object.keys(result.score_drift.category_deltas || {}).length > 0 && (
            <section className="panel"><div className="panel-head"><h3>By area</h3></div>
              <div className="table-wrap"><table className="table"><thead><tr><th>Area</th><th>Baseline</th><th>Current</th><th>Change</th></tr></thead>
                <tbody>{Object.entries(result.score_drift.category_deltas).map(([cat, d]) => (
                  <tr key={cat}><td>{cat}</td><td className="num">{result.score_drift.baseline_categories?.[cat]?.toFixed(1)}</td><td className="num">{result.score_drift.current_categories?.[cat]?.toFixed(1)}</td>
                    <td className="num" style={{ color: d < 0 ? 'var(--sev-critical)' : d > 0 ? 'var(--good)' : undefined }}>{d >= 0 ? '+' : ''}{d.toFixed(1)}</td></tr>
                ))}</tbody></table></div>
            </section>
          )}
          {(['NEW', 'RESOLVED', 'MODIFIED', 'PERSISTENT'] as const).map((state) => {
            const list = by(state);
            if (!list.length) return null;
            const titles = { NEW: 'New findings', RESOLVED: 'Resolved', MODIFIED: 'Changed severity', PERSISTENT: 'Unchanged' };
            return (
              <details key={state} className="panel disclosure" open={state !== 'PERSISTENT'}>
                <summary className="panel-head"><ChevronRight aria-hidden="true" /><h3>{titles[state]}</h3><span className="spacer" /><span className="label">{list.length}</span></summary>
                {list.map((t, i) => (
                  <div className="trans" key={`${t.finding_id}-${i}`}>
                    <span className={`state ${state.toLowerCase()}`}>{state === 'MODIFIED' ? `${t.baseline_severity}→` : ''}{state === 'PERSISTENT' ? 'SAME' : state}</span>
                    <span className="t">{t.title}</span>
                    <span><SevMarker sev={t.severity} /></span>
                    <span className="s">{t.rule_id}{t.location ? ` · ${t.location}` : ''}</span>
                  </div>
                ))}
              </details>
            );
          })}
        </>
      )}
    </>
  );
};
