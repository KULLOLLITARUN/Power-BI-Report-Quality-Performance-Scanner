import React, { useState, useRef } from 'react';
import { Check, ChevronRight, CircleX, ClipboardCopy, Download, FileUp, FolderOpen, GitCompareArrows, RefreshCw, Terminal, X } from 'lucide-react';
import type { DiffResult, FindingTransition, ScanResult } from '../types';
import { apiFetch } from '../utils/api';
import { sortFindings } from '../lib/severity';
import { SevMarker, copyText, useToast } from '../components/ui';
import { errorMessage } from '../lib/errors';
import { parseAuditJson } from '../lib/auditJson';

interface JsonDropzoneProps {
  id: string;
  label: string;
  sublabel: string;
  placeholder: string;
  value: string;
  data: Record<string, unknown> | null;
  loadedLabel?: string;
  onClear: () => void;
  onFileLoaded: (data: Record<string, unknown>, filename: string) => void;
  onChangeText: (text: string) => void;
  onBrowse: () => void;
  children?: React.ReactNode;
}

const JsonDropzone: React.FC<JsonDropzoneProps> = ({
  id,
  label,
  sublabel,
  placeholder,
  value,
  data,
  loadedLabel,
  onClear,
  onFileLoaded,
  onChangeText,
  onBrowse,
  children,
}) => {
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);
  const loadSeq = useRef(0);
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = async (file: File, extraCount = 0) => {
    const seq = ++loadSeq.current;
    const note = extraCount > 0 ? ` (Note: ${extraCount} other file(s) ignored)` : '';
    try {
      const text = await file.text();
      if (seq !== loadSeq.current) return;
      const res = parseAuditJson(text, file.name);
      if (!res.ok) {
        toast(`${res.error}${note}`, 'error');
        return;
      }
      onFileLoaded(res.value.data, file.name);
      toast(`Loaded ${file.name} (${res.value.report_name})${note}`, 'info');
    } catch (err) {
      if (seq !== loadSeq.current) return;
      toast(`Could not read "${file.name}": ${errorMessage(err)}${note}`, 'error');
    }
  };

  const handleClear = () => {
    loadSeq.current++;
    onClear();
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div
      className={`blk cmp-dropzone${isDragging ? ' dragging' : ''}`}
      onDragEnter={(e) => {
        if (!Array.from(e.dataTransfer?.types || []).includes('Files')) return;
        e.preventDefault();
        e.stopPropagation();
        dragDepth.current++;
        setIsDragging(true);
      }}
      onDragOver={(e) => {
        if (!Array.from(e.dataTransfer?.types || []).includes('Files')) return;
        e.preventDefault();
        e.stopPropagation();
      }}
      onDragLeave={(e) => {
        if (!Array.from(e.dataTransfer?.types || []).includes('Files')) return;
        e.preventDefault();
        e.stopPropagation();
        dragDepth.current = Math.max(0, dragDepth.current - 1);
        if (dragDepth.current === 0) {
          setIsDragging(false);
        }
      }}
      onDrop={async (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragDepth.current = 0;
        setIsDragging(false);
        const files = Array.from(e.dataTransfer?.files || []);
        if (!files.length) return;
        const f = files[0];
        if (!f.name.toLowerCase().endsWith('.json')) {
          loadSeq.current++;
          const note = files.length > 1 ? ` (Note: ${files.length - 1} other file(s) ignored)` : '';
          toast(`Only .json audit files can be dropped here. For .pbip folders, enter the folder path or use Browse.${note}`, 'error');
          return;
        }
        await handleFile(f, files.length - 1);
      }}
    >
      <label className="label" htmlFor={id}>
        {label} <span style={{ textTransform: 'none', letterSpacing: 0 }}>· {sublabel}</span>
      </label>
      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
          e.target.value = '';
        }}
      />
      <div style={{ display: 'flex', gap: 6 }}>
        <input
          id={id}
          className="input mono"
          style={{ flex: 1 }}
          value={value}
          onChange={(e) => {
            loadSeq.current++;
            onChangeText(e.target.value);
          }}
          placeholder={placeholder}
        />
        <button
          className="btn icon-btn"
          onClick={() => fileInputRef.current?.click()}
          title="Upload scan.json artifact"
          aria-label={`Upload ${label} JSON`}
        >
          <FileUp aria-hidden="true" />
        </button>
        <button
          className="btn icon-btn"
          onClick={onBrowse}
          title="Browse local folder"
          aria-label={`Browse for ${label} folder`}
        >
          <FolderOpen aria-hidden="true" />
        </button>
      </div>
      {(children || data) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
          {children}
          {data && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span className="chip" style={{ color: 'var(--good)' }}>
                ✓ {loadedLabel || 'JSON loaded'}: {(typeof data.report_name === 'string' && data.report_name) || 'audit'}
              </span>
              <button
                className="btn btn-ghost icon-btn"
                style={{ padding: '0 4px', height: 20 }}
                onClick={handleClear}
                title="Clear JSON"
              >
                <X size={12} aria-hidden="true" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const CompareScreen: React.FC<{
  hasBackend: boolean;
  initialBaseline?: string;
  activeScan?: ScanResult | null;
}> = ({ hasBackend, initialBaseline = '', activeScan }) => {
  const toast = useToast();
  const [baseline, setBaseline] = useState(initialBaseline);
  const [current, setCurrent] = useState('');
  const [baselineData, setBaselineData] = useState<Record<string, unknown> | null>(null);
  const [currentData, setCurrentData] = useState<Record<string, unknown> | null>(null);
  const [failOnRegression, setFailOnRegression] = useState(false);
  const [failOnNew, setFailOnNew] = useState('NONE');
  const [maxDrop, setMaxDrop] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiffResult | null>(null);

  const useActiveScanAsCurrent = () => {
    if (!activeScan) return;
    const jsonPayload: Record<string, unknown> = {
      report_name: activeScan.report_name,
      scores: activeScan.scores,
      findings: activeScan.findings,
      scanner_version: activeScan.scanner_version,
      warnings: activeScan.warnings,
    };
    setCurrentData(jsonPayload);
    setCurrent(`${activeScan.report_name} (active scan)`);
    toast(`Using active scan: ${activeScan.report_name}`, 'info');
  };

  const browse = async (target: 'baseline' | 'current') => {
    try {
      const res = await apiFetch('/api/native-dialog', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'folder' }) });
      const data = await res.json().catch(() => ({}));
      if (res.ok && !data.canceled && data.path) {
        if (target === 'baseline') {
          setBaselineData(null);
          setBaseline(data.path);
        } else {
          setCurrentData(null);
          setCurrent(data.path);
        }
      }
      else if (!res.ok) toast(data.detail || 'The folder picker is unavailable. Type the path instead.', 'error');
    } catch {
      toast('The folder picker is unavailable. Type the path instead.', 'error');
    }
  };

  const run = async () => {
    setLoading(true); setError(null); setResult(null);
    try {
      const payload: Record<string, unknown> = { fail_on_regression: failOnRegression };

      if (baselineData) {
        payload.baseline_data = baselineData;
      } else {
        payload.baseline_path = baseline.trim();
      }

      if (currentData) {
        payload.current_data = currentData;
      } else {
        payload.current_path = current.trim();
      }

      if (failOnNew !== 'NONE') payload.fail_on_new = failOnNew;
      if (maxDrop.trim() && !Number.isNaN(Number(maxDrop))) payload.max_score_drop = Number(maxDrop);

      const res = await apiFetch('/api/diff', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Comparison failed (${res.status})`);
      setResult(data);
    } catch (e) {
      setError(errorMessage(e) || 'Comparison failed.');
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

  const by = (state: FindingTransition['state']) => sortFindings((result?.transitions || []).filter((t) => t.state === state));

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
            <JsonDropzone
              id="cmp-baseline"
              label="Baseline"
              sublabel="Main branch, previous scan, or scan.json"
              placeholder="Drop scan.json or path (e.g. C:\Reports\Sales.pbip)"
              value={baseline}
              data={baselineData}
              onClear={() => {
                setBaselineData(null);
                setBaseline('');
              }}
              onFileLoaded={(data, name) => {
                setBaselineData(data);
                setBaseline(name);
              }}
              onChangeText={(text) => {
                if (baselineData) setBaselineData(null);
                setBaseline(text);
              }}
              onBrowse={() => browse('baseline')}
            />

            <JsonDropzone
              id="cmp-current"
              label="Current"
              sublabel="Your branch or new version"
              placeholder="Drop scan.json, path, or use active scan"
              value={current}
              data={currentData}
              loadedLabel="Current loaded"
              onClear={() => {
                setCurrentData(null);
                setCurrent('');
              }}
              onFileLoaded={(data, name) => {
                setCurrentData(data);
                setCurrent(name);
              }}
              onChangeText={(text) => {
                if (currentData) setCurrentData(null);
                setCurrent(text);
              }}
              onBrowse={() => browse('current')}
            >
              {activeScan && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ fontSize: 11, padding: '2px 8px', height: 22 }}
                  onClick={useActiveScanAsCurrent}
                >
                  <Check size={12} aria-hidden="true" /> Use active scan ({activeScan.report_name})
                </button>
              )}
            </JsonDropzone>
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
            <button className="btn btn-primary" onClick={run} disabled={loading || (!baseline.trim() && !baselineData) || (!current.trim() && !currentData)}>
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
