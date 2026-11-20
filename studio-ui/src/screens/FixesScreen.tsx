import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, CircleCheck, CircleX, History, RefreshCw, Terminal, TriangleAlert, Wrench } from 'lucide-react';
import type { AuditFinding } from '../types';
import { apiFetch } from '../utils/api';
import { FIXABLE_RULES } from '../components/Findings';
import { SevMarker, copyText, useToast } from '../components/ui';
import { errorMessage } from '../lib/errors';

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

const riskColor = (r: string) => (r === 'LOW' ? 'var(--good)' : r === 'MEDIUM' ? 'var(--med)' : r === 'HIGH' ? 'var(--high)' : 'var(--muted)');

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
      setOpen(new Set((data.plan?.patches || []).slice(0, 1).map((p: Patch) => p.rule_id)));
    } catch (e) {
      setError(errorMessage(e) || 'Could not build a fix plan.');
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
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setApplying(false);
    }
  };

  const toggle = (set: Set<string>, id: string) => { const n = new Set(set); n.has(id) ? n.delete(id) : n.add(id); return n; };
  const fixable = findings.filter((f) => FIXABLE_RULES.has(f.rule_id));
  const byRule = useMemo(() => {
    const m = new Map<string, Patch[]>();
    for (const p of plan?.patches ?? []) m.set(p.rule_id, [...(m.get(p.rule_id) ?? []), p]);
    return [...m.entries()];
  }, [plan]);
  const toggleRule = (patches: Patch[]) => {
    const n = new Set(selected);
    const all = patches.every((p) => n.has(p.patch_id));
    for (const p of patches) { if (all) n.delete(p.patch_id); else n.add(p.patch_id); }
    setSelected(n);
  };
  const destructive = plan?.patches.some((p) => selected.has(p.patch_id) && p.rule_id === 'DAX_UNUSED_MEASURE');

  if (!live) {
    const cmd = `pbiscan fix "${projectPath || 'path/to/report.pbip'}"`;
    return (
      <>
        <div className="page-head"><div><p>pbiscan patches TMDL files for {FIXABLE_RULES.size} rules, re-parses every file it touches, and keeps a backup and an audit record.</p></div></div>
        <div className="notice"><Terminal aria-hidden="true" />
          <div className="grow">
            <strong>Fixes write to your project files, so they need the local engine.</strong>{' '}
            {hasBackend ? 'This project was opened in the browser, not from disk. Open it with "Open project" to plan fixes.' : 'Run Studio from a terminal, or preview the plan with the CLI:'}
            {!hasBackend && <pre className="code" style={{ marginTop: 8 }}>{cmd}</pre>}
            {!hasBackend && <div className="actions" style={{ marginTop: 8 }}><button className="btn btn-sm" onClick={async () => toast((await copyText(cmd)) ? 'Copied the command.' : 'Copying is blocked here.')}>Copy command</button></div>}
          </div>
        </div>
        <section className="panel">
          <div className="panel-head"><h2>Findings with an automatic fix</h2><span className="muted small">{fixable.length}</span></div>
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
        <div><p>Review each patch before writing it. pbiscan backs up every file, re-parses it after the edit, and rejects edits that break the project.</p></div>
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
          {validation && !validation.accepted && validation.rejection_reasons.length > 0 && (
            <div className="notice error"><TriangleAlert aria-hidden="true" /><div className="grow"><strong>The sandbox rejected this plan.</strong><ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>{validation.rejection_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></div></div>
          )}
          <div className="fixes-grid">
            <div className="fixes-list" aria-label="Proposed fixes">
              {plan && plan.patches.length > 0 && (
                <div className="fixes-bar">
                  <span className="muted">{byRule.length} proposed fix{byRule.length === 1 ? '' : 'es'}, {plan.patches.length} file edit{plan.patches.length === 1 ? '' : 's'}</span>
                  <span className="grow" />
                  <label className="check"><input type="checkbox" checked={selected.size === plan.patches.length}
                    onChange={() => setSelected(selected.size === plan.patches.length ? new Set() : new Set(plan.patches.map((p) => p.patch_id)))} />Select all</label>
                </div>
              )}
              {loading && !plan ? <div className="panel"><div className="empty"><RefreshCw className="spin" aria-hidden="true" /><span>Planning fixes and checking them in a sandbox…</span></div></div>
                : !plan || plan.patches.length === 0 ? <div className="panel"><div className="empty"><CircleCheck aria-hidden="true" /><strong>Nothing to fix automatically</strong><span>No open finding has a safe automatic patch.</span></div></div>
                : byRule.map(([rule, patches]) => {
                  const risks = patches.map((p) => (p.evidence?.semantic_risk || '').toUpperCase());
                  const risk = risks.includes('HIGH') ? 'HIGH' : risks.includes('MEDIUM') ? 'MEDIUM' : risks.includes('LOW') ? 'LOW' : '';
                  const title = findings.find((f) => f.rule_id === rule)?.title ?? rule;
                  const picked = patches.filter((p) => selected.has(p.patch_id)).length;
                  const files = new Set(patches.map((p) => p.file_path)).size;
                  return (
                    <article className="panel patch" key={rule}>
                      <div className="patch-head">
                        <label className="patch-pick">
                          <input type="checkbox" checked={picked === patches.length} ref={(el) => { if (el) el.indeterminate = picked > 0 && picked < patches.length; }}
                                 onChange={() => toggleRule(patches)} aria-label={`Include ${title}`} />
                          <span className="patch-text">
                            <span className="title">{title}</span>
                            <span className="muted">{patches[0].rationale}</span>
                            <span className="sub"><span className="mono">{rule}</span><span>{files} file{files === 1 ? '' : 's'} edited</span></span>
                          </span>
                        </label>
                        <span className="sev-label" style={{ color: riskColor(risk) }}><SevMarker sev={risk === 'HIGH' ? 'HIGH' : risk === 'MEDIUM' ? 'MEDIUM' : 'ADVISORY'} size={11} />{risk ? `${risk[0]}${risk.slice(1).toLowerCase()} risk` : 'Review required'}</span>
                        <button className="btn btn-quiet btn-sm" aria-expanded={open.has(rule)} onClick={() => setOpen(toggle(open, rule))}>
                          {open.has(rule) ? 'Hide changes' : 'Show changes'}
                        </button>
                      </div>
                      {open.has(rule) && (
                        <div className="patch-body">
                          {patches.map((p) => (
                            <div className="blk" key={p.patch_id}>
                              <div className="diff-head"><span>{relativeTo(projectPath, p.file_path)}</span><span>{p.safety.replace(/_/g, ' ').toLowerCase()}</span></div>
                              {p.chunks.map((c, i) => (
                                <pre className="code diff" key={i}>
                                  <span className="l ctx">lines {c.start_line}–{c.end_line}</span>
                                  {chunkLines(c.original_text).map((l, k) => <span key={`d${k}`} className="l del">- {l}</span>)}
                                  {chunkLines(c.replacement_text).map((l, k) => <span key={`a${k}`} className="l add">+ {l}</span>)}
                                </pre>
                              ))}
                            </div>
                          ))}
                        </div>
                      )}
                    </article>
                  );
                })}
            </div>

            {plan && plan.patches.length > 0 && (
              <aside className="panel fix-aside" aria-label="Result of applying">
                <div className="panel-head"><h2>{selected.size === plan.patches.length ? `If you apply all ${byRule.length}` : `If you apply ${byRule.filter(([, ps]) => ps.some((p) => selected.has(p.patch_id))).length} of ${byRule.length}`}</h2></div>
                <div className="panel-body">
                  {validation && (
                    <>
                      <div className="proj">
                        <span className="score muted">{validation.before_score.toFixed(1)}</span>
                        <ArrowRight aria-hidden="true" />
                        <span className="score">{validation.after_score.toFixed(1)}</span>
                      </div>
                      <p><span className={`chip ${validation.score_delta >= 0 ? 'good' : 'hot'}`}>{validation.score_delta >= 0 ? '+' : ''}{validation.score_delta.toFixed(1)} predicted</span></p>
                    </>
                  )}
                  <dl className="kv">
                    {validation && <><dt>Resolved</dt><dd>{validation.resolved_count} finding{validation.resolved_count === 1 ? '' : 's'}</dd></>}
                    {validation && <><dt>New problems</dt><dd style={{ color: validation.new_high_critical_count ? 'var(--crit)' : undefined }}>{validation.new_high_critical_count} high or critical</dd></>}
                    {validation && <><dt>Sandbox</dt><dd style={{ color: validation.accepted ? 'var(--good)' : 'var(--crit)' }}>{validation.accepted ? 'Passes' : 'Rejected'}</dd></>}
                    <dt>Files</dt><dd>{new Set(plan.patches.filter((p) => selected.has(p.patch_id)).map((p) => p.file_path)).size} touched</dd>
                    <dt>Backup</dt><dd>A copy of each file is saved first</dd>
                    <dt>If it fails</dt><dd>The whole batch is rolled back</dd>
                  </dl>
                  {confirming ? (
                    <div className="confirm">
                      <span>Write <strong>{selected.size} file edit{selected.size === 1 ? '' : 's'}</strong> to <strong className="mono">{projectPath}</strong>? Each file is backed up first, and the whole batch is rolled back if any edited file no longer parses.</span>
                      {destructive && <span style={{ color: 'var(--high)' }}>This includes deleting measures. Reports outside this project that use them will break.</span>}
                      <div className="actions">
                        <button className={`btn ${destructive ? 'btn-danger' : 'btn-primary'}`} onClick={apply} disabled={applying}>{applying ? 'Writing…' : `Write ${selected.size} file edit${selected.size === 1 ? '' : 's'}`}</button>
                        <button className="btn" onClick={() => setConfirming(false)} disabled={applying}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <button className="btn btn-primary apply-btn" disabled={!selected.size || !validation?.accepted} onClick={() => setConfirming(true)}>
                      <Wrench aria-hidden="true" />Apply {byRule.filter(([, ps]) => ps.some((p) => selected.has(p.patch_id))).length} fix{byRule.filter(([, ps]) => ps.some((p) => selected.has(p.patch_id))).length === 1 ? '' : 'es'}
                    </button>
                  )}
                  <p className="muted small">The score is a prediction from a trial run on a copy. The real score is measured after applying.</p>
                </div>
              </aside>
            )}
          </div>
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
                  <td style={{ color: h.rollback_executed || h.decision === 'ROLLBACK_FAILED' ? 'var(--sev-critical)' : 'var(--good)' }}>
                    {h.decision === 'ROLLBACK_FAILED' ? 'Rollback failed' : h.rollback_executed ? 'Rolled back' : h.decision.toLowerCase()}
                  </td>
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
