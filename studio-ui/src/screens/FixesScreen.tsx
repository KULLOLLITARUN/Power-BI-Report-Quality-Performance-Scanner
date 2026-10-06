import React, { useCallback, useEffect, useState } from 'react';
import { ChevronRight, CircleCheck, CircleX, History, RefreshCw, Terminal, TriangleAlert, Wrench } from 'lucide-react';
import type { AuditFinding } from '../types';
import { apiFetch } from '../utils/api';
import { FIXABLE_RULES } from '../components/Findings';
import { copyText, useToast } from '../components/ui';

interface PatchChunk { start_line: number; end_line: number; original_text: string; replacement_text: string }
interface Patch {
  patch_id: string; rule_id: string; file_path: string; safety: string; state: string; rationale: string;
  evidence: { rule_id: string; safety: string; semantic_risk: string; affected_objects: string[]; expected_resolution: string };
  chunks: PatchChunk[];
}
interface Validation {
  accepted: boolean; before_score: number; after_score: number; score_delta: number;
  resolved_count: number; new_high_critical_count: number; rejection_reasons: string[];
}
interface Plan { model_path: string; created_at: string; patches: Patch[]; conflicts: unknown[] }
interface Manifest {
  manifest_id: string; created_at: string; decision: string; actor: string;
  before_score: number; after_score: number; score_delta: number; applied_count: number; rollback_executed: boolean;
}

/** Lines of a patch chunk; a trailing newline is not an extra empty line. */
const chunkLines = (text: string) => {
  const t = (text ?? '').replace(/\r\n/g, '\n').replace(/\n$/, '');
  return t === '' ? [] : t.split('\n'); // an empty replacement is a pure deletion
};

/** A patched file's path relative to the project folder, for display. */
function relativeTo(base: string, file: string): string {
  const b = base.replace(/\\/g, '/').replace(/\/+$/, '');
  const f = file.replace(/\\/g, '/');
  if (b && f.toLowerCase().startsWith(`${b.toLowerCase()}/`)) return f.slice(b.length + 1);
  return file;
}

const riskColor = (r: string) => (r === 'LOW' ? 'var(--good)' : r === 'MEDIUM' ? 'var(--sev-medium)' : 'var(--sev-high)');

export const FixesScreen: React.FC<{
  projectPath: string; findings: AuditFinding[]; hasBackend: boolean; isLocal: boolean; onApplied: () => void;
}> = ({ projectPath, findings, hasBackend, isLocal, onApplied }) => {
  const toast = useToast();
  const [tab, setTab] = useState<'plan' | 'history'>('plan');
  const [plan, setPlan] = useState<Plan | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [applying, setApplying] = useState(false);
  const [history, setHistory] = useState<Manifest[]>([]);
  const live = hasBackend && isLocal;

  const loadPlan = useCallback(async () => {
    if (!live || !projectPath) return;
    setLoading(true); setError(null);
    try {
      const res = await apiFetch('/api/remediation/plan', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_path: projectPath }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Planning failed (${res.status})`);
      setPlan(data.plan); setValidation(data.validation);
      const ids = new Set<string>((data.plan?.patches || []).map((p: Patch) => p.patch_id));
      setSelected(ids);
      setOpen(new Set([...ids].slice(0, 3)));
    } catch (e: any) {
      setError(e.message || 'Could not build a fix plan.');
    } finally {
      setLoading(false);
    }
  }, [live, projectPath]);

  const loadHistory = useCallback(async () => {
    if (!live || !projectPath) return;
    try {
      const res = await apiFetch(`/api/remediation/history?project_path=${encodeURIComponent(projectPath)}`);
      if (res.ok) setHistory((await res.json()).history || []);
    } catch { /* history is optional */ }
  }, [live, projectPath]);

  useEffect(() => { loadPlan(); loadHistory(); }, [loadPlan, loadHistory]);

  const apply = async () => {
    setApplying(true); setError(null);
    try {
      const res = await apiFetch('/api/remediation/apply', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath, patch_ids: [...selected], backup: true }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) throw new Error(data.manifest?.rejection_reasons?.join('; ') || data.detail || 'The fixes were not applied.');
      const n = data.manifest?.applied_patches?.length ?? selected.size;
      toast(`Applied ${n} fix${n === 1 ? '' : 'es'}. Score is now ${Number(data.manifest?.after_score ?? 0).toFixed(1)}.`);
      setConfirming(false);
      await Promise.all([loadPlan(), loadHistory()]);
      onApplied();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setApplying(false);
    }
  };

  const toggle = (set: Set<string>, id: string) => { const n = new Set(set); n.has(id) ? n.delete(id) : n.add(id); return n; };
  const fixable = findings.filter((f) => FIXABLE_RULES.has(f.rule_id));
  const destructive = plan?.patches.some((p) => selected.has(p.patch_id) && p.rule_id === 'DAX_UNUSED_MEASURE');

  if (!live) {
    const cmd = `pbiscan fix "${projectPath || 'path/to/report.pbip'}"`;
    return (
      <>
        <div className="page-head"><div><h2>Fixes</h2><p>pbiscan patches TMDL files for {FIXABLE_RULES.size} rules, re-parses every file it touches, and keeps a backup and an audit record.</p></div></div>
        <div className="notice"><Terminal aria-hidden="true" />
          <div className="grow">
            <strong>Fixes write to your project files, so they need the local engine.</strong>{' '}
            {hasBackend ? 'This project was opened in the browser, not from disk. Open it with "Open project" to plan fixes.' : 'Run Studio from a terminal, or preview the plan with the CLI:'}
            {!hasBackend && <pre className="code" style={{ marginTop: 8 }}>{cmd}</pre>}
            {!hasBackend && <div className="actions" style={{ marginTop: 8 }}><button className="btn btn-sm" onClick={async () => toast((await copyText(cmd)) ? 'Copied the command.' : 'Copying is blocked here.')}>Copy command</button></div>}
          </div>
        </div>
        <section className="panel">
          <div className="panel-head"><h3>Findings with an automatic fix</h3><span className="spacer" /><span className="label">{fixable.length}</span></div>
          {fixable.length ? fixable.map((f, i) => (
            <div key={i} className="trans"><span className="state">{f.rule_id.split('_')[0]}</span><span className="t">{f.title}</span><span /><span className="s">{f.location}</span></div>
          )) : <div className="empty">None of this project's findings have an automatic fix.</div>}
        </section>
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <div><h2>Fixes</h2><p>Review each patch before writing it. pbiscan backs up every file, re-parses it after the edit, and rejects edits that break the project.</p></div>
        <div className="actions">
          <div className="seg" role="group" aria-label="View">
            <button aria-pressed={tab === 'plan'} onClick={() => setTab('plan')}>Proposed fixes</button>
            <button aria-pressed={tab === 'history'} onClick={() => setTab('history')}>History ({history.length})</button>
          </div>
          <button className="btn" onClick={() => { loadPlan(); loadHistory(); }} disabled={loading}><RefreshCw className={loading ? 'spin' : ''} aria-hidden="true" />Refresh</button>
        </div>
      </div>
      {error && <div className="notice error"><CircleX aria-hidden="true" /><span className="grow"><strong>Fixes failed.</strong> {error}</span></div>}

      {tab === 'plan' && (
        <>
          {validation && plan && plan.patches.length > 0 && (
            <div className="panel grid-4">
              <div className="stat"><b>{validation.before_score.toFixed(1)} → {validation.after_score.toFixed(1)}</b><span>projected score</span></div>
              <div className="stat"><b>{validation.resolved_count}</b><span>findings resolved</span></div>
              <div className="stat"><b style={{ color: validation.new_high_critical_count ? 'var(--sev-critical)' : undefined }}>{validation.new_high_critical_count}</b><span>new high/critical</span></div>
              <div className="stat"><b style={{ color: validation.accepted ? 'var(--good)' : 'var(--sev-critical)' }}>{validation.accepted ? 'Passes' : 'Rejected'}</b><span>sandbox check</span></div>
            </div>
          )}
          {validation && !validation.accepted && validation.rejection_reasons.length > 0 && (
            <div className="notice error"><TriangleAlert aria-hidden="true" /><div className="grow"><strong>The sandbox rejected this plan.</strong><ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>{validation.rejection_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></div></div>
          )}
          <section className="panel" aria-label="Proposed fixes">
            <div className="panel-head">
              <h3>{plan ? `${plan.patches.length} proposed fix${plan.patches.length === 1 ? '' : 'es'}` : 'Proposed fixes'}</h3>
              <span className="spacer" />
              {plan && plan.patches.length > 0 && (
                <label className="check"><input type="checkbox" checked={selected.size === plan.patches.length}
                  onChange={() => setSelected(selected.size === plan.patches.length ? new Set() : new Set(plan.patches.map((p) => p.patch_id)))} />Select all</label>
              )}
            </div>
            {loading && !plan ? <div className="empty"><RefreshCw className="spin" aria-hidden="true" /><span>Planning fixes and checking them in a sandbox…</span></div>
              : !plan || plan.patches.length === 0 ? <div className="empty"><CircleCheck aria-hidden="true" /><strong>Nothing to fix automatically</strong><span>No open finding has a safe automatic patch.</span></div>
              : plan.patches.map((p) => (
                <div className="patch" key={p.patch_id}>
                  <div className="patch-head">
                    <input type="checkbox" aria-label={`Include ${p.patch_id}`} checked={selected.has(p.patch_id)} onChange={() => setSelected(toggle(selected, p.patch_id))} style={{ accentColor: 'var(--accent)', marginTop: 3 }} />
                    <span className="title">{p.rationale}</span>
                    <button className="btn btn-ghost btn-sm" aria-expanded={open.has(p.patch_id)} onClick={() => setOpen(toggle(open, p.patch_id))}>
                      <ChevronRight aria-hidden="true" style={{ transform: open.has(p.patch_id) ? 'rotate(90deg)' : undefined, transition: 'transform .15s' }} />Diff
                    </button>
                    <span className="sub">
                      <span>{p.rule_id}</span><span>{relativeTo(projectPath, p.file_path)}</span>
                      <span style={{ color: riskColor(p.evidence?.semantic_risk) }}>{p.evidence?.semantic_risk} risk</span>
                      <span>{p.safety.replace(/_/g, ' ').toLowerCase()}</span>
                    </span>
                  </div>
                  {open.has(p.patch_id) && (
                    <div className="patch-body">
                      {p.chunks.map((c, i) => (
                        <div className="blk" key={i}>
                          <div className="diff-head"><span>lines {c.start_line}–{c.end_line}</span></div>
                          <pre className="code diff">
                            {chunkLines(c.original_text).map((l, k) => <span key={`d${k}`} className="l del">- {l}</span>)}
                            {chunkLines(c.replacement_text).map((l, k) => <span key={`a${k}`} className="l add">+ {l}</span>)}
                          </pre>
                        </div>
                      ))}
                      {p.evidence?.affected_objects?.length > 0 && <p className="mono muted" style={{ margin: 0, fontSize: 12 }}>Affects: {p.evidence.affected_objects.join(', ')}</p>}
                    </div>
                  )}
                </div>
              ))}
            {plan && plan.patches.length > 0 && (
              <div className="list-foot">
                {confirming ? (
                  <div className="confirm" style={{ width: '100%' }}>
                    <span>Write <strong>{selected.size} fix{selected.size === 1 ? '' : 'es'}</strong> to <strong className="mono">{projectPath}</strong>? Each file is backed up first, and the whole batch is rolled back if any edited file no longer parses.</span>
                    {destructive && <span style={{ color: 'var(--sev-high)' }}>This includes deleting measures. Reports outside this project that use them will break.</span>}
                    <div className="actions">
                      <button className={`btn ${destructive ? 'btn-danger' : 'btn-primary'}`} onClick={apply} disabled={applying}>{applying ? 'Writing…' : `Write ${selected.size} fix${selected.size === 1 ? '' : 'es'}`}</button>
                      <button className="btn" onClick={() => setConfirming(false)} disabled={applying}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <button className="btn btn-primary" disabled={!selected.size || !validation?.accepted} onClick={() => setConfirming(true)}>
                    <Wrench aria-hidden="true" />Apply {selected.size} selected…
                  </button>
                )}
              </div>
            )}
          </section>
        </>
      )}

      {tab === 'history' && (
        <section className="panel" aria-label="Fix history">
          <div className="panel-head"><History size={16} aria-hidden="true" /><h3>Applied fixes</h3></div>
          {history.length === 0 ? <div className="empty">No fixes have been applied to this project yet.</div>
            : <div className="table-wrap"><table className="table">
              <thead><tr><th>When</th><th>Result</th><th>Fixes</th><th>Score</th><th>Record</th></tr></thead>
              <tbody>{history.map((h) => (
                <tr key={h.manifest_id}>
                  <td>{new Date(h.created_at).toLocaleString()}</td>
                  <td style={{ color: h.rollback_executed ? 'var(--sev-critical)' : 'var(--good)' }}>{h.rollback_executed ? 'Rolled back' : h.decision.toLowerCase()}</td>
                  <td className="num">{h.applied_count}</td>
                  <td className="mono">{h.before_score.toFixed(1)} → {h.after_score.toFixed(1)}</td>
                  <td className="mono muted">{h.manifest_id}</td>
                </tr>
              ))}</tbody>
            </table></div>}
        </section>
      )}
    </>
  );
};
