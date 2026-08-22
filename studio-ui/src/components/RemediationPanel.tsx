import React, { useState, useEffect } from 'react';
import {
  Wrench,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileCode,
  ArrowRight,
  RefreshCw,
  History,
  CheckSquare,
  Square,
  Play,
  RotateCcw,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Clock,
  Layers,
} from 'lucide-react';

interface PatchChunk {
  start_line: number;
  end_line: number;
  original_text: string;
  replacement_text: string;
}

interface PatchEvidence {
  rule_id: string;
  safety: string;
  semantic_risk: string;
  affected_objects: string[];
  expected_resolution: string;
}

interface Patch {
  patch_id: string;
  rule_id: string;
  file_path: string;
  safety: string;
  state: string;
  rationale: string;
  evidence: PatchEvidence;
  chunks: PatchChunk[];
}

interface ValidationResult {
  accepted: boolean;
  before_score: number;
  after_score: number;
  score_delta: number;
  resolved_count: number;
  new_high_critical_count: number;
  rejection_reasons: string[];
}

interface RemediationPlanData {
  model_path: string;
  created_at: string;
  patches: Patch[];
  conflicts: any[];
}

interface ManifestRecord {
  manifest_id: string;
  created_at: string;
  decision: string;
  actor: string;
  before_score: number;
  after_score: number;
  score_delta: number;
  applied_count: number;
  rollback_executed: boolean;
}

interface RemediationPanelProps {
  projectPath: string;
  currentScore: number;
  onProjectRefreshed?: () => void;
}

export const RemediationPanel: React.FC<RemediationPanelProps> = ({
  projectPath,
  currentScore,
  onProjectRefreshed,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'proposals' | 'history'>('proposals');
  const [loading, setLoading] = useState<boolean>(false);
  const [applying, setApplying] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [planData, setPlanData] = useState<RemediationPlanData | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [selectedPatchIds, setSelectedPatchIds] = useState<Set<string>>(new Set());
  const [expandedPatches, setExpandedPatches] = useState<Set<string>>(new Set());

  const [history, setHistory] = useState<ManifestRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);

  // Fetch candidate remediation plan from FastAPI
  const fetchPlan = async () => {
    if (!projectPath) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/remediation/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${res.status}`);
      }
      const data = await res.json();
      setPlanData(data.plan);
      setValidation(data.validation);

      // Select all candidate patches by default
      const patchIds = new Set<string>((data.plan.patches || []).map((p: Patch) => p.patch_id));
      setSelectedPatchIds(patchIds);
      setExpandedPatches(new Set(patchIds));
    } catch (err: any) {
      setError(err.message || 'Failed to generate remediation plan');
    } finally {
      setLoading(false);
    }
  };

  // Fetch history list
  const fetchHistory = async () => {
    if (!projectPath) return;
    setHistoryLoading(true);
    try {
      const res = await fetch(`/api/remediation/history?project_path=${encodeURIComponent(projectPath)}`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data.history || []);
      }
    } catch (err) {
      console.error('Failed to fetch remediation history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchPlan();
    fetchHistory();
  }, [projectPath]);

  const toggleSelectAll = () => {
    if (!planData?.patches) return;
    if (selectedPatchIds.size === planData.patches.length) {
      setSelectedPatchIds(new Set());
    } else {
      setSelectedPatchIds(new Set(planData.patches.map((p) => p.patch_id)));
    }
  };

  const togglePatchSelection = (patchId: string) => {
    const next = new Set(selectedPatchIds);
    if (next.has(patchId)) {
      next.delete(patchId);
    } else {
      next.add(patchId);
    }
    setSelectedPatchIds(next);
  };

  const toggleExpandPatch = (patchId: string) => {
    const next = new Set(expandedPatches);
    if (next.has(patchId)) {
      next.delete(patchId);
    } else {
      next.add(patchId);
    }
    setExpandedPatches(next);
  };

  // Apply selected patches
  const handleApply = async () => {
    if (!projectPath || selectedPatchIds.size === 0) return;
    setApplying(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await fetch('/api/remediation/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_path: projectPath,
          patch_ids: Array.from(selectedPatchIds),
          backup: true,
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.manifest?.rejection_reasons?.join(', ') || data.detail || 'Remediation failed');
      }

      setSuccessMessage(
        `Successfully applied ${data.manifest?.applied_patches?.length || selectedPatchIds.size} patch(es)! Score improved to ${data.manifest?.after_score?.toFixed(1)}.`
      );

      // Re-fetch plan, history and trigger global refresh
      fetchPlan();
      fetchHistory();
      if (onProjectRefreshed) {
        onProjectRefreshed();
      }
    } catch (err: any) {
      setError(err.message || 'Remediation apply failed');
    } finally {
      setApplying(false);
    }
  };

  const patches = planData?.patches || [];
  const candidateCount = patches.length;
  const delta = validation ? validation.after_score - validation.before_score : 0;

  return (
    <div className="space-y-5 font-mono">
      {/* Top Banner Card */}
      <div
        className="p-5 rounded-lg border flex flex-col md:flex-row md:items-center justify-between gap-4 select-none"
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderColor: 'var(--border-hairline)',
        }}
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
              Safe Automated Remediation Engine
            </h2>
            <span
              className="text-[10px] px-2 py-0.5 rounded border uppercase font-bold"
              style={{
                backgroundColor: 'var(--accent-muted)',
                borderColor: 'var(--accent)',
                color: 'var(--accent)',
              }}
            >
              Sandbox Verified
            </span>
          </div>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Two-tier SHA-256 anchored code transformations with atomic backup and rollback guarantees.
          </p>
        </div>

        {/* Action Controls & Sub-tabs */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex rounded border p-0.5" style={{ backgroundColor: 'var(--bg-canvas)', borderColor: 'var(--border-hairline)' }}>
            <button
              onClick={() => setActiveSubTab('proposals')}
              className="px-3 py-1.5 rounded text-xs font-bold transition flex items-center gap-1.5"
              style={{
                backgroundColor: activeSubTab === 'proposals' ? 'var(--bg-surface)' : 'transparent',
                color: activeSubTab === 'proposals' ? 'var(--accent)' : 'var(--text-muted)',
              }}
            >
              <Wrench className="w-3.5 h-3.5" />
              <span>Proposals ({candidateCount})</span>
            </button>
            <button
              onClick={() => {
                setActiveSubTab('history');
                fetchHistory();
              }}
              className="px-3 py-1.5 rounded text-xs font-bold transition flex items-center gap-1.5"
              style={{
                backgroundColor: activeSubTab === 'history' ? 'var(--bg-surface)' : 'transparent',
                color: activeSubTab === 'history' ? 'var(--accent)' : 'var(--text-muted)',
              }}
            >
              <History className="w-3.5 h-3.5" />
              <span>Audit Log ({history.length})</span>
            </button>
          </div>

          <button
            onClick={fetchPlan}
            disabled={loading}
            className="p-2 rounded border transition"
            title="Re-run sandbox validation"
            style={{
              backgroundColor: 'var(--bg-canvas)',
              borderColor: 'var(--border-hairline)',
              color: 'var(--text-secondary)',
            }}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div
          className="p-3.5 rounded border text-xs flex items-center gap-2.5 font-mono"
          style={{
            backgroundColor: 'var(--severity-critical-bg)',
            borderColor: 'var(--severity-critical-border)',
            color: 'var(--severity-critical)',
          }}
        >
          <XCircle className="w-4 h-4 shrink-0" />
          <span><strong>Remediation Error:</strong> {error}</span>
        </div>
      )}

      {successMessage && (
        <div
          className="p-3.5 rounded border text-xs flex items-center gap-2.5 font-mono"
          style={{
            backgroundColor: 'var(--accent-muted)',
            borderColor: 'var(--accent)',
            color: 'var(--accent)',
          }}
        >
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span><strong>Success:</strong> {successMessage}</span>
        </div>
      )}

      {/* PROPOSALS VIEW */}
      {activeSubTab === 'proposals' && (
        <div className="space-y-4">
          {/* Score Impact Projection Card */}
          {validation && (
            <div
              className="p-4 rounded-lg border grid grid-cols-2 md:grid-cols-4 gap-4"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <div>
                <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                  Current Score
                </div>
                <div className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                  {validation.before_score.toFixed(1)} <span className="text-xs font-normal">/ 100</span>
                </div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                  Projected Score
                </div>
                <div className="text-xl font-bold font-mono flex items-center gap-1.5" style={{ color: 'var(--accent)' }}>
                  <span>{validation.after_score.toFixed(1)}</span>
                  {delta > 0 && (
                    <span className="text-xs px-1.5 py-0.5 rounded font-bold" style={{ backgroundColor: 'var(--accent-muted)' }}>
                      +{delta.toFixed(1)}
                    </span>
                  )}
                </div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                  Resolved Findings
                </div>
                <div className="text-xl font-bold font-mono" style={{ color: 'var(--accent)' }}>
                  {validation.resolved_count} <span className="text-xs font-normal" style={{ color: 'var(--text-muted)' }}>defects</span>
                </div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                  Sandbox Gate
                </div>
                <div className="text-sm font-bold font-mono flex items-center gap-1 mt-1">
                  {validation.accepted ? (
                    <span className="text-emerald-500 flex items-center gap-1">
                      <CheckCircle2 className="w-4 h-4" /> PASSED
                    </span>
                  ) : (
                    <span className="text-red-500 flex items-center gap-1">
                      <XCircle className="w-4 h-4" /> REJECTED
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Action Bar */}
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <button
                onClick={toggleSelectAll}
                className="text-xs flex items-center gap-1.5 px-2.5 py-1 rounded border transition"
                style={{
                  backgroundColor: 'var(--bg-surface)',
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--text-secondary)',
                }}
              >
                {selectedPatchIds.size === candidateCount ? (
                  <CheckSquare className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
                ) : (
                  <Square className="w-3.5 h-3.5" />
                )}
                <span>Select All ({selectedPatchIds.size}/{candidateCount})</span>
              </button>
            </div>

            <button
              onClick={handleApply}
              disabled={applying || selectedPatchIds.size === 0 || loading}
              className="px-4 py-2 rounded text-xs font-bold font-mono flex items-center gap-2 transition shadow-sm disabled:opacity-50"
              style={{
                backgroundColor: 'var(--accent)',
                color: '#fff',
              }}
            >
              {applying ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Applying Patches & Rescanning...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Apply Selected Patches ({selectedPatchIds.size})</span>
                </>
              )}
            </button>
          </div>

          {/* Patch Cards List */}
          {loading ? (
            <div className="py-20 text-center space-y-2">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto" style={{ color: 'var(--accent)' }} />
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Running sandbox Before → After validation...
              </p>
            </div>
          ) : patches.length === 0 ? (
            <div
              className="p-12 rounded-lg border text-center space-y-2"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <CheckCircle2 className="w-8 h-8 mx-auto" style={{ color: 'var(--accent)' }} />
              <h4 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                No automated remediations needed
              </h4>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                This model is already compliant with certified safe remediation rules.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {patches.map((patch, idx) => {
                const isSelected = selectedPatchIds.has(patch.patch_id);
                const isExpanded = expandedPatches.has(patch.patch_id);
                const riskColor =
                  patch.evidence.semantic_risk === 'LOW'
                    ? 'text-emerald-500'
                    : patch.evidence.semantic_risk === 'MEDIUM'
                    ? 'text-amber-500'
                    : 'text-red-500';

                return (
                  <div
                    key={patch.patch_id}
                    className="rounded-lg border transition overflow-hidden"
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      borderColor: isSelected ? 'var(--accent)' : 'var(--border-hairline)',
                    }}
                  >
                    {/* Patch Header Row */}
                    <div className="p-3.5 flex items-center justify-between gap-3 select-none">
                      <div className="flex items-center gap-3 min-w-0">
                        <button
                          onClick={() => togglePatchSelection(patch.patch_id)}
                          className="shrink-0"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                          ) : (
                            <Square className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                          )}
                        </button>

                        <div className="space-y-0.5 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
                              [{idx + 1}] {patch.patch_id}
                            </span>
                            <span
                              className="text-[10px] px-2 py-0.2 rounded border font-bold uppercase"
                              style={{
                                backgroundColor: 'var(--bg-canvas)',
                                borderColor: 'var(--border-strong)',
                                color: 'var(--text-secondary)',
                              }}
                            >
                              {patch.rule_id}
                            </span>
                            <span className={`text-[10px] font-bold uppercase ${riskColor}`}>
                              {patch.evidence.semantic_risk} RISK
                            </span>
                          </div>
                          <div className="text-[11px] truncate" style={{ color: 'var(--text-muted)' }}>
                            Target: <span className="font-bold">{patch.file_path.split(/[\\/]/).pop()}</span> — {patch.rationale}
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => toggleExpandPatch(patch.patch_id)}
                        className="p-1 rounded hover:bg-black/10 transition shrink-0"
                      >
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                        ) : (
                          <ChevronRight className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                        )}
                      </button>
                    </div>

                    {/* Expandable Diff & Detail Section */}
                    {isExpanded && (
                      <div
                        className="p-4 border-t space-y-3"
                        style={{
                          backgroundColor: 'var(--bg-canvas)',
                          borderColor: 'var(--border-hairline)',
                        }}
                      >
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                          <div>
                            <span className="text-[10px] uppercase font-bold" style={{ color: 'var(--text-muted)' }}>
                              Expected Resolution:
                            </span>
                            <div className="mt-0.5" style={{ color: 'var(--accent)' }}>
                              {patch.evidence.expected_resolution}
                            </div>
                          </div>
                          {patch.evidence.affected_objects?.length > 0 && (
                            <div>
                              <span className="text-[10px] uppercase font-bold" style={{ color: 'var(--text-muted)' }}>
                                Affected Objects:
                              </span>
                              <div className="mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                                {patch.evidence.affected_objects.join(', ')}
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Diff Preview */}
                        <div>
                          <div className="text-[10px] uppercase font-bold mb-1.5" style={{ color: 'var(--text-muted)' }}>
                            Proposed Unified Diff:
                          </div>
                          <div
                            className="p-3 rounded border font-mono text-xs overflow-x-auto space-y-1"
                            style={{
                              backgroundColor: '#0d1117',
                              borderColor: 'var(--border-hairline)',
                            }}
                          >
                            {patch.chunks.map((chunk, cIdx) => (
                              <div key={cIdx} className="space-y-0.5">
                                <div className="text-cyan-400 text-[11px]">
                                  @@ Lines {chunk.start_line}..{chunk.end_line} @@
                                </div>
                                {chunk.original_text.split('\n').map((l, lIdx) => (
                                  <div key={`orig-${lIdx}`} className="text-red-400">
                                    - {l}
                                  </div>
                                ))}
                                {chunk.replacement_text.split('\n').map((l, lIdx) => (
                                  <div key={`repl-${lIdx}`} className="text-emerald-400">
                                    + {l}
                                  </div>
                                ))}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* HISTORY / AUDIT LOG VIEW */}
      {activeSubTab === 'history' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-xs uppercase tracking-wider font-bold" style={{ color: 'var(--text-muted)' }}>
              Remediation Audit Records ({history.length})
            </h3>
            <button
              onClick={fetchHistory}
              className="text-xs px-2.5 py-1 rounded border transition flex items-center gap-1.5"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
                color: 'var(--text-secondary)',
              }}
            >
              <RefreshCw className={`w-3 h-3 ${historyLoading ? 'animate-spin' : ''}`} />
              <span>Refresh History</span>
            </button>
          </div>

          {historyLoading ? (
            <div className="py-16 text-center">
              <RefreshCw className="w-5 h-5 animate-spin mx-auto" style={{ color: 'var(--accent)' }} />
            </div>
          ) : history.length === 0 ? (
            <div
              className="p-12 rounded-lg border text-center space-y-2"
              style={{
                backgroundColor: 'var(--bg-surface)',
                borderColor: 'var(--border-hairline)',
              }}
            >
              <Clock className="w-7 h-7 mx-auto" style={{ color: 'var(--text-muted)' }} />
              <h4 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                No audit records found
              </h4>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                No remediation patches have been applied to this project yet.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {history.map((record) => {
                const isAccepted = record.decision === 'ACCEPTED';
                const isRollback = record.rollback_executed;

                return (
                  <div
                    key={record.manifest_id}
                    className="p-4 rounded-lg border flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      borderColor: 'var(--border-hairline)',
                    }}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
                          {record.manifest_id}
                        </span>
                        <span
                          className={`text-[10px] px-2 py-0.2 rounded border font-bold uppercase ${
                            isAccepted
                              ? 'text-emerald-500 border-emerald-500/30 bg-emerald-500/10'
                              : 'text-red-500 border-red-500/30 bg-red-500/10'
                          }`}
                        >
                          {record.decision}
                        </span>
                        {isRollback && (
                          <span className="text-[10px] px-2 py-0.2 rounded border font-bold uppercase text-amber-500 border-amber-500/30 bg-amber-500/10">
                            ROLLED BACK
                          </span>
                        )}
                      </div>
                      <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                        Created: {new Date(record.created_at).toLocaleString()} • Actor: <span className="font-bold">{record.actor}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <div className="text-[10px] uppercase font-bold" style={{ color: 'var(--text-muted)' }}>
                          Score Impact
                        </div>
                        <div className="font-bold font-mono">
                          {record.before_score.toFixed(1)} →{' '}
                          <span style={{ color: 'var(--accent)' }}>{record.after_score.toFixed(1)}</span>
                          <span className="ml-1 text-[11px] text-emerald-500">
                            ({record.score_delta > 0 ? `+${record.score_delta.toFixed(1)}` : record.score_delta.toFixed(1)})
                          </span>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-[10px] uppercase font-bold" style={{ color: 'var(--text-muted)' }}>
                          Applied Patches
                        </div>
                        <div className="font-bold font-mono">{record.applied_count}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
